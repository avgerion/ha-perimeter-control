# PerimeterControl Configuration

## Configuration Architecture

PerimeterControl has three distinct configuration layers. Each has a clear owner and purpose. Do not mix concerns across layers.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Deployment Constants  (const.py)                          │
│  Owner: Developer / integration code                                 │
│  Set at: Code time                                                   │
│  Contains: Remote paths, service registry (file lists, pip packages, │
│            unit names), default port fallbacks for the deployer,     │
│            shared web file lists                                     │
│  NOT for: User-overridable settings, runtime service behavior        │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Runtime Capability Config  (config/templates/*.yaml)       │
│  Owner: User / operator                                              │
│  Set at: Deploy time — edited by user, deployed to Pi by HA          │
│  Contains: GPIO pins, device lists, network topology, dashboard      │
│            port, log paths, service-specific feature flags           │
│  THIS is the right place for port numbers, because users can         │
│  override them without touching Python code                          │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: Service Descriptors  (service_descriptors/*.yaml)          │
│  Owner: Developer — deployed to Pi by HA, read by Supervisor         │
│  Set at: Deploy time — rendered from SERVICE_REGISTRY at deploy      │
│  Contains: Entity definitions, access profile (port must match       │
│            Layer 2), resource limits, systemd unit name,             │
│            capability entrypoint                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Port Number Authority

**The YAML config template (`config/templates/<service>.yaml`) is the authoritative source for dashboard port numbers.**

This means:
- The user edits the YAML config to change a port (e.g. `dashboard.server.port: 8095`)
- The deployer reads this value and renders it into the service descriptor's `access_profile.port`
- `const.py` `SERVICE_REGISTRY` carries a `port` value only as a **fallback default** used when the YAML config is absent or the key is missing. It must not be treated as the runtime value.
- The service descriptor's `access_profile.port` must always match the config YAML port. The deployer is responsible for keeping them in sync at deploy time.

**Current state:** The deployer reads the port from the YAML config template at deploy time and uses it for the service health check probe. The service descriptor's `access_profile.port` is set to match by the supervisor on the Pi when the service starts.

## Supervisor API URL

The supervisor API URL (`supervisor_api_url` in runtime config) must be rendered at deploy time from the HA config entry (the Pi's host/port). It must **not** be hardcoded in any config template file. Template files that need this value should use the placeholder `{SUPERVISOR_API_URL}` which the deployer resolves from `entry.data[CONF_HOST]` and `entry.data[CONF_SUPERVISOR_PORT]`.

---

## Legacy Environment Variables for Path Configuration

PerimeterControl currently supports configurable installation paths via environment variables for backward compatibility. That compatibility layer still exists, but it should be treated as a boundary input, not as a pattern to extend across Python code.

Project direction:

- Do not add new scattered `os.environ` or `os.getenv` reads in deployers, entities, or service orchestration code.
- Resolve environment overrides once in a dedicated configuration helper, then pass concrete values through constants, config objects, or descriptor metadata.
- When touching existing Python code that binds runtime behavior directly from environment variables, replace those instances instead of copying the pattern into new logic.

### Legacy Base Path Variables

| Variable | Default | Description | Usage |
|----------|---------|-------------|--------|
| `PERIMETER_INSTALL_ROOT` | `/opt/PerimeterControl` | Base installation directory | Contains executables, web files, supervisor code |
| `PERIMETER_STATE_ROOT` | `/mnt/PerimeterControl` | State and configuration directory | Contains config files, capabilities settings |
| `PERIMETER_LOG_ROOT` | `/var/log/PerimeterControl` | Log file directory | Contains service logs, debug files |
| `PERIMETER_TEMP_ROOT` | `/tmp` | Temporary files directory | Used during deployment and updates |
| `PERIMETER_SYSTEMD_ROOT` | `/etc/systemd/system` | SystemD service files location | Service unit files |

### Legacy Service Name Configuration

| Variable | Default | Description | Usage |
|----------|---------|-------------|--------|
| `PERIMETER_SERVICE_PREFIX` | `PerimeterControl` | SystemD service name prefix | Creates services like `PerimeterControl-supervisor.service` |

### Derived Paths

These paths are automatically derived from the base paths above:

- **Web Directory**: `${PERIMETER_INSTALL_ROOT}/web`
- **Scripts Directory**: `${PERIMETER_INSTALL_ROOT}/scripts`  
- **Supervisor Directory**: `${PERIMETER_INSTALL_ROOT}/supervisor`
- **State Directory**: `${PERIMETER_INSTALL_ROOT}/state`
- **Python Virtual Environment**: `${PERIMETER_INSTALL_ROOT}/venv`
- **Configuration Directory**: `${PERIMETER_STATE_ROOT}/conf`
- **Services Descriptors**: `${PERIMETER_STATE_ROOT}/conf/services`

## Usage Examples

### 1. Custom Installation Directory

```bash
# Install to a custom location
export PERIMETER_INSTALL_ROOT="/opt/myproject"
export PERIMETER_STATE_ROOT="/mnt/myproject"
export PERIMETER_SERVICE_PREFIX="MyProject"

# Deploy will now use:
# - /opt/myproject/supervisor
# - /mnt/myproject/conf
# - MyProject-supervisor.service
```

### 2. Development Environment

```bash
# Use local directories for development
export PERIMETER_INSTALL_ROOT="/home/user/perimeter-dev"
export PERIMETER_STATE_ROOT="/home/user/perimeter-config"
export PERIMETER_LOG_ROOT="/home/user/perimeter-logs"
export PERIMETER_SERVICE_PREFIX="PerimeterDev"
```

### 3. Docker Container

```bash
# Configure for containerized deployment  
export PERIMETER_INSTALL_ROOT="/app"
export PERIMETER_STATE_ROOT="/config"
export PERIMETER_LOG_ROOT="/logs"
export PERIMETER_TEMP_ROOT="/tmp"
```

## SystemD Service Configuration

The supervisor service file is generated from a template and uses these environment variables. The template is located at:

`PerimeterControl-supervisor.service.template`

During deployment, the template is rendered with the current environment variable values and installed as a proper systemd service unit.

For new code, keep this translation at the template/configuration boundary. Do not reach back into environment variables from unrelated Python call sites just to recover the same values later.

## Configuration File Location Priority

The supervisor looks for configuration files in this order:

1. `${PERIMETER_STATE_ROOT}/conf/perimeterControl.conf.yaml`
2. `${PERIMETER_INSTALL_ROOT}/config/perimeterControl.conf.yaml`
3. `${PERIMETER_INSTALL_ROOT}/conf/perimeterControl.conf.yaml`

## Descriptor Path Normalization

Some capability descriptors ship with environment-style fallback syntax in source control, but the deployer must write concrete paths on the Pi. In particular, `gpio_control` must end up with:

- `/mnt/PerimeterControl/conf/gpio-control.yaml`

The deployer now normalizes that path during service descriptor installation so the supervisor does not persist a literal `${...}` string and start the capability with zero GPIO entities.

This matters because the Home Assistant integration reads capability availability from the supervisor API, and a descriptor that points at a non-existent config file will still appear "active" while publishing no entities.

## Replacement Rule For Python Code

When you encounter Python code like this:

```python
service_id = os.environ.get("PERIMETERCONTROL_GPIO_CONTROL_SERVICE", "gpio_control")
```

replace the instance rather than extending it. Preferred replacements are:

- a constant in `const.py` or another single configuration module
- a value loaded from `get_remote_path_config()` or an equivalent helper
- metadata stored in `_DASHBOARD_SERVICE_DEFS`, `SERVICE_REGISTRY` (always import from `const.py`), or a service descriptor

The goal is that Python behavior comes from one resolved configuration source, not from repeated environment lookups spread across the codebase.

## Deployment Integration

When using the deployer (`deployer.py`), the current compatibility layer still respects these environment variables through the centralized path configuration helpers. Do not add new direct environment lookups elsewhere in Python just because deployment already supports them.

```python
from your_module.deployer import Deployer
from your_module.ssh_client import SshClient

# Existing compatibility helpers still pick up environment overrides
deployer = Deployer(ssh_client, services)
await deployer.deploy()
```

## Backwards Compatibility

If no environment variables are set, the system uses the default paths listed above, maintaining backwards compatibility with existing deployments. New code should preserve that compatibility through centralized helpers instead of adding new call sites to `os.environ`.

## Security Considerations

- All paths should be owned by root with appropriate permissions
- Log directories need to be writable by service users
- Configuration directories should be readable by the supervisor process
- Temporary directories should have proper cleanup policies
