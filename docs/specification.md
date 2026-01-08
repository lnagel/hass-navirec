# Navirec Integration Specification

This document is the source of truth for design decisions in the hass-navirec integration.

## Overview

A Home Assistant custom integration for the Navirec fleet management platform. It enables real-time vehicle tracking and telemetry through cloud-push streaming rather than traditional polling.

- **Minimum Home Assistant:** 2025.10.0
- **IoT Class:** Cloud Push
- **Integration Type:** Service

## Architecture

### Data Flow

```
Navirec Streaming API (NDJSON)
        ↓
NavirecStreamClient.async_iter_events()
        ↓
NavirecCoordinator._async_handle_event()
        ↓
Entity listeners → async_write_ha_state()
```

### Core Components

| Component | Purpose |
|-----------|---------|
| `NavirecApiClient` | REST API wrapper for metadata and commands |
| `NavirecStreamClient` | NDJSON streaming client for real-time data |
| `NavirecCoordinator` | Data coordinator managing stream lifecycle |
| `NavirecData` | Runtime data container for cached metadata |

## Configuration

All configuration is UI-based via config flow:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| API URL | No | `https://api.navirec.com/` | Navirec API endpoint |
| API Token | Yes | - | Authentication token |
| Account ID | No | First available | Specific account UUID |

Multiple accounts are supported via separate config entries.

## Entity Types

### Device Tracker

**Entity:** `device_tracker.{vehicle_id}_location`

Tracks vehicle GPS location with real-time position updates.

**Attributes:** latitude, longitude, speed, heading, altitude, activity, name_display, registration, last_update

### Sensors

**Entity:** `sensor.{vehicle_id}_{sensor_id}`

Dynamic creation based on vehicle telemetry - one sensor per vehicle per sensor definition with matching interpretation.

**Device class derivation:**
- VOLTAGE: V, mV units
- CURRENT: A unit
- TEMPERATURE: °C unit
- DISTANCE: m, km units
- SPEED: km/h unit
- ENUM: interpretation has choices
- TIMESTAMP: datetime data type

**State class:**
- TOTAL_INCREASING: cumulative values (total_distance, total_engine_time, etc.)
- MEASUREMENT: all other numeric values

### Binary Sensors

**Entity:** `binary_sensor.{vehicle_id}_{sensor_id}`

Created only for interpretations with `data_type="boolean"`.

**Device class mapping:**
| Interpretation | Device Class |
|----------------|--------------|
| ignition | POWER |
| alarm, panic | SAFETY |
| driver_*_card_present | CONNECTIVITY |
| starter_blocked, vehicle_locked | LOCK |
| *_charging | BATTERY_CHARGING |
| scooter_buzzer | SOUND |

**Value inversion:** `starter_blocked` and `vehicle_locked` have inverted values to match HA LOCK semantics (is_on=True means unlocked/insecure).

### Buttons

**Entity:** `button.{vehicle_id}_{action_id}`

Execute remote vehicle actions (lock doors, block starter, etc.).

**Availability:** Always available regardless of stream connection or vehicle state. This allows users to trigger commands (e.g., GPS location update) before the initial state is received, which can take up to 20 minutes.

## Command Execution

### Flow

1. User triggers button or calls `navirec.execute_action` service
2. API creates DeviceCommand
3. Background polling task monitors command status
4. On completion, fires `navirec_command_result` event and creates notification

### Polling Schedule

- Initial delay: 2 seconds
- Max delay: 900 seconds (15 minutes)
- Backoff factor: 1.5x

### Terminal States

- `acknowledged` - Command succeeded
- `failed` - Command failed
- `expired` - Command timed out

## API Communication

### Authentication

```http
Authorization: Token {api_token}
Accept: application/json; version=1.45.0
```

### Streaming

```http
GET /streams/vehicle_states/?account={id}&updated_at__gt={timestamp}
Accept: application/x-ndjson; version=1.45.0
```

**Event types:** connected, vehicle_state, initial_state_sent, heartbeat, disconnected

**Resume capability:** Persists `updated_at` timestamp to HA Store for reconnection without data loss.

### Rate Limiting

- Respects HTTP 429 with `Retry-After` header
- Stream connections: 6/minute limit
- Exponential backoff on connection failure (1s → 60s)

## Key Design Decisions

### 1. Streaming vs Polling

**Decision:** NDJSON streaming with connection persistence

**Rationale:**
- Real-time data without polling latency
- Reduced API load
- Immediate state updates for critical data (location, ignition)
- Heartbeat-based connection health monitoring (30s interval)

### 2. Stream State Persistence

**Decision:** Persist `updated_at` timestamp across restarts

**Rationale:**
- Resume without missing intermediate updates
- Survives HA reloads, restarts, integration unload/reload
- Storage key: `navirec_stream_state_{account_id}`

### 3. Single Coordinator per Account

**Decision:** One config entry = one account = one coordinator

**Rationale:**
- Single stream connection per account (API limitation)
- Clean separation of accounts
- Unique ID based on account_id prevents duplicates

### 4. Binary Sensor Value Inversion

**Decision:** Explicit inversion for LOCK device class sensors

**Rationale:**
- HA LOCK semantics: is_on=True means unlocked (insecure)
- Navirec API: true means locked (secure)
- Explicit inversion list documents semantic difference

### 5. Metadata Caching at Startup

**Decision:** Fetch all vehicles, sensors, interpretations at setup time

**Rationale:**
- Entity definitions don't change frequently
- Avoids dynamic entity discovery complexity
- Single startup cost (~5-10 API requests)

**Trade-off:** New vehicles/sensors require integration reload.

### 6. Command Polling with Exponential Backoff

**Decision:** Exponential backoff for command status polling

**Rationale:**
- Commands may take seconds/minutes to execute
- Device needs processing time
- Avoids API rate limit issues

## Limitations

### Stream

- Requires persistent connection (firewalls/proxies may timeout)
- 35-second read timeout (heartbeats every 30s)
- Server disconnects ~1h for recycling (auto-reconnect handles it)

### Commands

- Asynchronous execution (no immediate response)
- Commands can expire if device unreachable
- Results communicated via event/notification only

### Metadata

- Static on startup - new vehicles/sensors require reload
- Sensor availability depends on vehicle hardware
- Entity enabled status controlled by API `show_in_map` flag

## Services

### navirec.execute_action

Execute a vehicle action by IDs.

```yaml
service: navirec.execute_action
data:
  vehicle_id: "uuid-string"
  action_id: "uuid-string"
```

## Events

### navirec_command_result

Fired when a command reaches terminal state.

```yaml
event_type: navirec_command_result
data:
  command_id: "uuid"
  vehicle_name: "Vehicle Name"
  action_name: "Action Name"
  state: "acknowledged|failed|expired"
  message: "optional message"
  response: "optional response"
  errors: "optional errors"
```