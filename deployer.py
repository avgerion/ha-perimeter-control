"""
Service-aware deployer using a unified, config-driven approach.

This deployer iterates over the SERVICE_REGISTRY, which defines all deployable services,
their files, dependencies, and configuration in a single source of truth.

All deployment logic is now generic and driven by the SERVICE_REGISTRY and component_services.py.
There are no longer any individual service-specific deployers (e.g. ble_deployer.py, camera_deployer.py, etc.).
All service composition, dependencies, and hardware requirements are handled by the component-based model.

Phases:
    1. service_selection — determine which services to deploy (from SERVICE_REGISTRY)
    2. service_preflight — run generic and component-based preflight checks
    3. service_deploy    — deploy each service using the config/component model
    4. supervisor        — install supervisor package + service unit
    5. restart           — restart systemd services
    6. verify            — poll service health

Note: SERVICE_REGISTRY is imported only for config data; all service logic is handled by the component_services.py model.
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
from .component_services import create_service, register_service_components

from .service_framework import ComponentRegistry, hardware_registry
from .const import (
    remote_temp_root,
    remote_web_dir,
    remote_scripts_dir,
    remote_conf_dir,
    remote_services_dir,
    remote_systemd_root,
    remote_supervisor_dir,
    remote_log_root,
    remote_state_root,
    get_remote_install_directories,
    SERVICE_REGISTRY,
    DASHBOARD_WEB_DIR,
    SUPERVISOR_SRC_DIR,
    SHARED_WEB_FILES,
    TEMPLATES_DIR,
)



_LOGGER = logging.getLogger(__name__)


async def _validate_python_file_syntax(path: Path) -> None:
    """Raise ValueError if the Python file has invalid syntax."""

    try:
        # If already in an event loop, use await; otherwise, fallback to run
        try:
            loop = asyncio.get_running_loop()
            # In async context, must be called from an async function
            raise RuntimeError("_validate_python_file_syntax must be called from async context if event loop is running.")
        except RuntimeError:
            # No running event loop, safe to use asyncio.run
            source = await asyncio.to_thread(path.read_text, encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read {path}: {exc}") from exc

    try:
        # ast.parse is CPU-bound, so run in thread as well
        await asyncio.to_thread(ast.parse, source, str(path))
    except SyntaxError as exc:
        detail = f"{path.name}:{exc.lineno}:{exc.offset} {exc.msg}"
        raise ValueError(f"Dashboard source syntax check failed: {detail}") from exc


async def _validate_dashboard_sources() -> None:
    """Validate all deployable dashboard python sources before remote upload."""
    for service_info in SERVICE_REGISTRY.values():
        for name in service_info.get("web_files", []):
            src = Path(remote_web_dir) / name
            if not src.exists():
                continue
            await _validate_python_file_syntax(src)


async def _render_service_template(template_path: Path) -> str:
    _LOGGER.warning(f"[PerimeterControl] _render_service_template called for: {template_path}")
    """Render a systemd service template with configurable paths."""
    if not template_path.exists():
        raise FileNotFoundError(f"Service template not found: {template_path}")
    
    # Use asyncio.to_thread to read file without blocking event loop
    template_content = await asyncio.to_thread(template_path.read_text, encoding="utf-8")
    from .const import get_remote_path_config
    path_config = get_remote_path_config()
    _LOGGER.warning(f"[PerimeterControl] Template path_config for {template_path}: {path_config}")
    try:
        return template_content.format(**path_config)
    except KeyError as e:
        raise ValueError(f"Missing template variable {e} in {template_path}. path_config={path_config}")




def _get_install_commands() -> list[str]:
    """Generate installation commands using configurable paths."""
    dirs = get_remote_install_directories()
    commands = [f"sudo mkdir -p {d}" for d in dirs]
    # Add ownership commands for directories that need root ownership
    commands.extend([
        f"sudo chown root:root {remote_log_root}",
        f"sudo chown root:root {remote_state_root}",
        f"sudo chmod 755 {remote_log_root}",
    ])
    return commands


class Deployer(BaseDeployer):
    """Component-based deployer orchestrating service composition."""

    def __init__(
        self,
        client,
        selected_services: list[str],
        service_descriptors: dict | None = None,
        progress_cb: Optional[ProgressCallback] = None,
        hass=None,
    ) -> None:
        super().__init__(client, progress_cb)
        self._selected_services = selected_services
        self._service_descriptors = service_descriptors or {}
        self._hass = hass
        # deploy_api URLs collected during Phase 2, fired in Phase 4 after supervisor is up
        self._pending_deploy_apis: list[tuple[str, str]] = []  # (service_id, url)
        # Auto-entities collected from hardware detection during Phase 2,
        # keyed by service_id. Injected into service descriptors in Phase 3.
        self._auto_entities: dict[str, list] = {}
        # Register component types
        register_service_components()
        # Create component-based services using SERVICE_REGISTRY from const.py
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
            # Phase 0: Stop all managed services before deployment
            _LOGGER.warning("Phase 0: Stop managed services (ID: %s)", deployment_id)
            await self._phase_stop_services()

            # Phase 1: Service Selection & Validation
            _LOGGER.warning("Phase 1: Service selection and validation (ID: %s)", deployment_id)
            await self._phase_service_selection()

            # Phase 2: Service-Specific Deployment
            _LOGGER.warning("Phase 2: Service-specific deployments (ID: %s)", deployment_id)
            await self._phase_service_deployment()

            # Phase 3: Supervisor Installation
            _LOGGER.warning("Phase 3: Install supervisor (ID: %s)", deployment_id)
            await self._phase_supervisor()

            # Phase 4: Service Restart
            _LOGGER.warning("Phase 4: Restart services (ID: %s)", deployment_id)
            await self._phase_restart()

            # Phase 5: Service Verification
            _LOGGER.warning("Phase 5: Verify deployment (ID: %s)", deployment_id)
            await self._phase_verify()

            _LOGGER.warning("=== SERVICE-AWARE DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True

        except Exception as exc:
            _LOGGER.error("Service-aware deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("service_deploy", f"Service deployment error: {exc}")
            return False

    async def _phase_stop_services(self) -> None:
        """Stop all managed systemd services before deployment."""
        self._emit("stop", "Stopping managed services before deployment...", 2)
        # Collect all units from SERVICE_REGISTRY (including supervisor)
        all_units = {info.get("unit") for info in SERVICE_REGISTRY.values() if info.get("unit")}
        all_units.add("perimetercontrol-supervisor")
        for unit in sorted(u for u in all_units if u):
            try:
                await self._client.async_run(f"sudo systemctl stop {unit} 2>/dev/null || true")
                _LOGGER.info("Stopped service: %s", unit)
            except Exception as exc:
                _LOGGER.warning("Failed to stop service %s: %s", unit, exc)
        self._emit("stop", "All managed services stopped (if running)", 3)

    async def _phase_service_selection(self) -> None:
        """Validate service selection and check for conflicts using component architecture."""
        self._emit("preflight", "Validating service selection...", 5)
        
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
        self._emit("preflight", "Service selection validated", 10)

    async def _phase_service_deployment(self) -> None:
        """Deploy each service using component composition."""
        self._emit("service_deploy", "Deploying component-based services...", 15)

        # All template/config info is now in SERVICE_REGISTRY in const.py
        
        total_services = len(self._selected_services)
        deployment_path = Path(remote_temp_root)
        
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
                # Use config_template and config_target from SERVICE_REGISTRY if present
                service_info = SERVICE_REGISTRY.get(service_id, {})
                template_rel_path = service_info.get("config_template")
                target_name = service_info.get("config_target")
                if template_rel_path and target_name:
                    await self._deploy_template_config(
                        template_rel_path=template_rel_path,
                        target_name=target_name,
                    )
                    _LOGGER.info(
                        "Installed runtime config for %s -> %s/%s",
                        service_id,
                        remote_conf_dir,
                        target_name,
                    )
                # If deploy_api is present, defer the call to Phase 4 when the
                # supervisor is running.  Calling it here would fail because the
                # supervisor service was stopped in Phase 0.
                deploy_api = service_info.get("deploy_api")
                if deploy_api:
                    self._pending_deploy_apis.append((service_id, deploy_api))
                    _LOGGER.info("Deferred deploy_api call for %s until supervisor is running", service_id)
                
                # Get auto-generated entities from hardware interfaces and
                # store them so deploy_service_descriptors can inject them.
                try:
                    deployed_services_set = set(self._selected_services)
                    entities = await service.get_hardware_entities(self._client, deployed_services_set)
                    if entities:
                        self._auto_entities[service_id] = entities
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
        
        # Ensure a baseline config is present even when using legacy deployment.
        # Use config_template and config_target from SERVICE_REGISTRY if present
        service_info = SERVICE_REGISTRY.get(service_id, {})
        template_rel_path = service_info.get("config_template")
        target_name = service_info.get("config_target")
        if template_rel_path and target_name:
            await self._deploy_template_config(
                template_rel_path=template_rel_path,
                target_name=target_name,
            )

        await self.deploy_service_descriptors([service_id], auto_entities=self._auto_entities)
        
        self._emit("service_deploy", f"Legacy deployment for {service_id} completed", base_progress + 5)

    async def _deploy_template_config(self, template_rel_path: str, target_name: str) -> None:
        """Upload a template config file to the remote runtime config directory."""
        # Always resolve config templates using TEMPLATES_DIR for robustness

        template_name = Path(template_rel_path).name
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            _LOGGER.error("Service config not found, skipping: %s (cwd=%s)", template_path, os.getcwd())
            return

        await self._client.async_put_file(template_path, f"{remote_temp_root}/{target_name}")
        await self._client.async_run(f"sudo mkdir -p {remote_conf_dir}")
        await self._client.async_run(
            f"sudo install -o root -g root -m 0644 {remote_temp_root}/{target_name} {remote_conf_dir}/{target_name}"
        )
        _LOGGER.info("Installed template config: %s -> %s/%s", template_path.name, remote_conf_dir, target_name)

    async def _phase_supervisor(self) -> None:
        """Install supervisor using base deployer functionality."""
        self._emit("supervisor", "Installing supervisor...", 76)

        # Guardrail: do not upload dashboard files if local Python sources are invalid.
        # Use the single source of truth for supervisor source directory
        supervisor_src = SUPERVISOR_SRC_DIR
        selected_dashboard_files: list[str] = []
        selected_dashboard_packages: set[str] = set()
        selected_dashboard_templates: list[str] = []
        for service_id in self._selected_services:
            service_info = SERVICE_REGISTRY.get(service_id, {})
            selected_dashboard_files.extend(service_info.get("web_files", []))
            selected_dashboard_packages.update(service_info.get("pip_packages", []))
            if service_info.get("template"):
                selected_dashboard_templates.append(service_info["template"])

        for name in sorted(set(selected_dashboard_files)):
            # Use canonical dashboard source location for dashboard files
            # Always resolve dashboard_web files from local source tree
            if name.startswith("dashboard_web/"):
                src = DASHBOARD_WEB_DIR / name.split("dashboard_web/")[1]
            elif name.startswith("remote_services/dashboard_web/"):
                src = DASHBOARD_WEB_DIR / name.split("remote_services/dashboard_web/")[1]
            else:
                src = Path(name)
            if src.exists() and src.suffix == ".py":
                await _validate_python_file_syntax(src)

        # Upload selected dashboard web files.
        if selected_dashboard_files:
            self._emit("supervisor", "Deploying dashboard web files...", 77)
            for _fname in sorted(set(selected_dashboard_files)):
                # Always resolve dashboard_web files from local source tree
                if _fname.startswith("dashboard_web/"):
                    _src = DASHBOARD_WEB_DIR / _fname.split("dashboard_web/")[1]
                elif _fname.startswith("remote_services/dashboard_web/"):
                    _src = DASHBOARD_WEB_DIR / _fname.split("remote_services/dashboard_web/")[1]
                else:
                    _src = Path(_fname)
                if _src.exists():
                    # Upload to a flat path under remote_temp_root so phase_install's
                    # `cp /tmp/*.py` glob picks it up regardless of local path structure.
                    await self._client.async_put_file(_src, f"{remote_temp_root}/{_src.name}")
                else:
                    _LOGGER.warning("Dashboard web file not found, skipping: %s", _src)

        # Additionally, always upload the entire DASHBOARD_WEB_DIR contents so
        # the Pi receives the latest dashboard sources even if SERVICE_REGISTRY
        # omits a file. Files are uploaded to remote_temp_root for the install
        # script to pick up and place into the remote web directory.
        try:
            dashboard_root = DASHBOARD_WEB_DIR
            if dashboard_root.exists():
                # Perform filesystem traversal in a thread to avoid blocking the
                # Home Assistant event loop (scandir/glob are blocking).
                try:
                    files = await asyncio.to_thread(lambda: [p for p in dashboard_root.rglob("*") if p.is_file()])
                except Exception:
                    files = []

                for p in sorted(files):
                    try:
                        await self._client.async_put_file(p, f"{remote_temp_root}/{p.name}")
                    except Exception:
                        _LOGGER.debug("Failed to upload dashboard file (ignored): %s", p)
        except Exception:
            _LOGGER.debug("Could not iterate DASHBOARD_WEB_DIR for bulk upload", exc_info=True)

        # Upload shared web files (runtime dependencies used by all dashboards)
        _COMPONENT_ROOT = Path(__file__).parent
        for _shared_fname in SHARED_WEB_FILES:
            _shared_src = _COMPONENT_ROOT / _shared_fname
            if _shared_src.exists():
                await self._client.async_put_file(_shared_src, f"{remote_temp_root}/{_shared_src.name}")
            else:
                _LOGGER.warning("Shared web file not found, skipping: %s", _shared_src)
        await self.phase_install()

        # Install Python packages required by selected dashboard services.
        if selected_dashboard_packages:
            await self.install_python_packages(
                sorted(selected_dashboard_packages),
                "dashboard",
            )

        # Install supervisor package
        self._emit("supervisor", "Uploading supervisor package...", 78)
        tar_bytes = await _pack_directory(supervisor_src, arcname="supervisor")
        await self._client.async_put_bytes(tar_bytes, f"{remote_temp_root}/supervisor.tar.gz")

        # Install systemd services; dashboard service is optional per selected capabilities.
        template_files = ["PerimeterControl-supervisor.service.template"] + selected_dashboard_templates
        await self.install_systemd_services(template_files)

        # Always sync selected service descriptors so Supervisor reads current access_profile
        # (mode/port/tls) instead of stale files from previous deployments.
        await self.deploy_service_descriptors(self._selected_services, auto_entities=self._auto_entities)
        
        # Install supervisor
        sup_install_script = _build_supervisor_install_script()
        await self._client.async_run_b64(sup_install_script)
        
        self._emit("supervisor", "Supervisor installed", 85)

    async def _phase_restart(self) -> None:
        """Restart systemd services."""
        self._emit("restart", "Restarting services...", 87)
        
        # Start supervisor service
        try:
            # Clear rate-limit counter so systemd allows a fresh start after crash loop
            await self._client.async_run(
                f"sudo systemctl reset-failed perimetercontrol-supervisor 2>/dev/null || true"
            )
            await self._client.async_run(f"sudo systemctl restart perimetercontrol-supervisor")
            await asyncio.sleep(2)
            _LOGGER.info("Supervisor service restarted successfully")
        except Exception as exc:
            try:
                journal = await self._client.async_run(
                    f"sudo journalctl -u perimetercontrol-supervisor -n 50 --no-pager 2>&1 || true"
                )
                status_out = await self._client.async_run(
                    f"sudo systemctl status perimetercontrol-supervisor --no-pager 2>&1 || true"
                )
                _LOGGER.warning(
                    "Supervisor service failed to restart: %s\nStatus:\n%s\nJournal:\n%s",
                    exc, status_out.strip(), journal.strip(),
                )
            except Exception:
                _LOGGER.warning("Supervisor service failed to restart: %s", exc)

        supervisor_ok, supervisor_last = await self._wait_for_service_active("perimetercontrol-supervisor")
        if not supervisor_ok:
            status_out, journal = await self._get_condensed_service_diagnostics("perimetercontrol-supervisor")
            _LOGGER.error(
                "Supervisor failed post-restart health gate (last is-active=%s).\nStatus:\n%s\nRecent Journal:\n%s",
                supervisor_last.strip() or "<empty>",
                status_out.strip(),
                journal.strip(),
            )
            raise RuntimeError("Supervisor failed post-restart health gate")

        # Fire any deferred deploy_api calls now that the supervisor is healthy
        for service_id, deploy_api in self._pending_deploy_apis:
            try:
                deploy_cmd = f"curl -fsS -X POST {deploy_api} -H 'Content-Type: application/json' -d '{{}}'"
                await self._client.async_run(deploy_cmd)
                _LOGGER.info("Triggered backend deployment via API for %s", service_id)
            except Exception as exc:
                _LOGGER.warning("Failed to trigger backend deployment for %s: %s", service_id, exc)

        for service_id in self._selected_services:
            service_info = SERVICE_REGISTRY.get(service_id, {})
            unit = service_info.get("unit")
            if not unit:
                continue

            # Read dashboard port from the YAML config template (single source of truth).
            port = None
            config_template_rel = service_info.get("config_template")
            if config_template_rel:
                try:
                    import yaml as _yaml
                    template_path = TEMPLATES_DIR / Path(config_template_rel).name
                    if await asyncio.to_thread(template_path.exists):
                        template_text = await asyncio.to_thread(template_path.read_text, encoding="utf-8")
                        tmpl = await asyncio.to_thread(_yaml.safe_load, template_text) or {}
                        port = (
                            tmpl.get("dashboard", {}).get("server", {}).get("port")
                            or tmpl.get("port")
                        )
                except Exception as _exc:
                    _LOGGER.debug("Could not read port from config template for %s: %s", service_id, _exc)

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

        all_units = {info.get("unit") for info in SERVICE_REGISTRY.values() if info.get("unit")}
        selected_units = {SERVICE_REGISTRY.get(s, {}).get("unit") for s in self._selected_services if SERVICE_REGISTRY.get(s, {}).get("unit")}
        non_selected_units = all_units - selected_units
        for unit in sorted(u for u in non_selected_units if u):
            await self._client.async_run(
                f"sudo systemctl stop {unit} 2>/dev/null || true; "
                f"sudo systemctl disable {unit} 2>/dev/null || true"
            )
            _LOGGER.info("Dashboard service %s is not selected; ensured it is stopped/disabled", unit)
        
        self._emit("restart", "Services restarted", 95)

    async def _phase_verify(self) -> None:
        """Verify deployment success."""
        self._emit("verify", "Verifying service health...", 96)
        
        # Check supervisor service
        supervisor_status = await self._client.async_run(
            f"systemctl is-active perimetercontrol-supervisor || echo INACTIVE"
        )
        supervisor_active = "active" in supervisor_status and "INACTIVE" not in supervisor_status
        
        dashboard_results: list[tuple[str, str, bool]] = []
        for service_id in self._selected_services:
            service_info = SERVICE_REGISTRY.get(service_id, {})
            unit = service_info.get("unit")
            if not unit:
                continue
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
            self._emit("verify", "Deploy complete — all services running", 100)
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
            self._emit("verify", "Deploy failed — services need attention", 100)
            _LOGGER.error("Deployment verification failed - services need attention")
            for svc_name, svc_const in (
                ("Supervisor", "perimetercontrol-supervisor"),
                *[(f"Dashboard({service_id})", SERVICE_REGISTRY.get(service_id, {}).get("unit")) for service_id in self._selected_services if SERVICE_REGISTRY.get(service_id, {}).get("unit")],
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
        for attempt in range(attempts):
            curl_cmd = f"curl -fsS --max-time 3 http://127.0.0.1:{port}/ >/dev/null 2>&1 && echo HTTP_OK || echo HTTP_FAIL"
            _LOGGER.warning("HTTP probe (attempt %s/%s): %s", attempt + 1, attempts, curl_cmd)
            last_probe = await self._client.async_run(curl_cmd)
            if "HTTP_OK" in last_probe:
                return True, last_probe
            await asyncio.sleep(delay_seconds)
        return False, last_probe


# ------------------------------------------------------------------
# Script builders
# ------------------------------------------------------------------

def _build_install_script() -> str:
    """Build the remote install script for Phase 3."""
    # Dynamically collect all web_files and script_files from SERVICE_REGISTRY
    file_entries = []
    for service_info in SERVICE_REGISTRY.values():
        for fname in service_info.get("web_files", []):
            file_entries.append((fname, remote_web_dir, "0644"))
        for fname in service_info.get("script_files", []):
            # Use 0755 for .py scripts, 0644 for .yaml/.conf, else default to 0755
            if fname.endswith(".py"):
                mode = "0755"
            elif fname.endswith(('.yaml', '.yml', '.conf')):
                mode = "0644"
            else:
                mode = "0755"
            file_entries.append((fname, remote_scripts_dir, mode))

    # Also include shared web assets (e.g. static CSS/JS) so files uploaded
    # via SHARED_WEB_FILES are installed into the web directory with
    # preserved subpaths (static/css/...)
    try:
        from .const import SHARED_WEB_FILES as _SHARED
        for shared in _SHARED:
            # shared entries are repository-relative paths (e.g. remote_services/dashboard_web/static/css/pc-dashboard.css)
            file_entries.append((shared, remote_web_dir, "0644"))
    except Exception:
        # If const can't be read for some reason, continue without shared entries
        pass

    # Use the configurable install commands
    lines = ["set -e"] + _get_install_commands()
    for fname, dest, mode in file_entries:
        base = fname.split("/")[-1]
        # Compute a relative destination path for dashboard_web files so that
        # directory structure (e.g. static/css/) is preserved under remote_web_dir.
        rel = None
        if "dashboard_web/" in fname:
            rel = fname.split("dashboard_web/")[-1]
        elif "remote_services/dashboard_web/" in fname:
            rel = fname.split("remote_services/dashboard_web/")[-1]
        # If we have a relative path, ensure the destination directory exists
        if rel and "/" in rel:
            rel_dir = "/".join(rel.split("/")[:-1])
            dst_path = f"{dest}/{rel_dir}/{base}"
            lines.append(f"sudo mkdir -p {dest}/{rel_dir} || true")
            lines.append(
                f"if [ -f {remote_temp_root}/{base} ]; then echo INSTALL_DEBUG: found {remote_temp_root}/{base}; "
                f"echo INSTALL_DEBUG: installing to {dst_path}; "
                f"sudo install -o root -g root -m {mode} {remote_temp_root}/{base} {dst_path} && echo INSTALL_OK: {dst_path} || echo INSTALL_FAIL: {dst_path}; "
                f"else echo INSTALL_MISSING: {remote_temp_root}/{base}; fi"
            )
        else:
            dst_path = f"{dest}/{base}"
            lines.append(
                f"if [ -f {remote_temp_root}/{base} ]; then echo INSTALL_DEBUG: found {remote_temp_root}/{base}; "
                f"echo INSTALL_DEBUG: installing to {dst_path}; "
                f"sudo install -o root -g root -m {mode} {remote_temp_root}/{base} {dst_path} && echo INSTALL_OK: {dst_path} || echo INSTALL_FAIL: {dst_path}; "
                f"else echo INSTALL_MISSING: {remote_temp_root}/{base}; fi"
            )
    # Also copy any uploaded python dashboard modules to the web directory so
    # bulk uploads placed in the temp root will be installed even if not
    # enumerated in SERVICE_REGISTRY. Use install to set correct permissions.
    lines.append(f"sudo mkdir -p {remote_web_dir} || true")
    lines.append(
        f"for f in {remote_temp_root}/*.py; do if [ -f \"$f\" ]; then echo INSTALL_DEBUG: installing $f to {remote_web_dir}/$(basename \"$f\"); "
        f"sudo install -o root -g root -m 0644 \"$f\" {remote_web_dir}/$(basename \"$f\") && echo INSTALL_OK: $f || echo INSTALL_FAIL: $f; fi; done"
    )
    lines.append("echo INSTALL_OK")
    return "\n".join(lines)


def _build_supervisor_install_script() -> str:
        from .const import remote_state_root, remote_log_root, remote_supervisor_dir, remote_temp_root, remote_systemd_root
        return f"""set -e
# Ensure required directories exist before service units are started
sudo mkdir -p {remote_state_root} {remote_log_root}
sudo chmod 755 {remote_state_root} {remote_log_root}
# Deploy tmpfiles.d config so directories survive reboots (runs before services at boot)
printf 'd {remote_state_root} 0755 root root -\nd {remote_log_root} 0755 root root -\n' | sudo tee /etc/tmpfiles.d/perimeter-control.conf > /dev/null
sudo systemd-tmpfiles --create /etc/tmpfiles.d/perimeter-control.conf 2>/dev/null || true
sudo cp -a {remote_supervisor_dir} {remote_temp_root}/PerimeterControl-supervisor-backup 2>/dev/null || true
cd {remote_temp_root}
rm -rf {remote_temp_root}/supervisor
tar --no-same-permissions --no-same-owner -xzf {remote_temp_root}/supervisor.tar.gz
sudo mkdir -p {remote_supervisor_dir}
sudo cp -r {remote_temp_root}/supervisor/. {remote_supervisor_dir}/
sudo chown -R root:root {remote_supervisor_dir}
sudo find {remote_supervisor_dir} -type f -exec chmod 644 {{}} +
sudo find {remote_supervisor_dir} -type d -exec chmod 755 {{}} +
[ -f {remote_temp_root}/perimetercontrol-supervisor.service ] && \
    sudo install -o root -g root -m 0644 {remote_temp_root}/perimetercontrol-supervisor.service \
    {remote_systemd_root}/perimetercontrol-supervisor.service && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable perimetercontrol-supervisor.service || true
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
