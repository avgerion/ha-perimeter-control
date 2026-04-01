"""Load and represent service descriptors bundled with the component."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_LOGGER = logging.getLogger(__name__)


@dataclass
class ServiceDescriptor:
    id: str
    name: str
    apt_dependency_groups: list[str] = field(default_factory=list)
    can_run_with: list[str] = field(default_factory=list)
    cannot_run_with: list[str] = field(default_factory=list)
    port: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


def load_service_descriptors(
    descriptors_dir: Path,
    service_ids: list[str],
) -> list[ServiceDescriptor]:
    """Load service descriptors for the given service IDs from the bundled YAML files."""
    result: list[ServiceDescriptor] = []
    import asyncio
    for sid in service_ids:
        path = descriptors_dir / f"{sid}.service.yaml"
        if not path.exists():
            _LOGGER.warning("Service descriptor not found: %s", path)
            continue
        try:
            # Use executor for file I/O
            text = asyncio.get_event_loop().run_until_complete(
                asyncio.get_event_loop().run_in_executor(None, path.read_text)
            )
            data: dict[str, Any] = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            _LOGGER.exception("Failed to parse service descriptor: %s", path)
            continue

        meta = data.get("metadata", {})
        spec = data.get("spec", {})
        placement = spec.get("placement", {})
        access = spec.get("access_profile", {})
        sys_deps = spec.get("system_deps", {})

        result.append(
            ServiceDescriptor(
                id=meta.get("id", sid),
                name=meta.get("name", sid),
                apt_dependency_groups=sys_deps.get("apt", []),
                can_run_with=placement.get("can_run_with", []),
                cannot_run_with=placement.get("cannot_run_with", []),
                port=access.get("port"),
                raw=data,
            )
        )
    return result
