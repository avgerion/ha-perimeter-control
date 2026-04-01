"""
SQLite state database for the Isolator Supervisor.

Manages deployments, capability states, health probes, rollback snapshots,
config change audit, and entity state history.
"""

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id                  TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    status              TEXT NOT NULL,   -- pending | in_progress | succeeded | failed | rolled_back
    capabilities        TEXT NOT NULL,   -- JSON list of capability IDs
    initiator           TEXT NOT NULL,   -- api | user | reconciliation | startup_restore
    dry_run             INTEGER NOT NULL DEFAULT 0,
    config_hash         TEXT,
    error_message       TEXT,
    rollback_snapshot_id TEXT
);

CREATE TABLE IF NOT EXISTS capabilities (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    version             TEXT,
    status              TEXT NOT NULL,   -- inactive | validating | deploying | active | failed | degraded | rolling_back
    config              TEXT NOT NULL,   -- JSON-encoded config dict
    config_hash         TEXT,
    last_deployed_at    TEXT,
    last_health_check_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    deployment_id       TEXT,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);

CREATE TABLE IF NOT EXISTS health_probes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id   TEXT NOT NULL,
    probe_type      TEXT NOT NULL,   -- process | exec | http
    probe_target    TEXT NOT NULL,
    result          TEXT NOT NULL,   -- ok | failed | timeout | error
    output          TEXT,
    duration_ms     INTEGER,
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (capability_id) REFERENCES capabilities(id)
);

CREATE TABLE IF NOT EXISTS rollback_snapshots (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    deployment_id   TEXT,
    snapshot_path   TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    description     TEXT,
    capabilities    TEXT NOT NULL,   -- JSON list of capability IDs
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);

CREATE TABLE IF NOT EXISTS config_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id   TEXT NOT NULL,
    changed_at      TEXT NOT NULL,
    initiator       TEXT NOT NULL,
    old_config_hash TEXT,
    new_config_hash TEXT,
    description     TEXT,
    deployment_id   TEXT
);

CREATE TABLE IF NOT EXISTS entity_state_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    capability_id   TEXT NOT NULL,
    state           TEXT NOT NULL,
    attributes      TEXT,           -- JSON
    sampled_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_health_probes_capability   ON health_probes(capability_id);
CREATE INDEX IF NOT EXISTS idx_health_probes_timestamp    ON health_probes(timestamp);
CREATE INDEX IF NOT EXISTS idx_entity_history_entity_id   ON entity_state_history(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_history_sampled_at  ON entity_state_history(sampled_at);
"""


class StateDatabase:
    """Thin SQLite wrapper with typed helpers for all supervisor state."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def init(self) -> None:
        """Create directory and apply schema DDL."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        logger.info("State database initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self._connect() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # ------------------------------------------------------------------
    # Deployments
    # ------------------------------------------------------------------

    def create_deployment(
        self,
        deployment_id: str,
        capabilities: List[str],
        initiator: str,
        dry_run: bool = False,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO deployments (id, started_at, status, capabilities, initiator, dry_run)
                   VALUES (?, ?, 'pending', ?, ?, ?)""",
                (deployment_id, _now(), json.dumps(capabilities), initiator, 1 if dry_run else 0),
            )

    def update_deployment_status(
        self,
        deployment_id: str,
        status: str,
        error: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> None:
        terminal = status in ("succeeded", "failed", "rolled_back")
        with self.transaction() as conn:
            conn.execute(
                """UPDATE deployments
                   SET status=?, completed_at=?, error_message=?, rollback_snapshot_id=?
                   WHERE id=?""",
                (
                    status,
                    _now() if terminal else None,
                    error,
                    snapshot_id,
                    deployment_id,
                ),
            )

    def get_deployment(self, deployment_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE id=?", (deployment_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["capabilities"] = json.loads(d["capabilities"])
                return d
        return None

    def list_deployments(self, limit: int = 50) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM deployments ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["capabilities"] = json.loads(d["capabilities"])
                result.append(d)
            return result

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def upsert_capability(
        self,
        cap_id: str,
        name: str,
        config: Dict,
        status: str = "inactive",
        version: Optional[str] = None,
    ) -> None:
        config_json = json.dumps(config, sort_keys=True)
        config_hash = _hash(config_json)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO capabilities (id, name, version, status, config, config_hash, last_deployed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,
                     version=excluded.version,
                     config=excluded.config,
                     config_hash=excluded.config_hash,
                     status=excluded.status,
                     last_deployed_at=excluded.last_deployed_at""",
                (cap_id, name, version, status, config_json, config_hash, _now()),
            )

    def update_capability_status(
        self,
        cap_id: str,
        status: str,
        consecutive_failures: Optional[int] = None,
    ) -> None:
        with self.transaction() as conn:
            if consecutive_failures is not None:
                conn.execute(
                    "UPDATE capabilities SET status=?, consecutive_failures=? WHERE id=?",
                    (status, consecutive_failures, cap_id),
                )
            else:
                conn.execute(
                    "UPDATE capabilities SET status=? WHERE id=?",
                    (status, cap_id),
                )

    def get_capability(self, cap_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM capabilities WHERE id=?", (cap_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["config"] = json.loads(d["config"])
                return d
        return None

    def list_capabilities(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM capabilities").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["config"] = json.loads(d["config"])
                result.append(d)
            return result

    # ------------------------------------------------------------------
    # Health probes
    # ------------------------------------------------------------------

    def record_health_probe(
        self,
        cap_id: str,
        probe_type: str,
        target: str,
        result: str,
        output: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO health_probes
                   (capability_id, probe_type, probe_target, result, output, duration_ms, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cap_id, probe_type, target, result, output, duration_ms, _now()),
            )
            if result == "ok":
                conn.execute(
                    "UPDATE capabilities SET consecutive_failures=0, last_health_check_at=? WHERE id=?",
                    (_now(), cap_id),
                )
            else:
                conn.execute(
                    """UPDATE capabilities
                       SET consecutive_failures = consecutive_failures + 1,
                           last_health_check_at = ?
                       WHERE id=?""",
                    (_now(), cap_id),
                )

    def get_health_history(self, cap_id: str, limit: int = 20) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM health_probes
                   WHERE capability_id=? ORDER BY timestamp DESC LIMIT ?""",
                (cap_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Rollback snapshots
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        snapshot_id: str,
        deployment_id: Optional[str],
        snapshot_path: str,
        config_hash: str,
        capabilities: List[str],
        size_bytes: int = 0,
        description: Optional[str] = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO rollback_snapshots
                   (id, created_at, deployment_id, snapshot_path, config_hash, size_bytes, description, capabilities)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    _now(),
                    deployment_id,
                    snapshot_path,
                    config_hash,
                    size_bytes,
                    description,
                    json.dumps(capabilities),
                ),
            )

    def list_snapshots(self, limit: int = 10) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM rollback_snapshots ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["capabilities"] = json.loads(d["capabilities"])
                result.append(d)
            return result

    def delete_old_snapshots(self, keep_count: int = 3) -> None:
        with self.transaction() as conn:
            conn.execute(
                """DELETE FROM rollback_snapshots
                   WHERE id NOT IN (
                     SELECT id FROM rollback_snapshots
                     ORDER BY created_at DESC LIMIT ?
                   )""",
                (keep_count,),
            )

    # ------------------------------------------------------------------
    # Config change audit
    # ------------------------------------------------------------------

    def record_config_change(
        self,
        cap_id: str,
        initiator: str,
        old_hash: Optional[str],
        new_hash: str,
        description: Optional[str] = None,
        deployment_id: Optional[str] = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO config_changes
                   (capability_id, changed_at, initiator, old_config_hash, new_config_hash, description, deployment_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cap_id, _now(), initiator, old_hash, new_hash, description, deployment_id),
            )

    # ------------------------------------------------------------------
    # Entity state history
    # ------------------------------------------------------------------

    def record_entity_state(
        self,
        entity_id: str,
        capability_id: str,
        state: str,
        attributes: Optional[Dict] = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO entity_state_history
                   (entity_id, capability_id, state, attributes, sampled_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (entity_id, capability_id, state, json.dumps(attributes) if attributes else None, _now()),
            )

    def get_entity_history(self, entity_id: str, limit: int = 100) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM entity_state_history
                   WHERE entity_id=? ORDER BY sampled_at DESC LIMIT ?""",
                (entity_id, limit),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("attributes"):
                    d["attributes"] = json.loads(d["attributes"])
                result.append(d)
            return result

    def purge_old_entity_history(self, days: int = 7) -> None:
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM entity_state_history WHERE sampled_at < datetime('now', '-' || ? || ' days')",
                (days,),
            )

    def purge_old_health_probes(self, days: int = 7) -> None:
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM health_probes WHERE timestamp < datetime('now', '-' || ? || ' days')",
                (days,),
            )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]
