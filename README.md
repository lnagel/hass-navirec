# Navirec

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

A Home Assistant custom integration for [Navirec](https://www.navirec.com/) fleet management platform. Track your
vehicles in real-time with GPS location, sensor data, and vehicle state monitoring.

## Features

- **Real-time GPS Tracking** - Live vehicle location updates via streaming API
- **Comprehensive Sensor Support** - Speed, fuel level, altitude, heading, distance, engine hours, and 400+ other sensor
  interpretations
- **Binary Sensors** - Ignition status, door locks, alarm states, driver card presence, and more
- **Stream-Based Updates** - Low-latency updates without polling, using Navirec's real-time streaming API
- **Automatic Reconnection** - Robust connection handling with exponential backoff

## Platforms

 Platform         | Description                                                              
------------------|--------------------------------------------------------------------------
 `device_tracker` | GPS location tracking for vehicles with speed, heading, and altitude     
 `sensor`         | Numeric and enum sensors (speed, fuel level, voltage, temperature, etc.) 
 `binary_sensor`  | Boolean states (ignition, alarms, door locks, driver card presence)      

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu and select "Custom repositories"
3. Add `https://github.com/lnagel/hass-navirec` as an Integration
4. Search for "Navirec" and install it
5. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/navirec` folder from this repository
2. Copy it to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

Configuration is done entirely through the Home Assistant UI.

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Navirec**
4. Enter your configuration:
    - **API URL**: Navirec API endpoint (default: `https://api.navirec.com/`)
    - **API Token**: Your API token from Navirec web app
    - **Account ID**: (Optional) Specific account to use

### Getting Your API Token

1. Log in to the [Navirec web application](https://app.navirec.com/)
2. Go to **Profile** > **Account settings**
3. Navigate to **API access**
4. Generate or copy your API token

### Reconfiguration

To update your API credentials:

1. Go to **Settings** > **Devices & Services**
2. Find the Navirec integration and click **Configure**
3. Update your API URL, token, or account ID as needed

## Entities

### Device Tracker

Each vehicle creates a device tracker entity with:

| Attribute                | Description                                               |
|--------------------------|-----------------------------------------------------------|
| `latitude` / `longitude` | GPS coordinates                                           |
| `speed`                  | Current speed                                             |
| `heading`                | Direction of travel                                       |
| `altitude`               | Elevation                                                 |
| `activity`               | Current state (driving, parking, idling, towing, offline) |
| `name_display`           | Vehicle display name                                      |
| `registration`           | Vehicle registration plate                                |

#### Map Card Labels

By default, the map card shows abbreviated entity names as marker labels. To display vehicle names or registration
plates instead, configure your map card with `label_mode: attribute`:

```yaml
type: map
entities:
  - entity: device_tracker.your_vehicle
    label_mode: attribute
    attribute: name_display  # or use "registration" for plate numbers
```

### Sensors

Sensors are dynamically created based on your vehicle's available interpretations:

| Sensor           | Unit  | Description              |
|------------------|-------|--------------------------|
| Speed            | km/h  | Current vehicle speed    |
| Fuel Level       | %     | Fuel tank level          |
| Total Distance   | km    | Odometer reading         |
| Engine Time      | hours | Total engine runtime     |
| Supply Voltage   | V     | Vehicle battery voltage  |
| Fuel Consumption | L     | Total fuel consumed      |
| Eco Score        | %     | Driving efficiency score |

*Many more sensors available depending on your vehicle's telematics hardware.*

### Binary Sensors

| Sensor           | Device Class     | Description               |
|------------------|------------------|---------------------------|
| Ignition         | power            | Engine ignition state     |
| Alarm            | safety           | Vehicle alarm triggered   |
| Panic            | safety           | Panic button pressed      |
| Driver Card      | connectivity     | Tachograph card inserted  |
| Vehicle Locked   | lock             | Central locking state     |
| Starter Blocked  | lock             | Starter immobilizer state |
| Battery Charging | battery_charging | EV charging status        |

### Diagnostic Sensors

Each vehicle also has diagnostic sensors (disabled by default):

| Sensor     | Description                        |
|------------|------------------------------------|
| Time       | Timestamp of the last GPS position |
| Updated At | Timestamp of the last state update |

## Technical Details

- **IoT Class**: Cloud Push (real-time streaming)
- **Integration Type**: Hub
- **Minimum HA Version**: 2025.10.0

The integration uses Navirec's NDJSON streaming API to receive real-time vehicle state updates. This provides immediate
updates without polling, reducing latency and API load.

## Development

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/lnagel/hass-navirec.git
cd hass-navirec

# Install dependencies with uv
uv sync --all-extras

# Run linting
./scripts/lint

# Start Home Assistant for development
./scripts/develop
```

### Running Tests

```bash
uv run pytest
```

### Code Quality

This project uses:

- **Ruff** for linting and formatting
- **pytest** with async support for testing
- **Pydantic** models auto-generated from OpenAPI spec

### Development Scripts

| Script                                       | Description                                      |
|----------------------------------------------|--------------------------------------------------|
| `./scripts/lint`                             | Format and lint code with Ruff                   |
| `./scripts/develop`                          | Start Home Assistant with the integration loaded |
| `uv run python scripts/generate_models.py`   | Regenerate Pydantic models from OpenAPI spec     |
| `uv run python scripts/download_fixtures.py` | Download fresh test fixtures from the API        |

## Contributing

Contributions are welcome! Please read the [Contribution guidelines](CONTRIBUTING.md) before submitting a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[navirec]: https://www.navirec.com/

[commits-shield]: https://img.shields.io/github/commit-activity/y/lnagel/hass-navirec.svg?style=for-the-badge

[commits]: https://github.com/lnagel/hass-navirec/commits/main

[hacs]: https://github.com/hacs/integration

[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge

[license-shield]: https://img.shields.io/github/license/lnagel/hass-navirec.svg?style=for-the-badge

[releases-shield]: https://img.shields.io/github/release/lnagel/hass-navirec.svg?style=for-the-badge

[releases]: https://github.com/lnagel/hass-navirec/releases
