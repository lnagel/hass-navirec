"""Tests for Navirec binary sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.navirec.binary_sensor import (
    BINARY_SENSOR_DEVICE_CLASSES,
    NavirecBinarySensor,
)
from custom_components.navirec.models import (
    Interpretation,
    Sensor,
    Vehicle,
    VehicleState,
)


def find_sensor_by_interpretation(
    sensors: list[dict[str, Any]], interpretation: str
) -> dict[str, Any] | None:
    """Find a sensor with given interpretation from fixture data."""
    for sensor in sensors:
        if sensor.get("interpretation") == interpretation:
            return sensor
    return None


def find_vehicle_by_id(
    vehicles: list[dict[str, Any]], vehicle_id: str
) -> dict[str, Any] | None:
    """Find a vehicle by ID from fixture data."""
    for vehicle in vehicles:
        if vehicle.get("id") == vehicle_id:
            return vehicle
    return None


def find_interpretation_by_key(
    interpretations: list[dict[str, Any]], key: str
) -> dict[str, Any] | None:
    """Find an interpretation by key from fixture data."""
    for interp in interpretations:
        if interp.get("key") == key:
            return interp
    return None


def extract_vehicle_id_from_url(url: str) -> str:
    """Extract vehicle ID from vehicle URL."""
    return url.split("/vehicles/")[1].rstrip("/")


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    return MagicMock()


class TestNavirecBinarySensor:
    """Tests for NavirecBinarySensor."""

    def test_ignition_sensor_device_class(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test ignition sensor has correct device class."""
        ignition_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "ignition"
        )
        assert ignition_sensor_data is not None, "No ignition sensor in fixtures"

        vehicle_id = extract_vehicle_id_from_url(ignition_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None, f"No vehicle {vehicle_id} in fixtures"

        ignition_interp_data = find_interpretation_by_key(
            interpretations_fixture, "ignition"
        )
        assert ignition_interp_data is not None, (
            "No ignition interpretation in fixtures"
        )

        ignition_sensor = Sensor.model_validate(ignition_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(ignition_interp_data)

        # Find matching state
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        vehicle_state = VehicleState.model_validate(state_data) if state_data else None

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state

        sensor = NavirecBinarySensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=ignition_sensor,
            interpretation=interpretation,
            device_class=BINARY_SENSOR_DEVICE_CLASSES.get("ignition"),
        )

        assert sensor.device_class == BinarySensorDeviceClass.POWER

    def test_ignition_is_on(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test ignition sensor returns correct boolean value."""
        ignition_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "ignition"
        )
        assert ignition_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(ignition_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        ignition_interp_data = find_interpretation_by_key(
            interpretations_fixture, "ignition"
        )
        assert ignition_interp_data is not None

        ignition_sensor = Sensor.model_validate(ignition_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(ignition_interp_data)

        # Find matching state with ignition
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        assert state_data is not None, "No state for vehicle with ignition sensor"
        vehicle_state = VehicleState.model_validate(state_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state

        sensor = NavirecBinarySensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=ignition_sensor,
            interpretation=interpretation,
            device_class=BINARY_SENSOR_DEVICE_CLASSES.get("ignition"),
        )

        # Value should match what's in the state
        expected_ignition = state_data.get("ignition")
        if expected_ignition is not None:
            assert sensor.is_on == expected_ignition

    def test_sensor_unique_id(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test binary sensor unique ID generation."""
        ignition_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "ignition"
        )
        assert ignition_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(ignition_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        ignition_interp_data = find_interpretation_by_key(
            interpretations_fixture, "ignition"
        )
        assert ignition_interp_data is not None

        ignition_sensor = Sensor.model_validate(ignition_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(ignition_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecBinarySensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=ignition_sensor,
            interpretation=interpretation,
            device_class=BINARY_SENSOR_DEVICE_CLASSES.get("ignition"),
        )

        assert vehicle_id in sensor.unique_id

    def test_sensor_enabled_by_default(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor enabled by default based on show_in_map."""
        # Find an ignition sensor with show_in_map attribute
        ignition_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "ignition"
        )
        assert ignition_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(ignition_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        ignition_interp_data = find_interpretation_by_key(
            interpretations_fixture, "ignition"
        )
        assert ignition_interp_data is not None

        ignition_sensor = Sensor.model_validate(ignition_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(ignition_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecBinarySensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=ignition_sensor,
            interpretation=interpretation,
            device_class=BINARY_SENSOR_DEVICE_CLASSES.get("ignition"),
        )

        # show_in_map determines enabled by default
        expected_enabled = ignition_sensor_data.get("show_in_map", False)
        assert sensor.entity_registry_enabled_default == expected_enabled

    def test_sensor_no_state_returns_none(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor returns None when no state available."""
        ignition_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "ignition"
        )
        assert ignition_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(ignition_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        ignition_interp_data = find_interpretation_by_key(
            interpretations_fixture, "ignition"
        )
        assert ignition_interp_data is not None

        ignition_sensor = Sensor.model_validate(ignition_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(ignition_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecBinarySensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=ignition_sensor,
            interpretation=interpretation,
            device_class=BINARY_SENSOR_DEVICE_CLASSES.get("ignition"),
        )

        assert sensor.is_on is None
