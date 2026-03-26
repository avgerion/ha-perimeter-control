# BLE Sniffing Guide

## Overview

The Network Isolator includes built-in Bluetooth Low Energy (BLE) sniffing capabilities for capturing and analyzing BLE communication between IoT devices and mobile apps. This is particularly useful when devices use BLE for initial setup/provisioning.

## Dashboard UI

The easiest way to capture BLE traffic is through the **BLE Traffic Sniffer** panel in the web dashboard at http://localhost:5006

### Using the Dashboard

1. **Navigate** to the BLE Traffic Sniffer section (bottom of the dashboard)
2. **Enter target device**:
   - Type device name in "Target Device Name" field, OR
   - Type MAC address in "Target MAC Address" field
   - Leave both empty to capture all BLE traffic
3. **Select duration**: Choose capture time (1-60 minutes)
4. **Click "🟢 Start Capture"** to begin
5. **Status indicator** shows active captures and PID
6. **Click "🛑 Stop Capture"** when done (or wait for duration to complete)

### Viewing Captures

After capturing:
1. **Select a capture** from the "View Capture Session" dropdown
2. **Filter events** by type (advertisement, connection, GATT read/write)
3. **Timeline plot** shows event distribution over time
4. **Event log table** displays detailed information:
   - Timestamp
   - Event type
   - Device address
   - Device name
   - GATT handle (for read/writes)
   - Additional info

The dashboard auto-refreshes every 3 seconds to show new events and available captures.

## Command Line Usage

### 1. Start BLE Capture (via CLI)

```bash
# Capture all BLE traffic
sudo python3 /opt/isolator/scripts/ble-sniffer.py

# Capture specific device by name
sudo python3 /opt/isolator/scripts/ble-sniffer.py --target "MyDevice"

# Capture specific device by MAC
sudo python3 /opt/isolator/scripts/ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF

# Capture for 5 minutes
sudo python3 /opt/isolator/scripts/ble-sniffer.py --target "MyDevice" --duration 300
```

### 2. Output Files

Captures are saved in multiple formats:

- **btsnoop format**: `/mnt/isolator/captures/ble/{device}_{timestamp}.btsnoop`
  - Standard Bluetooth packet capture format
  - Can be opened in Wireshark for detailed analysis
  
- **Human-readable log**: `/var/log/isolator/ble/{device}_{timestamp}.log`
  - Raw btmon output with all events
  
- **JSON structured**: `/var/log/isolator/ble/{device}_{timestamp}.json`
  - Machine-parsable format with key events
  - Advertisements, connections, GATT operations

## Use Cases

### IoT Device Provisioning

Many IoT devices use BLE for initial setup:

1. **Start BLE capture** before opening the mobile app
2. **Open the app** and go through device setup
3. **Stop capture** after setup completes
4. **Analyze** the captured data to understand the provisioning protocol

### Typical BLE Setup Flow

```
Phone → Device: BLE Advertisement Scan
Device → Phone: ADV_IND (device name, services)
Phone → Device: Connect Request
Device → Phone: Connection Complete
Phone ↔ Device: Service Discovery (GATT)
Phone → Device: Write (WiFi credentials)
Device → Phone: Notification (status)
```

### What You Can Capture

- **Device Advertisements**: Name, manufacturer data, service UUIDs
- **Connection Parameters**: Intervals, latency, supervision timeout
- **Service Discovery**: All GATT services and characteristics
- **Data Transfers**: Reads, writes, notifications
- **Pairing/Bonding**: Security procedures (encrypted data will appear encrypted)

## Analyzing Captures

### Using Wireshark

```bash
# Copy btsnoop file to your PC
scp pi@isolator.local:/mnt/isolator/captures/ble/*.btsnoop ./

# Open in Wireshark
wireshark device_20260326_153045.btsnoop
```

**Useful Wireshark Filters:**
```
btl2cap                    # All L2CAP packets
btatt                      # GATT attribute protocol
btatt.opcode == 0x12       # Write requests
btatt.value                # Show attribute values
bluetooth.addr == aa:bb:cc:dd:ee:ff  # Filter by device
```

### Parsing JSON Logs

```python
import json

with open('/var/log/isolator/ble/device_20260326_153045.json') as f:
    for line in f:
        event = json.loads(line)
        if event['type'] == 'advertisement':
            print(f"Device: {event['data'].get('name')}")
            print(f"  MAC: {event['data'].get('address')}")
```

## Common BLE Services

When analyzing captures, look for these standard services:

- **0x1800**: Generic Access (device name, appearance)
- **0x1801**: Generic Attribute
- **0x180A**: Device Information (manufacturer, model, firmware)
- **0x180F**: Battery Service

IoT devices often use custom UUIDs (128-bit) for proprietary services like WiFi provisioning.

## Tips for Successful Captures

### 1. Timing is Critical

Start capture **before** initiating any action:
```bash
# Terminal 1: Start capture
sudo python3 ble-sniffer.py --target "MyDevice"

# Terminal 2: After capture starts
# Now open your app and start setup
```

### 2. Reduce Noise

If capturing in a crowded BLE environment:
```bash
# Filter by target to reduce file size
sudo python3 ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF
```

### 3. Multiple Captures

Do multiple runs to ensure consistency:
```bash
for i in {1..3}; do
    echo "Capture run $i"
    sudo python3 ble-sniffer.py --target "MyDevice" --duration 180
    echo "Reset device and press Enter for next run"
    read
done
```

### 4. Know What to Look For

Common patterns in IoT provisioning:
- **WiFi Credentials**: Often sent as plain text or base64
- **Custom Characteristics**: Look for 128-bit UUIDs
- **Write-then-Notify**: Phone writes config, device notifies status
- **Multi-step Process**: Multiple writes with sequence numbers

## Integration with Network Isolator

### Workflow: Complete Device Analysis

```bash
# 1. Start BLE capture for provisioning
sudo python3 ble-sniffer.py --target "TempSensor" --duration 300 &

# 2. Start WiFi packet capture
# (device will join WiFi AP after BLE setup)

# 3. Provision device via mobile app
# - BLE sniffer captures credential exchange
# - Device joins WiFi AP
# - WiFi sniffer captures network traffic

# 4. Analyze both captures together to understand:
#    - How credentials are sent (BLE)
#    - What the device does after connecting (WiFi)
```

## Troubleshooting

### Bluetooth Interface Down

```bash
sudo hciconfig hci0 up
sudo systemctl restart bluetooth
```

### Permission Denied

BLE sniffing requires root:
```bash
sudo python3 ble-sniffer.py ...
```

### No Devices Found

Check Bluetooth is working:
```bash
# Scan for devices
sudo hcitool lescan

# Check interface status
hciconfig -a
```

### btmon Not Found

Install BlueZ tools:
```bash
sudo apt install bluez
```

## Security Considerations

### BLE Encryption

Modern BLE uses pairing and encryption:
- **Unencrypted**: Advertisements, public data
- **Encrypted**: Most data after pairing

You can capture encrypted traffic but won't see plaintext without the encryption keys. Look for:
- Pairing methods (Just Works, Passkey Entry, etc.)
- Security level negotiation
- Out-of-band data exchanges

### Legal and Ethical

- Only sniff devices you own
- Don't capture BLE traffic in public spaces without consent
- Check local regulations on wireless monitoring

## Advanced: Live Monitoring Dashboard

You can monitor BLE captures in real-time by tailing the JSON log:

```bash
tail -f /var/log/isolator/ble/device_*.json | jq .
```

Or create a simple monitor:

```python
import json, time
from pathlib import Path

log_dir = Path('/var/log/isolator/ble')
latest = max(log_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)

with open(latest) as f:
    f.seek(0, 2)  # Go to end
    while True:
        line = f.readline()
        if line:
            event = json.loads(line)
            print(f"[{event['type']}] ", end='')
            if event['type'] == 'advertisement':
                print(f"Device: {event['data'].get('name', 'Unknown')}")
            elif event['type'] == 'gatt_write':
                print(f"Write to handle {event['data'].get('handle')}")
        time.sleep(0.1)
```

## Example: WiFi Device Provisioning

### Captured Flow

```
[13:45:23] BLE Advertisement: Name="SmartPlug-A1B2"
[13:45:25] Connection Established
[13:45:26] Service Discovery:
           - Generic Access (0x1800)
           - Device Info (0x180A)
           - WiFi Provisioning (custom UUID)
[13:45:30] GATT Write → Handle 0x2A (SSID): "MyHomeNetwork"
[13:45:31] GATT Write → Handle 0x2B (Password): "MyPassword123"
[13:45:32] GATT Write → Handle 0x2C (Command): 0x01 (connect)
[13:45:35] GATT Notification ← Handle 0x2D: 0x00 (success)
[13:45:36] Disconnection
```

### Analysis

From this capture, you know:
1. Device name format: `SmartPlug-XXXX`
2. WiFi config sent in plaintext
3. Three separate characteristics for SSID, password, and command
4. Success/failure reported via notification

You can now:
- Script automated provisioning
- Test edge cases (long SSIDs, special characters)
- Understand error codes
- Build custom control tools

## Next Steps

- Read [REVERSE-ENGINEERING.md](REVERSE-ENGINEERING.md) for WiFi analysis
- Combine BLE + WiFi captures for complete device understanding
- Use [Wireshark documentation](https://www.wireshark.org/docs/)
- Check [BLE specification](https://www.bluetooth.com/specifications/specs/)
