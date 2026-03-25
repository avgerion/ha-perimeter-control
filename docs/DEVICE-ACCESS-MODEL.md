# Device Access Model

This document describes how the isolator applies access rules from `config/isolator.conf.yaml`.

## Network Topology

```
[ WiFi Clients ]
      |
   [ wlan0 ]  ←── AP (192.168.50.0/24), hosted on the Pi
      |
   [ Pi 3 ]   ←── nftables enforces all rules here
      |
   [ eth0 ]   ←── WAN (upstream LAN or router, separate subnet)
      |
[ Upstream LAN / Internet ]
```

## Device Identification

Devices are matched in this priority order:

1. **MAC address** — most reliable; identifies the hardware NIC regardless of hostname or IP.
2. **Static IP reservation** — if `static_ip` is set, dnsmasq assigns that IP to the MAC; nftables rules bind to the IP.
3. **Name** — informational only; used in log output, not for rule matching.

If a device is not listed in `devices[]`, the `default_policy` applies.

## Access Rule Semantics

### `internet: allow | deny | log-only`

| Value | Effect |
|---|---|
| `allow` | Device may initiate connections to any IP outside the LAN subnet via eth0. |
| `deny` | All outbound traffic to WAN dropped (ICMP unreachable returned). |
| `log-only` | Traffic is forwarded but every packet is logged — useful for auditing. |

### `lan_access: []` or list of `{host, ports}`

Each entry permits TCP/UDP to a specific upstream host on specific ports only.

```yaml
lan_access:
  - host: "192.168.1.10"   # NAS
    ports: [445, 22]        # SMB + SSH only
```

Empty list (`[]`) means no access to the upstream LAN at all (not even ping).

### `logging: none | metadata | full`

| Value | What is logged |
|---|---|
| `none` | Nothing |
| `metadata` | 5-tuple: src_ip, src_port, dst_ip, dst_port, protocol, timestamp, verdict |
| `full` | Metadata + payload (first N bytes). Use only for short-term debugging. |

## nftables Rule Generation (planned)

The config file is parsed by `scripts/apply-rules.py` which:

1. Reads `isolator.conf.yaml`.
2. Generates a `nftables` ruleset in `/etc/nftables.d/isolator.nft`.
3. Calls `nft -f /etc/nftables.d/isolator.nft` to apply atomically.
4. Calls `nft -f /etc/nftables.d/isolator.nft` on any config file change (inotify watch or `systemctl reload isolator`).

## Access Decision Flowchart

```
Packet arrives on wlan0
        │
        ▼
Is source MAC in devices[]?
   ├── No  → apply default_policy
   └── Yes → load device rules
              │
              ▼
        Is dst in upstream LAN?
           ├── Yes → is there a matching lan_access rule?
           │           ├── Yes → ALLOW + log(device.logging)
           │           └── No  → DROP  + log(metadata)
           └── No  → is dst Internet (beyond eth0)?
                       ├── internet: allow   → ALLOW + log
                       ├── internet: log-only→ ALLOW + log(full)
                       └── internet: deny    → DROP  + log(metadata)
```

## Config Live Reload

Any change to `isolator.conf.yaml` can be applied without dropping existing sessions:

```bash
sudo systemctl reload isolator
```

The reload script regenerates the nftables ruleset, which `nft` applies atomically — existing established connections are preserved.

## Future: Web UI

A lightweight web UI (planned, FastAPI + HTMX) will:
- Show connected devices (live, from dnsmasq leases + nftables counters).
- Display recent log entries per device.
- Allow editing device rules, which writes back to `isolator.conf.yaml` and triggers reload.
