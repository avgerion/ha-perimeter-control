# Server Components

This directory contains the server-side components for Network Isolator.

## Contents

### Setup Script
- `setup-isolator.sh` - Main installation script for Raspberry Pi

### Systemd Services
- `isolator.service` - Main service (applies firewall rules)
- `isolator-monitor.service` - Device monitoring daemon
- `isolator-dashboard.service` - Web dashboard (Bokeh server)
- `isolator-capture@.service` - Template for per-device packet captures
- `isolator-bridge.service` - Bridge mode (optional, for connecting to target device APs)

### Web Dashboard
- `web/` - Dashboard implementation (see [../docs/WEB-DASHBOARD.md](../docs/WEB-DASHBOARD.md))
  - `dashboard.py` - Main Bokeh server entry point
  - `layouts.py` - UI components and structure
  - `callbacks.py` - Live update handlers
  - `data_sources.py` - Data fetching from system sources
- `requirements.txt` - Python dependencies

## Installation

Run the setup script on your Raspberry Pi:

```bash
sudo bash setup-isolator.sh --config /mnt/isolator/conf/isolator.conf.yaml
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for complete installation instructions.

## Services Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    System Boot                           │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴───────────┬───────────┐
        ▼                       ▼           ▼
   hostapd.service      dnsmasq.service   isolator.service
   (WiFi AP)            (DHCP/DNS)        (Firewall Rules)
        │                       │           │
        └───────────┬───────────┘           │
                    │                       │
                    ▼                       ▼
          isolator-monitor.service    isolator-dashboard.service
          (Device Detection)          (Web UI)
                    │
                    ▼
          isolator-capture@MAC.service
          (Per-Device Captures)
```

## Service Management

```bash
# Start/stop main service
sudo systemctl start isolator
sudo systemctl stop isolator

# Reload config (regenerates rules without restart)
sudo systemctl reload isolator

# Check status
sudo systemctl status isolator
sudo systemctl status isolator-monitor
sudo systemctl status isolator-dashboard

# View logs
sudo journalctl -u isolator -f
sudo journalctl -u isolator-monitor -f
sudo journalctl -u isolator-dashboard -f

# List active captures
systemctl list-units 'isolator-capture@*'

# Stop specific device capture
sudo systemctl stop isolator-capture@aa-bb-cc-dd-ee-ff.service
```

## Web Dashboard

The dashboard runs on port 5006 (localhost only for security).

**Access via SSH tunnel:**
```bash
ssh -L 5006:localhost:5006 paul@192.168.69.11
```

Then browse to: http://localhost:5006

See [../docs/WEB-DASHBOARD.md](../docs/WEB-DASHBOARD.md) for features and screenshots.

## Bridge Mode

For advanced analysis (connecting to target device APs):

```bash
# Configure target AP credentials
sudo nano /etc/wpa_supplicant/wpa_supplicant-wlan1.conf

# Start bridge mode
sudo systemctl start isolator-bridge

# View bridge captures
ls -lh /mnt/isolator/captures/bridge/
```

See [../docs/BRIDGE-MODE.md](../docs/BRIDGE-MODE.md) for setup guide.

## Directory Structure (After Installation)

```
/opt/isolator/
├── venv/                    # Python virtual environment
├── scripts/                 # Python scripts (from ../scripts/)
│   ├── apply-rules.py
│   ├── monitor-devices.py
│   └── start-capture.py
├── web/                     # Dashboard code
│   ├── dashboard.py
│   ├── layouts.py
│   ├── callbacks.py
│   └── data_sources.py
└── requirements.txt

/etc/isolator/
├── hostapd.conf            # Generated WiFi AP config
├── dnsmasq.conf            # Generated DHCP/DNS config
└── isolator.nft            # Generated nftables rules

/etc/systemd/system/
├── isolator.service
├── isolator-monitor.service
├── isolator-dashboard.service
├── isolator-capture@.service
└── isolator-bridge.service

/var/log/isolator/
├── traffic.log             # Device traffic events (JSON)
└── dnsmasq.log             # DHCP/DNS events

/mnt/isolator/
├── conf/
│   └── isolator.conf.yaml  # User configuration
└── captures/
    ├── aa-bb-cc-dd-ee-ff/  # Per-device captures
    │   └── *.pcap
    ├── unknown/            # Unknown device captures
    │   └── *.pcap
    └── bridge/             # Bridge mode captures
        └── *.pcap
```

## Updating

To update the installation:

```bash
# Copy new files to Pi
scp -r server/ paul@192.168.69.11:/tmp/isolator-update/

# SSH into Pi
ssh paul@192.168.69.11

# Copy to installation directory
sudo cp -r /tmp/isolator-update/server/web/* /opt/isolator/web/
sudo cp /tmp/isolator-update/server/*.service /etc/systemd/system/

# Reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl restart isolator isolator-monitor isolator-dashboard
```

## Development

To test dashboard locally:

```bash
cd /opt/isolator
source venv/bin/activate
python3 web/dashboard.py
```

## Logs and Debugging

**Systemd journal:**
```bash
sudo journalctl -u isolator --since "1 hour ago"
```

**Traffic log:**
```bash
tail -f /var/log/isolator/traffic.log | jq
```

**nftables rules:**
```bash
sudo nft list ruleset
```

**DHCP leases:**
```bash
cat /var/lib/misc/dnsmasq.leases
```

**WiFi clients:**
```bash
iw dev wlan0 station dump
```

## Security Notes

- Dashboard binds to `127.0.0.1` only (SSH tunnel required)
- Services run with limited privileges where possible
- Packet captures require root (tcpdump)
- Config file should be readable only by root: `sudo chmod 600 /mnt/isolator/conf/isolator.conf.yaml`

## Troubleshooting

See [DEPLOYMENT.md](../DEPLOYMENT.md) for common issues and solutions.
