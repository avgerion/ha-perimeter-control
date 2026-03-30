"""
Dataclass models used throughout the Isolator Supervisor.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityStatus(str, Enum):
    INACTIVE = "inactive"
    VALIDATING = "validating"
    PLANNING = "planning"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    DEGRADED = "degraded"
    ROLLING_BACK = "rolling_back"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class HealthResult(str, Enum):
    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class CapabilityState:
    id: str
    name: str
    status: CapabilityStatus
    config: Dict[str, Any]
    config_hash: Optional[str] = None
    version: Optional[str] = None
    last_deployed_at: Optional[str] = None
    last_health_check_at: Optional[str] = None
    consecutive_failures: int = 0
    deployment_id: Optional[str] = None


@dataclass
class DeploymentRecord:
    id: str
    started_at: str
    status: DeploymentStatus
    capabilities: List[str]
    initiator: str
    dry_run: bool = False
    completed_at: Optional[str] = None
    config_hash: Optional[str] = None
    error_message: Optional[str] = None
    rollback_snapshot_id: Optional[str] = None


@dataclass
class HealthProbeResult:
    capability_id: str
    probe_type: str
    target: str
    result: HealthResult
    output: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: Optional[str] = None


@dataclass
class ResourceBudget:
    cpu_cores: float = 4.0
    memory_mb: int = 6000
    disk_mb: int = 50000
    exclusive_resources: List[str] = field(default_factory=list)


@dataclass
class ResourceRequest:
    cpu_cores: float = 0.5
    memory_mb: int = 256
    disk_mb: int = 500
    exclusive_resources: List[str] = field(default_factory=list)


@dataclass
class EntityState:
    entity_id: str
    capability_id: str
    state: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    platform: str = "sensor"
    device_class: Optional[str] = None
    unit_of_measurement: Optional[str] = None
    last_updated: Optional[str] = None
    available: bool = True
