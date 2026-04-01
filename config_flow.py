
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from pathlib import Path
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AVAILABLE_SERVICES,
    CONF_HOST,
    CONF_PORT,
    CONF_SSH_KEY,
    CONF_SSH_KEY_PATH,
    CONF_SERVICES,
    CONF_USER,
    DEFAULT_SSH_PORT,
    DEFAULT_USER,
    DOMAIN,
)
from .ssh_client import SshClient, SshConnectionError, SshPreflightError


_LOGGER = logging.getLogger(__name__)

# Check asyncssh availability and version for debugging
try:
    import asyncssh
    _LOGGER.debug("asyncssh version: %s", getattr(asyncssh, '__version__', 'unknown'))
except ImportError as e:
    _LOGGER.error("asyncssh dependency not available: %s", e)

STEP_CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): int,
        vol.Optional(CONF_USER, default=DEFAULT_USER): str,
        vol.Optional(CONF_SSH_KEY_PATH, default=""): str,
        vol.Optional(CONF_SSH_KEY, default=""): str,
    }
)

STEP_SERVICES_SCHEMA = vol.Schema(
    {
        vol.Optional(service_id, default=False): bool
        for service_id in AVAILABLE_SERVICES
    }
)



class PerimeterControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    """Handle the Add Device wizard."""
    @staticmethod
    async def _log_system_diagnostics():
        import sys
        import platform
        import ssl
        import os
        import asyncio
        loop = asyncio.get_event_loop()
        platform_str = await loop.run_in_executor(None, platform.platform)
        _LOGGER.debug("Python: %s | Executable: %s | Platform: %s", 
                      sys.version.split()[0], sys.executable, platform_str)
        _LOGGER.debug("OpenSSL: %s", ssl.OPENSSL_VERSION)

    VERSION = 1
    DOMAIN = DOMAIN


    def __init__(self) -> None:
        # DEBUG: Unique log marker to confirm config_flow.py __init__ is executed

        # Log system diagnostics at integration startup (schedule as task)
        import asyncio
        asyncio.get_event_loop().create_task(self._log_system_diagnostics())
        # Check DOMAIN is set and correct
        if not hasattr(self, "DOMAIN") or not self.DOMAIN or not isinstance(self.DOMAIN, str):
            _LOGGER.error("Config flow DOMAIN validation failed: %r", getattr(self, "DOMAIN", None))
            raise RuntimeError("PERIMETER_CONTROL_CONFIG_FLOW_ERROR: DOMAIN is missing or not a string!")
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
            ssh_key_path = user_input.get(CONF_SSH_KEY_PATH, "").strip()
            ssh_key = user_input.get(CONF_SSH_KEY, "").strip()

            private_key = None
            key_source = None
            # If a key file path is provided, use it
            if ssh_key_path:
                try:
                    private_key = await self.hass.async_add_executor_job(
                        lambda: Path(ssh_key_path).read_text(encoding="utf-8")
                    )
                    key_source = f"file:{ssh_key_path}"
                except Exception as exc:
                    _LOGGER.error("Failed to read SSH key file: %s", exc, exc_info=True)
                    errors[CONF_SSH_KEY_PATH] = "invalid_key_path"
            # If a key is pasted, save it to a file and use the file path
            if not private_key and ssh_key:
                try:
                    import os
                    from datetime import datetime
                    # Save to /config/ssh/ with a unique filename
                    ssh_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "ssh")
                    os.makedirs(ssh_dir, exist_ok=True)
                    filename = f"id_perimeter_{user}_{host.replace('.', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.key"
                    key_path = os.path.join(ssh_dir, filename)
                    with open(key_path, "w", encoding="utf-8") as f:
                        f.write(ssh_key)
                    os.chmod(key_path, 0o600)
                    private_key = ssh_key
                    key_source = f"saved:{key_path}"
                    ssh_key_path = key_path
                    _LOGGER.info("SSH key saved to: %s", key_path)
                except Exception as exc:
                    _LOGGER.error("Failed to save pasted SSH key to file: %s", exc, exc_info=True)
                    errors[CONF_SSH_KEY] = "save_failed"
            if not private_key:
                errors[CONF_SSH_KEY] = "no_key_provided"

            if private_key:
                _LOGGER.debug("Using SSH key from %s (length: %d)", key_source, len(private_key))

            await self.async_set_unique_id(f"{user}@{host}:{port}")
            self._abort_if_unique_id_configured()

            if not errors:
                try:
                    client = SshClient(host=host, port=port, user=user, private_key=private_key)
                    self._node_info = await client.async_preflight()
                except SshConnectionError:
                    _LOGGER.error("Cannot connect to %s:%s as %s", host, port, user, exc_info=True)
                    errors["base"] = "cannot_connect"
                except SshPreflightError as exc:
                    _LOGGER.warning("Preflight failed for %s: %s", host, exc, exc_info=True)
                    errors["base"] = "preflight_failed"
                except Exception as exc:
                    _LOGGER.error("Unexpected error connecting to %s: %s", host, exc, exc_info=True)
                    errors["base"] = "unknown"
                else:
                    # Store only the file path, never the key content
                    entry_input = dict(user_input)
                    entry_input[CONF_SSH_KEY_PATH] = ssh_key_path
                    entry_input[CONF_SSH_KEY] = ""
                    self._connection_data = entry_input
                    return await self.async_step_services()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CONNECTION_SCHEMA,
            errors=errors,
            description_placeholders={
                "ssh_key_hint": "Paste the full contents of your private key (e.g. ~/.ssh/id_rsa)",
                "ssh_key_path_hint": "Or provide the path to your private key file (e.g. /config/id_rsa)",
            },
        )

    async def async_step_services(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Select services to install on this device."""
        errors: dict[str, str] = {}
        try:
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
        except Exception as exc:
            _LOGGER.error("Error in async_step_services: %s", exc, exc_info=True)
            errors["base"] = "unknown"

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
