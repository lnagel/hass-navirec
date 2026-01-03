"""Base entity class for Navirec."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import NavirecCoordinator
from .data import VehicleState
from .models import Vehicle

if TYPE_CHECKING:
    from .data import NavirecConfigEntry


class NavirecEntity(CoordinatorEntity[NavirecCoordinator]):
    """Base entity for Navirec vehicles."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NavirecCoordinator,
        config_entry: NavirecConfigEntry,
        vehicle_id: str,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._vehicle = vehicle

        # Device info for the vehicle
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle_id)},
            name=vehicle.name_display or vehicle.registration or "",
            manufacturer=vehicle.make,
            model=vehicle.model,
            serial_number=vehicle.registration,
        )

    @property
    def vehicle_state(self) -> VehicleState | None:
        """Get the current vehicle state from the coordinator."""
        return self.coordinator.get_vehicle_state(self._vehicle_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator is connected and we have state data
        return self.coordinator.connected or self.vehicle_state is not None
