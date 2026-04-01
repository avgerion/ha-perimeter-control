# Supervisor Architecture

The Pi Supervisor is the heart of the **remote Pi device** autonomous stack. It runs on the target Pi device (e.g., `192.168.50.47`) and manages capability lifecycle, enforces resource constraints, handles health probes, and exposes the REST API that the Home Assistant integration queries via network calls.

## Device Architecture

```
┌─────────────────────────┐    SSH Deploy     ┌─────────────────────────┐
│   Home Assistant        │ ────────────────► │    Raspberry Pi         │
│   (Custom Integration)  │                   │    (Target Device)     │
│                         │    API Calls      │    192.168.50.47        │
│   - UI & Entity Mgmt    │ ◄──────────────── │                         │
│   - Deployment Logic    │                   │   - Supervisor API      │
│   - SSH Client          │                   │   - Dashboard Web       │
│                         │                   │   - Services Runtime    │
└─────────────────────────┘                   └─────────────────────────┘
```

## Core Responsibilities

1. **Capability Lifecycle Management**
   - Load capability manifests from `/opt/isolator/config/capabilities/`
   - Validate config schemas and resource requirements
   - Plan deployment (dependency order, conflict resolution)
   - Apply changes atomically (with rollback on failure)
   - Monitor service health and auto-restart

2. **Resource Scheduling**
   - Enforce CPU, RAM, disk, I/O budgets per capability
   - Track BLE adapter ownership (exclusive resource)
   - Detect conflicts and prevent incompatible workloads
   - Support priority-based preemption (e.g., critical can preempt normal)

3. **State Machine & Reconciliation**
   - Maintain desired state vs. actual state
   - Periodic reconciliation loop (check every 30s)
   - Drift detection and auto-correction
   - Transactional deploy with atomic rollback

4. **Health Probes & Self-Healing**
   - Run per-capability health checks (process, exec, HTTP, file)
   - Track consecutive failures and apply bounded restart policy
   - Collect diagnostics on health degradation
   - Report health rollup to HA via `/api/v1/health`

5. **REST API**
   - Entity discovery and state queries
   - Action triggers (reload rules, start scan, etc.)
   - Long-poll or WebSocket event stream
   - Configuration exposure and updates

## Process Architecture

```
┌─────────────────────────────────────────────┐
│  isolator-supervisor (main daemon)          │
├─────────────────────────────────────────────┤
│ • Config loader                             │
│ • State store (JSON/SQLite)                 │
│ • Resource scheduler                        │
│ • Health probe runner                       │
│ • REST API server (Tornado)                 │
│ • Event bus (local pub/sub)                 │
└─────────────────────────────────────────────┘
         │
         ├─ spawns ──→ isolator-network-isolation (systemd unit)
         ├─ spawns ──→ isolator-traffic (systemd unit)
         ├─ spawns ──→ isolator-dashboard (Tornado/Bokeh)
         ├─ spawns ──→ ble-scanner-v2 (on demand)
         ├─ spawns ──→ ble-profiler (on demand)
         └─ spawns ──→ pawr-advertiser (if enabled)
```

## Configuration Files

```
/opt/isolator/
├── config/
│   ├── node.yaml              # Node metadata (read-only)
│   ├── supervisor.yaml        # Supervisor settings (resource limits, etc.)
│   └── capabilities/
│       ├── network_isolation.yaml
│       ├── ble_gatt_translator.yaml
│       ├── pawr_esl_advertiser.yaml
│       └── (user custom capabilities)
├── state/
│   ├── supervisor.db          # SQLite: deployment history, rollback snapshots
│   └── entity_cache.json      # Last known entity states (for restart)
├── scripts/
│   ├── ble-scanner-v2.py
│   ├── ble-profiler.py
│   ├── traffic-logger.py
│   └── ...
└── web/
    └── (Tornado/Bokeh dashboard)
```

## State Machine

Each capability transitions through states:

```
┌─────────┐
│ inactive│ ← User disables capability
└────┬────┘
     │ User enables
     ↓
┌─────────────┐
│ validating  │ ← Validate config and resources
└────┬────────┘
     │ ✓ Valid
     ↓
┌──────────┐
│ planning │ ← Plan deploy (order, conflicts)
└────┬─────┘
     │ ✓ No conflicts
     ↓
┌──────────┐
│ deploying│ ← Pull images, install, apply config
└────┬─────┘
     │
  ┌──┴──────────────────────┐
  │ ✗ Deploy failed         │
  ↓                         │
┌──────────────────┐        │
│ rolling_back     │←───────┘
└────┬─────────────┘
     │
  ┌──┴──────────────────────┐
  │ ✓ Rollback succeeded    │ ✓ Deploy succeeded
  ↓                         ↓
┌──────────────┐         ┌────────┐
│ failed       │         │ active │
└──────────────┘         └───┬────┘
                             │
                    Health check fails
                             │
                             ↓
                        ┌──────────┐
                        │ degraded │
                        └────┬─────┘
                             │ Auto-restart (bounded)
                             │ Success: back to active
                             │ Max retries: → failed
```

## Reconciliation Loop

Pseudo-code:

```python
def reconcile_loop():
    interval = 30  # seconds
    while running:
        try:
            # 1. Load desired state from config
            desired = load_capabilities_config()
            
            # 2. Poll actual state (systemd, process lists, health checks)
            actual = poll_current_state()
            
            # 3. Compute diff
            diff = compute_diff(desired, actual)
            
            if diff:
                logger.info(f"State drift detected: {diff}")
                
                # 4. Plan changes (order, conflicts)
                plan = scheduler.plan(desired, actual)
                
                # 5. Apply changes (with transaction + rollback)
                try:
                    apply_plan(plan)
                    snapshot_state(desired)  # Save rollback point
                except Exception as e:
                    logger.error(f"Apply failed: {e}")
                    rollback_to_snapshot()
                    mark_degraded(plan.capabilities)
            
            # 6. Run health checks
            for cap_id in desired.keys():
                health = run_health_probes(cap_id)
                update_entity_state(f"health:{cap_id}", health)
            
            # 7. Publish entity updates via event bus
            publish_entity_updates()
            
        except Exception as e:
            logger.error(f"Reconciliation error: {e}")
        
        time.sleep(interval)
```

## Health Probes

Each capability declares probes in its manifest:

```yaml
health:
  startup_grace_period_sec: 10
  probes:
    - name: process_running
      type: process
      pattern: "traffic-logger.py"
      interval_sec: 30
      timeout_sec: 5
      max_failures: 3       # Restart after 3 consecutive failures
      
    - name: nftables_loaded
      type: exec
      command: ["sudo", "nft", "list", "table", "inet", "isolator"]
      interval_sec: 30
      timeout_sec: 5
      
    - name: api_responsive
      type: http
      url: "http://localhost:8080/api/v1/node/info"
      method: GET
      expected_status: 200
      interval_sec: 60
      timeout_sec: 5
```

Health states:
- `ok` — all probes passed
- `warn` — some probes failed but within tolerance
- `degraded` — multiple failures, auto-restart in progress
- `failed` — max retries exceeded, user intervention needed

## Resource Enforcement

Supervisor tracks live resource usage per capability:

```python
class ResourceBudget:
    cpu_cores: int
    cpu_load_percent: int
    ram_mb: int
    disk_free_mb: int
    io_read_mb_sec: int
    io_write_mb_sec: int
    exclusive_resources: List[str]  # ["ble_radio_0", "nftables"]

def can_admit_capability(cap_id: str, budget: ResourceBudget) -> Tuple[bool, str]:
    """Check if capability can be admitted within budget."""
    
    # 1. Check exclusive resource conflicts
    for exclusive in budget.exclusive_resources:
        if is_resource_in_use(exclusive):
            return False, f"Resource {exclusive} already in use"
    
    # 2. Check CPU headroom
    current_load = get_system_load_avg()
    if current_load + budget.cpu_load_percent > 100:
        return False, f"CPU load would exceed 100%"
    
    # 3. Check RAM headroom
    free_ram = get_free_ram_mb()
    if free_ram < budget.ram_mb:
        return False, f"Insufficient RAM: {free_ram}MB < {budget.ram_mb}MB"
    
    # 4. Check disk headroom
    free_disk = get_free_disk_mb()
    if free_disk < budget.disk_free_mb:
        return False, f"Insufficient disk: {free_disk}MB < {budget.disk_free_mb}MB"
    
    return True, "Resources available"
```

## Rollback Snapshot Strategy

Before applying a deploy:

1. Snapshot current capability versions and config
2. Save systemd unit state
3. Tag snapshot with deployment ID and timestamp
4. Store in SQLite rollback table

If deploy fails:

1. Retrieve snapshot with matching deployment ID
2. Restore config to snapshot state
3. Restart systemd units
4. Verify all health probes pass
5. Mark snapshot as active again

Keep last N snapshots (configurable, default 3) for quick rollback.

## Event Bus

Local pub/sub for system events:

```python
# Publisher (inside reconciliation loop)
event_bus.publish("entity_updated", {
    "entity_id": "traffic_logger_running",
    "state": True,
    "timestamp": datetime.now().isoformat()
})

# Subscriber (REST API handlers)
event_bus.subscribe("entity_updated", on_entity_changed)

# Used by:
# - Long-poll clients (accumulate events, return on timeout)
# - WebSocket clients (push immediately)
# - Local diagnostics (log to file)
```

## REST API Implementation

Supervisor exposes Tornado handlers:

```python
class NodeInfoHandler(tornado.web.RequestHandler):
    def get(self):
        info = supervisor.get_node_info()
        self.write(info)

class EntitiesHandler(tornado.web.RequestHandler):
    def get(self):
        entities = supervisor.get_exposed_entities()
        self.write({"entities": entities})

class EntityStateHandler(tornado.web.RequestHandler):
    def get(self, entity_id):
        state = supervisor.get_entity_state(entity_id)
        self.write(state)

class CapabilityActionHandler(tornado.web.RequestHandler):
    def post(self, cap_id, action_name):
        result = supervisor.trigger_action(cap_id, action_name)
        self.write(result)

class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        health = supervisor.get_health_rollup()
        self.write(health)
```

## Startup Sequence

1. Load supervisor config from `/opt/isolator/config/supervisor.yaml`
2. Initialize state store (SQLite)
3. Load last known entity states from cache
4. Read desired capabilities from `/opt/isolator/config/capabilities/*.yaml`
5. Validate all configs
6. Start REST API server on port 8080
7. Enter reconciliation loop
8. On first run: perform full deploy; on restart: reconcile to desired state

## Logging and Correlation

Every reconciliation cycle and action has a correlation ID:

```
2026-03-28 10:30:00 [INFO] [cid=abc123] Reconciliation cycle starting
2026-03-28 10:30:01 [INFO] [cid=abc123] Desired state: 3 capabilities
2026-03-28 10:30:02 [INFO] [cid=abc123] Health check: network_isolation=ok, ble_gatt_translator=warn
2026-03-28 10:30:03 [ERROR] [cid=abc123] Traffic logger failed 2/3 times, restarting
2026-03-28 10:30:05 [INFO] [cid=abc123] Reconciliation complete
```

HA can query diagnostics and see full correlation chains for troubleshooting.
