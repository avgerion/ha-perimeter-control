# Network Isolator - Deployment Guide

(This file was moved from the project root to avoid confusion with PerimeterControl. It contains deployment instructions for the standalone Network Isolator service.)

# --- Original Content Below ---
# Network Isolator - Deployment Guide

This guide walks you through deploying the Network Isolator to your Raspberry Pi.

## Prerequisites

- Raspberry Pi 3 Model B/B+ with Raspberry Pi OS Lite (64-bit)
- SSH access configured
- USB drive mounted at `/mnt/isolator` (recommended for config and captures)
- Network connectivity (ethernet recommended during setup)

## Quick Start

### 1. Prepare the Config File

First, customize your configuration on your development machine:

```bash
# PerimeterControl - Deployment Guide
cd C:\Users\avger\Offline\Documents\NetworkIsolator
This guide walks you through deploying PerimeterControl to your Raspberry Pi.
- USB drive mounted at `/mnt/perimetercontrol` (recommended for config and captures)

cd C:\Users\avger\Offline\Documents\PerimeterControl
notepad config\perimetercontrol.conf.yaml
- `ap.password` - WiFi password (min 8 characters)
ssh -i $KEY ${PI_USER}@${PI_IP} "sudo mkdir -p /mnt/perimetercontrol/conf /tmp/perimetercontrol-deploy"

scp -i $KEY config/perimetercontrol.conf.yaml ${PI_USER}@${PI_IP}:/tmp/perimetercontrol.conf.yaml
ssh -i $KEY ${PI_USER}@${PI_IP} "sudo mv /tmp/perimetercontrol.conf.yaml /mnt/perimetercontrol/conf/"
From your Windows machine:
scp -i $KEY -r . ${PI_USER}@${PI_IP}:/tmp/perimetercontrol-deploy/
```powershell
cd /tmp/perimetercontrol-deploy
$PI_IP = "192.168.69.11"
sudo bash system_services/setup-perimetercontrol.sh --config /mnt/perimetercontrol/conf/perimetercontrol.conf.yaml
$PI_USER = "paul"
sudo systemctl status perimetercontrol

sudo systemctl status perimetercontrol-dashboard
ssh -i $KEY ${PI_USER}@${PI_IP} "sudo mkdir -p /mnt/isolator/conf /tmp/isolator-deploy"
sudo systemctl status perimetercontrol-monitor
# Copy config file
sudo journalctl -u perimetercontrol -f
PerimeterControl consists of several systemd services:
| `perimetercontrol.service` | Main service - applies firewall rules | `systemctl status perimetercontrol` |
| `perimetercontrol-monitor.service` | Monitors for new devices, starts captures | `systemctl status perimetercontrol-monitor` |
| `perimetercontrol-dashboard.service` | Web dashboard (Bokeh server) | `systemctl status perimetercontrol-dashboard` |
| `perimetercontrol-capture@MAC.service` | Per-device packet capture (template) | Auto-started for each device |
| `perimetercontrol-bridge.service` | Bridge mode (optional) | Manual start when needed |
### 3. Run the Setup Script
sudo nano /mnt/perimetercontrol/conf/perimetercontrol.conf.yaml
SSH into the Pi and run the installer:
sudo systemctl reload perimetercontrol
```bash
sudo systemctl restart perimetercontrol perimetercontrol-monitor perimetercontrol-dashboard
ssh -i ./y paul@192.168.69.11
ls -lh /mnt/perimetercontrol/captures/
# Run setup script
Captures are stored in `/mnt/perimetercontrol/captures/`:
sudo bash system_services/setup-isolator.sh --config /mnt/isolator/conf/isolator.conf.yaml
ls -lh /mnt/perimetercontrol/captures/aa-bb-cc-dd-ee-ff/

sudo tcpdump -r /mnt/perimetercontrol/captures/aa-bb-cc-dd-ee-ff/capture_20240101_120000.pcap
- ✓ Install all required packages (hostapd, dnsmasq, nftables, tcpdump, Python)
scp -i ./y paul@192.168.69.11:/mnt/perimetercontrol/captures/aa-bb-cc-dd-ee-ff/*.pcap ./
- ✓ Set up Python virtual environment for dashboard
sudo journalctl -u perimetercontrol -u perimetercontrol-monitor -u perimetercontrol-dashboard -f
- ✓ Install and start systemd services
tail -f /var/log/perimetercontrol/traffic.log

cat /etc/perimetercontrol/hostapd.conf

sudo hostapd -dd /etc/perimetercontrol/hostapd.conf

cat /etc/perimetercontrol/dnsmasq.conf
# Check service status
sudo journalctl -u perimetercontrol-dashboard
sudo systemctl status isolator-dashboard
sudo systemctl status perimetercontrol-dashboard
sudo systemctl status hostapd
sudo systemctl status perimetercontrol-monitor

systemctl list-units 'perimetercontrol-capture@*'
sudo journalctl -u isolator -f
sudo systemctl status perimetercontrol-capture@aa-bb-cc-dd-ee-ff.service
# Check WiFi AP
ls -la /mnt/perimetercontrol/captures/

sudo systemctl start perimetercontrol-bridge
iw dev wlan0 station dump
Captures will be in `/mnt/perimetercontrol/captures/bridge/`

sudo mkdir -p /mnt/perimetercontrol

sudo mount /dev/sda1 /mnt/perimetercontrol

echo "/dev/sda1 /mnt/perimetercontrol ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
# Create SSH tunnel to dashboard
sudo mkdir -p /mnt/perimetercontrol/{conf,captures}
```
sudo cp /tmp/perimetercontrol.conf.yaml /mnt/perimetercontrol/conf/
Then open your browser to: **http://localhost:5006**
 # Edit /opt/perimetercontrol/scripts/start-capture.py
## Services Overview
 # Edit capture service to add:
The Network Isolator consists of several systemd services:
 # Edit /etc/systemd/system/perimetercontrol-monitor.service
| Service | Purpose | Status Check |
sudo systemctl restart perimetercontrol-monitor
| `isolator.service` | Main service - applies firewall rules | `systemctl status isolator` |
notepad config\perimetercontrol.conf.yaml
| `isolator-dashboard.service` | Web dashboard (Bokeh server) | `systemctl status isolator-dashboard` |
scp -i ./y config/perimetercontrol.conf.yaml paul@192.168.69.11:/tmp/
| `isolator-bridge.service` | Bridge mode (optional) | Manual start when needed |
ssh -i ./y paul@192.168.69.11 "sudo mv /tmp/perimetercontrol.conf.yaml /mnt/perimetercontrol/conf/"
| `dnsmasq.service` | DHCP/DNS server | `systemctl status dnsmasq` |
ssh -i ./y paul@192.168.69.11 "sudo systemctl reload perimetercontrol"
## Configuration Changes
scp -i ./y -r paul@192.168.69.11:/mnt/perimetercontrol/conf ./backup/
To modify the configuration after installation:
scp -i ./y -r paul@192.168.69.11:/mnt/perimetercontrol/captures ./backup/
```bash
ssh -i ./y paul@192.168.69.11 "sudo cp -r /tmp/conf/* /mnt/perimetercontrol/conf/"
sudo nano /mnt/isolator/conf/isolator.conf.yaml
sudo journalctl -u perimetercontrol -u perimetercontrol-monitor --since "10 minutes ago"
# Reload configuration (regenerates and applies rules)
sudo systemctl reload isolator

# Restart all services (if needed)
sudo systemctl restart isolator isolator-monitor isolator-dashboard
```

## Connecting Devices

1. **Find the WiFi AP** - Look for the SSID you configured (default: "NetworkIsolator")
2. **Connect with password** - Use the password from your config
3. **Device auto-detected** - The monitor service will detect the device
4. **Capture starts automatically** - If enabled in config

View connected devices:
```bash
# See DHCP leases
cat /var/lib/misc/dnsmasq.leases

# See WiFi associations
iw dev wlan0 station dump

# View captures
ls -lh /mnt/isolator/captures/
```

## Viewing Captures

Captures are stored in `/mnt/isolator/captures/`:

```bash
# List captures for a device
ls -lh /mnt/isolator/captures/aa-bb-cc-dd-ee-ff/

# View capture in terminal
sudo tcpdump -r /mnt/isolator/captures/aa-bb-cc-dd-ee-ff/capture_20240101_120000.pcap

# Copy to Windows for Wireshark analysis
# On Windows:
scp -i ./y paul@192.168.69.11:/mnt/isolator/captures/aa-bb-cc-dd-ee-ff/*.pcap ./
```

## Logs

View logs for troubleshooting:

```bash
# All isolator logs
sudo journalctl -u isolator -u isolator-monitor -u isolator-dashboard -f

# Just firewall events
sudo journalctl -k | grep -i nft

# DHCP events
sudo journalctl -u dnsmasq -f

# WiFi AP events
sudo journalctl -u hostapd -f

# Dashboard logs
sudo journalctl -u isolator-dashboard

# Traffic logs (JSON format)
tail -f /var/log/isolator/traffic.log
```

## Troubleshooting

### WiFi AP Not Visible

```bash
# Check hostapd status
sudo systemctl status hostapd

# Check wlan0 interface
ip addr show wlan0

# View hostapd config
cat /etc/isolator/hostapd.conf

# Test hostapd manually
sudo hostapd -dd /etc/isolator/hostapd.conf
```

### Devices Can't Get DHCP

```bash
# Check dnsmasq status
sudo systemctl status dnsmasq

# View DHCP config
cat /etc/isolator/dnsmasq.conf

# Check for errors
sudo journalctl -u dnsmasq -n 50
```

### No Internet Access

```bash
# Check IP forwarding
sysctl net.ipv4.ip_forward

# Check nftables rules
sudo nft list ruleset

# Check NAT
sudo nft list table ip nat

# Verify upstream interface
ip route show
```

### Dashboard Not Accessible

```bash
# Check dashboard service
sudo systemctl status isolator-dashboard

# View dashboard logs
sudo journalctl -u isolator-dashboard -f

# Test locally on Pi
curl http://localhost:5006
```

### Capture Not Working

```bash
# Check monitor service
sudo systemctl status isolator-monitor

# List active capture services
systemctl list-units 'isolator-capture@*'

# Check specific device capture
sudo systemctl status isolator-capture@aa-bb-cc-dd-ee-ff.service

# Check capture permissions
ls -la /mnt/isolator/captures/
```

## Bridge Mode (Optional)

To analyze a device's own AP (e.g., DJI drone, WiFi camera):

1. **Configure target AP**:
```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant-wlan1.conf
```

Add:
```
network={
    ssid="DJI_DRONE_AP"
    psk="12345678"
}
```

2. **Start bridge mode**:
```bash
sudo systemctl start isolator-bridge
```

3. **Check connection**:
```bash
iw dev wlan1 link
ip addr show wlan1
```

Captures will be in `/mnt/isolator/captures/bridge/`

See [docs/BRIDGE-MODE.md](../docs/BRIDGE-MODE.md) for full details.

## USB Drive Setup (Recommended)

Using a USB drive for config and captures:

```bash
# Format USB drive (on Pi)
sudo mkfs.ext4 /dev/sda1

# Create mount point
sudo mkdir -p /mnt/isolator

# Mount
sudo mount /dev/sda1 /mnt/isolator

# Auto-mount on boot
echo "/dev/sda1 /mnt/isolator ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

# Create directories
sudo mkdir -p /mnt/isolator/{conf,captures}

# Copy config
sudo cp /tmp/isolator.conf.yaml /mnt/isolator/conf/
```

## Performance Tuning

For better performance with multiple devices:

```bash
# Increase tcpdump buffer size
# Edit /opt/isolator/scripts/start-capture.py
# Add: -B 4096 to tcpdump command

# Limit capture file sizes
# Edit capture service to add:
# -C 100 (100MB files)

# Adjust monitoring interval
# Edit /etc/systemd/system/isolator-monitor.service
# Add: --interval 10 (check every 10s instead of 5s)

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl restart isolator-monitor
```

## Updating Configuration

To update device rules or AP settings:

```bash
# 1. Edit config on Windows
notepad config\isolator.conf.yaml

# 2. Copy to Pi
scp -i ./y config/isolator.conf.yaml paul@192.168.69.11:/tmp/
ssh -i ./y paul@192.168.69.11 "sudo mv /tmp/isolator.conf.yaml /mnt/isolator/conf/"

# 3. Reload on Pi
ssh -i ./y paul@192.168.69.11 "sudo systemctl reload isolator"
```

## Backup and Restore

### Backup

```powershell
# On Windows: Backup config and captures
scp -i ./y -r paul@192.168.69.11:/mnt/isolator/conf ./backup/
scp -i ./y -r paul@192.168.69.11:/mnt/isolator/captures ./backup/
```

### Restore

```bash
# On Pi: Restore from backup
scp -i ./y -r ./backup/conf paul@192.168.69.11:/tmp/
ssh -i ./y paul@192.168.69.11 "sudo cp -r /tmp/conf/* /mnt/isolator/conf/"
```

## Security Best Practices

1. **Change default WiFi password** - Use strong WPA2 password (16+ characters)
2. **Secure SSH access** - Use key-based auth only (disable password auth)
3. **Update regularly** - `sudo apt update && sudo apt upgrade`
4. **Firewall rules** - Review device access rules regularly
5. **Monitor logs** - Check for suspicious activity
6. **Backup captures** - Store important captures off-device

## Next Steps

- Read [docs/WEB-DASHBOARD.md](../docs/WEB-DASHBOARD.md) for dashboard features
- Read [docs/BRIDGE-MODE.md](../docs/BRIDGE-MODE.md) for advanced analysis
- Read [docs/DEVICE-ACCESS-MODEL.md](../docs/DEVICE-ACCESS-MODEL.md) for rule examples
- Add your devices to the config
- Test isolation with known devices
- Review traffic captures

## Getting Help

Check the logs first:
```bash
sudo journalctl -u isolator -u isolator-monitor --since "10 minutes ago"
```

Common issues and solutions in [docs/](../docs/)

