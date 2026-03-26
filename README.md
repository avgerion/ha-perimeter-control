# Pi Network Isolator

A Raspberry Pi 3 configured as a WiFi access point with per-device, policy-driven network isolation.

## What It Does

- Creates a secure WiFi AP on `wlan0`.
- Routes or isolates traffic to/from the upstream network via `eth0`.
- Applies per-device firewall rules (internet access, LAN reach, logging) driven by a single config file.
- Logs all WiFi client traffic at configurable verbosity.
- **Captures per-device pcap files** for Wireshark analysis — designed for reverse engineering unknown IoT devices (WiFi plugs, cameras, drone controllers, etc.).
- Streams live traffic to Wireshark on Windows via SSH pipe.
- **Real-time web dashboard** (Bokeh-powered) showing device status, bandwidth, connections, and alerts.
- **Max sniff mode by default** — unknown devices auto-captured for analysis.
- **Bridge mode** — connect to target device APs (drones, cameras) via second WiFi adapter for deep protocol analysis.

## Hardware Target

- Raspberry Pi 3 (Model B or B+)
- Raspberry Pi OS Lite 64-bit
- USB drive at `/mnt/isolator` (config + logs — same portability model as the music library Pi)

## Stack

| Component | Role |
|---|---|
| `hostapd` | WiFi AP (wlan0) |
| `dnsmasq` | DHCP + DNS for AP clients |
| `nftables` | Per-device firewall + traffic logging |
| `scripts/apply-rules.py` | Config → nftables ruleset generator |
| `systemd` unit `isolator.service` | Orchestrates startup and live reload |
| **Bokeh Server** | Real-time web dashboard (port 5006) |
| `tcpdump` | Per-device and bridge packet capture |
| `wpa_supplicant` | Bridge mode client (optional second WiFi) |

## Quick Start

### Initial Setup (First Time)

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment guide, or [docs/INITIAL-SETUP.md](docs/INITIAL-SETUP.md) for Pi setup from scratch.

**Quick Deploy from Windows:**
```powershell
# Edit config first
notepad config\isolator.conf.yaml

# Run one-command deployment
.\deploy.ps1
```

**Manual Setup:**
1. Use **Raspberry Pi Imager** with advanced settings (⚙️):
   - ✅ Enable SSH
   - ✅ Set hostname: `isolator`
   - ✅ Set username/password
2. Boot Pi with ethernet connected
3. Copy files and run setup:
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
# From Windows/Linux/Mac:
ssh -L 5006:localhost:5006 pi@isolator.local
```
Then browse to: `http://localhost:5006`

**Direct LAN access:**
Browse to: `http://isolator.local:5006` (less secure)

**Features:**
- Live device status cards with connection indicators
- Real-time bandwidth graphs
- Active connections table
- Event log with firewall alerts
- Quick rule editor (allow/deny/capture toggles)
- SSH command helpers for remote management

See [docs/WEB-DASHBOARD.md](docs/WEB-DASHBOARD.md) for full details.

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
ssh pi@isolator.local "cat /run/isolator/device.pipe" | wireshark -k -i -
```

**Reload rules:**
```bash
ssh pi@isolator.local "sudo systemctl reload isolator"
```

## Config

Edit `config/isolator.conf.yaml` — see inline comments for all options.

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

**Web Dashboard Files:**
- `server/web/dashboard.py` — Main Bokeh server entry point
- `server/web/layouts.py` — UI layout and widget definitions
- `server/web/callbacks.py` — Live data update handlers
- `server/web/data_sources.py` — Data fetching from nftables, dnsmasq, logs
- `server/requirements.txt` — Python dependencies (Bokeh, Pandas, PyYAML)
- `server/isolator-dashboard.service` — systemd service definition

Install dashboard dependencies:
```bash
pip3 install -r server/requirements.txt
```

Start dashboard manually (for development):
```bash
cd server/web
python3 dashboard.py
```

Enable as systemd service (production):
```bash
sudo cp server/isolator-dashboard.service /etc/systemd/system/
sudo systemctl enable isolator-dashboard
sudo systemctl start isolator-dashboard
```

## Phase Path

| Phase | Goal | Status |
|---|---|---|
| 1 | Config schema + device access model | ✅ Complete |
| 2 | Setup script: hostapd + dnsmasq + nftables on Pi OS | ✅ **Complete!** |
| 3 | `apply-rules.py` — config → live nftables rules | ✅ **Complete!** |
| 4 | Web dashboard with Bokeh (live traffic, device mgmt) | ✅ Complete |
| 4b | Bridge mode for target device AP analysis | ✅ Complete |
| 5 | Yocto image for true appliance deploy | 📋 Planned |
