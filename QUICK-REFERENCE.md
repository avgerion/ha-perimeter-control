# Network Isolator - Quick Reference Card

## 🚀 Quick Deploy (Windows → Pi)

```powershell
# One-command deploy
.\deploy.ps1

# Or specify custom settings
.\deploy.ps1 -PiIP "192.168.69.11" -PiUser "paul" -KeyFile "./y"
```

## 🔌 Access Dashboard

```powershell
# SSH tunnel
ssh -i ./y -L 5006:localhost:5006 paul@192.168.69.11
```
Browse to: **http://localhost:5006**

## 📋 Service Commands

```bash
# Status check
sudo systemctl status isolator isolator-monitor isolator-dashboard

# Reload config (live, no restart)
sudo systemctl reload isolator

# Restart all services
sudo systemctl restart isolator isolator-monitor isolator-dashboard

# View logs (live)
sudo journalctl -u isolator -f
sudo journalctl -u isolator-monitor -f
```

## 📡 Device Monitoring

```bash
# Connected devices
cat /var/lib/misc/dnsmasq.leases
iw dev wlan0 station dump

# Active captures
systemctl list-units 'isolator-capture@*'

# View captures
ls -lh /mnt/isolator/captures/
```

## 🔥 Firewall Commands

```bash
# View current rules
sudo nft list ruleset

# View traffic counters
sudo nft list ruleset | grep counter

# Check NAT
sudo nft list table ip nat

# View active connections
sudo conntrack -L
```

## 📦 Capture Management

```bash
# View device captures
sudo tcpdump -r /mnt/isolator/captures/aa-bb-cc-dd-ee-ff/capture_*.pcap

# Download to Windows
scp -i ./y -r paul@192.168.69.11:/mnt/isolator/captures/ ./

# Stop capture for device
sudo systemctl stop isolator-capture@aa-bb-cc-dd-ee-ff.service
```

## 🛠️ Configuration Updates

```bash
# Edit config (on Pi)
sudo nano /mnt/isolator/conf/isolator.conf.yaml

# Or from Windows
notepad config\isolator.conf.yaml
scp -i ./y config/isolator.conf.yaml paul@192.168.69.11:/tmp/
ssh -i ./y paul@192.168.69.11 "sudo mv /tmp/isolator.conf.yaml /mnt/isolator/conf/"

# Apply changes
sudo systemctl reload isolator
```

## 🌉 Bridge Mode (Target AP Analysis)

```bash
# Configure target AP
sudo nano /etc/wpa_supplicant/wpa_supplicant-wlan1.conf

# Start bridge mode
sudo systemctl start isolator-bridge

# Check connection
iw dev wlan1 link
ip addr show wlan1

# View captures
ls -lh /mnt/isolator/captures/bridge/
```

## 🐛 Troubleshooting

```bash
# Check WiFi AP
sudo systemctl status hostapd
iw dev wlan0 info

# Check DHCP
sudo systemctl status dnsmasq
sudo journalctl -u dnsmasq -n 50

# Check IP forwarding
sysctl net.ipv4.ip_forward

# Test hostapd manually
sudo hostapd -dd /etc/isolator/hostapd.conf

# View all isolator logs
sudo journalctl -u 'isolator*' --since "10 minutes ago"
```

## 📂 Important Locations

```
/mnt/isolator/conf/isolator.conf.yaml    # Main config
/etc/isolator/                           # Generated configs
/var/log/isolator/traffic.log           # Traffic events (JSON)
/mnt/isolator/captures/                  # All captures
/opt/isolator/                           # Installation directory
```

## 🔐 Security Quick Check

```bash
# Check SSH config
cat ~/.ssh/authorized_keys

# Check firewall rules
sudo nft list ruleset

# Check service permissions
ls -l /opt/isolator/scripts/

# Update system
sudo apt update && sudo apt upgrade
```

## 📊 Dashboard Features

- **Device Cards:** Live connection status, MAC, IP, hostname
- **Bandwidth Graphs:** Real-time upload/download per device
- **Connections Table:** Active TCP/UDP connections
- **Event Log:** Traffic events, firewall blocks, connections
- **Config Panel:** Quick rule editor (allow/deny/capture toggles)
- **SSH Helper:** Copy/paste SSH commands for remote access

## 🔄 Live Monitoring

```bash
# Watch device connections
watch -n 2 'cat /var/lib/misc/dnsmasq.leases'

# Monitor traffic log
tail -f /var/log/isolator/traffic.log | jq

# Watch captures grow
watch -n 5 'du -sh /mnt/isolator/captures/*'

# Monitor bandwidth (per interface)
iftop -i wlan0
nethogs wlan0
```

## ⚡ Performance Tuning

```bash
# Increase capture buffer
# Edit: /opt/isolator/scripts/start-capture.py
# Add: -B 4096 to tcpdump command

# Limit capture file size
# Edit: server/isolator-capture@.service
# Add: -C 100 (100MB max per file)

# Adjust monitoring interval
# Edit: /etc/systemd/system/isolator-monitor.service
# Add: --interval 10 (check every 10s)

# Apply changes
sudo systemctl daemon-reload
sudo systemctl restart isolator-monitor
```

## 📖 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[IMPLEMENTATION-SUMMARY.md](IMPLEMENTATION-SUMMARY.md)** - What's in Phase 2 & 3
- **[docs/WEB-DASHBOARD.md](docs/WEB-DASHBOARD.md)** - Dashboard features
- **[docs/BRIDGE-MODE.md](docs/BRIDGE-MODE.md)** - Target AP analysis
- **[docs/DEVICE-ACCESS-MODEL.md](docs/DEVICE-ACCESS-MODEL.md)** - Rule semantics
- **[docs/SSH-QUICK-REFERENCE.md](docs/SSH-QUICK-REFERENCE.md)** - SSH commands

## 🎯 Quick Start Checklist

- [ ] Edit `config/isolator.conf.yaml` (SSID, password, devices)
- [ ] Run `.\deploy.ps1` from Windows
- [ ] Wait for setup to complete (~5 minutes)
- [ ] SSH tunnel: `ssh -i ./y -L 5006:localhost:5006 paul@192.168.69.11`
- [ ] Open dashboard: http://localhost:5006
- [ ] Connect test device to WiFi AP
- [ ] Verify device appears in dashboard
- [ ] Check capture started: `ls /mnt/isolator/captures/`
- [ ] Download captures: `scp -i ./y -r paul@192.168.69.11:/mnt/isolator/captures/ ./`
- [ ] Open captures in Wireshark

---

**Created for:** Network Isolator v1.0  
**Platform:** Raspberry Pi 3 + Raspberry Pi OS Lite 64-bit  
**See:** DEPLOYMENT.md for full documentation
