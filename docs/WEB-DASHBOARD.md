# Web Dashboard — Network Isolator Quick View

A real-time web interface for monitoring connected devices, traffic patterns, and managing firewall rules using Bokeh Server.

## Overview

The dashboard provides live visibility into:
- All connected WiFi devices and their current status
- Real-time traffic graphs (bandwidth, packets, connections)
- Active firewall rules and capture status
- Logs and alerts for blocked connections
- Quick controls for rule modifications and capture toggles

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
- Device name/ID (color-coded by status: green=online, gray=offline, red=blocked)
- MAC address
- Current IP address
- Connection status and duration
- Current rules: `internet: allow|deny|log-only`
- Capture status indicator (recording icon if `capture.enabled: true`)
- Quick action buttons:
  - Toggle internet access
  - Enable/disable capture
  - View full logs

**Interactive Actions:**
- Click device card → expand to show detailed stats
- Hover → tooltip with connection count, total bytes transferred

### 2. Live Traffic Graphs (Center)

**Real-time plotting with 30-second rolling window:**

- **Bandwidth Graph** (stacked area chart)
  - Upload/download rates per device
  - Color-coded by device
  - Y-axis: KB/s or MB/s (auto-scaling)
  - X-axis: Time (last 30s, 5min, 1hr selectable)

- **Connection Timeline** (horizontal bars)
  - Shows active connections over time
  - Each row = one device
  - Bars = connection duration
  - Color = protocol (blue=TCP, green=UDP, orange=ICMP)

- **Packet Count Heatmap** (optional, for dense analysis)
  - 2D grid: devices × time
  - Color intensity = packet rate
  - Useful for spotting traffic bursts

- **Protocol Distribution** (pie/donut chart)
  - DNS, HTTP, HTTPS, MQTT, other
  - Updates every 5 seconds

### 3. Active Connections Table (Bottom Left)

**Sortable, filterable table:**

| Device | Protocol | Remote IP | Remote Port | State | Duration | Packets |
|--------|----------|-----------|-------------|-------|----------|---------|
| iot-sensor-01 | TCP | 52.1.2.3 | 443 | ESTABLISHED | 00:04:23 | 1,234 |
| target-device | UDP | 8.8.8.8 | 53 | - | 00:00:01 | 2 |

- Click column headers to sort
- Search/filter by device, IP, or port
- Click row → show full packet details (if `logging: full`)

### 4. Events & Alerts (Bottom Right)

**Live log stream:**

- Blocked connection attempts (red badge)
- New device connections (blue badge)
- Capture started/stopped (green badge)
- Config reloaded (yellow badge)

Format:
```
[14:32:01] 🔴 BLOCKED: guest-phone → 192.168.1.10:22 (SSH)
[14:31:45] 🟢 CAPTURE STARTED: target-device → /mnt/isolator/captures/
[14:30:12] 🔵 NEW DEVICE: MAC aa:bb:cc:dd:ee:ff (unknown-device-1)
```

Auto-scroll to latest, with pause button.

### 5. Configuration Panel (Collapsible Sidebar)

**Quick rule editor:**

- Select device from dropdown
- Toggle switches for:
  - Internet access (allow/deny/log-only)
  - Packet capture (on/off)
  - Logging level (none/metadata/full)
- LAN access rule builder (add/remove host:port entries)
- "Apply Changes" button → writes to `isolator.conf.yaml` and triggers reload

**System status indicators:**
- hostapd status (running/stopped)
- dnsmasq status
- nftables rules loaded
- USB drive mount status (`/mnt/isolator`)
- Disk space available for captures

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
- Device status (connected/disconnected): 2 seconds
- Bandwidth graphs: 1 second
- Connection table: 3 seconds
- Logs/alerts: 1 second
- Config file changes: inotify (instant)

**Data sources:**

1. **Connected devices** → parse `/var/lib/misc/dnsmasq.leases`
2. **Traffic stats** → read nftables counters via `nft list ruleset`
3. **Logs** → tail `/var/log/isolator/traffic.log` (structured JSON)
4. **Captures** → check `/mnt/isolator/captures/` for active tcpdump processes
5. **Config** → read `config/isolator.conf.yaml` on demand

### Performance Considerations

**On Raspberry Pi 3:**
- Limit Bokeh history buffer to 1000 data points max
- Use Pandas with optimized dtypes (categorical for devices)
- Cache parsed config in memory
- Use `ColumnDataSource.stream()` for efficient updates (no full data replacement)
- Lazy-load detailed packet captures only on user request

### Security

- **Authentication:** Basic HTTP auth (username/password in config) or SSH tunnel only
- **No public exposure:** Bind to `127.0.0.1:5006` by default; access via SSH tunnel from Windows:
  ```bash
  ssh -L 5006:localhost:5006 pi@isolator.local
  ```
  Then browse to `http://localhost:5006` on your Windows machine.
- **Read-only dashboard mode:** Option to disable rule editing from web UI (enforce config file changes only)

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

- [ ] Dark mode toggle
- [ ] Export traffic reports to PDF
- [ ] Mobile-responsive layout
- [ ] Geographic IP visualization (map of external connections)
- [ ] Packet payload viewer (hexdump + ASCII)
- [ ] Integration with Wireshark remote capture (open .pcap in browser)
- [ ] Voice control via Web Speech API ("Copilot, block that device")
- [ ] QR code generator for easy AP connection sharing

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
