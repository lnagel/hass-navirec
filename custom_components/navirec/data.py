"""Custom types for navirec."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import NavirecApiClient
    from .coordinator import NavirecDataUpdateCoordinator


type NavirecConfigEntry = ConfigEntry[NavirecData]


@dataclass
class NavirecData:
    """Data for the Navirec integration."""

    client: NavirecApiClient
    coordinator: NavirecDataUpdateCoordinator
    integration: Integration
