"""Sensor platform for Navirec vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API_UNIT_TO_HA_UNIT, INTERPRETATIONS_TOTAL_INCREASING, LOGGER
from .data import get_interpretation_choice_options, get_sensor_value_from_state
from .entity import NavirecEntity
from .models import Interpretation, Sensor, Vehicle

if TYPE_CHECKING:
    from .coordinator import NavirecCoordinator
    from .data import NavirecConfigEntry


def _get_device_class(interpretation: Interpretation) -> SensorDeviceClass | None:
    """Determine HA device class from interpretation data."""
    # If has choices, it's an ENUM
    if interpretation.choices:
        return SensorDeviceClass.ENUM

    # Infer from unit
    unit = interpretation.unit
    if hasattr(unit, "value"):
        unit = unit.value

    device_class = None
    if unit in ("V", "mV"):
        device_class = SensorDeviceClass.VOLTAGE
    elif unit == "A":
        device_class = SensorDeviceClass.CURRENT
    elif unit == "c":
        device_class = SensorDeviceClass.TEMPERATURE
    elif unit == "m":
        device_class = SensorDeviceClass.DISTANCE
    elif unit == "s":
        device_class = SensorDeviceClass.DURATION
    elif unit == "km__hr":
        device_class = SensorDeviceClass.SPEED

    if device_class:
        return device_class

    # Infer from data_type for timestamp
    data_type = interpretation.data_type
    if hasattr(data_type, "value"):
        data_type = data_type.value
    if data_type == "datetime":
        return SensorDeviceClass.TIMESTAMP

    return None


def _get_state_class(
    interpretation: Interpretation, device_class: SensorDeviceClass | None
) -> SensorStateClass | None:
    """Determine HA state class from interpretation data."""
    # ENUMs and timestamps don't have state class
    if device_class in (SensorDeviceClass.ENUM, SensorDeviceClass.TIMESTAMP):
        return None

    # Total/accumulated values
    key = interpretation.key or ""
    if key in INTERPRETATIONS_TOTAL_INCREASING:
        return SensorStateClass.TOTAL_INCREASING

    # Most numeric sensors are measurements
    data_type = interpretation.data_type
    if hasattr(data_type, "value"):
        data_type = data_type.value
    if data_type in ("int", "long", "float", "double", "duration"):
        return SensorStateClass.MEASUREMENT

    return None


def _get_native_unit(interpretation: Interpretation) -> str | None:
    """Get HA native unit from interpretation data."""
    unit = interpretation.unit
    if hasattr(unit, "value"):
        unit = unit.value
    if not unit:
        return None
    return API_UNIT_TO_HA_UNIT.get(unit)


def _get_suggested_unit(interpretation: Interpretation) -> str | None:
    """Get HA suggested display unit from interpretation data."""
    unit_conversion = interpretation.unit_conversion
    if hasattr(unit_conversion, "value"):
        unit_conversion = unit_conversion.value
    if not unit_conversion:
        return None
    return API_UNIT_TO_HA_UNIT.get(unit_conversion)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navirec sensors from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator
    interpretations = data.interpretations

    entities: list[NavirecSensor] = []

    # Create sensors for each vehicle based on their sensor definitions
    for vehicle_id, vehicle in data.vehicles.items():
        # Get sensors for this vehicle
        vehicle_sensors = data.sensors_by_vehicle.get(vehicle_id, [])

        for sensor_def in vehicle_sensors:
            # Get interpretation key - handle RootModel wrapper
            interpretation_key = ""
            if sensor_def.interpretation:
                interpretation_key = (
                    sensor_def.interpretation.root.value
                    if hasattr(sensor_def.interpretation, "root")
                    else str(sensor_def.interpretation)
                )

            # Get interpretation data
            interpretation = interpretations.get(interpretation_key)
            if not interpretation:
                LOGGER.warning(
                    "Skipping sensor %s: interpretation %s not found",
                    sensor_def.id,
                    interpretation_key,
                )
                continue

            # Skip binary sensor interpretations - they're handled in binary_sensor.py
            data_type = interpretation.data_type
            if hasattr(data_type, "value"):
                data_type = data_type.value
            if data_type == "boolean":
                continue

            # Derive sensor configuration from interpretation
            device_class = _get_device_class(interpretation)
            state_class = _get_state_class(interpretation, device_class)
            native_unit = _get_native_unit(interpretation)
            suggested_unit = _get_suggested_unit(interpretation)

            # Determine decimal precision: use explicit value, or 0 for integers, longs
            decimal_precision = interpretation.decimal_places
            if decimal_precision is None and data_type in {"int", "long"}:
                decimal_precision = 0

            # Get options for enum sensors
            options = None
            if device_class == SensorDeviceClass.ENUM:
                options = get_interpretation_choice_options(interpretation)

            entities.append(
                NavirecSensor(
                    coordinator=coordinator,
                    config_entry=entry,
                    vehicle_id=vehicle_id,
                    vehicle=vehicle,
                    sensor_def=sensor_def,
                    interpretation=interpretation,
                    device_class=device_class,
                    native_unit=native_unit,
                    suggested_unit=suggested_unit,
                    state_class=state_class,
                    options=options,
                    decimal_precision=decimal_precision,
                )
            )

    LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)


class NavirecSensor(NavirecEntity, SensorEntity):
    """Sensor entity for Navirec vehicle data."""

    def __init__(
        self,
        coordinator: NavirecCoordinator,
        config_entry: NavirecConfigEntry,
        vehicle_id: str,
        vehicle: Vehicle,
        sensor_def: Sensor,
        interpretation: Interpretation,
        device_class: SensorDeviceClass | None,
        native_unit: str | None,
        suggested_unit: str | None,
        state_class: SensorStateClass | None,
        options: list[str] | None,
        decimal_precision: int | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
        )
        self._sensor_def = sensor_def
        self._interpretation = interpretation
        self._interpretation_key = interpretation.key or ""

        # Entity attributes
        sensor_id = str(sensor_def.id) if sensor_def.id else ""
        self._attr_unique_id = f"{vehicle_id}_{sensor_id}"
        self._attr_name = sensor_def.name_display or self._interpretation_key

        # Use show_in_map to determine if entity is enabled by default
        self._attr_entity_registry_enabled_default = sensor_def.show_in_map

        # Sensor-specific attributes
        if device_class:
            self._attr_device_class = device_class
        if native_unit:
            self._attr_native_unit_of_measurement = native_unit
        if suggested_unit:
            self._attr_suggested_unit_of_measurement = suggested_unit
        if state_class:
            self._attr_state_class = state_class
        if decimal_precision is not None:
            self._attr_suggested_display_precision = decimal_precision

        # Handle enum sensors with options from interpretation choices
        if device_class == SensorDeviceClass.ENUM and options:
            self._attr_options = options

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        state = self.vehicle_state
        if not state:
            return None

        value = get_sensor_value_from_state(state, self._interpretation_key)
        if value is None:
            return None

        # Handle Pydantic RootModel types (like Activity)
        if hasattr(value, "root"):
            # RootModel wraps an enum, get the enum value
            root_value = value.root
            if hasattr(root_value, "value"):
                value = root_value.value
            else:
                value = str(root_value)
        # Handle regular enum types
        elif hasattr(value, "value"):
            value = value.value

        # For enum sensors, convert value to string to match options
        if self.device_class == SensorDeviceClass.ENUM:
            return str(value)
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
