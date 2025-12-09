"""Test the Cielo Home initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.cielo_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    hass: HomeAssistant, entry_config: dict, mock_cielo_client: AsyncMock
) -> None:
    """Test successful setup and unload of the config entry."""

    # 1. Create the config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_config,
        unique_id="test_user@example.com",
        version=1,
    )
    entry.add_to_hass(hass)

    # 2. Test Setup (mock_cielo_client fixture handles the API mock)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify entry is loaded successfully
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # 3. Test Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Verify entry is unloaded
    assert entry.state is ConfigEntryState.NOT_LOADED
