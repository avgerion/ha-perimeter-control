#!/usr/bin/env python3
"""Prepare and inspect resolved network topology for the isolator."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

from topology_config import resolve_topology, validate_topology


def _load_config(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    topology = resolve_topology(config)
    validate_topology(config, topology)
    return config, topology


def _run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def _summary_shell(topology: dict) -> str:
    values = {
        "ISOLATED_INTERFACE": topology["isolated"]["interface"],
        "ISOLATED_KIND": topology["isolated"]["kind"],
        "UPSTREAM_INTERFACE": topology["upstream"]["interface"],
        "UPSTREAM_KIND": topology["upstream"]["kind"],
        "LAN_GATEWAY": topology["lan"]["gateway"],
        "LAN_GATEWAY_CIDR": topology["lan"]["gateway_cidr"],
    }
    return "\n".join(f"{key}={shlex.quote(str(value))}" for key, value in values.items())


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve and apply PerimeterControl network topology")
    parser.add_argument("--config", required=True, help="Path to perimetercontrol.conf.yaml")
    parser.add_argument("command", choices=["summary", "prepare-interface", "cleanup-interface"])
    parser.add_argument("--format", choices=["json", "shell"], default="json")
    args = parser.parse_args()

    _config, topology = _load_config(Path(args.config))
    isolated_interface = topology["isolated"]["interface"]
    gateway_cidr = topology["lan"]["gateway_cidr"]

    if args.command == "summary":
        if args.format == "shell":
            print(_summary_shell(topology))
        else:
            print(json.dumps(topology, indent=2))
        return 0

    if args.command == "prepare-interface":
        _run("/usr/sbin/ip", "addr", "flush", "dev", isolated_interface)
        _run("/usr/sbin/ip", "addr", "add", gateway_cidr, "dev", isolated_interface)
        _run("/usr/sbin/ip", "link", "set", isolated_interface, "up")
        return 0

    if args.command == "cleanup-interface":
        _run("/usr/sbin/ip", "addr", "flush", "dev", isolated_interface)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())