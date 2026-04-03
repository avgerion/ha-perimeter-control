# PerimeterControl Configuration

## Environment Variables for Path Configuration

PerimeterControl supports configurable installation paths via environment variables. This allows deployment flexibility across different systems and environments.

### Base Path Variables

| Variable | Default | Description | Usage |
|----------|---------|-------------|--------|
| `PERIMETER_INSTALL_ROOT` | `/opt/PerimeterControl` | Base installation directory | Contains executables, web files, supervisor code |
| `PERIMETER_STATE_ROOT` | `/mnt/PerimeterControl` | State and configuration directory | Contains config files, capabilities settings |
| `PERIMETER_LOG_ROOT` | `/var/log/PerimeterControl` | Log file directory | Contains service logs, debug files |
| `PERIMETER_TEMP_ROOT` | `/tmp` | Temporary files directory | Used during deployment and updates |
| `PERIMETER_SYSTEMD_ROOT` | `/etc/systemd/system` | SystemD service files location | Service unit files |

### Service Name Configuration

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

## Configuration File Location Priority

The supervisor looks for configuration files in this order:

1. `${PERIMETER_STATE_ROOT}/conf/perimeterControl.conf.yaml`
2. `${PERIMETER_INSTALL_ROOT}/config/perimeterControl.conf.yaml`
3. `${PERIMETER_INSTALL_ROOT}/conf/perimeterControl.conf.yaml`

## Deployment Integration

When using the deployer (`deployer.py`), all these environment variables are respected automatically. Set them in your deployment environment before running:

```python
from your_module.deployer import Deployer
from your_module.ssh_client import SshClient

# Environment variables are automatically picked up
deployer = Deployer(ssh_client, services)
await deployer.deploy()
```

## Backwards Compatibility

If no environment variables are set, the system uses the default paths listed above, maintaining backwards compatibility with existing deployments.

## Security Considerations

- All paths should be owned by root with appropriate permissions
- Log directories need to be writable by service users
- Configuration directories should be readable by the supervisor process
- Temporary directories should have proper cleanup policies
