"""Command execution for Navirec vehicle actions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.persistent_notification import async_create

from .const import (
    COMMAND_POLL_BACKOFF_FACTOR,
    COMMAND_POLL_INITIAL_DELAY,
    COMMAND_POLL_MAX_DELAY,
    COMMAND_TERMINAL_STATES,
    EVENT_COMMAND_RESULT,
    LOGGER,
)
from .models import DeviceCommand

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import NavirecApiClient


async def execute_action(
    hass: HomeAssistant,
    client: NavirecApiClient,
    vehicle_id: str,
    action_id: str,
    vehicle_name: str,
    action_name: str,
) -> DeviceCommand:
    """
    Execute an action on a vehicle.

    Creates a device command via the API and spawns a background task
    to poll for completion. Fires an event and creates a persistent
    notification when the command reaches a terminal state.

    Args:
        hass: Home Assistant instance.
        client: Navirec API client.
        vehicle_id: UUID of the target vehicle.
        action_id: UUID of the action to execute.
        vehicle_name: Display name of the vehicle (for notifications).
        action_name: Display name of the action (for notifications).

    Returns:
        The created DeviceCommand object.

    """
    # Create the command
    command_data = await client.async_create_device_command(
        vehicle_id=vehicle_id,
        action_id=action_id,
    )
    command = DeviceCommand.model_validate(command_data)

    LOGGER.info(
        "Created device command %s for action %s on vehicle %s",
        command.id,
        action_name,
        vehicle_name,
    )

    # Start background polling task
    hass.async_create_background_task(
        _poll_command_status(
            hass=hass,
            client=client,
            command_id=str(command.id),
            expires_at=command.expires_at,
            vehicle_name=vehicle_name,
            action_name=action_name,
        ),
        f"navirec_command_{command.id}",
    )

    return command


async def _poll_command_status(
    hass: HomeAssistant,
    client: NavirecApiClient,
    command_id: str,
    expires_at: datetime | None,
    vehicle_name: str,
    action_name: str,
) -> None:
    """
    Poll command status until terminal state or expiry.

    Args:
        hass: Home Assistant instance.
        client: Navirec API client.
        command_id: UUID of the command to poll.
        expires_at: When the command expires.
        vehicle_name: Display name of the vehicle (for notifications).
        action_name: Display name of the action (for notifications).

    """
    delay = COMMAND_POLL_INITIAL_DELAY

    while True:
        # Check if expired before polling
        if expires_at and datetime.now(UTC) >= expires_at:
            LOGGER.warning(
                "Command %s expired before reaching terminal state", command_id
            )
            _fire_result_event(
                hass,
                command_id=command_id,
                state="expired",
                vehicle_name=vehicle_name,
                action_name=action_name,
            )
            _create_notification(
                hass,
                command_id=command_id,
                state="expired",
                vehicle_name=vehicle_name,
                action_name=action_name,
            )
            return

        await asyncio.sleep(delay)

        try:
            command_data = await client.async_get_device_command(command_id)
            command = DeviceCommand.model_validate(command_data)
        except Exception as err:
            LOGGER.warning("Failed to poll command %s: %s", command_id, err)
            delay = min(delay * COMMAND_POLL_BACKOFF_FACTOR, COMMAND_POLL_MAX_DELAY)
            continue

        if command.state in COMMAND_TERMINAL_STATES:
            LOGGER.info(
                "Command %s reached terminal state: %s",
                command_id,
                command.state,
            )
            _fire_result_event(
                hass,
                command_id=command_id,
                state=command.state,
                message=command.message,
                response=command.response,
                errors=command.errors,
                vehicle_name=vehicle_name,
                action_name=action_name,
            )
            _create_notification(
                hass,
                command_id=command_id,
                state=command.state,
                message=command.message,
                response=command.response,
                errors=command.errors,
                vehicle_name=vehicle_name,
                action_name=action_name,
            )
            return

        # Increase delay with exponential backoff
        delay = min(delay * COMMAND_POLL_BACKOFF_FACTOR, COMMAND_POLL_MAX_DELAY)


def _fire_result_event(
    hass: HomeAssistant,
    command_id: str,
    state: str | None,
    vehicle_name: str,
    action_name: str,
    message: str | None = None,
    response: str | None = None,
    errors: str | None = None,
) -> None:
    """Fire an event for command result."""
    hass.bus.async_fire(
        EVENT_COMMAND_RESULT,
        {
            "command_id": command_id,
            "vehicle_name": vehicle_name,
            "action_name": action_name,
            "state": state,
            "message": message,
            "response": response,
            "errors": errors,
        },
    )


def _create_notification(
    hass: HomeAssistant,
    command_id: str,
    state: str | None,
    vehicle_name: str,
    action_name: str,
    message: str | None = None,
    response: str | None = None,
    errors: str | None = None,
) -> None:
    """Create a persistent notification for command result."""
    if state == "acknowledged":
        title = f"Navirec: {action_name} for {vehicle_name} succeeded"
        notification_message = f"Response: {response or '-'}"
    elif state == "expired":
        title = f"Navirec: {action_name} for {vehicle_name} timed out"
        notification_message = ""
    else:
        title = f"Navirec: {action_name} for {vehicle_name} failed"
        notification_message = f"Errors: {errors or '-'}"

    async_create(
        hass,
        message=notification_message,
        title=title,
        notification_id=f"navirec_command_{command_id}",
    )
