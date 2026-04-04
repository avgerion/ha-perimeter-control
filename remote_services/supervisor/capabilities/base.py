"""
Abstract base class for all capability modules.

Every capability (network_isolation, ble_gatt_translator, pawr_esl_advertiser,
…) subclasses CapabilityModule and implements the four abstract methods.
The supervisor only calls the interface defined here; it never imports
capability-specific code directly.

Lifecycle
---------
1. Supervisor calls ``validate_config(config)`` (static) before any deploy.
2. Supervisor instantiates the subclass with (cap_id, config, entity_cache, emit_event).
3. Supervisor calls ``await start()``  – capability may start OS services, spawn
   background tasks, publish initial entity states.
4. Supervisor calls ``await stop()``   – capability stops background tasks, cleans up.
5. Supervisor periodically calls ``await execute_action(action_id, params)``
   when the REST API receives an action request.
6. Supervisor calls ``get_entities()`` to list all entities exposed by this
   capability, and ``get_health_probe()`` to know how to health-check it.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CapabilityModule(ABC):
    """
    Abstract base for capability modules.

    Parameters
    ----------
    cap_id:       Unique ID of this capability instance (e.g. "network_isolation").
    config:       Capability config dict (validated before __init__ is called).
    entity_cache: EntityCache instance shared across all capabilities.
    emit_event:   Callable(event_type: str, data: dict) → None.
    """

    def __init__(
        self,
        cap_id: str,
        config: Dict[str, Any],
        entity_cache,
        emit_event: Callable[[str, Dict], None],
    ) -> None:
        self.cap_id = cap_id
        self.config = config
        self.entity_cache = entity_cache
        self._emit_event = emit_event

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def start(self) -> None:
        """Start the capability (idempotent – safe to call on restart)."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the capability and release resources."""

    @abstractmethod
    def get_entities(self) -> List[Dict[str, Any]]:
        """
        Return a list of entity descriptor dicts.

        Each dict must contain at minimum::

            {
              "id":       "network_isolation:lwip:connected",
              "name":     "lwip Connected",
              "platform": "binary_sensor",   # sensor | binary_sensor | switch | …
              "capability_id": "network_isolation",
              "state":    "on",
            }
        """

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Return current state of a single entity (checked against cache)."""
        return self.entity_cache.get(entity_id)

    def get_health_probe(self) -> Optional[Dict[str, Any]]:
        """
        Return health probe config, or None to skip probing.

        Examples::

            # systemd unit
            {"type": "process", "unit": "isolator.service", "timeout_sec": 5}

            # exec command
            {"type": "exec", "command": "pgrep ble-scanner", "expected_rc": 0}

            # HTTP endpoint
            {"type": "http", "url": "http://localhost:9090/health", "timeout_sec": 3}
        """
        return None

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        """
        Execute a named action.  Override in subclass to support actions.
        Raise NotImplementedError for unknown action IDs.
        """
        raise NotImplementedError(f"Action '{action_id}' not implemented by {self.cap_id}")

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate config dict.  Return a list of error strings (empty = valid).
        Called before any instantiation; must not have side-effects.
        """
        return []

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    def _publish_entity(
        self,
        entity_or_id: str | Dict[str, Any],
        state: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> None:
        """
        Write entity state to the shared entity cache and emit an
        ``entity_updated`` event so WebSocket subscribers see it immediately.
        
        Can be called in two ways:
        1. _publish_entity(entity_id, state, attributes=..., **extra)
        2. _publish_entity(entity_dict) - where entity_dict contains id, state, etc.
        """
        if isinstance(entity_or_id, dict):
            # Called with entity dict - extract fields
            entity = entity_or_id
            entity_id = entity["id"]
            state = entity["state"] 
            attributes = entity.get("attributes", {})
            
            # Copy other fields as extra parameters for the cache
            extra = {
                "platform": entity.get("type", "sensor"),
                "device_class": entity.get("device_class"),
                "icon": entity.get("icon"),
                "friendly_name": entity.get("friendly_name"),
                **{k: v for k, v in entity.items() 
                   if k not in ["id", "state", "attributes", "capability"]}
            }
            # Filter out None values
            extra = {k: v for k, v in extra.items() if v is not None}
        else:
            # Called with individual parameters (legacy)
            entity_id = entity_or_id
            if state is None:
                raise ValueError("state parameter required when passing entity_id as string")
        
        self.entity_cache.update(
            entity_id,
            state,
            attributes=attributes or {},
            capability_id=self.cap_id,
            last_updated=datetime.utcnow().isoformat() + "Z",
            **extra,
        )
        self._emit_event(
            "entity_updated",
            {
                "entity_id": entity_id,
                "state": state,
                "capability_id": self.cap_id,
            },
        )
