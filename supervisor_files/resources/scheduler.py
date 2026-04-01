"""
Resource admission controller.

Tracks CPU / RAM / disk allocations per capability and rejects new deployments
that would overcommit the node budget or claim an already-held exclusive
resource (e.g. the BLE radio).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class NodeBudget:
    """Maximum resources available on this node."""
    cpu_cores: float = 4.0
    memory_mb: int = 6000
    disk_mb: int = 50_000


@dataclass
class CapabilityAllocation:
    cpu_cores: float = 0.5
    memory_mb: int = 256
    disk_mb: int = 500
    exclusive: List[str] = field(default_factory=list)


class ResourceScheduler:
    """
    Lightweight admission controller.

    Capabilities declare their resource needs in config under a ``resources``
    key::

        resources:
          cpu_cores: 0.5
          memory_mb: 256
          disk_mb: 500
          exclusive:          # Resources only one capability can hold at a time
            - ble_radio

    ``check_admission`` returns a list of conflict strings (empty = OK).
    ``allocate`` / ``release`` update the in-memory tally.
    """

    def __init__(self, budget: NodeBudget = None) -> None:
        self.budget = budget or NodeBudget()
        self._allocations: Dict[str, CapabilityAllocation] = {}

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------

    def check_admission(
        self,
        new_capabilities: Dict[str, Dict],
        active_capabilities: Dict,
    ) -> List[str]:
        """
        Check whether *new_capabilities* can be admitted alongside the
        currently *active_capabilities*.

        Capabilities present in *new_capabilities* replace any existing
        allocation with the same ID (i.e. redeployments are always allowed as
        long as the new request fits).
        """
        conflicts: List[str] = []

        # Tally usage from capabilities NOT being replaced
        used_cpu = 0.0
        used_mem = 0
        used_disk = 0
        used_exclusive: Set[str] = set()

        for cap_id, _cap in active_capabilities.items():
            if cap_id in new_capabilities:
                continue  # will be replaced
            alloc = self._allocations.get(cap_id, CapabilityAllocation())
            used_cpu += alloc.cpu_cores
            used_mem += alloc.memory_mb
            used_disk += alloc.disk_mb
            used_exclusive.update(alloc.exclusive)

        # Now check each incoming capability
        for cap_id, cap_config in new_capabilities.items():
            res = cap_config.get("resources", {})
            req_cpu = float(res.get("cpu_cores", 0.5))
            req_mem = int(res.get("memory_mb", 256))
            req_disk = int(res.get("disk_mb", 500))
            req_exclusive: List[str] = res.get("exclusive", [])

            if used_cpu + req_cpu > self.budget.cpu_cores:
                conflicts.append(
                    f"{cap_id}: CPU overcommit "
                    f"({used_cpu + req_cpu:.1f} / {self.budget.cpu_cores} cores)"
                )
            if used_mem + req_mem > self.budget.memory_mb:
                conflicts.append(
                    f"{cap_id}: Memory overcommit "
                    f"({used_mem + req_mem} / {self.budget.memory_mb} MB)"
                )
            if used_disk + req_disk > self.budget.disk_mb:
                conflicts.append(
                    f"{cap_id}: Disk overcommit "
                    f"({used_disk + req_disk} / {self.budget.disk_mb} MB)"
                )
            for resource in req_exclusive:
                if resource in used_exclusive:
                    conflicts.append(
                        f"{cap_id}: Exclusive resource conflict: '{resource}' "
                        f"already held by another capability"
                    )

        return conflicts

    # ------------------------------------------------------------------
    # Allocation tracking
    # ------------------------------------------------------------------

    def allocate(self, cap_id: str, cap_config: Dict) -> None:
        """Record an allocation after a capability is successfully deployed."""
        res = cap_config.get("resources", {})
        self._allocations[cap_id] = CapabilityAllocation(
            cpu_cores=float(res.get("cpu_cores", 0.5)),
            memory_mb=int(res.get("memory_mb", 256)),
            disk_mb=int(res.get("disk_mb", 500)),
            exclusive=list(res.get("exclusive", [])),
        )
        logger.debug("Allocated resources for %s: %s", cap_id, self._allocations[cap_id])

    def release(self, cap_id: str) -> None:
        """Free allocations when a capability is stopped."""
        if cap_id in self._allocations:
            del self._allocations[cap_id]
            logger.debug("Released resources for %s", cap_id)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_usage_summary(self) -> Dict:
        total_cpu = sum(a.cpu_cores for a in self._allocations.values())
        total_mem = sum(a.memory_mb for a in self._allocations.values())
        total_disk = sum(a.disk_mb for a in self._allocations.values())
        all_exclusive = [r for a in self._allocations.values() for r in a.exclusive]
        return {
            "cpu_cores_used": total_cpu,
            "cpu_cores_total": self.budget.cpu_cores,
            "cpu_percent": round((total_cpu / self.budget.cpu_cores) * 100, 1) if self.budget.cpu_cores else 0,
            "memory_mb_used": total_mem,
            "memory_mb_total": self.budget.memory_mb,
            "disk_mb_used": total_disk,
            "disk_mb_total": self.budget.disk_mb,
            "exclusive_in_use": all_exclusive,
            "capabilities": list(self._allocations.keys()),
        }
