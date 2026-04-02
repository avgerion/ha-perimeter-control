"""Coordinator — polls node health and drives deploy operations."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional
import json
import asyncio

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SERVICES,
    CONF_SSH_KEY,
    CONF_USER,
    DEFAULT_API_PORT,
    DEFAULT_SSH_PORT,
    DOMAIN,
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
        self._client = None  # SSH client for deploys
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._supervisor_base_url = f"http://{entry.data[CONF_HOST]}:{DEFAULT_API_PORT}/api/v1"
        self._supervisor_ws_url = f"ws://{entry.data[CONF_HOST]}:{DEFAULT_API_PORT}/api/v1/events"
        self._selected_services: list[str] = entry.data.get(CONF_SERVICES, [])
        self._deploy_in_progress = False
        self._deploy_log: list[DeployProgress] = []
        self._running = True
        self._reconnect_attempts = 0
        # Service descriptors will be loaded in create() method
        self._service_descriptors: dict[str, ServiceDescriptor] = {}

    @classmethod
    async def create(cls, hass: HomeAssistant, entry: ConfigEntry) -> PerimeterControlCoordinator:
        # Load SSH key from file at runtime if not present in config entry, using executor
        private_key = entry.data.get(CONF_SSH_KEY, "")
        ssh_key_path = entry.data.get("ssh_key_path", "")
        if not private_key and ssh_key_path:
            try:
                from pathlib import Path
                private_key = await hass.async_add_executor_job(
                    lambda: Path(ssh_key_path).read_text(encoding="utf-8")
                )
                _LOGGER.debug("Loaded SSH key from %s (%d bytes)", ssh_key_path, len(private_key))
            except Exception as exc:
                _LOGGER.error("Failed to read SSH key file: %s", exc)
                private_key = ""
        instance = cls(hass, entry)
        
        # Load service descriptors asynchronously now that we're in async context
        descriptors_dir = Path(__file__).parent / "service_descriptors"
        descriptors = await load_service_descriptors(descriptors_dir, instance._selected_services)
        instance._service_descriptors = {d.id: d for d in descriptors}
        
        instance._client = SshClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
            user=entry.data[CONF_USER],
            private_key=private_key,
        )
        # Initialize HTTP session for Supervisor API
        instance._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=aiohttp.TCPConnector(limit=10),
        )
        
        # Check if supervisor is available before starting WebSocket
        try:
            await instance._supervisor_get("/api/v1/health")
            _LOGGER.info("Supervisor API is available at %s", instance._supervisor_base_url)
            
            # Also check if dashboard is healthy by testing a simple HTTP request
            try:
                async with instance._http_session.get(f"http://{instance._entry.data[CONF_HOST]}:{instance._entry.data.get('dashboard_port', 8080)}/") as resp:
                    if resp.status == 200:
                        _LOGGER.info("Dashboard is also healthy. Both services running, skipping deployment.")
                        # Start WebSocket connection after successful health checks  
                        instance.hass.async_create_task(
                            instance._delayed_websocket_start(),
                            name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                        )
                    else:
                        raise Exception(f"Dashboard returned HTTP {resp.status}")
            except Exception as dashboard_exc:
                _LOGGER.warning("Supervisor healthy but dashboard unhealthy (%s). Will attempt deployment to fix dashboard.", dashboard_exc)
                # Trigger deployment even though supervisor is working
                await instance._client.async_run("echo 'SSH test'")
                _LOGGER.info("SSH connection successful. Starting deployment to fix dashboard...")
                
                deploy_task = instance.hass.async_create_task(
                    instance._auto_deploy_supervisor(),
                    name=f"perimeter_control_auto_deploy_{instance._entry.entry_id}"
                )
                
                def deployment_completed(task):
                    try:
                        if task.exception():
                            _LOGGER.error("Auto-deployment task failed with exception: %s", 
                                        task.exception(), exc_info=task.exception())
                        else:
                            _LOGGER.debug("Auto-deployment task completed successfully")
                            # Start websocket connection after successful deployment
                            instance.hass.async_create_task(
                                instance._delayed_websocket_start(),
                                name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                            )
                    except Exception as cb_exc:
                        _LOGGER.error("Error in deployment completion callback: %s", cb_exc)
                
                deploy_task.add_done_callback(deployment_completed)
                
        except Exception as exc:
            _LOGGER.info("Supervisor API not available at %s (this is expected during initial setup): %s. Will attempt auto-deployment.", 
                          instance._supervisor_base_url, exc)
            
            # Don't try to start WebSocket during initialization - it blocks startup
            # WebSocket connection will be attempted later via background task
            
            # Try auto-deployment if supervisor is not available
            try:
                # Quick SSH test to see if deployment is possible
                await instance._client.async_run("echo 'SSH test'")
                _LOGGER.info("SSH connection successful. Starting automatic deployment...")
                
                # Trigger automatic deployment in background with explicit task tracking
                deploy_task = instance.hass.async_create_task(
                    instance._auto_deploy_supervisor(),
                    name=f"perimeter_control_auto_deploy_{instance._entry.entry_id}"
                )
                
                # Add task done callback for debugging
                def deployment_completed(task):
                    try:
                        if task.exception():
                            _LOGGER.error("Auto-deployment task failed with exception: %s", 
                                        task.exception(), exc_info=task.exception())
                        else:
                            _LOGGER.debug("Auto-deployment task completed successfully")
                            # Start websocket connection after successful deployment
                            instance.hass.async_create_task(
                                instance._delayed_websocket_start(),
                                name=f"perimeter_control_websocket_{instance._entry.entry_id}"
                            )
                    except Exception as callback_exc:
                        _LOGGER.error("Error in deployment callback: %s", callback_exc)
                
                deploy_task.add_done_callback(deployment_completed)
                
            except Exception as ssh_exc:
                _LOGGER.error("Cannot auto-deploy: SSH connection failed: %s", ssh_exc)
        
        return instance

    # ------------------------------------------------------------------
    # Supervisor API HTTP methods
    # ------------------------------------------------------------------

    async def _supervisor_get(self, endpoint: str) -> dict[str, Any]:
        """Make GET request to Supervisor API endpoint."""
        if not self._http_session:
            raise UpdateFailed("HTTP session not initialized")
        
        url = f"{self._supervisor_base_url}{endpoint}"
        try:
            async with self._http_session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return {}
                else:
                    raise UpdateFailed(f"Supervisor API error {response.status}: {await response.text()}")
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Failed to connect to Supervisor API: {exc}") from exc
    
    async def _supervisor_post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make POST request to Supervisor API endpoint."""
        if not self._http_session:
            raise UpdateFailed("HTTP session not initialized")
        
        url = f"{self._supervisor_base_url}{endpoint}"
        try:
            async with self._http_session.post(url, json=data) as response:
                if response.status in (200, 201):
                    return await response.json()
                else:
                    raise UpdateFailed(f"Supervisor API error {response.status}: {await response.text()}")
        except aiohttp.ClientError as exc:
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
            return {state["entity_id"]: state for state in states if "entity_id" in state}
        except UpdateFailed:
            # Fallback to empty dict if Supervisor unavailable
            return {}

    async def _fetch_ha_integration_data(self) -> dict[str, Any]:
        """Fetch all integration data using the efficient HA endpoint."""
        try:
            result = await self._supervisor_get("/ha/integration")
            
            # Also fetch dashboard URLs for convenience
            dashboard_urls = await self.get_dashboard_urls()
            
            # Transform to match expected format
            return {
                "supervisor_active": result.get("health", {}).get("status") == "healthy",
                "supervisor_entities": result.get("entities", []),
                "entity_states": result.get("states", {}),
                "services_config": result.get("services", {}),
                "config_changes": result.get("config_changes", {}),
                "dashboard_urls": dashboard_urls,
            }
        except UpdateFailed:
            # Fallback to empty data if Supervisor unavailable
            return {
                "supervisor_active": False,
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
            return result.get("dashboard_urls", {})
        except UpdateFailed:
            # Fall back to manual construction
            return self._build_legacy_dashboard_urls()

    def get_dashboard_url(self, service_id: str) -> str | None:
        """Get dashboard URL for service from cached data or access profile."""
        # Try to get from cached dashboard URLs first
        dashboard_urls = self.data.get("dashboard_urls", {})
        if service_id in dashboard_urls:
            return dashboard_urls[service_id]
            
        # Fall back to manual construction
        return self._build_legacy_dashboard_url(service_id)
    
    def _build_legacy_dashboard_url(self, service_id: str) -> str | None:
        """Legacy method to build dashboard URL from access profile."""
        services_config = self.data.get("services_config", {})
        service_config = services_config.get(service_id, {})
        access_profile = service_config.get("access_profile", {})
        
        # Get port from access profile or fall back to default
        port = access_profile.get("port", 8080)
        
        # Check if service is exposed
        mode = access_profile.get("mode", "localhost")
        if mode == "isolated":
            return None  # Service not accessible
            
        host = self._entry.data[CONF_HOST]
        return f"http://{host}:{port}/"
    
    def _build_legacy_dashboard_urls(self) -> dict[str, str]:
        """Legacy method to build all dashboard URLs manually."""
        services_config = self.data.get("services_config", {})
        dashboard_urls = {}
        
        for service_id in services_config:
            url = self._build_legacy_dashboard_url(service_id)
            if url:
                dashboard_urls[service_id] = url
                
        return dashboard_urls
    
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
        if not self._http_session or not self._running:
            return
            
        try:
            # Add timeout to websocket connection
            self._websocket = await asyncio.wait_for(
                self._http_session.ws_connect(self._supervisor_ws_url),
                timeout=10.0
            )
            
            # Reset reconnection attempts on successful connection
            self._reconnect_attempts = 0
            
            # Send subscription filter for entity events
            await self._websocket.send_str(json.dumps({
                "event_types": ["entity_updated", "deployment_completed", "capability_status_changed"]
            }))
            
            # Start background task to listen for events
            self.hass.async_create_task(self._websocket_event_loop())
            
            _LOGGER.info("WebSocket listener started for Supervisor events")
        except asyncio.TimeoutError:
            _LOGGER.warning("WebSocket connection timed out after 10 seconds")
            self._websocket = None
        except Exception as exc:
            _LOGGER.warning("Failed to start WebSocket listener: %s", exc)
            self._websocket = None
    
    async def _websocket_event_loop(self) -> None:
        """Listen for WebSocket events and trigger coordinator updates."""
        if not self._websocket:
            return
            
        try:
            # No timeout - websockets can be idle for long periods
            await self._websocket_message_loop()
        except Exception as exc:
            _LOGGER.warning("WebSocket event loop error: %s", exc)
        finally:
            # Clean up websocket connection
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()
            self._websocket = None
            
            # Only attempt reconnection if we're still supposed to be running
            # and this isn't during shutdown
            if self._running and hasattr(self, '_reconnect_attempts'):
                self._reconnect_attempts = getattr(self, '_reconnect_attempts', 0) + 1
                if self._reconnect_attempts < 3:  # Limit reconnection attempts
                    _LOGGER.debug("Scheduling WebSocket reconnection attempt %d", self._reconnect_attempts)
                    await asyncio.sleep(10)  # Shorter delay
                    if self._running:  # Check again after delay
                        await self._start_websocket_listener()
                else:
                    _LOGGER.warning("Max WebSocket reconnection attempts reached, giving up")
    
    async def _websocket_message_loop(self) -> None:
        """Process websocket messages in a loop."""
        async for msg in self._websocket:
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
    
    async def _delayed_websocket_start(self) -> None:
        """Start websocket connection after a delay to avoid blocking coordinator startup."""
        try:
            # Wait a bit to ensure coordinator is fully initialized
            await asyncio.sleep(2)
            
            # Check if supervisor is available before starting websocket
            try:
                await self._supervisor_get("/api/v1/health")
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
        # Use new HA integration endpoint for efficient data fetching
        supervisor_data = await self._fetch_ha_integration_data()
        
        # Legacy service status via SSH (fallback for deploy operations)
        service_status = {}
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
                
                # Try to connect to the newly deployed supervisor
                try:
                    await self._supervisor_get("/api/v1/health")
                    await self._start_websocket_listener()
                    _LOGGER.info("Successfully connected to deployed supervisor API")
                    
                    # Trigger a coordinator update to refresh all entities
                    await self.async_request_refresh()
                except Exception as exc:
                    _LOGGER.warning("Deployment succeeded but supervisor connection failed: %s", exc)
            else:
                _LOGGER.error("Automatic supervisor deployment failed. Please check the integration logs and try manual deployment.")
        except Exception as exc:
            _LOGGER.error("Error during automatic supervisor deployment: %s", exc, exc_info=True)

    async def async_deploy(self) -> bool:
        """Start a deploy in the background; progress dispatched via coordinator updates."""
        if self._deploy_in_progress:
            _LOGGER.warning("Deploy already in progress for %s", self._entry.data[CONF_HOST])
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
            progress_cb=_on_progress,
        )
        try:
            _LOGGER.debug("Calling deployer.async_deploy()...")
            success = await deployer.async_deploy()
            _LOGGER.info("Deployer finished with success=%s", success)
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

    async def async_shutdown(self) -> None:
        """Clean shutdown of coordinator resources."""
        # Stop reconnection attempts
        self._running = False
        
        # Close WebSocket connection
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
            
        # Close HTTP session
        if self._http_session:
            await self._http_session.close()
            
        # Close SSH client
        await self._client.async_close()
