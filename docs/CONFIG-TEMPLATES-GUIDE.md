# Configuration & Templates: Practical Guide

Quick reference for working with PerimeterControl config files and understanding the difference between production configs and templates.

---

## Quick Answers

### Q: Why do I see both `config/perimeterControl.conf.yaml` AND `config/templates/gpio_control.yaml`?

**A:** Different purposes:

| File | Purpose | Deployed | Usage |
|------|---------|----------|-------|
| `perimeterControl.conf.yaml` | **Runtime config** for a specific Pi | ✅ YES | Tells supervisor which services to run and how to configure them |
| `config/templates/gpio_control.yaml` | **Reference template** showing schema | ❌ NO | Documentation & validation; shows available options |

**Don't duplicate settings between them.** Put service config in the main file only.

---

### Q: How do I set up multiple GPIO instances (relays + buttons)?

**A:** Add multiple instances in the main config using instance names:

```yaml
# config/perimeterControl.conf.yaml

services:
  gpio_control:
    relays:                          # Instance name: "relays"
      pins:
        - id: relay1
          gpio_pin: 17
          type: switch
          friendly_name: Relay 1
        - id: relay2
          gpio_pin: 27
          type: switch
          
    inputs:                          # Instance name: "inputs"
      pins:
        - id: button1
          gpio_pin: 23
          type: binary_sensor
        - id: button2
          gpio_pin: 24
          type: binary_sensor
```

Generated capability IDs:
- `gpio_control:relays` (for relay entities)
- `gpio_control:inputs` (for button entities)

---

### Q: Can I have multiple Pis with different GPIO configs?

**A:** Yes—each Pi gets its own config file at deploy time. Current implementation supports:

```
Windows/HA Server
├── config/perimeterControl.conf.yaml  (Single file, deploy to one Pi)
└── [Future] config/perimeterControl-pi-perimeter.yaml
    [Future] config/perimeterControl-pi-media.yaml
```

For now: Edit `config/perimeterControl.conf.yaml` before deploying to each Pi. Multi-Pi UI support coming in Phase 3 of roadmap.

---

## Understanding the Architecture

### How Config Flows Through the System

```
1. Windows Developer
   └─ edits config/perimeterControl.conf.yaml
   
2. Home Assistant Integration
   └─ reads config file
   └─ uploads to Pi via SCP
   
3. Raspberry Pi
   └─ Supervisor starts
   └─ reads /mnt/PerimeterControl/conf/perimeterControl.conf.yaml
   └─ calls _deploy_configured_capabilities()
   
4. Supervisor Auto-Deployment
   └─ for each service in config:
      ├─ extracts service type (gpio_control, photo_booth, etc.)
      ├─ loops through all instances
      ├─ calls GpioControlCapability.validate_config()
      └─ starts capability with instance config
      
5. Dashboard
   └─ calls data_manager.get_entities_with_state("gpio_control")
   └─ receives entities from supervisor API
```

### Instance Names & Capability IDs

When supervisor sees:

```yaml
services:
  gpio_control:
    relays:      # ← instance name
      pins: [...]
```

It generates:
- Capability ID: `gpio_control:relays`
- Entity IDs: `gpio_control:switch:relay1`, `gpio_control:switch:relay2`

Multiple instances = multiple capability IDs:

```yaml
gpio_control:
  relays:     → gpio_control:relays
  inputs:     → gpio_control:inputs
  status_led: → gpio_control:status_led
```

---

## Working with Templates

### ✅ DO: Use Templates for Documentation

Template files show the **schema and available options**:

```yaml
# config/templates/gpio_control.yaml (REFERENCE)

gpio_control:
  instance_name:
    pins:
      - id: pin_id                    # Required
        gpio_pin: 17                  # Required, int
        type: switch | light | binary_sensor  # Required
        friendly_name: "Display Name" # Optional
        active_high: true             # Optional, default true
        initial_state: on | off        # Optional, default off
        initial_brightness: 0-255     # Optional for lights only
        icon: mdi:icon-name           # Optional
```

### ❌ DON'T: Duplicate Template Content in Main Config

**Bad:**
```yaml
# config/perimeterControl.conf.yaml
services:
  gpio_control:
    relays:
      pins: [...]
      
# config/templates/gpio_control.yaml
gpio_control:
  relays:
    pins: [...]  # DUPLICATE!
```

**Good:**
```yaml
# config/perimeterControl.conf.yaml (only this has pins)
services:
  gpio_control:
    relays:
      pins: [...]
      
# config/templates/gpio_control.yaml (reference only, no actual pins)
gpio_control:
  instance_name:
    pins: [...]
```

### When to Update Templates

Update `config/templates/service_name.yaml` **only** when:
1. Adding new optional field to schema
2. Changing validation rules
3. Updating documentation

**Don't** update templates when changing your Pi's configuration—update the main config only.

---

## Per-Service Configuration

### GPIO Control

```yaml
services:
  gpio_control:
    relays:                   # Instance for relay control
      pins:
        - id: relay1
          gpio_pin: 17
          type: switch
          friendly_name: Relay 1
          active_high: true
          initial_state: off
```

### Photo Booth

```yaml
services:
  photo_booth:
    booth1:                   # Instance name
      camera_device: /dev/video0
      photo_directory: /opt/PerimeterControl/photos/booth1
      resolution: "1920x1080"
      quality: 85
      motion_detection: false
      timelapse:
        enabled: false
        interval_sec: 60
```

### Network Isolator

```yaml
services:
  network_isolator:
    main:                     # Instance name
      topology:
        upstream:
          interface: eth0
          kind: ethernet
        isolated:
          interface: wlan0
          kind: wifi-ap
      devices:
        - id: trusted-laptop
          mac: aa:bb:cc:dd:ee:ff
          name: Trusted Laptop
          static_ip: 192.168.111.10
          internet: allow
          lan_access:
            - host: 192.168.50.10
              ports: [445, 22, 80]
```

### Wildlife Monitor

```yaml
services:
  wildlife_monitor:
    backyard:                 # Instance name
      model: usb_camera
      camera_device: /dev/video0
      data_dir: /mnt/PerimeterControl/wildlife/backyard
```

### BLE GATT Repeater

```yaml
services:
  ble_gatt_repeater:
    main:                     # Instance name
      # BLE-specific config
```

---

## Validation Flow

### How Configs Get Validated

```
1. deployer.py (Windows)
   └─ loads config/perimeterControl.conf.yaml
   └─ calls PerimeterControlSchema.validate_file()
   └─ checks structure and per-capability validation
   
2. supervisor.py (on Pi)
   └─ in _deploy_configured_capabilities()
   └─ for each service:
      └─ calls GpioControlCapability.validate_config()
      └─ capability checks pins for duplicates, required fields, etc.
```

### Example: GPIO Validation

```python
# supervisor/capabilities/gpio_control/capability.py

@staticmethod
def validate_config(config):
    errors = []
    
    # Extract pins from all instances
    services = config.get("services", {})
    gpio_cfg = services.get("gpio_control", {})
    
    for instance_name, instance_cfg in gpio_cfg.items():
        pins = instance_cfg.get("pins", [])
        
        # Check for required fields
        for pin in pins:
            if "id" not in pin:
                errors.append(f"{instance_name}: pin missing 'id'")
            if "gpio_pin" not in pin:
                errors.append(f"{instance_name}: pin missing 'gpio_pin'")
    
    return errors
```

---

## Common Config Tasks

### Add a Second GPIO Relay

```yaml
services:
  gpio_control:
    relays:
      pins:
        - id: relay1
          gpio_pin: 17
          type: switch
        - id: relay2          # ← Add this
          gpio_pin: 27        # ← New GPIO pin
          type: switch
```

### Add Status LEDs (New Instance)

```yaml
services:
  gpio_control:
    relays:
      pins: [...]            # Existing relays
    
    status_leds:             # ← New instance
      pins:
        - id: online_led
          gpio_pin: 18
          type: light
        - id: alarm_led
          gpio_pin: 23
          type: light
```

### Add Second Photo Booth Camera

```yaml
services:
  photo_booth:
    booth1:
      camera_device: /dev/video0
      photo_directory: /opt/PerimeterControl/photos/front
      
    booth2:                  # ← New instance
      camera_device: /dev/video1
      photo_directory: /opt/PerimeterControl/photos/back
```

---

## Troubleshooting

### Config Not Loading

**Symptom**: Dashboard shows bootstrap GPIO entities but no API entities

**Cause**: Supervisor couldn't auto-deploy from config

**Check**:
1. Is config file valid YAML?
   ```powershell
   # On Pi
   python3 -c "import yaml; yaml.safe_load(open('/mnt/PerimeterControl/conf/perimeterControl.conf.yaml'))"
   ```

2. Check supervisor logs for errors:
   ```bash
   sudo journalctl -u PerimeterControl-supervisor.service -n 50
   ```

### Duplicate ID Error

**Symptom**: Error "duplicate id: relay1"

**Cause**: Same pin ID used twice in same instance

**Fix**: Each pin needs unique `id` within an instance (can repeat across instances):
```yaml
# ❌ Bad
relays:
  pins:
    - id: relay1
      gpio_pin: 17
    - id: relay1        # Duplicate!
      gpio_pin: 27

# ✅ Good
relays:
  pins:
    - id: relay1
      gpio_pin: 17
    - id: relay2        # Unique
      gpio_pin: 27
```

### Pin Conflicts

**Symptom**: "duplicate gpio_pin: 17"

**Cause**: Same GPIO pin used by multiple pins (not allowed)

**Fix**: Use different GPIO pins:
```yaml
# ❌ Bad
relays:
  pins:
    - id: relay1
      gpio_pin: 17
    - id: relay2
      gpio_pin: 17      # Same GPIO pin!

# ✅ Good  
relays:
  pins:
    - id: relay1
      gpio_pin: 17
    - id: relay2
      gpio_pin: 27      # Different GPIO pin
```

---

## Future: Multi-Pi Config Management

Planned enhancement (Phase 2-3):

```yaml
# perimetercontrol.yaml (single file, all nodes)

perimeter_control:
  version: "1.0"
  
  nodes:
    - name: pi-perimeter
      host: 192.168.69.11
      services:
        gpio_control:
          - name: relays
            pins: [...]
            
    - name: pi-media
      host: 192.168.69.12
      services:
        photo_booth:
          - name: booth1
            camera_device: /dev/video0
```

See [YAML-CONFIGURATION-SCHEMA.md](YAML-CONFIGURATION-SCHEMA.md) for design details.
