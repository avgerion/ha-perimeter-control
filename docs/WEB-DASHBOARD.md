# Web Dashboard — Network Isolator Quick View

A real-time web interface for monitoring connected devices, traffic patterns, and managing firewall rules using Bokeh Server.

## Overview

The dashboard provides live visibility into:

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (http://isolator.local:5006)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ Bokeh WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│  Bokeh Server (server/web/dashboard.py)                     │
│  - Live data updates via periodic callbacks                 │
│  - Interactive widgets for rule changes                     │
└───┬─────────────┬─────────────┬─────────────┬──────────────┘
    │             │             │             │
    ▼             ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐
│nftables│  │ dnsmasq  │  │ pcap    │  │ config       │
│ logs   │  │ leases   │  │ stats   │  │ isolator.    │
│        │  │          │  │         │  │ conf.yaml    │
└────────┘  └──────────┘  └─────────┘  └──────────────┘
```

## Technology Stack

| Component | Purpose |
|-----------|---------|
| **Bokeh Server** | Interactive visualization and real-time updates |
| **Tornado** | Web server (included with Bokeh) |
| **Pandas** | Data processing for traffic logs |
| **pyinotify** | Watch config file for changes |
| **subprocess** | Interface with nftables, dnsmasq, tcpdump |

## Dashboard Views

### 1. Device Overview Panel (Top)

**Layout:** Grid of device cards

Each card shows:
  - Toggle internet access
  - Enable/disable capture
  - View full logs

**Interactive Actions:**

### 2. Live Traffic Graphs (Center)

**Real-time plotting with 30-second rolling window:**

  - Upload/download rates per device
  - Color-coded by device
  - Y-axis: KB/s or MB/s (auto-scaling)
  - X-axis: Time (last 30s, 5min, 1hr selectable)

  - Shows active connections over time
  - Each row = one device
  - Bars = connection duration
  - Color = protocol (blue=TCP, green=UDP, orange=ICMP)

  - 2D grid: devices × time
  - Color intensity = packet rate
  - Useful for spotting traffic bursts

  - DNS, HTTP, HTTPS, MQTT, other
  - Updates every 5 seconds

### 3. Active Connections Table (Bottom Left)

**Sortable, filterable table:**

| Device | Protocol | Remote IP | Remote Port | State | Duration | Packets |
|--------|----------|-----------|-------------|-------|----------|---------|
| iot-sensor-01 | TCP | 52.1.2.3 | 443 | ESTABLISHED | 00:04:23 | 1,234 |
| target-device | UDP | 8.8.8.8 | 53 | - | 00:00:01 | 2 |


### 4. Events & Alerts (Bottom Right)

**Live log stream:**


Format:
```
[14:32:01] 🔴 BLOCKED: guest-phone → 192.168.1.10:22 (SSH)
[14:31:45] 🟢 CAPTURE STARTED: target-device → /mnt/isolator/captures/
[14:30:12] 🔵 NEW DEVICE: MAC aa:bb:cc:dd:ee:ff (unknown-device-1)
```

Auto-scroll to latest, with pause button.

### 5. Configuration Panel (Collapsible Sidebar)

**Quick rule editor:**

  - Internet access (allow/deny/log-only)
  - Packet capture (on/off)
  - Logging level (none/metadata/full)

**System status indicators:**

## Implementation Details

### File Structure

```
server/
  web/
    dashboard.py          # Main Bokeh app entry point
    layouts.py            # Dashboard layout definitions
    data_sources.py       # Live data fetching and processing
    callbacks.py          # Interactive widget callbacks
    config_manager.py     # Read/write isolator.conf.yaml
    traffic_monitor.py    # Parse nftables logs, dnsmasq leases
    static/
      custom.css          # Custom styling
      logo.png            # Branding
    templates/
      index.html          # Bokeh app template

  isolator-dashboard.service  # systemd unit for web server
```

### Data Update Strategy

**Polling intervals:**

**Data sources:**

1. **Connected devices** → parse `/var/lib/misc/dnsmasq.leases`
2. **Traffic stats** → read nftables counters via `nft list ruleset`
3. **Logs** → tail `/var/log/isolator/traffic.log` (structured JSON)
4. **Captures** → check `/mnt/isolator/captures/` for active tcpdump processes
5. **Config** → read `config/isolator.conf.yaml` on demand

### Performance Considerations

**On Raspberry Pi 3:**

### Security

  ```bash
  ssh -L 5006:localhost:5006 pi@isolator.local
  ```
  Then browse to `http://localhost:5006` on your Windows machine.

## Running the Dashboard

### Development (manual start)

```bash
cd server/web
bokeh serve dashboard.py --show --port 5006
```

### Production (systemd service)

```bash
sudo systemctl enable isolator-dashboard
sudo systemctl start isolator-dashboard
sudo systemctl status isolator-dashboard
```

Service runs as user `isolator` with limited permissions; writes to config require group `isolator-admin`.

### Accessing from Windows

**SSH tunnel method (most secure):**
```powershell
ssh -L 5006:localhost:5006 pi@isolator.local
```
Browse to: `http://localhost:5006`

**Direct access (if Pi is on trusted LAN):**
Configure dashboard to bind to `0.0.0.0:5006`, then browse to: `http://isolator.local:5006`

## Future Enhancements


## Dependencies

Add to `server/requirements.txt`:

```
bokeh>=3.3.0
pandas>=2.0.0
pyyaml>=6.0
pyinotify>=0.9.6
```

Install:
```bash
pip3 install -r server/requirements.txt
```
