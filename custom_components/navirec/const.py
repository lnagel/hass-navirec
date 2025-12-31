"""Constants for navirec."""

from logging import Logger, getLogger

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

# Binary sensor interpretations (boolean values in VehicleState)
BINARY_SENSOR_INTERPRETATIONS = frozenset(
    {
        "ignition",
        "alarm",
        "digital_input_1",
        "digital_input_2",
        "digital_input_3",
        "digital_input_4",
        "digital_input_5",
        "digital_input_6",
        "digital_input_7",
        "digital_input_8",
        "digital_output_1",
        "digital_output_2",
        "digital_output_3",
        "digital_output_4",
        "driver_1_card_present",
        "driver_2_card_present",
        "panic",
        "notification",
        "starter_blocked",
        "vehicle_locked",
        "hv_battery_charging",
        "scooter_charging",
        "scooter_buzzer",
    }
)
