"""Tests for Navirec integration setup and unload."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navirec.const import DOMAIN


@pytest.fixture
def mock_config_entry(
    mock_config_entry_data: dict[str, Any],
    accounts_fixture: list[dict[str, Any]],
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=accounts_fixture[0]["name"],
        data=mock_config_entry_data,
        unique_id=accounts_fixture[0]["id"],
    )


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_start_streaming = AsyncMock()
    coordinator.async_stop_streaming = AsyncMock()
    coordinator.get_vehicle_state = MagicMock(return_value=None)
    coordinator.connected = False
    return coordinator


@pytest.mark.asyncio
async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    accounts_fixture: list[dict[str, Any]],
    vehicles_fixture: list[dict[str, Any]],
    sensors_fixture: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        # Use the proper config entries setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Verify API client was called
        mock_api_client.async_get_accounts.assert_called_once()
        mock_api_client.async_get_vehicles.assert_called_once()
        mock_api_client.async_get_sensors.assert_called_once()

        # Verify coordinator was started
        mock_coordinator.async_start_streaming.assert_called_once()

        # Verify runtime data was set
        assert mock_config_entry.runtime_data is not None
        assert mock_config_entry.runtime_data.account_id == accounts_fixture[0]["id"]
        assert mock_config_entry.runtime_data.account_name == accounts_fixture[0]["name"]
        assert len(mock_config_entry.runtime_data.vehicles) == len(vehicles_fixture)
        assert len(mock_config_entry.runtime_data.sensors) == len(sensors_fixture)


@pytest.mark.asyncio
async def test_setup_entry_creates_vehicles_dict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    vehicles_fixture: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test that setup creates proper vehicles dictionary."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify vehicles are keyed by ID
        for vehicle_data in vehicles_fixture:
            vehicle_id = vehicle_data["id"]
            assert vehicle_id in mock_config_entry.runtime_data.vehicles
            vehicle = mock_config_entry.runtime_data.vehicles[vehicle_id]
            assert str(vehicle.id) == vehicle_id


@pytest.mark.asyncio
async def test_setup_entry_groups_sensors_by_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    sensors_fixture: list[dict[str, Any]],
    vehicles_fixture: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test that setup groups sensors by vehicle ID."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify sensors_by_vehicle is populated
        sensors_by_vehicle = mock_config_entry.runtime_data.sensors_by_vehicle
        assert len(sensors_by_vehicle) > 0

        # Each sensor in the dict should belong to a vehicle we know about
        vehicle_ids = set(mock_config_entry.runtime_data.vehicles.keys())
        for vehicle_id in sensors_by_vehicle:
            assert vehicle_id in vehicle_ids


@pytest.mark.asyncio
async def test_unload_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    enable_custom_integrations: None,
) -> None:
    """Test successful unload of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        # First set up the entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Then unload it
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        # Verify streaming was stopped
        mock_coordinator.async_stop_streaming.assert_called_once()


@pytest.mark.asyncio
async def test_unload_entry_no_runtime_data(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    accounts_fixture: list[dict[str, Any]],
    mock_config_entry_data: dict[str, Any],
) -> None:
    """Test unload when entry was never loaded successfully."""
    # Create a config entry that's not loaded
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data=mock_config_entry_data,
        unique_id=accounts_fixture[0]["id"],
    )
    entry.add_to_hass(hass)

    # Try to unload - should not crash even without runtime_data
    # Note: This scenario happens when setup fails before setting runtime_data
    result = await hass.config_entries.async_unload(entry.entry_id)

    # Should return True (no platforms to unload)
    assert result is True


@pytest.mark.asyncio
async def test_setup_account_name_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    accounts_fixture: list[dict[str, Any]],
    vehicles_fixture: list[dict[str, Any]],
    sensors_fixture: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test that account ID is used as fallback when name is missing."""
    mock_config_entry.add_to_hass(hass)

    # Create a mock API client that returns account without name
    mock_api_client = MagicMock()
    account_without_name = {"id": accounts_fixture[0]["id"]}  # No name field
    mock_api_client.async_get_accounts = AsyncMock(return_value=[account_without_name])
    mock_api_client.async_get_vehicles = AsyncMock(return_value=vehicles_fixture)
    mock_api_client.async_get_sensors = AsyncMock(return_value=sensors_fixture)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Account name should fall back to account ID
        assert mock_config_entry.runtime_data.account_name == accounts_fixture[0]["id"]


@pytest.mark.asyncio
async def test_setup_account_not_found_uses_id_as_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    mock_config_entry_data: dict[str, Any],
    vehicles_fixture: list[dict[str, Any]],
    sensors_fixture: list[dict[str, Any]],
    enable_custom_integrations: None,
) -> None:
    """Test that account ID is used as name when account not in response."""
    mock_config_entry.add_to_hass(hass)

    # Create a mock API client that returns different account
    mock_api_client = MagicMock()
    different_account = {"id": "different-id", "name": "Different Account"}
    mock_api_client.async_get_accounts = AsyncMock(return_value=[different_account])
    mock_api_client.async_get_vehicles = AsyncMock(return_value=vehicles_fixture)
    mock_api_client.async_get_sensors = AsyncMock(return_value=sensors_fixture)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Account name should fall back to configured account ID
        from custom_components.navirec.const import CONF_ACCOUNT_ID

        expected_id = mock_config_entry_data[CONF_ACCOUNT_ID]
        assert mock_config_entry.runtime_data.account_name == expected_id


@pytest.mark.asyncio
async def test_setup_platforms_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    enable_custom_integrations: None,
) -> None:
    """Test that all expected platforms are set up."""
    from homeassistant.helpers import device_registry as dr

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entry is loaded
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Platforms should be loaded (entities registered)
        # We verify this by checking that devices exist for vehicles
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())

        # Should have devices for vehicles
        assert len(devices) > 0


@pytest.mark.asyncio
async def test_setup_and_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    mock_coordinator: MagicMock,
    enable_custom_integrations: None,
) -> None:
    """Test that config entry can be reloaded."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.navirec.NavirecApiClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.navirec.NavirecCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.navirec.async_get_loaded_integration",
        ) as mock_integration,
    ):
        mock_integration.return_value = MagicMock()

        # Initial setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        mock_coordinator.async_start_streaming.assert_called_once()

        # Reload
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Streaming should have been stopped and restarted
        mock_coordinator.async_stop_streaming.assert_called_once()
        assert mock_coordinator.async_start_streaming.call_count == 2
