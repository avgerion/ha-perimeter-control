"""Service-aware deployer orchestrating specialized service deployers.


Uses service-specific deployers to handle deployment of individual capabilities:
- BLE GATT Repeater (ble_deployer.py)  
- PerimeterControl Network Service (network_deployer.py)
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

import ast
import asyncio
import logging
import os
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .base_deployer import BaseDeployer
from .base_deployer import DeployProgress, ProgressCallback
from .component_services import create_service, register_service_components, SERVICE_REGISTRY
from .service_framework import ComponentRegistry, hardware_registry
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


def _validate_python_file_syntax(path: Path) -> None:
    """Raise ValueError if the Python file has invalid syntax."""
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read {path}: {exc}") from exc

    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        detail = f"{path.name}:{exc.lineno}:{exc.offset} {exc.msg}"
        raise ValueError(f"Dashboard source syntax check failed: {detail}") from exc


def _validate_dashboard_sources() -> None:
    """Validate all deployable dashboard python sources before remote upload."""
    for name in ("dashboard.py", "layouts.py", "callbacks.py", "data_sources.py"):
        src = _SERVER_FILES_DIR / name
        if not src.exists():
            continue
        _validate_python_file_syntax(src)


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


def get_install_directories() -> list[str]:
    """Get list of directories to create during installation."""
    path_config = get_remote_path_config()
    return [
        path_config['CONF_DIR'],
        path_config['SCRIPTS_DIR'],
        path_config['SUPERVISOR_DIR'],
        path_config['LOG_ROOT'],
        path_config['STATE_ROOT'],
    ]


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


class Deployer(BaseDeployer):
    """Component-based deployer orchestrating service composition."""

    def __init__(
        self,
        client: SshClient,
        selected_services: list[str],
        service_descriptors: dict[str, ServiceDescriptor] | None = None,
        progress_cb: Optional[ProgressCallback] = None,
        hass=None,
    ) -> None:
        super().__init__(client, progress_cb)
        self._selected_services = selected_services
        self._service_descriptors = service_descriptors or {}
        self._hass = hass
        
        # Register component types
        register_service_components()
        
        # Create component-based services
        self._services = {}
        for service_id in selected_services:
            if service_id in SERVICE_REGISTRY:
                self._services[service_id] = create_service(service_id)
                _LOGGER.info(f"Created component-based service: {service_id}")
            else:
                _LOGGER.warning(f"No component service for {service_id}, will use legacy deployment")

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
        """Validate service selection and check for conflicts using component architecture."""
        self._emit(PHASE_PREFLIGHT, "Validating service selection...", 5)
        
        if not self._selected_services:
            raise ValueError("No services selected for deployment")
        
        # Only check conflicts among selected services
        all_conflicts = []
        component_services = []
        selected_service_ids = set(self._selected_services)

        # Only include selected services
        for service_id in self._selected_services:
            if service_id in self._services:
                service = self._services[service_id]
                service_conflicts = service.check_component_conflicts()
                if service_conflicts:
                    all_conflicts.extend([f"{service_id}: {c}" for c in service_conflicts])
                component_services.append(service_id)

        # Check cross-service component conflicts only among selected services
        SHAREABLE_COMPONENTS = {
            'python_dependencies', 'system_dependencies', 'config_manager',
            'data_logging', 'alert_system'
        }
        all_components = {}
        exclusive_components = {}

        for service_id in component_services:
            service = self._services[service_id]
            for comp_name, component in service._components.items():
                if component.config.enabled:
                    if comp_name in SHAREABLE_COMPONENTS:
                        if comp_name not in all_components:
                            all_components[comp_name] = [service_id]
                        else:
                            all_components[comp_name].append(service_id)
                    else:
                        # Only check exclusivity among selected services
                        if comp_name in exclusive_components:
                            existing_service = exclusive_components[comp_name]
                            all_conflicts.append(
                                f"Exclusive component {comp_name} used by both {existing_service} and {service_id}"
                            )
                        else:
                            exclusive_components[comp_name] = service_id

        if all_conflicts:
            raise ValueError(f"Component conflicts detected: {'; '.join(all_conflicts)}")
        
        # Report unknown services that will use legacy deployment
        unknown_services = [s for s in self._selected_services if s not in SERVICE_REGISTRY]
        if unknown_services:
            _LOGGER.warning("Unknown services (will use legacy deployment): %s", unknown_services)
        
        _LOGGER.info("Service selection validated: %s component services, %s legacy services", 
                    len(component_services), len(unknown_services))
        self._emit(PHASE_PREFLIGHT, "Service selection validated", 10)

    async def _phase_service_deployment(self) -> None:
        """Deploy each service using component composition."""
        self._emit("service_deploy", "Deploying component-based services...", 15)
        
        total_services = len(self._selected_services)
        deployment_path = Path("/tmp/perimeter_deployment")
        
        for i, service_id in enumerate(self._selected_services):
            base_progress = 15 + int(60 * i / total_services)  # Services take 15-75% of total
            
            if service_id in self._services:
                service = self._services[service_id]
                _LOGGER.info("Deploying service %s with component architecture", service_id)
                self._emit("service_deploy", f"Deploying {service_id} components...", base_progress)
                
                # Show component breakdown
                components = [comp.name for comp in service._components.values() if comp.config.enabled]
                _LOGGER.info(f"Service {service_id} components: {components}")
                
                # Deploy using component composition
                success = await service.deploy(self._client, deployment_path, hass=self._hass)
                if not success:
                    raise Exception(f"Service {service_id} component deployment failed")
                
                # Get auto-generated entities from hardware interfaces
                try:
                    deployed_services_set = set(self._selected_services)
                    entities = await service.get_hardware_entities(self._client, deployed_services_set)
                    if entities:
                        _LOGGER.info(f"Service {service_id} generated {len(entities)} auto-entities")
                except Exception as exc:
                    _LOGGER.warning(f"Failed to get auto-entities for {service_id}: {exc}")
                    
                self._emit("service_deploy", f"Service {service_id} deployed", base_progress + int(60 / total_services))
            else:
                _LOGGER.warning("No component service for %s, using legacy deployment", service_id)
                await self._legacy_deploy_service(service_id, base_progress)
        
        self._emit("service_deploy", "All services deployed", 75)

    async def _legacy_deploy_service(self, service_id: str, base_progress: int) -> None:
        """Deploy service using legacy monolithic approach."""
        self._emit("service_deploy", f"Legacy deployment for {service_id}...", base_progress)
        
        # Use base deployer capabilities for unknown services
        config_files = ["perimeterControl.conf.yaml"]
        await self.phase_config(config_files)
        
        # gpio_control expects /mnt/PerimeterControl/conf/gpio-control.yaml.
        # Ensure a baseline config is present even when using legacy deployment.
        if service_id == os.environ.get('PERIMETERCONTROL_GPIO_CONTROL_SERVICE', 'gpio_control'):
            await self._deploy_template_config(
                template_rel_path="config/templates/gpio_control_config.yaml",
                target_name="gpio-control.yaml",
            )

        await self.deploy_service_descriptors([service_id])
        
        self._emit("service_deploy", f"Legacy deployment for {service_id} completed", base_progress + 5)

    async def _deploy_template_config(self, template_rel_path: str, target_name: str) -> None:
        """Upload a template config file to the remote runtime config directory."""
        template_path = _COMPONENT_DIR / template_rel_path
        if not template_path.exists():
            _LOGGER.warning("Template config not found, skipping: %s", template_path)
            return

        await self._client.async_put_file(template_path, f"{REMOTE_TEMP_ROOT}/{target_name}")
        await self._client.async_run(f"sudo mkdir -p {REMOTE_CONF_DIR}")
        await self._client.async_run(
            f"sudo install -o root -g root -m 0644 {REMOTE_TEMP_ROOT}/{target_name} {REMOTE_CONF_DIR}/{target_name}"
        )
        _LOGGER.info("Installed template config: %s -> %s/%s", template_path.name, REMOTE_CONF_DIR, target_name)

    async def _phase_supervisor(self) -> None:
        """Install supervisor using base deployer functionality."""
        self._emit(PHASE_SUPERVISOR, "Installing supervisor...", 76)

        # Guardrail: do not upload dashboard files if local Python sources are invalid.
        _validate_dashboard_sources()
        
        # For now, keep the existing supervisor installation logic
        # but use base deployer where possible
        supervisor_src = _SUPERVISOR_DIR
        if not supervisor_src.exists():
            _LOGGER.warning("supervisor_files/ not found in component dir — skipping supervisor phase")
            return

        # Upload and install dashboard web files so WorkingDirectory always exists
        # (phase_install from service deployers may not have run if no component services selected)
        self._emit(PHASE_SUPERVISOR, "Deploying dashboard web files...", 77)
        _web_files = ["dashboard.py", "layouts.py", "callbacks.py", "data_sources.py"]
        for _fname in _web_files:
            _src = _SERVER_FILES_DIR / _fname
            if _src.exists():
                await self._client.async_put_file(_src, f"{REMOTE_TEMP_ROOT}/{_fname}")
            else:
                _LOGGER.warning("Dashboard web file not found, skipping: %s", _src)
        await self.phase_install()

        # Install Python packages required by the dashboard (always needed, regardless of
        # which component services were selected)
        await self.install_python_packages(
            ["bokeh", "tornado", "pyyaml", "pandas"],
            "dashboard",
        )

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
            # Clear rate-limit counter so systemd allows a fresh start after crash loop
            await self._client.async_run(
                f"sudo systemctl reset-failed {SYSTEMD_SUPERVISOR} 2>/dev/null || true"
            )
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_SUPERVISOR}")
            await asyncio.sleep(2)
            _LOGGER.info("Supervisor service restarted successfully")
        except Exception as exc:
            try:
                journal = await self._client.async_run(
                    f"sudo journalctl -u {SYSTEMD_SUPERVISOR} -n 50 --no-pager 2>&1 || true"
                )
                status_out = await self._client.async_run(
                    f"sudo systemctl status {SYSTEMD_SUPERVISOR} --no-pager 2>&1 || true"
                )
                _LOGGER.warning(
                    "Supervisor service failed to restart: %s\nStatus:\n%s\nJournal:\n%s",
                    exc, status_out.strip(), journal.strip(),
                )
            except Exception:
                _LOGGER.warning("Supervisor service failed to restart: %s", exc)

        supervisor_ok, supervisor_last = await self._wait_for_service_active(SYSTEMD_SUPERVISOR)
        if not supervisor_ok:
            status_out, journal = await self._get_condensed_service_diagnostics(SYSTEMD_SUPERVISOR)
            _LOGGER.error(
                "Supervisor failed post-restart health gate (last is-active=%s).\nStatus:\n%s\nRecent Journal:\n%s",
                supervisor_last.strip() or "<empty>",
                status_out.strip(),
                journal.strip(),
            )
            raise RuntimeError("Supervisor failed post-restart health gate")
        
        # Start dashboard service
        try:
            # Clear rate-limit counter so systemd allows a fresh start after crash loop
            await self._client.async_run(
                f"sudo systemctl reset-failed {SYSTEMD_DASHBOARD} 2>/dev/null || true"
            )
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_DASHBOARD}")
            await asyncio.sleep(2)
            _LOGGER.info("Dashboard service restarted successfully")
        except Exception as exc:
            try:
                journal = await self._client.async_run(
                    f"sudo journalctl -u {SYSTEMD_DASHBOARD} -n 50 --no-pager 2>&1 || true"
                )
                status_out = await self._client.async_run(
                    f"sudo systemctl status {SYSTEMD_DASHBOARD} --no-pager 2>&1 || true"
                )
                _LOGGER.warning(
                    "Dashboard service failed to restart: %s\nStatus:\n%s\nJournal:\n%s",
                    exc, status_out.strip(), journal.strip(),
                )
            except Exception:
                _LOGGER.warning("Dashboard service failed to restart: %s", exc)

        dashboard_ok, dashboard_last = await self._wait_for_service_active(SYSTEMD_DASHBOARD)
        if not dashboard_ok:
            status_out, journal = await self._get_condensed_service_diagnostics(SYSTEMD_DASHBOARD)
            _LOGGER.error(
                "Dashboard failed post-restart health gate (last is-active=%s).\nStatus:\n%s\nRecent Journal:\n%s",
                dashboard_last.strip() or "<empty>",
                status_out.strip(),
                journal.strip(),
            )
            raise RuntimeError("Dashboard failed post-restart health gate")
        
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
            status_out, journal = await self._get_condensed_service_diagnostics(SYSTEMD_DASHBOARD)
            _LOGGER.error(
                "Deployment failed verification: supervisor active but dashboard inactive.\nStatus:\n%s\nRecent Journal:\n%s",
                status_out.strip(),
                journal.strip(),
            )
            raise RuntimeError("Deployment verification failed: dashboard inactive")
        else:
            self._emit(PHASE_VERIFY, "Deploy failed — services need attention", 100)
            _LOGGER.error("Deployment verification failed - services need attention")
            for svc_name, svc_const in (
                ("Supervisor", SYSTEMD_SUPERVISOR),
                ("Dashboard", SYSTEMD_DASHBOARD),
            ):
                try:
                    journal = await self._client.async_run(
                        f"sudo journalctl -u {svc_const} -n 50 --no-pager 2>&1 || true"
                    )
                    status_out = await self._client.async_run(
                        f"sudo systemctl status {svc_const} --no-pager 2>&1 || true"
                    )
                    _LOGGER.error(
                        "%s diagnostics:\nStatus:\n%s\nJournal:\n%s",
                        svc_name, status_out.strip(), journal.strip(),
                    )
                except Exception as diag_exc:
                    _LOGGER.debug("Could not capture %s diagnostics: %s", svc_name, diag_exc)
            raise RuntimeError("Deployment verification failed: core services inactive")

    async def _wait_for_service_active(
        self,
        service_name: str,
        *,
        attempts: int = 8,
        delay_seconds: float = 2.0,
    ) -> tuple[bool, str]:
        """Wait for a systemd service to reach active state."""
        last_status = ""
        for _ in range(attempts):
            last_status = await self._client.async_run(
                f"systemctl is-active {service_name} 2>/dev/null || echo INACTIVE"
            )
            if "active" in last_status and "INACTIVE" not in last_status:
                return True, last_status
            await asyncio.sleep(delay_seconds)
        return False, last_status

    async def _get_condensed_service_diagnostics(self, service_name: str) -> tuple[str, str]:
        """Return condensed status and journal output for a service."""
        status_out = await self._client.async_run(
            f"sudo systemctl status {service_name} --no-pager --lines=20 2>&1 || true"
        )
        journal = await self._client.async_run(
            f"sudo journalctl -u {service_name} -n 30 --no-pager 2>&1 || true"
        )
        return status_out, journal


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
    _path = get_remote_path_config()
    _state_root = _path["STATE_ROOT"]
    _log_root = _path["LOG_ROOT"]
    return f"""set -e
# Ensure required directories exist before service units are started
sudo mkdir -p {_state_root} {_log_root}
sudo chmod 755 {_state_root} {_log_root}
# Deploy tmpfiles.d config so directories survive reboots (runs before services at boot)
printf 'd {_state_root} 0755 root root -\nd {_log_root} 0755 root root -\n' | sudo tee /etc/tmpfiles.d/perimeter-control.conf > /dev/null
sudo systemd-tmpfiles --create /etc/tmpfiles.d/perimeter-control.conf 2>/dev/null || true
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
