# Home Assistant Integration Deep Dive

Detailed guide for HA discovery, entity translation, automation examples, and fleet management.

## Two-Device Architecture

This integration operates across **two separate devices**:

1. **Home Assistant Server**: Runs the custom integration (custom_components/perimeter_control/)
2. **Raspberry Pi Target Device(s)**: Remote Pi(s) where services are deployed (e.g., `192.168.50.47`)

Communication flow:
- HA → Pi: SSH deployment of supervisor and services
- HA ← Pi: HTTP API calls for entity states and actions  
- HA ← Pi: WebSocket events for real-time updates

## Integration Architecture

```
Home Assistant Server                          Raspberry Pi Target (192.168.50.47)         
├── Isolator Integration (custom component)    ├── Supervisor API (port 8080)
│   ├── Config Flow (Pi IP & SSH setup)       │   ├── Entity Discovery Endpoints
│   ├── SSH Deployer (push code to Pi)        │   ├── State Query Handlers  
│   ├── HTTP API Client (query Pi states)     │   ├── Action Trigger Handlers
│   ├── Entity Platform Handlers              │   └── WebSocket Event Stream
│   │   ├── sensor (BLE values, network stats)├── Dashboard Web (port 3000)
│   │   ├── binary_sensor (connectivity, health)├── Service Runtime
│   │   ├── switch (enable/disable capability) │   ├── BLE Repeater
│   │   └── device_tracker (network devices)   │   ├── ESL Access Point
│   ├── Service Handlers (trigger actions)     │   ├── Photo Booth
│   └── Webhook Listener (Pi → HA push)        │   └── Wildlife Monitor
└── SSH Connection (deploy & manage)           └── Systemd Services
```

## Generic Fleet UI Model

The HA UI should be generic and reusable across all services.

### Level 1: Fleet View
- Add one or more Pis.
- Show hardware/features per Pi (BLE, camera, GPIO lighting, NICs).
- Show assigned services and current health.

### Level 2: Node Detail
- Assign or remove services from that Pi.
- View compatibility warnings (resource conflicts).
- Open each service editor card.

### Level 3: Service Editor (Reusable Card)
Each service card has the same sections:
1. Runtime status (active/degraded/stopped).
2. Service config file editor (service-specific content).
3. Shared access profile editor (generic controls):
  - mode: localhost | upstream | isolated | all | explicit
  - bind address / port
  - TLS mode and certificates
  - auth mode
  - exposure scope (lan/vpn/tunnel)
4. Actions: validate, apply, restart, rollback.

This model supports running network isolator + photo booth on one Pi or across different Pis with identical UX patterns.

## Config Flow (First-Time Setup)

User adds new integration:

```python
# custom_components/isolator/config_flow.py

class IsolatorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_NETWORK
    
    async def async_step_user(self, user_input=None):
        """Initiate by user entering Pi IP."""
        
        if user_input is not None:
            # 1. Validate Pi is reachable
            try:
                pi_info = await validate_pi_connection(user_input["host"])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            
            if not errors:
                # 2. Generate registration code on Pi
                registration_code = await generate_registration_code(
                    user_input["host"]
                )
                
                # 3. Return code to user (one-time)
                return self.async_show_form(
                    step_id="pairing",
                    description_placeholders={
                        "registration_code": registration_code
                    }
                )
        
        # Show form asking for Pi IP
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,  # "192.168.1.50"
                vol.Optional("port", default=8080): int,
            }),
            errors=errors
        )
    
    async def async_step_pairing(self, user_input=None):
        """User confirms pairing on Pi."""
        
        # User navigates to http://192.168.1.50:8080/pairing
        # Sees code on Pi, clicks "Pair"
        # HA polls http://192.168.1.50:8080/pairing/status
        # until status == "approved"
        
        pairing_status = await check_pairing_status(self.pi_host)
        
        if pairing_status["status"] == "approved":
            # 4. Exchange token
            token = pairing_status["token"]
            
            # 5. Create config entry
            return self.async_create_entry(
                title=f"Isolator Pi ({self.pi_host})",
                data={
                    "host": self.pi_host,
                    "token": token,  # Encrypted in secrets.yaml
                    "verify_ssl": False,  # Local network
                }
            )
        
        # Still waiting
        return self.async_abort(reason="pairing_timeout")
```

### Multi-Pi Onboarding Extension

The flow repeats per node. Each successful pairing creates a separate node record under one integration instance.

```python
# conceptual state shape in HA
fleet = {
  "nodes": {
    "pi_perimeter": {"host": "192.168.69.11", "labels": ["role=perimeter"]},
    "pi_media": {"host": "192.168.69.12", "labels": ["role=media", "feature=camera"]},
  }
}
```

## Entity Platform Handlers

Dynamically create HA entities from Pi entities.

### Entity Discovery

```python
# custom_components/isolator/sensor.py

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities from Pi."""
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    @callback
    def handle_coordinator_update():
        """Called when Pi data updates."""
        
        # Get all Pi entities
        pi_entities = coordinator.data["entities"]
        
        for pi_entity in pi_entities:
            # Create HA entity for each Pi entity of type "sensor"
            if pi_entity["platform"] == "sensor":
                entity = IsolatorSensor(
                    coordinator,
                    entry,
                    pi_entity["id"],
                    pi_entity["name"],
                    pi_entity.get("device_class"),
                    pi_entity.get("unit_of_measurement")
                )
                entities.append(entity)
        
        async_add_entities(entities)
    
    # Subscribe to Pi data updates
    coordinator.async_add_listener(handle_coordinator_update)
    handle_coordinator_update()
```

### Sensor Entity

```python
class IsolatorSensor(SensorEntity, CoordinatorEntity):
    """Represent a Pi entity as HA sensor."""
    
    def __init__(self, coordinator, entry, entity_id, name, device_class, unit):
        super().__init__(coordinator)
        self._entity_id = entity_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_unit_of_measurement = unit
        self._attr_unique_id = f"isolator_{entry.entry_id}_{entity_id}"
    
    @property
    def native_value(self):
        """Return current state from coordinator."""
        state = self.coordinator.data["entity_states"].get(self._entity_id)
        return state["state"] if state else None
    
    @property
    def last_updated(self):
        """Return last update time."""
        state = self.coordinator.data["entity_states"].get(self._entity_id)
        return state["last_updated"] if state else None
    
    @property
    def device_info(self):
        """Return device info for grouping in HA."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.pi_id)},
            "name": f"Isolator Pi ({self.coordinator.pi_host})",
            "model": self.coordinator.pi_hardware["model"],
            "sw_version": self.coordinator.pi_version,
            "hw_version": self.coordinator.pi_hardware["version"],
        }
```

## Coordinator Pattern

Data fetching and caching:

```python
# custom_components/isolator/coordinator.py

class IsolatorDataUpdateCoordinator(DataUpdateCoordinator):
    """Manage Pi data fetching and real-time updates."""
    
    def __init__(self, hass, client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),  # Poll every 30s
        )
        self.client = client
    
    async def _async_update_data(self):
        """Fetch data from Pi."""
        
        try:
            # 1. Get node info
            node_info = await self.client.get_node_info()
            
            # 2. Get all entities
            entities_response = await self.client.get_entities()
            
            # 3. Get entity states (bulk query)
            entity_ids = [e["id"] for e in entities_response["entities"]]
            state_response = await self.client.query_entity_states(entity_ids)
            
            return {
                "node_info": node_info,
                "entities": entities_response["entities"],
                "entity_states": {
                    e["entity_id"]: e["state"]
                    for e in state_response["states"]
                }
            }
        
        except Exception as err:
            raise UpdateFailed(f"Error fetching Pi data: {err}")
    
    async def async_subscribe_to_events(self):
        """Subscribe to real-time entity updates via WebSocket."""
        
        async for event in self.client.subscribe_events():
            if event["type"] == "entity_updated":
                # Update coordinator data immediately (don't wait for poll)
                entity_id = event["entity_id"]
                self.data["entity_states"][entity_id] = event["state"]
                
                # Notify listeners
                self.async_set_updated_data(self.data)
```

### REST Client

```python
# custom_components/isolator/client.py

class IsolatorPiClient:
    """HTTP client for Pi REST API."""
    
    def __init__(self, host, token, session):
        self.base_url = f"http://{host}:8080/api/v1"
        self.token = token
        self.session = session
    
    async def get_node_info(self):
        """Get Pi hardware and capability info."""
        
        async with self.session.get(
            f"{self.base_url}/node/info",
            headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def get_entities(self):
        """Get list of all entities."""
        
        async with self.session.get(
            f"{self.base_url}/entities",
            headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def query_entity_states(self, entity_ids: List[str]):
        """Bulk query entity states."""
        
        async with self.session.post(
            f"{self.base_url}/entities/states/query",
            json={"entity_ids": entity_ids},
            headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def trigger_action(self, capability_id: str, action_id: str, params=None):
        """Trigger a capability action."""
        
        async with self.session.post(
            f"{self.base_url}/capabilities/{capability_id}/actions/{action_id}",
            json=params or {},
            headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def subscribe_events(self):
        """Subscribe to real-time events via WebSocket."""
        
        async with self.session.ws_connect(
            f"ws://{self.host}:8080/api/v1/events",
            headers=self._headers()
        ) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    yield json.loads(msg.data)
    
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
```

## Service Handlers

Trigger Pi actions from HA automations:

```python
# custom_components/isolator/services.py

async def async_setup_services(hass, domain, entry):
    """Set up service handlers."""

    async def handle_reload_rules(call):
        """Service: reload network isolation rules."""

        coordinator = hass.data[DOMAIN][entry.entry_id]
        result = await coordinator.client.trigger_action(
            "network_isolation",
            "reload_rules"
        )

        if result["success"]:
            _LOGGER.info("Network isolation rules reloaded")
        else:
            _LOGGER.error(f"Reload failed: {result.get('error')}")

    async def handle_trigger_ble_scan(call):
        """Service: start BLE scan."""

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.client.trigger_action(
            "ble_gatt_translator",
            "start_scan"
        )

    hass.services.async_register(
        DOMAIN,
        "reload_rules",
        handle_reload_rules
    )

    hass.services.async_register(
        DOMAIN,
        "trigger_ble_scan",
        handle_trigger_ble_scan
    )
```

### New Generic Service APIs Used By HA UI

The integration should call generic endpoints for every service type.

```http
GET    /api/v1/services
GET    /api/v1/services/{service_id}
GET    /api/v1/services/{service_id}/config
PUT    /api/v1/services/{service_id}/config
GET    /api/v1/services/{service_id}/access
PUT    /api/v1/services/{service_id}/access
POST   /api/v1/services/{service_id}/validate
POST   /api/v1/services/{service_id}/apply
POST   /api/v1/services/{service_id}/rollback
```

Example access payload (shared across all services):

```json
{
  "mode": "upstream",
  "bind_address": "",
  "port": 5006,
  "tls_mode": "self_signed",
  "cert_file": "/etc/isolator/tls/fullchain.pem",
  "key_file": "/etc/isolator/tls/privkey.pem",
  "auth_mode": "token",
  "allowed_origins": ["https://ha.local:8123"],
  "exposure_scope": "lan_only"
}
```

Example service config file payload:

```json
{
  "config_file": "/mnt/isolator/conf/photo-booth.yaml",
  "format": "yaml",
  "content": "camera:\n  source: picam0\nlighting:\n  backend: ha\n"
}
```

Register services in HA:

```yaml
# service call in automation
action:
  service: isolator.reload_rules
  data:
    capability: network_isolation
```

## Automation Examples

### Example 1: Alert When Device Offline

```yaml
automation:
  - alias: "Alert if lwip device offline"
    trigger:
      platform: state
      entity_id: binary_sensor.isolator_device_lwip_connected
      to: "off"
      for:
        minutes: 5
    action:
      - service: notify.slack
        data:
          message: "lwip device offline for 5+ minutes"
      - service: isolator.reload_rules
        data:
          comment: "Auto-reload after device offline"
```

### Example 2: Dynamic Rate Limiting Based on Time

```yaml
automation:
  - alias: "Reduce connectivity during business hours"
    trigger:
      - platform: time
        at: "08:00:00"
      - platform: time
        at: "17:00:00"
    action:
      - service: isolator.set_device_policy
        data:
          device_id: iphone
          policy_id: work_hours_restricted
          rate_limit_mbps: 50  # Slower during work hours

  - alias: "Restore normal connectivity"
    trigger:
      platform: time
      at: "18:00:00"
    action:
      - service: isolator.set_device_policy
        data:
          device_id: iphone
          policy_id: evening_unrestricted
          rate_limit_mbps: null
```

### Example 3: Monitor and Alert on Network Anomaly

```yaml
automation:
  - alias: "Alert on unusual device traffic"
    trigger:
      platform: numeric_state
      entity_id: sensor.isolator_device_traffic_packets_per_minute
      above: 10000  # Abnormally high
      for:
        minutes: 2
    action:
      - service: notify.mobile_app_iphone
        data:
          message: "{{ trigger.entity_id }} has unusual traffic"
          data:
            tag: network_alert
            category: network
            actions:
              - action: BLOCK_DEVICE
                title: "Block device"
              - action: SNIFF_TRAFFIC
                title: "Capture packets"

  - alias: "Block device (from notification)"
    trigger:
      platform: event
      event_type: mobile_app_notification_action
      event_data:
        action: BLOCK_DEVICE
    action:
      - service: isolator.set_device_policy
        data:
          device_id: "{{ trigger.event.data.device_id }}"
          action: block
```

### Example 4: BLE Device Discovery & Integration

```yaml
automation:
  - alias: "Welcome new BLE device"
    trigger:
      platform: state
      entity_id: sensor.isolator_ble_devices_discovered
      # New device appears in entity list
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.new_device != null }}"
    action:
      - service: notify.persistent_notification
        data:
          title: "New BLE device discovered"
          message: |
            Device: {{ trigger.event.data.name }}
            MAC: {{ trigger.event.data.mac }}
            RSSI: {{ trigger.event.data.rssi }}
          data:
            tag: ble_discovery
            actions:
              - action: PAIR_DEVICE
                title: "Remember device"
              - action: BLOCK_DEVICE
                title: "Block device"
```

## Fleet Management Dashboard

Tornado dashboard view for multi-Pi oversight:

```python
# Custom card in HA dashboard:
# "isolator-fleet-card"

# Shows all connected Pi instances:
Isolator Fleet
├── Pi Kitchen (192.168.1.50)
│   ├── Health: ✓ OK
│   ├── CPU: 35% | RAM: 512MB | Disk: 80GB free
│   ├── Capabilities: network_isolation, ble_gatt_translator
│   ├── Entities: 24 total (20 OK, 4 warning)
│   ├── Last update: 2 minutes ago
│   └── Actions: [Restart] [View Logs] [Snapshot]
│
├── Pi Garage (192.168.1.51)
│   ├── Health: ⚠ DEGRADED (BLE offline)
│   ├── CPU: 15% | RAM: 256MB | Disk: 40GB free
│   ├── Capabilities: network_isolation (OK), ble_gatt_translator (OFFLINE)
│   ├── Entities: 18 total (16 OK, 2 offline)
│   ├── Last update: 45 seconds ago
│   └── Actions: [Fix] [View Details]
```

## Entity State Translation

Map Pi entity states to HA types:

```python
ENTITY_TYPE_MAPPING = {
    # Binary sensors
    "binary_sensor": {
        "device_class": ["battery", "cold", "connectivity", "door", "garage_door", "gas", "moisture", "motion", "occupancy", "opening", "plug", "power", "presence", "problem", "running", "safety", "tamper", "vibration", "window"],
        "entity_category": ["diagnostic"],
    },
    
    # Sensors
    "sensor": {
        "device_class": ["aqi", "battery", "carbon_dioxide", "carbon_monoxide", "distance", "energy", "frequency", "gas", "humidity", "illuminance", "irradiance", "moisture", "monetary", "nitrogen_dioxide", "nitrogen_monoxide", "nitrous_oxide", "ozone", "pm1", "pm10", "pm25", "power", "power_factor", "pressure", "reactive_power", "signal_strength", "sound_pressure", "speed", "sulphur_dioxide", "temperature", "volatile_organic_compounds", "voltage", "volume"],
        "state_class": ["measurement", "total", "total_increasing"],
    },
    
    # Devices
    "device_tracker": {
        "source_type": ["arp", "bluetooth", "bluetooth_le", "dhcp", "gps", "gpslogger", "icecast", "mqtt", "nmap", "snmp", "snmp_apcups", "snmp_printer", "ubus", "udp_sender", "unifi"],
    },
}
```

Example entity conversion:

```python
# Pi entity:
{
    "id": "ble_device:kitchen_scale:weight",
    "name": "Kitchen Scale Weight",
    "platform": "sensor",
    "device_class": "weight",
    "unit_of_measurement": "kg",
    "state_class": "measurement",
    "state": 5.23
}

# Becomes HA entity:
sensor.isolator_kitchen_scale_weight
  - State: 5.23 kg
  - Attributes:
      device_class: weight
      unit_of_measurement: kg
      state_class: measurement
      friendly_name: Kitchen Scale Weight
```

## Troubleshooting Guide

### Integration Won't Connect

```bash
# 1. Verify Pi is reachable
ping 192.168.1.50

# 2. Check REST API is running
curl http://192.168.1.50:8080/api/v1/node/info

# 3. Verify token is valid
curl -H "Authorization: Bearer <token>" http://192.168.1.50:8080/api/v1/entities

# 4. Check HA logs for integration errors
# HA → Developer Tools → Logs (filter "isolator")

# 5. Re-pair: remove integration, restart HA, re-add
```

### Entities Not Updating

```bash
# 1. Verify WebSocket connection
# HA logs should show "Subscribing to Pi events"

# 2. Check Pi logs
ssh pi@192.168.1.50
journalctl -u isolator-supervisor -f

# 3. Test manual entity state query
curl http://192.168.1.50:8080/api/v1/entities/ble_device:kitchen_scale:weight

# 4. Check coordinator polling interval
# (default 30s; can be tuned in integration config)
```

### High Pi Load from HA Queries

```yaml
# Tune coordinator poll interval
coordinator:
  poll_interval: 60  # seconds (default: 30)
  
# Disable less-critical entities
disabled_entities:
  - sensor.isolator_raw_metrics_*  # High-volume internal metrics
```
