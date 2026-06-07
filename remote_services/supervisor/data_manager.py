"""
Generic DataManager for supervisor-level data access.
Move dashboard-specific logic to dashboard_web, keep only generic config and device helpers here.
"""
import logging
import os
import json
from pathlib import Path
from typing import Dict, Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urljoin
import yaml

logger = logging.getLogger("supervisor.data_manager")

class DataManager:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.debug(f"Loaded config: {len(config.get('devices', []))} devices")
                return config or {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {'devices': [], 'default_policy': {}}

    def reload_config(self):
        logger.info("Reloading configuration...")
        self.config = self._load_config()

    def get_devices(self):
        return self.config.get('devices', [])

    def get_default_policy(self):
        return self.config.get('default_policy', {})

    @property
    def supervisor_api_url(self) -> str:
        """Return supervisor API base URL with sensible local fallbacks."""
        configured = self.config.get("supervisor_api_url") or os.environ.get("PERIMETER_SUPERVISOR_API_URL")
        if configured:
            return str(configured).rstrip("/")

        host = self.config.get("supervisor_host") or "127.0.0.1"
        port = int(self.config.get("supervisor_port", 8080))
        return f"http://{host}:{port}"

    def _request_json(self, endpoint: str, method: str = "GET", payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Call supervisor API and return parsed JSON payload."""
        url = endpoint if endpoint.startswith("http://") or endpoint.startswith("https://") else urljoin(f"{self.supervisor_api_url}/", endpoint.lstrip("/"))
        headers = {"Accept": "application/json"}
        body = None

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib_request.Request(url=url, method=method.upper(), data=body, headers=headers)
        try:
            with urllib_request.urlopen(req, timeout=4) as response:
                raw = response.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {}
                return json.loads(raw)
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            logger.warning("Supervisor API HTTP error %s for %s: %s", exc.code, url, detail)
        except urllib_error.URLError as exc:
            logger.warning("Supervisor API URL error for %s: %s", url, exc)
        except Exception as exc:
            logger.warning("Supervisor API request failed for %s: %s", url, exc)
        return {}

    def get_entities(self, capability_id: str | None = None, entity_type: str | None = None) -> list[Dict[str, Any]]:
        """Fetch entity schemas from supervisor and optionally filter by capability/type."""
        result = self._request_json("/entities")
        entities = result.get("entities", []) if isinstance(result, dict) else []
        if not isinstance(entities, list):
            return []

        filtered: list[Dict[str, Any]] = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue

            capability = entity.get("capability_id") or entity.get("capability")
            if capability_id and capability != capability_id:
                continue
            if entity_type and entity.get("type") != entity_type:
                continue
            filtered.append(entity)
        return filtered

    def get_entity_states(self, entity_ids: list[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch runtime state for a list of entity IDs."""
        if not entity_ids:
            return {}

        result = self._request_json("/entities/states/query", method="POST", payload={"entity_ids": entity_ids})
        states = result.get("states", {}) if isinstance(result, dict) else {}
        return states if isinstance(states, dict) else {}

    def get_entities_with_state(self, capability_id: str, entity_type: str | None = None) -> list[Dict[str, Any]]:
        """Return entity schema rows enriched with their current state payload."""
        entities = self.get_entities(capability_id=capability_id, entity_type=entity_type)
        ids = [str(entity.get("id")) for entity in entities if entity.get("id")]
        states = self.get_entity_states(ids)

        rows: list[Dict[str, Any]] = []
        for entity in entities:
            entity_id = str(entity.get("id", ""))
            state_payload = states.get(entity_id, {}) if isinstance(states, dict) else {}
            if isinstance(state_payload, dict) and isinstance(state_payload.get("state"), dict):
                state_payload = state_payload.get("state")
            attrs = state_payload.get("attributes", {}) if isinstance(state_payload, dict) else {}
            rows.append({
                "id": entity_id,
                "friendly_name": entity.get("friendly_name") or entity_id,
                "type": entity.get("type", ""),
                "capability": entity.get("capability") or entity.get("capability_id", ""),
                "state": state_payload.get("state") if isinstance(state_payload, dict) else None,
                "attributes": attrs if isinstance(attrs, dict) else {},
            })
        return rows

    def call_capability_action(self, capability: str, action_id: str, payload: Dict[str, Any] | None = None) -> bool:
        """Invoke a capability action via supervisor API."""
        if not capability or not action_id:
            return False
        result = self._request_json(
            f"/capabilities/{capability}/actions/{action_id}",
            method="POST",
            payload=payload or {},
        )
        if not isinstance(result, dict):
            return False
        if result.get("ok") is True:
            return True
        return "error" not in result

    def capture_photo(self, capability: str = "photo_booth") -> tuple[bool, str]:
        """Try known photo capture action IDs and report result."""
        for action_id in ("capture_photo", "capture", "take_photo", "snap"):
            if self.call_capability_action(capability, action_id, payload={}):
                return True, f"Triggered action '{action_id}'."
        return False, "No supported capture action responded from supervisor API."
