"""Device tracker platform for Navirec vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
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

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        state = self.vehicle_state
        if state:
            lat, _ = get_coordinates_from_state(state)
            return lat
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        state = self.vehicle_state
        if state:
            _, lon = get_coordinates_from_state(state)
            return lon
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
