"""Base deployment functionality shared across all service deployers.

Provides core deployment infrastructure including SSH operations, 
system checks, file upload, and common installation phases.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import (
    PHASE_INSTALL,
    PHASE_PREFLIGHT,
    PHASE_RESTART,
    PHASE_SUPERVISOR,
    PHASE_UPLOAD,
    PHASE_VERIFY,
    REMOTE_CONF_DIR,
    REMOTE_LOG_ROOT,
    REMOTE_SCRIPTS_DIR,
    REMOTE_SERVICES_DIR,
    REMOTE_SUPERVISOR_DIR,
    REMOTE_SYSTEMD_ROOT,
    REMOTE_TEMP_ROOT,
    REMOTE_VENV,
    REMOTE_WEB_DIR,
    SYSTEMD_DASHBOARD,
    SYSTEMD_SERVICE_PREFIX,
    SYSTEMD_SUPERVISOR,
    get_install_directories,
    get_remote_path_config,
)
from .service_descriptor import ServiceDescriptor
from .ssh_client import SshClient, SshCommandError

_LOGGER = logging.getLogger(__name__)

# Component directory paths
_COMPONENT_DIR = Path(__file__).parent
_SERVER_FILES_DIR = _COMPONENT_DIR / "remote_services" / "dashboard_web"
_SUPERVISOR_DIR = _COMPONENT_DIR / "remote_services" / "supervisor"
_SERVICE_DESCRIPTORS_DIR = _COMPONENT_DIR / "service_descriptors"
_SYSTEM_SERVICES_DIR = _COMPONENT_DIR / "system_services"
_SCRIPTS_DIR = _COMPONENT_DIR / "scripts"
_CONFIG_DIR = _COMPONENT_DIR / "config"


async def _render_service_template(template_path: Path) -> str:
    """Render a systemd service template with configurable paths."""
    if not template_path.exists():
        raise FileNotFoundError(f"Service template not found: {template_path}")
    
    template_content = await asyncio.to_thread(template_path.read_text, encoding="utf-8")
    path_config = get_remote_path_config()
    
    try:
        return template_content.format(**path_config)
    except KeyError as e:
        raise ValueError(f"Missing template variable {e} in {template_path}")


def _get_install_commands() -> list[str]:
    """Generate installation commands using configurable paths."""
    dirs = get_install_directories()
    commands = [f"sudo mkdir -p {d}" for d in dirs]
    
    # Add ownership commands for directories that need root ownership
    path_config = get_remote_path_config()
    commands.extend([
        f"sudo chown root:root {path_config['LOG_ROOT']}",
        f"sudo chown root:root {path_config['STATE_ROOT']}",
        f"sudo chmod 755 {path_config['LOG_ROOT']}",
    ])
    
    return commands


def _build_install_script() -> str:
    """Build complete install script for atomic deployment."""
    commands = _get_install_commands()
    
    # Add file installation commands
    commands.extend([
        f"sudo cp {REMOTE_TEMP_ROOT}/*.py {REMOTE_WEB_DIR}/ 2>/dev/null || true",
        f"sudo cp {REMOTE_TEMP_ROOT}/*.sh {REMOTE_SCRIPTS_DIR}/ 2>/dev/null || true",
        f"sudo chmod +x {REMOTE_SCRIPTS_DIR}/*.sh 2>/dev/null || true",
    ])
    
    return "; ".join(commands)


@dataclass
class DeployProgress:
    phase: str
    message: str
    percent: int = 0
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None


ProgressCallback = Callable[[DeployProgress], None]


class BaseDeployer:
    """Base deployer with core deployment infrastructure."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._cb = progress_cb or (lambda p: None)

    def _emit(self, phase: str, message: str, percent: int = 0) -> None:
        _LOGGER.debug("[%s] %s", phase, message)
        self._cb(DeployProgress(phase=phase, message=message, percent=percent))

    def _emit_error(self, phase: str, message: str) -> DeployProgress:
        _LOGGER.error("[%s] %s", phase, message)
        p = DeployProgress(phase=phase, message=message, error=message)
        self._cb(p)
        return p

    async def check_system_resources(self, required_cpu: float = 0.2, required_memory: int = 128, required_disk: int = 100) -> None:
        """Check system resources before deployment to prevent failures."""
        self._emit(PHASE_PREFLIGHT, "Checking system resources...", 1)
        
        try:
            resource_check_script = """
# Check CPU cores
CPU_CORES=$(nproc 2>/dev/null || echo "1")
echo "CPU_CORES=$CPU_CORES"

# Check available memory (in MB)
MEMORY_MB=$(awk '/MemAvailable:/ {printf "%.0f", $2/1024}' /proc/meminfo 2>/dev/null || echo "512")
echo "MEMORY_MB=$MEMORY_MB"

# Check available disk space in /tmp and /opt (in MB)  
TMP_SPACE_MB=$(df /tmp | awk 'NR==2 {printf "%.0f", $4/1024}')
OPT_SPACE_MB=$(df /opt | awk 'NR==2 {printf "%.0f", $4/1024}')
echo "TMP_SPACE_MB=$TMP_SPACE_MB"
echo "OPT_SPACE_MB=$OPT_SPACE_MB"

# Check system load
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{gsub(/,/, ""); print $1}')
echo "LOAD_AVG=$LOAD_AVG"

# Check if systemd is available
if command -v systemctl >/dev/null 2>&1; then
    echo "SYSTEMD=available"
else
    echo "SYSTEMD=missing"
fi

# Check if we have sudo access
if sudo -n true 2>/dev/null; then
    echo "SUDO=available"
else
    echo "SUDO=needs_password"
fi
"""
            
            self._emit(PHASE_PREFLIGHT, "Gathering system information...", 2)
            resource_output = await self._client.async_run(resource_check_script)
            
            # Parse the output
            resources = {}
            for line in resource_output.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    resources[key] = value
            
            _LOGGER.debug("System resources detected: %s", resources)
            
            self._emit(PHASE_PREFLIGHT, "Validating resource requirements...", 3)
            
            # Check CPU cores
            cpu_cores = float(resources.get('CPU_CORES', 1))
            if cpu_cores < required_cpu:
                raise SshCommandError(
                    "resource_check",
                    1,
                    f"Insufficient CPU cores: available {cpu_cores}, required {required_cpu:.1f}"
                )
            
            # Check available memory
            memory_mb = float(resources.get('MEMORY_MB', 0))
            if memory_mb < required_memory:
                raise SshCommandError(
                    "resource_check", 
                    1,
                    f"Insufficient memory: available {memory_mb:.0f}MB, required {required_memory:.0f}MB"
                )
            
            # Check disk space
            tmp_space_mb = float(resources.get('TMP_SPACE_MB', 0))
            opt_space_mb = float(resources.get('OPT_SPACE_MB', 0))
            upload_space_required = 50  # Estimated upload size in MB
            
            if tmp_space_mb < upload_space_required:
                raise SshCommandError(
                    "resource_check",
                    1,
                    f"Insufficient /tmp space: available {tmp_space_mb:.0f}MB, required {upload_space_required}MB"
                )
            
            if opt_space_mb < required_disk:
                raise SshCommandError(
                    "resource_check",
                    1,
                    f"Insufficient /opt space: available {opt_space_mb:.0f}MB, required {required_disk:.0f}MB"
                )
            
            # Check system load (warn if too high, but don't fail)
            load_avg = float(resources.get('LOAD_AVG', 0))
            if load_avg > cpu_cores * 2:
                _LOGGER.warning("High system load detected: %.2f (CPU cores: %.0f). Deployment may be slow.", 
                              load_avg, cpu_cores)
                self._emit(PHASE_PREFLIGHT, f"High system load detected ({load_avg:.1f}), continuing anyway...", 4)
            
            # Check systemd availability
            if resources.get('SYSTEMD') != 'available':
                raise SshCommandError(
                    "resource_check",
                    1,
                    "systemctl command not available. This system may not use systemd."
                )
            
            # Check sudo access
            if resources.get('SUDO') != 'available':
                _LOGGER.warning("Sudo access may require password. Deployment may prompt for password.")
                self._emit(PHASE_PREFLIGHT, "Sudo access may require password prompt...", 4)
            
            _LOGGER.info("Resource check passed - CPU: %.1f cores, Memory: %.0fMB, Disk: /tmp %.0fMB /opt %.0fMB", 
                        cpu_cores, memory_mb, tmp_space_mb, opt_space_mb)
            self._emit(PHASE_PREFLIGHT, "System resources validated successfully", 4)
            
        except SshCommandError:
            raise
        except Exception as exc:
            raise SshCommandError("resource_check", 1, f"Resource check failed: {exc}") from exc

    async def phase_preflight(self, required_cpu: float = 0.2, required_memory: int = 128, required_disk: int = 100) -> None:
        """Common preflight checks for all deployers."""
        await self.check_system_resources(required_cpu, required_memory, required_disk)
        
        self._emit(PHASE_PREFLIGHT, "Verifying Python interpreter and environment...", 5)
        out = await self._client.async_run(
            "set -e; "
            "python3 --version && echo PYTHON_OK; "
            f"[ -x {REMOTE_VENV}/bin/python3 ] && echo VENV_OK "
            "|| echo VENV_MISSING; "
            f"[ -d {REMOTE_WEB_DIR} ] && echo WEBDIR_OK || echo WEBDIR_MISSING"
        )
        
        # Check if we need to create the venv
        if "VENV_MISSING" in out:
            self._emit(PHASE_PREFLIGHT, "Creating Python virtual environment...", 7)
            await self._client.async_run(
                f"sudo mkdir -p $(dirname {REMOTE_VENV}) && "
                f"cd $(dirname {REMOTE_VENV}) && "
                f"sudo python3 -m venv --system-site-packages $(basename {REMOTE_VENV})"
            )
            self._emit(PHASE_PREFLIGHT, "Virtual environment created", 8)
        
        # Ensure web directory exists
        if "WEBDIR_MISSING" in out:
            self._emit(PHASE_PREFLIGHT, "Creating web directory...", 9)
            await self._client.async_run(f"sudo mkdir -p {REMOTE_WEB_DIR}")
            
        self._emit(PHASE_PREFLIGHT, "Preflight passed", 10)

    async def phase_upload_files(self, files_to_upload: dict[str, list[str]]) -> None:
        """Upload files for deployment.
        
        Args:
            files_to_upload: Dict with 'web' and 'scripts' keys containing file lists
        """
        self._emit(PHASE_UPLOAD, "Uploading service files...", 15)
        
        web_files = files_to_upload.get('web', [])
        script_files = files_to_upload.get('scripts', [])
        total = len(web_files) + len(script_files)
        
        if not total:
            self._emit(PHASE_UPLOAD, "No files to upload", 30)
            return
        
        # Upload web files from dashboard_web directory
        for i, fname in enumerate(web_files):
            src = _SERVER_FILES_DIR / fname
            if not src.exists():
                _LOGGER.warning("Web file not found, skipping: %s", src)
                continue
            await self._client.async_put_file(src, f"{REMOTE_TEMP_ROOT}/{fname}")
            pct = 15 + int(15 * (i + 1) / len(web_files))
            self._emit(PHASE_UPLOAD, f"Uploaded {fname}", pct)
        
        # Upload script files from scripts directory
        for i, fname in enumerate(script_files):
            src = _SCRIPTS_DIR / fname
            if not src.exists():
                _LOGGER.warning("Script file not found, skipping: %s", src)
                continue
            await self._client.async_put_file(src, f"{REMOTE_TEMP_ROOT}/{fname}")
            pct = 30 + int(15 * (i + 1) / len(script_files))
            self._emit(PHASE_UPLOAD, f"Uploaded {fname}", pct)

    async def phase_install(self) -> None:
        """Install uploaded files into active directories."""
        self._emit(PHASE_INSTALL, "Installing files into active directories...", 45)
        install_script = _build_install_script()
        await self._client.async_run_b64(install_script)
        self._emit(PHASE_INSTALL, "Files installed", 55)

    async def phase_config(self, config_files: list[str]) -> None:
        """Deploy configuration files to their expected locations."""
        self._emit(PHASE_INSTALL, "Deploying configuration files...", 57)
        
        for config_file_name in config_files:
            config_file = _CONFIG_DIR / config_file_name
            if config_file.exists():
                try:
                    _LOGGER.debug("Uploading config file from %s", config_file)
                    await self._client.async_put_file(config_file, f"{REMOTE_TEMP_ROOT}/{config_file_name}")
                    
                    # Ensure target directory exists and move to final location
                    await self._client.async_run(f"sudo mkdir -p {REMOTE_CONF_DIR}")
                    await self._client.async_run(
                        f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{config_file_name} {REMOTE_CONF_DIR}/{config_file_name}"
                    )
                    _LOGGER.debug("Config file %s installed successfully", config_file_name)
                    
                except Exception as exc:
                    _LOGGER.error("Config file %s installation failed: %s", config_file_name, exc)
                    raise
            else:
                _LOGGER.warning("Config file not found, skipping: %s", config_file)

    async def install_python_packages(self, packages: list[str], service_name: str) -> None:
        """Install Python packages for a specific service."""
        if not packages:
            return
            
        self._emit(PHASE_SUPERVISOR, f"Installing {service_name} Python packages...", 70)
        
        # Install packages one by one for better error tracking
        for package in packages:
            try:
                _LOGGER.info("Installing Python package: %s", package)
                await self._client.async_run(
                    f"sudo {REMOTE_VENV}/bin/python3 -m pip install {package}",
                    timeout=300  # 5 minute timeout for package installation
                )
                _LOGGER.info("Successfully installed: %s", package)
            except Exception as exc:
                _LOGGER.error("Failed to install %s: %s", package, exc)
                # Continue with other packages rather than failing completely
                
        _LOGGER.info("Package installation completed for %s", service_name)

    async def deploy_service_descriptors(self, service_ids: list[str]) -> None:
        """Deploy service descriptor files for specified services."""
        self._emit(PHASE_SUPERVISOR, "Deploying service descriptors...", 78)
        
        for service_id in service_ids:
            fname = f"{service_id}.service.yaml"
            src = _SERVICE_DESCRIPTORS_DIR / fname
            if src.exists():
                await self._client.async_put_file(src, f"{REMOTE_TEMP_ROOT}/{fname}")
                await self._client.async_run(
                    f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{fname} {REMOTE_SERVICES_DIR}/{fname}"
                )
            else:
                _LOGGER.warning("Service descriptor not found: %s", src)
                
        self._emit(PHASE_SUPERVISOR, "Service descriptors deployed", 80)

    async def install_systemd_services(self, template_files: list[str]) -> None:
        """Install systemd service templates."""
        self._emit(PHASE_SUPERVISOR, "Installing systemd service units...", 82)
        
        for template_name in template_files:
            template_file = _COMPONENT_DIR / template_name
            if template_file.exists():
                _LOGGER.info("Generating service from template: %s", template_name)
                service_content = await _render_service_template(template_file)
                
                # Write to temporary file and upload
                temp_fd, temp_service_file = await asyncio.to_thread(tempfile.mkstemp, suffix='.service')
                try:
                    await asyncio.to_thread(lambda: os.write(temp_fd, service_content.encode()))
                    await asyncio.to_thread(os.close, temp_fd)
                    
                    service_name = template_name.replace('.template', '')
                    await self._client.async_put_file(Path(temp_service_file), f"{REMOTE_TEMP_ROOT}/{service_name}")
                    await self._client.async_run(
                        f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{service_name} {REMOTE_SYSTEMD_ROOT}/{service_name}"
                    )
                    await self._client.async_run(f"sudo systemctl daemon-reload")
                    await self._client.async_run(f"sudo systemctl enable {service_name}")
                    _LOGGER.info("Service %s installed and enabled", service_name)
                    
                finally:
                    await asyncio.to_thread(os.unlink, temp_service_file)
            else:
                _LOGGER.warning("Template not found: %s", template_file)
                
        self._emit(PHASE_SUPERVISOR, "Systemd services installed", 85)