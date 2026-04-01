"""
Isolator Supervisor — core state machine and reconciliation engine.

Responsibilities
----------------
* Maintain desired capability state (read from SQLite).
* Run a 30-second reconciliation loop that detects drift and converges
  actual state toward desired state.
* Drive the 6-phase deployment pipeline (validate → preflight → stage →
  apply → verify → finalize) with automatic rollback on failure.
* Delegate health probing, resource admission, and entity publishing to the
  appropriate sub-systems.
* Expose a typed async API used by the REST handlers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import platform
import signal
import tarfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from .capabilities.base import CapabilityModule
from .health.probes import HealthProbeEvaluator
from .resources.scheduler import NodeBudget, ResourceScheduler
from .state.database import StateDatabase
from .state.entity_cache import EntityCache

logger = logging.getLogger(__name__)

RECONCILIATION_INTERVAL_SEC = 30
MAX_CONSECUTIVE_FAILURES = 3
POST_DEPLOY_HEALTH_DELAY_SEC = 5
SUPERVISOR_VERSION = "0.1.0"


class Supervisor:
    """
    Central supervisor daemon.

    Parameters
    ----------
    config_dir: Path to YAML config directory (synced from git or UI).
    state_dir:  Path to persistent state directory (SQLite, snapshots, cache).
    budget:     Optional custom node resource budget.
    """

    def __init__(
        self,
        config_dir: str,
        state_dir: str,
        budget: Optional[NodeBudget] = None,
    ) -> None:
        self.config_dir = Path(config_dir)
        self.state_dir = Path(state_dir)

        self.db = StateDatabase(str(self.state_dir / "supervisor.db"))
        self.entity_cache = EntityCache(str(self.state_dir / "entity_cache.json"))
        self.health = HealthProbeEvaluator(self.db, max_consecutive_failures=MAX_CONSECUTIVE_FAILURES)
        self.resources = ResourceScheduler(budget)

        # capability type name → CapabilityModule subclass
        self._modules: Dict[str, Type[CapabilityModule]] = {}
        # capability ID → live CapabilityModule instance
        self._active: Dict[str, CapabilityModule] = {}

        # WebSocket / polling event subscribers
        self._subscribers: List[Callable[[Dict], None]] = []

        self._running = False
        self._reconcile_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_capability(self, cap_type: str, module_class: Type[CapabilityModule]) -> None:
        """Register a capability module class under *cap_type*."""
        self._modules[cap_type] = module_class
        logger.info("Registered capability module: %s", cap_type)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise DB, restore previously-active capabilities, start loop."""
        logger.info("Supervisor %s starting …", SUPERVISOR_VERSION)

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db.init()

        await self._restore_state()

        self._running = True
        self._reconcile_task = asyncio.create_task(self._reconciliation_loop())

        logger.info("Supervisor started")

    async def stop(self) -> None:
        """Cancel reconciliation loop; stop all active capabilities."""
        logger.info("Supervisor stopping …")
        self._running = False

        if self._reconcile_task:
            self._reconcile_task.cancel()
            try:
                await self._reconcile_task
            except asyncio.CancelledError:
                pass

        for cap_id, cap in list(self._active.items()):
            try:
                await cap.stop()
            except Exception as exc:
                logger.warning("Error stopping capability %s: %s", cap_id, exc)

        logger.info("Supervisor stopped")

    # ------------------------------------------------------------------
    # Deployment pipeline
    # ------------------------------------------------------------------

    async def deploy(
        self,
        desired: Dict[str, Dict[str, Any]],
        initiator: str = "api",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Deploy or update a set of capabilities.

        Returns a result dict with keys: deployment_id, status,
        capabilities, [error].
        """
        deployment_id = f"dep_{uuid.uuid4().hex[:12]}"
        cap_ids = list(desired.keys())

        logger.info("[%s] Deploy requested: caps=%s dry_run=%s", deployment_id, cap_ids, dry_run)

        if not dry_run:
            self.db.create_deployment(deployment_id, cap_ids, initiator)
            self.db.update_deployment_status(deployment_id, "in_progress")

        try:
            # Phase 1 – validate configs
            errs = await self._validate_configs(desired)
            if errs:
                raise ValueError(f"Config validation failed: {'; '.join(errs)}")

            # Phase 2 – resource admission
            conflicts = self.resources.check_admission(desired, self._active)
            if conflicts:
                raise ValueError(f"Resource conflicts: {'; '.join(conflicts)}")

            if dry_run:
                return {
                    "deployment_id": "dry_run",
                    "status": "preview",
                    "capabilities": cap_ids,
                    "validation": "passed",
                    "resource_check": "passed",
                    "would_deploy": cap_ids,
                }

            # Phase 3 – pre-deploy snapshot
            snapshot_id = await self._create_snapshot(deployment_id, "pre_deploy")

            # Upsert capability rows in DB (desired state recorded before apply)
            for cap_id, cap_config in desired.items():
                cap_name = cap_config.get("name", cap_id)
                cap_version = cap_config.get("version")
                old_cap = self.db.get_capability(cap_id)
                old_hash = old_cap["config_hash"] if old_cap else None

                self.db.upsert_capability(cap_id, cap_name, cap_config, "deploying", cap_version)
                new_hash = (self.db.get_capability(cap_id) or {}).get("config_hash")
                self.db.record_config_change(cap_id, initiator, old_hash, new_hash or "", deployment_id=deployment_id)

            # Phase 4 – apply each capability
            for cap_id, cap_config in desired.items():
                await self._start_capability(cap_id, cap_config, deployment_id)

            # Phase 5 – health verification
            await asyncio.sleep(POST_DEPLOY_HEALTH_DELAY_SEC)
            health_ok = await self._verify_health(cap_ids)

            if not health_ok:
                logger.error("[%s] Health check failed; rolling back", deployment_id)
                await self._rollback(snapshot_id, deployment_id)
                self.db.update_deployment_status(deployment_id, "rolled_back", "Health check failed")
                return {
                    "deployment_id": deployment_id,
                    "status": "rolled_back",
                    "error": "Health check failed after deploy",
                }

            # Phase 6 – finalize
            self.db.update_deployment_status(deployment_id, "succeeded")
            self._emit("deployment_completed", {"deployment_id": deployment_id, "status": "succeeded"})
            logger.info("[%s] Deploy succeeded", deployment_id)

            return {"deployment_id": deployment_id, "status": "succeeded", "capabilities": cap_ids}

        except Exception as exc:
            logger.error("[%s] Deploy failed: %s", deployment_id, exc, exc_info=True)
            if not dry_run:
                self.db.update_deployment_status(deployment_id, "failed", str(exc))
            return {"deployment_id": deployment_id, "status": "failed", "error": str(exc)}

    async def trigger_action(
        self, cap_id: str, action_id: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Trigger a capability action by name."""
        cap = self._active.get(cap_id)
        if not cap:
            return {"success": False, "error": f"Capability '{cap_id}' is not active"}
        try:
            result = await cap.execute_action(action_id, params or {})
            return {"success": True, "result": result}
        except Exception as exc:
            logger.error("Action %s on %s failed: %s", action_id, cap_id, exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Query API (used by REST handlers)
    # ------------------------------------------------------------------

    def get_node_info(self) -> Dict[str, Any]:
        caps = self.db.list_capabilities()
        return {
            "node_id": self._node_id(),
            "hostname": platform.node(),
            "platform": "linux",
            "arch": platform.machine(),
            "python_version": platform.python_version(),
            "supervisor_version": SUPERVISOR_VERSION,
            "capabilities": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "status": c["status"],
                    "version": c.get("version"),
                }
                for c in caps
            ],
        }

    def get_entities(self) -> List[Dict[str, Any]]:
        entities: List[Dict] = []
        for cap in self._active.values():
            entities.extend(cap.get_entities())
        return entities

    def get_entity_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        cached = self.entity_cache.get(entity_id)
        if cached:
            return cached
        for cap in self._active.values():
            state = cap.get_entity_state(entity_id)
            if state:
                return state
        return None

    def query_entity_states(self, entity_ids: List[str]) -> List[Dict[str, Any]]:
        return [
            {"entity_id": eid, "state": self.get_entity_state(eid)}
            for eid in entity_ids
            if self.get_entity_state(eid) is not None
        ]

    def get_health_summary(self) -> Dict[str, Any]:
        caps = self.db.list_capabilities()
        roll_up = "ok"
        capability_health: Dict[str, str] = {}
        for cap in caps:
            status = cap.get("status", "unknown")
            capability_health[cap["id"]] = status
            if status in ("failed", "degraded"):
                roll_up = "degraded"
        return {"status": roll_up, "capabilities": capability_health}

    def subscribe_events(self, callback: Callable[[Dict], None]) -> Callable:
        """Subscribe to supervisor events; returns an unsubscribe callable."""
        self._subscribers.append(callback)

        def _unsub():
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

        return _unsub

    # ------------------------------------------------------------------
    # Reconciliation loop
    # ------------------------------------------------------------------

    async def _reconciliation_loop(self) -> None:
        logger.info("Reconciliation loop started (interval=%ds)", RECONCILIATION_INTERVAL_SEC)
        while self._running:
            try:
                await self._reconcile()
            except Exception as exc:
                logger.error("Reconciliation error: %s", exc, exc_info=True)
            await asyncio.sleep(RECONCILIATION_INTERVAL_SEC)

    async def _reconcile(self) -> None:
        """Single reconciliation pass: desired state → actual state."""
        all_caps = self.db.list_capabilities()

        for cap in all_caps:
            cap_id = cap["id"]
            desired_status = cap["status"]

            if desired_status == "inactive":
                continue

            active = self._active.get(cap_id)

            if desired_status in ("active", "deploying"):
                if active is None:
                    logger.warning("[reconcile] %s should be active but isn't — restarting", cap_id)
                    try:
                        await self._start_capability(cap_id, cap["config"], "reconciliation")
                    except Exception as exc:
                        logger.error("[reconcile] Failed to restart %s: %s", cap_id, exc)
                else:
                    # Run health probe
                    await self.health.run_probe(cap_id, active)

            elif desired_status == "failed":
                failures = cap.get("consecutive_failures", 0)
                if failures < MAX_CONSECUTIVE_FAILURES:
                    logger.info("[reconcile] Retrying failed capability %s (failures=%d)", cap_id, failures)
                    try:
                        await self._start_capability(cap_id, cap["config"], "reconciliation")
                    except Exception as exc:
                        logger.error("[reconcile] Retry of %s failed: %s", cap_id, exc)

    # ------------------------------------------------------------------
    # Internal start / stop a single capability
    # ------------------------------------------------------------------

    async def _start_capability(
        self, cap_id: str, cap_config: Dict[str, Any], deployment_id: str
    ) -> None:
        """Stop any existing instance, start a fresh one."""
        cap_type = cap_config.get("type", cap_id)
        module_class = self._modules.get(cap_type)

        if not module_class:
            raise ValueError(f"No module registered for capability type '{cap_type}'")

        # Stop existing instance
        if cap_id in self._active:
            try:
                await self._active[cap_id].stop()
            except Exception as exc:
                logger.warning("Error stopping %s before redeploy: %s", cap_id, exc)
            del self._active[cap_id]
            self.resources.release(cap_id)

        instance = module_class(cap_id, cap_config, self.entity_cache, self._emit)
        await instance.start()

        self._active[cap_id] = instance
        self.resources.allocate(cap_id, cap_config)
        self.db.update_capability_status(cap_id, "active", consecutive_failures=0)
        self._emit("capability_started", {"capability_id": cap_id})
        logger.info("Capability %s is now active", cap_id)

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------

    async def _validate_configs(self, desired: Dict[str, Dict]) -> List[str]:
        errors: List[str] = []
        for cap_id, cap_config in desired.items():
            cap_type = cap_config.get("type", cap_id)
            module_class = self._modules.get(cap_type)
            if not module_class:
                errors.append(f"{cap_id}: No registered module for type '{cap_type}'")
                continue
            cap_errors = module_class.validate_config(cap_config)
            errors.extend(f"{cap_id}: {e}" for e in cap_errors)
        return errors

    # ------------------------------------------------------------------
    # Health verification post-deploy
    # ------------------------------------------------------------------

    async def _verify_health(self, cap_ids: List[str]) -> bool:
        for cap_id in cap_ids:
            active = self._active.get(cap_id)
            if not active:
                logger.error("Health verify: %s not found in active capabilities", cap_id)
                return False
            result = await self.health.run_probe(cap_id, active)
            if result != "ok":
                logger.error("Health verify: %s probe result=%s", cap_id, result)
                return False
        return True

    # ------------------------------------------------------------------
    # Snapshot & rollback
    # ------------------------------------------------------------------

    async def _create_snapshot(self, deployment_id: str, label: str) -> str:
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        snap_dir = self.state_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = str(snap_dir / f"{snapshot_id}.tar.gz")

        caps = [c["id"] for c in self.db.list_capabilities()]
        size = 0

        try:
            with tarfile.open(snapshot_path, "w:gz") as tar:
                if self.config_dir.exists():
                    tar.add(str(self.config_dir), arcname="config")
                db_path = str(self.state_dir / "supervisor.db")
                if Path(db_path).exists():
                    tar.add(db_path, arcname="supervisor.db")
            size = Path(snapshot_path).stat().st_size
            config_hash = hashlib.sha256(snapshot_path.encode()).hexdigest()[:16]
            self.db.create_snapshot(snapshot_id, deployment_id, snapshot_path, config_hash, caps, size, label)
            self.db.delete_old_snapshots(keep_count=3)
            logger.info("Snapshot %s created (%d bytes)", snapshot_id, size)
        except Exception as exc:
            logger.warning("Failed to create snapshot: %s", exc)

        return snapshot_id

    async def _rollback(self, snapshot_id: str, deployment_id: str) -> None:
        snapshots = self.db.list_snapshots(limit=20)
        record = next((s for s in snapshots if s["id"] == snapshot_id), None)

        if not record:
            logger.error("Rollback snapshot %s not found", snapshot_id)
            return

        snap_path = record["snapshot_path"]
        if not Path(snap_path).exists():
            logger.error("Snapshot file missing: %s", snap_path)
            return

        # Stop all active capabilities
        for cap_id, cap in list(self._active.items()):
            try:
                await cap.stop()
            except Exception as exc:
                logger.warning("Error stopping %s during rollback: %s", cap_id, exc)
        self._active.clear()
        self.resources._allocations.clear()

        restore_dir = self.state_dir / "restore_tmp"
        restore_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(snap_path, "r:gz") as tar:
                # Security: only extract expected members
                members = [m for m in tar.getmembers()
                           if not m.name.startswith("/") and ".." not in m.name]
                tar.extractall(str(restore_dir), members=members)
            logger.info("Rolled back to snapshot %s", snapshot_id)
        except Exception as exc:
            logger.error("Rollback extract failed: %s", exc)

    # ------------------------------------------------------------------
    # State restore on startup
    # ------------------------------------------------------------------

    async def _restore_state(self) -> None:
        active_caps = [
            c for c in self.db.list_capabilities()
            if c["status"] in ("active", "deploying")
        ]
        if not active_caps:
            logger.info("No previously active capabilities to restore")
            return

        logger.info("Restoring %d capabilities from state DB …", len(active_caps))
        for cap in active_caps:
            try:
                await self._start_capability(cap["id"], cap["config"], "startup_restore")
            except Exception as exc:
                logger.error("Failed to restore capability %s: %s", cap["id"], exc)

    # ------------------------------------------------------------------
    # Event bus
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **data,
        }
        for cb in list(self._subscribers):
            try:
                cb(event)
            except Exception as exc:
                logger.warning("Event subscriber raised: %s", exc)

    # ------------------------------------------------------------------
    # Node ID
    # ------------------------------------------------------------------

    def _node_id(self) -> str:
        id_file = self.state_dir / "node_id"
        if id_file.exists():
            return id_file.read_text().strip()
        node_id = f"pi_{uuid.uuid4().hex[:12]}"
        id_file.write_text(node_id)
        return node_id
