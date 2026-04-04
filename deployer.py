"""Service-aware deployer orchestrating specialized service deployers.

Uses service-specific deployers to handle deployment of individual capabilities:
- BLE GATT Repeater (ble_deployer.py)  
- Network Isolator (network_deployer.py)
- Photo Booth (camera_deployer.py)
- Wildlife Monitor (wildlife_deployer.py)
- ESL AP (esl_deployer.py)

Phases:
  1. service_selection — determine which services to deploy
  2. service_preflight — run service-specific preflight checks
  3. service_deploy    — deploy each service with its specialized deployer
  4. supervisor        — install supervisor package + service unit  
  5. restart           — restart systemd services
  6. verify            — poll service health
"""
from __future__ import annotations

import asyncio
import logging
import os
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base_deployer import BaseDeployer, DeployProgress, ProgressCallback
from .ble_deployer import BleDeployer
from .camera_deployer import CameraDeployer
from .const import (
    APT_DEPENDENCY_GROUPS,
    PHASE_PREFLIGHT,
    PHASE_RESTART,
    PHASE_SUPERVISOR,
    PHASE_VERIFY,
    REMOTE_CONF_DIR,
    REMOTE_SCRIPTS_DIR, 
    REMOTE_SUPERVISOR_DIR,
    REMOTE_SYSTEMD_ROOT,
    REMOTE_TEMP_ROOT,
    REMOTE_VENV,
    REMOTE_WEB_DIR,
    SYSTEMD_DASHBOARD,
    SYSTEMD_SUPERVISOR,
    get_remote_path_config,
)
from .esl_deployer import EslDeployer
from .network_deployer import NetworkDeployer
from .service_descriptor import ServiceDescriptor, load_service_descriptors
from .ssh_client import SshClient, SshCommandError
from .wildlife_deployer import WildlifeDeployer

_LOGGER = logging.getLogger(__name__)

# Resolved at runtime relative to this file (inside the HA custom component)
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
    
    # Use asyncio.to_thread to read file without blocking event loop
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


class Deployer(BaseDeployer):
    """Service-aware deployer orchestrating specialized service deployers."""

    def __init__(
        self,
        client: SshClient,
        selected_services: list[str],
        service_descriptors: dict[str, ServiceDescriptor] | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        self._selected_services = selected_services
        self._service_descriptors = service_descriptors or {}
        
        # Initialize service-specific deployers
        self._service_deployers = {
            'ble_gatt_repeater': BleDeployer(client, progress_cb),
            'network_isolator': NetworkDeployer(client, progress_cb),
            'photo_booth': CameraDeployer(client, progress_cb),
            'wildlife_monitor': WildlifeDeployer(client, progress_cb),
            'esl_ap': EslDeployer(client, progress_cb),
        }

    async def async_deploy(self) -> bool:
        """Run service-aware deployment using specialized deployers."""
        deployment_id = id(self)
        _LOGGER.warning("=== SERVICE-AWARE DEPLOYMENT STARTED === (ID: %s)", deployment_id)
        _LOGGER.info("Deploying services: %s", self._selected_services)
        
        try:
            # Phase 1: Service Selection & Validation
            _LOGGER.info("Phase 1: Service selection and validation (ID: %s)", deployment_id)
            await self._phase_service_selection()
            
            # Phase 2: Service-Specific Deployment
            _LOGGER.info("Phase 2: Service-specific deployments (ID: %s)", deployment_id)
            await self._phase_service_deployment()
            
            # Phase 3: Supervisor Installation
            _LOGGER.info("Phase 3: Install supervisor (ID: %s)", deployment_id)
            await self._phase_supervisor()
            
            # Phase 4: Service Restart
            _LOGGER.info("Phase 4: Restart services (ID: %s)", deployment_id)
            await self._phase_restart()
            
            # Phase 5: Service Verification
            _LOGGER.info("Phase 5: Verify deployment (ID: %s)", deployment_id)
            await self._phase_verify()
            
            _LOGGER.warning("=== SERVICE-AWARE DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("Service-aware deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("service_deploy", f"Service deployment error: {exc}")
            return False

    async def _phase_service_selection(self) -> None:
        """Validate service selection and check for conflicts."""
        self._emit(PHASE_PREFLIGHT, "Validating service selection...", 5)
        
        if not self._selected_services:
            raise ValueError("No services selected for deployment")
        
        # Check for service conflicts
        conflicts = []
        for service_id in self._selected_services:
            deployer = self._service_deployers.get(service_id)
            if deployer and hasattr(deployer, 'conflicts_with'):
                service_conflicts = deployer.conflicts_with()
                for conflict_service in service_conflicts:
                    if conflict_service in self._selected_services:
                        conflicts.append(f"{service_id} conflicts with {conflict_service}")
        
        if conflicts:
            raise ValueError(f"Service conflicts detected: {', '.join(conflicts)}")
        
        # Validate all selected services have deployers
        unknown_services = [s for s in self._selected_services if s not in self._service_deployers]
        if unknown_services:
            _LOGGER.warning("Unknown services (will use legacy deployment): %s", unknown_services)
        
        _LOGGER.info("Service selection validated: %s", self._selected_services)
        self._emit(PHASE_PREFLIGHT, "Service selection validated", 10)

    async def _phase_service_deployment(self) -> None:
        """Deploy each service using its specialized deployer."""
        self._emit("service_deploy", "Deploying individual services...", 15)
        
        total_services = len(self._selected_services)
        for i, service_id in enumerate(self._selected_services):
            base_progress = 15 + int(60 * i / total_services)  # Services take 15-75% of total
            deployer = self._service_deployers.get(service_id)
            
            if deployer:
                _LOGGER.info("Deploying service %s with specialized deployer", service_id)
                self._emit("service_deploy", f"Deploying {service_id}...", base_progress)
                
                success = await deployer.deploy()
                if not success:
                    raise Exception(f"Service {service_id} deployment failed")
                    
                self._emit("service_deploy", f"Service {service_id} deployed", base_progress + int(60 / total_services))
            else:
                _LOGGER.warning("No specialized deployer for %s, using legacy deployment", service_id)
                await self._legacy_deploy_service(service_id, base_progress)
        
        self._emit("service_deploy", "All services deployed", 75)

    async def _legacy_deploy_service(self, service_id: str, base_progress: int) -> None:
        """Deploy service using legacy monolithic approach."""
        self._emit("service_deploy", f"Legacy deployment for {service_id}...", base_progress)
        
        # Use base deployer capabilities for unknown services
        config_files = ["perimeterControl.conf.yaml"]
        await self.phase_config(config_files)
        await self.deploy_service_descriptors([service_id])
        
        self._emit("service_deploy", f"Legacy deployment for {service_id} completed", base_progress + 5)

    async def _phase_supervisor(self) -> None:
        """Install supervisor using base deployer functionality."""
        self._emit(PHASE_SUPERVISOR, "Installing supervisor...", 76)
        
        # For now, keep the existing supervisor installation logic
        # but use base deployer where possible
        supervisor_src = _SUPERVISOR_DIR
        if not supervisor_src.exists():
            _LOGGER.warning("supervisor_files/ not found in component dir — skipping supervisor phase")
            return

        # Install supervisor package
        self._emit(PHASE_SUPERVISOR, "Uploading supervisor package...", 78)
        tar_bytes = await _pack_directory(supervisor_src, arcname="supervisor")
        await self._client.async_put_bytes(tar_bytes, f"{REMOTE_TEMP_ROOT}/supervisor.tar.gz")

        # Install systemd services
        await self.install_systemd_services([
            "PerimeterControl-supervisor.service.template",
            "PerimeterControl-dashboard.service.template"
        ])
        
        # Install supervisor
        sup_install_script = _build_supervisor_install_script()
        await self._client.async_run_b64(sup_install_script)
        
        self._emit(PHASE_SUPERVISOR, "Supervisor installed", 85)

    async def _phase_restart(self) -> None:
        """Restart systemd services."""
        self._emit(PHASE_RESTART, "Restarting services...", 87)
        
        # Start supervisor service
        try:
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_SUPERVISOR}")
            await asyncio.sleep(2)
            _LOGGER.info("Supervisor service restarted successfully")
        except Exception as exc:
            _LOGGER.warning("Supervisor service failed to restart: %s", exc)
        
        # Start dashboard service
        try:
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_DASHBOARD}")
            await asyncio.sleep(2)
            _LOGGER.info("Dashboard service restarted successfully")
        except Exception as exc:
            _LOGGER.warning("Dashboard service failed to restart: %s", exc)
        
        self._emit(PHASE_RESTART, "Services restarted", 95)

    async def _phase_verify(self) -> None:
        """Verify deployment success."""
        self._emit(PHASE_VERIFY, "Verifying service health...", 96)
        
        # Check supervisor service
        supervisor_status = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_SUPERVISOR} || echo INACTIVE"
        )
        supervisor_active = "active" in supervisor_status and "INACTIVE" not in supervisor_status
        
        # Check dashboard service
        dashboard_status = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_DASHBOARD} || echo INACTIVE"
        )
        dashboard_active = "active" in dashboard_status and "INACTIVE" not in dashboard_status
        
        _LOGGER.info("Service status - Supervisor: %s, Dashboard: %s", 
                    supervisor_status.strip(), dashboard_status.strip())
        
        if supervisor_active and dashboard_active:
            self._emit(PHASE_VERIFY, "Deploy complete — all services running", 100)
            _LOGGER.info("Deployment completed successfully - all services active")
        elif supervisor_active:
            self._emit(PHASE_VERIFY, "Deploy complete — supervisor running", 100)
            _LOGGER.warning("Deployment completed with warnings - supervisor active but dashboard failed")
        else:
            self._emit(PHASE_VERIFY, "Deploy complete — services need attention", 100)
            _LOGGER.error("Deployment completed with errors - services need attention")


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
[ -f {REMOTE_TEMP_ROOT}/{SYSTEMD_SUPERVISOR}.service ] && \\
  sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{SYSTEMD_SUPERVISOR}.service \\
  {REMOTE_SYSTEMD_ROOT}/{SYSTEMD_SUPERVISOR}.service && \\
  sudo systemctl daemon-reload && \\
  sudo systemctl enable {SYSTEMD_SUPERVISOR}.service || true
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
