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
from .const import CONF_ACCOUNT_ID, CONF_API_TOKEN, CONF_API_URL, LOGGER
from .const import DOMAIN as DOMAIN
from .coordinator import NavirecCoordinator
from .data import NavirecData, get_vehicle_id_from_sensor
from .models import Sensor, Vehicle

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
    account_id = entry.data[CONF_ACCOUNT_ID]

    # Create API client
    client = NavirecApiClient(
        api_url=api_url,
        api_token=api_token,
        session=async_get_clientsession(hass),
    )

    # Fetch account info to get the name
    LOGGER.debug("Fetching account info from Navirec API")
    accounts_data = await client.async_get_accounts()
    account_name = account_id  # fallback
    for acc in accounts_data:
        if acc.get("id") == account_id:
            account_name = acc.get("name") or account_id
            break

    # Fetch vehicles and sensors for this account
    LOGGER.debug("Fetching vehicles for account %s", account_id)
    vehicles_data = await client.async_get_vehicles(
        account_id=account_id, active_only=True
    )

    LOGGER.debug("Fetching sensors for account %s", account_id)
    sensors_data = await client.async_get_sensors(account_id=account_id)

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
        "Account %s: found %d vehicles, %d sensors",
        account_name,
        len(vehicles),
        len(sensors),
    )

    # Create single coordinator for this account
    coordinator = NavirecCoordinator(
        hass=hass,
        api_url=api_url,
        api_token=api_token,
        account_id=account_id,
        account_name=account_name,
    )

    # Store runtime data
    entry.runtime_data = NavirecData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        account_id=account_id,
        account_name=account_name,
        vehicles=vehicles,
        sensors=sensors,
        sensors_by_vehicle=dict(sensors_by_vehicle),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start streaming
    await coordinator.async_start_streaming()

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Stop streaming
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        await entry.runtime_data.coordinator.async_stop_streaming()

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
