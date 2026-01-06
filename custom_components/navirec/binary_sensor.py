"""Binary sensor platform for Navirec vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
from .data import get_sensor_value_from_state
from .entity import NavirecEntity
from .models import Interpretation, Sensor, Vehicle

if TYPE_CHECKING:
    from .coordinator import NavirecCoordinator
    from .data import NavirecConfigEntry


# Mapping of binary sensor interpretations to device classes
BINARY_SENSOR_DEVICE_CLASSES: dict[str, BinarySensorDeviceClass | None] = {
    "ignition": BinarySensorDeviceClass.POWER,
    "alarm": BinarySensorDeviceClass.SAFETY,
    "panic": BinarySensorDeviceClass.SAFETY,
    "digital_input_1": None,
    "digital_input_2": None,
    "digital_input_3": None,
    "digital_input_4": None,
    "digital_input_5": None,
    "digital_input_6": None,
    "digital_input_7": None,
    "digital_input_8": None,
    "digital_output_1": None,
    "digital_output_2": None,
    "digital_output_3": None,
    "digital_output_4": None,
    "driver_1_card_present": BinarySensorDeviceClass.CONNECTIVITY,
    "driver_2_card_present": BinarySensorDeviceClass.CONNECTIVITY,
    "notification": None,
    "starter_blocked": BinarySensorDeviceClass.LOCK,
    "vehicle_locked": BinarySensorDeviceClass.LOCK,
    "hv_battery_charging": BinarySensorDeviceClass.BATTERY_CHARGING,
    "scooter_charging": BinarySensorDeviceClass.BATTERY_CHARGING,
    "scooter_buzzer": BinarySensorDeviceClass.SOUND,
}

# Binary sensors that need their values inverted
# The LOCK device class in Home Assistant has inverted semantics:
# - is_on=True means "unlocked" (open/insecure)
# - is_on=False means "locked" (closed/secure)
# However, the Navirec API uses standard boolean semantics:
# - true means "locked", false means "unlocked"
# Sensors in this list will have their boolean values inverted.
BINARY_SENSOR_INVERTED: list[str] = [
    "starter_blocked",
    "vehicle_locked",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navirec binary sensors from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator
    interpretations = data.interpretations

    entities: list[NavirecBinarySensor] = []

    # Create binary sensors for each vehicle based on their sensor definitions
    for vehicle_id, vehicle in data.vehicles.items():
        # Get sensors for this vehicle
        vehicle_sensors = data.sensors_by_vehicle.get(vehicle_id, [])

        for sensor_def in vehicle_sensors:
            # Get interpretation data
            if not sensor_def.interpretation:
                continue
            interpretation = interpretations.get(sensor_def.interpretation)
            if not interpretation:
                continue

            # Only handle binary sensor interpretations (data_type == "boolean")
            data_type = interpretation.data_type
            if hasattr(data_type, "value"):
                data_type = data_type.value
            if data_type != "boolean":
                continue

            # Get device class for this interpretation
            interpretation_key = interpretation.key
            device_class = (
                BINARY_SENSOR_DEVICE_CLASSES.get(interpretation_key)
                if interpretation_key
                else None
            )

            entities.append(
                NavirecBinarySensor(
                    coordinator=coordinator,
                    config_entry=entry,
                    vehicle_id=vehicle_id,
                    vehicle=vehicle,
                    sensor_def=sensor_def,
                    interpretation=interpretation,
                    device_class=device_class,
                )
            )

    LOGGER.debug("Adding %d binary sensor entities", len(entities))
    async_add_entities(entities)


class NavirecBinarySensor(NavirecEntity, BinarySensorEntity):
    """Binary sensor entity for Navirec vehicle data."""

    def __init__(
        self,
        coordinator: NavirecCoordinator,
        config_entry: NavirecConfigEntry,
        vehicle_id: str,
        vehicle: Vehicle,
        sensor_def: Sensor,
        interpretation: Interpretation,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize the binary sensor."""
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

        # Set device class
        if device_class:
            self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        state = self.vehicle_state
        if state:
            value = get_sensor_value_from_state(state, self._interpretation_key)
            if value is not None:
                bool_value = bool(value)
                # Invert value for sensors in the inversion list
                if self._interpretation_key in BINARY_SENSOR_INVERTED:
                    return not bool_value
                return bool_value
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
