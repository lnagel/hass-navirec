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
from custom_components.navirec.sensor import (
    NavirecDiagnosticSensor,
    NavirecSensor,
    _get_device_class,
    _get_native_unit,
    _get_state_class,
    _get_suggested_unit,
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


class TestNavirecDiagnosticSensor:
    """Tests for NavirecDiagnosticSensor."""

    def test_diagnostic_sensor_with_datetime_value(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
    ) -> None:
        """Test diagnostic sensor returns datetime value."""
        from datetime import datetime

        vehicle_data = vehicles_fixture[0]
        vehicle = Vehicle.model_validate(vehicle_data)
        vehicle_id = vehicle_data["id"]

        # Create a state with a datetime updated_at
        state_data = vehicle_states_fixture[0]
        vehicle_state = VehicleState.model_validate(state_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state
        coordinator.connected = True

        sensor = NavirecDiagnosticSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_key="updated_at",
            translation_key="updated_at",
        )

        value = sensor.native_value
        assert value is not None
        assert isinstance(value, datetime)

    def test_diagnostic_sensor_no_state(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
    ) -> None:
        """Test diagnostic sensor returns None when no state."""
        vehicle_data = vehicles_fixture[0]
        vehicle = Vehicle.model_validate(vehicle_data)
        vehicle_id = vehicle_data["id"]

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = None

        sensor = NavirecDiagnosticSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_key="updated_at",
            translation_key="updated_at",
        )

        assert sensor.native_value is None

    def test_diagnostic_sensor_missing_attribute(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
        vehicle_states_fixture: list[dict[str, Any]],
    ) -> None:
        """Test diagnostic sensor returns None for missing attribute."""
        vehicle_data = vehicles_fixture[0]
        vehicle = Vehicle.model_validate(vehicle_data)
        vehicle_id = vehicle_data["id"]

        state_data = vehicle_states_fixture[0]
        vehicle_state = VehicleState.model_validate(state_data)

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = vehicle_state

        sensor = NavirecDiagnosticSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_key="nonexistent_key",
            translation_key="nonexistent_key",
        )

        assert sensor.native_value is None

    def test_diagnostic_sensor_invalid_datetime_string(
        self,
        mock_config_entry: MagicMock,
        vehicles_fixture: list[dict[str, Any]],
    ) -> None:
        """Test diagnostic sensor handles invalid datetime string."""
        vehicle_data = vehicles_fixture[0]
        vehicle = Vehicle.model_validate(vehicle_data)
        vehicle_id = vehicle_data["id"]

        # Create a mock state with invalid datetime string
        mock_state = MagicMock()
        mock_state.updated_at = "not-a-valid-datetime"

        coordinator = MagicMock()
        coordinator.get_vehicle_state.return_value = mock_state

        sensor = NavirecDiagnosticSensor(
            coordinator=coordinator,
            config_entry=mock_config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
            sensor_key="updated_at",
            translation_key="updated_at",
        )

        # Should return None and log warning for invalid datetime
        assert sensor.native_value is None


# Test data for _get_device_class parametrized tests
_DEVICE_CLASS_CASES = [
    # (unit, data_type, choices, expected_device_class, test_id)
    ("V", "float", None, SensorDeviceClass.VOLTAGE, "voltage"),
    ("mV", "float", None, SensorDeviceClass.VOLTAGE, "millivolt"),
    ("A", "float", None, SensorDeviceClass.CURRENT, "current"),
    ("c", "float", None, SensorDeviceClass.TEMPERATURE, "temperature"),
    ("m", "float", None, SensorDeviceClass.DISTANCE, "distance_meters"),
    ("km", "float", None, SensorDeviceClass.DISTANCE, "distance_km"),
    ("s", "duration", None, SensorDeviceClass.DURATION, "duration"),
    ("km__hr", "float", None, SensorDeviceClass.SPEED, "speed"),
    (None, "datetime", None, SensorDeviceClass.TIMESTAMP, "timestamp"),
    (None, "string", [["a", "A"]], SensorDeviceClass.ENUM, "enum_with_choices"),
    ("xyz", "string", None, None, "unknown_unit"),
]

# Test data for _get_state_class parametrized tests
_STATE_CLASS_CASES = [
    # (key, data_type, device_class, expected_state_class, test_id)
    (
        "speed",
        "float",
        SensorDeviceClass.SPEED,
        SensorStateClass.MEASUREMENT,
        "measurement",
    ),
    (
        "accumulated_distance",
        "float",
        SensorDeviceClass.DISTANCE,
        SensorStateClass.TOTAL_INCREASING,
        "total_increasing",
    ),
    ("activity", "string", SensorDeviceClass.ENUM, None, "enum_no_state"),
    (
        "last_update",
        "datetime",
        SensorDeviceClass.TIMESTAMP,
        None,
        "timestamp_no_state",
    ),
    (
        "engine_hours",
        "duration",
        None,
        SensorStateClass.MEASUREMENT,
        "duration_measurement",
    ),
]

# Test data for _get_native_unit parametrized tests
_NATIVE_UNIT_CASES = [
    # (unit, expected_is_not_none, test_id)
    ("km__hr", True, "known_unit"),
    ("xyz", False, "unknown_unit"),
    ("", False, "empty_unit"),
]

# Test data for _get_suggested_unit parametrized tests
_SUGGESTED_UNIT_CASES = [
    # (unit_conversion, expected_is_not_none, test_id)
    ("km", True, "with_conversion"),
    (None, False, "without_conversion"),
]


class TestSensorHelperFunctions:
    """Tests for sensor helper functions using parameterized test cases."""

    @pytest.mark.parametrize(
        ("unit", "data_type", "choices", "expected", "test_id"),
        _DEVICE_CLASS_CASES,
        ids=[c[4] for c in _DEVICE_CLASS_CASES],
    )
    def test_get_device_class(
        self,
        unit: str | None,
        data_type: str,
        choices: list | None,
        expected: SensorDeviceClass | None,
        test_id: str,
    ) -> None:
        """Test device class detection from interpretation data."""
        del test_id  # Only used for test IDs
        interp_data: dict[str, Any] = {
            "key": "test",
            "name": "Test",
            "data_type": data_type,
        }
        if unit:
            interp_data["unit"] = unit
        if choices:
            interp_data["choices"] = choices
        interpretation = Interpretation.model_validate(interp_data)
        assert _get_device_class(interpretation) == expected

    @pytest.mark.parametrize(
        ("key", "data_type", "device_class", "expected", "test_id"),
        _STATE_CLASS_CASES,
        ids=[c[4] for c in _STATE_CLASS_CASES],
    )
    def test_get_state_class(
        self,
        key: str,
        data_type: str,
        device_class: SensorDeviceClass | None,
        expected: SensorStateClass | None,
        test_id: str,
    ) -> None:
        """Test state class detection from interpretation data."""
        del test_id  # Only used for test IDs
        interpretation = Interpretation.model_validate(
            {"key": key, "name": "Test", "data_type": data_type}
        )
        assert _get_state_class(interpretation, device_class) == expected

    @pytest.mark.parametrize(
        ("unit", "expected_is_not_none", "test_id"),
        _NATIVE_UNIT_CASES,
        ids=[c[2] for c in _NATIVE_UNIT_CASES],
    )
    def test_get_native_unit(
        self,
        unit: str,
        expected_is_not_none: bool,
        test_id: str,
    ) -> None:
        """Test native unit mapping from interpretation data."""
        del test_id  # Only used for test IDs
        interpretation = Interpretation.model_validate(
            {"key": "test", "name": "Test", "unit": unit, "data_type": "float"}
        )
        result = _get_native_unit(interpretation)
        assert (result is not None) == expected_is_not_none

    @pytest.mark.parametrize(
        ("unit_conversion", "expected_is_not_none", "test_id"),
        _SUGGESTED_UNIT_CASES,
        ids=[c[2] for c in _SUGGESTED_UNIT_CASES],
    )
    def test_get_suggested_unit(
        self,
        unit_conversion: str | None,
        expected_is_not_none: bool,
        test_id: str,
    ) -> None:
        """Test suggested unit from unit_conversion field."""
        del test_id  # Only used for test IDs
        interp_data: dict[str, Any] = {
            "key": "test",
            "name": "Test",
            "unit": "m",
            "data_type": "float",
        }
        if unit_conversion:
            interp_data["unit_conversion"] = unit_conversion
        interpretation = Interpretation.model_validate(interp_data)
        result = _get_suggested_unit(interpretation)
        assert (result is not None) == expected_is_not_none
