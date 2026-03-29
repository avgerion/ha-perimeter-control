# Network Isolator Platform Roadmap

## Vision
Build an open-source Raspberry Pi platform managed from Home Assistant, where each Pi can run multiple capabilities concurrently (when compatible), and multiple Pis can be orchestrated as a fleet.

The platform should support:
- Network isolation and traffic logging
- BLE controller workflows (scan, profile, mirror, GATT translation)
- PAwR advertising for ESL (dongle-backed when needed)

## Product Principles
1. Home Assistant is the control plane.
2. Tornado/Bokeh remains the local expert console for deep diagnostics and advanced workflows.
3. A Pi can run multiple modes concurrently when resource and hardware constraints allow.
4. Multiple Pis are first-class from day one.
5. Deployments must be idempotent, observable, and rollback-safe.

## User Experience Goal
A user can:
1. Flash a blank Raspberry Pi image and enable SSH.
2. Install the Home Assistant integration.
3. Add the Pi with SSH host and key in integration config.
4. Select capabilities to run.
5. Be fully operational without manual shell steps.

## Target Architecture

### 1) Home Assistant Integration (Fleet Control Plane)
Responsibilities:
- Node onboarding via SSH credentials and connectivity checks
- Capability deployment and lifecycle control
- Fleet inventory, health, and diagnostics
- Policy and mode assignment per node
- Automation-facing services and entities

Key concepts:
- Node: one managed Pi
- Capability: deployable runtime unit (network isolation, BLE translation, PAwR advertiser)
- Instance: a running capability on a node

### 2) Pi Supervisor Agent (Per Node)
Always-on service that:
- Registers node capabilities and hardware inventory
- Receives desired state from Home Assistant
- Plans and executes reconcile actions
- Starts/stops/restarts capability services
- Runs health checks and self-healing
- Performs rollback on failed deploy or health regressions

### 3) Capability Runtimes (Composable)
Each capability implements a common contract:
- validate_config(config) -> pass/fail + reasons
- plan(current_state, desired_state) -> actions
- apply(actions) -> result + diagnostics
- start()/stop()/status()/health()
- collect_diagnostics()

Initial capability set:
- network_isolation
- ble_controller
- ble_gatt_translation
- pawr_esl_advertiser

### 4) Local Expert Console (Tornado/Bokeh)
Per-node advanced interface for:
- Packet/flow inspection
- BLE event timeline and payload analysis
- Device profile authoring and translation testing
- Deep troubleshooting not practical in HA cards

## Scheduling and Coexistence Model
Replace "single active mode" with a scheduler that evaluates requirements, conflicts, and priorities.

### Resource Dimensions
- CPU cores and load budget
- RAM budget
- Disk IO and storage budget
- Network interface ownership (wlan0/eth0)
- BLE radio ownership per adapter (built-in or USB dongle)
- Optional GPIO/UART ownership

### Capability Manifest (per runtime)
Each capability declares:
- required_resources
- preferred_resources
- hard_conflicts
- soft_conflicts
- priority_class (critical/high/normal/best-effort)
- preemption_policy
- health_probe definitions

### Example Coexistence Rules
Allowed:
- network_isolation + ble_gatt_translation (if BLE adapter available)

Conditionally allowed:
- ble scan + ble proxy when separate adapters exist

Disallowed on same adapter:
- high-duty PAwR advertising + active scan loops

## Fleet Model (Multi-Pi)

### Node Labels and Capability Tags
Examples:
- role=perimeter
- role=ble-gateway
- hw=ble-native
- hw=silabs-dongle
- feature=pawr

### Placement Strategies
- Pin capability to node
- Spread capability across nodes
- Affinity/anti-affinity (for redundancy)
- Drain and migrate workloads for maintenance

### Failure Handling
- Node unreachable -> mark degraded, keep desired state
- Health probe failures -> bounded restart policy
- Persistent failures -> rollback last deployment and raise HA event

## Security Baseline
1. SSH key-based auth only by default.
2. Least-privilege service users on Pi.
3. Signed release artifacts with checksum validation.
4. Strict audit logging for deploy, config, mode transitions.
5. Secret handling via Home Assistant secure storage.

## Open Source Plan

### Governance and Packaging
- License: Apache-2.0 or MIT
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- Semantic versioning and changelog policy
- Hardware compatibility matrix

### Suggested Repository Layout
- /supervisor
- /capabilities/network_isolation
- /capabilities/ble_controller
- /capabilities/ble_gatt_translation
- /capabilities/pawr_esl
- /ha_integration
- /deploy
- /docs
- /tests

## 18-Month Roadmap

### Phase 0 (0-1 month): Stabilize Current Baseline
- Consolidate existing scripts into clear capability boundaries
- Introduce capability contract interfaces
- Add structured logs and correlation IDs
- Ensure reliable config apply and reload behavior

Deliverable:
- Single-node supervisor running current Network Isolator and BLE stack behind one local API

### Phase 1 (1-3 months): Supervisor and Capability Manifests
- Build per-node supervisor daemon
- Define capability manifest schema (resources/conflicts/priorities)
- Implement scheduler for multi-capability admission control
- Add health checks and bounded restart policies

Deliverable:
- One Pi can run multiple compatible capabilities concurrently

### Phase 2 (2-5 months): Home Assistant Integration MVP
- Config flow: host, ssh key, auth verification
- Node entities: online status, active capabilities, health
- Services: deploy capability, start/stop, diagnostics pull, rollback
- Keep Tornado/Bokeh as "Open expert console" action per node

Deliverable:
- HA can onboard and manage one Pi end-to-end

### Phase 3 (4-8 months): Fleet and Placement
- Multi-node inventory and grouping
- Placement policies (pin/spread/affinity)
- Rolling deploys and node drain workflows
- Fleet diagnostics and alert surfacing in HA

Deliverable:
- HA manages multiple Pis as one fleet

### Phase 4 (6-10 months): BLE Translation Productization
- Profile packs for common devices (scale, thermometer, sensors)
- Translation pipeline hardening and retries
- Device-specific validation and simulation tests

Deliverable:
- Reusable BLE translation profiles with stable operation

### Phase 5 (9-14 months): PAwR + ESL Capability
- Adapter abstraction and hardware matrix
- PAwR scheduler, payload queueing, retry semantics
- ESL-focused APIs and HA entities/services

Deliverable:
- PAwR/ESL capability on supported dongles with health and observability

### Phase 6 (12-18 months): OSS Maturity and Ecosystem
- Public beta with installation guide and migration guides
- CI for lint/test/package/release
- Community contribution workflows and profile registry

Deliverable:
- Community-usable open-source platform with clear onboarding

## Immediate Next 30-Day Execution Plan
1. Define capability manifest schema and JSON/YAML validation.
2. Add a lightweight supervisor process around current services.
3. Standardize mode lifecycle commands: validate, plan, apply, health.
4. Scaffold Home Assistant custom integration with config flow.
5. Expose minimal node API endpoints needed by HA.
6. Add first placement/conflict rule set for BLE adapter ownership.
7. Add automated smoke tests for deploy, rollback, and health checks.

## Definition of Success
- New Pi onboarding from HA in under 10 minutes.
- Multi-capability operation on a single Pi without resource thrash.
- Multi-Pi fleet visibility and control from one HA instance.
- Reliable recovery from failed deploys via automated rollback.
- Stable BLE translation and PAwR operation on supported hardware.
