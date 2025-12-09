"""Coordinator for Cielo integration."""

from __future__ import annotations

from datetime import timedelta
from time import time
from typing import Any, Final, NamedTuple

from aiohttp import ClientError
from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError, CieloError
from cieloconnectapi.model import CieloDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

REQUEST_REFRESH_DELAY: Final[int] = 2 * 60


class CieloData(NamedTuple):
    """Data structure for the coordinator."""

    raw: dict[str, Any]
    parsed: dict[str, CieloDevice]


class CieloDataUpdateCoordinator(DataUpdateCoordinator[CieloData]):
    """Cielo Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = CieloClient(
            api_key=entry.data[CONF_API_KEY],
            timeout=TIMEOUT,
            token=entry.data.get("token"),
            session=async_get_clientsession(hass),
        )

        self._recent_actions: dict[str, dict[str, Any]] = {}
        self._hold_seconds: Final[int] = 10

        # scan interval calculation
        seconds: Final[int] = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=seconds),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    def note_recent_action(self, device_id: str, state: dict[str, Any]) -> None:
        """Remember that we just sent an action for this device; mask stale pulls briefly."""
        self._recent_actions[device_id] = {
            "ts": int(time()),
            "state": dict(state or {}),
        }

    def _apply_recent_action_overlay(
        self, device: CieloDevice, recent: dict[str, Any]
    ) -> None:
        """Helper to apply recent action to device data without excessive nesting."""
        # 1. Update the nested ac_states dict
        if getattr(device, "ac_states", None) is not None:
            if type(device.ac_states) is dict:
                device.ac_states.update(recent)

        # 2. Update top-level properties (now outside the main loop/try block)
        for k in (
            "mode",
            "fan_speed",
            "preset",
            "swing_position",
            "power",
            "set_point",
            "heat_set_point",
            "cool_set_point",
        ):
            if k not in recent:
                continue

            val = recent[k]
            if k == "mode":
                setattr(device, "hvac_mode", val)
            elif k == "fan_speed":
                setattr(device, "fan_mode", val)
            # ... (rest of the conditions)
            # ... (ensure all original logic is here)
            elif k == "preset":
                setattr(device, "preset_mode", val)
            elif k == "swing_position":
                setattr(device, "swing_mode", val)
            elif k == "power":
                setattr(device, "device_on", val == "on")
            elif k == "set_point":
                setattr(device, "target_temp", str(val))
            elif k == "heat_set_point":
                setattr(device, "target_heat_set_point", float(val))
            elif k == "cool_set_point":
                setattr(device, "target_cool_set_point", float(val))

    async def _async_update_data(self) -> CieloData:
        """Fetch data from the API and handle auto-removal and state overlay."""
        try:
            data = await self.client.get_devices_data()

            # --- Device/Entity Auto-Removal Logic ---
            old_devices = (
                set(getattr(self.data, "parsed", {}).keys()) if self.data else set()
            )
            new_devices = set(data.parsed.keys())
            removed = old_devices - new_devices

            if removed:
                self.logger.info(
                    "Found removed devices: %s. Initiating cleanup.", removed
                )
                er_reg = er.async_get(self.hass)
                dev_reg = dr.async_get(self.hass)

                for dev_id in removed:
                    # Remove Entities
                    for ent in list(er_reg.entities.values()):
                        if (
                            ent.config_entry_id == self.config_entry.entry_id
                            and dev_id in ent.unique_id
                        ):
                            er_reg.async_remove(ent.entity_id)

                    # Remove Device
                    device_entry = dev_reg.async_get_device(
                        identifiers={(DOMAIN, dev_id)}
                    )
                    if device_entry:
                        dev_reg.async_remove_device(device_entry.id)

            # ---- Overlay recent actions to avoid stale flicker (Crucial Logic) ----
            now = int(time())
            parsed = dict(data.parsed or {})

            # Prune and overlay actions
            to_delete = []
            for dev_id, info in list(self._recent_actions.items()):  # Iterate over copy
                ts = info.get("ts", 0)
                if now - ts <= self._hold_seconds and dev_id in parsed:
                    try:
                        recent = dict(info.get("state") or {})
                        device = parsed[dev_id]
                        # Call the extracted helper function
                        self._apply_recent_action_overlay(device, recent)

                    except Exception:
                        self.logger.exception(
                            "Error applying recent action overlay for %s", dev_id
                        )
                else:
                    # Action expired
                    to_delete.append(dev_id)

            for dev_id in to_delete:
                self._recent_actions.pop(dev_id, None)

            # return the possibly-overlaid structure
            return CieloData(raw=data.raw, parsed=parsed)  # pyright: ignore[reportArgumentType]

        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (TimeoutError, CieloError, ClientError) as err:
            raise UpdateFailed(err) from err
