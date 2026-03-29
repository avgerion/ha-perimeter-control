# Pi Supervisor REST API Contract

This document defines the HTTP API that Home Assistant queries to discover, monitor, and control Pi nodes.

## Authentication
All endpoints accept SSH key auth (done once during node addition in HA). Subsequent API calls happen over local network (Pi running on LAN).

Optional: Bearer token auth for remote scenarios (add `Authorization: Bearer {token}` header).

## Base URL
`http://{pi_hostname}:8080/api/v1`

---

## Node Information

### GET `/api/v1/node/info`
Returns hardware inventory, active capabilities, and supervisor status.

**Response:**
```json
{
  "node_id": "pi_kitchen",
  "hostname": "pi.local",
  "uptime_sec": 864000,
  "supervisor_version": "1.0.0",
  "python_version": "3.11.2",
  "os": "Raspberry Pi OS Bookworm",
  "hardware": {
    "model": "Raspberry Pi 5",
    "cpu_cores": 4,
    "ram_mb": 8192,
    "storage_gb": 64,
    "network_interfaces": ["eth0", "wlan0"],
    "ble_adapters": [
      {
        "name": "hci0",
        "type": "built-in",
        "address": "b8:27:eb:00:00:00",
        "version": "5.82"
      }
    ],
    "usb_devices": [
      {
        "vendor": "Silicon Labs",
        "product": "Wireless Gecko",
        "device": "/dev/ttyACM0"
      }
    ]
  },
  "capabilities": {
    "network_isolation": {
      "status": "active",
      "version": "1.0.0",
      "health": "ok",
      "services": ["isolator", "isolator-traffic", "isolator-dashboard"]
    },
    "ble_gatt_translator": {
      "status": "active",
      "version": "1.0.0",
      "health": "degraded",
      "services": ["ble-scanner", "ble-profiler"]
    },
    "pawr_esl_advertiser": {
      "status": "inactive",
      "reason": "dongle not detected",
      "version": "1.0.0"
    }
  },
  "timestamp": "2026-03-28T10:30:00Z"
}
```

---

## Entity Schema Discovery

### GET `/api/v1/entities`
Returns list of all entities the Pi is willing to expose to Home Assistant.

**Response:**
```json
{
  "entities": [
    {
      "id": "traffic_logger_running",
      "type": "binary_sensor",
      "friendly_name": "Traffic Logger",
      "icon": "mdi:card-outline",
      "capability": "network_isolation",
      "update_interval_sec": 60,
      "availability_mode": "always"
    },
    {
      "id": "device_traffic",
      "type": "sensor",
      "friendly_name_template": "{device_id} {metric}",
      "capability": "network_isolation",
      "unit_of_measurement": "packets",
      "update_interval_sec": 30,
      "dimensions": {
        "device_id": ["moto-g-2025", "guest-phone", "iot-sensor-01"],
        "metric": ["allowed_packets", "blocked_packets", "data_bytes"]
      }
    },
    {
      "id": "ble_device",
      "type": "sensor",
      "friendly_name_template": "BLE {device_id} {metric}",
      "capability": "ble_gatt_translator",
      "unit_of_measurement_template": "{metric}",
      "dimensions": {
        "device_id": ["kitchen_scale", "living_room_thermo"],
        "metric": ["rssi", "battery_percent", "last_seen"]
      }
    }
  ],
  "timestamp": "2026-03-28T10:30:00Z"
}
```

---

## Entity State Queries

### GET `/api/v1/entities/{entity_id}`
Get current state of a single entity.

**Example:**
`GET /api/v1/entities/traffic_logger_running`

**Response:**
```json
{
  "entity_id": "traffic_logger_running",
  "state": true,
  "state_class": null,
  "last_updated": "2026-03-28T10:29:50Z",
  "friendly_name": "Traffic Logger",
  "icon": "mdi:card-outline"
}
```

### GET `/api/v1/entities/device_traffic?device_id=moto-g-2025&metric=allowed_packets`
Get state of a templated entity with dimensions.

**Response:**
```json
{
  "entity_id": "device_traffic:moto_g_2025:allowed_packets",
  "state": 1247,
  "unit_of_measurement": "packets",
  "state_class": "total_increasing",
  "last_updated": "2026-03-28T10:29:55Z",
  "attributes": {
    "device_id": "moto-g-2025",
    "metric": "allowed_packets",
    "device_name": "Moto G (2025)",
    "online": true
  }
}
```

---

## Bulk State Fetch

### POST `/api/v1/entities/bulk`
Fetch state for multiple entities at once (reduces roundtrips).

**Request:**
```json
{
  "entities": [
    "traffic_logger_running",
    "device_traffic?device_id=moto-g-2025&metric=allowed_packets",
    "ble_device?device_id=kitchen_scale&metric=battery_percent"
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "entity_id": "traffic_logger_running",
      "state": true,
      "last_updated": "2026-03-28T10:29:50Z"
    },
    {
      "entity_id": "device_traffic:moto_g_2025:allowed_packets",
      "state": 1247,
      "last_updated": "2026-03-28T10:29:55Z"
    },
    {
      "entity_id": "ble_device:kitchen_scale:battery_percent",
      "state": 85,
      "last_updated": "2026-03-28T10:25:30Z"
    }
  ]
}
```

---

## Entity Updates (Event Stream)

### GET `/api/v1/events/entities?since={timestamp}` (Long-Poll)
Subscribe to entity state changes via long-polling. Returns when state changes or timeout (default 30s).

**Request:**
`GET /api/v1/events/entities?since=2026-03-28T10:29:00Z&timeout=30`

**Response:**
```json
{
  "events": [
    {
      "timestamp": "2026-03-28T10:29:50Z",
      "entity_id": "traffic_logger_running",
      "state": true,
      "reason": "periodic_update"
    },
    {
      "timestamp": "2026-03-28T10:29:55Z",
      "entity_id": "device_traffic:moto_g_2025:allowed_packets",
      "state": 1247,
      "reason": "state_change"
    }
  ]
}
```

**Alternative (WebSocket):** For real-time updates, Pi can expose `/ws/events`:
```websocket
message: { "subscribe": "entities" }
// Server sends updates as they occur
```

---

## Capabilities and Actions

### GET `/api/v1/capabilities`
List all capabilities with their actions.

**Response:**
```json
{
  "capabilities": [
    {
      "id": "network_isolation",
      "status": "active",
      "actions": [
        {
          "name": "reload_rules",
          "friendly_name": "Reload Firewall Rules",
          "description": "Regenerate and apply nftables rules from config"
        },
        {
          "name": "export_logs",
          "friendly_name": "Export Traffic Logs",
          "parameters": {
            "device_id": { "type": "string", "required": false },
            "format": { "type": "enum", "values": ["json", "csv"], "default": "json" }
          }
        }
      ]
    },
    {
      "id": "ble_gatt_translator",
      "status": "active",
      "actions": [
        {
          "name": "start_scan",
          "friendly_name": "Start BLE Scan"
        },
        {
          "name": "stop_scan",
          "friendly_name": "Stop BLE Scan"
        },
        {
          "name": "profile_device",
          "friendly_name": "Profile Device GATT",
          "parameters": {
            "mac_address": { "type": "string", "required": true },
            "timeout_sec": { "type": "integer", "default": 30 }
          }
        }
      ]
    }
  ]
}
```

### POST `/api/v1/capabilities/{capability_id}/actions/{action_name}`
Trigger a capability action.

**Example:** Reload firewall rules
```
POST /api/v1/capabilities/network_isolation/actions/reload_rules
```

**Response:**
```json
{
  "success": true,
  "message": "Firewall rules reloaded successfully",
  "execution_time_ms": 250,
  "result": {
    "rules_applied": 42,
    "errors": 0
  }
}
```

---

## Health and Diagnostics

### GET `/api/v1/health`
Get system-level health state.

**Response:**
```json
{
  "status": "healthy",  // healthy | degraded | unhealthy
  "last_check": "2026-03-28T10:30:00Z",
  "components": [
    {
      "name": "network_isolation",
      "status": "ok",
      "last_check": "2026-03-28T10:29:50Z"
    },
    {
      "name": "ble_gatt_translator",
      "status": "degraded",
      "issues": ["BLE adapter connection lost"],
      "last_check": "2026-03-28T10:29:55Z"
    }
  ]
}
```

### GET `/api/v1/capabilities/{capability_id}/diagnostics`
Download diagnostics bundle (logs, metrics, state dump) for a capability.

**Response:** (tar.gz file)
- `logs/` — recent service logs
- `metrics.json` — performance/health metrics
- `state.json` — capability state snapshot
- `config.yaml` — active capability config

---

## Configuration and Exposure

### GET `/api/v1/config/exposed_entities`
Get the current entity exposure configuration (which entities are advertised to HA).

**Response:**
```yaml
entities:
  network_isolation:
    - traffic_logger_running
    - device_traffic
    - nftables_active
  ble_gatt_translator:
    - scanner_active
    - device_count
    - devices
  pawr_esl_advertiser: []  # Inactive, no entities exposed

timestamp: "2026-03-28T10:30:00Z"
```

### PUT `/api/v1/config/exposed_entities`
Update which entities are exposed (changes take effect immediately).

**Request:**
```json
{
  "updates": {
    "network_isolation": {
      "add": ["nftables_active"],
      "remove": ["device_traffic"]
    }
  }
}
```

---

## Error Responses

All errors return JSON with consistent schema:

```json
{
  "error": "invalid_parameter",
  "message": "device_id must be a valid MAC address",
  "status_code": 400,
  "timestamp": "2026-03-28T10:30:00Z"
}
```

**Common error codes:**
- 400: Bad request (invalid params)
- 401: Unauthorized
- 404: Entity or capability not found
- 503: Service temporarily unavailable (capability starting up)

---

## Implementation Notes for HA Integration

**Discovery flow:**
1. HA has Pi SSH credentials from config.
2. SSH to Pi, run health check command.
3. Query `/api/v1/node/info` to confirm supervisor is running.
4. Query `/api/v1/entities` to learn available entities.
5. Cache entity schema locally in HA (refresh every 5 min or on manual refresh).

**Polling strategy:**
1. Query `/api/v1/events/entities?since={last_timestamp}&timeout=30` with long-poll.
2. Fall back to `/api/v1/entities/bulk` with fast poll (15-30 sec) if streaming is unavailable.
3. Detect offline: if no response after 3 timeouts, mark node as unreachable.

**Service exposure:**
- Render each action as an HA `script` or `button` entity.
- Example: `button.pi_kitchen_reload_firewall_rules` → calls `POST /api/v1/capabilities/network_isolation/actions/reload_rules`.
