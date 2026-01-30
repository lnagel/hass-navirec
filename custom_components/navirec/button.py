"""Button platform for Navirec vehicle actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .commands import execute_action
from .entity import NavirecEntity
from .models import Action, Vehicle

if TYPE_CHECKING:
    from .coordinator import NavirecCoordinator
    from .data import NavirecConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Navirec action buttons from a config entry."""
    data = entry.runtime_data
    coordinator = data.coordinator

    entities: list[NavirecActionButton] = []

    # Create button entities for each action on each vehicle
    for vehicle_id, vehicle in data.vehicles.items():
        actions = data.actions_by_vehicle.get(vehicle_id, [])
        entities.extend(
            NavirecActionButton(
                coordinator=coordinator,
                config_entry=entry,
                vehicle_id=vehicle_id,
                vehicle=vehicle,
                action=action,
            )
            for action in actions
        )

    async_add_entities(entities)


class NavirecActionButton(NavirecEntity, ButtonEntity):
    """Button entity for executing a vehicle action."""

    def __init__(
        self,
        coordinator: NavirecCoordinator,
        config_entry: NavirecConfigEntry,
        vehicle_id: str,
        vehicle: Vehicle,
        action: Action,
    ) -> None:
        """Initialize the action button."""
        super().__init__(coordinator, config_entry, vehicle_id, vehicle)
        self._action = action
        self._config_entry = config_entry

        # Entity attributes
        self._attr_unique_id = f"{vehicle_id}_{action.id}"
        self._attr_translation_key = action.slug
        self._attr_name = action.name_display or action.slug or str(action.type)
        # Actions are enabled by default (unlike diagnostic sensors)
        self._attr_entity_registry_enabled_default = True

    @property
    def available(self) -> bool:
        """
        Return if entity is available.

        Buttons are always available since commands can be sent to the API
        regardless of vehicle state. This allows users to trigger GPS location
        updates before the initial state is received from the stream.
        """
        return True

    async def async_press(self) -> None:
        """Handle button press - execute the action."""
        vehicle_name = (
            self._vehicle.name_display or self._vehicle.registration or self._vehicle_id
        )
        action_name = (
            self._action.name_display or self._action.slug or str(self._action.type)
        )

        await execute_action(
            hass=self.hass,
            client=self._config_entry.runtime_data.client,
            vehicle_id=self._vehicle_id,
            action_id=str(self._action.id),
            vehicle_name=vehicle_name,
            action_name=action_name,
        )
