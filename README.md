# Perimeter Control for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/avgerion/ha-perimeter-control.svg?style=for-the-badge)](https://github.com/avgerion/ha-perimeter-control/releases)

Advanced Raspberry Pi network gateway management with **dynamic entity discovery**, **real-time monitoring**, and **optimized performance**.

## 🏗️ Architecture Overview

This integration uses a **two-device architecture**:

- 🏠 **Home Assistant Server**: Runs the custom integration that provides the UI, entity management, and deployment orchestration
- 🥧 **Raspberry Pi Target Device**: Remote Pi where supervisor API and services are deployed (e.g., `192.168.50.47`)

The Home Assistant integration uses SSH to deploy services to the Pi, then communicates with the supervisor API running on the Pi for real-time monitoring and control.

## ✨ Features

### 🔄 **Dynamic Entity Discovery**
- **Auto-Detection**: Network devices, services, and capabilities discovered automatically
- **Real-time States**: Live connectivity status, network policies, and service health
- **Smart Organization**: Entities grouped by device type and capability
- **Hot Reloading**: New devices appear instantly without HA restart

### 🚀 **Performance Optimized** 
- **70% Fewer API Calls**: Batch endpoints reduce network overhead
- **WebSocket Events**: Real-time updates without polling
- **Smart Caching**: Only changed data transmitted
- **Efficient Sync**: Single call fetches entities + states + configuration

### 🛠 **Service Management**
- **Dashboard Access**: Pre-computed URLs for all Pi services
- **Configuration Monitoring**: Automatic change detection and versioning
- **Health Tracking**: Real-time service status and capability monitoring
- **Multi-Service Support**: BLE repeater, ESL AP, photo booth, wildlife monitor

### 🔧 **Developer Tools**
- **SSH Deployment**: Push code updates directly from HA
- **Automatic Rollback**: Safe deployments with failure recovery
- **Fleet Management**: Control multiple Pi gateways from one HA instance
- **Diagnostic Tools**: Built-in connectivity and service testing

## � Repository Structure

```
ha-perimeter-control/
├── 📦 *.py, manifest.json                  # Main HA Integration (root level)
│   ├── deployer.py                        # GUI deployment from HA
│   ├── coordinator.py                     # Optimized API client
│   ├── dynamic_entity.py                  # Auto-discovery system
│   └── ... (integration files)
├── 📁 ha-integration/                      # Deployment & Automation
│   ├── scripts/deploy.py                  # CLI deployment script
│   ├── example-ha-configuration.yaml      # Shell command setup
│   └── ... (automation examples)
├── 📁 supervisor/                          # Pi backend service
│   ├── api/handlers.py                    # HA-optimized endpoints
│   └── ... (supervisor implementation)
├── 📁 config/services/                     # Service descriptors
├── 📄 hacs.json                           # HACS metadata
└── 📄 README.md                           # This file
```

## 🚀 **Dual Deployment System**

This integration provides **two deployment methods** for setting up fresh Pi nodes:

### Method 1: GUI Deployment (Recommended for Users)
Deploy directly from Home Assistant interface:
1. **Add Integration** via Settings > Devices & Services
2. **Enter Pi Target Details** (IP address like `192.168.50.47`, SSH key, username)  
3. **Select Services** to install (photo booth, BLE repeater, etc.)
4. **Deploy** - Home Assistant pushes code to Pi via SSH and starts services automatically

### Method 2: Command Line Deployment (Power Users)  
Deploy via HA shell commands or automation:
```yaml
shell_command:
  deploy_pi: >
    python3 /config/ha-integration/scripts/deploy.py
    --host 192.168.50.47 --user pi --ssh-key /config/ssh_key
```

> **Note**: The `--host` parameter specifies the **target Pi device** IP address, not the Home Assistant server IP.

### Fresh Pi Bootstrap Capability
Both methods can set up a **fresh Pi target device with just Pi OS + SSH**:
- ✅ Home Assistant SSH deploys to Pi target (e.g., `192.168.50.47`)
- ✅ Install system dependencies (GStreamer, I2C tools, etc.) on Pi
- ✅ Set up supervisor service and API on port 8080 on Pi
- ✅ Deploy service configurations and descriptors to Pi
- ✅ Start all systemd services automatically on Pi
- ✅ Handle rollback on deployment failures

## 📦 Installation

### Via HACS (Recommended)

1. **Open HACS** in Home Assistant
2. **Go to Integrations**
3. **Click the 3 dots** in top right corner
4. **Add Custom Repository**
5. **Repository URL**: `https://github.com/avgerion/ha-perimeter-control.git`
6. **Category**: Integration
7. **Click Add**
8. **Search** for "Perimeter Control"
9. **Install** the integration
10. **Restart** Home Assistant

### Manual Installation

1. **Download** the latest release
2. **Extract** integration files (`*.py`, `manifest.json`) to your HA config directory under `custom_components/perimeter_control/`
3. **Restart** Home Assistant
4. **Add Integration** via Settings > Devices & Services

## ⚙️ Configuration

### 1. Add Integration

1. **Settings** > **Devices & Services**
2. **Add Integration**
3. **Search** for "Perimeter Control"
4. **Enter** your Pi details:
   - **Host**: Pi IP address (e.g., `192.168.1.100`)
   - **Port**: SSH port (default: `22`)
   - **Username**: SSH username (e.g., `pi`)
   - **SSH Key**: Private key content or path

### 2. Pi Setup Requirements

Your Raspberry Pi needs:
- **SSH Access**: Key-based authentication enabled
- **Supervisor Service**: Running on port 8080
- **Network Access**: HA can reach the Pi on SSH and HTTP ports

### 3. Automatic Discovery

Once configured, the integration will:
- ✅ **Discover** all network devices and services
- ✅ **Create** entities for connectivity, policies, and service states  
- ✅ **Monitor** configuration changes automatically
- ✅ **Provide** real-time updates via WebSocket events

## 🎯 Entity Types

### Network Devices
- **Binary Sensors**: Device connectivity status
- **Sensors**: Current network policy (default, isolate, etc.)
- **Buttons**: Quick policy changes

### Services  
- **Binary Sensors**: Service health (active/inactive)
- **Sensors**: Configuration status and versions
- **Buttons**: Service control (start, stop, restart)

### System Status
- **Sensors**: Pi system health, CPU, memory
- **Binary Sensors**: SSH connectivity, API availability

## � Documentation

### Core Architecture
- [**Port Architecture**](docs/PORT-ARCHITECTURE.md) - Complete port assignment, configuration, and troubleshooting guide
- [**Network Architecture**](docs/NETWORK-ARCHITECTURE.md) - Network topology and isolation design
- [**Component Services**](SERVICE-DEPLOYMENT-ARCHITECTURE.md) - Service composition and deployment architecture

### Setup & Deployment  
- [**Initial Setup**](docs/INITIAL-SETUP.md) - Pi setup from scratch
- [**Deployment Guide**](DEPLOYMENT.md) - Complete deployment procedures
- [**SSH Quick Reference**](docs/SSH-QUICK-REFERENCE.md) - SSH commands and troubleshooting

### Advanced Features
- [**Web Dashboard**](docs/WEB-DASHBOARD.md) - Dashboard features and access methods
- [**BLE Scanning**](docs/BLE-SNIFFING.md) - Bluetooth monitoring capabilities
- [**HA Integration Deep Dive**](docs/HA-INTEGRATION-DEEP-DIVE.md) - Advanced Home Assistant integration

### Development
- [**Capability Development**](docs/CAPABILITY-DEVELOPMENT-GUIDE.md) - Building new service capabilities
- [**Testing & CI/CD**](docs/TESTING-CI-CD.md) - Development workflow and testing

## �🔧 Advanced Configuration

### Custom Service Descriptors

Add service descriptors to `/mnt/isolator/conf/services/*.yaml`:

```yaml
id: my_service
name: My Custom Service  
version: "1.0.0"
ports:
  - 8095
access:
  mode: localhost
  port: 8095
capabilities:
  - custom_capability
system_deps:
  - custom-package
```

### Network Policies

Configure device policies via the Pi's network isolator:
- **default**: Full network access
- **isolate**: Internet blocked, local network allowed  
- **strict**: Complete network isolation
- **custom**: User-defined iptables rules

### WebSocket Events

Real-time events for:
- Device connectivity changes
- Policy modifications  
- Service status updates
- Configuration changes

## 🐛 Troubleshooting

### Common Issues

#### Integration Not Discovering Entities
- ✅ Check Pi supervisor is running on port 8080
- ✅ Verify SSH connectivity from HA to Pi  
- ✅ Ensure firewall allows HTTP access to port 8080

#### SSH Connection Failed
- ✅ Verify SSH key has correct permissions (600)
- ✅ Check username and key match Pi configuration
- ✅ Test SSH manually: `ssh -i keyfile user@pi-ip`

#### API Timeout Errors
- ✅ Check Pi supervisor logs: `sudo journalctl -u isolator-supervisor -f`
- ✅ Verify Pi has sufficient resources (CPU, memory)
- ✅ Test API manually: `curl http://pi-ip:8080/api/v1/health`

### Debug Logging

Enable detailed logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.perimeter_control: debug
```

### Manual Testing

Test the integration components:

```bash
# Test supervisor API
curl http://pi-ip:8080/api/v1/ha/integration

# Test SSH connectivity  
ssh -i keyfile user@pi-ip 'echo Connection OK'

# Check supervisor status
ssh -i keyfile user@pi-ip 'sudo systemctl status isolator-supervisor'
```

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Build** if needed:
   ```bash
   # For HA integration TypeScript changes
   cd ha-integration
   npm install
   npm run build
   ```
5. **Test** thoroughly
6. **Submit** a pull request

## 🔧 Development Tasks

**VS Code Tasks (Ctrl+Shift+P → "Tasks: Run Task"):**
- **Build HA Integration** - Compile TypeScript to JavaScript
- **Watch HA Integration** - Auto-rebuild on file changes  
- **Deploy Dashboard** - Deploy to Pi device
- **Open SSH Tunnel** - Create secure connection to Pi

**Manual Build Commands:**
```bash
cd ha-integration
npm run build      # One-time build
npm run watch      # Watch mode for development
npm run dev        # Development server
```

## 📄 **Frontend Panel System**

The integration provides a comprehensive web-based management interface through multiple components:

### **Core Components**

**🎛️ Main Panel (`panel.ts`)**: 
- **Location**: Appears in HA sidebar as "Perimeter Control"
- **Purpose**: Central management interface for all Pi devices and services
- **Features**: Device overview, service status, dashboard URLs, global actions
- **Entity Discovery**: Auto-detects entities from supervisor API and displays them in organized cards
- **Dashboard Access**: One-click access to web dashboards for each service

**⚙️ Panel Registration (`frontend_panel.py`)**:
- **TypeScript Compilation**: Builds frontend from `ha-integration/src/` to `frontend/ha-integration.js`
- **Static File Serving**: Registers `/perimeter_control_static` endpoint for assets
- **Panel Injection**: Adds custom web component to HA sidebar
- **Error Handling**: Graceful fallback when frontend files missing

**🔧 Build System (`ha-integration/`)**: 
- **Source**: TypeScript files in `src/` directory with modern Lit framework
- **Build**: Rollup configuration compiles to single JavaScript bundle
- **Components**: Error boundaries, safe loaders, service editors, fleet views
- **Auto-Copy**: Build process copies output to `frontend/` for HA consumption

### **Dashboard URL Entities**

The integration creates **clickable entities** for each service dashboard:

```yaml
# Example entities created automatically:
sensor.perimeter_control_photo_booth_dashboard:
  friendly_name: "Photo Booth Dashboard"
  state: "http://192.168.50.47:3000"
  attributes:
    service_id: photo_booth
    port: 3000
    status: active
    
sensor.perimeter_control_supervisor_dashboard:
  friendly_name: "Supervisor API"
  state: "http://192.168.50.47:8080"
  attributes:
    service_id: supervisor
    port: 8080
    status: active
```

**Usage in HA**: Click entity in Entities card or use in automations:
```yaml
# Automation example: Open dashboard on button press
action:
  - service: browser_mod.navigate
    data:
      path: "{{ states('sensor.perimeter_control_photo_booth_dashboard') }}"
```

### **Development Workflow**

**Frontend Development**:
```bash
# Auto-rebuild during development
cd ha-integration
npm run watch

# One-time build for deployment  
npm run build
```

**Panel Debugging**:
1. Check browser console for TypeScript errors
2. Verify `frontend/ha-integration.js` exists and is recent
3. Check HA logs for panel registration errors
4. Use VS Code task "Build HA Integration" for quick rebuilds

**Entity Debugging**:
1. Verify supervisor API returns dashboard URLs: `curl http://pi-ip:8080/api/v1/ha/dashboard-urls`
2. Check coordinator logs for entity creation
3. Restart integration if entities don't appear
4. Use Developer Tools > States to verify entity creation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
| `nftables` | Per-device firewall + traffic logging |
| `scripts/apply-rules.py` | Config → nftables ruleset generator |
| `systemd` unit `isolator.service` | Orchestrates startup and live reload |
| **Bokeh/Tornado** | Real-time web dashboard (port 5006) |
| `tcpdump` | Per-device and bridge packet capture |
| `wpa_supplicant` | Bridge mode client (optional second WiFi) |
| `BlueZ` / `bleak` | BLE scanning, GATT profiling, sniffer, mirror proxy |
| **Supervisor** | Capability lifecycle API (port 8080) |

## Quick Start

### Deploy from Windows

See [DEPLOYMENT.md](DEPLOYMENT.md) for the complete guide.

```powershell
# Edit config first
notepad config\isolator.conf.yaml

# Deploy dashboard + supervisor (default)
.\scripts\deploy-dashboard-web.ps1

# Dashboard only (skip supervisor)
.\scripts\deploy-dashboard-web.ps1 -SkipSupervisor

# Deploy without restarting services
.\scripts\deploy-dashboard-web.ps1 -NoRestart

# Also sync local config\isolator.conf.yaml to /mnt/isolator/conf/isolator.conf.yaml
.\scripts\deploy-dashboard-web.ps1 -SyncConfig
```

The deploy script:
1. **Phase 1** — uploads `server/web/*.py` and BLE scripts, backs up existing files, installs, restarts `isolator-dashboard`
2. **Optional config sync** (`-SyncConfig`) — backs up `/mnt/isolator/conf/isolator.conf.yaml`, installs local `config/isolator.conf.yaml` to runtime path, reloads `isolator` (unless `-NoRestart`)
3. **Phase 2** — packs `supervisor/` as a tarball, uploads, installs to `/opt/isolator/supervisor/`, installs/enables `isolator-supervisor.service`, installs pip deps, restarts supervisor

### Initial Setup (First Time)

See [docs/INITIAL-SETUP.md](docs/INITIAL-SETUP.md) for Pi setup from scratch.

```bash
# On Windows: copy project to Pi
scp -r . pi@isolator.local:/tmp/isolator-deploy/

# SSH in and install
ssh pi@isolator.local
cd /tmp/isolator-deploy
sudo bash system_services/setup-isolator.sh --config config/isolator.conf.yaml
```

## Web Dashboard Access

The **Network Isolator Quick View** provides real-time monitoring via web browser.

**Access via SSH tunnel (recommended):**
```powershell
ssh -L 5006:localhost:5006 paul@192.168.69.11
```
Then browse to: `http://localhost:5006`

**Direct LAN access:**
Browse to: `http://isolator.local:5006`

**Features:**
- Live device status cards with connection indicators
- Real-time bandwidth graphs
- Active connections table
- Event log with firewall alerts
- Quick rule editor (allow/deny/capture toggles)
- BLE scan / GATT capture viewer
- SSH command helpers for remote management

See [docs/WEB-DASHBOARD.md](docs/WEB-DASHBOARD.md) for full details.

## Supervisor API

The supervisor runs on port 8080 and exposes a REST + WebSocket control plane.

**Access via SSH tunnel:**
```powershell
ssh -L 8080:localhost:8080 paul@192.168.69.11
```

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/node/info` | Node identity, platform, capabilities |
| `GET` | `/api/v1/entities` | All entity states across capabilities |
| `GET` | `/api/v1/capabilities` | Capability status summary |
| `POST` | `/api/v1/capabilities/{id}/deploy` | Deploy / reconfigure a capability |
| `POST` | `/api/v1/capabilities/{id}/actions/{action}` | Execute a capability action |
| `GET` | `/api/v1/health` | Health probe results |
| `GET` | `/api/v1/metrics` | CPU / memory / disk / capability counts |
| `WS` | `/api/v1/events` | Real-time event stream |

**Smoke test:**
```powershell
python scripts/smoke-supervisor-api.py --base-url http://127.0.0.1:8080
```

See [docs/PI-SUPERVISOR-API.md](docs/PI-SUPERVISOR-API.md) for the full API contract.

## Generic Service Descriptors

The platform now includes a generic per-service descriptor contract for multi-service, multi-Pi orchestration.

**Descriptor schema:**
- `supervisor/resources/schemas/service-descriptor.schema.yaml`

**Initial descriptors:**
- `config/services/network_isolator.service.yaml`
- `config/services/ble_gatt_repeater.service.yaml`
- `config/services/esl_ap.service.yaml`
- `config/services/photo_booth.service.yaml`
- `config/services/wildlife_monitor.service.yaml`

**Validate descriptors locally:**
```powershell
python scripts/validate-service-descriptors.py
```

## SSH Remote Management

**Connect to Pi:**
```bash
ssh pi@isolator.local
```

**Live log monitoring:**
```bash
ssh pi@isolator.local "tail -f /var/log/isolator/traffic.log"
```

**Download captures:**
```bash
scp -r pi@isolator.local:/mnt/isolator/captures/ ./local-captures/
```

**Stream live to Wireshark (Windows):**
```powershell
ssh -i .\y paul@192.168.69.11 "cat /run/isolator/device.pipe" | wireshark -k -i -
```

**Reload rules:**
```bash
ssh -i ./y paul@192.168.69.11 "sudo systemctl reload isolator"
```

## Config

Edit `config/isolator.conf.yaml` — see inline comments for all options.

The config supports explicit interface roles:

```yaml
topology:
	upstream:
		interface: eth0
		kind: ethernet
	isolated:
		interface: wlan0
		kind: wifi-ap
```

Dashboard listener exposure is configurable too:

```yaml
dashboard:
	port: 5006
	exposure:
		mode: localhost   # localhost | upstream | isolated | all | explicit
		bind_address: "" # used only when mode=explicit
```

To expose the dashboard on the upstream IP (instead of SSH-only), set:

```yaml
dashboard:
	exposure:
		mode: upstream
```

Reverse mode is also supported:

```yaml
topology:
	upstream:
		interface: wlan0
		kind: wifi-client
	isolated:
		interface: eth0
		kind: ethernet
```

**Key Features:**
- **Max sniff mode by default:** Unknown devices are auto-captured with full logging for immediate analysis
- **Bridge mode:** Connect to target device APs (drones, cameras) using a second WiFi adapter
- **Per-device rules:** Internet allow/deny/log-only, LAN access restrictions, capture settings
- **Live streaming:** Stream packets directly to Wireshark on your Windows/Mac machine via SSH

Live reload without dropping connections:

```bash
sudo systemctl reload isolator
```

## Docs

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Complete deployment guide with step-by-step instructions, troubleshooting, and service management.
- [docs/INITIAL-SETUP.md](docs/INITIAL-SETUP.md) — **START HERE:** complete setup from Raspberry Pi Imager to first SSH connection.
- [docs/DEVICE-ACCESS-MODEL.md](docs/DEVICE-ACCESS-MODEL.md) — how access rules work, rule semantics, nftables flow.
- [docs/REVERSE-ENGINEERING.md](docs/REVERSE-ENGINEERING.md) — capturing and analysing unknown IoT device traffic with tcpdump, tshark, and Wireshark.
- [docs/WEB-DASHBOARD.md](docs/WEB-DASHBOARD.md) — real-time web interface with Bokeh: setup, features, SSH access.
- [docs/BRIDGE-MODE.md](docs/BRIDGE-MODE.md) — connect to target device APs using a second WiFi adapter for deep analysis.
- [docs/SSH-QUICK-REFERENCE.md](docs/SSH-QUICK-REFERENCE.md) — all SSH commands for remote management, log access, and capture retrieval.

## Implementation

**Web Dashboard (`server/web/`):**
- `dashboard.py` — Tornado/Bokeh server entry point
- `layouts.py` — UI layout and widget definitions
- `callbacks.py` — Live data update handlers
- `data_sources.py` — Data fetching from nftables, dnsmasq, logs

**Supervisor (`supervisor/`):**
- `supervisor.py` — Core state machine: deploy pipeline, reconciliation loop, rollback
- `main.py` — Entry point (`python3 -m supervisor`)
- `api/handlers.py` — Tornado REST + WebSocket handlers
- `state/database.py` — SQLite state store (deployments, capabilities, health, entity history)
- `state/entity_cache.py` — Atomic JSON entity cache
- `state/models.py` — Typed dataclasses and enums
- `health/probes.py` — Async health probe evaluator (process / exec / HTTP)
- `resources/scheduler.py` — Resource admission control (CPU / RAM / disk / exclusive)
- `capabilities/base.py` — Abstract `CapabilityModule` interface
- `capabilities/network_isolation/` — NetworkIsolation capability (wraps `isolator.service`)

**Systemd services (`server/`):**
- `isolator-dashboard.service` — Bokeh dashboard (port 5006)
- `isolator-supervisor.service` — Supervisor API (port 8080)
- `isolator.service` — nftables + hostapd orchestrator
- `isolator-traffic.service` — Traffic logger

**Dependencies (`server/requirements.txt`):**
```bash
pip3 install -r server/requirements.txt
```

## Docs

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Complete deployment guide with step-by-step instructions, troubleshooting, and service management.
- [docs/INITIAL-SETUP.md](docs/INITIAL-SETUP.md) — **START HERE:** complete setup from Raspberry Pi Imager to first SSH connection.
- [docs/DEVICE-ACCESS-MODEL.md](docs/DEVICE-ACCESS-MODEL.md) — how access rules work, rule semantics, nftables flow.
- [docs/REVERSE-ENGINEERING.md](docs/REVERSE-ENGINEERING.md) — capturing and analysing unknown IoT device traffic.
- [docs/WEB-DASHBOARD.md](docs/WEB-DASHBOARD.md) — real-time web interface: setup, features, SSH access.
- [docs/BRIDGE-MODE.md](docs/BRIDGE-MODE.md) — connect to target device APs using a second WiFi adapter.
- [docs/BLE-SNIFFING.md](docs/BLE-SNIFFING.md) — BLE scanning, GATT profiling, sniffer, mirror proxy.
- [docs/SSH-QUICK-REFERENCE.md](docs/SSH-QUICK-REFERENCE.md) — SSH commands for remote management, log access, capture retrieval.
- [docs/PLATFORM-ROADMAP.md](docs/PLATFORM-ROADMAP.md) — long-term multi-mode platform vision and capability schema.
- [docs/PI-SUPERVISOR-API.md](docs/PI-SUPERVISOR-API.md) — supervisor REST + WebSocket API contract.
- [docs/SUPERVISOR-ARCHITECTURE.md](docs/SUPERVISOR-ARCHITECTURE.md) — supervisor internals: state machine, reconciliation, resource scheduling.
- [docs/HA-INTEGRATION-DEEP-DIVE.md](docs/HA-INTEGRATION-DEEP-DIVE.md) — Home Assistant integration design.

## Phase Path

| Phase | Goal | Status |
|---|---|---|
| 1 | Config schema + device access model | ✅ Complete |
| 2 | Setup script: hostapd + dnsmasq + nftables on Pi OS | ✅ Complete |
| 3 | `apply-rules.py` — config → live nftables rules | ✅ Complete |
| 4 | Web dashboard with Bokeh (live traffic, device mgmt) | ✅ Complete |
| 4b | Bridge mode for target device AP analysis | ✅ Complete |
| 4c | BLE scanning, GATT profiling, sniffer, mirror proxy | ✅ Complete |
| 5 | Supervisor control plane (REST API, state, reconciliation) | ✅ Complete (MVP) |
| 6 | Multi-capability scheduling (BLE scan + WiFi isolation concurrent) | 📋 Planned |
| 7 | Home Assistant integration (optional aggregation layer) | 📋 Planned |
| 8 | Yocto image for true appliance deploy | 📋 Planned |

## Home Assistant Integration: Manual Dependency Installation

If you use the custom Home Assistant integration in `custom_components/perimeter_control`, you may need to manually install the `asyncssh` Python package in your Home Assistant environment. 

- Home Assistant is supposed to install requirements from `manifest.json` automatically, but this may fail if there are early import or syntax errors, or due to platform limitations.
- If you see errors like `connected but preflight checks failed`, `Preflight script did not complete. stdout=''`, or the integration icon does not appear, it likely means `asyncssh` was not installed.
- To fix, install `asyncssh` manually in your Home Assistant environment (e.g., using the SSH add-on or a terminal):

```
pip install asyncssh==2.14.2
```

- After installing, restart Home Assistant.
- If you continue to have issues, check the Home Assistant logs for import errors and ensure your integration code is error-free.

> **Note:** This is a known limitation. A smarter model or future Home Assistant update may resolve this in the future.
