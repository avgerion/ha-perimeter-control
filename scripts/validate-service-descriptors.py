#!/usr/bin/env python3
"""Validate generic service descriptor YAML files.

Usage:
  python scripts/validate-service-descriptors.py
  python scripts/validate-service-descriptors.py --dir config/services
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


ALLOWED_RUNTIME_TYPES = {"systemd", "python_module", "container"}
ALLOWED_MODES = {"localhost", "upstream", "isolated", "all", "explicit"}
ALLOWED_TLS = {"off", "self_signed", "provided_cert"}
ALLOWED_AUTH = {"none", "token", "mTLS"}
ALLOWED_SCOPE = {"lan_only", "vpn_only", "tunnel_only"}


def _require(d: Dict[str, Any], key: str, where: str, errors: List[str]) -> Any:
    if key not in d:
        errors.append(f"{where}: missing required key '{key}'")
        return None
    return d[key]


def _validate_descriptor(path: Path) -> List[str]:
    errors: List[str] = []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: failed to parse YAML: {exc}"]

    if not isinstance(data, dict):
        return [f"{path}: top-level YAML must be a map"]

    api_version = _require(data, "apiVersion", str(path), errors)
    kind = _require(data, "kind", str(path), errors)
    metadata = _require(data, "metadata", str(path), errors)
    spec = _require(data, "spec", str(path), errors)

    if api_version is not None and api_version != "isolator/v1":
        errors.append(f"{path}: apiVersion must be 'isolator/v1'")
    if kind is not None and kind != "ServiceDescriptor":
        errors.append(f"{path}: kind must be 'ServiceDescriptor'")

    if isinstance(metadata, dict):
        for key in ("id", "name", "version"):
            _require(metadata, key, f"{path}.metadata", errors)
    elif metadata is not None:
        errors.append(f"{path}.metadata: must be a map")

    if not isinstance(spec, dict):
        if spec is not None:
            errors.append(f"{path}.spec: must be a map")
        return errors

    runtime = _require(spec, "runtime", f"{path}.spec", errors)
    config_file = _require(spec, "config_file", f"{path}.spec", errors)
    access = _require(spec, "access_profile", f"{path}.spec", errors)

    if isinstance(runtime, dict):
        r_type = _require(runtime, "type", f"{path}.spec.runtime", errors)
        _require(runtime, "entrypoint", f"{path}.spec.runtime", errors)
        if isinstance(r_type, str) and r_type not in ALLOWED_RUNTIME_TYPES:
            errors.append(
                f"{path}.spec.runtime.type: '{r_type}' not in {sorted(ALLOWED_RUNTIME_TYPES)}"
            )

    if isinstance(config_file, dict):
        _require(config_file, "path", f"{path}.spec.config_file", errors)
        c_format = _require(config_file, "format", f"{path}.spec.config_file", errors)
        if isinstance(c_format, str) and c_format not in {"yaml", "json", "toml", "ini"}:
            errors.append(f"{path}.spec.config_file.format: invalid '{c_format}'")

    if isinstance(access, dict):
        mode = _require(access, "mode", f"{path}.spec.access_profile", errors)
        port = _require(access, "port", f"{path}.spec.access_profile", errors)
        tls_mode = _require(access, "tls_mode", f"{path}.spec.access_profile", errors)
        auth_mode = _require(access, "auth_mode", f"{path}.spec.access_profile", errors)
        scope = _require(access, "exposure_scope", f"{path}.spec.access_profile", errors)

        if isinstance(mode, str) and mode not in ALLOWED_MODES:
            errors.append(f"{path}.spec.access_profile.mode: invalid '{mode}'")
        if isinstance(port, int) and not (1 <= port <= 65535):
            errors.append(f"{path}.spec.access_profile.port: {port} out of range")
        if isinstance(tls_mode, str) and tls_mode not in ALLOWED_TLS:
            errors.append(f"{path}.spec.access_profile.tls_mode: invalid '{tls_mode}'")
        if isinstance(auth_mode, str) and auth_mode not in ALLOWED_AUTH:
            errors.append(f"{path}.spec.access_profile.auth_mode: invalid '{auth_mode}'")
        if isinstance(scope, str) and scope not in ALLOWED_SCOPE:
            errors.append(f"{path}.spec.access_profile.exposure_scope: invalid '{scope}'")

    low_power = spec.get("low_power_profile")
    if low_power is not None:
        if not isinstance(low_power, dict):
            errors.append(f"{path}.spec.low_power_profile: must be a map")
        else:
            duty = low_power.get("duty_cycle_percent")
            if duty is not None and (not isinstance(duty, int) or not (1 <= duty <= 100)):
                errors.append(
                    f"{path}.spec.low_power_profile.duty_cycle_percent must be int 1..100"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate service descriptors")
    parser.add_argument("--dir", default="config/services", help="Descriptor directory")
    args = parser.parse_args()

    descriptor_dir = Path(args.dir)
    if not descriptor_dir.exists():
        print(f"ERROR: directory not found: {descriptor_dir}")
        return 2

    files = sorted(descriptor_dir.glob("*.service.yaml"))
    if not files:
        print(f"ERROR: no descriptor files found in {descriptor_dir}")
        return 2

    all_errors: List[str] = []
    for path in files:
        errs = _validate_descriptor(path)
        if errs:
            all_errors.extend(errs)

    if all_errors:
        print("Descriptor validation FAILED:\n")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print(f"Descriptor validation passed: {len(files)} files")
    for path in files:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
