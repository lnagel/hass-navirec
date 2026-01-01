"""Tests for Navirec sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfSpeed, UnitOfVolume

from custom_components.navirec.models import (
    Interpretation,
    Sensor,
    Vehicle,
    VehicleState,
)
from custom_components.navirec.sensor import NavirecSensor


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


class TestNavirecSensor:
    """Tests for NavirecSensor."""

    def test_speed_sensor_device_class(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test speed sensor has correct device class."""
        # Find a speed sensor
        speed_sensor_data = find_sensor_by_interpretation(sensors_fixture, "speed")
        assert speed_sensor_data is not None, "No speed sensor in fixtures"

        vehicle_id = extract_vehicle_id_from_url(speed_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None, f"No vehicle {vehicle_id} in fixtures"

        # Get interpretation data
        speed_interp_data = find_interpretation_by_key(interpretations_fixture, "speed")
        assert speed_interp_data is not None, "No speed interpretation in fixtures"

        speed_sensor = Sensor.model_validate(speed_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(speed_interp_data)

        # Find matching state
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        vehicle_state = VehicleState.model_validate(state_data) if state_data else None

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state
        coordinator.connected = True

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=speed_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.SPEED,
            native_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=None,
        )

        assert sensor.device_class == SensorDeviceClass.SPEED
        assert sensor.native_unit_of_measurement == UnitOfSpeed.KILOMETERS_PER_HOUR
        assert sensor.state_class == SensorStateClass.MEASUREMENT

    def test_speed_sensor_native_value(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test speed sensor returns correct value."""
        speed_sensor_data = find_sensor_by_interpretation(sensors_fixture, "speed")
        assert speed_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(speed_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        speed_interp_data = find_interpretation_by_key(interpretations_fixture, "speed")
        assert speed_interp_data is not None

        speed_sensor = Sensor.model_validate(speed_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(speed_interp_data)

        # Find matching state with speed value
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        assert state_data is not None, "No state for vehicle with speed sensor"
        vehicle_state = VehicleState.model_validate(state_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state
        coordinator.connected = True

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=speed_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.SPEED,
            native_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=None,
        )

        # Speed should come from state
        expected_speed = state_data.get("speed")
        assert sensor.native_value == expected_speed

    def test_fuel_sensor_native_value(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test fuel sensor returns correct value."""
        fuel_sensor_data = find_sensor_by_interpretation(sensors_fixture, "fuel_level")
        assert fuel_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(fuel_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        fuel_interp_data = find_interpretation_by_key(
            interpretations_fixture, "fuel_level"
        )
        assert fuel_interp_data is not None

        fuel_sensor = Sensor.model_validate(fuel_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(fuel_interp_data)

        # Find matching state
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        vehicle_state = VehicleState.model_validate(state_data) if state_data else None

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state
        coordinator.connected = True

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=fuel_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.VOLUME_STORAGE,
            native_unit=UnitOfVolume.LITERS,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=None,
        )

        # Value depends on what's in the state
        if state_data and "fuel_level" in state_data:
            expected_fuel = state_data.get("fuel_level")
            assert sensor.native_value == expected_fuel
        else:
            # No fuel level in state is acceptable
            assert sensor.native_value is None

    def test_activity_sensor_enum(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test activity sensor returns string value for enum."""
        activity_sensor_data = find_sensor_by_interpretation(
            sensors_fixture, "activity"
        )
        assert activity_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(activity_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        activity_interp_data = find_interpretation_by_key(
            interpretations_fixture, "activity"
        )
        assert activity_interp_data is not None

        activity_sensor = Sensor.model_validate(activity_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(activity_interp_data)

        # Find matching state with activity
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        vehicle_state = VehicleState.model_validate(state_data) if state_data else None

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state
        coordinator.connected = True

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=activity_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.ENUM,
            native_unit=None,
            suggested_unit=None,
            state_class=None,
            options=["offline", "parking", "towing", "idling", "driving"],
            decimal_precision=None,
        )

        # Activity should be a string value, not an object
        if state_data and "activity" in state_data:
            native_value = sensor.native_value
            assert isinstance(native_value, str), (
                f"Expected string, got {type(native_value)}"
            )
            assert native_value in ["offline", "parking", "towing", "idling", "driving"]

    def test_sensor_unique_id(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor unique ID generation."""
        speed_sensor_data = find_sensor_by_interpretation(sensors_fixture, "speed")
        assert speed_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(speed_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        speed_interp_data = find_interpretation_by_key(interpretations_fixture, "speed")
        assert speed_interp_data is not None

        speed_sensor = Sensor.model_validate(speed_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(speed_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=speed_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.SPEED,
            native_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=None,
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
        # Find a sensor with show_in_map=True
        sensor_data = next(
            (s for s in sensors_fixture if s.get("show_in_map") is True), None
        )
        assert sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        interp_key = sensor_data["interpretation"]
        interp_data = find_interpretation_by_key(interpretations_fixture, interp_key)
        assert interp_data is not None

        sensor_def = Sensor.model_validate(sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=sensor_def,
            interpretation=interpretation,
            device_class=None,
            native_unit=None,
            suggested_unit=None,
            state_class=None,
            options=None,
            decimal_precision=None,
        )

        # show_in_map is True, so should be enabled
        assert sensor.entity_registry_enabled_default is True

    def test_sensor_no_state_returns_none(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor returns None when no state available."""
        speed_sensor_data = find_sensor_by_interpretation(sensors_fixture, "speed")
        assert speed_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(speed_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        speed_interp_data = find_interpretation_by_key(interpretations_fixture, "speed")
        assert speed_interp_data is not None

        speed_sensor = Sensor.model_validate(speed_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(speed_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=speed_sensor,
            interpretation=interpretation,
            device_class=SensorDeviceClass.SPEED,
            native_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=None,
        )

        assert sensor.native_value is None

    def test_sensor_decimal_precision(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor decimal precision from interpretation."""
        # Find a sensor that has decimal_places in interpretation
        fuel_sensor_data = find_sensor_by_interpretation(sensors_fixture, "fuel_level")
        assert fuel_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(fuel_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        fuel_interp_data = find_interpretation_by_key(
            interpretations_fixture, "fuel_level"
        )
        assert fuel_interp_data is not None

        fuel_sensor = Sensor.model_validate(fuel_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(fuel_interp_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        decimal_places = fuel_interp_data.get("decimal_places")

        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=fuel_sensor,
            interpretation=interpretation,
            device_class=None,
            native_unit=UnitOfVolume.LITERS,
            suggested_unit=None,
            state_class=SensorStateClass.MEASUREMENT,
            options=None,
            decimal_precision=decimal_places,
        )

        if decimal_places is not None:
            assert sensor.suggested_display_precision == decimal_places

    def test_sensor_native_value_without_device_class(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        sensors_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
        interpretations_fixture: list[dict[str, Any]],
    ) -> None:
        """Test sensor returns value correctly when device_class is None."""
        # This test ensures native_value works when _attr_device_class is not set
        speed_sensor_data = find_sensor_by_interpretation(sensors_fixture, "speed")
        assert speed_sensor_data is not None

        vehicle_id = extract_vehicle_id_from_url(speed_sensor_data["vehicle"])
        vehicle_data = find_vehicle_by_id(vehicles_fixture, vehicle_id)
        assert vehicle_data is not None

        speed_interp_data = find_interpretation_by_key(interpretations_fixture, "speed")
        assert speed_interp_data is not None

        speed_sensor = Sensor.model_validate(speed_sensor_data)
        vehicle = Vehicle.model_validate(vehicle_data)
        interpretation = Interpretation.model_validate(speed_interp_data)

        # Find matching state with a value
        state_data = next(
            (s for s in vehicle_states_fixture if vehicle_id in s["vehicle"]), None
        )
        assert state_data is not None
        vehicle_state = VehicleState.model_validate(state_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state

        # Create sensor with device_class=None (would trigger AttributeError before fix)
        sensor = NavirecSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_def=speed_sensor,
            interpretation=interpretation,
            device_class=None,  # Intentionally None
            native_unit=None,
            suggested_unit=None,
            state_class=None,
            options=None,
            decimal_precision=None,
        )

        # Should return the value without raising AttributeError
        value = sensor.native_value
        assert value is not None
