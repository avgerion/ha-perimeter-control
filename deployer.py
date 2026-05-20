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

_DASHBOARD_SERVICE_DEFS: dict[str, dict[str, Any]] = {
    os.environ.get("PERIMETERCONTROL_NETWORK_ISOLATOR_SERVICE", "network_isolator"): {
        "unit": SYSTEMD_DASHBOARD,
        "port": int(os.environ.get("PERIMETERCONTROL_DASHBOARD_PORT", "5006")),
        "template": "PerimeterControl-dashboard.service.template",
        "web_files": ["dashboard.py", "layouts.py", "callbacks.py", "data_sources.py"],
        "pip_packages": ["bokeh", "tornado", "pyyaml", "pandas"],
    },
    os.environ.get("PERIMETERCONTROL_PHOTO_BOOTH_SERVICE", "photo_booth"): {
        "unit": "PerimeterControl-photo-booth-dashboard",
        "port": 8093,
        "template": "PerimeterControl-photo-booth-dashboard.service.template",
        "web_files": ["photo_booth_dashboard.py"],
        "pip_packages": ["tornado"],
    },
    os.environ.get("PERIMETERCONTROL_GPIO_CONTROL_SERVICE", "gpio_control"): {
        "unit": "PerimeterControl-gpio-dashboard",
        "port": 8095,
        "template": "PerimeterControl-gpio-dashboard.service.template",
        "web_files": ["gpio_control_dashboard.py"],
        "pip_packages": ["tornado"],
    },
    os.environ.get("PERIMETERCONTROL_BLE_GATT_REPEATER_SERVICE", "ble_gatt_repeater"): {
        "unit": "PerimeterControl-ble-dashboard",
        "port": 8091,
        "template": "PerimeterControl-ble-dashboard.service.template",
        "web_files": ["ble_gatt_dashboard.py"],
        "pip_packages": ["tornado"],
    },
    os.environ.get("PERIMETERCONTROL_ESL_AP_SERVICE", "esl_ap"): {
        "unit": "PerimeterControl-esl-dashboard",
        "port": 8092,
        "template": "PerimeterControl-esl-dashboard.service.template",
        "web_files": ["esl_ap_dashboard.py"],
        "pip_packages": ["tornado"],
    },
    os.environ.get("PERIMETERCONTROL_WILDLIFE_MONITOR_SERVICE", "wildlife_monitor"): {
        "unit": "PerimeterControl-wildlife-dashboard",
        "port": 8094,
        "template": "PerimeterControl-wildlife-dashboard.service.template",
        "web_files": ["wildlife_monitor_dashboard.py"],
        "pip_packages": ["tornado"],
    },
}


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
        self._dashboard_service_id = os.environ.get("PERIMETERCONTROL_NETWORK_ISOLATOR_SERVICE", "network_isolator")
        self._selected_dashboard_services = [
            service_id for service_id in selected_services if service_id in _DASHBOARD_SERVICE_DEFS
        ]
        self._selected_dashboard_units = {
            _DASHBOARD_SERVICE_DEFS[service_id]["unit"]
            for service_id in self._selected_dashboard_services
        }
        self._manage_dashboard_service = bool(self._selected_dashboard_services)
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

        runtime_template_overrides = {
            os.environ.get('PERIMETERCONTROL_GPIO_CONTROL_SERVICE', 'gpio_control'): (
                "config/templates/gpio_control_config.yaml",
                "gpio-control.yaml",
            ),
            os.environ.get('PERIMETERCONTROL_PHOTO_BOOTH_SERVICE', 'photo_booth'): (
                "config/templates/photo_booth_config.yaml",
                "photo-booth.yaml",
            ),
        }
        
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

                # Ensure capability runtime config is installed at the exact path
                # the service descriptor expects under /mnt/PerimeterControl/conf.
                if service_id in runtime_template_overrides:
                    template_rel_path, target_name = runtime_template_overrides[service_id]
                    await self._deploy_template_config(
                        template_rel_path=template_rel_path,
                        target_name=target_name,
                    )
                    _LOGGER.info(
                        "Installed runtime config override for %s -> %s/%s",
                        service_id,
                        REMOTE_CONF_DIR,
                        target_name,
                    )
                
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
        selected_dashboard_files: list[str] = []
        selected_dashboard_packages: set[str] = set()
        selected_dashboard_templates: list[str] = []
        for service_id in self._selected_dashboard_services:
            definition = _DASHBOARD_SERVICE_DEFS[service_id]
            selected_dashboard_files.extend(definition["web_files"])
            selected_dashboard_packages.update(definition["pip_packages"])
            selected_dashboard_templates.append(definition["template"])

        for name in sorted(set(selected_dashboard_files)):
            src = _SERVER_FILES_DIR / name
            if src.exists() and src.suffix == ".py":
                _validate_python_file_syntax(src)
        
        # For now, keep the existing supervisor installation logic
        # but use base deployer where possible
        supervisor_src = _SUPERVISOR_DIR
        if not supervisor_src.exists():
            _LOGGER.warning("supervisor_files/ not found in component dir — skipping supervisor phase")
            return

        # Upload selected dashboard web files.
        if selected_dashboard_files:
            self._emit(PHASE_SUPERVISOR, "Deploying dashboard web files...", 77)
            for _fname in sorted(set(selected_dashboard_files)):
                _src = _SERVER_FILES_DIR / _fname
                if _src.exists():
                    await self._client.async_put_file(_src, f"{REMOTE_TEMP_ROOT}/{_fname}")
                else:
                    _LOGGER.warning("Dashboard web file not found, skipping: %s", _src)
        await self.phase_install()

        # Install Python packages required by selected dashboard services.
        if selected_dashboard_packages:
            await self.install_python_packages(
                sorted(selected_dashboard_packages),
                "dashboard",
            )

        # Install supervisor package
        self._emit(PHASE_SUPERVISOR, "Uploading supervisor package...", 78)
        tar_bytes = await _pack_directory(supervisor_src, arcname="supervisor")
        await self._client.async_put_bytes(tar_bytes, f"{REMOTE_TEMP_ROOT}/supervisor.tar.gz")

        # Install systemd services; dashboard service is optional per selected capabilities.
        template_files = ["PerimeterControl-supervisor.service.template"] + selected_dashboard_templates
        await self.install_systemd_services(template_files)

        # Always sync selected service descriptors so Supervisor reads current access_profile
        # (mode/port/tls) instead of stale files from previous deployments.
        await self.deploy_service_descriptors(self._selected_services)
        
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
        
        for service_id in self._selected_dashboard_services:
            definition = _DASHBOARD_SERVICE_DEFS[service_id]
            unit = definition["unit"]
            port = definition["port"]
            try:
                await self._client.async_run(
                    f"sudo systemctl reset-failed {unit} 2>/dev/null || true"
                )
                await self._client.async_run(f"sudo systemctl restart {unit}")
                await asyncio.sleep(2)
                _LOGGER.info("Dashboard service %s restarted successfully", unit)
            except Exception as exc:
                try:
                    journal = await self._client.async_run(
                        f"sudo journalctl -u {unit} -n 50 --no-pager 2>&1 || true"
                    )
                    status_out = await self._client.async_run(
                        f"sudo systemctl status {unit} --no-pager 2>&1 || true"
                    )
                    _LOGGER.warning(
                        "Dashboard service %s failed to restart: %s\nStatus:\n%s\nJournal:\n%s",
                        unit, exc, status_out.strip(), journal.strip(),
                    )
                except Exception:
                    _LOGGER.warning("Dashboard service %s failed to restart: %s", unit, exc)

            dashboard_ok, dashboard_last = await self._wait_for_service_active(unit)
            if not dashboard_ok:
                status_out, journal = await self._get_condensed_service_diagnostics(unit)
                _LOGGER.error(
                    "Dashboard service %s failed post-restart health gate (last is-active=%s).\nStatus:\n%s\nRecent Journal:\n%s",
                    unit,
                    dashboard_last.strip() or "<empty>",
                    status_out.strip(),
                    journal.strip(),
                )
                raise RuntimeError(f"Dashboard failed post-restart health gate: {unit}")

            http_ok, http_probe = await self._wait_for_http_ready(port)
            if not http_ok:
                status_out, journal = await self._get_condensed_service_diagnostics(unit)
                _LOGGER.error(
                    "Dashboard service %s is active but HTTP probe failed on port %s (%s).\nStatus:\n%s\nRecent Journal:\n%s",
                    unit,
                    port,
                    http_probe.strip() or "<empty>",
                    status_out.strip(),
                    journal.strip(),
                )
                raise RuntimeError(f"Dashboard HTTP probe failed: {unit}")

        non_selected_dashboard_units = {
            definition["unit"] for definition in _DASHBOARD_SERVICE_DEFS.values()
        } - self._selected_dashboard_units
        for unit in sorted(non_selected_dashboard_units):
            await self._client.async_run(
                f"sudo systemctl stop {unit} 2>/dev/null || true; "
                f"sudo systemctl disable {unit} 2>/dev/null || true"
            )
            _LOGGER.info("Dashboard service %s is not selected; ensured it is stopped/disabled", unit)
        
        self._emit(PHASE_RESTART, "Services restarted", 95)

    async def _phase_verify(self) -> None:
        """Verify deployment success."""
        self._emit(PHASE_VERIFY, "Verifying service health...", 96)
        
        # Check supervisor service
        supervisor_status = await self._client.async_run(
            f"systemctl is-active {SYSTEMD_SUPERVISOR} || echo INACTIVE"
        )
        supervisor_active = "active" in supervisor_status and "INACTIVE" not in supervisor_status
        
        dashboard_results: list[tuple[str, str, bool]] = []
        for service_id in self._selected_dashboard_services:
            definition = _DASHBOARD_SERVICE_DEFS[service_id]
            unit = definition["unit"]
            status = await self._client.async_run(
                f"systemctl is-active {unit} || echo INACTIVE"
            )
            active = "active" in status and "INACTIVE" not in status
            dashboard_results.append((service_id, unit, active))

        if not dashboard_results:
            _LOGGER.info("Service status - Supervisor: %s, Dashboards: skipped (none selected)", supervisor_status.strip())
        else:
            summary = ", ".join(
                f"{service_id}:{'active' if active else 'inactive'}({unit})"
                for service_id, unit, active in dashboard_results
            )
            _LOGGER.info("Service status - Supervisor: %s, Dashboards: %s", supervisor_status.strip(), summary)

        dashboards_active = all(active for _, _, active in dashboard_results)

        if supervisor_active and dashboards_active:
            self._emit(PHASE_VERIFY, "Deploy complete — all services running", 100)
            _LOGGER.info("Deployment completed successfully - all services active")
        elif supervisor_active:
            failing_units = [unit for _, unit, active in dashboard_results if not active]
            for unit in failing_units:
                status_out, journal = await self._get_condensed_service_diagnostics(unit)
                _LOGGER.error(
                    "Deployment failed verification: supervisor active but dashboard %s inactive.\nStatus:\n%s\nRecent Journal:\n%s",
                    unit,
                    status_out.strip(),
                    journal.strip(),
                )
            raise RuntimeError("Deployment verification failed: selected dashboards inactive")
        else:
            self._emit(PHASE_VERIFY, "Deploy failed — services need attention", 100)
            _LOGGER.error("Deployment verification failed - services need attention")
            for svc_name, svc_const in (
                ("Supervisor", SYSTEMD_SUPERVISOR),
                *[(f"Dashboard({service_id})", _DASHBOARD_SERVICE_DEFS[service_id]["unit"]) for service_id in self._selected_dashboard_services],
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

    async def _wait_for_http_ready(
        self,
        port: int,
        *,
        attempts: int = 6,
        delay_seconds: float = 1.5,
    ) -> tuple[bool, str]:
        """Wait for local HTTP endpoint to return success on the remote host."""
        last_probe = ""
        for _ in range(attempts):
            last_probe = await self._client.async_run(
                f"curl -fsS --max-time 3 http://127.0.0.1:{port}/ >/dev/null 2>&1 && echo HTTP_OK || echo HTTP_FAIL"
            )
            if "HTTP_OK" in last_probe:
                return True, last_probe
            await asyncio.sleep(delay_seconds)
        return False, last_probe


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
        ("photo_booth_dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("gpio_control_dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("ble_gatt_dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("esl_ap_dashboard.py", REMOTE_WEB_DIR, "0644"),
        ("wildlife_monitor_dashboard.py", REMOTE_WEB_DIR, "0644"),
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
