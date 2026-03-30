"""HA REST API views for Perimeter Control — called by the Lovelace card.

Endpoints:
  GET  /api/perimeter_control/devices
       List all configured devices and their current health.

  GET  /api/perimeter_control/{entry_id}/status
       Current deploy status + progress log for a single device.

  POST /api/perimeter_control/{entry_id}/deploy
       Trigger a deploy (non-blocking; poll /status for progress).
"""
from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import (
    KEY_DASHBOARD_ACTIVE,
    KEY_DEPLOY_IN_PROGRESS,
    KEY_DEPLOY_PROGRESS,
    KEY_SUPERVISOR_ACTIVE,
    PerimeterControlCoordinator,
)

_LOGGER = logging.getLogger(__name__)


def async_register_views(hass: HomeAssistant) -> None:
    hass.http.register_view(DeviceListView)
    hass.http.register_view(DeviceStatusView)
    hass.http.register_view(DeviceDeployView)


class DeviceListView(HomeAssistantView):
    url = "/api/perimeter_control/devices"
    name = "api:perimeter_control:devices"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entries = hass.config_entries.async_entries(DOMAIN)
        devices = []
        for entry in entries:
            coord: PerimeterControlCoordinator | None = (
                hass.data.get(DOMAIN, {}).get(entry.entry_id)
            )
            data = coord.data if coord and coord.data else {}
            devices.append(
                {
                    "entry_id": entry.entry_id,
                    "title": entry.title,
                    "host": entry.data.get("host"),
                    "services": entry.data.get("services", []),
                    "dashboard_active": data.get(KEY_DASHBOARD_ACTIVE, False),
                    "supervisor_active": data.get(KEY_SUPERVISOR_ACTIVE, False),
                    "deploy_in_progress": data.get(KEY_DEPLOY_IN_PROGRESS, False),
                }
            )
        return self.json(devices)


class DeviceStatusView(HomeAssistantView):
    url = "/api/perimeter_control/{entry_id}/status"
    name = "api:perimeter_control:status"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        coord = _get_coordinator(request.app["hass"], entry_id)
        if coord is None:
            return self.json_message("Device not found", status_code=404)
        data = coord.data or {}
        return self.json(
            {
                "dashboard_active": data.get(KEY_DASHBOARD_ACTIVE, False),
                "supervisor_active": data.get(KEY_SUPERVISOR_ACTIVE, False),
                "deploy_in_progress": data.get(KEY_DEPLOY_IN_PROGRESS, False),
                "deploy_log": [
                    {
                        "phase": p.phase,
                        "message": p.message,
                        "percent": p.percent,
                        "error": p.error,
                    }
                    for p in data.get(KEY_DEPLOY_PROGRESS, [])
                ],
            }
        )


class DeviceDeployView(HomeAssistantView):
    url = "/api/perimeter_control/{entry_id}/deploy"
    name = "api:perimeter_control:deploy"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        coord = _get_coordinator(hass, entry_id)
        if coord is None:
            return self.json_message("Device not found", status_code=404)
        if coord.data and coord.data.get(KEY_DEPLOY_IN_PROGRESS):
            return self.json_message("Deploy already in progress", status_code=409)
        hass.async_create_task(coord.async_deploy())
        return self.json({"queued": True})


def _get_coordinator(
    hass: HomeAssistant, entry_id: str
) -> PerimeterControlCoordinator | None:
    return hass.data.get(DOMAIN, {}).get(entry_id)
