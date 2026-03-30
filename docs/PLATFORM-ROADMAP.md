# Network Isolator Platform Roadmap

## Vision
Build an open-source Raspberry Pi platform managed from Home Assistant, where each Pi can run multiple capabilities concurrently (when compatible), and multiple Pis can be orchestrated as a fleet.

The platform should support:
- Network isolation and traffic logging
- BLE controller workflows (scan, profile, mirror, GATT translation)
- PAwR advertising for ESL (dongle-backed when needed)
- Photo booth workflows (camera + lighting orchestration)
- Generic service hosting where each Pi can run one or more app services under the same control plane
- Wildlife monitoring for edge/off-grid deployments
- Workshop safety monitoring and alert workflows
- Classroom lab console workflows for offline STEM environments

## Product Principles
1. Home Assistant is the control plane.
2. Tornado/Bokeh remains the local expert console for deep diagnostics and advanced workflows.
3. A Pi can run multiple modes concurrently when resource and hardware constraints allow.
4. Multiple Pis are first-class from day one.
5. Deployments must be idempotent, observable, and rollback-safe.
6. Every service has a dedicated config file plus a shared, reusable access profile.
7. Common access/security controls (SSL, direct LAN, tunnel-only, explicit bind) are platform-level primitives reused by every service.

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
- Generic per-node service catalog (what can run on this node)
- Generic per-service access policy controls

Key concepts:
- Node: one managed Pi
- Capability: deployable runtime unit (network isolation, BLE translation, PAwR advertiser)
- Instance: a running capability on a node
- Service: a concrete runtime app instance with its own config file and access profile

### Generic Service Model (New)
Every deployable service follows one shared metadata model so the HA UI can stay consistent across all projects.

Per-service required metadata:
- `service_id` (e.g. `network_isolator`, `ble_gatt_repeater`, `esl_ap`, `photo_booth`)
- `display_name`
- `config_file` (single source of truth path on node)
- `runtime_type` (`systemd`, `python_module`, `container`)
- `health_endpoint` or probe set
- `access_profile` (generic, reusable controls)

Shared access profile fields:
- `mode`: `localhost` | `upstream` | `isolated` | `all` | `explicit`
- `bind_address`: explicit IP/host when mode is `explicit`
- `port`
- `tls_mode`: `off` | `self_signed` | `provided_cert`
- `auth_mode`: `none` | `token` | `mTLS`
- `allowed_origins`
- `exposure_scope`: `lan_only` | `vpn_only` | `tunnel_only`

This gives one reusable HA form for access/security in every service editor.

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
- photo_booth
- wildlife_monitor
- workshop_safety_sentinel
- classroom_lab_console

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

### Hardware Tiers
- Pi Zero W: low-power edge nodes (event capture, lightweight telemetry, duty-cycled service runtime)
- Pi 3/4: balanced nodes for mixed workloads
- Pi 5: high-throughput nodes for heavy BLE/media workloads

Low-power-first design requirement:
- Services intended for Pi Zero W must define a low-power profile (duty cycle, wake triggers, reduced polling, bounded memory footprint).

### Deployment Topologies
- Single-node stacked services: one Pi runs multiple services (e.g. network isolator + photo booth)
- Split-node services: dedicated Pi per service with shared HA orchestration
- Hybrid: core networking on one Pi, media/interaction services on another
- Offline HA cluster mode: local HA controls all nodes without internet dependency

### Node Labels and Capability Tags
Examples:
- role=perimeter
- role=ble-gateway
- hw=ble-native
- hw=silabs-dongle
- feature=pawr
- feature=camera
- feature=gpio-lighting

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
- Add generic service card UI with per-service config file editor and shared access profile editor

Deliverable:
- HA can onboard and manage one Pi end-to-end

### Phase 3 (4-8 months): Fleet and Placement
- Multi-node inventory and grouping
- Placement policies (pin/spread/affinity)
- Rolling deploys and node drain workflows
- Fleet diagnostics and alert surfacing in HA
- Service placement matrix (which services can run on same Pi)

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

### Phase 5b (9-14 months): Photo Booth Capability
- Camera source abstraction (Pi camera, USB camera, HA camera entity, RTSP)
- Light source abstraction (GPIO/PWM, USB/serial, HA light entities)
- Session templates (single shot, burst, timed, event-triggered)
- Output pipeline (local gallery, NAS export, HA media notifications)

Deliverable:
- Photo booth service deployable on same Pi as isolator or on separate Pi, managed from the same HA fleet UI

### Phase 5c (9-15 months): Wildlife Monitor Capability (Edge + Low Power)
- Event-driven sensing pipeline (PIR/camera/audio optional combinations)
- Low-power runtime profile for Pi Zero W (duty-cycled processing, sparse sync windows)
- Energy-aware operation (battery/solar state telemetry, adaptive capture rates)
- Offline-first buffering with deferred upload/sync to HA when link available

Deliverable:
- Wildlife monitor running on Pi Zero W or larger Pis with one shared service model, including low-power and energy-harvesting-aware behavior

### Phase 5d (10-16 months): Workshop Safety Sentinel Capability
- Safety zone and machine-state monitoring workflows
- Rule engine for local alerts + HA escalation
- Optional BLE beacon presence + camera corroboration hooks

Deliverable:
- Generic safety sentinel service deployable on designated workshop nodes with reusable access/security profile

### Phase 5e (10-16 months): Classroom Lab Console Capability
- Multi-station sensor/camera/BLE lab dashboard
- Session templates for experiments, timed runs, and result export
- Offline classroom mode with local HA instance and no cloud dependency

Deliverable:
- Classroom lab service integrated into the same fleet control plane and service editor model

### Phase 5f (10-16 months): Project Incubator Track
Candidate projects using Bokeh over SSL and Pi hardware primitives:
- Edge wildlife monitor (priority)
- Workshop safety sentinel
- Classroom lab console
- Additional future candidates: greenhouse microclimate node, maker-space tool telemetry board

Deliverable:
- Repeatable template for rapidly adding new Pi services with per-service config file and shared access profile UI

## Detailed Service Tracks

### Service Track A: Wildlife Monitor (Priority)
Primary hardware targets:
- Pi Zero W (primary low-power target)
- Pi 3/4/5 (full-feature fallback)

Core features:
- Motion/event-triggered capture (PIR, optional audio threshold)
- Camera snapshots and short burst clips
- Species/event tagging pipeline (manual-first, optional model-assisted)
- Local storage ring buffer with retention policy
- Deferred sync to HA during scheduled network windows

Low-power profile requirements:
- Duty-cycled scheduler with configurable wake interval
- Event-first wake sources (GPIO interrupt, periodic timer)
- Bounded sync windows (for example 2-5 minute upload windows)
- Budget fields in config: max average current, minimum battery threshold, solar charging window

Configuration file expectations:
- File path: `/mnt/isolator/conf/wildlife-monitor.yaml`
- Sections: `power`, `sensors`, `camera`, `capture_policy`, `sync_policy`, `retention`, `alerts`

Acceptance metrics:
- Pi Zero W median idle current within configured budget envelope
- Event capture success rate >= 95 percent for validated trigger set
- Offline buffering survives 7-day no-link period without data loss

### Service Track B: Workshop Safety Sentinel
Primary hardware targets:
- Pi 3/4/5 with optional USB camera and BLE beacon receiver

Core features:
- Zone occupancy and policy checks
- Event-to-alert rules (local siren, HA notification, dashboard alert)
- Optional multi-sensor corroboration (camera + BLE + GPIO switch)

Configuration file expectations:
- File path: `/mnt/isolator/conf/workshop-safety.yaml`
- Sections: `zones`, `rules`, `signal_inputs`, `alert_outputs`, `escalation`

Acceptance metrics:
- Alert latency under 2 seconds for local trigger path
- False-positive rate below defined per-zone thresholds

### Service Track C: Classroom Lab Console
Primary hardware targets:
- Pi 4/5 teacher node, optional Pi Zero/3 student edge nodes

Core features:
- Experiment templates and timed sessions
- Shared dashboards for sensors, BLE, camera feed snapshots
- Per-session artifact export (CSV, image packs, event logs)

Configuration file expectations:
- File path: `/mnt/isolator/conf/classroom-lab.yaml`
- Sections: `stations`, `experiments`, `capture`, `exports`, `permissions`

Acceptance metrics:
- Session creation to active state in under 60 seconds
- Export completion under 30 seconds for standard class session data volume

### Service Track D: Photo Booth (Expanded)
Primary hardware targets:
- Pi 4/5 for high-throughput local media workflows
- Pi 3 for lightweight still capture mode

Core features:
- Multiple source abstraction (Pi camera, USB camera, HA camera, RTSP)
- Lighting abstraction (GPIO/PWM and HA light entities)
- Trigger abstraction (button, schedule, QR flow, HA automation)
- Gallery and post-processing presets

Configuration file expectations:
- File path: `/mnt/isolator/conf/photo-booth.yaml`
- Sections: `sources`, `lighting`, `triggers`, `sessions`, `storage`, `publishing`

Acceptance metrics:
- Trigger-to-capture latency under 1.5 seconds in local mode
- Session stability with 100+ captures without service restart

### Service Track E: Core Platform Generic Access Profile
Applies to every service editor in HA.

Required generic controls:
- Exposure mode (`localhost`, `upstream`, `isolated`, `all`, `explicit`)
- Bind address and port
- TLS mode and certificate source
- Authentication mode
- Origin allowlist
- Tunnel policy and LAN/VPN scope

Validation behavior:
- No apply if profile is invalid for node topology
- Dry-run preview of firewall/listener changes before commit
- Rollback to last known good access profile on health regression

Acceptance metrics:
- Same access editor component reused across all services
- Access profile apply and rollback success >= 99 percent in integration tests

## Milestone Gates (Execution Readiness)

### Gate 1: Generic Service Substrate
- Descriptor schema finalized and versioned
- Config file CRUD and validation APIs available
- Shared access profile API and UI component complete

Exit criteria:
- Two existing services (network isolator + photo booth) managed via one generic service editor

### Gate 2: Multi-Node Orchestration
- Add/remove/manage multiple Pis in one HA integration instance
- Placement checks and conflict reporting active
- Cross-node service assignment and drift reporting active

Exit criteria:
- One mixed deployment running at least three services across two Pis

### Gate 3: Edge Low-Power Readiness
- Wildlife monitor low-power profile validated on Pi Zero W
- Energy-budget fields enforced by scheduler and runtime guardrails
- Offline sync strategy tested with intermittent connectivity

Exit criteria:
- 72-hour field simulation with no data corruption and bounded power draw

### Phase 6 (12-18 months): OSS Maturity and Ecosystem
- Public beta with installation guide and migration guides
- CI for lint/test/package/release
- Community contribution workflows and profile registry

Deliverable:
- Community-usable open-source platform with clear onboarding

## Immediate Next 30-Day Execution Plan
1. Add generic service descriptor schema (service metadata + config file + access profile).
2. Implement reusable access profile form in HA (SSL/direct/tunnel/bind/auth) and bind it to service descriptors.
3. Add per-service config file CRUD API in supervisor with validation hooks.
4. Extend scheduler with service-level placement constraints and resource checks.
5. Add initial descriptors for: network isolator, BLE GATT repeater, ESL AP, photo booth.
6. Add node feature discovery for cameras, BLE adapters, and lighting backends.
7. Add smoke tests for multi-node add/remove, per-service config writes, and access profile apply.
8. Draft `wildlife_monitor` descriptor with Pi Zero W low-power profile + energy budget fields.
9. Define a common low-power manifest extension (`duty_cycle`, `wake_sources`, `max_avg_current_ma`).
10. Prototype offline HA sync policy for edge nodes with intermittent power/network.

## Definition of Success
- New Pi onboarding from HA in under 10 minutes.
- Multi-capability operation on a single Pi without resource thrash.
- Multi-Pi fleet visibility and control from one HA instance.
- Reliable recovery from failed deploys via automated rollback.
- Stable BLE translation and PAwR operation on supported hardware.
- Any service can be onboarded using the same generic HA UI and per-service config file workflow.
- Access policy changes (SSL/direct/tunnel/auth) apply consistently across all services with one shared model.
- Wildlife monitor can run in a practical low-power mode on Pi Zero W-class hardware.
- Offline HA deployments can orchestrate heterogeneous nodes (network isolator + photo booth + edge sensors) without internet dependency.
