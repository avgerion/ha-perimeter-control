# Deployment & Upgrade Strategy

Safe, observable, and reversible deployments with minimal downtime.

## Deployment Phases

```
Phase 1: Validation
  ↓
Phase 2: Preflight Checks
  ↓
Phase 3: Staging
  ↓
Phase 4: Apply (with transactional rollback)
  ↓
Phase 5: Health Verification
  ↓
Phase 6: Snapshot & Activate
```

## Phase 1: Validation

Validate all configuration schemas before touching the system:

```python
def validate_deployment(desired_state: Dict) -> Tuple[bool, List[str]]:
    """Validate all configs and resource requirements."""
    
    errors = []
    
    # 1. Schema validation
    for cap_id, cap_config in desired_state.items():
        schema = load_schema(f"capabilities/{cap_id}.schema.json")
        try:
            jsonschema.validate(cap_config, schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{cap_id}: {e.message}")
    
    # 2. Resource conflict check
    total_cpu = sum(c.get("resources", {}).get("cpu_cores", 0) 
                    for c in desired_state.values())
    if total_cpu > available_cpu_cores():
        errors.append(f"Total CPU {total_cpu} exceeds {available_cpu_cores()}")
    
    # 3. Exclusive resource conflict check
    exclusive_resources = set()
    for cap_config in desired_state.values():
        for resource in cap_config.get("hardware", {}).get("exclusive_resources", []):
            if resource in exclusive_resources:
                errors.append(f"Exclusive resource conflict: {resource}")
            exclusive_resources.add(resource)
    
    # 4. Dependency and version check
    for cap_id, cap_config in desired_state.items():
        version = cap_config.get("version")
        if not is_package_available(cap_id, version):
            errors.append(f"Package {cap_id}:{version} not available")
    
    return len(errors) == 0, errors
```

If any validation fails, abort immediately (no changes to system).

## Phase 2: Preflight Checks

Snapshot what we're about to change:

```python
def preflight_checks(desired_state: Dict) -> Dict:
    """Capture current state before any changes."""
    
    preflight = {
        "deployment_id": generate_uuid(),
        "correlation_id": generate_uuid(),
        "timestamp": datetime.now().isoformat(),
        "desired_state": desired_state,
        "current_state": {
            "systemd_units": get_systemd_status(),
            "processes": get_running_processes(),
            "resource_usage": get_resource_usage(),
            "health_probes": run_all_health_probes(),
        },
        "changes": compute_diff(desired_state, current_state),
    }
    
    # Save preflight report for audit
    save_preflight_report(preflight)
    
    return preflight
```

## Phase 3: Staging

Download and verify new packages/images before live switch:

```python
def stage_deployment(deployment: Dict) -> Dict:
    """Download, verify, and prepare packages."""
    
    staging_dir = f"/tmp/isolator_deploy_{deployment['deployment_id']}"
    os.makedirs(staging_dir, exist_ok=True)
    
    staged_packages = {}
    
    for cap_id, cap_config in deployment["desired_state"].items():
        version = cap_config.get("version", "latest")
        image_tag = cap_config.get("image_tag", "latest")
        
        # 1. Fetch package
        logger.info(f"Fetching {cap_id}:{version}...")
        package_path = download_package(cap_id, version, staging_dir)
        
        # 2. Verify checksum
        expected_checksum = load_checksum_manifest(cap_id, version)
        actual_checksum = compute_sha256(package_path)
        if actual_checksum != expected_checksum:
            raise VerificationError(f"Checksum mismatch for {cap_id}")
        
        # 3. Verify signature (if enabled)
        if verify_signatures_enabled():
            verify_signature(package_path)
        
        # 4. Extract and validate structure
        extract_to_verify(package_path, f"{staging_dir}/verify/{cap_id}")
        validate_package_structure(cap_id, f"{staging_dir}/verify/{cap_id}")
        
        staged_packages[cap_id] = {
            "path": package_path,
            "checksum": actual_checksum,
            "size_mb": os.path.getsize(package_path) / 1024 / 1024,
        }
    
    return staged_packages
```

## Phase 4: Apply (Atomic with Rollback)

Execute the deployment with transactional semantics:

```python
def apply_deployment(deployment: Dict, staged: Dict):
    """Apply deploy with rollback on failure."""
    
    deployment_id = deployment["deployment_id"]
    correlation_id = deployment["correlation_id"]
    
    try:
        # Create rollback point BEFORE any changes
        logger.info(f"[{correlation_id}] Creating rollback snapshot...")
        snapshot_id = create_rollback_snapshot(deployment_id)
        
        # 1. Stop affected services (graceful)
        logger.info(f"[{correlation_id}] Stopping affected services...")
        for cap_id in deployment["changes"].get("modified", []):
            stop_capability(cap_id, timeout_sec=30)
        
        # 2. Copy staged packages to active locations
        logger.info(f"[{correlation_id}] Installing packages...")
        for cap_id, package_info in staged.items():
            install_package(cap_id, package_info)
        
        # 3. Generate/update systemd units
        logger.info(f"[{correlation_id}] Updating systemd units...")
        for cap_id, cap_config in deployment["desired_state"].items():
            generate_systemd_unit(cap_id, cap_config)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], timeout=10)
        
        # 4. Apply configuration (order matters)
        logger.info(f"[{correlation_id}] Applying configurations...")
        apply_order = topological_sort_capabilities(deployment["desired_state"])
        for cap_id in apply_order:
            cap_config = deployment["desired_state"][cap_id]
            apply_capability_config(cap_id, cap_config)
        
        # 5. Start services
        logger.info(f"[{correlation_id}] Starting services...")
        for cap_id in apply_order:
            start_capability(cap_id, timeout_sec=60)
        
        logger.info(f"[{correlation_id}] Deployment apply succeeded")
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Deploy failed: {e}")
        logger.info(f"[{correlation_id}] Initiating rollback...")
        try:
            rollback_to_snapshot(snapshot_id)
            logger.info(f"[{correlation_id}] Rollback succeeded")
        except Exception as rb_err:
            logger.critical(f"[{correlation_id}] Rollback FAILED: {rb_err}")
            mark_system_failed(deployment_id, str(rb_err))
        raise
```

## Phase 5: Health Verification

After services are up, run comprehensive health checks:

```python
def verify_deployment_health(deployment: Dict, timeout_sec: int = 120) -> bool:
    """Verify all health probes pass after deploy."""
    
    correlation_id = deployment["correlation_id"]
    start_time = time.time()
    
    # Grace period for services to stabilize
    time.sleep(10)
    
    while time.time() - start_time < timeout_sec:
        all_healthy = True
        
        for cap_id in deployment["desired_state"].keys():
            probes = get_capability_health_probes(cap_id)
            results = {}
            
            for probe in probes:
                try:
                    result = run_probe(probe)
                    results[probe["name"]] = result
                    if not result:
                        all_healthy = False
                        logger.warn(f"[{correlation_id}] Probe {probe['name']} failed")
                except Exception as e:
                    logger.error(f"[{correlation_id}] Probe error: {e}")
                    all_healthy = False
            
            db.insert_health_check(cap_id, results, datetime.now())
        
        if all_healthy:
            logger.info(f"[{correlation_id}] All health checks passed")
            return True
        
        time.sleep(5)
    
    logger.error(f"[{correlation_id}] Health checks failed after {timeout_sec}s")
    return False
```

## Phase 6: Snapshot & Activate

If all health checks pass, mark the deployment as active:

```python
def finalize_deployment(deployment: Dict, snapshot_id: str):
    """Finalize deploy: snapshot and mark active."""
    
    correlation_id = deployment["correlation_id"]
    
    # 1. Create final snapshot
    logger.info(f"[{correlation_id}] Creating deployment snapshot...")
    final_snapshot = create_rollback_snapshot(
        deployment_id=deployment["deployment_id"],
        is_active=True
    )
    
    # 2. Clean up older snapshots
    cleanup_old_snapshots(keep_count=3)
    
    # 3. Record deployment
    db.update_deployments({
        "deployment_id": deployment["deployment_id"],
        "status": "succeeded",
        "snapshot_id": final_snapshot,
        "timestamp": datetime.now().isoformat(),
    })
    
    # 4. Update entity cache from live state
    update_entity_cache()
    
    logger.info(f"[{correlation_id}] Deployment {deployment['deployment_id']} succeeded")
```

## Upgrade Path example

User wants to upgrade BLE translator from v1.0 to v1.1:

```yaml
# Current
ble_gatt_translator:
  version: "1.0.0"

# Desired
ble_gatt_translator:
  version: "1.1.0"
```

Supervisor:

1. **Validates** v1.1 schema and compatibility
2. **Preflight**: captures current profiles, state, running scans
3. **Stages**: downloads v1.1 package, verifies
4. **Applies**: 
   - Stops BLE scanner gracefully (save current session state)
   - Installs v1.1 files
   - Runs migration if v1.0 → v1.1 has schema changes
   - Starts scanner with v1.1
5. **Verifies**: runs health probes, checks profiles still load
6. **Snapshots**: creates rollback point with v1.1 active

If step 5 fails, rolls back to v1.0 snapshot automatically.

## Rollback Scenarios

**User-initiated rollback:**
```
HA → /api/v1/capabilities/ble_gatt_translator/actions/rollback
  ↓
Supervisor finds latest successful snapshot
  ↓
Executes rollback (Phase 4 in reverse)
  ↓
Verifies health
  ↓
Confirms v1.0 is active again
```

**Automatic rollback (health check failure):**
```
Deploy succeeds but health check fails
  → Wait 5 more seconds, retry
  → Still failing after 60s timeout?
  → Auto-rollback to previous snapshot
  → Mark deployment as "failed_health_check"
  → Alert HA / emit event
```

## Multi-capability Deployment

Deploying changes to multiple capabilities respects dependencies:

```python
def plan_multi_capability_deployment(desired: Dict) -> List[ExecutionPlan]:
    """Generate execution order based on dependencies."""
    
    # Build dependency graph
    deps = {
        "network_isolation": [],
        "ble_gatt_translator": ["network_isolation"],  # Needs network
        "pawr_esl_advertiser": ["ble_gatt_translator"],  # Needs BLE
    }
    
    # Topological sort
    order = topological_sort(deps)
    
    # Example: if all 3 are being deployed
    # Order: network_isolation → ble_gatt_translator → pawr_esl
    # If one fails, rollback entire deployment
    
    return order
```

## Dry Run / Preview

Before actual deploy, show user what will happen:

```bash
# Preview deploy without executing
curl -X POST http://localhost:8080/api/v1/deployments/preview \
  -d @desired_state.json

# Response:
{
  "deployment_id": "dep_preview_001",
  "changes": {
    "modified": ["ble_gatt_translator"],
    "unchanged": ["network_isolation", "pawr_esl_advertiser"]
  },
  "impact": {
    "service_restarts": ["ble-scanner", "ble-profiler"],
    "estimated_downtime_sec": 10,
    "risk_level": "low"
  },
  "can_proceed": true,
  "warnings": []
}
```

## Monitoring Deployment

HA can observe deployment progress:

```bash
# Watch deploy in real-time
curl http://localhost:8080/api/v1/events/deployments?since=2026-03-28T10:00:00Z

# Response (events):
{
  "events": [
    {"timestamp": "...", "stage": "validation", "status": "passed"},
    {"timestamp": "...", "stage": "preflight", "status": "passed"},
    {"timestamp": "...", "stage": "staging", "status": "in_progress", "progress": 45},
    {"timestamp": "...", "stage": "apply", "status": "in_progress"},
    ...
  ]
}
```
