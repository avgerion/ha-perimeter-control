# Capability Schema Reference

This document defines the YAML schema for each capability runtime. Schemas are inspired by ESPHome's simple, declarative style.

## Common Capability Manifest Structure

Every capability is deployed with a manifest that declares requirements, conflicts, and health probes.

```yaml
# Base capability structure (common to all)
id: network_isolator          # Unique capability ID
version: "1.0"                # Semantic version
package: network_isolation    # Python package name
image_tag: "latest"           # Container or venv tag
priority_class: critical      # critical | high | normal | best-effort

# Resource requirements
resources:
  cpu_cores: 1                # Minimum CPU cores
  cpu_load_percent: 30        # Max sustained load %
  ram_mb: 256                 # Minimum RAM in MB
  disk_free_mb: 1000          # Minimum free disk
  io_read_mb_sec: 50          # Max read throughput
  io_write_mb_sec: 50         # Max write throughput

# Hardware requirements
hardware:
  required_interfaces:
    - wlan0                   # Must have AP interface
    - eth0                    # Must have uplink
  required_features:
    - nftables                # Kernel feature
    - netfilter               # Kernel feature
  # Conflict with hardware in use (e.g., "ble_radio_0" if BLE scan active)
  exclusive_resources:
    - ble_radio_0             # Cannot coexist with active BLE on radio 0

# Health probes
health:
  startup_grace_period_sec: 10
  probes:
    - name: nftables_active
      type: exec
      command: ["sudo", "nft", "list", "ruleset"]
      interval_sec: 30
      timeout_sec: 5
    - name: traffic_logger_running
      type: process
      pattern: traffic-logger.py
      interval_sec: 60
      timeout_sec: 5

# Rollback policy
rollback_policy:
  max_failed_deployments: 2   # Auto-rollback after N failures
  health_check_timeout_sec: 60
  keep_versions: 3

# Secrets (referenced by Home Assistant secure store keys)
secrets: {}                   # Filled by HA integration

# Service lifecycle
services:
  - name: isolator
    type: systemd
    unit: isolator.service
  - name: isolator-traffic
    type: systemd
    unit: isolator-traffic.service
  - name: isolator-dashboard
    type: systemd
    unit: isolator-dashboard.service
```

## 1. Network Isolation Capability

Firewall rules, traffic logging, and device policy enforcement.

```yaml
id: network_isolator
version: "1.0"

package: network_isolation
priority_class: critical

resources:
  cpu_cores: 1
  ram_mb: 256
  disk_free_mb: 2000

hardware:
  required_interfaces:
    - wlan0
    - eth0
  required_features:
    - nftables
    - netfilter

health:
  startup_grace_period_sec: 15
  probes:
    - name: nftables_loaded
      type: exec
      command: ["sudo", "nft", "list", "table", "inet", "isolator"]
      interval_sec: 30
    - name: traffic_logger_running
      type: process
      pattern: traffic-logger.py
      interval_sec: 60

# Capability-specific config
config:
  # WiFi AP configuration
  wifi:
    ssid: MyNetwork
    password: !secret wifi_password
    band: 2.4GHz
    channel: 6
    max_clients: 32

  # Network interfaces
  interfaces:
    ap: wlan0
    upstream: eth0

  # IP ranges for LAN
  lan:
    network: 192.168.111.0/24
    gateway: 192.168.111.1
    dhcp_start: 192.168.111.100
    dhcp_end: 192.168.111.200
    lease_hours: 24

  # Global logging policy (default for unknown devices)
  default_policy:
    internet: log-only        # log-only | allow | deny
    lan_access: []            # Allowed LAN destinations
    logging: full             # full | metadata | disabled
    capture:
      enabled: true
      rotate_mb: 100

  # Per-device rules (overrides default policy)
  devices:
    - id: trusted-laptop
      mac: aa:bb:cc:dd:ee:ff
      name: Trusted Laptop
      internet: allow
      logging: metadata       # Less verbose logging
      lan_access:
        - host: 192.168.50.10
          ports: [22, 80, 443, 445]
      capture:
        enabled: false        # Don't capture this device

    - id: iot-sensor-01
      mac: 11:22:33:44:55:66
      name: IoT Sensor
      internet: deny
      logging: full
      capture:
        enabled: true
        filter: "tcp or udp"

    - id: guest-phone
      mac: aa:11:bb:22:cc:33
      name: Guest Phone
      internet: allow
      logging: metadata

  # Logging and storage
  logging:
    output: /var/log/isolator/traffic.log
    rotate_mb: 50
    retain_days: 30
    format: json

  capture:
    base_output_dir: /mnt/isolator/captures
    default_rotate_mb: 100
    default_retention_days: 7

# Entities exposed to Home Assistant (Pi declares availability)
exposed_entities:
  traffic_logger_running:
    type: binary_sensor
    friendly_name: Traffic Logger
    icon: mdi:card-outline
    availability_topic: null  # Always available if supervisor is responding

  device_traffic:
    # One entity per configured device
    # Template: device_traffic:{device_id}:{metric}
    type: sensor
    device_class: null
    unit_of_measurement: packets
    friendly_name_template: "{device_id} {metric}"
    metrics:
      - allowed_packets
      - blocked_packets
      - data_bytes

  nftables_active:
    type: binary_sensor
    friendly_name: nftables Firewall
    icon: mdi:shield-check

  default_policy_internet:
    type: enum_sensor
    friendly_name: Default Internet Policy
    values: [ log-only, allow, deny ]
    icon: mdi:network

```

**ESPHome-inspired features:**
- `!secret` references for sensitive values
- Simple list syntax for rules
- Flat key-value where possible
- Clear defaults

---

## 2. BLE GATT Translation Capability

Scan for BLE devices, profile their GATT, translate to sensors in Home Assistant.

```yaml
id: ble_gatt_translator
version: "1.0"

package: ble_controller
priority_class: normal

resources:
  cpu_cores: 1
  ram_mb: 512
  disk_free_mb: 500

hardware:
  # Can use native BLE or external dongle
  ble_adapters:
    - /dev/ttyACM0            # SiLabs WSTK or CDC async
    - hci0                    # Native adapter
  exclusive_resources:
    - ble_radio_0             # Exclusive use of BLE radio
    - network_isolator:ble_blocking  # If network isolator needs BLE for device profiling

health:
  startup_grace_period_sec: 20
  probes:
    - name: scanner_active
      type: process
      pattern: ble-scanner
      interval_sec: 30
    - name: translator_active
      type: process
      pattern: ble-gatt-mirror
      interval_sec: 30

# Capability-specific config
config:
  # Scanner settings
  scanner:
    duration_sec: 25          # Active scan cycle
    interval_ms: 100          # Scan interval
    window_ms: 50             # Scan window
    phys: [1m]                # 1M PHY (or 2m for coded)

  # Profiler / GATT discovery
  profiler:
    enabled: true
    service_discovery_timeout_sec: 25
    max_gatt_attempts: 0      # 0 = infinite retry
    backoff_min_sec: 2
    backoff_max_sec: 20
    use_cached_services: false

  # GATT translation profiles (built-in and custom)
  profiles:
    # Built-in profiles
    - name: ble_standard_thermometer
      uuid: 180a              # Environmental Sensing Service
      include_characteristics:
        - uuid: 2a1c          # Temperature; maps to home_assistant.sensor
      translations:
        - characteristic_uuid: 2a1c
          ha_domain: sensor
          ha_device_class: temperature
          unit_of_measurement: "°C"

    - name: ble_kitchen_scale
      uuid: 181d              # Weight Scale Service
      include_characteristics:
        - uuid: 2a98          # Weight
      translations:
        - characteristic_uuid: 2a98
          ha_domain: sensor
          ha_device_class: weight
          unit_of_measurement: "kg"

    # Custom user profile
    - name: custom_iot_sensor
      filter:
        manufacturer_id: 0x004c  # Apple
        local_name_prefix: "sensor_"
      include_characteristics:
        - uuid: a1000000-b1c2-11e3-a5e2-0800200c9a66
      translations:
        - characteristic_uuid: a1000000-b1c2-11e3-a5e2-0800200c9a66
          ha_domain: sensor
          value_template: "{{ value | int }}"

  # Known devices to always profile
  known_devices:
    - mac: de:ad:be:ef:00:01
      name: kitchen_scale
      profile: ble_kitchen_scale
      auto_connect: true

    - mac: ca:fe:ba:be:a0:00
      name: living_room_thermo
      profile: ble_standard_thermometer
      auto_connect: true

  # Connection retry logic
  connection:
    max_attempts: 5
    backoff_base_sec: 2
    timeout_sec: 10

  # Logging
  logging:
    level: info
    output: /var/log/isolator/ble.log
    capture_dir: /var/log/isolator/ble/captures

# Entities exposed to Home Assistant (Pi declares availability)
exposed_entities:
  scanner_active:
    type: binary_sensor
    friendly_name: BLE Scanner
    icon: mdi:bluetooth-connect
    update_interval_sec: 30

  device_count:
    type: sensor
    friendly_name: BLE Devices Found
    device_class: null
    update_interval_sec: 30
    unit_of_measurement: devices
    icon: mdi:bluetooth

  devices:
    # One sensor per discovered device
    # Template: ble_device:{device_id}:{metric}
    type: sensor
    friendly_name_template: "BLE {device_id} {metric}"
    metrics:
      - rssi
      - connected
      - last_seen
      - battery_percent
    icon_template: mdi:bluetooth

  profiler_status:
    type: enum_sensor
    friendly_name: GATT Profiler
    values: [ idle, running, succeeded, failed ]
    icon: mdi:cards

```

**ESPHome-inspired features:**
- Nested `scanner`, `profiler`, `profiles` sections
- UUID filtering with flexible matchers
- Built-in and custom profile inheritance
- Value templates for transformations
- Backoff and retry as first-class config

---

## 3. PAwR ESL Advertiser Capability

Broadcast PAwR (Periodic Advertising with Response) for Electronic Shelf Labels.

```yaml
id: pawr_esl_advertiser
version: "1.0"

package: pawr_esl
priority_class: high

resources:
  cpu_cores: 2
  ram_mb: 1024
  disk_free_mb: 500

hardware:
  # Must use external dongle or specific chipset
  ble_adapters:
    - /dev/ttyACM0            # SiLabs or Nordic Semiconductor dongle
  exclusive_resources:
    - ble_radio_0             # Exclusive BLE radio usage
    - network_isolator:ble_scan  # Cannot coexist with active scanner

preemption_policy:
  higher_priority_classes: []  # (nothing can preempt this)
  can_preempt:
    - ble_gatt_translator     # Can pause BLE scanner

health:
  startup_grace_period_sec: 30
  probes:
    - name: pawr_advertiser_active
      type: process
      pattern: pawr-advertiser.py
      interval_sec: 30
    - name: dongle_responsive
      type: exec
      command: ["btmgmt", "info"]
      interval_sec: 60

# Capability-specific config
config:
  # Dongle / radio config
  radio:
    adapter: /dev/ttyACM0
    chipset: silabs              # silabs | nordic | broadcom
    firmware_version_min: "1.0.0"
    max_tx_power_dbm: 8
    frequency_hopping: true

  # PAwR advertising parameters
  advertising:
    interval_ms: 100             # Periodic adv interval
    window_ms: 10                # Adv window
    phy: 2m                      # 1m | 2m | coded
    data_length_bytes: 1650       # Max PAwR subevent data

  # Response-slot scheduling
  response_slots:
    count_per_period: 10
    duration_us: 5000
    response_tx_power_dbm: 8

  # ESL groups and products
  esl_groups:
    - id: grocery_section
      name: Produce Aisle
      max_tag_count: 50
      update_interval_sec: 30
      tags:
        - id: esl_001
          name: Lettuce Price
          image_url: https://images.example.com/lettuce.png
          text_fields:
            - line: 1
              text: "Fresh Lettuce"
            - line: 2
              text: "$2.99"
          update_strategy: pull    # pull | push | poll

        - id: esl_002
          name: Tomato Price
          image_url: https://images.example.com/tomato.png
          text_fields:
            - line: 1
              text: "Organic Tomato"
            - line: 2
              text: "$3.49"

    - id: electronics
      name: Electronics Shelf
      max_tag_count: 20
      tags:
        - id: esl_100
          name: Headphone Stock
          text_fields:
            - line: 1
              text: "Wireless Headphones"
            - line: 2
              text: "In Stock: 15 units"  # Can be dynamic via API

  # Campaign scheduling
  campaigns:
    - id: daily_price_update
      schedule: "0 9 * * *"       # Every 9 AM (CRON)
      target_groups:
        - grocery_section
      action: broadcast_all_tags
      retry_attempts: 3
      retry_backoff_sec: 5

    - id: stock_monitor
      schedule: "*/5 * * * *"     # Every 5 minutes
      target_groups:
        - electronics
      action: fetch_and_broadcast_stock_levels
      data:
        - esl_id: esl_100
          api_endpoint: https://api.example.com/stock/headphones
          json_path: "$.units_in_stock"

  # Logging and diagnostics
  logging:
    level: debug
    output: /var/log/isolator/pawr.log
    packet_capture:
      enabled: true
      output_dir: /var/log/isolator/pawr/captures

  # Statistics collection
  statistics:
    enabled: true
    export_interval_sec: 60
    metrics:
      - broadcast_count
      - response_count
      - tag_update_latency_ms
      - packet_loss_percent

# Entities exposed to Home Assistant (Pi declares availability)
exposed_entities:
  advertiser_active:
    type: binary_sensor
    friendly_name: PAwR Advertiser
    icon: mdi:broadcast
    update_interval_sec: 30

  tag_count:
    type: sensor
    friendly_name: ESL Tags Active
    icon: mdi:tag-multiple
    unit_of_measurement: tags
    update_interval_sec: 60

  broadcast_success_rate:
    type: sensor
    friendly_name: Broadcast Success Rate
    device_class: null
    unit_of_measurement: "%"
    icon: mdi:percent
    update_interval_sec: 60

  campaigns:
    # One sensor per campaign
    # Template: pawr_campaign:{campaign_id}:{metric}
    type: enum_sensor
    friendly_name_template: "Campaign {campaign_id}"
    values: [ idle, running, succeeded, failed, paused ]
    icon: mdi:calendar-plot
    metrics:
      - status
      - last_run_time
      - next_run_time

```

**ESPHome-inspired features:**
- Nested `advertising`, `esl_groups`, `campaigns` sections
- CRON-style scheduling
- Flexible action definitions
- Referenced group and tag IDs
- Statistics as a first-class section

---

## Merging Multi-Capability Node Config

When a Pi runs all three capabilities, the Home Assistant integration auto-generates a unified node config:

```yaml
# Example: full Pi node config (HA-generated)
node:
  id: pi_kitchen
  hostname: pi.local
  ssh_host: 192.168.1.50

capabilities:
  - network_isolator:
      config: {...}  # From network_isolation.yaml
  - ble_gatt_translator:
      config: {...}  # From ble_translator.yaml
  - pawr_esl_advertiser:
      config: {...}  # From pawr_esl.yaml (only if supported hardware)

# Health and scheduling enforced at node level
node_health:
  desired_state: operational
  rollback_policy:
    max_consecutive_failures: 2
```

---

## Validation and Type Hints

Each capability schema is validated on deploy via JSON Schema validators:

```python
# Python side: pydantic model example
from pydantic import BaseModel
from typing import List, Optional

class WiFiConfig(BaseModel):
    ssid: str
    password: str
    band: str = "2.4GHz"
    channel: int = 6

class DevicePolicy(BaseModel):
    id: str
    mac: str
    name: Optional[str] = None
    internet: str = "log-only"   # Enum: log-only, allow, deny
    logging: str = "full"
    capture: Optional[dict] = None

class NetworkIsolatorConfig(BaseModel):
    wifi: WiFiConfig
    interfaces: dict
    devices: List[DevicePolicy]
    default_policy: dict
```

---

## Configuration Storage and Updates

- Home Assistant stores node list and SSH creds in `/config/custom_components/isolator/config.yaml`
- Each Pi's capability config stored locally at `/opt/isolator/config/capabilities/{capability_id}.yaml`
- Pi supervisor watches for config changes and triggers reconcile
- Entity exposure config is managed in Tornado/Bokeh dashboard UI or Pi-side YAML
- All config changes are audited with correlation IDs

## HA Integration Query Flow

```
1. HA fetches node list from config
2. For each node:
   - SSH to Pi, query /api/v1/node/info
   - Query /api/v1/entities to learn available entity schema
   - Subscribe to /api/v1/events/entities for updates (or long-poll)
3. HA renders entities as binary_sensor, sensor, enum_sensor, etc.
4. User can enable/disable entity exposure in Pi dashboard or HA YAML
5. HA automation can reference Pi entity state in conditions/triggers
6. Optional: HA calls /api/v1/capabilities/{id}/action to trigger Pi workflow
```

## Example: BLE Scale Battery in HA Automation

Pi exposes entity: `ble_device:kitchen_scale:battery_percent`

In HA YAML:
```yaml
automations:
  - id: notify_low_scale_battery
    trigger:
      platform: numeric_state
      entity_id: isolator.pi_kitchen.ble_device_kitchen_scale_battery_percent
      below: 20
    condition:
      - condition: state
        entity_id: light.kitchen
        state: "on"
    action:
      - service: persistent_notification.create
        data:
          title: "Kitchen Scale Low Battery"
          message: "Battery {{ state_attr(...) }}%"
```
