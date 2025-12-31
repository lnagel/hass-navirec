"""Sensor platform for Navirec vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_SENSOR_INTERPRETATIONS, DOMAIN, LOGGER
from .data import get_sensor_value_from_state
from .entity import NavirecEntity
from .models import Sensor, Vehicle

if TYPE_CHECKING:
    from .coordinator import NavirecCoordinator
    from .data import NavirecConfigEntry


# Mapping of sensor interpretations to HA device class and units
SENSOR_MAPPINGS: dict[
    str, tuple[SensorDeviceClass | None, str | None, SensorStateClass | None]
] = {
    # Speed and movement
    "speed": (
        SensorDeviceClass.SPEED,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        SensorStateClass.MEASUREMENT,
    ),
    "heading": (None, DEGREE, SensorStateClass.MEASUREMENT),
    "altitude": (None, UnitOfLength.METERS, SensorStateClass.MEASUREMENT),
    # Fuel
    "fuel_level": (None, UnitOfVolume.LITERS, SensorStateClass.MEASUREMENT),
    "total_fuel_used": (None, UnitOfVolume.LITERS, SensorStateClass.TOTAL_INCREASING),
    # Voltage
    "supply_voltage": (
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    "battery_voltage": (
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    # Distance and time
    "total_distance": (
        SensorDeviceClass.DISTANCE,
        UnitOfLength.METERS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "total_engine_time": (
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "accumulated_distance": (
        SensorDeviceClass.DISTANCE,
        UnitOfLength.METERS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "accumulated_engine_time": (
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    # Activity and status
    "activity": (SensorDeviceClass.ENUM, None, None),
    "eco_score": (None, None, SensorStateClass.MEASUREMENT),
    # Satellites
    "satellites": (None, None, SensorStateClass.MEASUREMENT),
    # Driver information
    "driver_1_card_id": (None, None, None),
    "driver_2_card_id": (None, None, None),
    "driver_1_ibutton_id": (None, None, None),
    "driver_1_rfid_id": (None, None, None),
    "driver_1_working_state": (SensorDeviceClass.ENUM, None, None),
    "driver_2_working_state": (SensorDeviceClass.ENUM, None, None),
    # Timestamps
    "tacho_current_time": (SensorDeviceClass.TIMESTAMP, None, None),
    "timezone_offset": (None, UnitOfTime.SECONDS, None),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navirec sensors from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator

    entities: list[NavirecSensor] = []

    # Create sensors for each vehicle based on their sensor definitions
    for vehicle_id, vehicle in data.vehicles.items():
        # Get sensors for this vehicle
        vehicle_sensors = data.sensors_by_vehicle.get(vehicle_id, [])

        for sensor_def in vehicle_sensors:
            # Get interpretation - handle RootModel wrapper
            interpretation = ""
            if sensor_def.interpretation:
                interpretation = (
                    sensor_def.interpretation.root.value
                    if hasattr(sensor_def.interpretation, "root")
                    else str(sensor_def.interpretation)
                )

            # Skip binary sensor interpretations - they're handled in binary_sensor.py
            if interpretation in BINARY_SENSOR_INTERPRETATIONS:
                continue

            # Get mapping for this interpretation
            mapping = SENSOR_MAPPINGS.get(interpretation)

            entities.append(
                NavirecSensor(
                    coordinator=coordinator,
                    config_entry=entry,
                    vehicle_id=vehicle_id,
                    vehicle=vehicle,
                    sensor_def=sensor_def,
                    interpretation=interpretation,
                    device_class=mapping[0] if mapping else None,
                    unit=mapping[1] if mapping else None,
                    state_class=mapping[2] if mapping else None,
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
        interpretation: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        state_class: SensorStateClass | None,
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

        # Entity attributes
        sensor_id = str(sensor_def.id) if sensor_def.id else ""
        self._attr_unique_id = f"{vehicle_id}_{sensor_id}"
        self._attr_name = sensor_def.name_display or interpretation

        # Use show_in_map to determine if entity is enabled by default
        self._attr_entity_registry_enabled_default = sensor_def.show_in_map

        # Sensor-specific attributes
        if device_class:
            self._attr_device_class = device_class
        if unit:
            self._attr_native_unit_of_measurement = unit
        if state_class:
            self._attr_state_class = state_class

        # Handle enum sensors
        if device_class == SensorDeviceClass.ENUM:
            if self._interpretation == "activity":
                # All possible activity values from Activity3b5Enum
                self._attr_options = [
                    "offline", "parking", "towing", "idling", "driving"
                ]
            elif self._interpretation in (
                "driver_1_working_state",
                "driver_2_working_state",
            ):
                # Working state codes: 0=rest, 1=availability, 2=work, 3=driving
                self._attr_options = ["0", "1", "2", "3"]

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        state = self.vehicle_state
        if state:
            value = get_sensor_value_from_state(state, self._interpretation)
            if value is None:
                return None
            # Handle Pydantic RootModel types (like Activity)
            if hasattr(value, "root"):
                # RootModel wraps an enum, get the enum value
                root_value = value.root
                if hasattr(root_value, "value"):
                    return root_value.value
                return str(root_value)
            # Handle regular enum types
            if hasattr(value, "value"):
                return value.value
            return value
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
