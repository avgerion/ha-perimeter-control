# Bridge Mode — Reverse Engineering Devices with Their Own APs

Some IoT devices create their own WiFi access points for initial setup or ongoing control:
- **Dron controllers** (DJI, Parrot)
- **WiFi cameras** with direct connect mode
- **Smart home hubs** in setup mode
- **WiFi-enabled robots or toys**
- **Media streaming devices** (Chromecast setup, etc.)

Normally, you can only connect to ONE WiFi network at a time. **Bridge Mode** solves this by using a second WiFi adapter to connect to the target device's AP while your Pi continues hosting its own AP on `wlan0`.

This allows you to:
1. Connect your phone/laptop to the Pi's AP (secure, known network)
2. Pi bridges traffic to/from the target device's AP
3. All traffic is captured and logged for analysis
4. You maintain full visibility and control over the communication

## Hardware Requirements

### Option 1: USB WiFi Adapter (Recommended)

Add a second WiFi interface using a USB adapter:

**Recommended adapters (Linux-friendly, monitor mode support):**
- **TP-Link Archer T2U Nano** (RTL8811AU chipset) — $10-15, compact
- **Panda Wireless PAU09** (Ralink RT5572) — $14, excellent Linux support
- **ALFA AWUS036ACH** (RTL8812AU) — $40, professional-grade, dual-band

**Avoid:** Broadcom-based adapters (poor Linux driver support)

Plug the adapter into any USB port on the Pi, then:

```bash
# Verify the adapter is detected
lsusb | grep -i wireless

# Check interface name (usually wlan1)
ip link show

# Expected output:
# 2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...  (Pi's built-in, hosting AP)
# 3: wlan1: <BROADCAST,MULTICAST> ...              (USB adapter, for bridge)
```

### Option 2: Pi Zero W as Wireless Bridge (Advanced)

Use a second Raspberry Pi Zero W as a dedicated wireless bridge:
- Pi 3: Hosts the main AP on `wlan0`
- Pi Zero W: Connects to target device AP, bridges via USB Ethernet

This is overkill for most use cases but provides maximum isolation.

## Network Topology

### Standard Mode (no bridge)
```
[ Your Laptop ]  ──WiFi──>  [ Pi wlan0 AP ]  ──eth0──>  [ Internet ]
```

### Bridge Mode
```
[ Your Laptop ]  ──WiFi──>  [ Pi wlan0 AP ]
                                   │
                                   │ (routing/NAT)
                                   │
                            [ Pi wlan1 client ]  ──WiFi──>  [ Target Device AP ]
                                                                   │
                                                            [ Target IoT Device ]
```

## Configuration

### 1. Enable Bridge Mode in Config

Edit `/mnt/isolator/conf/isolator.conf.yaml`:

```yaml
# ── Bridge Mode ──────────────────────────────────────────────────────────────
# Allows the Pi to connect to a target device's AP as a client on wlan1,
# while still hosting its own AP on wlan0.
# Requires a second WiFi adapter (USB recommended).

bridge:
  enabled: true
  client_interface: wlan1            # Interface to connect to target AP
  target_ap:
    ssid: "DroneController_ABC123"   # Target device's AP name
    password: "12345678"             # Password (if secured)
    # password: ""                   # Leave empty for open networks
  
  # Traffic routing
  route_to_internet: false           # If true, target device gets internet via eth0
                                     # If false, target is fully isolated (safer)
  
  # Capture settings for bridge traffic
  capture:
    enabled: true                    # Capture ALL traffic on wlan1
    output: /mnt/isolator/captures/bridge
    rotate_mb: 200
    live: true                       # Stream to /run/isolator/bridge.pipe
```

### 2. Apply Configuration

```bash
sudo systemctl reload isolator
```

The isolator service will:
1. Connect `wlan1` to the target AP using `wpa_supplicant`
2. Set up routing between `wlan0` (your network) and `wlan1` (target device)
3. Start tcpdump on `wlan1` to capture all bridge traffic
4. Apply nftables rules for isolation and logging

### 3. Verify Bridge is Active

```bash
# Check wlan1 connection status
iwconfig wlan1

# Should show:
# wlan1     IEEE 802.11  ESSID:"DroneController_ABC123"
#           Mode:Managed  Frequency:2.437 GHz  Access Point: XX:XX:XX:XX:XX:XX

# Test connectivity to target device
# (Assume target device has IP 192.168.43.1 on its own AP)
ping -c 3 192.168.43.1
```

## Use Cases

### Use Case 1: DJI Drone Controller Analysis

**Scenario:** You want to reverse engineer the DJI drone control protocol.

**Setup:**
1. Power on the drone and controller
2. Drone controller creates AP: `DJI-XXXXX`
3. Configure bridge mode:
   ```yaml
   target_ap:
     ssid: "DJI-XXXXX"
     password: ""  # DJI uses open AP initially
   route_to_internet: false  # Isolate drone from internet
   ```
4. Reload isolator: `sudo systemctl reload isolator`
5. Connect your laptop to Pi's AP
6. Access dashboard: `http://isolator.local:5006`
7. Monitor live traffic to the drone controller

**Analysis:**
- All drone telemetry and control packets are captured
- Use Wireshark to view live: `ssh -L 5006:localhost:5006 pi@isolator.local "cat /run/isolator/bridge.pipe" | wireshark -k -i -`
- Look for unencrypted protocols (MQTT, UDP, custom binary)

### Use Case 2: WiFi Camera Direct Connect

**Scenario:** Security camera offers "direct connect" mode for setup.

**Setup:**
1. Put camera in setup mode (creates its own AP)
2. Configure bridge:
   ```yaml
   target_ap:
     ssid: "Camera_Setup_ABCD"
     password: "12345678"  # Check camera manual
   route_to_internet: true  # Camera may need internet for firmware check
   ```
3. Connect your phone to Pi's AP
4. Phone app connects through Pi → camera
5. All setup traffic is captured and logged

**Analysis:**
- Capture initial pairing/authentication process
- Check if credentials are transmitted in plaintext
- Identify API endpoints and protocols used

### Use Case 3: Smart Home Hub Initial Setup

Many smart home hubs (Philips Hue, smart plugs, etc.) use temporary APs for setup.

**Setup:**
1. Reset device to factory mode
2. Device creates setup AP
3. Bridge mode captures the entire setup flow
4. Analyze how device joins your home network

## SSH Commands for Bridge Mode

### Start Live Wireshark Capture (from Windows)

```powershell
# Stream bridge traffic to Wireshark on your Windows machine
ssh pi@isolator.local "cat /run/isolator/bridge.pipe" | & "C:\Program Files\Wireshark\Wireshark.exe" -k -i -
```

### Download Bridge Captures

```bash
# Copy all bridge captures to your Windows machine
scp -r pi@isolator.local:/mnt/isolator/captures/bridge/ ./bridge-analysis/
```

### Check Bridge Status Remotely

```bash
# Check if bridge is connected
ssh pi@isolator.local "iwconfig wlan1 | grep ESSID"

# View bridge routing table
ssh pi@isolator.local "ip route show"

# Check bridge traffic stats
ssh pi@isolator.local "sudo iptables -L -v -n | grep wlan1"
```

### Manual Bridge Control

```bash
# Disable bridge temporarily (keep AP running)
ssh pi@isolator.local "sudo systemctl stop isolator-bridge"

# Re-enable bridge
ssh pi@isolator.local "sudo systemctl start isolator-bridge"

# Change target AP on the fly (edit config, then reload)
ssh pi@isolator.local "sudo nano /mnt/isolator/conf/isolator.conf.yaml"
ssh pi@isolator.local "sudo systemctl reload isolator"
```

## Security Considerations

### Isolation by Default

When `route_to_internet: false` (recommended):
- Target device is **fully isolated** from your home LAN and internet
- Only your laptop (connected to Pi AP) can reach the target
- Prevents malicious behavior from devices under analysis

### Internet Access (Use with Caution)

When `route_to_internet: true`:
- Target device can reach the internet via Pi's `eth0`
- Use only if device requires internet for initialization
- All traffic is still logged and can be blocked by nftables rules

### Access Control

```yaml
# Example: Allow specific outbound connections only
bridge:
  route_to_internet: true
  allowed_destinations:
    - host: "192.168.1.10"
      ports: [80, 443]  # NAS web interface only
```

## Troubleshooting

### Problem: wlan1 won't connect to target AP

**Check:**
1. Adapter is detected: `lsusb`
2. Driver is loaded: `lsmod | grep 8812`
3. Target SSID is visible: `sudo iwlist wlan1 scan | grep ESSID`
4. Password is correct in config

**Solution:**
```bash
# Manually test connection
sudo wpa_passphrase "TargetSSID" "password" > /tmp/wpa_test.conf
sudo wpa_supplicant -i wlan1 -c /tmp/wpa_test.conf
```

### Problem: Bridge routing not working

**Check routing table:**
```bash
ip route show
# Should see routes for both wlan0 and wlan1 subnets
```

**Check NAT rules:**
```bash
sudo iptables -t nat -L -v -n
```

### Problem: Capture not recording

**Check tcpdump process:**
```bash
ps aux | grep tcpdump | grep wlan1
```

**Check disk space:**
```bash
df -h /mnt/isolator
```

## Performance Impact

**CPU Usage:** Bridge mode adds ~5-10% CPU load on Pi 3 (packet forwarding + capture)

**Memory:** Minimal (~50MB additional for wpa_supplicant + tcpdump)

**WiFi Range:** USB adapters typically have better range/power than Pi's built-in WiFi

## Advanced: Dual-Band Bridge

Use a dual-band USB adapter to bridge between 2.4 GHz and 5 GHz:

```yaml
ap:
  band: "5GHz"    # Pi hosts AP on 5 GHz (if supported)

bridge:
  enabled: true
  client_interface: wlan1
  target_ap:
    ssid: "2.4GHz_Device_AP"  # Connect to 2.4 GHz target
```

This reduces interference and maximizes capture quality.

## Future Enhancements

- [ ] Auto-detect target APs and present selection UI
- [ ] Protocol analyzer integration (automatic MQTT/HTTP/CoAP detection)
- [ ] Man-in-the-middle proxy support for HTTPS inspection
- [ ] Multi-target bridge support (connect to multiple device APs)

## Recommended USB WiFi Adapters — Quick Reference

| Adapter | Chipset | Price | Dual-Band | Monitor Mode | Notes |
|---------|---------|-------|-----------|--------------|-------|
| TP-Link T2U Nano | RTL8811AU | $12 | No | Yes | Best value, compact |
| Panda PAU09 | RT5572 | $14 | No | Yes | Excellent Linux support |
| ALFA AWUS036ACH | RTL8812AU | $40 | Yes | Yes | Professional, long range |
| Realtek RTL8812BU | RTL8812BU | $25 | Yes | Yes | Good middle option |

All listed adapters work out-of-the-box with Raspberry Pi OS (kernel 5.10+).
