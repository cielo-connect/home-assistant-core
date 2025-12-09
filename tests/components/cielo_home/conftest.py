"""Common fixtures for the Cielo Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_API_KEY


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for the Cielo Home integration."""
    with patch(
        "homeassistant.components.cielo_home.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def entry_config() -> dict:
    """Return valid config for a Cielo Home entry."""
    return {
        CONF_API_KEY: "test-api-key",
        "token": "valid-test-token",
    }


@pytest.fixture
def mock_cielo_client() -> Generator[AsyncMock]:
    """Mock the CieloClient to prevent actual API calls during init."""
    with patch(
        "homeassistant.components.cielo_home.coordinator.CieloClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value

        # 1. Create a non-async Mock for the data object returned by the API
        # This represents the CieloData object or the raw response wrapper
        mock_data = MagicMock()
        mock_data.raw = {}
        mock_data.parsed = {}

        # 2. Configure the async method to return this object when awaited
        client.get_devices_data.return_value = mock_data

        yield client
