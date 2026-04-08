# Phase 2 & 3 Implementation Summary

This document summarizes the implementation of Phase 2 (Setup Script) and Phase 3 (Rules Generator) for the PerimeterControl project.

## 📦 Files Created

### Core Implementation

#### 1. **server/setup-perimetercontrol.sh** (Main Installer)
- 🎯 **Purpose:** One-command installation script for Raspberry Pi
- **Features:**
  - Installs all required packages (hostapd, dnsmasq, nftables, tcpdump, Python)
  - Creates directory structure (`/opt/perimetercontrol`, `/var/log/perimetercontrol`, `/mnt/perimetercontrol`)
  - Sets up Python virtual environment for dashboard
  - Enables IP forwarding
  - Disables conflicting services (NetworkManager, default dnsmasq)
  - Generates configuration files from YAML
  - Installs and starts systemd services
  - Provides installation verification and status output
- **Usage:** `sudo bash setup-perimetercontrol.sh --config /mnt/perimetercontrol/conf/perimetercontrol.conf.yaml`

#### 2. **scripts/apply-rules.py** (Configuration Generator)
- 🎯 **Purpose:** Reads `isolator.conf.yaml` and generates all system configuration files
- **Generates:**
  - `hostapd.conf` - WiFi AP configuration (SSID, password, channel, security)
  - `dnsmasq.conf` - DHCP/DNS configuration (IP range, static leases)
  - `isolator.nft` - nftables firewall rules (per-device chains, NAT)
- **Features:**
  - Per-device firewall chains with MAC address matching
  - LAN access rules (specific hosts/ports)
  - Internet access policies (allow/deny/log-only)
  - Default policy for unknown devices (max sniff mode)
  - NAT/masquerading for internet access
  - Automatic rule application with `nft -f`
- **Called by:** `isolator.service` on start and reload

### Systemd Services

#### 3. **server/isolator.service** (Main Service)
- 🎯 **Purpose:** Main orchestration service
- **Actions:**
  - Configures static IP on wlan0 (AP interface)
  - Calls `apply-rules.py` to generate and apply configurations
  - Supports live reload via `systemctl reload isolator`
  - Cleans up on stop (flushes nftables, removes IP from wlan0)

#### 4. **server/isolator-monitor.service** (Device Monitor)
- 🎯 **Purpose:** Monitors for new device connections
- **Actions:**
  - Watches dnsmasq.leases file for changes
  - Identifies devices from config (or marks as unknown)
  - Auto-starts packet captures for devices
  - Logs connection/disconnection events

#### 5. **server/isolator-capture@.service** (Packet Capture Template)
- 🎯 **Purpose:** Per-device packet capture
- **Features:**
  - Template service (instantiated per MAC address)
  - Rolling captures (1-hour files, 24 files max = 24 hours)
  - Automatic directory creation for each device
  - Restart on failure
- **Example:** `isolator-capture@aa-bb-cc-dd-ee-ff.service`

#### 6. **server/isolator-bridge.service** (Bridge Mode)
- 🎯 **Purpose:** Connect to target device APs for deep analysis
- **Features:**
  - Uses wlan1 (USB WiFi adapter) to connect to target AP
  - Runs wpa_supplicant to join target network
  - Captures all traffic on the target network
  - Stores captures in `/mnt/isolator/captures/bridge/`
- **Conflicts with:** `isolator.service` (cannot run simultaneously)

### Support Scripts

#### 7. **scripts/start-capture.py** (Capture Manager)
- 🎯 **Purpose:** Start/stop packet captures for specific devices
- **Features:**
  - Normalizes MAC addresses for systemd service names
  - Starts `isolator-capture@MAC.service` instances
  - Checks if capture already running (no duplicates)
  - Logs capture start/stop events
- **Called by:** `monitor-devices.py` automatically, or manually for testing

#### 8. **scripts/monitor-devices.py** (Device Detection Daemon)
- 🎯 **Purpose:** Main monitoring daemon for device connections
- **Features:**
  - Parses dnsmasq.leases file every 5 seconds (configurable)
  - Maintains active device list
  - Detects new connections and disconnections
  - Triggers capture starts/stops automatically
  - Applies default policy for unknown devices
  - Logs all device events to systemd journal

### Documentation

#### 9. **DEPLOYMENT.md** (Complete Deployment Guide)
- 📚 **Purpose:** Step-by-step deployment instructions
- **Sections:**
  - Quick start guide
  - Prerequisites checklist
  - File preparation and copying
  - Setup script execution
  - Service overview and management
  - Connecting devices
  - Viewing captures
  - Log locations and troubleshooting
  - Bridge mode setup
  - USB drive configuration
  - Performance tuning
  - Backup/restore procedures
  - Security best practices

#### 10. **scripts/README.md** (Scripts Documentation)
- 📚 **Purpose:** Explains all Python scripts and their architecture
- **Covers:**
  - Script purposes and usage
  - Dependencies and installation
  - Development/testing instructions
  - Architecture diagram
  - Logging and error handling

#### 11. **server/README.md** (Server Components Documentation)
- 📚 **Purpose:** Documents systemd services and web dashboard
- **Covers:**
  - Service architecture and dependencies
  - Service management commands
  - Directory structure after installation
  - Dashboard access methods
  - Bridge mode setup
  - Updating and development
  - Security notes

#### 12. **deploy.ps1** (Windows Quick Deploy Script)
- 🎯 **Purpose:** One-command deployment from Windows to Pi
- **Features:**
  - Prerequisites checking (SSH key, config file)
  - SSH connection testing
  - Automatic file archiving and upload
  - Remote setup script execution
  - Service verification
  - Next steps guidance with actual SSID from config
- **Usage:** `.\deploy.ps1` (or with custom parameters)

## 🏗️ Architecture

### Service Dependency Flow

```
System Boot
    │
    ├─► hostapd.service (WiFi AP on wlan0)
    ├─► dnsmasq.service (DHCP/DNS for AP clients)
    │
    └─► isolator.service (Main service)
            │
            ├─► Configures wlan0 IP
            ├─► Runs apply-rules.py
            │       ├─► Generates hostapd.conf
            │       ├─► Generates dnsmasq.conf
            │       └─► Generates isolator.nft
            │
            ├─► isolator-monitor.service
            │       │
            │       └─► Monitors dnsmasq.leases
            │               │
            │               └─► Starts isolator-capture@MAC.service
            │                       │
            │                       └─► tcpdump per device
            │
            └─► isolator-dashboard.service
                    │
                    └─► Bokeh web server (port 5006)
```

### Data Flow

```
Device connects to AP
    │
    ├─► hostapd accepts connection
    │
    ├─► dnsmasq assigns IP via DHCP
    │       │
    │       └─► Writes to /var/lib/misc/dnsmasq.leases
    │
    ├─► monitor-devices.py detects new lease
    │       │
    │       ├─► Identifies device from config (or "unknown")
    │       └─► Calls start-capture.py
    │               │
    │               └─► Starts isolator-capture@MAC.service
    │                       │
    │                       └─► tcpdump writes to /mnt/isolator/captures/MAC/
    │
    ├─► nftables applies per-device rules
    │       │
    │       ├─► Matches by MAC address
    │       ├─► Applies internet access policy
    │       ├─► Applies LAN access rules
    │       └─► Logs traffic (if enabled)
    │
    └─► Dashboard shows live data
            │
            ├─► Reads dnsmasq.leases
            ├─► Reads nftables counters
            ├─► Reads conntrack
            └─► Tails traffic.log
```

## 📂 Directory Structure (After Installation)

```
/opt/isolator/                      # Installation directory
├── venv/                          # Python virtual environment
│   └── ...                        # Bokeh, pandas, yaml, etc.
├── scripts/                       # Python scripts
│   ├── apply-rules.py            # Config generator
│   ├── monitor-devices.py        # Device monitor daemon
│   └── start-capture.py          # Capture manager
├── web/                          # Dashboard code
│   ├── dashboard.py              # Bokeh server entry
│   ├── layouts.py                # UI components
│   ├── callbacks.py              # Live update handlers
│   └── data_sources.py           # Data fetching
└── requirements.txt              # Python dependencies

/etc/isolator/                     # Generated configurations
├── hostapd.conf                  # WiFi AP config
├── dnsmasq.conf                  # DHCP/DNS config
└── isolator.nft                  # nftables rules

/etc/systemd/system/               # System services
├── isolator.service
├── isolator-monitor.service
├── isolator-dashboard.service
├── isolator-capture@.service
└── isolator-bridge.service

/var/log/isolator/                 # Logs
├── traffic.log                   # JSON traffic events
└── dnsmasq.log                   # DHCP/DNS events

/mnt/isolator/                     # USB drive (config + captures)
├── conf/
│   └── isolator.conf.yaml        # User configuration
└── captures/
    ├── aa-bb-cc-dd-ee-ff/        # Per-device captures
    │   └── capture_*.pcap
    ├── unknown/                  # Unknown device captures
    │   └── capture_*.pcap
    └── bridge/                   # Bridge mode captures
        └── capture_*.pcap
```

## 🚀 Deployment Workflow

### Option 1: Quick Deploy (Windows)

```powershell
# 1. Edit config
notepad config\isolator.conf.yaml

# 2. Run deployment script
.\deploy.ps1
```

### Option 2: Manual Deploy

```powershell
# 1. Edit config
notepad config\isolator.conf.yaml

# 2. Copy to Pi
scp -i ./y -r . paul@192.168.69.11:/tmp/isolator-deploy/

# 3. Copy config to USB drive
scp -i ./y config/isolator.conf.yaml paul@192.168.69.11:/tmp/
ssh -i ./y paul@192.168.69.11 "sudo mv /tmp/isolator.conf.yaml /mnt/isolator/conf/"

# 4. Run setup
ssh -i ./y paul@192.168.69.11
cd /tmp/isolator-deploy
sudo bash server/setup-isolator.sh --config /mnt/isolator/conf/isolator.conf.yaml
```

## 🔧 Service Management

```bash
# Start/stop main service
sudo systemctl start isolator
sudo systemctl stop isolator

# Reload config (no restart needed)
sudo systemctl reload isolator

# Check status
sudo systemctl status isolator
sudo systemctl status isolator-monitor
sudo systemctl status isolator-dashboard

# View logs
sudo journalctl -u isolator -f
sudo journalctl -u isolator-monitor -f

# List active captures
systemctl list-units 'isolator-capture@*'

# Stop specific capture
sudo systemctl stop isolator-capture@aa-bb-cc-dd-ee-ff.service
```

## 🎓 Testing Workflow

### 1. Verify Installation

```bash
# Check all services
sudo systemctl status isolator isolator-monitor isolator-dashboard hostapd dnsmasq

# View generated configs
cat /etc/isolator/hostapd.conf
cat /etc/isolator/dnsmasq.conf
sudo nft list ruleset
```

### 2. Connect Test Device

```bash
# Watch for new connections
sudo journalctl -u isolator-monitor -f

# Check DHCP leases
cat /var/lib/misc/dnsmasq.leases

# Check nftables counters
sudo nft list ruleset | grep counter
```

### 3. Verify Capture

```bash
# List captures
ls -lh /mnt/isolator/captures/

# View capture in terminal
sudo tcpdump -r /mnt/isolator/captures/aa-bb-cc-dd-ee-ff/capture_*.pcap
```

### 4. Access Dashboard

```powershell
# From Windows
ssh -i ./y -L 5006:localhost:5006 paul@192.168.69.11
```
Browse to: http://localhost:5006

## ✅ What's Complete

- ✅ **Setup Script:** Full installation automation
- ✅ **Rules Generator:** YAML → hostapd/dnsmasq/nftables
- ✅ **Device Monitor:** Auto-detection and capture triggering
- ✅ **Packet Capture:** Per-device rolling captures
- ✅ **Systemd Services:** All service units defined
- ✅ **Bridge Mode:** Service for target AP analysis
- ✅ **Documentation:** Complete deployment and usage guides
- ✅ **Windows Deployment:** One-command PowerShell script

## 🎯 Next Steps

1. **Deploy to Pi:**
   - Run `.\deploy.ps1` from Windows
   - Or follow manual deployment in DEPLOYMENT.md

2. **Test with Real Device:**
   - Connect phone/camera to AP
   - Verify capture starts automatically
   - Check dashboard shows device

3. **Review Captures:**
   - Download .pcap files
   - Open in Wireshark
   - Analyze traffic patterns

4. **Tune Configuration:**
   - Adjust device rules as needed
   - Test isolation between devices
   - Verify internet access policies

5. **Future Enhancements (Phase 5):**
   - Yocto image for appliance deployment
   - QR code configuration for devices
   - Voice trigger UI for hands-free operation

## 📝 Notes

- All Python scripts run in a virtual environment (`/opt/isolator/venv`)
- Config changes require `sudo systemctl reload isolator` to apply
- Captures auto-rotate (1-hour files, 24 hours retention)
- Dashboard binds to localhost only (SSH tunnel required for remote access)
- Bridge mode conflicts with normal AP mode (cannot run simultaneously)
- USB drive at `/mnt/isolator` stores config and captures (portable)

## 🐛 Known Issues

None at this time. See DEPLOYMENT.md troubleshooting section for common issues.

## 🤝 Contributing

This is a personal project for IoT device reverse engineering. Config examples and device profiles welcome!
