# BLE Device Profile Registry

Reusable, versionable GATT translation profiles for common and custom devices.

## Profile Structure

```
/opt/isolator/data/profiles/
├── built_in/
│   ├── std_profiles/
│   │   ├── @1.0.0/
│   │   │   ├── thermometer.yaml
│   │   │   ├── kitchen_scale.yaml
│   │   │   ├── motion_sensor.yaml
│   │   │   └── heart_rate_monitor.yaml
│   │   └── @1.1.0/
│   │       ├── (updated profiles)
│   └── vendor_specific/
│       ├── apple_airpods.yaml
│       ├── xiaomi_mi_band.yaml
│       └── (vendor profiles)
└── custom/
    ├── my_iot_device_v1.yaml
    ├── proprietary_sensor.yaml
    └── (user-authored)
```

## Profile Schema

```yaml
# complete profile example

schema_version: "1.0"
name: "Kitchen Scale"
version: "1.0.0"
author: "isolator.dev"
repository: "https://github.com/avgerion/ha-perimeter-control/profiles
description: "Weight scale using standard GATT Weight Scale Service"

# Device matching
match:
  # Any of these can match (OR logic)
  - uuid_service: "181d"            # Weight Scale Service
    uuid_manufacturer: null          # Any manufacturer
    
  - local_name_prefix: "scale"      # Or match by name
    
  - mac_address_ranges:             # Or match by MAC
      - start: "AA:BB:CC:00:00:00"
        end: "AA:BB:CC:FF:FF:FF"

# GATT Services and Characteristics to expose
services:
  - uuid: 181d                      # Weight Scale Service
    characteristics:
      - uuid: 2a98                  # Weight
        name: weight
        unit: kg
        data_type: uint16           # Encoding
        scale: 0.01                 # Multiply raw by 0.01 (e.g., 50000 → 500.0)
        offset: 0
        min: 0
        max: 500
        ha_device_class: weight
        icon: mdi:scale-bathroom
        
      - uuid: 2a19                  # Battery Level
        name: battery_percent
        unit: "%"
        data_type: uint8
        ha_device_class: battery
        entity_category: diagnostic
        icon: mdi:battery

  - uuid: 180a                      # Device Information Service
    characteristics:
      - uuid: 2a29                  # Manufacturer Name
        name: manufacturer
        data_type: string
        entity_category: diagnostic

# Translation rules (advanced)
translations:
  - characteristic_uuid: 2a98
    value_template: "{{ (raw_value * 0.01) | round(1) }}"  # Jinja2 template
    precision: 1
    state_class: measurement        # measurement | total | total_increasing
    
# Availability probe (optional)
availability:
  - type: characteristic_notify
    uuid: 2a19                      # If battery notifies, device available
    timeout_sec: 300

# Connection settings
connection:
  encryption: false                # Force encryption
  mtu: 23                          # Preferred MTU
  connection_interval_ms: 1000
  
# Reconnection policy
reconnection:
  max_attempts: 5
  backoff_base_sec: 2
  backoff_max_sec: 30
  retry_after_disconnect: true

# Required for Home Assistant integration
home_assistant:
  # One entity per characteristic
  entities:
    - uuid: 2a98
      platform: sensor              # binary_sensor | sensor | number | switch
      device_class: weight
      state_class: measurement
      unit_of_measurement: kg
      
    - uuid: 2a19
      platform: sensor
      device_class: battery
      unit_of_measurement: "%"
      entity_category: diagnostic
```

## Built-in Standard Profiles

Pre-packaged profiles for common devices:

### Thermometer (Environmental Sensing)

```yaml
name: "BLE Thermometer"
match:
  - uuid_service: 180a              # Environmental Sensing Service

services:
  - uuid: 180a
    characteristics:
      - uuid: 2a1c                  # Temperature
        name: temperature
        unit: °C
        scale: 0.01
        ha_device_class: temperature
      - uuid: 2a1e                  # Humidity
        name: humidity
        unit: "%"
        ha_device_class: humidity
```

### Kitchen Scale (Weight)

```yaml
name: "Kitchen Scale"
match:
  - uuid_service: 181d
  - local_name_prefix: "scale"

services:
  - uuid: 181d
    characteristics:
      - uuid: 2a98                  # Weight
        scale: 0.01
        ha_device_class: weight
```

### Motion Sensor

```yaml
name: "Motion Sensor"
match:
  - uuid_service: 180a
  - local_name: "*motion*"

services:
  - uuid: 180a
    characteristics:
      - uuid: 2a6c                  # Motion
        name: motion
        data_type: boolean
        ha_device_class: motion
```

### Heart Rate Monitor

```yaml
name: "Heart Rate Monitor"
match:
  - uuid_service: 180d              # Heart Rate Service

services:
  - uuid: 180d
    characteristics:
      - uuid: 2a37                  # Heart Rate Measurement
        name: heart_rate
        unit: bpm
        ha_device_class: heart_rate
```

## Community Profile Registry

Central repository for user-contributed profiles:

```
https://profiles.isolator.dev/

GET /profiles
  → List all published profiles

GET /profiles/kitchen_scale@1.0.0
  → Fetch profile YAML

POST /profiles
  → Submit new profile (requires auth + community review)
```

Python package: `pip install isolator-profiles`

```python
from isolator_profiles import load_profile

profile = load_profile("kitchen_scale@1.0.0")
# or
profile = load_profile("custom/my_device")
```

## Custom Profile Authoring

Users create profiles in Tornado/Bokeh UI or edit YAML directly:

### UI Workflow

1. **Discover device** — start BLE scan
2. **Connect to device** — select from scan results
3. **Browse GATT** — show all services/chars
4. **Map characteristics** — drag UUIDs to HA entities
5. **Test values** — read/subscribe to verify parsing
6. **Save profile** — export as YAML + local store

### Example Custom Profile

```yaml
# /opt/isolator/data/profiles/custom/my_iot_sensor.yaml

schema_version: "1.0"
name: "My IoT Sensor"
description: "Proprietary temperature + motion sensor"

match:
  - manufacturer_name: "MyCompany"
  - local_name: "SENSOR*"

services:
  - uuid: a0000000-b0c0-11e3-a5e2-0800200c9a66
    characteristics:
      - uuid: a0000001-b0c0-11e3-a5e2-0800200c9a66
        name: temperature
        unit: °C
        scale: 0.1
        ha_device_class: temperature
        
      - uuid: a0000002-b0c0-11e3-a5e2-0800200c9a66
        name: motion
        data_type: boolean
        ha_device_class: motion
```

## Profile Versioning and Compatibility

Profiles can evolve:

```
kitchen_scale@1.0.0
  → Original profile, 10 installations
  
kitchen_scale@1.1.0
  → Add battery characteristic
  → Auto-upgrade existing devices

kitchen_scale@2.0.0
  → Breaking change: change scale factor
  → User must manually review or stay on @1.1.0
```

Migration rules:

```yaml
migrations:
  from: "1.0.0"
  to: "1.1.0"
  changes:
    - added: battery_percent
    - no_breaking_changes: true
    - auto_apply: true          # Auto-upgrade without user prompt
```

## Profile Testing

Profiles can include test vectors:

```yaml
test_vectors:
  - name: "Static weight reading"
    raw_bytes: [0x87, 0xc4]  # 50247 → 502.47 kg (with scale 0.01)
    expected_value: 502.47
    expected_unit: kg
    
  - name: "Maximum weight"
    raw_bytes: [0xff, 0xff]
    expected_value: 655.35
    
  - name: "Battery low"
    characteristic_uuid: 2a19
    raw_bytes: [0x05]  # 5%
    expected_value: 5
    expected_unit: "%"
```

Test via: `isolator profile test my_device.yaml`

## Profile Metrics

Track profile effectiveness:

```json
{
  "profile_id": "kitchen_scale@1.0.0",
  "installations": 42,
  "successful_connections": 1250,
  "failed_connections": 8,
  "success_rate": 0.994,
  "avg_discovery_time_ms": 8500,
  "users": 38,
  "ratings": {
    "average": 4.7,
    "count": 15
  },
  "last_updated": "2026-02-15"
}
```

## Profile Sharing

Export/import profiles:

```bash
# Export local profile
isolator profile export custom/my_device.yaml → my_device_export.isolator

# Import profile from file
isolator profile import my_device_export.isolator → custom/my_device_v2.yaml

# Share via registry
isolator profile publish custom/my_device.yaml --public
```

## Profile Conflict Resolution

If two profiles match same device, use priority:

```
Priority order (highest first):
1. User's custom profiles (in /opt/isolator/data/profiles/custom/)
2. Device-specific pinned profile
3. Vendor-specific profiles (@1.1.0+)
4. Standard profiles by UUID match confidence score

Example:
- Both "thermometer" and "apple_airpods" match UUID 180a
- If local_name matches "iPad" → use apple_airpods (higher specificity)
- Otherwise: use thermometer (generic match)
```
