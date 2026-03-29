"""
network_isolation capability module.

Wraps the existing isolator.service / isolator-traffic.service setup.
Exposes each configured device as a set of HA-compatible entities:

  network_isolation:<device_id>:connected   → binary_sensor (connectivity)
  network_isolation:<device_id>:policy      → sensor (active policy name)
  network_isolation:<device_id>:tx_bytes    → sensor (traffic, bytes)
  network_isolation:<device_id>:rx_bytes    → sensor (traffic, bytes)

Actions
-------
  reload_rules   — sudo systemctl reload isolator.service
  add_device     — append device to config YAML + reload
  remove_device  — remove device from config YAML + reload
  set_policy     — change a device's policy + reload
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..base import CapabilityModule

logger = logging.getLogger(__name__)

# systemd unit names managed by this capability
_ISOLATOR_SERVICE = "isolator.service"
_TRAFFIC_SERVICE = "isolator-traffic.service"

# Candidate paths for isolator.conf.yaml that apply-rules.py reads.
# The first existing path is used unless overridden per deploy via config["config_file"].
_ISOLATOR_CONF_CANDIDATES = (
    "/mnt/isolator/conf/isolator.conf.yaml",
    "/opt/isolator/config/isolator.conf.yaml",
    "/opt/isolator/conf/isolator.conf.yaml",
)


class NetworkIsolationCapability(CapabilityModule):
    """Capability module for network_isolation."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        logger.info("[%s] Starting network isolation", self.cap_id)

        # If isolator.service is not running, start it
        rc = await _systemctl("is-active", "--quiet", _ISOLATOR_SERVICE)
        if rc != 0:
            rc = await _systemctl("start", _ISOLATOR_SERVICE)
            if rc != 0:
                raise RuntimeError(f"Failed to start {_ISOLATOR_SERVICE}")

        # Reload rules to pick up any config changes
        await self._reload_rules()

        # Publish initial entity states
        self._refresh_entities()

        logger.info("[%s] Network isolation started", self.cap_id)

    async def stop(self) -> None:
        """
        We deliberately do NOT stop isolator.service here – leaving network
        rules active is safer than suddenly removing them when the supervisor
        restarts.
        """
        logger.info(
            "[%s] Network isolation module stopping (rules remain active for safety)",
            self.cap_id,
        )
        self.entity_cache.clear_capability_entities(self.cap_id)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_entities(self) -> List[Dict[str, Any]]:
        return list(self.entity_cache.get_by_capability(self.cap_id).values())

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    def get_health_probe(self) -> Optional[Dict[str, Any]]:
        return {
            "type": "process",
            "unit": _ISOLATOR_SERVICE,
            "timeout_sec": 5,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        if action_id == "reload_rules":
            await self._reload_rules()
            return {"message": "Rules reloaded"}

        if action_id == "add_device":
            return await self._add_device(params)

        if action_id == "remove_device":
            return await self._remove_device(params)

        if action_id == "set_policy":
            return await self._set_policy(params)

        raise NotImplementedError(f"Unknown action: {action_id}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not isinstance(config.get("devices", []), list):
            errors.append("'devices' must be a list")
        if not isinstance(config.get("policies", []), list):
            errors.append("'policies' must be a list")
        # Validate each device entry has required fields
        for i, dev in enumerate(config.get("devices", [])):
            if not isinstance(dev, dict):
                errors.append(f"devices[{i}] must be a mapping")
                continue
            if not dev.get("id") and not dev.get("name"):
                errors.append(f"devices[{i}] missing 'id' or 'name'")
        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _reload_rules(self) -> None:
        rc = await _systemctl("reload", _ISOLATOR_SERVICE)
        if rc != 0:
            raise RuntimeError(f"systemctl reload {_ISOLATOR_SERVICE} failed (rc={rc})")
        self._refresh_entities()

    def _conf_path(self) -> Path:
        """Return isolator.conf.yaml path (override first, then known defaults)."""
        override = self.config.get("config_file")
        if override:
            return Path(override)

        for candidate in _ISOLATOR_CONF_CANDIDATES:
            p = Path(candidate)
            if p.exists():
                return p

        # Fall back to primary target path; caller will get a clear error if missing.
        return Path(_ISOLATOR_CONF_CANDIDATES[0])

    async def _persist_devices_to_yaml(self) -> None:
        """
        Atomically update the 'devices' section of isolator.conf.yaml so that
        apply-rules.py picks up device changes on the next systemctl reload.

        All other top-level keys (ap, wan, lan, …) are preserved.
        """
        path = self._conf_path()
        try:
            full_conf: dict = {}
            if path.exists():
                with open(path) as f:
                    full_conf = yaml.safe_load(f) or {}

            full_conf["devices"] = self.config.get("devices", [])

            tmp_path = path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                yaml.dump(full_conf, f, default_flow_style=False, allow_unicode=True)
            os.replace(str(tmp_path), str(path))
            logger.info(
                "[%s] Persisted %d device(s) to %s",
                self.cap_id, len(full_conf["devices"]), path,
            )
        except Exception as exc:
            logger.error("[%s] Failed to persist config to YAML: %s", self.cap_id, exc)
            raise

    def _refresh_entities(self) -> None:
        """Publish entity states derived from current config."""
        for device in self.config.get("devices", []):
            device_id = device.get("id") or device.get("name", "unknown")
            prefix = f"network_isolation:{device_id}"

            self._publish_entity(
                f"{prefix}:connected",
                "on",
                attributes={
                    "device_id": device_id,
                    "mac": device.get("mac"),
                    "ip": device.get("ip"),
                    "policy": device.get("policy", "default"),
                    "friendly_name": f"{device_id} Connected",
                },
                platform="binary_sensor",
                device_class="connectivity",
                name=f"{device_id} Connected",
            )

            self._publish_entity(
                f"{prefix}:policy",
                device.get("policy", "default"),
                attributes={"device_id": device_id},
                platform="sensor",
                name=f"{device_id} Policy",
            )

    async def _add_device(self, params: Dict[str, Any]) -> Dict:
        device_id = params.get("device_id") or params.get("id")
        mac = params.get("mac")
        policy = params.get("policy", "default")
        ip = params.get("ip")

        if not device_id or not mac:
            raise ValueError("'device_id' and 'mac' are required")

        # Append to in-memory config
        devices: List[Dict] = self.config.setdefault("devices", [])
        # Avoid duplicates
        if any(d.get("id") == device_id or d.get("mac") == mac for d in devices):
            return {"message": f"Device {device_id} already exists"}

        entry: Dict[str, Any] = {"id": device_id, "mac": mac, "policy": policy}
        if ip:
            entry["ip"] = ip
        devices.append(entry)

        await self._persist_devices_to_yaml()
        await self._reload_rules()
        logger.info("[%s] Added device %s (%s)", self.cap_id, device_id, mac)
        return {"message": f"Device {device_id} added"}

    async def _remove_device(self, params: Dict[str, Any]) -> Dict:
        device_id = params.get("device_id") or params.get("id")
        if not device_id:
            raise ValueError("'device_id' is required")

        devices: List[Dict] = self.config.get("devices", [])
        self.config["devices"] = [
            d for d in devices
            if d.get("id") != device_id and d.get("name") != device_id
        ]

        prefix = f"network_isolation:{device_id}"
        self.entity_cache.remove(f"{prefix}:connected")
        self.entity_cache.remove(f"{prefix}:policy")

        await self._persist_devices_to_yaml()
        await self._reload_rules()
        logger.info("[%s] Removed device %s", self.cap_id, device_id)
        return {"message": f"Device {device_id} removed"}

    async def _set_policy(self, params: Dict[str, Any]) -> Dict:
        device_id = params.get("device_id") or params.get("id")
        policy = params.get("policy")
        if not device_id or not policy:
            raise ValueError("'device_id' and 'policy' are required")

        devices: List[Dict] = self.config.get("devices", [])
        updated = False
        for dev in devices:
            if dev.get("id") == device_id or dev.get("name") == device_id:
                dev["policy"] = policy
                updated = True
                break

        if not updated:
            raise ValueError(f"Device '{device_id}' not found in config")

        await self._persist_devices_to_yaml()
        await self._reload_rules()
        logger.info("[%s] Set policy for %s → %s", self.cap_id, device_id, policy)
        return {"message": f"Policy for {device_id} set to {policy}"}


# ------------------------------------------------------------------
# Subprocess helper
# ------------------------------------------------------------------

async def _systemctl(*args: str) -> int:
    """Run ``sudo systemctl <args>`` and return the exit code."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 and stderr:
        logger.warning("systemctl %s: %s", " ".join(args), stderr.decode(errors="replace").strip())
    return proc.returncode
