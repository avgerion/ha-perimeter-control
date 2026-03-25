# Reverse Engineering WiFi Devices

This guide covers using the Pi Isolator to analyse unknown IoT devices:
cheap WiFi plugs, cameras, drone controller apps, and similar commodity products.

## Why This Works

Because the Pi is the AP, **all WiFi traffic passes through it before reaching the
internet**. You are in a privileged position — a true man-in-the-middle for
devices you own and are testing. No ARP spoofing or special modes needed.

> **Legal note:** Only analyse devices you own or have explicit written permission
> to test. Traffic capture of third-party devices without authorization is
> illegal in most jurisdictions.

---

## Toolchain

| Tool | Role | Installed on |
|---|---|---|
| `tcpdump` | Packet capture to pcap or named pipe | Pi |
| `tshark` | CLI Wireshark — dissect, filter, export | Pi or Windows |
| Wireshark | GUI analysis | Windows laptop |
| `nftables` | Logs connection metadata | Pi |
| `dnsmasq` | Logs DNS queries per device | Pi |
| `mitmproxy` | Optional: intercept HTTP/HTTPS | Pi (Phase 4) |

---

## Step-by-Step: First Look at an Unknown Device

### 1. Add the device to config

Find the device MAC after it connects (check dnsmasq lease log or ARM UI):

```bash
cat /var/lib/misc/dnsmasq.leases
# or
sudo journalctl -u dnsmasq | tail -30
```

Add a profile in `config/isolator.conf.yaml`:

```yaml
- id: "wifi-plug-01"
  mac: "de:ad:be:ef:00:01"          # actual MAC from leases
  name: "Generic WiFi Plug"
  static_ip: "192.168.50.200"
  internet: log-only                 # let it reach internet so app works
  lan_access: []
  logging: full
  capture:
    enabled: true
    filter: ""                       # all traffic
    output: "/mnt/isolator/captures/wifi-plug-01"
    rotate_mb: 100
    live: true
```

Reload:

```bash
sudo systemctl reload isolator
```

### 2. Watch DNS queries in real time

DNS tells you what servers the device is phoning home to before you even look
at pcap:

```bash
sudo journalctl -u dnsmasq -f | grep "wifi-plug-01\|192.168.50.200"
```

### 3. Capture to pcap file (write and analyse later)

```bash
sudo tcpdump -U -n -s 65535 \
  -i wlan0 \
  "ether host de:ad:be:ef:00:01" \
  -w /mnt/isolator/captures/wifi-plug-01/$(date +%Y%m%d-%H%M%S).pcap
```

Copy the pcap to Windows and open in Wireshark:

```powershell
# From Windows PowerShell
scp pi@<pi-ip>:/mnt/isolator/captures/wifi-plug-01/*.pcap C:\Captures\
```

### 4. Live capture directly into Wireshark on Windows

Wireshark can read from an SSH-piped tcpdump stream in real time.

**Option A — SSH pipe (simplest):**

In Windows PowerShell (requires Wireshark in PATH):

```powershell
ssh pi@<pi-ip> "sudo tcpdump -U -n -s 65535 -w - -i wlan0 'ether host de:ad:be:ef:00:01'" | wireshark -k -i -
```

**Option B — named pipe on the Pi (pre-configured via `live: true` in config):**

The isolator creates `/run/isolator/wifi-plug-01.pipe`. On the Pi:

```bash
tshark -i /run/isolator/wifi-plug-01.pipe
```

Or read it from Windows via the SSH pipe above pointing at the named pipe instead.

---

## What to Look For

### Unencrypted protocols (easy wins)

Many cheap IoT devices use plain HTTP or custom UDP/TCP protocols:

- Look for `HTTP` in Wireshark's Protocol column.
- Filter: `http || http2 || dns || udp`
- Find control commands: look for short, repeated UDP datagrams to a fixed IP.

### Finding the control server

1. Filter DNS: `dns.qry.name` — shows every hostname the device looked up.
2. Note the IPs those names resolved to.
3. Filter by those IPs: `ip.addr == x.x.x.x`

### Identifying the protocol

| Pattern | Likely protocol |
|---|---|
| Short UDP bursts on port 8888/9999/6666 | Custom binary control protocol |
| TCP port 80/8080 to a cloud IP | HTTP REST API — inspect with `Follow TCP Stream` |
| TCP port 443 | TLS — see section below |
| UDP port 5353 | mDNS — device advertising itself locally |
| TCP port 1883 | MQTT (unencrypted IoT messaging) |
| TCP port 8883 | MQTT over TLS |

### Drone/PTZ controller apps

These often use UDP on high ports (e.g., 8889 for MAVLink, 11111 for video streams).
Filter:

```
udp.port >= 8000 && udp.port <= 12000
```

Then `Follow UDP Stream` to see the raw bytes or ASCII command structure.

---

## TLS / Encrypted Traffic

If the device uses HTTPS or TLS, raw capture only shows the handshake
(certificate, server name via SNI). You can still learn:

- **Server name** from TLS SNI: Wireshark column `tls.handshake.extensions_server_name`
- **Certificate details**: who issued it, what org, expiry — often reveals the OEM
- **Cipher suite and TLS version**: weak suites (TLS 1.0, RC4) signal cheap firmware

To intercept TLS (Phase 4 — optional):

- Run `mitmproxy` on the Pi as a transparent proxy.
- Install mitmproxy's CA cert on the target device (only works if the app doesn't pin certs).
- If the app does certificate pinning, this approach won't work without patching the APK.

---

## Exporting Data for Analysis

### Export to JSON (for scripting)

```bash
tshark -r capture.pcap -T json > capture.json
```

### Extract all HTTP requests

```bash
tshark -r capture.pcap -Y http.request -T fields \
  -e frame.time -e ip.src -e ip.dst \
  -e http.request.method -e http.request.uri \
  -e http.user_agent
```

### Extract all DNS queries

```bash
tshark -r capture.pcap -Y dns.flags.response==0 -T fields \
  -e frame.time -e ip.src -e dns.qry.name
```

### Reconstruct a UDP stream (binary protocol)

```bash
tshark -r capture.pcap -Y "udp.stream eq 0" -T fields \
  -e frame.time -e data.data | xxd
```

---

## Workflow Summary

```
Device connects to isolator AP
        │
        ▼
dnsmasq logs assigned IP + MAC
        │
        ▼
Add device entry to isolator.conf.yaml (internet: log-only, capture: enabled)
        │
        ▼
sudo systemctl reload isolator
        │
        ├──► DNS log → what hostnames is it resolving?
        ├──► nftables log → what IPs/ports is it connecting to?
        └──► tcpdump/Wireshark → full packet analysis
                │
                ├──► Unencrypted? → read protocol directly
                ├──► TLS? → SNI + cert tells you who it calls
                └──► Custom UDP? → stream follow + hex decode
```

---

## Useful Wireshark Display Filters

```
# All traffic from target device
ip.addr == 192.168.50.200

# Exclude AP management traffic
ip.addr == 192.168.50.200 && !arp && !icmp

# DNS only
dns

# Non-TLS TCP (likely plaintext)
tcp && !tls

# HTTP requests
http.request

# Short UDP bursts (typical control protocol)
udp && frame.len < 200

# TLS server names
tls.handshake.type == 1
```
