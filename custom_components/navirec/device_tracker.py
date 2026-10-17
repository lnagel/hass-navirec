"""Device tracker platform for Navirec vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
from .data import get_activity_from_state, get_coordinates_from_state
from .entity import NavirecEntity
from .models import Vehicle

if TYPE_CHECKING:
    from .coordinator import NavirecCoordinator
    from .data import NavirecConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navirec device trackers from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator

    entities: list[NavirecDeviceTracker] = []

    # Create a device tracker for each vehicle
    for vehicle_id, vehicle in data.vehicles.items():
        entities.append(
            NavirecDeviceTracker(
                coordinator=coordinator,
                config_entry=entry,
                vehicle_id=vehicle_id,
                vehicle=vehicle,
            )
        )

    LOGGER.debug("Adding %d device tracker entities", len(entities))
    async_add_entities(entities)


class NavirecDeviceTracker(NavirecEntity, TrackerEntity):
    """Device tracker for a Navirec vehicle."""

    _attr_entity_category = None
    _attr_translation_key = "vehicle"

    def __init__(
        self,
        coordinator: NavirecCoordinator,
        config_entry: NavirecConfigEntry,
        vehicle_id: str,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(
            coordinator=coordinator,
            config_entry=config_entry,
            vehicle_id=vehicle_id,
            vehicle=vehicle,
        )
        # Unique ID for this entity
        self._attr_unique_id = f"{vehicle_id}_location"
        self._update_attrs()

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    def _update_attrs(self) -> None:
        """Set the location and extra state attributes from coordinator data."""
        self._attr_latitude, self._attr_longitude = self._compute_coordinates()
        self._attr_extra_state_attributes = self._compute_extra_state_attributes()

    def _compute_coordinates(self) -> tuple[float | None, float | None]:
        """Return the (latitude, longitude) of the device."""
        state = self.vehicle_state
        if state:
            return get_coordinates_from_state(state)
        return None, None

    def _compute_extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "name_display": self._vehicle.name_display,
            "registration": self._vehicle.registration,
        }
        state = self.vehicle_state

        if state:
            if state.speed is not None:
                attrs["speed"] = state.speed
            if state.heading is not None:
                attrs["heading"] = state.heading
            if state.altitude is not None:
                attrs["altitude"] = state.altitude
            activity = get_activity_from_state(state)
            if activity:
                attrs["activity"] = activity
            if state.time:
                attrs["last_update"] = state.time.isoformat()

        return attrs
