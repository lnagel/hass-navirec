"""Constants for navirec."""

from logging import Logger, getLogger

from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfMass,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

LOGGER: Logger = getLogger(__package__)

DOMAIN = "navirec"
ATTRIBUTION = "Data provided by Navirec"

# API Configuration
API_VERSION = "1.45.0"
DEFAULT_API_URL = "https://api.navirec.com/"
USER_AGENT = "hass-navirec"

# Config entry keys
CONF_API_URL = "api_url"
CONF_API_TOKEN = "api_token"
CONF_ACCOUNT_ID = "account_id"

# Stream reconnection settings
STREAM_RECONNECT_MIN_DELAY = 1  # seconds
STREAM_RECONNECT_MAX_DELAY = 60  # seconds
STREAM_RECONNECT_MULTIPLIER = 2

# Storage settings
STORAGE_VERSION = 1
STORAGE_KEY = "navirec_stream_state"

# Mapping from Navirec API unit codes to Home Assistant unit constants
API_UNIT_TO_HA_UNIT: dict[str, str] = {
    "A": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "mV": UnitOfElectricPotential.MILLIVOLT,
    "c": UnitOfTemperature.CELSIUS,
    "kg": UnitOfMass.KILOGRAMS,
    "km__hr": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "l": UnitOfVolume.LITERS,
    "m": UnitOfLength.METERS,
    "km": UnitOfLength.KILOMETERS,
    "percent": PERCENTAGE,
    "rpm": REVOLUTIONS_PER_MINUTE,
    "s": UnitOfTime.SECONDS,
    "hr": UnitOfTime.HOURS,
}

# Interpretation keys that represent cumulative/total values
INTERPRETATIONS_TOTAL_INCREASING: frozenset[str] = frozenset(
    {
        "accumulated_distance",
        "accumulated_engine_time",
        "elect_odometer",
        "engine_total_fuel_used",
        "total_din1_time",
        "total_din2_time",
        "total_din3_time",
        "total_din4_time",
        "total_distance",
        "total_engine_time",
        "total_fuel_used",
        "total_gps_distance",
    }
)
