"""Config flow for Perimeter Control — Add Device wizard."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AVAILABLE_SERVICES,
    CONF_HOST,
    CONF_PORT,
    CONF_SSH_KEY,
    CONF_SERVICES,
    CONF_USER,
    DEFAULT_SSH_PORT,
    DEFAULT_USER,
    DOMAIN,
)
from .ssh_client import SshClient, SshConnectionError, SshPreflightError

_LOGGER = logging.getLogger(__name__)

STEP_CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): int,
        vol.Optional(CONF_USER, default=DEFAULT_USER): str,
        vol.Required(CONF_SSH_KEY): str,  # Will be rendered as textarea
    }
)

STEP_SERVICES_SCHEMA = vol.Schema(
    {
        vol.Optional(service_id, default=False): bool
        for service_id in AVAILABLE_SERVICES
    }
)


class PerimeterControlConfigFlow(config_entries.ConfigFlow):
    """Handle the Add Device wizard."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._node_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: SSH connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_SSH_PORT)
            user = user_input.get(CONF_USER, DEFAULT_USER).strip()
            ssh_key = user_input[CONF_SSH_KEY].strip()

            # Prevent duplicate entries for the same host
            await self.async_set_unique_id(f"{user}@{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                client = SshClient(host=host, port=port, user=user, private_key=ssh_key)
                self._node_info = await client.async_preflight()
            except SshConnectionError:
                errors["base"] = "cannot_connect"
            except SshPreflightError as exc:
                _LOGGER.warning("Preflight failed for %s: %s", host, exc)
                errors["base"] = "preflight_failed"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to %s", host)
                errors["base"] = "unknown"
            else:
                self._connection_data = user_input
                return await self.async_step_services()

        # Home Assistant supports multi-line input for secrets.yaml and TextArea in UI (if supported by frontend)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CONNECTION_SCHEMA,
            errors=errors,
            description_placeholders={
                "ssh_key_hint": "Paste the full contents of your private key (e.g. ~/.ssh/id_rsa)"
            },
        )

    async def async_step_services(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Select services to install on this device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = [svc for svc in AVAILABLE_SERVICES if user_input.get(svc)]
            if not selected:
                errors["base"] = "no_services_selected"
            else:
                entry_data = {
                    **self._connection_data,
                    CONF_SERVICES: selected,
                    "node_info": self._node_info,
                }
                host = self._connection_data[CONF_HOST]
                return self.async_create_entry(
                    title=f"Pi @ {host}",
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="services",
            data_schema=STEP_SERVICES_SCHEMA,
            errors=errors,
            description_placeholders={
                "node_summary": _format_node_summary(self._node_info),
            },
        )


def _format_node_summary(node_info: dict[str, Any]) -> str:
    hostname = node_info.get("hostname", "unknown")
    arch = node_info.get("arch", "?")
    python = node_info.get("python", "?")
    features = ", ".join(node_info.get("features", [])) or "none detected"
    return f"{hostname} ({arch}), Python {python}, hardware: {features}"
