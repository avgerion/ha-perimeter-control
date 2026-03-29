# State Persistence & Storage

The Pi stores configuration, entity state, deployment history, and metrics persistently for restart safety and observability.

## Directory Structure

```
/opt/isolator/
├── config/
│   ├── node.yaml                    # Node identity and metadata (generated once)
│   ├── supervisor.yaml              # Supervisor runtime config
│   └── capabilities/
│       ├── network_isolation.yaml
│       ├── ble_gatt_translator.yaml
│       ├── pawr_esl_advertiser.yaml
│       └── (custom capabilities)
│
├── state/
│   ├── supervisor.db                # SQLite: main state store
│   ├── entity_cache.json            # Last known entity states (JSON)
│   ├── deployment_history.jsonl     # Deployment records (newline-delimited JSON)
│   └── rollback_snapshots/
│       ├── snapshot_001.tar.gz      # Compressed config + state snapshot
│       ├── snapshot_002.tar.gz
│       └── snapshot_003.tar.gz
│
├── data/
│   ├── profiles/                    # BLE device profiles (user-authored)
│   ├── translations/                # GATT translations (device-specific)
│   └── esl/                         # PAwR/ESL campaign templates
│
├── logs/
│   ├── supervisor.log               # Main supervisor log (rotated)
│   ├── ble.log                      # BLE runtime log
│   ├── traffic.log                  # Network traffic log
│   └── pawr.log                     # PAwR advertiser log
│
└── metrics/
    ├── supervisor_metrics.jsonl     # Hourly rollup (CPU, RAM, uptime)
    ├── ble_metrics.jsonl            # BLE session metrics
    └── traffic_metrics.jsonl        # Network traffic statistics
```

## SQLite Schema (supervisor.db)

Central state database with audit trail:

```sql
-- Deployments
CREATE TABLE deployments (
    id TEXT PRIMARY KEY,
    timestamp DATETIME,
    correlation_id TEXT,
    requested_state JSONB,
    executed_plan JSONB,
    status TEXT,  -- pending, applying, failed, succeeded, rolled_back
    error_message TEXT,
    duration_ms INTEGER
);

-- Capability state
CREATE TABLE capabilities (
    id TEXT PRIMARY KEY,
    name TEXT,
    version TEXT,
    status TEXT,  -- inactive, validating, planning, deploying, active, degraded, failed
    health TEXT,  -- ok, warn, degraded, failed
    config JSONB,
    last_updated DATETIME,
    last_health_check DATETIME
);

-- Health probes
CREATE TABLE health_probes (
    id INTEGER PRIMARY KEY,
    capability_id TEXT,
    probe_name TEXT,
    status TEXT,  -- ok, failed
    message TEXT,
    timestamp DATETIME,
    FOREIGN KEY (capability_id) REFERENCES capabilities(id)
);

-- Rollback snapshots
CREATE TABLE rollback_snapshots (
    id TEXT PRIMARY KEY,
    deployment_id TEXT,
    timestamp DATETIME,
    config_hash TEXT,
    archive_path TEXT,
    capabilities JSONB,  -- serialized all capability states at snapshot time
    is_active BOOLEAN,
    created_at DATETIME,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);

-- Entity state history (optional, for HA metrics)
CREATE TABLE entity_state_history (
    id INTEGER PRIMARY KEY,
    entity_id TEXT,
    state TEXT,
    timestamp DATETIME,
    capability_id TEXT,
    correlation_id TEXT
);

-- Configuration audit log
CREATE TABLE config_changes (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    change_type TEXT,  -- created, updated, deleted
    capability_id TEXT,
    old_config JSONB,
    new_config JSONB,
    changed_by TEXT,  -- "user", "ha_integration", "auto_recover", etc.
    correlation_id TEXT
);
```

## Entity Cache (entity_cache.json)

Lightweight snapshot of last known entity states (for fast HA reconnect):

```json
{
  "timestamp": "2026-03-28T10:30:00Z",
  "entities": {
    "traffic_logger_running": {
      "state": true,
      "last_updated": "2026-03-28T10:29:50Z",
      "friendly_name": "Traffic Logger"
    },
    "device_traffic:moto_g_2025:allowed_packets": {
      "state": 1247,
      "unit_of_measurement": "packets",
      "last_updated": "2026-03-28T10:29:55Z"
    },
    "ble_device:kitchen_scale:battery_percent": {
      "state": 85,
      "last_updated": "2026-03-28T10:25:30Z"
    }
  }
}
```

On startup, supervisor can seed these values immediately so HA doesn't see stale/empty until first sync.

## Deployment History (deployment_history.jsonl)

Append-only newline-delimited JSON for audit trail:

```json
{"timestamp":"2026-03-28T10:00:00Z","deployment_id":"dep_001","correlation_id":"cid_abc123","action":"deploy","capabilities":["network_isolation","ble_gatt_translator"],"status":"succeeded","duration_ms":5000}
{"timestamp":"2026-03-28T09:45:00Z","deployment_id":"dep_002","correlation_id":"cid_def456","action":"redeploy","capability":"ble_gatt_translator","status":"failed","error":"service_timeout","rollback_id":"snap_003"}
{"timestamp":"2026-03-28T09:00:00Z","deployment_id":"dep_003","correlation_id":"cid_ghi789","action":"rollback","snapshot_id":"snap_002","status":"succeeded"}
```

Query example: `tail -n 100 deployment_history.jsonl | jq 'select(.status=="failed")'`

## Rollback Snapshots

Before each deploy, create an atomic snapshot:

```bash
# snapshot_001.tar.gz contains:
/config/
  capabilities/
    network_isolation.yaml
    ble_gatt_translator.yaml
    pawr_esl_advertiser.yaml

/state/
  supervisor.db  (checkpoint at deploy time)
  entity_cache.json

metadata.json:
  {
    "snapshot_id": "snap_001",
    "deployment_id": "dep_001",
    "timestamp": "2026-03-28T10:00:00Z",
    "capabilities": ["network_isolation", "ble_gatt_translator"],
    "config_hash": "sha256:abc123...",
    "systemd_units": {
      "isolator.service": "active",
      "isolator-traffic.service": "active"
    }
  }
```

To rollback:

```python
def rollback_to_snapshot(snapshot_id):
    snapshot_tar = f"/opt/isolator/state/rollback_snapshots/{snapshot_id}.tar.gz"
    
    # 1. Stop all services
    subprocess.run(["sudo", "systemctl", "stop", "isolator.service"], timeout=10)
    
    # 2. Restore config
    subprocess.run(["tar", "-xzf", snapshot_tar, "-C", "/opt/isolator"], timeout=30)
    
    # 3. Restore database (checkpoint)
    shutil.copy(
        f"/opt/isolator/.tmp/restore/state/supervisor.db",
        "/opt/isolator/state/supervisor.db"
    )
    
    # 4. Restart services
    subprocess.run(["sudo", "systemctl", "start", "isolator.service"], timeout=10)
    
    # 5. Verify health
    health = run_health_probes()
    if health != "ok":
        raise RollbackFailedError(f"Health failed after rollback: {health}")
    
    # 6. Mark snapshot as active
    db.update_rollback_snapshots(
        snapshot_id, {"is_active": True},
        datetime.now().isoformat()
    )
```

## Metrics Collection

Supervisor collects periodic metrics for observability:

### supervisor_metrics.jsonl (hourly)
```json
{"timestamp":"2026-03-28T10:00:00Z","cpu_load_avg":[0.42,0.38,0.35],"ram_used_mb":512,"ram_free_mb":7680,"disk_used_gb":32,"disk_free_gb":32,"uptime_sec":864000,"deployments_today":3,"health_incidents":0,"entity_count":15}
```

### ble_metrics.jsonl
```json
{"timestamp":"2026-03-28T10:29:55Z","devices_found":5,"connected_devices":2,"total_scans":150,"successful_profiles":4,"failed_profiles":1,"avg_discovery_time_ms":8500}
```

### traffic_metrics.jsonl
```json
{"timestamp":"2026-03-28T10:29:50Z","total_packets":127500,"allowed_packets":125000,"blocked_packets":2500,"data_bytes":85345000,"active_devices":8}
```

HA can query these via API for dashboard graphs.

## BLE Device Profiles (/opt/isolator/data/profiles/)

User-authored and built-in GATT translation profiles:

```
/opt/isolator/data/profiles/
├── built_in/
│   ├── thermometer.yaml
│   ├── kitchen_scale.yaml
│   ├── motion_sensor.yaml
│   └── (more std profiles)
└── custom/
    ├── my_iot_device.yaml
    └── proprietary_sensor.yaml
```

Example profile structure:

```yaml
# kitchen_scale.yaml
name: "Kitchen Scale"
uuid_service: 181d              # Weight Scale Service
uuid_manufacturer: null
filter:
  local_name_prefix: "scale"    # Or MAC address ranges
  
characteristics:
  - uuid: 2a98                  # Weight
    name: weight
    unit: kg
    ha_device_class: weight
    
  - uuid: 2a19                  # Battery Level
    name: battery
    unit: "%"
    ha_device_class: battery
    
translation_rules:
  - match_uuid: 2a98
    scale_factor: 0.01          # Convert from raw (e.g., 50000 → 500 kg)
    offset: 0
```

## ESL Campaign Templates (/opt/isolator/data/esl/)

PAwR/ESL campaigns stored as templates:

```
/opt/isolator/data/esl/
├── daily_price_update.yaml
├── stock_monitor.yaml
└── seasonal_promotions.yaml
```

Example:

```yaml
# daily_price_update.yaml
name: Daily Price Update
schedule: "0 9 * * *"
target_groups:
  - group_id: grocery
    
campaigns:
  - id: produce_section
    tags:
      - esl_001
      - esl_002
      - esl_003
    payload:
      - field: line_1
        static: "Fresh Produce"
      - field: line_2
        dynamic:
          api: "https://api.example.com/prices/produce"
          json_path: "$.current_price"
          format: "${value:.2f}"
```

## Configuration as Code

All configs are YAML, stored in git for version control:

```bash
git init /opt/isolator/config
git add -A
git commit -m "Initial config: network_isolation + ble_gatt_translator"

# Track changes
git log --oneline --all

# Revert specific config
git checkout <hash> -- capabilities/ble_gatt_translator.yaml
```

## Retention Policies

- **Deployment history**: Keep 90 days or last 1000 records
- **Health probes**: Keep 7 days or last 10000 records
- **Entity state history**: Keep 30 days (optional, can be expensive)
- **Rollback snapshots**: Keep last 3 (configurable)
- **Metrics**: Keep 365 days at hourly granularity
- **Logs**: Rotate at 50 MB, keep 30 days

## Backup & Recovery

Backup strategy:

```bash
# Full backup (to USB or network storage)
tar -czf /mnt/backup/isolator_$(date +%Y%m%d_%H%M%S).tar.gz \
  /opt/isolator/config \
  /opt/isolator/state \
  /opt/isolator/data

# Incremental (since yesterday)
tar -czf /mnt/backup/incremental_$(date +%Y%m%d).tar.gz \
  --newer-mtime-than /mnt/backup/LAST_FULL \
  /opt/isolator/config \
  /opt/isolator/state
```

Recovery:

```bash
# Restore from backup
tar -xzf /mnt/backup/isolator_20260328_120000.tar.gz -C /

# Restart supervisor
sudo systemctl restart isolator-supervisor

# Verify
curl http://localhost:8080/api/v1/health
```
