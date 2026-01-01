"""
Custom types for navirec integration.

This module provides runtime data types and helper functions for the Navirec
integration. The API data models are auto-generated in models.py from the
OpenAPI specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import Interpretation, Sensor, Vehicle, VehicleState

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import NavirecApiClient
    from .coordinator import NavirecCoordinator


type NavirecConfigEntry = ConfigEntry[NavirecData]

# UUID regex pattern for extracting IDs from URLs
UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def extract_uuid_from_url(url: str) -> str | None:
    """
    Extract UUID from a Navirec API URL.

    Args:
        url: URL in format https://api.navirec.com/resource/{uuid}/

    Returns:
        The extracted UUID string, or None if not found.

    """
    if match := UUID_PATTERN.search(url):
        return match.group(0)
    return None


def get_vehicle_id_from_sensor(sensor: Sensor) -> str | None:
    """Extract vehicle ID from sensor's vehicle URL."""
    if sensor.vehicle:
        return extract_uuid_from_url(str(sensor.vehicle))
    return None


def get_vehicle_id_from_state(state: VehicleState) -> str | None:
    """Extract vehicle ID from state's vehicle URL."""
    if state.vehicle:
        return extract_uuid_from_url(str(state.vehicle))
    return None


def get_coordinates_from_state(
    state: VehicleState,
) -> tuple[float | None, float | None]:
    """
    Extract latitude and longitude from VehicleState location.

    Args:
        state: VehicleState with location in GeoJSON Point format

    Returns:
        Tuple of (latitude, longitude), or (None, None) if not available.
        Note: GeoJSON uses [longitude, latitude] order.

    """
    if state.location and state.location.coordinates:
        coords = state.location.coordinates
        if len(coords) >= 2:
            # GeoJSON is [longitude, latitude]
            return (coords[1], coords[0])
    return (None, None)


def get_sensor_value_from_state(state: VehicleState, interpretation: str) -> Any:
    """
    Get a sensor value from VehicleState by interpretation key.

    Args:
        state: VehicleState object
        interpretation: The sensor interpretation key (e.g., 'speed', 'fuel_level')

    Returns:
        The sensor value, or None if not present.

    """
    return getattr(state, interpretation, None)


def get_activity_from_state(state: VehicleState) -> str | None:
    """
    Get activity string from VehicleState.

    Args:
        state: VehicleState object

    Returns:
        Activity string (e.g., 'driving', 'parking') or None.

    """
    if state.activity:
        # Activity is a RootModel wrapping the enum
        return state.activity.root.value
    return None


def get_interpretation_choice_options(interpretation: Interpretation) -> list[str]:
    """
    Get list of choice options for ENUM sensors.

    Args:
        interpretation: Interpretation object with choices field

    Returns:
        List of choice value strings for use as sensor options.

    """
    if not interpretation.choices:
        return []
    # choices is a list of [value, label] pairs
    # For HA enum sensors, options should be the raw values (as strings)
    return [str(choice[0]) for choice in interpretation.choices]


@dataclass
class NavirecData:
    """
    Runtime data for the Navirec integration.

    Each config entry represents a single account. This simplifies the
    coordinator setup and entity creation.
    """

    client: NavirecApiClient
    integration: Integration
    coordinator: NavirecCoordinator
    account_id: str
    account_name: str
    vehicles: dict[str, Vehicle] = field(default_factory=dict)
    sensors: dict[str, Sensor] = field(default_factory=dict)
    sensors_by_vehicle: dict[str, list[Sensor]] = field(default_factory=dict)
    interpretations: dict[str, Interpretation] = field(default_factory=dict)


# Re-export for convenience
__all__ = [
    "Interpretation",
    "NavirecConfigEntry",
    "NavirecData",
    "Sensor",
    "Vehicle",
    "VehicleState",
    "extract_uuid_from_url",
    "get_activity_from_state",
    "get_coordinates_from_state",
    "get_interpretation_choice_options",
    "get_sensor_value_from_state",
    "get_vehicle_id_from_sensor",
    "get_vehicle_id_from_state",
]
