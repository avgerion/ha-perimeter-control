# Network Isolator Scripts

This directory contains Python scripts for the Network Isolator system.

## Scripts

### apply-rules.py
**Purpose:** Configuration generator and rules applier

Reads `isolator.conf.yaml` and generates:
- `hostapd.conf` - WiFi AP configuration
- `dnsmasq.conf` - DHCP/DNS configuration  
- `isolator.nft` - nftables firewall rules

**Usage:**
```bash
python3 apply-rules.py --config /mnt/isolator/conf/isolator.conf.yaml --output-dir /etc/isolator
```

**Called by:**
- `isolator.service` on start and reload
- Setup script during installation

### monitor-devices.py
**Purpose:** Device connection monitor

Watches dnsmasq.leases file for new device connections and:
- Identifies devices from config (or marks as unknown)
- Starts packet capture services automatically
- Logs connection/disconnection events

**Usage:**
```bash
python3 monitor-devices.py --config /mnt/isolator/conf/isolator.conf.yaml --interval 5
```

**Runs as:** `isolator-monitor.service` (systemd daemon)

### start-capture.py
**Purpose:** Packet capture manager

Starts/stops tcpdump captures for specific devices using systemd template units.

**Usage:**
```bash
# Start capture for a device
python3 start-capture.py --mac AA:BB:CC:DD:EE:FF --device-id my-camera --action start

# Stop capture
python3 start-capture.py --mac AA:BB:CC:DD:EE:FF --device-id my-camera --action stop
```

**Called by:**
- `monitor-devices.py` when devices connect/disconnect
- Manual execution for testing

**Manages:** `isolator-capture@MAC.service` instances

## Installation

These scripts are automatically copied to `/opt/isolator/scripts/` during setup and run within a Python virtual environment.

## Dependencies

All scripts require Python 3.7+ and the following packages (managed via venv):
- pyyaml
- Standard library modules (subprocess, logging, pathlib, etc.)

## Development

To test scripts locally on Pi:

```bash
cd /opt/isolator
source venv/bin/activate
python3 scripts/apply-rules.py --config /mnt/isolator/conf/isolator.conf.yaml --output-dir /tmp/test
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ isolator.service (systemd)                              │
│   Calls: apply-rules.py                                 │
│   Generates: hostapd.conf, dnsmasq.conf, isolator.nft   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ isolator-monitor.service (systemd daemon)               │
│   Runs: monitor-devices.py                              │
│   Watches: /var/lib/misc/dnsmasq.leases                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ (calls on device connect)
┌─────────────────────────────────────────────────────────┐
│ start-capture.py                                        │
│   Starts: isolator-capture@MAC.service                  │
│   Captures: tcpdump per device                          │
└─────────────────────────────────────────────────────────┘
```

## Logging

All scripts log to systemd journal:

```bash
# View logs
sudo journalctl -u isolator -f
sudo journalctl -u isolator-monitor -f
```

## Error Handling

Scripts use proper exit codes:
- `0` - Success
- `1` - General error (config missing, permission denied, etc.)
- Non-zero from subprocess calls

Check logs when services fail to start.
