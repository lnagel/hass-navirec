"""
Custom integration to integrate Navirec with Home Assistant.

Navirec is a fleet management platform. This integration streams real-time
vehicle locations and sensor data via the Navirec API.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, NamedTuple

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from pydantic import BaseModel, ValidationError

from .api import (
    NavirecApiClient,
    NavirecApiClientAuthenticationError,
    NavirecApiClientError,
    NavirecApiClientRateLimitError,
)
from .const import CONF_ACCOUNT_ID, CONF_API_TOKEN, CONF_API_URL, DOMAIN, LOGGER
from .coordinator import NavirecCoordinator
from .data import NavirecData, get_vehicle_id_from_action, get_vehicle_id_from_sensor
from .models import Action, Interpretation, Sensor, Vehicle
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    from .data import NavirecConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Navirec integration."""
    await async_setup_services(hass)
    return True


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

    # Fetch all metadata up front. Nothing is registered with Home Assistant
    # until this succeeds, so a failure leaves no partial state behind.
    raw = await _async_fetch_metadata(client, account_id)

    account_name = account_id  # fallback
    for acc in raw.accounts:
        if acc.get("id") == account_id:
            account_name = acc.get("name") or account_id
            break

    # Build lookup dictionaries with Pydantic models
    vehicles: dict[str, Vehicle] = {}
    for vehicle in _validate_items(Vehicle, raw.vehicles):
        if vehicle.id:
            vehicles[str(vehicle.id)] = vehicle

    sensors: dict[str, Sensor] = {}
    sensors_by_vehicle: dict[str, list[Sensor]] = defaultdict(list)
    for sensor in _validate_items(Sensor, raw.sensors):
        if sensor.id:
            sensors[str(sensor.id)] = sensor
            # Extract vehicle ID from URL
            vehicle_id = get_vehicle_id_from_sensor(sensor)
            if vehicle_id and vehicle_id in vehicles:
                sensors_by_vehicle[vehicle_id].append(sensor)

    interpretations: dict[str, Interpretation] = {}
    for interpretation in _validate_items(Interpretation, raw.interpretations):
        if interpretation.key:
            interpretations[interpretation.key] = interpretation

    actions_by_vehicle: dict[str, list[Action]] = defaultdict(list)
    for action in _validate_items(Action, raw.actions):
        vehicle_id = get_vehicle_id_from_action(action)
        if vehicle_id and vehicle_id in vehicles:
            actions_by_vehicle[vehicle_id].append(action)

    # Count total actions across all vehicles
    total_actions = sum(len(actions) for actions in actions_by_vehicle.values())

    LOGGER.info(
        "Account %s: found %d vehicles, %d sensors, %d interpretations, %d actions",
        account_name,
        len(vehicles),
        len(sensors),
        len(interpretations),
        total_actions,
    )

    # Create single coordinator for this account
    coordinator = NavirecCoordinator(
        hass=hass,
        config_entry=entry,
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
        interpretations=interpretations,
        actions_by_vehicle=dict(actions_by_vehicle),
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start streaming
    await coordinator.async_start_streaming()

    return True


class _RawMetadata(NamedTuple):
    """Raw API responses fetched during setup."""

    accounts: list[dict[str, Any]]
    vehicles: list[dict[str, Any]]
    sensors: list[dict[str, Any]]
    interpretations: list[dict[str, Any]]
    actions: list[dict[str, Any]]


async def _async_fetch_metadata(
    client: NavirecApiClient, account_id: str
) -> _RawMetadata:
    """
    Fetch the metadata needed to build entities.

    API errors are translated into the exceptions Home Assistant uses to
    decide what happens next: ConfigEntryAuthFailed starts a reauth flow,
    ConfigEntryNotReady schedules a setup retry with backoff.
    """
    try:
        LOGGER.debug("Fetching account info from Navirec API")
        accounts = await client.async_get_accounts()

        LOGGER.debug("Fetching vehicles for account %s", account_id)
        vehicles = await client.async_get_vehicles(
            account_id=account_id, active_only=True
        )

        LOGGER.debug("Fetching sensors for account %s", account_id)
        sensors = await client.async_get_sensors(account_id=account_id)

        LOGGER.debug("Fetching interpretations")
        interpretations = await client.async_get_interpretations()

        LOGGER.debug("Fetching actions for account %s", account_id)
        actions = await client.async_get_actions(account_id=account_id)
    except NavirecApiClientAuthenticationError as err:
        msg = f"Authentication with the Navirec API failed: {err}"
        raise ConfigEntryAuthFailed(msg) from err
    except NavirecApiClientRateLimitError as err:
        msg = f"Rate limited by the Navirec API, retry after {err.retry_after}s"
        raise ConfigEntryNotReady(msg) from err
    except NavirecApiClientError as err:
        # Network errors, timeouts, 5xx and malformed responses are usually
        # transient
        msg = f"Unable to fetch data from the Navirec API: {err}"
        raise ConfigEntryNotReady(msg) from err

    return _RawMetadata(accounts, vehicles, sensors, interpretations, actions)


def _validate_items[ModelT: BaseModel](
    model: type[ModelT], items: list[dict[str, Any]]
) -> list[ModelT]:
    """
    Validate API items into models, skipping the ones that fail validation.

    A single unexpected record (e.g. after an API change) should cost only
    that record, not the whole config entry.
    """
    validated: list[ModelT] = []
    for item in items:
        try:
            validated.append(model.model_validate(item))
        except ValidationError as err:
            LOGGER.warning(
                "Skipping invalid %s from Navirec API (id=%s): %s",
                model.__name__,
                item.get("id") if isinstance(item, dict) else None,
                err,
            )
    return validated


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NavirecConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Stop streaming
    if entry.runtime_data is not None:
        await entry.runtime_data.coordinator.async_stop_streaming()

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
