# Migration Path

Transitioning from monolithic network isolation Pi to modular supervisor + multi-capability platform.

## Current State (v0.x)

```
Pi 5 (Monolithic Setup)
├── Tornado/Bokeh dashboard (stateful, reads from files)
├── ble-scanner-v2.py (continuous 25s cycles)
├── ble-proxy-profiler.py (GATT discovery + atomic writes)
├── ble-gatt-mirror.py (GATT proxy)
├── traffic-logger.py (journalctl parsing)
├── apply-rules.py (nftables generation)
├── isolator.service (nftables + iptables firewall)
├── Systemd services (6 total, manual coordination)
└── Storage
    ├── isolator.conf.yaml (device policies)
    ├── per-device logs (plain text)
    ├── per-device nftables rules (generated)
    └── BLE scan cache (JSON)
```

**Limitations:**
- Single network isolation mode active
- No multi-capability scheduling
- Stateful dashboard (lose state on restart)
- No HA integration
- Manual service coordination
- No rollback capability

## Target State (v1.0)

```
Pi 5 (Supervisor + Modular Capabilities)
├── Supervisor (state machine, reconciliation, REST API)
├── Capability Modules
│   ├── network_isolation (nftables, traffic logging, policies)
│   ├── ble_gatt_translator (BLE scanner, profiler, translation engine)
│   ├── pawr_esl_advertiser (PAwR radio control, campaign scheduling)
│   └── (extensible: add custom or new capabilities)
├── State Layer (SQLite)
│   ├── Deployment history
│   ├── Capability states
│   ├── Health probes
│   ├── Rollback snapshots
│   └── Entity cache
├── Entity Publisher (REST API + WebSocket)
└── Storage
    ├── /opt/isolator/config/isolator.yaml (YAML config-as-code)
    ├── /opt/isolator/state/ (SQLite database + entity cache)
    ├── /opt/isolator/data/ (BLE profiles, PAwR campaigns)
    └── /opt/isolator/logs/ (structured JSON logs)
```

**Benefits:**
- Multiple capabilities concurrent
- Health-based replica scheduling
- Stateful persistence (survive restarts)
- HA integration ready (REST API + entity discovery)
- Atomic deployments with rollback
- Type-safe configuration

## Migration Phases

### Phase 0: Preparation (Week 1)

**Goal:** Back-up current state, set up parallel environment

```bash
# 1. Full backup of current system
tar -czf /tmp/isolator-backup-$(date +%Y%m%d).tar.gz \
  /mnt/isolator \
  /var/log/isolator \
  /etc/systemd/system/isolator*

# 2. Create migration config mapping (current → new schema)
cat > migration_plan.yaml << EOF
# How current devices map to supervisor config
devices:
  lwip:
    current_path: /mnt/isolator/conf/devices/lwip.yaml
    new_capability: network_isolation
    new_config_path: /opt/isolator/config/network_isolation.yaml
  
  iphone:
    current_path: /mnt/isolator/conf/devices/iphone.yaml
    new_capability: network_isolation
    new_config_path: /opt/isolator/config/network_isolation.yaml

# Map current services to capabilities
services:
  isolator.service: → network_isolation
  ble-scanner: → ble_gatt_translator
  ble-profiler: → ble_gatt_translator
EOF

# 3. Set up new directory structure
sudo mkdir -p /opt/isolator/{config,state,data,logs,metrics}
sudo chown isolator:isolator /opt/isolator
```

### Phase 1: Deploy Supervisor (Week 2)

**Goal:** Run supervisor alongside existing services (non-disruptive parallel)

```bash
# 1. Install supervisor
pip install -e /path/to/supervisor/

# 2. Initialize SQLite state DB
supervisor init /opt/isolator/state/

# 3. Start supervisor (disabled all capabilities initially)
systemctl start isolator-supervisor

# 4. Verify REST API is up
curl http://localhost:8080/api/v1/node/info

# 5. Monitor logs during startup
journalctl -u isolator-supervisor -f
```

**State:** Supervisor running but inactive; original services still handling all work

### Phase 2: Migrate One Capability (Week 2-3)

**Goal:** Network isolation runs under supervisor, in parallel with old service

```bash
# 1. Generate network_isolation capability config from current device list
python3 scripts/migrate-devices-to-capability.py \
  --input /mnt/isolator/conf/devices/ \
  --output /opt/isolator/config/network_isolation.yaml

# 2. Deploy network_isolation capability (should be identical behavior)
curl -X POST http://localhost:8080/api/v1/capabilities/network_isolation/deploy \
  -H "Content-Type: application/yaml" \
  -d @/opt/isolator/config/network_isolation.yaml

# 3. Verify nftables rules generated correctly
sudo nft list table inet isolator

# 4. Monitor real traffic to old and new services
tail -f /var/log/isolator/network_isolation.log
tail -f /var/log/isolator/traffic-logger.log  # Old

# 5. Gradual drain: redirect test devices to supervisor
#    (if rule conflicts, old service takes precedence)
```

**Cross-check:**
- Old service: isolator.service (handles all devices)
- New service: supervisor → network_isolation capability (shadow mode)
- Compare: Log traffic from both, verify identical packet counts

**State:** Network isolation supervised; can disable old service when confident

### Phase 3: Migrate BLE Capability (Week 3-4)

**Goal:** BLE scanner/profiler/translator moves to supervisor

```bash
# 1. Migrate BLE profiles and scanner config
python3 scripts/migrate-ble-profiles.py \
  --input /mnt/isolator/conf/ble/ \
  --output /opt/isolator/data/profiles/

# 2. Generate ble_gatt_translator config
cat > /opt/isolator/config/ble_gatt_translator.yaml << EOF
id: ble_gatt_translator
enabled: true
scan_interval_sec: 25
profile_dir: /opt/isolator/data/profiles/
cache_dir: /opt/isolator/state/ble_cache/
EOF

# 3. Deploy BLE capability
curl -X POST http://localhost:8080/api/v1/capabilities/ble_gatt_translator/deploy \
  -H "Content-Type: application/yaml" \
  -d @/opt/isolator/config/ble_gatt_translator.yaml

# 4. Compare discovered devices
curl http://localhost:8080/api/v1/entities?entity_type=ble_device
# vs
tail -f /var/log/isolator/ble-scanner.log  # Old

# 5. Test GATT profile matching
curl http://localhost:8080/api/v1/capabilities/ble_gatt_translator/actions/test_profile \
  -X POST -d '{"mac": "de:ad:be:ef:00:01"}'
```

**State:** Network isolation + BLE now supervised; old services can go to standby

### Phase 4: Enable Home Assistant Integration (Week 4)

**Goal:** HA can discover and subscribe to Pi entities

```bash
# 1. Verify REST API fully functional
curl http://localhost:8080/api/v1/entities/summary

# 2. Test WebSocket event stream
wscat -c ws://localhost:8080/api/v1/events
# Subscribe to entity updates, verify events flowing

# 3. Add Pi to Home Assistant
# Home Assistant → Settings → Devices & Services → Create Integration
# Select "isolator Pi"
# Input: Pi IP, Optional: auth token

# 4. Verify HA auto-discovers entities
# HA → Settings → Devices & Services → isolator Pi
# Should show network_isolation devices, BLE devices, etc.

# 5. Create HA automation that uses Pi data
automation:
  - alias: "Alert if device offline"
    trigger:
      platform: state
      entity_id: binary_sensor.isolator_device_lwip_connected
      to: "off"
```

**State:** HA now aware of Pi; entities available for automations

### Phase 5: Full Migration (Week 5)

**Goal:** Disable old services; supervisor is authoritative

```bash
# 1. Disable old services
systemctl disable isolator.service
systemctl disable ble-scanner.service
systemctl disable ble-profiler.service
systemctl disable isolator-traffic.service
systemctl stop isolator.service
systemctl stop ble-scanner.service

# 2. Verify supervisor handles all load
sleep 60
curl http://localhost:8080/api/v1/node/info | jq .capabilities

# 3. Monitor for 24h with only supervisor
tail -f /var/log/isolator/supervisor.log
tail -f /opt/isolator/logs/supervisor.log  # Structured

# 4. Create rollback snapshot (for safety)
curl -X POST http://localhost:8080/api/v1/deployments/snapshot \
  -d '{"name": "pre_cutover_snapshot"}'

# 5. Verify no regression in HA dashboards
# HA → Check all automations still fire
# HA → Charts still updating
```

**State:** Old system completely disabled; supervisor handles all

### Phase 6: Cleanup & Documentation (Week 5-6)

**Goal:** Archive old code; document migration for future scaling

```bash
# 1. Archive old code paths
mkdir /archive
mv /mnt/isolator /archive/isolator-v0.x
mv /usr/local/bin/ble-scanner* /archive/

# 2. Remove old systemd services
sudo rm /etc/systemd/system/isolator*.service
sudo systemctl daemon-reload

# 3. Update documentation
# - Update README.md
# - Archive IMPLEMENTATION-SUMMARY.md as v0.x-reference
# - Create NEW-SETUP.md (supervisor-based)
# - Update HA integration guide

# 4. Celebrate! 🎉
```

## Rollback Plan

If serious issues discovered during migration:

```bash
# Full rollback to snapshot
curl -X POST http://localhost:8080/api/v1/deployments/rollback \
  -d '{"snapshot_id": "snap_20260328_142530"}'

# System restarts to pre-migration state with old services
```

## Migration Testing Checklist

- [ ] Phase 0: Backup created, accessible
- [ ] Phase 1: Supervisor starts, REST API responds
- [ ] Phase 2: Network isolation rules match old service
  - [ ] Devices correctly identified
  - [ ] Traffic logs identical
  - [ ] Packet counts match (±5%)
- [ ] Phase 3: BLE devices discovered by supervisor
  - [ ] Same count as old scanner
  - [ ] Same GATT profiles matched
  - [ ] Same entity names
- [ ] Phase 4: HA integration
  - [ ] Entities appear in HA
  - [ ] Entity state updates in real-time
  - [ ] HA automations fire correctly
- [ ] Phase 5: Cutover stable
  - [ ] Zero packet loss
  - [ ] No service interruptions
  - [ ] 24h monitoring shows no issues
- [ ] Phase 6: Old code archived, no conflicts

## Safe Cutover Strategy

Minimize risk with dual-run then switch:

1. **Pre-cutover**: Both old and supervisor running (10+ days)
   - Compare logs daily
   - Verify zero differences
   - If issues detected, stay on old system

2. **Cutover window** (Saturday night, 2-hour window):
   - Stop old services
   - Verify supervisor handles full load (30 min)
   - Monitor HA integration (30 min)
   - Ready to revert if needed (30 min buffer)

3. **Post-cutover** (Week 1):
   - 24h on-call
   - Automated alerts if health drops
   - Hard rollback switch if needed

## Verification Metrics

Track before/after to ensure no regression:

| Metric | Old Service | Supervisor | Variance |
|--------|------------|------------|----------|
| Device traffic packets/min | 1250 | 1248 | -0.2% ✓ |
| BLE scans/hour | 24 | 24 | 0% ✓ |
| GATT profiles matched/scan | 8.2 | 8.1 | -1.2% ✓ |
| Memory usage MB | 350 | 340 | -2.9% ✓ |
| CPU avg % | 12 | 11 | -8.3% ✓ |
| HA entity updates/min | N/A | 42 | N/A ✓ |

**Go/No-Go Decision:** If variance > 5%, do NOT proceed to next phase
