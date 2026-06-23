# PerimeterControl YAML Configuration Schema

Formal specification for the single-file YAML configuration system, modeled after ESPHome's declarative YAML patterns but adapted for PerimeterControl's multi-node, multi-capability architecture.

**Status**: Design document. Proposes standardized schema for multi-Pi fleet management.

---

## Overview

### Design Goals

1. **Single Source of Truth**: One YAML file (`perimetercontrol.yaml`) describes entire system state
2. **ESPHome-like Patterns**: Named lists with IDs for multiple instances of same service type
3. **Multi-Pi Fleet**: Support multiple Raspberry Pi nodes with different configurations
4. **Home Assistant Compatible**: Config mergeable with HA's YAML structure
5. **Schema Validation**: Each capability validates its own config section
6. **Self-Documenting**: Structure is declarative and explicit

### Current State vs Proposed

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Config Files** | Multiple (perimeterControl.conf.yaml + templates/) | Single (perimetercontrol.yaml) |
| **Multi-Instance Support** | Nested dict: `services.gpio_control.relays.pins` | Named list: `gpio_control[0].name: "relays"` |
| **Multi-Pi Support** | Hardcoded single Pi config | `nodes[]` array with per-node services |
| **Validation** | Per-capability static method | Capability validation + schema validation layer |
| **Schema Language** | None (implicit) | YAML schema + Python vol.Schema |
| **Templates** | `config/templates/` duplicates main config | Reference examples only |

---

## Proposed Schema Structure

### Top-Level Layout

```yaml
# perimetercontrol.yaml - Single file for entire fleet

perimeter_control:
  version: "1.0"                          # Schema version
  
  # Fleet-level settings (apply to all nodes unless overridden)
  defaults:
    supervisor_port: 8080
    dashboard_port: 5006
    
  # One or more Raspberry Pi nodes
  nodes:
    - name: pi-perimeter                  # Human-readable node ID
      host: 192.168.69.11                 # Hostname or IP
      ssh_key: ~/.ssh/perimeterNode1      # (HA config entry stores this)
      
      # Services deployed on this node
      services:
        network_isolator:                 # Capability type
          - name: main_network            # Instance name (optional, auto-indexed if omitted)
            topology:
              upstream:
                interface: eth0
                kind: ethernet
              isolated:
                interface: wlan0
                kind: wifi-ap
            devices: [...]
            
        gpio_control:
          - name: relays                  # Instance #1
            pins:
              - id: relay1
                gpio_pin: 17
                type: switch
              - id: relay2
                gpio_pin: 27
                type: switch
                
          - name: inputs                  # Instance #2
            pins:
              - id: button1
                gpio_pin: 23
                type: binary_sensor
              - id: button2
                gpio_pin: 24
                type: binary_sensor
                
        photo_booth:
          - name: booth1
            camera_device: /dev/video0
            photo_directory: /opt/PerimeterControl/photos
            
        wildlife_monitor:
          - name: backyard
            model: usb_camera
            
    - name: pi-media                      # Second node
      host: 192.168.69.12
      services:
        photo_booth:
          - name: front_door
            camera_device: /dev/video0
```

---

## Service Instance Naming

Each service is deployed as a **list of named instances**. Instance names:

- **Recommended**: Semantic names (`relays`, `inputs`, `booth1`, `backyard`)
- **Required**: Unique within that service on that node
- **Used for**: Entity ID prefixes, capability ID generation

### Capability ID Generation

Capability IDs are auto-generated from node + service + instance:

```
perimeter_control:<service>:<node>_<instance>
```

Examples:
- `gpio_control:pi-perimeter_relays`
- `gpio_control:pi-perimeter_inputs`
- `photo_booth:pi-media_front_door`

---

## Schema Validation Flow

### Layer 1: YAML Schema Validation (Future)

Define a JSON Schema or Pydantic model for top-level structure:

```python
# Example: config_schema.py (to be created)

from typing import List, Dict, Any
from pydantic import BaseModel, Field

class NodeConfig(BaseModel):
    name: str = Field(..., description="Unique node name")
    host: str = Field(..., description="Node hostname or IP")
    ssh_key: Optional[str] = None
    services: Dict[str, List[Dict[str, Any]]]

class PerimeterControlConfig(BaseModel):
    version: str = Field(default="1.0")
    defaults: Optional[Dict[str, Any]] = None
    nodes: List[NodeConfig]
```

### Layer 2: Per-Capability Validation

Each capability implements `validate_config(config: Dict[str, Any]) -> List[str]`:

```python
# Example: gpio_control.capability.py

@staticmethod
def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate GPIO capability config.
    
    Expects config shape:
    {
      "type": "gpio_control",
      "services": {
        "gpio_control": {
          "instance_name": {
            "pins": [...]
          }
        }
      }
    }
    """
    errors = []
    # Validation logic...
    return errors
```

### Layer 3: Deployment Validation

Deployer validates entire node before deployment:

```python
async def validate_node(self, node_config: Dict[str, Any]) -> List[str]:
    """Validate all services on a node."""
    all_errors = []
    
    for service_type, instances in node_config.get("services", {}).items():
        module_class = self._modules.get(service_type)
        if not module_class:
            all_errors.append(f"Unknown service type: {service_type}")
            continue
            
        # Build config dict for this capability
        cap_config = {"type": service_type, "services": {service_type: {}}}
        for instance in instances:
            # Instance structure
            instance_name = instance.get("name", str(len(cap_config["services"][service_type])))
            cap_config["services"][service_type][instance_name] = instance
            
        # Call capability's validate_config
        cap_errors = module_class.validate_config(cap_config)
        all_errors.extend([f"{service_type}:{err}" for err in cap_errors])
    
    return all_errors
```

---

## Multi-Instance Examples

### GPIO with Multiple Instance Groups

```yaml
gpio_control:
  - name: relays              # Relay control group
    pins:
      - id: relay1
        gpio_pin: 17
        type: switch
      - id: relay2
        gpio_pin: 27
        type: switch
        
  - name: status_leds         # Status LED group
    pins:
      - id: online_led
        gpio_pin: 18
        type: light
        initial_brightness: 255
      - id: alarm_led
        gpio_pin: 23
        type: light
        
  - name: inputs              # Button/sensor inputs
    pins:
      - id: reset_button
        gpio_pin: 24
        type: binary_sensor
```

### Photo Booth with Multiple Cameras

```yaml
photo_booth:
  - name: front_door
    camera_device: /dev/video0
    photo_directory: /opt/PerimeterControl/photos/front
    
  - name: back_patio
    camera_device: /dev/video1
    photo_directory: /opt/PerimeterControl/photos/back
```

### Network Isolator on Multiple Pis

```yaml
# pi-perimeter node
network_isolator:
  - name: eth0_wlan0
    topology:
      upstream:
        interface: eth0
        kind: ethernet
      isolated:
        interface: wlan0
        kind: wifi-ap
    devices: [...]

# pi-media node (in separate node config)
network_isolator:
  - name: eth0_wlan1
    topology:
      upstream:
        interface: eth0
        kind: ethernet
      isolated:
        interface: wlan1
        kind: wifi-ap
    devices: [...]
```

---

## Home Assistant Integration with Multi-Pi

### config_flow.py Pattern

User adds integration once per **node**:

```python
async def async_step_user(self, user_input=None):
    """Step 1: Enter node details."""
    
    if user_input:
        # User enters: host, SSH key path
        # HA validates SSH connection
        # Then stores in config entry data with encrypted token
        
        return self.async_create_entry(
            title=f"PerimeterControl ({user_input['host']})",
            data={
                "host": "192.168.69.11",
                "supervisor_port": 8080,
                "token": "encrypted_token_here",
            }
        )
```

Each config entry maps to **one node** in `perimetercontrol.yaml`.

### Multi-Entry Discovery

HA's frontend shows multiple config entries as a "fleet":

```
Home Assistant
├── Perimeter Control Integration
│   ├── 192.168.69.11 (pi-perimeter)
│   │   ├── Network Isolator (main_network)
│   │   ├── GPIO Control (relays, inputs)
│   │   └── Wildlife Monitor
│   │
│   ├── 192.168.69.12 (pi-media)
│   │   ├── Photo Booth (front_door, back_patio)
│   │   └── BLE GATT Repeater
│   │
│   └── 192.168.69.13 (pi-iot)
│       ├── ESL Access Point
│       └── GPIO Control (devices)
```

---

## Template Files Purpose (Clarified)

**Templates in `config/templates/` are NOT deployed directly.**  
They serve as **reference and documentation only**.

### When to Update Templates

Update `config/templates/service_name.yaml` when:
- Adding new service capability
- Changing validation rules
- Need to document all possible fields

Example template structure:

```yaml
# config/templates/gpio_control.yaml (REFERENCE ONLY)
# This shows the schema and available options, not deployed config

gpio_control:
  - name: example_instance
    # Required fields
    pins:
      - id: example_pin
        gpio_pin: 17
        type: switch | light | binary_sensor
        friendly_name: "Pin Description"
        
    # Optional fields
    active_high: true | false
    initial_state: on | off
    initial_brightness: 0-255  # For lights only
    icon: mdi:icon-name
```

---

## Migration Path

### Phase 1: Documentation & Schema (Current)

- ✅ Formalize YAML schema (this document)
- 🔄 Create validation layer (pydantic models)
- 🔄 Update deployer to understand new schema

### Phase 2: Refactor Deployer

- Accept `--node-name pi-perimeter` parameter
- Load `perimetercontrol.yaml`
- Extract `nodes[name == pi-perimeter]` config
- Deploy services from that node only

### Phase 3: HA Integration Update

- Modify config_flow to guide multi-node setup
- Create UI for managing fleet (add/remove nodes)
- Sync `perimetercontrol.yaml` to Pi on deployment

### Phase 4: Cleanup

- Remove `config/templates/` from deployment
- Keep as reference documentation only
- Update README to point to schema doc

---

## Current Implementation Notes

### How Supervisor Reads Config

Today supervisor reads `perimeterControl.conf.yaml` from Pi:

```python
# supervisor/data_manager.py
config = yaml.safe_load(open("/mnt/PerimeterControl/conf/perimeterControl.conf.yaml"))
services = config.get("services", {})

# Extracts services section and passes to capabilities
for cap_type, instances in services.items():
    for instance_name, instance_config in instances.items():
        # instance_config has the service-specific settings
```

### How Capabilities Validate

Each capability's `validate_config()` expects:

```python
config = {
    "type": "gpio_control",
    "services": {
        "gpio_control": {
            "relays": {"pins": [...]},
            "inputs": {"pins": [...]}
        }
    }
}
```

The `services.gpio_control` dict contains **all instances** of that capability on that node.

---

## Schema Validation Examples

### ✅ Valid Config

```yaml
perimeter_control:
  version: "1.0"
  nodes:
    - name: pi-perimeter
      host: 192.168.69.11
      services:
        gpio_control:
          - name: relays
            pins:
              - id: relay1
                gpio_pin: 17
                type: switch
```

### ❌ Invalid: Duplicate pin IDs

```yaml
gpio_control:
  - name: relays
    pins:
      - id: relay1       # Duplicate!
        gpio_pin: 17
      - id: relay1       # Error: duplicate id
        gpio_pin: 18
```

### ❌ Invalid: Missing required field

```yaml
gpio_control:
  - name: relays
    pins:
      - gpio_pin: 17     # Error: missing 'id'
        type: switch
```

---

## Backward Compatibility

Current nested format **already works**:

```yaml
# Old: nested dict (still valid)
services:
  gpio_control:
    relays:
      pins: [...]

# New: list of objects (proposed)
gpio_control:
  - name: relays
    pins: [...]
```

Both structures produce the same capability config internally, so validation logic doesn't change immediately. Deployer can support both formats during migration.

---

## Next Steps

1. **Schema Definition**: Create `config_schema.py` with Pydantic models
2. **Validation Layer**: Implement formal schema validation
3. **Deployer Updates**: Modify to support node selection
4. **Documentation**: Add YAML examples for each service
5. **HA Integration**: Enhance UI for multi-node management
