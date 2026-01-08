"""Tests for Navirec device tracker."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from homeassistant.components.device_tracker import SourceType

from custom_components.navirec.device_tracker import NavirecDeviceTracker
from custom_components.navirec.models import Vehicle, VehicleState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_vehicle() -> dict:
    """Load a sample vehicle from fixtures."""
    with open(FIXTURES_DIR / "vehicles.json") as f:
        vehicles = json.load(f)
    return vehicles[0] if vehicles else {}


@pytest.fixture
def sample_vehicle_state() -> dict:
    """Load a sample vehicle state from fixtures."""
    with open(FIXTURES_DIR / "last_vehicle_states.json") as f:
        states = json.load(f)
    return states[0] if states else {}


@pytest.fixture
def mock_vehicle(sample_vehicle) -> Vehicle:
    """Create a Vehicle model from fixture."""
    return Vehicle.model_validate(sample_vehicle)


@pytest.fixture
def mock_vehicle_state(sample_vehicle_state) -> VehicleState:
    """Create a VehicleState model from fixture."""
    return VehicleState.model_validate(sample_vehicle_state)


@pytest.fixture
def mock_coordinator(mock_vehicle_state) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.get_vehicle_state.return_value = mock_vehicle_state
    coordinator.connected = True
    return coordinator


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    return MagicMock()


@pytest.fixture
def vehicle_id(sample_vehicle) -> str:
    """Extract vehicle ID from sample vehicle."""
    return sample_vehicle["id"]


class TestNavirecDeviceTracker:
    """Tests for NavirecDeviceTracker."""

    def test_source_type(
        self, mock_coordinator, mock_config_entry, mock_vehicle, vehicle_id
    ) -> None:
        """Test that source type is GPS."""
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        assert tracker.source_type == SourceType.GPS

    def test_latitude(
        self,
        mock_coordinator,
        mock_config_entry,
        mock_vehicle,
        vehicle_id,
        sample_vehicle_state,
    ) -> None:
        """Test latitude property."""
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        # GeoJSON is [longitude, latitude], so latitude is coords[1]
        expected_lat = sample_vehicle_state["location"]["coordinates"][1]
        assert tracker.latitude == expected_lat

    def test_longitude(
        self,
        mock_coordinator,
        mock_config_entry,
        mock_vehicle,
        vehicle_id,
        sample_vehicle_state,
    ) -> None:
        """Test longitude property."""
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        # GeoJSON is [longitude, latitude], so longitude is coords[0]
        expected_lon = sample_vehicle_state["location"]["coordinates"][0]
        assert tracker.longitude == expected_lon

    def test_extra_state_attributes(
        self,
        mock_coordinator,
        mock_config_entry,
        mock_vehicle,
        vehicle_id,
        sample_vehicle_state,
    ) -> None:
        """Test extra state attributes."""
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        attrs = tracker.extra_state_attributes

        assert attrs["name_display"] == "TEST-1"
        assert attrs["registration"] == "TEST-1"
        assert attrs["speed"] == sample_vehicle_state["speed"]
        assert attrs["heading"] == sample_vehicle_state["heading"]
        assert attrs["altitude"] == sample_vehicle_state["altitude"]
        assert "activity" in attrs
        assert "last_update" in attrs

    def test_unique_id(
        self, mock_coordinator, mock_config_entry, mock_vehicle, vehicle_id
    ) -> None:
        """Test unique ID generation."""
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        assert tracker.unique_id == f"{vehicle_id}_location"

    def test_no_state_returns_none(
        self, mock_coordinator, mock_config_entry, mock_vehicle, vehicle_id
    ) -> None:
        """Test that None is returned when no state is available."""
        mock_coordinator.get_vehicle_state.return_value = None

        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        assert tracker.latitude is None
        assert tracker.longitude is None
        # Label is always present (from vehicle data, not state)
        assert tracker.extra_state_attributes == {
            "name_display": "TEST-1",
            "registration": "TEST-1",
        }

    def test_entity_category_is_not_diagnostic(
        self, mock_coordinator, mock_config_entry, mock_vehicle, vehicle_id
    ) -> None:
        """Test that entity category is None (primary), not diagnostic.

        Home Assistant's BaseTrackerEntity defaults to EntityCategory.DIAGNOSTIC.
        We override this to None so the device tracker appears as a primary entity.
        """
        tracker = NavirecDeviceTracker(
            coordinator=mock_coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=mock_vehicle,
        )

        # Explicitly None, not EntityCategory.DIAGNOSTIC
        assert tracker.entity_category is None
