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
        self._client = SshClient(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
            user=entry.data[CONF_USER],
            private_key=entry.data[CONF_SSH_KEY],
        )
        self._selected_services: list[str] = entry.data.get(CONF_SERVICES, [])
        self._deploy_in_progress = False
        self._deploy_log: list[DeployProgress] = []

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            result = await self._client.async_run(
                "systemctl is-active isolator-dashboard; "
                "systemctl is-active isolator-supervisor 2>/dev/null || echo inactive"
            )
        except SshConnectionError as exc:
            raise UpdateFailed(f"SSH connection failed: {exc}") from exc

        lines = result.strip().splitlines()
        return {
            KEY_DASHBOARD_ACTIVE: (lines[0].strip() == "active") if lines else False,
            KEY_SUPERVISOR_ACTIVE: (lines[1].strip() == "active") if len(lines) > 1 else False,
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
