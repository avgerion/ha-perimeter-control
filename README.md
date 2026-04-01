# Pi Network Isolator

A Raspberry Pi with per-device, policy-driven network isolation that can run in either direction: WiFi AP isolated from Ethernet, or isolated Ethernet behind a WiFi uplink. It is also a growing platform for multi-mode BLE/WiFi analysis with a supervisory control plane.

## What It Does

- Resolves interfaces by role (`topology.isolated` and `topology.upstream`) instead of assuming fixed `wlan0`/`eth0` wiring.
- Supports a secure WiFi AP isolated from Ethernet, or an isolated Ethernet segment behind a WiFi uplink.
- Applies per-device firewall rules (internet access, LAN reach, logging) driven by a single config file.
- Logs all WiFi client traffic at configurable verbosity.
- **Captures per-device pcap files** for Wireshark analysis — designed for reverse engineering unknown IoT devices (WiFi plugs, cameras, drone controllers, etc.).
- Streams live traffic to Wireshark on Windows via SSH pipe.
- **Real-time web dashboard** (Bokeh-powered) showing device status, bandwidth, connections, and alerts.
- **BLE scanning, sniffing, GATT profiling, and mirror proxy** via integrated BLE scripts.
- **Max sniff mode by default** — unknown devices auto-captured for analysis.
- **Bridge mode** — connect to target device APs (drones, cameras) via second WiFi adapter for deep protocol analysis.
- **Supervisor control plane** — REST API for capability lifecycle management, entity state, health probes, and resource scheduling.

## Hardware Target

- Raspberry Pi 5 (primary) or Pi 3 Model B/B+
- Raspberry Pi OS Lite 64-bit
- USB drive at `/mnt/isolator` (config + logs)

## Stack

| Component | Role |
|---|---|
| `hostapd` | WiFi AP for isolated side when `topology.isolated.kind=wifi-ap` |
| `dnsmasq` | DHCP + DNS for the isolated side |
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
sudo bash server/setup-isolator.sh --config config/isolator.conf.yaml
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
