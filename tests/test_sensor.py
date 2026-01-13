"""Tests for Navirec sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfSpeed

from custom_components.navirec.models import (
    Interpretation,
    Sensor,
    Vehicle,
    VehicleState,
)
from custom_components.navirec.sensor import (
    NavirecSensor,
    _get_device_class,
    _get_native_unit,
    _get_state_class,
    _get_suggested_unit,
)


# --- Fixtures ---
@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create mock config entry."""
    return MagicMock()


# --- Helpers ---
def _find(items: list[dict], key: str, value: str) -> dict | None:
    """Find item in list by key value."""
    return next(
        (i for i in items if i.get(key) == value or value in str(i.get(key, ""))), None
    )


def _make_sensor(
    entry: MagicMock,
    fixtures: dict,
    interp_key: str,
    device_class: SensorDeviceClass | None = None,
    state_value: Any = None,
    **kwargs: Any,
) -> NavirecSensor:
    """Create NavirecSensor from fixtures with minimal boilerplate."""
    s = _find(fixtures["sensors"], "interpretation", interp_key)
    assert s, f"No sensor with interpretation {interp_key}"
    vid = s["vehicle"].split("/")[-2]
    v = _find(fixtures["vehicles"], "id", vid)
    i = _find(fixtures["interpretations"], "key", interp_key)
    st = _find(fixtures["states"], "vehicle", vid)

    state = MagicMock(spec=VehicleState)
    if state_value is not None:
        setattr(state, interp_key, state_value)
    elif st:
        state = VehicleState.model_validate(st)

    coord = MagicMock(get_vehicle_state=MagicMock(return_value=state), connected=True)
    return NavirecSensor(
        coordinator=coord,
        config_entry=entry,
        vehicle_id=vid,
        vehicle=Vehicle.model_validate(v),
        sensor_def=Sensor.model_validate(s),
        interpretation=Interpretation.model_validate(i),
        device_class=device_class,
        native_unit=kwargs.get("native_unit"),
        suggested_unit=kwargs.get("suggested_unit"),
        state_class=kwargs.get("state_class"),
        options=kwargs.get("options"),
        decimal_precision=kwargs.get("decimal_precision"),
    )


@pytest.fixture
def fixtures(
    vehicles_fixture, sensors_fixture, vehicle_states_fixture, interpretations_fixture
) -> dict:
    """Bundle all fixtures."""
    return {
        "vehicles": vehicles_fixture,
        "sensors": sensors_fixture,
        "states": vehicle_states_fixture,
        "interpretations": interpretations_fixture,
    }


# --- NavirecSensor Tests ---
_SENSOR_CASES = [
    (
        "speed",
        SensorDeviceClass.SPEED,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        SensorStateClass.MEASUREMENT,
    ),
]


@pytest.mark.parametrize(("interp", "dev_cls", "unit", "state_cls"), _SENSOR_CASES)
def test_sensor_attributes(
    mock_config_entry, fixtures, interp, dev_cls, unit, state_cls
):
    """Test sensor has correct device class, unit, and state class."""
    sensor = _make_sensor(
        mock_config_entry,
        fixtures,
        interp,
        dev_cls,
        native_unit=unit,
        state_class=state_cls,
    )
    assert sensor.device_class == dev_cls
    assert sensor.native_unit_of_measurement == unit
    assert sensor.state_class == state_cls


def test_sensor_native_value(mock_config_entry, fixtures):
    """Test sensor native_value property works."""
    sensor = _make_sensor(mock_config_entry, fixtures, "speed", SensorDeviceClass.SPEED)
    # Just verify property access doesn't raise
    _ = sensor.native_value


def test_sensor_enum_returns_string(mock_config_entry, fixtures):
    """Test enum sensor returns string value."""
    sensor = _make_sensor(
        mock_config_entry,
        fixtures,
        "activity",
        SensorDeviceClass.ENUM,
        options=["driving", "parking"],
    )
    val = sensor.native_value
    assert val is None or isinstance(val, str)


def test_sensor_unique_id(mock_config_entry, fixtures):
    """Test sensor unique ID format."""
    sensor = _make_sensor(mock_config_entry, fixtures, "speed", SensorDeviceClass.SPEED)
    assert "_" in sensor.unique_id


def test_sensor_no_state_returns_none(mock_config_entry, fixtures):
    """Test sensor returns None when no state."""
    s = _find(fixtures["sensors"], "interpretation", "speed")
    assert s is not None
    vid = s["vehicle"].split("/")[-2]
    coord = MagicMock(get_vehicle_state=MagicMock(return_value=None), connected=True)
    sensor = NavirecSensor(
        coordinator=coord,
        config_entry=mock_config_entry,
        vehicle_id=vid,
        vehicle=Vehicle.model_validate(_find(fixtures["vehicles"], "id", vid)),
        sensor_def=Sensor.model_validate(s),
        interpretation=Interpretation.model_validate(
            _find(fixtures["interpretations"], "key", "speed")
        ),
        device_class=SensorDeviceClass.SPEED,
        native_unit=None,
        suggested_unit=None,
        state_class=None,
        options=None,
        decimal_precision=None,
    )
    assert sensor.native_value is None


# --- Helper Function Tests (for coverage of enum .value branches) ---
_HELPER_CASES = [
    (
        _get_device_class,
        {"key": "t", "name": "T", "unit": "V"},
        "unit",
        "V",
        {},
        SensorDeviceClass.VOLTAGE,
    ),
    (
        _get_device_class,
        {"key": "t", "name": "T", "data_type": "datetime"},
        "data_type",
        "datetime",
        {},
        SensorDeviceClass.TIMESTAMP,
    ),
    (
        _get_state_class,
        {"key": "t", "name": "T", "data_type": "float"},
        "data_type",
        "float",
        {"device_class": SensorDeviceClass.SPEED},
        SensorStateClass.MEASUREMENT,
    ),
    (
        _get_native_unit,
        {"key": "t", "name": "T", "unit": "km__hr"},
        "unit",
        "km__hr",
        {},
        True,
    ),
    (
        _get_suggested_unit,
        {"key": "t", "name": "T", "unit": "m", "unit_conversion": "km"},
        "unit_conversion",
        "km",
        {},
        True,
    ),
]


@pytest.mark.parametrize(
    ("func", "data", "field", "val", "args", "expect"), _HELPER_CASES
)
def test_helper_enum_branches(func, data, field, val, args, expect):
    """Test helper functions handle enum-like .value attributes."""
    interp = Interpretation.model_validate(data)
    mock = MagicMock(value=val)
    setattr(interp, field, mock)
    result = func(interp, **args) if args else func(interp)
    assert (
        (result is not None) == expect if isinstance(expect, bool) else result == expect
    )


# --- Native Value Edge Cases (RootModel/enum handling) ---
def _mock_activity(mode: str):
    """Create mock activity value."""
    if mode == "root_enum":
        return MagicMock(root=MagicMock(value="driving"))
    if mode == "root_str":
        return MagicMock(root="parking")
    m = MagicMock(value="idling")
    del m.root
    return m


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("root_enum", "driving"), ("root_str", "parking"), ("enum", "idling")],
)
def test_native_value_enum_handling(mock_config_entry, fixtures, mode, expected):
    """Test native_value handles RootModel and enum values."""
    sensor = _make_sensor(
        mock_config_entry,
        fixtures,
        "activity",
        SensorDeviceClass.ENUM,
        state_value=_mock_activity(mode),
        options=["offline", "parking", "driving", "idling"],
    )
    assert sensor.native_value == expected
