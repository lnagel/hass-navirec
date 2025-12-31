"""Fixtures for Navirec integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.navirec.const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_API_URL,
)


@pytest.fixture
def mock_setup_entry() -> Any:
    """Override async_setup_entry."""
    with patch(
        "custom_components.navirec.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def fixtures_path() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def accounts_fixture(fixtures_path: Path) -> list[dict[str, Any]]:
    """Load accounts fixture."""
    with (fixtures_path / "accounts.json").open() as f:
        return json.load(f)


@pytest.fixture
def vehicles_fixture(fixtures_path: Path) -> list[dict[str, Any]]:
    """Load vehicles fixture."""
    with (fixtures_path / "vehicles.json").open() as f:
        return json.load(f)


@pytest.fixture
def sensors_fixture(fixtures_path: Path) -> list[dict[str, Any]]:
    """Load sensors fixture."""
    with (fixtures_path / "sensors.json").open() as f:
        return json.load(f)


@pytest.fixture
def vehicle_states_fixture(fixtures_path: Path) -> list[dict[str, Any]]:
    """Load vehicle states fixture."""
    with (fixtures_path / "last_vehicle_states.json").open() as f:
        return json.load(f)


@pytest.fixture
def mock_api_client(
    accounts_fixture: list[dict[str, Any]],
    vehicles_fixture: list[dict[str, Any]],
    sensors_fixture: list[dict[str, Any]],
) -> MagicMock:
    """Create a mock API client."""
    client = MagicMock()
    client.async_get_accounts = AsyncMock(return_value=accounts_fixture)
    client.async_get_vehicles = AsyncMock(return_value=vehicles_fixture)
    client.async_get_sensors = AsyncMock(return_value=sensors_fixture)
    client.async_validate_token = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_config_entry_data(accounts_fixture: list[dict[str, Any]]) -> dict[str, Any]:
    """Return mock config entry data."""
    return {
        CONF_API_URL: "https://api.navirec.test",
        CONF_API_TOKEN: "test-token",
        CONF_ACCOUNT_ID: accounts_fixture[0]["id"],
    }
