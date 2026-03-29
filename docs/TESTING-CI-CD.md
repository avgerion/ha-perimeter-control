# Testing & CI/CD

Comprehensive testing strategy for reliability and community contribution.

## Test Pyramid

```
       ╱╲  Contract Tests (Pi API ↔ HA integration)
      ╱  ╲
     ╱────╲ Integration Tests (multi-capability, reconciliation)
    ╱      ╲
   ╱────────╲ Unit Tests (individual components, logic)
```

## Unit Tests

Test individual functions and classes in isolation.

### Supervisor Tests (`tests/unit/test_supervisor.py`)

```python
def test_reconciliation_no_changes():
    """Reconciliation with matching desired/actual state."""
    supervisor = MockSupervisor()
    supervisor.desired_state = {"cap1": {"status": "active"}}
    supervisor.actual_state = get_current_state()  # Matches
    
    diff = supervisor.compute_diff()
    assert diff == {}  # No changes needed

def test_reconciliation_with_drift():
    """Reconciliation detects and corrects drift."""
    supervisor = MockSupervisor()
    supervisor.desired_state = {"cap1": {"status": "active"}}
    supervisor.actual_state = {"cap1": {"status": "stopped"}}
    
    diff = supervisor.compute_diff()
    assert "cap1" in diff["to_start"]

def test_resource_admission_cpu_overcommit():
    """Reject capability if CPU overcommitted."""
    supervisor = MockSupervisor()
    supervisor.available_cpu_cores = 4
    supervisor.used_cpu_cores = 3.5
    
    new_cap = {"resources": {"cpu_cores": 1}}
    can_admit, reason = supervisor.can_admit(new_cap)
    assert can_admit is False

def test_health_probe_failure_bounded_restart():
    """After N failures, mark degraded instead of infinite retry."""
    supervisor = MockSupervisor()
    supervisor.max_consecutive_failures = 3
    
    # Simulate 3 probe failures
    for i in range(3):
        supervisor.run_health_probe("cap1")
        supervisor.consecutive_failures["cap1"] += 1
    
    status = supervisor.get_capability_health("cap1")
    assert status == "degraded"

def test_rollback_snapshot_restore():
    """Snapshot restore actually reverts state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = f"{tmpdir}/snap.tar.gz"
        
        # Create snapshot
        create_snapshot(snapshot_path, config_data)
        
        # Modify live state
        modify_live_state()
        
        # Restore from snapshot
        restore_snapshot(snapshot_path)
        
        # Verify state matches snapshot
        current = load_current_state()
        assert current == config_data
```

### Capability Tests (`tests/unit/test_capabilities.py`)

```python
def test_network_isolation_config_validation():
    """Valid network isolation config passes schema."""
    config = load_yaml("tests/fixtures/network_isolation.yaml")
    valid, errors = validate_config("network_isolation", config)
    assert valid is True

def test_ble_gatt_translator_profile_parsing():
    """BLE profile parsing handles all required fields."""
    profile = load_yaml("tests/fixtures/kitchen_scale_profile.yaml")
    parsed = parse_profile(profile)
    assert parsed.uuid_service == "181d"
    assert len(parsed.characteristics) >= 1

def test_pawr_campaign_schedule_cron():
    """PAwR campaign CRON schedule parses correctly."""
    schedule = "0 9 * * *"
    next_run = compute_next_run_time(schedule)
    assert next_run.hour == 9
    assert next_run.minute == 0
```

## Integration Tests

Test how components interact together.

### Multi-capability Reconciliation (`tests/integration/test_multi_cap.py`)

```python
def test_deploy_network_isolation_and_ble():
    """Deploy network_isolation + ble_gatt_translator together."""
    with IsolatorTestEnvironment() as env:
        # Set desired state
        env.desired_state = {
            "network_isolation": load_yaml("configs/network_isolation.yaml"),
            "ble_gatt_translator": load_yaml("configs/ble_gatt_translator.yaml"),
        }
        
        # Execute deploy
        deployment_id = env.supervisor.deploy(env.desired_state)
        
        # Verify both services are active
        assert env.get_service_status("isolator.service") == "active"
        assert env.get_service_status("ble-scanner.service") == "active"
        
        # Verify health probes pass
        health = env.supervisor.get_health_rollup()
        assert health["network_isolation"] == "ok"
        assert health["ble_gatt_translator"] == "ok"

def test_conflicting_radio_exclusive_resource():
    """Cannot deploy BLE scanner and PAwR advertiser on same radio."""
    with IsolatorTestEnvironment() as env:
        # Deploy BLE scanner first
        env.deploy_capability("ble_gatt_translator")
        assert env.get_service_status("ble-scanner.service") == "active"
        
        # Try to deploy PAwR (should fail or preempt based on policy)
        pawr_config = load_yaml("configs/pawr_esl_advertiser.yaml")
        deployment_id = env.supervisor.deploy({"pawr_esl_advertiser": pawr_config})
        
        # Depending on preemption policy, either:
        # 1. PAwR succeeds and BLE pauses
        # 2. PAwR deploy rejected
        # Test should verify one of these behaviors
        
def test_ble_profile_discovery_and_translation():
    """Full flow: discover BLE device, match profile, translate to HA entity."""
    with IsolatorTestEnvironment() as env:
        env.deploy_capability("ble_gatt_translator")
        
        # Simulate device advertisement
        env.mock_ble_advertisement({
            "mac": "de:ad:be:ef:00:01",
            "name": "kitchen_scale",
            "uuid_service": "181d",  # Weight Scale Service
        })
        
        # Trigger scan
        env.supervisor.trigger_action("ble_gatt_translator", "start_scan")
        
        # Wait for discovery
        time.sleep(5)
        
        # Verify device discovered and profiled
        devices = env.supervisor.get_entities_like("ble_device:*")
        assert any("kitchen_scale" in e for e in devices)
        
        # Verify translation applied
        weight_entity = env.supervisor.get_entity_state("ble_device:kitchen_scale:weight")
        assert weight_entity["unit_of_measurement"] == "kg"
```

## Contract Tests

Test API contract between Pi and Home Assistant.

### REST API Contract (`tests/contract/test_pi_api.py`)

```python
def test_api_node_info_schema():
    """GET /api/v1/node/info returns valid schema."""
    response = requests.get("http://localhost:8080/api/v1/node/info")
    
    assert response.status_code == 200
    
    data = response.json()
    assert "node_id" in data
    assert "hardware" in data
    assert "capabilities" in data
    assert isinstance(data["hardware"]["ble_adapters"], list)

def test_api_entities_discover_and_query():
    """Entity discovery and state queries work end-to-end."""
    # 1. Discover available entities
    response = requests.get("http://localhost:8080/api/v1/entities")
    assert response.status_code == 200
    
    entities = response.json()["entities"]
    assert len(entities) > 0
    
    # 2. Query state of first entity
    entity_id = entities[0]["id"]
    response = requests.get(f"http://localhost:8080/api/v1/entities/{entity_id}")
    assert response.status_code == 200
    
    state = response.json()
    assert "state" in state
    assert "last_updated" in state

def test_api_capability_action_trigger():
    """Triggering a capability action works."""
    # 1. Get available actions
    response = requests.get("http://localhost:8080/api/v1/capabilities")
    capabilities = response.json()["capabilities"]
    
    # 2. Find an action
    action = next(
        a for cap in capabilities 
        for a in cap["actions"] if a["name"] == "reload_rules"
    )
    
    # 3. Trigger it
    response = requests.post(
        f"http://localhost:8080/api/v1/capabilities/network_isolation/actions/reload_rules"
    )
    assert response.status_code == 200
    
    result = response.json()
    assert "success" in result
    assert result["success"] is True
```

## Hardware-in-the-Loop Tests

Test against real Pi hardware (in CI runner or dedicated lab).

### Real Pi Smoke Tests (`tests/hardware/test_real_pi.py`)

```python
@pytest.mark.hardware
def test_real_pi_network_isolation_deploy():
    """Deploy network_isolation on real Pi hardware."""
    pi = connect_to_real_pi("192.168.1.50")
    
    # 1. Deploy via API
    response = pi.deploy({
        "network_isolation": load_yaml("configs/network_isolation.yaml")
    })
    assert response["status"] == "succeeded"
    
    # 2. Verify nftables rules actually loaded
    result = pi.run_command("sudo nft list table inet isolator")
    assert result.returncode == 0
    assert "chain ap_clients" in result.stdout
    
    # 3. Test device connectivity and log generation
    test_device = connect_to_test_device("192.168.111.100")
    test_device.ping("192.8.8.8")
    
    # 4. Verify packet logged
    time.sleep(2)
    response = pi.get_entity_state("device_traffic:test_device:allowed_packets")
    assert response["state"] > 0

@pytest.mark.hardware
def test_real_pi_ble_scan_discovery():
    """Test actual BLE scan on real Pi with real devices."""
    pi = connect_to_real_pi("192.168.1.50")
    
    # Deploy BLE translator
    pi.deploy({"ble_gatt_translator": {...}})
    
    # Trigger scan
    pi.trigger_action("ble_gatt_translator", "start_scan")
    
    # Wait for devices
    time.sleep(30)
    
    # Query discovered devices
    devices = pi.get_entities_like("ble_device:*")
    assert len(devices) > 0
```

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/test.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit_tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/unit/ -v --cov=isolator

  integration_tests:
    runs-on: ubuntu-latest
    services:
      isolator_pi:
        image: isolator:test
        ports:
          - 8080:8080
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/integration/ -v --cov=isolator

  contract_tests:
    runs-on: ubuntu-latest
    services:
      isolator_api:
        image: isolator:test
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/contract/ -v

  lint_and_format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install flake8 black mypy
      - run: black --check isolator/
      - run: flake8 isolator/ --max-line-length=100
      - run: mypy isolator/ --strict

  hardware_smoke_tests:
    runs-on: [self-hosted, rpi]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/hardware/ -v --hardware
```

## Test Fixtures

Reusable test data:

```
tests/
├── fixtures/
│   ├── network_isolation.yaml           # Valid config
│   ├── ble_gatt_translator.yaml
│   ├── kitchen_scale_profile.yaml
│   ├── invalid_config.yaml              # For schema validation tests
│   └── mock_hardware_info.json
├── conftest.py                          # Pytest config + fixtures
└── (test files)
```

Example `conftest.py`:

```python
@pytest.fixture
def supervisor_instance():
    """Provide a fresh supervisor for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        supervisor = Supervisor(config_dir=tmpdir)
        yield supervisor
        supervisor.cleanup()

@pytest.fixture
def mock_ble_adapter():
    """Mock BLE adapter for testing."""
    return MockBleAdapter()

@pytest.fixture
def isolator_test_env():
    """Full test environment with supervisor + mocked services."""
    return IsolatorTestEnvironment()
```

## Coverage Goals

- **Unit tests**: >= 80% code coverage
- **Integration tests**: >= 60% coverage
- **Critical paths**: >= 95% coverage (deployment, rollback, health probes)

## Performance Benchmarks

Track performance regressions:

```python
@pytest.mark.benchmark
def test_reconciliation_performance(benchmark):
    """Reconciliation loop should complete < 500ms."""
    supervisor = Supervisor()
    supervisor.desired_state = {
        "cap1": {...},
        "cap2": {...},
        "cap3": {...},
    }
    
    result = benchmark(supervisor.reconcile)
    assert result < 0.5  # 500ms
```

Run with: `pytest tests/ --benchmark-only`
