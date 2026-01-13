"""Tests for Navirec services module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.navirec.models import Action, Vehicle
from custom_components.navirec.services import (
    SERVICE_EXECUTE_ACTION,
    _find_vehicle_and_action,
    async_setup_services,
    async_unload_services,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_vehicle() -> dict:
    """Load a sample vehicle from fixtures."""
    with open(FIXTURES_DIR / "vehicles.json") as f:
        vehicles = json.load(f)
    return vehicles[0] if vehicles else {}


@pytest.fixture
def sample_action() -> dict:
    """Load a sample action from fixtures."""
    with open(FIXTURES_DIR / "actions.json") as f:
        actions = json.load(f)
    return actions[0] if actions else {}


@pytest.fixture
def mock_vehicle(sample_vehicle) -> Vehicle:
    """Create a Vehicle model from fixture."""
    return Vehicle.model_validate(sample_vehicle)


@pytest.fixture
def mock_action(sample_action) -> Action:
    """Create an Action model from fixture."""
    return Action.model_validate(sample_action)


@pytest.fixture
def mock_hass(mock_vehicle, mock_action, sample_vehicle, sample_action) -> MagicMock:
    """Create a mock Home Assistant instance with config entries."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()

    # Create mock config entry
    vehicle_id = sample_vehicle["id"]

    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.client = MagicMock()
    mock_entry.runtime_data.vehicles = {vehicle_id: mock_vehicle}
    mock_entry.runtime_data.actions_by_vehicle = {vehicle_id: [mock_action]}

    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    return hass


class TestAsyncSetupServices:
    """Tests for async_setup_services function."""

    @pytest.mark.asyncio
    async def test_registers_service(self, mock_hass) -> None:
        """Test that service is registered."""
        await async_setup_services(mock_hass)

        mock_hass.services.async_register.assert_called_once()
        call_args = mock_hass.services.async_register.call_args
        assert call_args[0][0] == "navirec"
        assert call_args[0][1] == SERVICE_EXECUTE_ACTION


class TestAsyncUnloadServices:
    """Tests for async_unload_services function."""

    @pytest.mark.asyncio
    async def test_removes_service(self, mock_hass) -> None:
        """Test that service is removed."""
        await async_unload_services(mock_hass)

        mock_hass.services.async_remove.assert_called_once_with(
            "navirec", SERVICE_EXECUTE_ACTION
        )


class TestFindVehicleAndAction:
    """Tests for _find_vehicle_and_action function."""

    def test_finds_existing_vehicle_and_action(
        self, mock_hass, mock_vehicle, mock_action, sample_vehicle, sample_action
    ) -> None:
        """Test finding existing vehicle and action."""
        vehicle_id = sample_vehicle["id"]
        action_id = sample_action["id"]

        entry, vehicle, action = _find_vehicle_and_action(
            mock_hass, vehicle_id, action_id
        )

        assert entry is not None
        assert vehicle is not None
        assert action is not None
        assert vehicle.id == mock_vehicle.id
        assert action.id == mock_action.id

    def test_returns_none_for_nonexistent_vehicle(self, mock_hass) -> None:
        """Test that None is returned for nonexistent vehicle."""
        entry, vehicle, action = _find_vehicle_and_action(
            mock_hass, "nonexistent-vehicle-id", "nonexistent-action-id"
        )

        assert entry is None
        assert vehicle is None
        assert action is None

    def test_returns_none_for_nonexistent_action(
        self, mock_hass, sample_vehicle
    ) -> None:
        """Test that None is returned for nonexistent action."""
        vehicle_id = sample_vehicle["id"]

        entry, vehicle, action = _find_vehicle_and_action(
            mock_hass, vehicle_id, "nonexistent-action-id"
        )

        assert entry is None
        assert vehicle is None
        assert action is None

    def test_skips_entry_without_runtime_data(
        self, mock_hass, sample_vehicle, sample_action
    ) -> None:
        """Test that entries without runtime_data are skipped."""
        vehicle_id = sample_vehicle["id"]
        action_id = sample_action["id"]

        # Create entry without runtime_data attribute
        mock_entry_no_data = MagicMock(spec=[])  # No runtime_data attribute

        # Create entry with runtime_data but without vehicles
        mock_entry_with_data = MagicMock()
        mock_entry_with_data.runtime_data = MagicMock()
        mock_entry_with_data.runtime_data.vehicles = {}  # Empty vehicles

        mock_hass.config_entries.async_entries = MagicMock(
            return_value=[mock_entry_no_data, mock_entry_with_data]
        )

        entry, vehicle, action = _find_vehicle_and_action(
            mock_hass, vehicle_id, action_id
        )

        # Should return None since no entry has the vehicle
        assert entry is None
        assert vehicle is None
        assert action is None


class TestExecuteActionService:
    """Tests for the execute_action service call handler."""

    @pytest.fixture
    def service_hass(
        self, mock_vehicle, mock_action, sample_vehicle, sample_action
    ) -> MagicMock:
        """Create a mock Home Assistant with services that can be invoked."""
        hass = MagicMock()
        hass.bus = MagicMock()
        hass.bus.async_fire = MagicMock()

        # Store the service handler when registered
        service_handler = None

        def capture_register(domain, service, handler, schema=None):
            nonlocal service_handler
            service_handler = handler

        hass.services = MagicMock()
        hass.services.async_register = MagicMock(side_effect=capture_register)
        hass.services.async_remove = MagicMock()

        # Attach reference to get handler later
        hass._get_service_handler = lambda: service_handler

        # Create mock config entry
        vehicle_id = sample_vehicle["id"]

        mock_entry = MagicMock()
        mock_entry.runtime_data = MagicMock()
        mock_entry.runtime_data.client = MagicMock()
        mock_entry.runtime_data.vehicles = {vehicle_id: mock_vehicle}
        mock_entry.runtime_data.actions_by_vehicle = {vehicle_id: [mock_action]}

        hass.config_entries = MagicMock()
        hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

        return hass

    @pytest.mark.asyncio
    @patch("custom_components.navirec.services.execute_action", new_callable=AsyncMock)
    async def test_service_call_executes_action(
        self,
        mock_execute: AsyncMock,
        service_hass: MagicMock,
        sample_vehicle: dict,
        sample_action: dict,
    ) -> None:
        """Test successful service call execution."""
        # Register the service
        await async_setup_services(service_hass)

        # Get the registered handler
        handler = service_hass._get_service_handler()
        assert handler is not None

        # Create mock service call
        mock_call = MagicMock()
        mock_call.data = {
            "vehicle_id": sample_vehicle["id"],
            "action_id": sample_action["id"],
        }

        # Invoke the handler
        await handler(mock_call)

        # Verify execute_action was called with correct parameters
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["hass"] == service_hass
        assert call_kwargs["vehicle_id"] == sample_vehicle["id"]
        assert call_kwargs["action_id"] == sample_action["id"]

    @pytest.mark.asyncio
    async def test_service_call_raises_for_nonexistent_vehicle(
        self, service_hass: MagicMock
    ) -> None:
        """Test service call raises HomeAssistantError for nonexistent vehicle."""
        # Register the service
        await async_setup_services(service_hass)

        # Get the registered handler
        handler = service_hass._get_service_handler()

        # Create mock service call with nonexistent vehicle
        mock_call = MagicMock()
        mock_call.data = {
            "vehicle_id": "nonexistent-vehicle-id",
            "action_id": "nonexistent-action-id",
        }

        # Should raise HomeAssistantError
        with pytest.raises(HomeAssistantError) as exc_info:
            await handler(mock_call)

        assert "not found" in str(exc_info.value)
