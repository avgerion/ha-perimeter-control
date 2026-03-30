"""
Entity cache: fast JSON file mapping entity_id → current state.

Used by Home Assistant and the REST API to read entity states without
querying the full capability modules. Persists across supervisor restarts.

Atomic writes (write-to-temp + os.replace) ensure no partial reads.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EntityCache:
    """
    In-memory entity state cache backed by a JSON file.

    File format::

        {
          "last_updated": "2026-03-28T10:00:00Z",
          "count": 3,
          "entities": {
            "network_isolation:lwip:connected": {
              "state": "on",
              "capability_id": "network_isolation",
              "platform": "binary_sensor",
              "device_class": "connectivity",
              "attributes": {...},
              "last_updated": "2026-03-28T10:00:00Z"
            }
          }
        }
    """

    def __init__(self, cache_path: str) -> None:
        self.cache_path = Path(cache_path)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            with open(self.cache_path) as f:
                data = json.load(f)
            self._cache = data.get("entities", {})
            logger.debug("Loaded %d entities from cache", len(self._cache))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load entity cache (%s); starting empty", exc)
            self._cache = {}

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "count": len(self._cache),
            "entities": self._cache,
        }
        # Atomic write: temp file in same directory, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.cache_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, self.cache_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def update(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Insert or update an entity state entry."""
        self._cache[entity_id] = {
            "state": state,
            "attributes": attributes or {},
            "last_updated": datetime.utcnow().isoformat() + "Z",
            **kwargs,
        }
        self._save()

    def remove(self, entity_id: str) -> None:
        """Remove a single entity from the cache."""
        if entity_id in self._cache:
            del self._cache[entity_id]
            self._save()

    def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(entity_id)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._cache)

    def get_by_capability(self, capability_id: str) -> Dict[str, Dict[str, Any]]:
        return {
            eid: state
            for eid, state in self._cache.items()
            if state.get("capability_id") == capability_id
        }

    def list_entity_ids(self) -> List[str]:
        return list(self._cache.keys())

    def clear_capability_entities(self, capability_id: str) -> None:
        """Remove all entities belonging to a capability."""
        to_remove = [
            eid
            for eid, state in self._cache.items()
            if state.get("capability_id") == capability_id
        ]
        if not to_remove:
            return
        for eid in to_remove:
            del self._cache[eid]
        self._save()

    def __len__(self) -> int:
        return len(self._cache)
