"""Coordinator — polls node health and drives deploy operations."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional, cast
import json
import asyncio
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SERVICES,
    CONF_SSH_KEY,
    CONF_SUPERVISOR_PORT,
    CONF_USER,
    DEFAULT_API_PORT,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_SSH_PORT,
    DOMAIN,
    SYSTEMD_SUPERVISOR,
)
from .deployer import DeployProgress, Deployer
from .ssh_client import SshClient, SshConnectionError
from .service_descriptor import ServiceDescriptor, load_service_descriptors
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_POLL_INTERVAL = timedelta(seconds=30)

# Status keys stored in coordinator.data
KEY_DASHBOARD_ACTIVE = "dashboard_active"
KEY_SUPERVISOR_ACTIVE = "supervisor_active"
KEY_LAST_DEPLOY = "last_deploy"
KEY_DEPLOY_IN_PROGRESS = "deploy_in_progress"
KEY_DEPLOY_PROGRESS = "deploy_progress"


class PerimeterControlCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator per config entry (one Pi node)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{entry.data[CONF_HOST]}",
            update_interval=_POLL_INTERVAL,
        )
        self._entry = entry
        self._client: Optional[SshClient] = None  # SSH client for deploys
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._supervisor_base_url = f"http://{entry.data[CONF_HOST]}:{entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)}/api/v1"
        self._supervisor_ws_url = f"ws://{entry.data[CONF_HOST]}:{entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)}/api/v1/events"
        self._selected_services: list[str] = entry.data.get(CONF_SERVICES, [])
        self._deploy_in_progress = False
        self._deploy_log: list[DeployProgress] = []
        self._running = True
        self._reconnect_attempts = 0
        self._websocket_task: Optional[asyncio.Task] = None
        self._websocket_starting = False
        self._client_initialized = False  # Track SSH client state
        self._noted_local_only_services: set[str] = set()
        self._noted_isolated_services: set[str] = set()
        # Service descriptors will be loaded in create() method
        self._service_descriptors: dict[str, ServiceDescriptor] = {}

    def _spawn_background_task(self, coro: Any, name: str) -> asyncio.Task[Any]:
        """Create a background task that won't block Home Assistant startup."""
        create_bg = getattr(self.hass, "async_create_background_task", None)
        if callable(create_bg):
            try:
                return cast(asyncio.Task[Any], create_bg(coro, name=name))
            except TypeError:
                # Compatibility with older HA signatures.
                return cast(asyncio.Task[Any], create_bg(coro, name))
        return cast(asyncio.Task[Any], self.hass.async_create_task(coro, name=name))

    @classmethod
    async def create(cls, hass: HomeAssistant, entry: ConfigEntry) -> PerimeterControlCoordinator:
        # Load SSH key from file at runtime if not present in config entry, using executor
        private_key = entry.data.get(CONF_SSH_KEY, "")
        ssh_key_path = entry.data.get("ssh_key_path", "")
        if not private_key and ssh_key_path:
            try:
                private_key = await hass.async_add_executor_job(
                    lambda: Path(ssh_key_path).read_text(encoding="utf-8")
                )
                _LOGGER.debug("Loaded SSH key from %s (%d bytes)", ssh_key_path, len(private_key))
            except Exception as exc:
                _LOGGER.error("Failed to read SSH key file: %s", exc)
                private_key = ""
        instance = cls(hass, entry)
        
        # Load service descriptors asynchronously now that we're in async context
        try:
            descriptors_dir = Path(__file__).parent / "service_descriptors"
            descriptors = await load_service_descriptors(descriptors_dir, instance._selected_services)
            instance._service_descriptors = {d.id: d for d in descriptors}
            _LOGGER.debug("Loaded %d service descriptors", len(instance._service_descriptors))
        except Exception as exc:
            _LOGGER.warning("Failed to load service descriptors: %s", exc)
            instance._service_descriptors = {}
        
        instance._client = SshClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
            user=entry.data[CONF_USER],
            private_key=private_key,
        )
        instance._client_initialized = True
        
        # Initialize HTTP session for Supervisor API with proper SSL handling
        instance._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(
                limit=10,
                ssl=False,  # Pi supervisor typically uses HTTP not HTTPS
                force_close=False,  # Allow connection reuse
                keepalive_timeout=30,
            ),
        )
        
        # Check if supervisor is available before starting WebSocket
        try:
            await instance._supervisor_get("/health")
            _LOGGER.info("Supervisor API is available at %s", instance._supervisor_base_url)
            
            # Also check if dashboard is healthy by testing a simple HTTP request
            try:
                # Use the PerimeterControl dashboard port for health check
                import os
                dashboard_port = int(os.environ.get('PERIMETERCONTROL_DASHBOARD_PORT', DEFAULT_DASHBOARD_PORT))
                dashboard_url = f"http://{instance._entry.data[CONF_HOST]}:{dashboard_port}/"
                _LOGGER.warning("Dashboard health check URL: %s", dashboard_url)
                if not instance._http_session.closed:
                    async with instance._http_session.get(dashboard_url) as resp:
                        if resp.status == 200:
                            _LOGGER.info("Dashboard is also healthy. Both services running, skipping deployment.")
                            # Start WebSocket connection after successful health checks  
                            instance._spawn_background_task(
                                instance._delayed_websocket_start(),
                                name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                            )
                        else:
                            raise Exception(f"Dashboard returned HTTP {resp.status}")
                else:
                    raise Exception("HTTP session is closed")
            except Exception as dashboard_exc:
                _LOGGER.warning("Supervisor healthy but dashboard unhealthy (%s). Will attempt deployment to fix dashboard.", dashboard_exc)
                # Trigger deployment even though supervisor is working - but don't block startup
                _LOGGER.info("Scheduling deployment to fix dashboard issues...")
                if not instance._client_initialized or not instance._client:
                    _LOGGER.error("SSH client not initialized, cannot schedule deployment")
                else:
                    async def _ssh_test_and_deploy() -> None:
                        """Background task to test SSH and start deployment if successful."""
                        try:
                            if not instance._client_initialized or not instance._client:
                                _LOGGER.error("SSH client not initialized, cannot test connection")
                                return

                            await instance._client.async_run("echo 'SSH test'")
                            _LOGGER.info("SSH connection successful. Starting deployment to fix dashboard...")

                            deploy_task = instance._spawn_background_task(
                                instance._auto_deploy_supervisor(),
                                name=f"perimeter_control_auto_deploy_{instance._entry.entry_id}"
                            )

                            def deployment_completed(task: asyncio.Task[Any]) -> None:
                                try:
                                    if task.exception():
                                        _LOGGER.error("Auto-deployment task failed with exception: %s",
                                                    task.exception(), exc_info=task.exception())
                                    else:
                                        _LOGGER.debug("Auto-deployment task completed successfully")
                                        # Start websocket connection after successful deployment
                                        instance._spawn_background_task(
                                            instance._delayed_websocket_start(),
                                            name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                                        )
                                except Exception as cb_exc:
                                    _LOGGER.error("Error in deployment completion callback: %s", cb_exc)

                            deploy_task.add_done_callback(deployment_completed)

                        except Exception as ssh_exc:
                            _LOGGER.warning("SSH connection failed during background test: %s", ssh_exc)
                            # Still try to start WebSocket in case services are actually working
                            instance._spawn_background_task(
                                instance._delayed_websocket_start(),
                                name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                            )
                
                    # Schedule SSH test and deployment as background task
                    instance._spawn_background_task(
                        _ssh_test_and_deploy(),
                        name=f"perimeter_control_ssh_test_{instance._entry.entry_id}"
                    )
                
        except Exception as exc:
            _LOGGER.info("Supervisor API not available at %s (this is expected during initial setup): %s. Will attempt auto-deployment.", 
                          instance._supervisor_base_url, exc)
            
            # Don't try to start WebSocket during initialization - it blocks startup
            # WebSocket connection will be attempted later via background task
            
            # Try auto-deployment if supervisor is not available
            _LOGGER.info("Scheduling auto-deployment check...")
            
            async def _ssh_test_and_auto_deploy() -> None:
                """Background task to test SSH and start deployment if successful."""
                try:
                    if not instance._client_initialized or not instance._client:
                        _LOGGER.error("SSH client not initialized, cannot test connection")
                        return

                    # Quick SSH test to see if deployment is possible
                    await instance._client.async_run("echo 'SSH test'")
                    _LOGGER.info("SSH connection successful. Starting automatic deployment...")

                    # Trigger automatic deployment in background with explicit task tracking
                    deploy_task = instance._spawn_background_task(
                        instance._auto_deploy_supervisor(),
                        name=f"perimeter_control_auto_deploy_{instance._entry.entry_id}"
                    )

                    # Add task done callback for debugging
                    def deployment_completed(task: asyncio.Task[Any]) -> None:
                        try:
                            if task.exception():
                                _LOGGER.error("Auto-deployment task failed with exception: %s",
                                            task.exception(), exc_info=task.exception())
                            else:
                                _LOGGER.debug("Auto-deployment task completed successfully")
                                # Start websocket connection after successful deployment
                                instance._spawn_background_task(
                                    instance._delayed_websocket_start(),
                                    name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                                )
                        except Exception as callback_exc:
                            _LOGGER.error("Error in deployment callback: %s", callback_exc)

                    deploy_task.add_done_callback(deployment_completed)

                except Exception as ssh_exc:
                    _LOGGER.warning("SSH connection failed during auto-deployment check: %s", ssh_exc)
                    # Integration will work in monitoring mode only
            
            # Schedule SSH test and auto-deployment as background task - don't block startup
            instance._spawn_background_task(
                _ssh_test_and_auto_deploy(),
                name=f"perimeter_control_auto_deploy_check_{instance._entry.entry_id}"
            )
        
        return instance

    # ------------------------------------------------------------------
    # Supervisor API HTTP methods
    # ------------------------------------------------------------------

    async def _supervisor_get(self, endpoint: str) -> dict[str, Any]:
        """Make GET request to Supervisor API endpoint."""
        if not self._http_session or self._http_session.closed:
            raise UpdateFailed("HTTP session not initialized or closed")
        
        url = f"{self._supervisor_base_url}{endpoint}"
        try:
            # Add 10-second timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=10)
            async with self._http_session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return {}
                else:
                    raise UpdateFailed(f"Supervisor API error {response.status}: {await response.text()}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Failed to connect to Supervisor API: {exc}") from exc
    
    async def _supervisor_post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request to Supervisor API endpoint."""
        if not self._http_session or self._http_session.closed:
            raise UpdateFailed("HTTP session not initialized or closed")
        
        url = f"{self._supervisor_base_url}{endpoint}"
        try:
            # Add 10-second timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=10)
            async with self._http_session.post(url, json=data, timeout=timeout) as response:
                if response.status in (200, 201):
                    return await response.json()
                else:
                    raise UpdateFailed(f"Supervisor API error {response.status}: {await response.text()}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Failed to connect to Supervisor API: {exc}") from exc

    async def _fetch_supervisor_entities(self) -> list[dict[str, Any]]:
        """Fetch entity schema from Supervisor API."""
        try:
            result = await self._supervisor_get("/entities")
            return result.get("entities", [])
        except UpdateFailed:
            # Fallback to empty list if Supervisor unavailable
            return []

    async def _fetch_entity_states(self, entity_ids: list[str]) -> dict[str, Any]:
        """Fetch entity states in bulk from Supervisor API."""
        if not entity_ids:
            return {}
        
        try:
            result = await self._supervisor_post("/entities/states/query", {"entity_ids": entity_ids})
            states = result.get("states", [])
            normalized: dict[str, Any] = {}
            for item in states:
                if not isinstance(item, dict):
                    continue

                entity_id = item.get("entity_id")
                if not isinstance(entity_id, str) or not entity_id:
                    continue

                # API shape is typically: {"entity_id": "...", "state": {...}}
                # Normalize to the inner state payload expected by dynamic entities.
                payload = item.get("state")
                if isinstance(payload, dict):
                    normalized[entity_id] = payload
                else:
                    normalized[entity_id] = item

            return normalized
        except UpdateFailed:
            # Fallback to empty dict if Supervisor unavailable
            return {}

    async def _fetch_ha_integration_data(self) -> dict[str, Any]:
        """Fetch all integration data using the efficient HA endpoint."""
        try:
            result = await self._supervisor_get("/ha/integration")
            _LOGGER.debug("Supervisor API /ha/integration response: %s", result)
            
            # Also fetch dashboard URLs for convenience
            dashboard_urls = await self.get_dashboard_urls()
            
            # Log what we're extracting
            entities = result.get("entities", [])
            services_raw = result.get("services", [])
            node_info = result.get("node_info", {})
            capabilities = node_info.get("capabilities", [])

            entity_ids = [e.get("id") for e in entities if e.get("id")]
            _LOGGER.info("[DEBUG] Entities from /ha/integration: %s", entity_ids)

            services: list[dict[str, Any]] = []
            services_config: dict[str, Any] = {}
            if isinstance(services_raw, list):
                services = [s for s in services_raw if isinstance(s, dict)]
                services_config = {
                    (s.get("id") or f"service_{idx}"): s
                    for idx, s in enumerate(services)
                }
            elif isinstance(services_raw, dict):
                services_config = services_raw
                services = [s for s in services_raw.values() if isinstance(s, dict)]

            _LOGGER.info(
                "Extracted from API - entities: %d, services: %d, capabilities: %d",
                len(entities),
                len(services),
                len(capabilities) if isinstance(capabilities, list) else 0,
            )
            if not services and isinstance(capabilities, list) and capabilities:
                _LOGGER.debug("API reported capabilities but no services; waiting for service registration")
            
            # Transform to match expected format
            dashboard_entities = self._create_dashboard_url_entities(services, dashboard_urls)
            
            # Transform entities array into entity_states dict for compatibility.
            # Prefer live state values from /entities/states/query when available.
            entity_states = {}
            all_entities = entities + dashboard_entities  # Include dashboard entities in state processing
            entity_ids = [e.get("id") for e in all_entities if e.get("id")]
            live_entity_states = await self._fetch_entity_states(entity_ids)
            _LOGGER.info("[DEBUG] State keys from /entities/states/query: %s", list(live_entity_states.keys()))
            for entity in all_entities:
                entity_id = entity.get("id")
                if entity_id:
                    state_payload = live_entity_states.get(entity_id, {})
                    if not isinstance(state_payload, dict) or not state_payload.get("state"):
                        # Fall back to schema/integration payload state when live state is unavailable
                        state_payload = {
                            "state": entity.get("state"),
                            "attributes": entity.get("attributes", {}),
                            "last_updated": entity.get("last_updated"),
                            "friendly_name": entity.get("friendly_name"),
                            "icon": entity.get("icon"),
                            "device_class": entity.get("device_class"),
                            "unit_of_measurement": entity.get("unit_of_measurement"),
                            "state_class": entity.get("state_class"),
                        }

                    # Wrap the entity data in the expected format
                    entity_states[entity_id] = {
                        "state": state_payload
                    }
            
            _LOGGER.info("Transformed %d entities (including %d dashboard URLs) into entity_states dict", len(entity_states), len(dashboard_entities))

            # /ha/integration (Tornado) does not include a top-level health object.
            # Reaching this point means supervisor is responding, so mark it active.
            supervisor_active = True

            # Consider dashboard active when at least one service reports active status
            # with a dashboard URL, or any normalized dashboard URL is available.
            dashboard_active = any(
                (s.get("status") == "active") and bool(s.get("dashboard_url"))
                for s in services
                if isinstance(s, dict)
            ) or bool(dashboard_urls)
            
            return {
                "supervisor_active": supervisor_active,
                "dashboard_active": dashboard_active,
                "supervisor_entities": entities + dashboard_entities,
                "entity_states": entity_states,
                "services_config": services_config,
                "config_changes": result.get("config_changes", {}),
                "dashboard_urls": dashboard_urls,
            }
        except UpdateFailed:
            # Fallback to empty data if Supervisor unavailable
            return {
                "supervisor_active": False,
                "dashboard_active": False,
                "supervisor_entities": [],
                "entity_states": {},
                "services_config": {},
                "config_changes": {},
                "dashboard_urls": {},
            }

    async def _check_supervisor_health(self) -> bool:
        """Check if Supervisor API is responding."""
        try:
            await self._supervisor_get("/health")
            return True
        except UpdateFailed:
            return False

    async def _ssh_supervisor_local_health(self) -> tuple[bool, str]:
        """Check supervisor health from the remote host itself via SSH."""
        if not self._client_initialized or not self._client:
            return False, "SSH client not initialized"

        cmd = (
            "curl -fsS --max-time 3 http://127.0.0.1:8080/api/v1/health >/dev/null 2>&1 "
            "&& echo LOCAL_HEALTH_OK || echo LOCAL_HEALTH_FAIL"
        )
        try:
            result = await self._client.async_run(cmd)
            ok = "LOCAL_HEALTH_OK" in result
            return ok, result.strip()
        except Exception as exc:
            return False, str(exc)

    async def _ssh_restart_supervisor_for_recovery(self) -> None:
        """Attempt a one-shot supervisor restart and log status for diagnosis."""
        if not self._client_initialized or not self._client:
            _LOGGER.warning("Cannot run supervisor recovery restart: SSH client not initialized")
            return

        try:
            # Clear systemd rate-limit counter so a fresh restart is allowed
            await self._client.async_run(
                f"sudo systemctl reset-failed {SYSTEMD_SUPERVISOR} 2>/dev/null || true"
            )
            await self._client.async_run(f"sudo systemctl restart {SYSTEMD_SUPERVISOR}")
            await asyncio.sleep(2)
            status = await self._client.async_run(
                f"systemctl is-active {SYSTEMD_SUPERVISOR} 2>/dev/null || echo inactive"
            )
            _LOGGER.warning("Supervisor recovery restart status: %s", status.strip())
        except Exception as exc:
            # Capture crash logs so the root cause is visible in HA logs
            try:
                journal = await self._client.async_run(
                    f"sudo journalctl -u {SYSTEMD_SUPERVISOR} -n 50 --no-pager 2>&1 || true"
                )
                status_out = await self._client.async_run(
                    f"sudo systemctl status {SYSTEMD_SUPERVISOR} --no-pager 2>&1 || true"
                )
                _LOGGER.warning(
                    "Supervisor recovery restart failed: %s\nStatus:\n%s\nJournal:\n%s",
                    exc, status_out.strip(), journal.strip(),
                )
            except Exception:
                _LOGGER.warning("Supervisor recovery restart failed: %s", exc)
    
    async def _fetch_services_config(self) -> dict[str, Any]:
        """Fetch service configurations from Supervisor API."""
        try:
            services_result = await self._supervisor_get("/services")
            services = services_result.get("services", [])
            
            configs = {}
            for service in services:
                service_id = service.get("id")
                if service_id:
                    # Fetch config for each service
                    try:
                        config_result = await self._supervisor_get(f"/services/{service_id}/config")
                        access_result = await self._supervisor_get(f"/services/{service_id}/access")
                        
                        configs[service_id] = {
                            "config": config_result,
                            "access_profile": access_result.get("access_profile", {}),
                            "service_info": service,
                        }
                    except UpdateFailed:
                        # Skip services with config errors
                        continue
                        
            return configs
        except UpdateFailed:
            return {}
    
    async def get_dashboard_urls(self) -> dict[str, str]:
        """Get dashboard URLs for all services using efficient endpoint."""
        try:
            result = await self._supervisor_get("/ha/dashboard-urls")
            # API returns DashboardUrls model: {"services": {id: DashboardUrl}, "timestamp": ...}
            services_data = result.get("services", {})
            if not isinstance(services_data, dict):
                _LOGGER.warning("Unexpected dashboard URL payload from supervisor: %r", services_data)
                return {}
            # Each value is a serialized DashboardUrl object; extract the "url" string field.
            raw_urls: dict[str, str] = {}
            for sid, svc in services_data.items():
                if not isinstance(sid, str):
                    continue
                if isinstance(svc, dict):
                    url = svc.get("url", "")
                    status = svc.get("status", "unknown")
                    mode = svc.get("mode", svc.get("access_mode", "unknown"))
                    port = svc.get("port", "unknown")
                    _LOGGER.warning(
                        "Dashboard service status for %s: status=%s mode=%s port=%s url=%s",
                        sid,
                        status,
                        mode,
                        port,
                        url or "<empty>",
                    )
                    if status != "active":
                        _LOGGER.warning(
                            "Dashboard service %s is not active, so the URL may refuse connections: %s",
                            sid,
                            url or "<empty>",
                        )
                elif isinstance(svc, str):
                    url = svc
                else:
                    continue
                if url:
                    raw_urls[sid] = url
                    _LOGGER.warning("Dashboard URL discovered for %s: %s", sid, url)
            if not raw_urls:
                _LOGGER.warning("No dashboard URLs returned by /ha/dashboard-urls")
            return self._normalize_dashboard_urls(raw_urls)
        except UpdateFailed:
            # Fall back to manual construction
            _LOGGER.warning("Dashboard URL API unavailable; using legacy URL construction")
            return self._build_legacy_dashboard_urls()

    def _normalize_dashboard_urls(self, dashboard_urls: dict[str, str]) -> dict[str, str]:
        """Normalize dashboard URLs to the integration host when API returns localhost URLs."""
        normalized: dict[str, str] = {}
        host = self._entry.data.get(CONF_HOST)

        for service_id, url in dashboard_urls.items():
            if not isinstance(service_id, str) or not isinstance(url, str) or not url:
                continue

            candidate = url.strip()
            if not candidate:
                continue

            try:
                parsed = urlparse(candidate)
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    # Always prefer configured node host for dashboard links so we avoid
                    # unreachable internal/container addresses from supervisor responses.
                    parsed_host = (parsed.hostname or "").strip().lower()
                    if host and parsed_host != str(host).strip().lower():
                        port = parsed.port
                        netloc = f"{host}:{port}" if port else str(host)
                        parsed = parsed._replace(netloc=netloc)
                        candidate = urlunparse(parsed)
                        _LOGGER.warning(
                            "Normalized dashboard URL for %s from %s to %s",
                            service_id,
                            url,
                            candidate,
                        )
                elif host and candidate.startswith(":"):
                    # Handle malformed ":5006" style values defensively.
                    candidate = f"http://{host}{candidate}"
                    _LOGGER.warning(
                        "Normalized malformed dashboard URL for %s from %s to %s",
                        service_id,
                        url,
                        candidate,
                    )
            except Exception:
                # Keep original URL when parsing fails.
                pass

            normalized[service_id] = candidate

        return normalized

    def get_dashboard_url(self, service_id: str) -> str | None:
        """Get dashboard URL for service from cached data or access profile."""
        # Try to get from cached dashboard URLs first
        dashboard_urls = self.data.get("dashboard_urls", {})
        if service_id in dashboard_urls:
            _LOGGER.warning("Using cached dashboard URL for %s: %s", service_id, dashboard_urls[service_id])
            return dashboard_urls[service_id]
            
        # Fall back to manual construction
        fallback_url = self._build_legacy_dashboard_url(service_id)
        _LOGGER.warning("Using legacy dashboard URL for %s: %s", service_id, fallback_url)
        return fallback_url
    
    def _build_legacy_dashboard_url(self, service_id: str) -> str | None:
        """Legacy method to build dashboard URL from access profile."""
        if self._selected_services and service_id not in self._selected_services:
            return None

        services_config = self.data.get("services_config", {})
        service_config = services_config.get(service_id, {})
        access_profile = service_config.get("access_profile", {})
        
        # Get port from access profile or fall back to default
        port = access_profile.get("port", 8080)
        
        # Check if service is exposed
        mode = access_profile.get("mode", "localhost")
        if mode in ("isolated", "localhost"):
            return None  # Service not directly accessible from HA host URL

        tls_mode = str(access_profile.get("tls_mode", "off"))
        scheme = "https" if tls_mode not in ("off", "none", "disabled", "false", "0", "") else "http"
            
        host = self._entry.data[CONF_HOST]
        return f"{scheme}://{host}:{port}/"
    
    def _build_legacy_dashboard_urls(self) -> dict[str, str]:
        """Legacy method to build all dashboard URLs manually."""
        services_config = self.data.get("services_config", {})
        dashboard_urls = {}

        # Prefer selected services to avoid publishing links for undeployed capabilities.
        service_ids = self._selected_services or list(services_config.keys())
        for service_id in service_ids:
            url = self._build_legacy_dashboard_url(service_id)
            if url:
                dashboard_urls[service_id] = url
                
        return dashboard_urls
    
    def _create_dashboard_url_entities(
        self,
        services: list[dict[str, Any]],
        dashboard_urls: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Create dashboard URL entities for each service with dashboard access."""
        from datetime import datetime
        
        dashboard_entities = []
        selected_ids = set(self._selected_services)

        def _is_selected(service_id: str | None) -> bool:
            return bool(service_id) and (not selected_ids or service_id in selected_ids)

        service_by_id = {
            s.get("id"): s
            for s in services
            if isinstance(s, dict) and _is_selected(s.get("id"))
        }

        normalized_urls: dict[str, str] = {}
        if isinstance(dashboard_urls, dict):
            for sid, url in dashboard_urls.items():
                if _is_selected(sid) and isinstance(url, str) and url:
                    normalized_urls[sid] = url

        # Accept URLs provided directly on service objects as a fallback.
        for service in services:
            service_id = service.get("id")
            dashboard_url = service.get("dashboard_url")
            service_status = service.get("status", "unknown")
            service_mode = service.get("access_mode", "unknown")
            service_port = service.get("port", "unknown")
            _LOGGER.warning(
                "Evaluating dashboard entity for %s: status=%s mode=%s port=%s url=%s",
                service_id or "<missing>",
                service_status,
                service_mode,
                service_port,
                dashboard_url or "<empty>",
            )
            if not _is_selected(service_id):
                continue

            if service_id and isinstance(dashboard_url, str) and dashboard_url and service_id not in normalized_urls:
                normalized_urls[service_id] = dashboard_url

        # If URLs are still missing, synthesize per-service links from known service ports.
        host = self._entry.data[CONF_HOST]
        for service in services:
            service_id = service.get("id")
            if not service_id or service_id in normalized_urls:
                continue

            if not _is_selected(service_id):
                continue

            access_mode = str(service.get("access_mode", "localhost"))
            if access_mode in ("localhost", "isolated"):
                continue

            port = service.get("port")
            tls_mode = str(service.get("tls_mode", "off"))
            scheme = "https" if tls_mode not in ("off", "none", "disabled", "false", "0", "") else "http"
            if isinstance(port, int):
                normalized_urls[service_id] = f"{scheme}://{host}:{port}/"
            elif isinstance(port, str) and port.isdigit():
                normalized_urls[service_id] = f"{scheme}://{host}:{port}/"

        # Last-resort fallback: publish a main dashboard URL on default dashboard port.
        # This ensures at least one clickable URL entity when API-provided links are not available yet.
        if not normalized_urls and (not selected_ids or "network_isolator" in selected_ids):
            normalized_urls["network_isolator"] = f"http://{host}:{DEFAULT_DASHBOARD_PORT}/"
            _LOGGER.warning(
                "No service dashboard URLs were available; publishing fallback main dashboard URL: %s",
                normalized_urls["network_isolator"],
            )

        for service_id, dashboard_url in normalized_urls.items():
            service = service_by_id.get(service_id, {})
            service_name = service.get("name", service_id)
            access_mode = service.get("access_mode", "localhost")
            if access_mode == "localhost" and service_id not in self._noted_local_only_services:
                self._noted_local_only_services.add(service_id)
                _LOGGER.info(
                    "Dashboard entity %s is local-only; a direct host URL may refuse unless a tunnel or proxy is active: %s",
                    service_id,
                    dashboard_url,
                )
            elif access_mode == "isolated" and service_id not in self._noted_isolated_services:
                self._noted_isolated_services.add(service_id)
                _LOGGER.info(
                    "Dashboard entity %s is isolated; suppressing any expectation that the host URL will be reachable: %s",
                    service_id,
                    dashboard_url,
                )
            
            # Create a sensor entity for the dashboard URL
            entity = {
                "id": f"{service_id}:dashboard:url",
                "type": "sensor",
                "platform": "sensor",
                "friendly_name": f"{service_name} Dashboard",
                "capability_id": service_id,
                "state": dashboard_url,
                "attributes": {
                    "service_id": service_id,
                    "service_name": service_name,
                    "port": service.get("port", DEFAULT_DASHBOARD_PORT),
                    "access_mode": access_mode,
                    "status": service.get("status", "unknown"),
                    "url": dashboard_url,
                    "entity_type": "dashboard_url"
                },
                "icon": "mdi:web",
                "device_class": None,
                "unit_of_measurement": None,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }

            if service.get("status") not in (None, "active"):
                _LOGGER.warning(
                    "Dashboard entity %s is published while service status is %s; URL=%s",
                    service_id,
                    service.get("status", "unknown"),
                    dashboard_url,
                )
            
            dashboard_entities.append(entity)
            
        return dashboard_entities
    
    def detect_config_changes(self) -> dict[str, str]:
        """Detect which service configs have changed externally."""
        # Compare current config hashes with last known state
        # This would be stored in entry options in a full implementation
        changes = {}
        services_config = self.data.get("services_config", {})
        
        for service_id, config_data in services_config.items():
            config_content = config_data.get("config", {}).get("content", "")
            # For now, just log that we could detect changes
            # In full implementation, store previous hash in entry options

            
        return changes
    
    async def _start_websocket_listener(self) -> None:
        """Start WebSocket connection for real-time events."""
        # Skip if already starting or websocket already exists
        if self._websocket_starting or self._websocket or not self._http_session or self._http_session.closed or not self._running:
            return
            
        # Set flag to prevent concurrent starts    
        self._websocket_starting = True
        try:
            _LOGGER.debug("Attempting WebSocket connection to: %s", self._supervisor_ws_url)
            # Add timeout to websocket connection
            self._websocket = await asyncio.wait_for(
                self._http_session.ws_connect(self._supervisor_ws_url),
                timeout=10.0
            )
            _LOGGER.info("WebSocket connected successfully to %s", self._supervisor_ws_url)
            
            # Reset reconnection attempts on successful connection
            self._reconnect_attempts = 0
            
            # Send subscription filter for entity events
            await self._websocket.send_str(json.dumps({
                "event_types": ["entity_updated", "deployment_completed", "capability_status_changed"]
            }))
            
            # Start background task to listen for events
            # Cancel any existing websocket task to prevent concurrent receive() calls
            if self._websocket_task and not self._websocket_task.done():
                self._websocket_task.cancel()
                try:
                    await self._websocket_task
                except asyncio.CancelledError:
                    pass
            
            self._websocket_task = self._spawn_background_task(
                self._websocket_event_loop(),
                name=f"perimeter_control_websocket_loop_{self._entry.entry_id}",
            )
            
            _LOGGER.info("WebSocket listener started for Supervisor events")
        except asyncio.TimeoutError:
            _LOGGER.warning("WebSocket connection timed out after 10 seconds")
            self._websocket = None
        except Exception as exc:
            _LOGGER.warning("Failed to start WebSocket listener: %s", exc)
            self._websocket = None
        finally:
            # Always clear the starting flag
            self._websocket_starting = False
    
    async def _websocket_event_loop(self) -> None:
        """Listen for WebSocket events and trigger coordinator updates."""
        if not self._websocket:
            _LOGGER.debug("No websocket connection available for event loop")
            return
            
        try:
            # Set a reasonable timeout for the entire event loop
            await asyncio.wait_for(
                self._websocket_message_loop(),
                timeout=300.0  # 5 minutes max, then restart connection
            )
        except asyncio.TimeoutError:
            _LOGGER.debug("WebSocket event loop timeout - restarting connection")
        except Exception as exc:
            _LOGGER.debug("WebSocket event loop error: %s", exc)
        finally:
            # Clean up websocket connection
            try:
                if self._websocket and not self._websocket.closed:
                    await asyncio.wait_for(self._websocket.close(), timeout=5.0)
            except Exception as close_exc:
                _LOGGER.debug("WebSocket close error: %s", close_exc)
            finally:
                self._websocket = None
            
            # Only attempt reconnection if we're still supposed to be running
            # and this isn't during shutdown
            if self._running and hasattr(self, '_reconnect_attempts'):
                self._reconnect_attempts = getattr(self, '_reconnect_attempts', 0) + 1
                if self._reconnect_attempts < 3:  # Limit reconnection attempts
                    _LOGGER.debug("Scheduling WebSocket reconnection attempt %d", self._reconnect_attempts)
                    # Use exponential backoff for reconnection
                    delay = min(10 * (2 ** (self._reconnect_attempts - 1)), 60)
                    await asyncio.sleep(delay)
                    if self._running:  # Check again after delay
                        try:
                            await self._start_websocket_listener()
                        except Exception as reconnect_exc:
                            _LOGGER.debug("WebSocket reconnection failed: %s", reconnect_exc)
                else:
                    _LOGGER.info("Max WebSocket reconnection attempts reached, giving up")
    
    async def _websocket_message_loop(self) -> None:
        """Process websocket messages in a loop with timeout handling."""
        try:
            while self._websocket and not self._websocket.closed and self._running:
                try:
                    # Use wait_for with timeout to prevent indefinite blocking
                    msg = await asyncio.wait_for(
                        self._websocket.receive(),
                        timeout=30.0  # 30 second timeout for each message
                    )
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            event = json.loads(msg.data)
                            await self._handle_supervisor_event(event)
                        except json.JSONDecodeError:
                            _LOGGER.debug("Invalid WebSocket JSON: %s", msg.data[:100])
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.warning("WebSocket error: %s", self._websocket.exception())
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        _LOGGER.debug("WebSocket closed by server")
                        break
                        
                except asyncio.TimeoutError:
                    # Timeout on receive - this is normal for idle connections
                    # Send a ping to keep connection alive
                    if self._websocket and not self._websocket.closed:
                        try:
                            await self._websocket.ping()
                            _LOGGER.debug("WebSocket ping sent (keepalive)")
                        except Exception as ping_exc:
                            _LOGGER.debug("WebSocket ping failed: %s", ping_exc)
                            break
                    continue
                    
        except (ConnectionError, OSError, aiohttp.ClientError) as exc:
            _LOGGER.debug("WebSocket connection error: %s", exc)
            return
        except Exception as exc:
            # Log unexpected errors at warning level - these might be bugs
            _LOGGER.warning("Unexpected WebSocket message loop error: %s", exc, exc_info=True)
            return
    
    async def _delayed_websocket_start(self) -> None:
        """Start websocket connection after a delay to avoid blocking coordinator startup."""
        try:
            # Wait a bit to ensure coordinator is fully initialized
            await asyncio.sleep(2)
            
            # Check if supervisor is available before starting websocket
            try:
                await self._supervisor_get("/health")
                await self._start_websocket_listener()
                _LOGGER.info("Delayed WebSocket connection established")
            except Exception as exc:
                _LOGGER.debug("Supervisor not ready for WebSocket connection: %s", exc)
                # Don't retry here - let normal reconnection logic handle it
        except Exception as exc:
            _LOGGER.warning("Failed to start delayed WebSocket connection: %s", exc)
    
    async def _handle_supervisor_event(self, event: dict[str, Any]) -> None:
        """Handle incoming Supervisor event."""
        event_type = event.get("type")
        
        if event_type == "entity_updated":
            # Entity state changed - trigger immediate refresh

            await self.async_request_refresh()
            
        elif event_type == "deployment_completed":
            # Deployment finished - refresh entity schema
            _LOGGER.info("Deployment completed: %s", event.get("deployment_id"))
            await self.async_request_refresh()
            
        elif event_type == "capability_status_changed":
            # Service started/stopped - refresh schema
            _LOGGER.info("Capability status changed: %s", event.get("capability_id"))
            await self.async_request_refresh()
    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the supervisor API efficiently."""
        _LOGGER.debug("Polling supervisor API...")
        
        # Get all integration data from the efficient HA endpoint
        try:
            integration_data = await self._fetch_ha_integration_data()
            _LOGGER.debug("Successfully fetched %d entities from supervisor", 
                        len(integration_data.get("supervisor_entities", [])))
            return integration_data
        except Exception as exc:
            _LOGGER.debug("Failed to fetch integration data: %s. Using fallback.", exc)
            
        # Fallback to basic status if HA endpoint fails
        supervisor_data = {}
        try:
            status = await self._supervisor_get("/status")
            supervisor_data = {
                KEY_SUPERVISOR_ACTIVE: True,
                KEY_DASHBOARD_ACTIVE: status.get("dashboard", {}).get("active", False),
                "services": status.get("services", {}),
                "system_info": status.get("system_info", {}),
                "supervisor_entities": [],  # No entities in fallback
            }
        except Exception as exc:
            _LOGGER.debug("Supervisor API not available: %s", exc)
            supervisor_data = {
                KEY_SUPERVISOR_ACTIVE: False,
                KEY_DASHBOARD_ACTIVE: False,
                "services": {},
                "system_info": {},
                "supervisor_entities": [],
            }
        
        _LOGGER.debug("Service descriptors loaded: %s", list(self._service_descriptors.keys()))
        
        # Legacy service status via SSH (fallback for deploy operations)
        service_status = {}
        if self._client_initialized and self._client:
            try:
                for service_id, desc in self._service_descriptors.items():
                    # Try to check systemd status for each service
                    sysd_name = f"{service_id}.service"
                    try:
                        result = await self._client.async_run(f"systemctl is-active {sysd_name} 2>/dev/null || echo inactive")
                        service_status[service_id] = (result.strip() == "active")
                    except Exception:
                        service_status[service_id] = False
            except SshConnectionError:
                # SSH failure is no longer critical since we have Supervisor API
                _LOGGER.debug("SSH connection failed, using Supervisor API only")
        else:
            _LOGGER.debug("SSH client not initialized, skipping legacy service status")

        return {
            # Supervisor API data via efficient combined endpoint
            **supervisor_data,
            # Legacy data for backward compatibility
            "legacy_service_status": service_status,
            "network_status": {"status": "unknown"},  # Placeholder
            "device_registry": {},  # Placeholder
        }

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    async def _auto_deploy_supervisor(self) -> None:
        """Automatically deploy supervisor if not available during initial setup."""
        try:
            # Check for concurrent deployment to prevent race conditions
            if self._deploy_in_progress:
                _LOGGER.warning("Auto-deployment skipped - deployment already in progress for %s", self._entry.data[CONF_HOST])
                return
                
            _LOGGER.warning("Auto-deployment started for %s", self._entry.data[CONF_HOST])
            
            # Use the existing deploy method but only log the key phases
            success = await self.async_deploy()
            
            if success:
                _LOGGER.warning("Auto-deployment completed successfully")
                
                # Try to connect to the newly deployed supervisor, with retries.
                last_exc = None
                for attempt in range(6):
                    try:
                        # On first attempt wait 1s, then exponential backoff
                        await asyncio.sleep(1 if attempt == 0 else min(10, 2 ** attempt))
                        await self._supervisor_get("/health")
                        
                        # Try to activate selected services in the Supervisor
                        _LOGGER.warning("About to call _activate_supervisor_services")
                        await self._activate_supervisor_services()
                        _LOGGER.warning("Finished calling _activate_supervisor_services")
                        
                        await self._start_websocket_listener()
                        _LOGGER.info("Successfully connected to deployed supervisor API (attempt %d)", attempt + 1)

                        # Trigger a coordinator update to refresh all entities
                        await self.async_request_refresh()
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        _LOGGER.debug("Supervisor not ready yet (attempt %d/6): %s", attempt + 1, exc)

                if last_exc is not None:
                    # Diagnose from remote host perspective: service may be up locally but unreachable from HA.
                    local_ok, local_detail = await self._ssh_supervisor_local_health()
                    if local_ok:
                        _LOGGER.warning(
                            "Deployment succeeded and supervisor is healthy on remote host, but HA cannot reach %s. "
                            "Check network path/firewall to %s:%s. Local check: %s",
                            self._supervisor_base_url,
                            self._entry.data[CONF_HOST],
                            self._entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT),
                            local_detail,
                        )
                    else:
                        _LOGGER.warning(
                            "Deployment succeeded but supervisor connection failed after retries; local health also failed (%s). "
                            "Attempting one supervisor restart and final retries.",
                            local_detail,
                        )
                        await self._ssh_restart_supervisor_for_recovery()

                        recovery_exc = None
                        for attempt in range(4):
                            try:
                                await asyncio.sleep(2 + attempt * 2)
                                await self._supervisor_get("/health")
                                await self._start_websocket_listener()
                                _LOGGER.info("Connected to supervisor API after recovery restart (attempt %d)", attempt + 1)
                                await self.async_request_refresh()
                                recovery_exc = None
                                break
                            except Exception as exc:
                                recovery_exc = exc
                                _LOGGER.debug("Recovery connect attempt %d/4 failed: %s", attempt + 1, exc)

                        if recovery_exc is not None:
                            _LOGGER.warning(
                                "Deployment succeeded but supervisor connection failed after recovery restart: %s",
                                recovery_exc,
                            )
            else:
                _LOGGER.error("Automatic supervisor deployment failed. Please check the integration logs and try manual deployment.")
        except Exception as exc:
            _LOGGER.error("Error during automatic supervisor deployment: %s", exc, exc_info=True)

    async def async_deploy(self) -> bool:
        """Start a deploy in the background; progress dispatched via coordinator updates."""
        if self._deploy_in_progress:
            _LOGGER.warning("Deploy already in progress for %s", self._entry.data[CONF_HOST])
            return False
            
        if not self._client_initialized or not self._client:
            _LOGGER.error("SSH client not initialized, cannot start deployment")
            return False

        _LOGGER.info("Starting deployment for %s", self._entry.data[CONF_HOST])
        self._deploy_in_progress = True
        self._deploy_log = []
        current_data = self.data or {}
        self.async_set_updated_data({
            **current_data,
            KEY_DEPLOY_IN_PROGRESS: True,
            KEY_DEPLOY_PROGRESS: [],
        })

        def _on_progress(p: DeployProgress) -> None:
            self._deploy_log.append(p)
            current_data = self.data or {}
            self.async_set_updated_data({
                **current_data,
                KEY_DEPLOY_IN_PROGRESS: True,
                KEY_DEPLOY_PROGRESS: list(self._deploy_log),
            })

        deployer = Deployer(
            client=self._client,
            selected_services=self._selected_services,
            service_descriptors=self._service_descriptors,
            progress_cb=_on_progress,
            hass=self.hass,
        )
        try:
            _LOGGER.debug("Calling deployer.async_deploy()...")
            success = await deployer.async_deploy()
            _LOGGER.info("Deployer finished with success=%s", success)

            if success:
                # Manual deploy path must also activate selected capabilities,
                # otherwise entities remain inactive until a separate auto-deploy path runs.
                try:
                    await self._activate_supervisor_services()
                except Exception as activate_exc:
                    _LOGGER.warning("Deployment succeeded but capability activation failed: %s", activate_exc)

                # Refresh once more so newly active entities/states are reflected in HA.
                await self.async_request_refresh()

            return success
        except Exception as exc:
            _LOGGER.error("Deployment failed with exception: %s", exc, exc_info=True)
            return False
        finally:
            self._deploy_in_progress = False
            current_data = self.data or {}
            self.async_set_updated_data({
                **current_data,
                KEY_DEPLOY_IN_PROGRESS: False,
                KEY_DEPLOY_PROGRESS: list(self._deploy_log),
            })
            await self.async_refresh()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def _activate_supervisor_services(self) -> None:
        """Activate selected services in the Supervisor via API deployment."""
        if not self._selected_services:
            _LOGGER.warning("No services selected for activation")
            return
            
        _LOGGER.warning("Activating selected services in Supervisor: %s", self._selected_services)
        
        # Build deployment payload for selected services
        deployment_payload = {}
        for service_id in self._selected_services:
            if service_id in self._service_descriptors:
                desc = self._service_descriptors[service_id]
                # Get version from descriptor metadata, default to "1.0.0"
                version = desc.raw.get("metadata", {}).get("version", "1.0.0")
                # Create basic capability config for deployment
                deployment_payload[service_id] = {
                    "name": desc.name,
                    "type": service_id,
                    "version": version,
                    "enabled": True,
                }
        
        if deployment_payload:
            try:
                _LOGGER.warning("Deploying capabilities to Supervisor: %s", list(deployment_payload.keys()))
                
                # Use a shorter timeout for deployment to avoid connection drops
                if not self._http_session or self._http_session.closed:
                    raise UpdateFailed("HTTP session not initialized or closed")
                
                url = f"{self._supervisor_base_url}/deployments"
                payload = {
                    "capabilities": deployment_payload,
                    "dry_run": False
                }
                _LOGGER.debug("Posting deployment payload to URL %s", url)
                
                timeout = aiohttp.ClientTimeout(total=30)  # Shorter timeout for deployment
                async with self._http_session.post(url, json=payload, timeout=timeout) as response:
                    _LOGGER.info("Supervisor deployment response status: %s", response.status)
                    if response.status in (200, 201):
                        result = await response.json()
                        _LOGGER.info("Supervisor deployment result: %s", result)
                    else:
                        error_text = await response.text()
                        _LOGGER.error("Deployment failed with status %s: %s", response.status, error_text)
                        raise UpdateFailed(f"Supervisor API error {response.status}: {error_text}")
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.warning("Failed to activate services in Supervisor (connection error): %s", exc)
            except Exception as exc:
                _LOGGER.warning("Failed to activate services in Supervisor: %s", exc)
    
    async def async_shutdown(self) -> None:
        """Clean shutdown of coordinator resources."""
        # Stop reconnection attempts
        self._running = False
        
        # Clear websocket starting flag
        self._websocket_starting = False
        
        # Cancel websocket background task
        if self._websocket_task and not self._websocket_task.done():
            self._websocket_task.cancel()
            try:
                await self._websocket_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket connection
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
            
        # Close HTTP session
        if self._http_session:
            await self._http_session.close()
            
        # Close SSH client
        if self._client_initialized and self._client:
            await self._client.async_close()
