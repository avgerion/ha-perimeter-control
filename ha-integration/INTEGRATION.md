# Perimeter Control Integration — Technical Overview

This document details the **native Home Assistant integration** architecture for managing PerimeterControl Pi edge nodes.

## Architecture

### Integration Components

The Perimeter Control integration consists of several key components:

```
Home Assistant Core
├── Perimeter Control Integration (custom_components/perimeter_control/)
│   ├── Config Flow (device setup & SSH management)  
│   ├── Coordinator (API communication & data refresh)
│   ├── Services (6 HA services for Pi management)
│   ├── Frontend Panel (integrated UI in HA sidebar)
│   └── Entities (device discovery & state tracking)
└── Target Pi Devices
    └── PerimeterControl Supervisor (API server on port 8080)
```

### Data Flow

```
┌─────────────────────────────────────────┐
│  Home Assistant Server                  │
├─────────────────────────────────────────┤
│                                         │
│  Perimeter Control Integration          │
│  ┌─────────────────────────────────┐   │
│  │ Config Flow    │ Coordinator    │   │ 
│  │ (Setup/SSH)    │ (API Client)   │   │
│  │                │                │   │
│  │ Frontend Panel │ Services       │   │
│  │ (UI)           │ (deploy, etc.) │   │
│  └─────────────────────────────────┘   │
│                    ↓                    │
│  SSH Deploy + HTTP API Calls            │
│  POST /api/v1/deploy                    │
│  GET /api/v1/services                   │
│  POST /capabilities/{id}/actions        │
│                    ↓                    │
│  JSON Request/Response                  │
│                                         │
│  Target Pi Device (192.168.50.47)      │
│  ├── PerimeterControl Supervisor (port 8080)   │
│  ├── Service Runtime (capabilities)    │
│  └── SSH Server (deployment target)    │
│                                         │
└─────────────────────────────────────────┘
```

## Integration Features

### 1. Native HA Integration

- **Domain**: `perimeter_control`
- **Configuration Flow**: Guided setup via HA UI
- **Device Management**: Appears in Settings → Devices & Services
- **Service Discovery**: Automatic entity creation based on Pi capabilities  
- **State Management**: Persistent device connection and status tracking

### 2. Service Registration

The integration registers 6 native Home Assistant services:

```python
# Available in Developer Tools → Services
perimeter_control.deploy              # Deploy supervisor to Pi
perimeter_control.start_capability    # Start a Pi service  
perimeter_control.stop_capability     # Stop a Pi service
perimeter_control.trigger_capability  # Trigger capability actions
perimeter_control.reload_config       # Reload Pi configuration
perimeter_control.get_device_info     # Get Pi hardware details
```

### 3. Frontend Panel

- **Automatic Registration**: Panel appears in HA sidebar after setup
- **Static Asset Serving**: Integration serves its own CSS/JS resources
- **No Manual Setup**: No configuration.yaml or www/ directory management
- **Responsive Design**: Mobile-friendly interface

### 4. SSH Management

- **Secure Key Storage**: SSH keys stored encrypted in HA config
- **Multi-line Support**: Full PEM/OpenSSH key format support
- **Connection Testing**: Automatic SSH connectivity validation
- **Error Handling**: Detailed SSH error reporting and troubleshooting

## Configuration Examples

### Adding a Pi Device

Via Home Assistant UI (Settings → Devices & Services → Add Integration):

```yaml
# Integration will prompt for:
host: "192.168.50.47"           # Pi IP or hostname
port: 22                        # SSH port
username: "paul"                # SSH username  
ssh_key: !secret perimeter_key  # SSH private key
supervisor_port: 8080           # Supervisor API port
```

### Service Automation Examples

```yaml
# Automation: Deploy on HA start
automation:
  - trigger:
      platform: homeassistant
      event: start
    action:
      service: perimeter_control.deploy
      data:
        force: true

# Script: Emergency stop all services
script:
  emergency_stop:
    sequence:
      - service: perimeter_control.stop_capability
        data:
          capability: photo_booth
      - service: perimeter_control.stop_capability  
        data:
          capability: ble_scanner

# Scene: Configuration for different modes
scene:
  - name: "Party Mode"
    entities:
      script.deploy_party_config: "on"
    action:
      service: perimeter_control.trigger_capability
      data:
        capability: photo_booth
        action: party_mode
        config: '{"duration": 7200}'
```

## API Integration

### Supervisor REST API

The integration communicates with the Isolator Supervisor API on each Pi:

```bash
# Service Discovery
GET /api/v1/services
{
  "services": [
    {"id": "photo_booth", "name": "Photo Booth", "status": "running"},
    {"id": "ble_scanner", "name": "BLE Scanner", "status": "stopped"},
    ...
  ]
}

# Device Capabilities  
GET /api/v1/node/features
{
  "gpio": {"available": true, "chips": [...]},
  "i2c": {"available": true, "buses": [...]},
  "audio": {"available": true, "cards": [...]},
  ...
}

# Capability Actions
POST /api/v1/capabilities/{id}/actions/{action}
{
  "action": "start_scan",
  "config": {"duration": 30}
}
```

### Entity Creation

The integration automatically creates Home Assistant entities for:

- **Device**: Each Pi becomes an HA device with model/SW info
- **Sensors**: Service status, device capabilities, connection state
- **Buttons**: Quick actions for deploy/start/stop operations
- **Binary Sensors**: Online/offline status, service health checks

## Development

### Frontend Build Process

The integration includes a modern frontend build system:

```bash
cd ha-integration/
npm install                    # Install dependencies
npm run build                  # Build frontend resources 
npm run dev                    # Development server

# Output: dist/ha-integration.js → integration/frontend/
```

### File Structure

```
NetworkIsolator/                    # Integration root
├── manifest.json                   # Integration manifest  
├── __init__.py                     # Integration setup
├── config_flow.py                  # Device setup flow
├── coordinator.py                  # API communication
├── frontend_panel.py               # Panel registration
├── services.yaml                   # Service definitions
├── const.py                        # Constants
└── ha-integration/                 # Frontend build
    ├── package.json                # NPM dependencies
    ├── src/                        # TypeScript source
    └── dist/                       # Built assets
```

### Installation for Development

```bash
# Development install 
cd NetworkIsolator/
ln -s $(pwd) ~/.homeassistant/custom_components/perimeter_control

# Or manual copy for testing
cp -r . ~/.homeassistant/custom_components/perimeter_control/

# Restart HA and add integration via UI
```

## Troubleshooting

### Common Issues

**Integration not found:**
- Verify files in `custom_components/perimeter_control/`
- Check HA logs: `grep perimeter_control home-assistant.log`
- Restart Home Assistant after file changes

**SSH connection fails:**
- Test manually: `ssh user@192.168.50.47`
- Verify SSH key format (PEM/OpenSSH with BEGIN/END lines)
- Check firewall/network connectivity

**API communication errors:**
- Verify supervisor running: `systemctl status isolator-supervisor`
- Test API: `curl http://192.168.50.47:8080/api/v1/services`
- Check supervisor logs for errors

**Frontend panel missing:**
- Clear browser cache and reload
- Check browser console for JS errors
- Verify frontend assets built correctly

### Debug Logging

Enable detailed logging in HA `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.perimeter_control: debug
    custom_components.perimeter_control.coordinator: debug
```

## Security Considerations

- **SSH Keys**: Stored encrypted in HA database
- **API Communication**: HTTP-only, intended for local network  
- **Network Isolation**: Pi devices should be on isolated VLAN
- **Access Control**: Integration requires HA admin privileges
- **Audit Trail**: All deploy actions logged with timestamps

## Performance

- **Polling Frequency**: 30-second default update interval
- **Resource Usage**: Minimal; single coordinator per device
- **Concurrent Operations**: SSH/API calls are async and non-blocking
- **Caching**: Device info and service lists cached between polls
- **Error Handling**: Exponential backoff for failed API calls