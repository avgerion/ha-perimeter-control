# Workspace vs Remote Path Mappings

This document clarifies the relationship between local workspace paths (Windows/Linux dev) and remote paths on the Raspberry Pi deployment target.

## Overview

- **Workspace**: Local development machine (Windows with WSL or native Linux)
- **Remote Pi**: Target Raspberry Pi running PerimeterControl services
- **Path Configuration**: All remote paths are explicitly defined in config files (YAML) passed to services

## Path Mappings

### Dashboard Web Files

#### Workspace Paths
```
NetworkIsolator/
├── remote_services/
│   └── dashboard_web/
│       ├── dashboard_common.py          (shared utilities)
│       ├── gpio_control_dashboard.py    (GPIO service entry point)
│       ├── gpio_control_layouts.py      (GPIO UI layout)
│       ├── gpio_control_callbacks.py    (GPIO UI callbacks)
│       ├── network_isolator_dashboard.py
│       ├── photo_booth_dashboard.py
│       ├── esl_dashboard.py
│       ├── wildlife_dashboard.py
│       ├── ble_gatt_repeater_dashboard.py
│       └── static/
│           └── css/
│               └── pc-dashboard.css     (shared CSS styling)
```

#### Remote Pi Paths
```
/opt/PerimeterControl/web/
├── dashboard_common.py
├── gpio_control_dashboard.py
├── gpio_control_layouts.py
├── gpio_control_callbacks.py
├── network_isolator_dashboard.py
├── photo_booth_dashboard.py
├── esl_dashboard.py
├── wildlife_dashboard.py
├── ble_gatt_repeater_dashboard.py
└── static/
    └── css/
        └── pc-dashboard.css            ← Served via HTTP as /css/pc-dashboard.css (custom route)
```

### Configuration Files

#### Workspace Paths
```
NetworkIsolator/
└── config/
    └── templates/
        ├── gpio_control.yaml           (GPIO service config template)
        ├── network_isolator.conf.yaml
        ├── photo_booth_config.yaml
        ├── esl_config.yaml
        ├── wildlife_config.yaml
        └── ble_gatt_repeater.yaml
```

#### Remote Pi Paths
```
/mnt/PerimeterControl/conf/
├── gpio-control.yaml                   ← Deployed config for GPIO service
├── network-isolator.yaml
├── photo-booth.yaml
├── esl-ap.yaml
├── wildlife-monitor.yaml
└── ble-gatt-repeater.yaml
```

### Scripts and Utilities

#### Workspace Paths
```
NetworkIsolator/
└── remote_services/
    └── scripts/
        ├── network_isolator/
        │   ├── apply-rules.py
        │   ├── network-topology.py
        │   └── topology_config.py
        ├── ble_gatt_repeater/
        │   ├── ble-gatt-mirror.py
        │   ├── ble-proxy-profiler.py
        │   ├── ble-scanner.py
        │   └── ble-scanner-v2.py
        └── ...
```

#### Remote Pi Paths
```
/opt/PerimeterControl/scripts/
├── network_isolator/
│   ├── apply-rules.py
│   ├── network-topology.py
│   └── topology_config.py
├── ble_gatt_repeater/
│   ├── ble-gatt-mirror.py
│   ├── ble-proxy-profiler.py
│   ├── ble-scanner.py
│   └── ble-scanner-v2.py
└── ...
```

### Supervisor and Services

#### Workspace Paths
```
NetworkIsolator/
├── remote_services/
│   └── supervisor/
│       ├── data_manager.py             (shared supervisor utilities)
│       └── supervisor_manager.py
└── PerimeterControl-*.service.template (systemd service templates)
```

#### Remote Pi Paths
```
/opt/PerimeterControl/supervisor/
├── data_manager.py
└── supervisor_manager.py

/etc/systemd/system/
├── perimetercontrol-gpio-dashboard.service
├── perimetercontrol-network-isolator-dashboard.service
├── perimetercontrol-photo-booth-dashboard.service
└── ...
```

### Logs and State

#### Remote Pi Paths Only (Not in Workspace)
```
/var/log/PerimeterControl/
├── gpio_dashboard.log
├── network_isolator_dashboard.log
├── photo_booth_dashboard.log
├── supervisor.log
└── ...

/mnt/PerimeterControl/state/
├── gpio_state.json
├── entities.json
└── ...
```

## CSS File Serving

The CSS file is served via HTTP from Tornado:

- **Workspace source**: `remote_services/dashboard_web/static/css/pc-dashboard.css`
- **Deployed location**: `/opt/PerimeterControl/web/static/css/pc-dashboard.css`
- **HTTP URL**: `http://<pi-ip>:8095/css/pc-dashboard.css` (GPIO dashboard) - Note: `/css/` is a custom route, not Bokeh's `/static/`
- **URL pattern**: `/css/pc-dashboard.css` (custom handler, not Bokeh's /static/)

When you see this in the server log, CSS is being served correctly:
```
GET /css/pc-dashboard.css HTTP/1.1 200 OK
```

## Configuration File Format

GPIO configuration uses a nested service-based architecture in the remote config file:

**File**: `/mnt/PerimeterControl/conf/gpio-control.yaml`

```yaml
services:
  gpio_control:
    relays:
      pins:
        - id: relay1
          gpio_pin: 17
          type: switch
          friendly_name: Relay 1
          active_high: true
          initial_state: off

    lights:
      pins:
        - id: led1
          gpio_pin: 18
          type: light
          friendly_name: Status LED
          active_high: true
          initial_state: on
          initial_brightness: 255

dashboard:
  server:
    host: "0.0.0.0"
    port: 8095
    type: "bokeh"
  features:
    pin_status: true
    relay_control: true
    led_control: true
  data_refresh_interval: 10
```

**Format notes**:
- Multiple GPIO instances (e.g., `relays`, `lights`, `inputs`) can coexist under `services.gpio_control`
- Each instance has its own `pins` list
- Supports future multi-Pi deployments with per-Pi config files
- Dashboard configuration is at the root level (shared across all instances)

## Deployment Flow

1. **Local workspace**: Developer edits Python, YAML, CSS files
2. **SSH upload**: Files copied from workspace to `/tmp/` on Pi
3. **Installation**: Files moved from `/tmp/` to final explicit locations:
   - `.py` files → `/opt/PerimeterControl/web/` or `/opt/PerimeterControl/scripts/`
   - `.yaml` files → `/mnt/PerimeterControl/conf/`
   - CSS files → `/opt/PerimeterControl/web/static/css/`
4. **Service restart**: Systemd services reloaded and restarted
5. **Verification**: Check logs and HTTP requests

## Path Resolution

All remote paths are **hardcoded explicit values**, not derived from environment variables:

- Install root: `/opt/PerimeterControl` (hardcoded)
- State/Config root: `/mnt/PerimeterControl` (hardcoded)
- Logs root: `/var/log/PerimeterControl` (hardcoded)
- Temp directory: `/tmp` (hardcoded)
- Systemd services: `/etc/systemd/system` (hardcoded)

## Debugging

### Check if CSS is deployed correctly
```bash
ssh pi@<pi-ip> "ls -la /opt/PerimeterControl/web/static/css/"
```

### View GPIO dashboard logs with path context
```bash
ssh pi@<pi-ip> "tail -f /var/log/PerimeterControl/gpio_dashboard.log"
```

### Check if GPIO config is deployed
```bash
ssh pi@<pi-ip> "cat /mnt/PerimeterControl/conf/gpio-control.yaml"
```

### Verify Tornado static file handler is configured
```bash
ssh pi@<pi-ip> "journalctl -u perimetercontrol-gpio-dashboard -n 50 --no-pager"
```

Look for lines like:
```
[STATIC] Serving /static from: /opt/PerimeterControl/web/static
[GPIO_DASH] CSS will be loaded from /css/pc-dashboard.css via HTTP
```
