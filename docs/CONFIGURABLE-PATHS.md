# PerimeterControl Configuration

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
- metadata stored in `_DASHBOARD_SERVICE_DEFS`, `SERVICE_REGISTRY`, or a service descriptor

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
