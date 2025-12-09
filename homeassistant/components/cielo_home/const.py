"""Constants for the Cielo Home integration."""

import asyncio
import logging
from typing import Final

from aiohttp.client_exceptions import ClientConnectionError
from cieloconnectapi.exceptions import AuthenticationError, CieloError

from homeassistant.const import Platform

# Add Final type hint
LOGGER: Final = logging.getLogger(__package__)

# Add Final and type hints to all constants
DOMAIN: Final = "cielo_home"
PLATFORMS: Final[list[Platform]] = [
    Platform.CLIMATE,
]
DEFAULT_NAME: Final = "Cielo Home"
DEFAULT_SCAN_INTERVAL: Final[int] = 60
TIMEOUT: Final[int] = 20

CIELO_ERRORS: Final[tuple] = (
    ClientConnectionError,
    asyncio.TimeoutError,
    AuthenticationError,
    CieloError,
)


class NoDevicesError(Exception):
    """No devices from Cielo api."""


class NoUsernameError(Exception):
    """No username from Cielo api."""
