"""
Custom integration to integrate Navirec with Home Assistant.

Navirec is a fleet management platform. This integration streams real-time
vehicle locations and sensor data via the Navirec API.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import NavirecApiClient
from .const import CONF_API_TOKEN, CONF_API_URL, LOGGER
from .const import DOMAIN as DOMAIN
from .coordinator import NavirecCoordinator
from .data import NavirecData, get_vehicle_id_from_sensor
from .models import Account, Sensor, Vehicle

if TYPE_CHECKING:
    from .data import NavirecConfigEntry

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    api_url = entry.data[CONF_API_URL]
    api_token = entry.data[CONF_API_TOKEN]

    # Create API client
    client = NavirecApiClient(
        api_url=api_url,
        api_token=api_token,
        session=async_get_clientsession(hass),
    )

    # Fetch accounts, vehicles, and sensors
    LOGGER.debug("Fetching accounts from Navirec API")
    accounts_data = await client.async_get_accounts()
    accounts = [Account.model_validate(a) for a in accounts_data]

    LOGGER.debug("Fetching vehicles from Navirec API")
    vehicles_data = await client.async_get_vehicles(active_only=True)

    LOGGER.debug("Fetching sensors from Navirec API")
    sensors_data = await client.async_get_sensors()

    # Build lookup dictionaries with Pydantic models
    vehicles: dict[str, Vehicle] = {}
    for v in vehicles_data:
        vehicle = Vehicle.model_validate(v)
        if vehicle.id:
            vehicles[str(vehicle.id)] = vehicle

    sensors: dict[str, Sensor] = {}
    sensors_by_vehicle: dict[str, list[Sensor]] = defaultdict(list)
    for s in sensors_data:
        sensor = Sensor.model_validate(s)
        if sensor.id:
            sensors[str(sensor.id)] = sensor
            # Extract vehicle ID from URL
            vehicle_id = get_vehicle_id_from_sensor(sensor)
            if vehicle_id and vehicle_id in vehicles:
                sensors_by_vehicle[vehicle_id].append(sensor)

    LOGGER.info(
        "Found %d accounts, %d vehicles, %d sensors",
        len(accounts),
        len(vehicles),
        len(sensors),
    )

    # Create coordinators for each account
    coordinators: dict[str, NavirecCoordinator] = {}
    for account in accounts:
        if not account.id:
            continue
        account_id = str(account.id)
        account_name = account.name or account_id

        coordinator = NavirecCoordinator(
            hass=hass,
            api_url=api_url,
            api_token=api_token,
            account_id=account_id,
            account_name=account_name,
        )
        coordinators[account_id] = coordinator

    # Store runtime data
    entry.runtime_data = NavirecData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinators=coordinators,
        accounts=accounts,
        vehicles=vehicles,
        sensors=sensors,
        sensors_by_vehicle=dict(sensors_by_vehicle),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start streaming for all coordinators
    for coordinator in coordinators.values():
        await coordinator.async_start_streaming()

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Stop streaming for all coordinators
    if entry.runtime_data:
        for coordinator in entry.runtime_data.coordinators.values():
            await coordinator.async_stop_streaming()

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
