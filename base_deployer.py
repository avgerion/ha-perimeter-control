"""Base deployment functionality shared across all service deployers.

Provides core deployment infrastructure including SSH operations, 
system checks, file upload, and common installation phases.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .const import (
    remote_temp_root,
    remote_web_dir,
    remote_scripts_dir,
    remote_venv_dir,
    remote_conf_dir,
    remote_services_dir,
    remote_systemd_root,
    remote_supervisor_dir,
    remote_log_root,
    remote_state_root,
    remote_state_dir,
    remote_install_root,
    get_remote_install_directories,
)
from .service_descriptor import ServiceDescriptor
from .ssh_client import SshClient, SshCommandError

from .const import SERVICE_REGISTRY

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
    from .const import get_remote_path_config
    path_config = get_remote_path_config()
    try:
        return template_content.format(**path_config)
    except KeyError as e:
        raise ValueError(f"Missing template variable {e} in {template_path}")


def _get_install_commands() -> list[str]:
    """Generate installation commands using configurable paths."""
    # Use the authoritative list from const.py so no directory is missed
    dirs = get_remote_install_directories()
    commands = [f"sudo mkdir -p {d}" for d in dirs]
    # Add ownership commands for directories that need root ownership
    commands.extend([
        f"sudo chown root:root {remote_log_root}",
        f"sudo chown root:root {remote_state_root}",
        f"sudo chmod 755 {remote_log_root}",
    ])
    return commands


def _build_install_script() -> str:
    """Build complete install script for atomic deployment."""
    commands = _get_install_commands()
    
    # Add file installation commands
    commands.extend([
        f"sudo cp {remote_temp_root}/*.py {remote_web_dir}/ 2>/dev/null || true",
        f"sudo cp {remote_temp_root}/*.sh {remote_scripts_dir}/ 2>/dev/null || true",
        f"sudo chmod +x {remote_scripts_dir}/*.sh 2>/dev/null || true",
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

    async def check_system_resources(self, required_cpu: float = 0.1, required_memory: int = 64, required_disk: int = 50) -> None:
        """Check system resources before deployment to prevent failures."""
        self._emit("preflight", "Checking system resources...", 1)
        
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
            
            self._emit("preflight", "Gathering system information...", 2)
            resource_output = await self._client.async_run(resource_check_script)
            
            # Parse the output
            resources = {}
            for line in resource_output.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    resources[key] = value
            
            _LOGGER.debug("System resources detected: %s", resources)
            
            self._emit("preflight", "Validating resource requirements...", 3)
            
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
                self._emit("preflight", f"High system load detected ({load_avg:.1f}), continuing anyway...", 4)
            
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
                self._emit("preflight", "Sudo access may require password prompt...", 4)
            
            _LOGGER.info("Resource check passed - CPU: %.1f cores, Memory: %.0fMB, Disk: /tmp %.0fMB /opt %.0fMB", 
                        cpu_cores, memory_mb, tmp_space_mb, opt_space_mb)
            self._emit("preflight", "System resources validated successfully", 4)
            
        except SshCommandError:
            raise
        except Exception as exc:
            raise SshCommandError("resource_check", 1, f"Resource check failed: {exc}") from exc

    async def phase_preflight(self, required_cpu: float = 0.1, required_memory: int = 64, required_disk: int = 50) -> None:
        """Common preflight checks for all deployers."""
        await self.check_system_resources(required_cpu, required_memory, required_disk)
        
        self._emit("preflight", "Verifying Python interpreter and environment...", 5)
        out = await self._client.async_run(
            "set -e; "
            "python3 --version && echo PYTHON_OK; "
            f"[ -x {remote_venv_dir}/bin/python3 ] && echo VENV_OK "
            "|| echo VENV_MISSING; "
            f"[ -d {remote_web_dir} ] && echo WEBDIR_OK || echo WEBDIR_MISSING"
        )
        
        # Check if we need to create the venv
        if "VENV_MISSING" in out:
            self._emit("preflight", "Creating Python virtual environment...", 7)
            await self._client.async_run(
                f"sudo mkdir -p $(dirname {remote_venv_dir}) && "
                f"cd $(dirname {remote_venv_dir}) && "
                f"sudo python3 -m venv --system-site-packages $(basename {remote_venv_dir})"
            )
            self._emit("preflight", "Virtual environment created", 8)
        
        # Ensure web directory exists
        if "WEBDIR_MISSING" in out:
            self._emit("preflight", "Creating web directory...", 9)
            await self._client.async_run(f"sudo mkdir -p {remote_web_dir}")
            
        self._emit("preflight", "Preflight passed", 10)

    async def phase_upload_files(self, files_to_upload: dict[str, list[str]]) -> None:
        """Upload files for deployment.
        
        Args:
            files_to_upload: Dict with 'web' and 'scripts' keys containing file lists
        """
        self._emit("upload", "Uploading service files...", 15)
        
        web_files = files_to_upload.get('web', [])
        script_files = files_to_upload.get('scripts', [])
        total = len(web_files) + len(script_files)
        
        if not total:
            self._emit("upload", "No files to upload", 30)
            return
        
        # Upload web files from dashboard_web directory
        for i, fname in enumerate(web_files):
            src = _SERVER_FILES_DIR / fname
            if not src.exists():
                _LOGGER.warning("Web file not found, skipping: %s", src)
                continue
            await self._client.async_put_file(src, f"{remote_temp_root}/{fname}")
            pct = 15 + int(15 * (i + 1) / len(web_files))
            self._emit("upload", f"Uploaded {fname}", pct)
        
        # Upload script files from scripts directory
        for i, fname in enumerate(script_files):
            src = _SCRIPTS_DIR / fname
            if not src.exists():
                _LOGGER.warning("Script file not found, skipping: %s", src)
                continue
            await self._client.async_put_file(src, f"{remote_temp_root}/{fname}")
            pct = 30 + int(15 * (i + 1) / len(script_files))
            self._emit("upload", f"Uploaded {fname}", pct)

    async def phase_install(self) -> None:
        """Install uploaded files into active directories."""
        self._emit("install", "Installing files into active directories...", 45)
        install_script = _build_install_script()
        await self._client.async_run_b64(install_script)
        self._emit("install", "Files installed", 55)

    async def phase_config(self, config_files: list[str]) -> None:
        """Deploy configuration files to their expected locations."""
        self._emit("install", "Deploying configuration files...", 57)
        
        for config_file_name in config_files:
            config_file = _CONFIG_DIR / config_file_name
            if config_file.exists():
                try:
                    _LOGGER.debug("Uploading config file from %s", config_file)
                    await self._client.async_put_file(config_file, f"{remote_temp_root}/{config_file_name}")
                    
                    # Ensure target directory exists and move to final location
                    await self._client.async_run(f"sudo mkdir -p {remote_conf_dir}")
                    await self._client.async_run(
                        f"sudo install -o root -g root -m 0644 {remote_temp_root}/{config_file_name} {remote_conf_dir}/{config_file_name}"
                    )
                    _LOGGER.debug("Config file %s installed successfully", config_file_name)
                    
                except Exception as exc:
                    _LOGGER.error("Config file %s installation failed: %s", config_file_name, exc)
                    raise
            else:
                _LOGGER.warning("Config file not found, skipping: %s", config_file)

    async def install_python_packages(self, packages: list[str], service_name: str) -> None:
        """Install Python packages for a specific service with improved logging."""
        if not packages:
            return

        self._emit("supervisor", f"Installing {service_name} Python packages...", 70)

        for package in packages:
            try:
                cmd = f"sudo {remote_venv_dir}/bin/python3 -m pip install {package}"
                _LOGGER.info("Installing Python package: %s", package)
                _LOGGER.debug("Running command: %s", cmd)
                result = await self._client.async_run(cmd)
                if result and result.strip():
                    _LOGGER.debug("pip output for %s: %s", package, result.strip())
                _LOGGER.info("Successfully installed: %s", package)
            except Exception as exc:
                _LOGGER.error("Failed to install %s: %s", package, exc, exc_info=True)
                # Continue with other packages rather than failing completely

        _LOGGER.info("Package installation completed for %s", service_name)

    async def deploy_service_descriptors(self, service_ids: list[str], auto_entities: dict[str, list] | None = None) -> None:
        """Deploy service descriptor files for specified services."""
        self._emit("supervisor", "Deploying service descriptors...", 78)
        auto_entities = auto_entities or {}
        
        for service_id in service_ids:
            fname = f"{service_id}.service.yaml"
            src = _SERVICE_DESCRIPTORS_DIR / fname
            if src.exists():
                descriptor_text = await asyncio.to_thread(src.read_text, encoding="utf-8")
                descriptor_data = await asyncio.to_thread(yaml.safe_load, descriptor_text) or {}

                service_info = SERVICE_REGISTRY.get(service_id, {})
                config_target = service_info.get("config_target")
                if config_target:
                    spec = descriptor_data.setdefault("spec", {})
                    config_file = spec.setdefault("config_file", {})
                    config_file["path"] = f"/mnt/PerimeterControl/conf/{config_target}"

                # Inject auto-detected entities (from hardware detection) into the descriptor.
                # The supervisor reads spec.entities to publish them to Home Assistant.
                if service_id in auto_entities and auto_entities[service_id]:
                    spec = descriptor_data.setdefault("spec", {})
                    spec["entities"] = auto_entities[service_id]
                    _LOGGER.info("Injected %d auto-entities into descriptor for %s",
                                 len(auto_entities[service_id]), service_id)

                rendered_text = await asyncio.to_thread(
                    yaml.safe_dump,
                    descriptor_data,
                    sort_keys=False,
                    allow_unicode=False,
                )
                await self._client.async_put_bytes(rendered_text.encode("utf-8"), f"{remote_temp_root}/{fname}")
                await self._client.async_run(
                    f"sudo install -o root -g root -m 0644 {remote_temp_root}/{fname} {remote_services_dir}/{fname}"
                )
            else:
                _LOGGER.warning("Service descriptor not found: %s", src)
                
        self._emit("supervisor", "Service descriptors deployed", 80)

    async def install_systemd_services(self, template_files: list[str]) -> None:
        """Install systemd service templates."""
        self._emit("supervisor", "Installing systemd service units...", 82)
        
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
                    
                    # systemd unit names are case-sensitive and conventionally lowercase.
                    # The template filename uses PascalCase; normalise to lowercase so
                    # the uploaded filename matches what _build_supervisor_install_script
                    # and all `systemctl` calls expect.
                    pascal_name = template_name.replace('.template', '')
                    service_name = pascal_name.lower()
                    await self._client.async_put_file(Path(temp_service_file), f"{remote_temp_root}/{service_name}")
                    await self._client.async_run(
                        f"sudo install -o root -g root -m 0644 {remote_temp_root}/{service_name} {remote_systemd_root}/{service_name}"
                    )
                    # Disable and remove any old PascalCase unit that may still be on the Pi
                    if pascal_name != service_name:
                        await self._client.async_run(
                            f"sudo systemctl disable --now {pascal_name} 2>/dev/null || true"
                        )
                        await self._client.async_run(
                            f"sudo rm -f {remote_systemd_root}/{pascal_name}"
                        )
                    await self._client.async_run(f"sudo systemctl daemon-reload")
                    await self._client.async_run(f"sudo systemctl enable {service_name}")
                    _LOGGER.info("Service %s installed and enabled", service_name)
                    
                finally:
                    await asyncio.to_thread(os.unlink, temp_service_file)
            else:
                _LOGGER.warning("Template not found: %s", template_file)
                
        self._emit("supervisor", "Systemd services installed", 85)