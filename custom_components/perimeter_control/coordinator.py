"""Coordinator — polls node health and drives deploy operations."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SERVICES,
    CONF_SSH_KEY,
    CONF_USER,
    DEFAULT_SSH_PORT,
    DOMAIN,
)
from .deployer import DeployProgress, Deployer
from .ssh_client import SshClient, SshConnectionError
from .service_descriptor import load_service_descriptors
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
        self._client = None  # Initialize client as None
        self._selected_services: list[str] = entry.data.get(CONF_SERVICES, [])
        self._deploy_in_progress = False
        self._deploy_log: list[DeployProgress] = []
        # Use Home Assistant's config path for config/services directory
        descriptors_dir = Path(hass.config.path("config/services"))
        self._service_descriptors = {d.id: d for d in load_service_descriptors(descriptors_dir, self._selected_services)}

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
                _LOGGER.info("PERIMETER_CONTROL: Loaded SSH key from file at runtime: %s (len=%d)", ssh_key_path, len(private_key))
            except Exception as exc:
                _LOGGER.error("PERIMETER_CONTROL: Failed to read SSH key file at runtime: %s", exc, exc_info=True)
                private_key = ""
        instance = cls(hass, entry)
        instance._client = SshClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
            user=entry.data[CONF_USER],
            private_key=private_key,
        )
        return instance
        self._client = SshClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
            user=entry.data[CONF_USER],
            private_key=private_key,
        )
        self._selected_services: list[str] = entry.data.get(CONF_SERVICES, [])
        self._deploy_in_progress = False
        self._deploy_log: list[DeployProgress] = []
        # Load service descriptors for selected services
        # Use workspace root config/services directory
        workspace_root = Path(__file__).parents[3]
        descriptors_dir = workspace_root / "config" / "services"
        self._service_descriptors = {d.id: d for d in load_service_descriptors(descriptors_dir, self._selected_services)}

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        # Query status for each selected service
        service_status = {}
        try:
            for service_id, desc in self._service_descriptors.items():
                # Try to check systemd status for each service
                sysd_name = f"{service_id}.service"
                try:
                    result = await self._client.async_run(f"systemctl is-active {sysd_name} 2>/dev/null || echo inactive")
                    service_status[service_id] = (result.strip() == "active")
                except Exception as exc:
                    service_status[service_id] = False
        except SshConnectionError as exc:
            raise UpdateFailed(f"SSH connection failed: {exc}") from exc

        return {
            "service_status": service_status,
            "service_ports": {k: v.port for k, v in self._service_descriptors.items()},
            KEY_DEPLOY_IN_PROGRESS: self._deploy_in_progress,
            KEY_DEPLOY_PROGRESS: list(self._deploy_log),
        }

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    async def async_deploy(self) -> bool:
        """Start a deploy in the background; progress dispatched via coordinator updates."""
        if self._deploy_in_progress:
            _LOGGER.warning("Deploy already in progress for %s", self._entry.data[CONF_HOST])
            return

        self._deploy_in_progress = True
        self._deploy_log = []
        self.async_set_updated_data({
            **self.data,
            KEY_DEPLOY_IN_PROGRESS: True,
            KEY_DEPLOY_PROGRESS: [],
        })

        def _on_progress(p: DeployProgress) -> None:
            self._deploy_log.append(p)
            self.async_set_updated_data({
                **self.data,
                KEY_DEPLOY_IN_PROGRESS: True,
                KEY_DEPLOY_PROGRESS: list(self._deploy_log),
            })

        deployer = Deployer(
            client=self._client,
            selected_services=self._selected_services,
            progress_cb=_on_progress,
        )
        try:
            success = await deployer.async_deploy()
        finally:
            self._deploy_in_progress = False
        await self.async_refresh()
        return success

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def async_shutdown(self) -> None:
        await self._client.async_close()
