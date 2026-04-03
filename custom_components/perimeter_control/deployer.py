"""Deploy Perimeter Control backend files to a Pi node over SSH.

Mirrors the logic of deploy-dashboard-web.ps1 but as an async Python class,
usable from within Home Assistant or the CLI.

Phases:
  1. preflight  — verify python3, systemd, venv presence
  2. upload     — SCP web/ and scripts/ files to /tmp
  3. install    — atomic install into /opt/isolator via `sudo install`
  4. supervisor — install supervisor package + service unit
  5. restart    — restart systemd services
  6. verify     — poll service health
"""
from __future__ import annotations

import asyncio
import logging
import os
import tarfile
import tempfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .const import (
    APT_DEPENDENCY_GROUPS,
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
    SYSTEMD_SUPERVISOR,
    get_install_directories,
    get_remote_path_config,
)
from .service_descriptor import ServiceDescriptor, load_service_descriptors
from .ssh_client import SshClient, SshCommandError

_LOGGER = logging.getLogger(__name__)

# Resolved at runtime relative to this file (inside the HA custom component)
_COMPONENT_DIR = Path(__file__).parent
_SERVER_FILES_DIR = _COMPONENT_DIR / "remote_services" / "dashboard_web"
_SUPERVISOR_DIR = _COMPONENT_DIR / "remote_services" / "supervisor"
_SERVICE_DESCRIPTORS_DIR = _COMPONENT_DIR / "service_descriptors"
_SYSTEM_SERVICES_DIR = _COMPONENT_DIR / "system_services"
_SCRIPTS_DIR = _COMPONENT_DIR / "scripts"
_CONFIG_DIR = _COMPONENT_DIR / "config"


def _render_service_template(template_path: Path) -> str:
    """Render a systemd service template with configurable paths."""
    if not template_path.exists():
        raise FileNotFoundError(f"Service template not found: {template_path}")
    
    template_content = template_path.read_text(encoding="utf-8")
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


class Deployer:
    """Deploy backend to a single Pi node."""

    def __init__(
        self,
        client: SshClient,
        selected_services: list[str],
        service_descriptors: dict[str, ServiceDescriptor] | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._selected_services = selected_services
        self._service_descriptors = service_descriptors or {}
        self._cb = progress_cb or (lambda p: None)

    def _emit(self, phase: str, message: str, percent: int = 0) -> None:
        _LOGGER.debug("[%s] %s", phase, message)
        self._cb(DeployProgress(phase=phase, message=message, percent=percent))

    def _emit_error(self, phase: str, message: str) -> DeployProgress:
        _LOGGER.error("[%s] %s", phase, message)
        p = DeployProgress(phase=phase, message=message, error=message)
        self._cb(p)
        return p

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def async_deploy(self) -> bool:
        """Run all deploy phases. Returns True on success."""
        deployment_id = id(self)  # Unique ID for this deployment instance
        _LOGGER.warning("=== DEPLOYMENT STARTED === (ID: %s)", deployment_id)
        _LOGGER.warning("async_deploy() method called - deployment is being triggered (ID: %s)", deployment_id)
        self._emit(PHASE_PREFLIGHT, "Starting deployment process...", 0)
        
        try:
            _LOGGER.warning("Starting deployment phases... (ID: %s)", deployment_id)
            await self._phase_preflight()
            await self._phase_upload()
            await self._phase_install()
            await self._phase_config()
            await self._phase_supervisor()
            await self._phase_system_services()
            await self._phase_test_dashboard()
            await self._phase_restart()
            await self._phase_verify()
            _LOGGER.warning("=== DEPLOYMENT COMPLETED SUCCESSFULLY === (ID: %s)", deployment_id)
        except SshCommandError as exc:
            _LOGGER.error(f"SSH command failed during deployment (ID: %s): {exc}", deployment_id)
            self._emit_error(exc.command[:40], str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error(f"Unexpected deployment error (ID: %s): {exc}", deployment_id)
            self._emit_error("deploy", f"Unexpected error: {exc}")
            return False
        return True

    # ------------------------------------------------------------------
    # Resource Pre-check
    # ------------------------------------------------------------------

    async def _check_system_resources(self) -> None:
        """Check system resources before deployment to prevent failures."""
        self._emit(PHASE_PREFLIGHT, "Checking system resources...", 1)
        
        try:
            # Get system information in one SSH call for efficiency
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
            
            # Calculate resource requirements for selected services
            total_cpu_required = 0.5  # Base supervisor requirement
            total_memory_required = 256  # Base memory in MB
            total_disk_required = 100  # Base disk space in MB
            
            for service_id in self._selected_services:
                if service_id in self._service_descriptors:
                    service_desc = self._service_descriptors[service_id]
                    service_resources = service_desc.resources or {}
                    total_cpu_required += service_resources.get('cpu_cores', 0.1)
                    total_memory_required += service_resources.get('memory_mb', 64)
                    total_disk_required += service_resources.get('disk_mb', 20)
            
            self._emit(PHASE_PREFLIGHT, "Validating resource requirements...", 3)
            
            # Check CPU cores
            cpu_cores = float(resources.get('CPU_CORES', 1))
            if cpu_cores < total_cpu_required:
                raise SshCommandError(
                    "resource_check",
                    f"Insufficient CPU cores: available {cpu_cores}, required {total_cpu_required:.1f}"
                )
            
            # Check available memory
            memory_mb = float(resources.get('MEMORY_MB', 0))
            if memory_mb < total_memory_required:
                raise SshCommandError(
                    "resource_check", 
                    f"Insufficient memory: available {memory_mb:.0f}MB, required {total_memory_required:.0f}MB"
                )
            
            # Check disk space in /tmp (for uploads)
            tmp_space_mb = float(resources.get('TMP_SPACE_MB', 0))
            upload_space_required = 50  # Estimated upload size in MB
            if tmp_space_mb < upload_space_required:
                raise SshCommandError(
                    "resource_check",
                    f"Insufficient /tmp space: available {tmp_space_mb:.0f}MB, required {upload_space_required}MB"
                )
            
            # Check disk space in /opt (for installation)
            opt_space_mb = float(resources.get('OPT_SPACE_MB', 0))
            if opt_space_mb < total_disk_required:
                raise SshCommandError(
                    "resource_check",
                    f"Insufficient /opt space: available {opt_space_mb:.0f}MB, required {total_disk_required:.0f}MB"
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
                    "systemctl command not available. This system may not use systemd."
                )
            
            # Check sudo access
            if resources.get('SUDO') != 'available':
                _LOGGER.warning("Sudo access may require password. Deployment may prompt for password.")
                self._emit(PHASE_PREFLIGHT, "Sudo access may require password prompt...", 4)
            
            # Log success message with resource summary
            _LOGGER.info("Resource check passed - CPU: %.1f cores, Memory: %.0fMB, Disk: /tmp %.0fMB /opt %.0fMB", 
                        cpu_cores, memory_mb, tmp_space_mb, opt_space_mb)
            self._emit(PHASE_PREFLIGHT, "System resources validated successfully", 4)
            
        except SshCommandError:
            # Re-raise SSH command errors (these include our resource check failures)
            raise
        except Exception as exc:
            # Convert other exceptions to SSH command errors for consistent handling
            raise SshCommandError("resource_check", f"Resource check failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Phase 1: Preflight
    # ------------------------------------------------------------------

    async def _phase_preflight(self) -> None:
        # First check system resources before proceeding
        await self._check_system_resources()
        
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

    # ------------------------------------------------------------------
    # Phase 2: Upload
    # ------------------------------------------------------------------

    async def _phase_upload(self) -> None:
        self._emit(PHASE_UPLOAD, "Uploading server files...", 15)
        web_files = [
            "dashboard.py",
            "layouts.py",
            "callbacks.py",
            "data_sources.py",
        ]
        script_files = [
            "ble-scanner-v2.py",
            "ble-sniffer.py",
            "ble-debug.sh",
            "ble-proxy-profiler.py",
            "ble-gatt-mirror.py",
            "apply-rules.py",
            "network-topology.py",
            "topology_config.py",
        ]
        total = len(web_files) + len(script_files)
        
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

    # ------------------------------------------------------------------
    # Phase 3: Install
    # ------------------------------------------------------------------

    async def _phase_install(self) -> None:
        self._emit(PHASE_INSTALL, "Installing files into active directories...", 45)
        install_script = _build_install_script()
        await self._client.async_run_b64(install_script)
        self._emit(PHASE_INSTALL, "Files installed", 55)

    # ------------------------------------------------------------------
    # Phase 4: Config  
    # ------------------------------------------------------------------

    async def _phase_config(self) -> None:
        """Deploy configuration files to their expected locations."""
        self._emit(PHASE_INSTALL, "Deploying configuration files...", 57)
        
        # Deploy main config file
        config_file = _CONFIG_DIR / "perimeterControl.conf.yaml"
        if config_file.exists():
            try:
                # Verify file is readable
                file_size = config_file.stat().st_size
                _LOGGER.debug("Config file found: %s (%d bytes)", config_file, file_size)
                
                # Test file readability with async to avoid blocking
                content_preview = await asyncio.to_thread(
                    lambda: config_file.read_text(encoding="utf-8")[:100]
                )
                _LOGGER.debug("Config file readable, preview: %s...", repr(content_preview))
                
                _LOGGER.debug("Uploading config file from %s to %s/perimeterControl.conf.yaml", config_file, REMOTE_TEMP_ROOT)
                # Upload to temp location (this is where it's failing)
                await self._client.async_put_file(config_file, f"{REMOTE_TEMP_ROOT}/perimeterControl.conf.yaml")
                _LOGGER.debug("Config file upload completed successfully")
                
                # Ensure target directory exists and move to final location
                await self._client.async_run(f"sudo mkdir -p {REMOTE_CONF_DIR}")
                await self._client.async_run(f"sudo mv {REMOTE_TEMP_ROOT}/perimeterControl.conf.yaml {REMOTE_CONF_DIR}/")
                await self._client.async_run(f"sudo chown root:root {REMOTE_CONF_DIR}/perimeterControl.conf.yaml")
                await self._client.async_run(f"sudo chmod 644 {REMOTE_CONF_DIR}/perimeterControl.conf.yaml")
                
                _LOGGER.info("Successfully deployed config file: perimeterControl.conf.yaml")
            except Exception as exc:
                _LOGGER.error("Failed to deploy config file %s: %s", config_file, exc, exc_info=True)
                # Don't fail the entire deployment, just log the error and skip config deployment 
                return
        else:
            _LOGGER.warning("Main config file not found: %s (Full path: %s)", config_file, config_file.absolute())
        
        self._emit(PHASE_INSTALL, "Configuration files deployed", 60)

    # ------------------------------------------------------------------
    # Phase 5: Supervisor
    # ------------------------------------------------------------------

    async def _phase_supervisor(self) -> None:
        self._emit(PHASE_SUPERVISOR, "Preparing supervisor package...", 62)
        supervisor_src = _SUPERVISOR_DIR
        if not supervisor_src.exists():
            _LOGGER.warning("supervisor_files/ not found in component dir — skipping supervisor phase")
            return

        # Resolve required apt deps from selected service descriptors
        descriptors = await load_service_descriptors(
            _SERVICE_DESCRIPTORS_DIR, self._selected_services
        )
        apt_groups: set[str] = set()
        for desc in descriptors:
            apt_groups.update(desc.apt_dependency_groups)

        # Install apt packages first with retry logic for dpkg lock contention
        for group in sorted(apt_groups):
            pkgs = APT_DEPENDENCY_GROUPS.get(group, [])
            if pkgs:
                pkg_str = " ".join(pkgs)
                self._emit(PHASE_SUPERVISOR, f"Installing apt group: {group}", 60)
                
                # Retry apt-get install with backoff for dpkg lock issues
                max_retries = 3
                retry_delay = 10  # seconds
                
                for attempt in range(max_retries):
                    try:
                        await self._client.async_run(
                            f"DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq {pkg_str}"
                        )
                        _LOGGER.warning(f"Successfully installed apt group: {group}")
                        break  # Success, exit retry loop
                    except SshCommandError as exc:
                        if "dpkg/lock" in str(exc) or "frontend lock" in str(exc):
                            if attempt < max_retries - 1:
                                _LOGGER.warning(f"Apt lock detected (attempt {attempt+1}/{max_retries}), waiting {retry_delay}s for other apt process to finish...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                continue
                            else:
                                # Persistent apt lock - skip apt packages and proceed with pip 
                                _LOGGER.warning(f"Apt lock persists after {max_retries} attempts - skipping apt packages and proceeding with pip installation")
                                break  # Skip this apt group but continue deployment
                        else:
                            # Different error, re-raise immediately
                            raise

        # Install pip deps
        self._emit(PHASE_SUPERVISOR, "Installing pip dependencies...", 70)
        # Activate venv and install as root (matches systemd service user)
        # Install pip dependencies with debugging
        self._emit(PHASE_SUPERVISOR, "Starting pip dependency installation...", 71)
        
        pip_cmd = (
            f"sudo bash -c '"
            f"source {REMOTE_VENV}/bin/activate && "
            f"pip install aiohttp psutil python-json-logger bokeh pyyaml tornado pandas"
            f"'"
        )
        
        try:
            _LOGGER.warning(f"Executing pip install command: {pip_cmd}")
            result = await self._client.async_run(pip_cmd)
            _LOGGER.warning(f"Pip install completed successfully")
            self._emit(PHASE_SUPERVISOR, "Pip dependencies installed successfully", 72)
        except Exception as e:
            _LOGGER.error(f"Pip install failed: {e}")
            self._emit(PHASE_SUPERVISOR, f"Pip install failed: {e}", 72)
            raise

        # Pack supervisor/ into tar and upload
        self._emit(PHASE_SUPERVISOR, "Uploading supervisor package...", 73)
        tar_bytes = await _pack_directory(supervisor_src, arcname="supervisor")
        await self._client.async_put_bytes(tar_bytes, f"{REMOTE_TEMP_ROOT}/supervisor.tar.gz")

        # Generate systemd service file from template
        service_template = _COMPONENT_DIR / "PerimeterControl-supervisor.service.template"
        if service_template.exists():
            service_content = _render_service_template(service_template)
            # Write to temporary file and upload
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.service') as f:
                f.write(service_content)
                temp_service_file = f.name
            try:
                await self._client.async_put_file(Path(temp_service_file), f"{REMOTE_TEMP_ROOT}/PerimeterControl-supervisor.service")
            finally:
                Path(temp_service_file).unlink(missing_ok=True)
        else:
            # Fallback to static file if template doesn't exist
            service_unit = _COMPONENT_DIR / "PerimeterControl-supervisor.service"
            if service_unit.exists():
                await self._client.async_put_file(service_unit, f"{REMOTE_TEMP_ROOT}/PerimeterControl-supervisor.service")

        # Extract + install on remote via b64 script
        sup_install_script = _build_supervisor_install_script()
        await self._client.async_run_b64(sup_install_script)
        self._emit(PHASE_SUPERVISOR, "Supervisor installed", 77)

        # Deploy service descriptors
        await self._deploy_service_descriptors(descriptors)

    async def _deploy_service_descriptors(
        self, descriptors: list[ServiceDescriptor]
    ) -> None:
        if not descriptors:
            return
        self._emit(PHASE_SUPERVISOR, "Deploying service descriptors...", 78)
        await self._client.async_run(f"sudo mkdir -p {REMOTE_SERVICES_DIR}")
        for desc in descriptors:
            fname = f"{desc.id}.service.yaml"
            src = _SERVICE_DESCRIPTORS_DIR / fname
            if not src.exists():
                _LOGGER.warning("Descriptor not found: %s", src)
                continue
            await self._client.async_put_file(src, f"/tmp/{fname}")
            await self._client.async_run(
                f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{fname} {REMOTE_SERVICES_DIR}/{fname}"
            )
        self._emit(PHASE_SUPERVISOR, "Service descriptors deployed", 80)

    async def _phase_system_services(self) -> None:
        """Deploy systemd service unit files from system_services/ directory."""
        if not _SYSTEM_SERVICES_DIR.exists():
            _LOGGER.warning("system_services/ directory not found, skipping service units")
            return

        self._emit(PHASE_SUPERVISOR, "Installing systemd service units...", 82)
        
        # Find all .service files in system_services/
        service_files = await asyncio.to_thread(lambda: list(_SYSTEM_SERVICES_DIR.glob("*.service")))
        if not service_files:
            _LOGGER.info("No .service files found in system_services/")
            return

        for service_file in service_files:
            # Upload service file
            await self._client.async_put_file(service_file, f"{REMOTE_TEMP_ROOT}/{service_file.name}")
            
            # Install to /etc/systemd/system/
            await self._client.async_run(
                f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{service_file.name} {REMOTE_SYSTEMD_ROOT}/{service_file.name}"
            )
            
            _LOGGER.debug("Installed systemd service: %s", service_file.name)

        # Reload systemd to pick up new service files
        await self._client.async_run("sudo systemctl daemon-reload")
        
        # Enable services (but skip template units which end with @.service)
        for service_file in service_files:
            service_name = service_file.name
            if "@." in service_name:
                # Skip template units - they can't be enabled directly
                _LOGGER.debug("Skipping template unit (cannot enable): %s", service_name)
                continue
            await self._client.async_run(f"sudo systemctl enable {service_name}")
            _LOGGER.debug("Enabled systemd service: %s", service_name)
            
        self._emit(PHASE_SUPERVISOR, "Systemd service units installed", 85)

    async def _phase_test_dashboard(self) -> None:
        """Test dashboard startup before trying to run as systemd service."""
        self._emit(PHASE_SUPERVISOR, "Testing dashboard startup...", 86)
        
        # Make sure log directory is writable
        install_commands = _get_install_commands()
        for cmd in install_commands:
            await self._client.async_run(cmd)
        
        # Test if all required files are present
        required_files = ["dashboard.py", "layouts.py", "callbacks.py", "data_sources.py"]
        for file in required_files:
            check_result = await self._client.async_run(
                f"[ -f {REMOTE_WEB_DIR}/{file} ] && echo FOUND || echo MISSING"
            )
            if "MISSING" in check_result:
                _LOGGER.error("Required file missing: %s", file)
        
        # Test Python import directly
        import_test = await self._client.async_run(
            f"cd {REMOTE_WEB_DIR} && sudo {REMOTE_VENV}/bin/python3 -c '"
            f"import sys; sys.path.insert(0, \".\"); "
            f"try: "
            f"    import dashboard; print(\"IMPORT_SUCCESS\"); "
            f"except Exception as e: "
            f"    print(f\"IMPORT_ERROR: {{e}}\"); "
            f"    import traceback; traceback.print_exc()' 2>&1 || echo FAILED"
        )
        _LOGGER.info("Dashboard import test result: %s", import_test.strip())
        
        # Test if we can at least instantiate the basic components
        component_test = await self._client.async_run(
            f"cd {REMOTE_WEB_DIR} && timeout 10s sudo {REMOTE_VENV}/bin/python3 -c '"
            f"import sys; sys.path.insert(0, \".\"); "
            f"try: "
            f"    import yaml, logging; "
            f"    from bokeh.server.server import Server; "
            f"    print(\"COMPONENTS_OK\"); "
            f"except Exception as e: "
            f"    print(f\"COMPONENT_ERROR: {{e}}\"); "
            f"    import traceback; traceback.print_exc()' 2>&1 || echo TIMEOUT"
        )
        _LOGGER.info("Dashboard components test result: %s", component_test.strip())
        
        self._emit(PHASE_SUPERVISOR, "Dashboard testing complete", 87)

    # ------------------------------------------------------------------
    # Phase 7: Restart
    # ------------------------------------------------------------------

    async def _phase_restart(self) -> None:
        # Start base PerimeterControl service first (dashboard depends on it)
        base_service_exists = await self._client.async_run(
            "systemctl list-unit-files PerimeterControl.service 2>/dev/null | grep -c PerimeterControl || true"
        )
        if base_service_exists.strip() != "0":
            self._emit(PHASE_RESTART, "Starting base PerimeterControl service...", 87)
            try:
                await self._client.async_run("sudo systemctl start PerimeterControl.service")
                await asyncio.sleep(2)
                _LOGGER.info("Base isolator service started successfully")
            except SshCommandError as exc:
                # Base service failure should not block dashboard deployment
                # This is expected during initial deployment before network config is complete
                _LOGGER.info("Base PerimeterControl service failed to start (expected during initial setup): %s", exc)
                _LOGGER.info("Continuing deployment - dashboard can run independently")
        
        # Check if dashboard service exists before trying to restart it
        dashboard_service_exists = await self._client.async_run(
            f"systemctl list-unit-files {SYSTEMD_DASHBOARD}.service 2>/dev/null | grep -c {SYSTEMD_DASHBOARD} || true"
        )
        if dashboard_service_exists.strip() != "0":
            self._emit(PHASE_RESTART, f"Starting {SYSTEMD_DASHBOARD}...", 90)
            try:
                await self._client.async_run(f"sudo systemctl start {SYSTEMD_DASHBOARD}")
                _LOGGER.info("Dashboard service started successfully")
            except SshCommandError as exc:
                _LOGGER.warning("Dashboard service failed to start: %s", exc)
        else:
            _LOGGER.warning("Dashboard service unit not found, skipping restart")
        await asyncio.sleep(2)

        sup_service_exists = await self._client.async_run(
            f"systemctl list-unit-files {SYSTEMD_SUPERVISOR}.service 2>/dev/null | grep -c {SYSTEMD_SUPERVISOR} || true"
        )
        if sup_service_exists.strip() != "0":
            self._emit(PHASE_RESTART, f"Restarting {SYSTEMD_SUPERVISOR}...", 93)
            try:
                await self._client.async_run(f"sudo systemctl restart {SYSTEMD_SUPERVISOR}")
                await asyncio.sleep(2)
            except SshCommandError as exc:
                _LOGGER.warning("Supervisor service failed to restart: %s", exc)

    # ------------------------------------------------------------------
    # Phase 8: Verify
    # ------------------------------------------------------------------

    async def _phase_verify(self) -> None:
        self._emit(PHASE_VERIFY, "Verifying service health...", 95)
        
        # Check base PerimeterControl service (but don't fail if it's not running)
        base_status = await self._client.async_run(
            "systemctl is-active PerimeterControl.service || echo INACTIVE"
        )
        if "INACTIVE" in base_status:
            _LOGGER.info("Base PerimeterControl.service is not active (this is often expected for dashboard-only deployments)")
        else:
            _LOGGER.info("Base PerimeterControl.service is active: %s", base_status)
        
        # Check dashboard service - this is the main service we care about
        dashboard_status = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_DASHBOARD} || echo INACTIVE"
        )
        
        if "active" not in dashboard_status or "INACTIVE" in dashboard_status:
            _LOGGER.warning("Dashboard service is not active: %s", dashboard_status)
            
            # Get comprehensive diagnostics before retry
            try:
                # Check systemd status and logs
                status_detail = await self._client.async_run(
                    f"systemctl status {SYSTEMD_DASHBOARD} --no-pager -l || true"
                )
                _LOGGER.info("Dashboard service status detail: %s", status_detail)
                
                # Get recent systemd journal entries for the service
                journal_logs = await self._client.async_run(
                    f"journalctl -u {SYSTEMD_DASHBOARD} --no-pager -n 20 -o cat || true"
                )
                _LOGGER.info("Dashboard service logs: %s", journal_logs)
                
                # Check if service unit file exists
                unit_exists = await self._client.async_run(
                    f"[ -f {REMOTE_SYSTEMD_ROOT}/{SYSTEMD_DASHBOARD}.service ] && echo UNIT_EXISTS || echo UNIT_MISSING"
                )
                _LOGGER.info("Service unit check: %s", unit_exists.strip())
                
                # Check if python and dashboard.py exist and are accessible
                venv_check = await self._client.async_run(
                    f"[ -x {REMOTE_VENV}/bin/python3 ] && echo PYTHON_OK || echo PYTHON_MISSING"
                )
                dashboard_check = await self._client.async_run(
                    f"[ -f {REMOTE_WEB_DIR}/dashboard.py ] && echo DASHBOARD_OK || echo DASHBOARD_MISSING"
                )
                perms_check = await self._client.async_run(
                    f"ls -la {REMOTE_WEB_DIR}/dashboard.py || echo NO_FILE"
                )
                _LOGGER.info("Environment check - Python: %s, Dashboard: %s", venv_check.strip(), dashboard_check.strip())
                _LOGGER.info("Dashboard file permissions: %s", perms_check.strip())
                
                # Check if required packages are installed in venv
                pkg_check = await self._client.async_run(
                    f"sudo {REMOTE_VENV}/bin/pip3 list | grep -E '(bokeh|tornado|pyyaml)' || echo 'PACKAGES_MISSING'"
                )
                _LOGGER.info("Required packages in venv: %s", pkg_check.strip())
                
                # Try to run dashboard.py directly to see specific errors
                direct_test = await self._client.async_run(
                    f"cd {REMOTE_WEB_DIR} && timeout 10s sudo {REMOTE_VENV}/bin/python3 -c 'import sys; print(f\"Python: {{sys.version}}\"); import dashboard; print(\"Import successful\")' 2>&1 || echo FAILED"
                )
                _LOGGER.info("Dashboard import test result: %s", direct_test.strip())
                
            except Exception as e:
                _LOGGER.warning("Diagnostic check failed: %s", e)
            
            # Try to start it one more time
            _LOGGER.info("Attempting final start of dashboard service...")
            try:
                await self._client.async_run(f"sudo systemctl start {SYSTEMD_DASHBOARD}")
                await asyncio.sleep(3)
                
                # Check again
                final_status = await self._client.async_run(
                    f"systemctl is-active {SYSTEMD_DASHBOARD} || echo INACTIVE"
                )
                if "active" in final_status and "INACTIVE" not in final_status:
                    _LOGGER.info("Dashboard service started successfully on retry")
                else:
                    # Get final error details
                    try:
                        status_detail = await self._client.async_run(
                            f"systemctl status {SYSTEMD_DASHBOARD} --no-pager -l || true"
                        )
                        journal_logs = await self._client.async_run(
                            f"journalctl -u {SYSTEMD_DASHBOARD} --no-pager -n 10 -o cat || true"
                        )
                        _LOGGER.warning("Dashboard service failed to start. Status: %s", status_detail)
                        _LOGGER.warning("Dashboard service logs: %s", journal_logs)
                    except Exception:
                        pass
                    
                    # For now, don't fail the entire deployment if just dashboard fails
                    # The supervisor API might still work and provide diagnostic capabilities
                    _LOGGER.error("Dashboard service deployment failed, but continuing verify phase to check supervisor...")
            except Exception as e:
                _LOGGER.error("Failed to retry dashboard service start: %s", e)
                        
        else:
            _LOGGER.info("Dashboard service is running successfully")
        
        # Check supervisor service regardless of dashboard status
        supervisor_status = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_SUPERVISOR} || echo INACTIVE"
        )
        
        if "active" not in supervisor_status or "INACTIVE" in supervisor_status:
            _LOGGER.warning("Supervisor service is not active: %s", supervisor_status)
            
            # Get comprehensive diagnostics for supervisor service
            try:
                # Check systemd status and logs for supervisor
                supervisor_status_detail = await self._client.async_run(
                    f"systemctl status {SYSTEMD_SUPERVISOR} --no-pager -l || true"
                )
                _LOGGER.info("Supervisor service status detail: %s", supervisor_status_detail)
                
                # Get recent systemd journal entries for the supervisor service
                supervisor_journal_logs = await self._client.async_run(
                    f"journalctl -u {SYSTEMD_SUPERVISOR} --no-pager -n 20 -o cat || true"
                )
                _LOGGER.info("Supervisor service logs: %s", supervisor_journal_logs)
                
                # Check if supervisor unit file exists
                supervisor_unit_exists = await self._client.async_run(
                    f"[ -f {REMOTE_SYSTEMD_ROOT}/{SYSTEMD_SUPERVISOR}.service ] && echo UNIT_EXISTS || echo UNIT_MISSING"
                )
                _LOGGER.info("Supervisor service unit check: %s", supervisor_unit_exists.strip())
                
                # Check if supervisor files exist
                supervisor_check = await self._client.async_run(
                    f"[ -d {REMOTE_SUPERVISOR_DIR} ] && echo DIR_OK || echo DIR_MISSING"
                )
                supervisor_main_check = await self._client.async_run(
                    f"[ -f {REMOTE_SUPERVISOR_DIR}/__main__.py ] && echo MAIN_OK || echo MAIN_MISSING"
                )
                _LOGGER.info("Supervisor environment check - Dir: %s, Main: %s", 
                           supervisor_check.strip(), supervisor_main_check.strip())
                
                # Test supervisor import directly
                supervisor_direct_test = await self._client.async_run(
                    f"cd {REMOTE_SUPERVISOR_DIR} && timeout 10s sudo {REMOTE_VENV}/bin/python3 -c 'import sys; print(f\"Python: {{sys.version}}\"); import supervisor; print(\"Supervisor import successful\")' 2>&1 || echo FAILED"
                )
                _LOGGER.info("Supervisor import test result: %s", supervisor_direct_test.strip())
                
                # Check required packages for supervisor
                supervisor_pkg_check = await self._client.async_run(
                    f"sudo {REMOTE_VENV}/bin/pip3 list | grep -E '(aiohttp|psutil|pyyaml)' || echo 'SUPERVISOR_PACKAGES_MISSING'"
                )
                _LOGGER.info("Supervisor required packages in venv: %s", supervisor_pkg_check.strip())
                
            except Exception as e:
                _LOGGER.warning("Supervisor diagnostic check failed: %s", e)
            
            # Try to start supervisor
            try:
                _LOGGER.info("Attempting to start supervisor service...")
                await self._client.async_run(f"sudo systemctl start {SYSTEMD_SUPERVISOR}")
                await asyncio.sleep(3)
                supervisor_status = await self._client.async_run(
                    f"systemctl is-active {SYSTEMD_SUPERVISOR} || echo INACTIVE"
                )
                if "active" in supervisor_status and "INACTIVE" not in supervisor_status:
                    _LOGGER.info("Supervisor service started successfully on retry")
                else:
                    # Get final error details for supervisor
                    try:
                        supervisor_final_status = await self._client.async_run(
                            f"systemctl status {SYSTEMD_SUPERVISOR} --no-pager -l || true"
                        )
                        supervisor_final_logs = await self._client.async_run(
                            f"journalctl -u {SYSTEMD_SUPERVISOR} --no-pager -n 10 -o cat || true"
                        )
                        _LOGGER.warning("Supervisor service failed to start. Status: %s", supervisor_final_status)
                        _LOGGER.warning("Supervisor service logs: %s", supervisor_final_logs)
                    except Exception:
                        pass
                    _LOGGER.error("Supervisor service failed to start")
            except Exception as e:
                _LOGGER.error("Failed to start supervisor service: %s", e)
        else:
            _LOGGER.info("Supervisor service is running successfully")
        
        # Give final status summary
        dashboard_active = "active" in dashboard_status and "INACTIVE" not in dashboard_status
        supervisor_active = "active" in supervisor_status and "INACTIVE" not in supervisor_status
        
        if dashboard_active and supervisor_active:
            self._emit(PHASE_VERIFY, "Deploy complete — all services running", 100)
            _LOGGER.info("Deployment completed successfully - all services active")
        elif supervisor_active:
            self._emit(PHASE_VERIFY, "Deploy complete — supervisor running (dashboard failed)", 100)
            _LOGGER.warning("Deployment completed with warnings - supervisor active but dashboard failed")
        else:
            self._emit(PHASE_VERIFY, "Deploy complete — services need attention", 100)
            _LOGGER.error("Deployment completed with errors - both services need attention")


# ------------------------------------------------------------------
# Script builders
# ------------------------------------------------------------------

def _build_install_script() -> str:
    """Build the remote install script for Phase 3."""
    web_files = [
        ("dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("layouts.py", REMOTE_WEB_DIR, "0644"),
        ("callbacks.py", REMOTE_WEB_DIR, "0644"),
        ("data_sources.py", REMOTE_WEB_DIR, "0644"),
    ]
    script_files = [
        ("ble-scanner-v2.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-sniffer.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-debug.sh", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-proxy-profiler.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("ble-gatt-mirror.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("apply-rules.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("network-topology.py", REMOTE_SCRIPTS_DIR, "0755"),
        ("topology_config.py", REMOTE_SCRIPTS_DIR, "0644"),
    ]
    
    # Use the configurable install commands
    lines = ["set -e"] + _get_install_commands()
    
    for fname, dest, mode in web_files + script_files:
        lines.append(
            f"[ -f {REMOTE_TEMP_ROOT}/{fname} ] && sudo install -o root -g root -m {mode} "
            f"{REMOTE_TEMP_ROOT}/{fname} {dest}/{fname} || true"
        )
    lines.append("echo INSTALL_OK")
    return "\n".join(lines)


def _build_supervisor_install_script() -> str:
    return f"""set -e
sudo cp -a {REMOTE_SUPERVISOR_DIR} {REMOTE_TEMP_ROOT}/PerimeterControl-supervisor-backup 2>/dev/null || true
cd {REMOTE_TEMP_ROOT}
rm -rf {REMOTE_TEMP_ROOT}/supervisor
tar --no-same-permissions --no-same-owner -xzf {REMOTE_TEMP_ROOT}/supervisor.tar.gz
sudo mkdir -p {REMOTE_SUPERVISOR_DIR}
sudo cp -r {REMOTE_TEMP_ROOT}/supervisor/. {REMOTE_SUPERVISOR_DIR}/
sudo chown -R root:root {REMOTE_SUPERVISOR_DIR}
sudo find {REMOTE_SUPERVISOR_DIR} -type f -exec chmod 644 {{}} +
sudo find {REMOTE_SUPERVISOR_DIR} -type d -exec chmod 755 {{}} +
[ -f {REMOTE_TEMP_ROOT}/PerimeterControl-supervisor.service ] && \\
  sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/PerimeterControl-supervisor.service \\
  {REMOTE_SYSTEMD_ROOT}/PerimeterControl-supervisor.service && \\
  sudo systemctl daemon-reload && \
  sudo systemctl enable PerimeterControl-supervisor.service || true
echo SUPERVISOR_INSTALLED
"""


async def _pack_directory(src_dir: Path, arcname: str) -> bytes:
    """Pack a directory into an in-memory .tar.gz and return the bytes."""
    def _do_pack():
        buf = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(src_dir), arcname=arcname)
        buf.seek(0)
        return buf.read()
    
    # Run the blocking tar operation in a thread pool
    return await asyncio.to_thread(_do_pack)
