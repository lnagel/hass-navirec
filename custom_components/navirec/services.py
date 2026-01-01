"""Services for Navirec integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .commands import execute_action
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from .data import NavirecConfigEntry

SERVICE_EXECUTE_ACTION = "execute_action"

SERVICE_EXECUTE_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("vehicle_id"): cv.string,
        vol.Required("action_id"): cv.string,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Navirec services."""

    async def async_execute_action_service(call: ServiceCall) -> None:
        """Handle execute_action service call."""
        vehicle_id = call.data["vehicle_id"]
        action_id = call.data["action_id"]

        # Find the config entry containing this vehicle
        entry, vehicle, action = _find_vehicle_and_action(hass, vehicle_id, action_id)
        if not entry or not vehicle or not action:
            msg = f"Vehicle '{vehicle_id}' or action '{action_id}' not found"
            raise HomeAssistantError(msg)

        # Get display names
        vehicle_name = vehicle.name_display or vehicle.registration or vehicle_id
        action_name = action.name_display or action.slug or str(action.type)

        LOGGER.info(
            "Service call: executing action %s on vehicle %s",
            action_name,
            vehicle_name,
        )

        await execute_action(
            hass=hass,
            client=entry.runtime_data.client,
            vehicle_id=vehicle_id,
            action_id=action_id,
            vehicle_name=vehicle_name,
            action_name=action_name,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXECUTE_ACTION,
        async_execute_action_service,
        schema=SERVICE_EXECUTE_ACTION_SCHEMA,
    )


def _find_vehicle_and_action(
    hass: HomeAssistant,
    vehicle_id: str,
    action_id: str,
) -> tuple[NavirecConfigEntry | None, object, object]:
    """Find vehicle and action by their IDs across all config entries."""
    entries: list[NavirecConfigEntry] = hass.config_entries.async_entries(DOMAIN)

    for entry in entries:
        if not hasattr(entry, "runtime_data") or not entry.runtime_data:
            continue

        data = entry.runtime_data

        # Check if vehicle exists in this entry
        if vehicle_id not in data.vehicles:
            continue

        vehicle = data.vehicles[vehicle_id]

        # Find the action
        actions = data.actions_by_vehicle.get(vehicle_id, [])
        for action in actions:
            if str(action.id) == action_id:
                return entry, vehicle, action

    return None, None, None


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Navirec services."""
    hass.services.async_remove(DOMAIN, SERVICE_EXECUTE_ACTION)
