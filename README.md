# Pi Network Isolator

A Raspberry Pi 3 configured as a WiFi access point with per-device, policy-driven network isolation.

## What It Does

- Creates a secure WiFi AP on `wlan0`.
- Routes or isolates traffic to/from the upstream network via `eth0`.
- Applies per-device firewall rules (internet access, LAN reach, logging) driven by a single config file.
- Logs all WiFi client traffic at configurable verbosity.
- **Captures per-device pcap files** for Wireshark analysis — designed for reverse engineering unknown IoT devices (WiFi plugs, cameras, drone controllers, etc.).
- Streams live traffic to Wireshark on Windows via SSH pipe.

## Hardware Target

- Raspberry Pi 3 (Model B or B+)
- Raspberry Pi OS Lite 64-bit
- USB drive at `/mnt/isolator` (config + logs — same portability model as the music library Pi)

## Stack

| Component | Role |
|---|---|
| `hostapd` | WiFi AP (wlan0) |
| `dnsmasq` | DHCP + DNS for AP clients |
| `nftables` | Per-device firewall + traffic logging |
| `scripts/apply-rules.py` | Config → nftables ruleset generator |
| `systemd` unit `isolator.service` | Orchestrates startup and live reload |

## Quick Start (planned)

```bash
cd /path/to/NetworkIsolator
sudo bash server/setup-isolator.sh --config config/isolator.conf.yaml
```

## Config

Edit `config/isolator.conf.yaml` — see inline comments for all options.

Live reload without dropping connections:

```bash
sudo systemctl reload isolator
```

## Docs

- [docs/DEVICE-ACCESS-MODEL.md](docs/DEVICE-ACCESS-MODEL.md) — how access rules work, rule semantics, nftables flow.
- [docs/REVERSE-ENGINEERING.md](docs/REVERSE-ENGINEERING.md) — capturing and analysing unknown IoT device traffic with tcpdump, tshark, and Wireshark.

## Phase Path

| Phase | Goal |
|---|---|
| 1 | Config schema + device access model (current) |
| 2 | Setup script: hostapd + dnsmasq + nftables on Pi OS |
| 3 | `apply-rules.py` — config → live nftables rules |
| 4 | Optional: lightweight web UI for live device view + rule edits |
| 5 | Yocto image for true appliance deploy |
