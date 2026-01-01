"""Tests for Navirec services module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
