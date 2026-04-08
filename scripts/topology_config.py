#!/usr/bin/env python3
"""Helpers for resolving network topology from perimetercontrol.conf.yaml."""

from __future__ import annotations

import ipaddress
from typing import Any, Dict


def resolve_topology(config: Dict[str, Any]) -> Dict[str, Any]:
    topology = config.get("topology", {}) or {}
    upstream = topology.get("upstream", {}) or {}
    isolated = topology.get("isolated", {}) or {}
    ap = config.get("ap", {}) or {}
    wan = config.get("wan", {}) or {}
    lan = config.get("lan", {}) or {}

    isolated_kind = isolated.get("kind") or ("wifi-ap" if ap else "ethernet")
    isolated_interface = (
        isolated.get("interface")
        or lan.get("interface")
        or ap.get("interface")
        or ("wlan0" if isolated_kind == "wifi-ap" else "eth0")
    )

    upstream_interface = upstream.get("interface") or wan.get("interface")
    if not upstream_interface:
        upstream_interface = "eth0" if isolated_interface != "eth0" else "wlan0"

    upstream_kind = upstream.get("kind") or wan.get("kind")
    if not upstream_kind:
        upstream_kind = "wifi-client" if upstream_interface.startswith("wl") else "ethernet"

    subnet = lan.get("subnet", "192.168.111.0/24")
    network = ipaddress.ip_network(subnet, strict=False)
    gateway = lan.get("gateway") or str(next(network.hosts()))
    gateway_cidr = f"{gateway}/{network.prefixlen}"

    return {
        "upstream": {
            "interface": upstream_interface,
            "kind": upstream_kind,
            "label": upstream.get("label") or "Upstream",
        },
        "isolated": {
            "interface": isolated_interface,
            "kind": isolated_kind,
            "label": isolated.get("label") or "Isolated",
        },
        "lan": {
            "subnet": subnet,
            "gateway": gateway,
            "gateway_cidr": gateway_cidr,
            "dhcp_range": lan.get("dhcp_range", "192.168.111.100-192.168.111.200"),
            "lease_hours": int(lan.get("lease_hours", 24)),
        },
        "ap": ap,
    }


def validate_topology(config: Dict[str, Any], topology: Dict[str, Any]) -> None:
    isolated = topology["isolated"]
    upstream = topology["upstream"]

    if isolated["interface"] == upstream["interface"]:
        raise ValueError("isolated.interface and upstream.interface must be different")

    if isolated["kind"] not in {"wifi-ap", "ethernet"}:
        raise ValueError("isolated.kind must be 'wifi-ap' or 'ethernet'")

    if upstream["kind"] not in {"ethernet", "wifi-client"}:
        raise ValueError("upstream.kind must be 'ethernet' or 'wifi-client'")

    if isolated["kind"] == "wifi-ap":
        ap = config.get("ap", {}) or {}
        if not ap.get("ssid"):
            raise ValueError("ap.ssid is required when isolated.kind is 'wifi-ap'")
        if not ap.get("password"):
            raise ValueError("ap.password is required when isolated.kind is 'wifi-ap'")