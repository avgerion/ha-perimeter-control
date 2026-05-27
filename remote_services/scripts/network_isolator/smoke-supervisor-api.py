#!/usr/bin/env python3
"""Quick smoke test for the Isolator Supervisor API.

Usage:
  python scripts/smoke-supervisor-api.py --base-url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _get(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=10) as response:
        data = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.status, json.loads(data)
        return response.status, data


def _post(base_url: str, path: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read().decode("utf-8")
        return response.status, json.loads(data)


def _assert(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def run(base_url: str) -> dict:
    report = {}

    status, node_info = _get(base_url, "/api/v1/node/info")
    _assert(status == 200, "node info endpoint did not return 200")
    _assert("supervisor_version" in node_info, "node info missing supervisor_version")
    report["node_info"] = {
        "node_id": node_info.get("node_id"),
        "version": node_info.get("supervisor_version"),
    }

    status, health = _get(base_url, "/api/v1/health")
    _assert(status == 200, "health endpoint did not return 200")
    report["health"] = health

    dry_payload = {
        "capabilities": {
            "network_isolation": {
                "type": "network_isolation",
                "name": "Network Isolation",
                "devices": [],
                "policies": [],
            }
        },
        "dry_run": True,
    }
    status, dry_run = _post(base_url, "/api/v1/deployments", dry_payload)
    _assert(status == 200, "dry-run deployment failed")
    _assert(dry_run.get("status") == "preview", "dry-run did not return preview status")
    report["deploy_dry_run"] = dry_run

    real_payload = dict(dry_payload)
    real_payload["dry_run"] = False
    status, deploy = _post(base_url, "/api/v1/deployments", real_payload)
    _assert(status == 200, "real deployment call failed")
    _assert(deploy.get("status") in ("succeeded", "preview"), "deployment did not succeed")
    report["deploy_real"] = {
        "deployment_id": deploy.get("deployment_id"),
        "status": deploy.get("status"),
    }

    status, action = _post(
        base_url,
        "/api/v1/capabilities/network_isolation/actions/reload_rules",
        {},
    )
    _assert(status == 200, "reload_rules action failed")
    _assert(action.get("success") is True, "reload_rules action did not report success")
    report["action_reload_rules"] = action

    status, metrics = _get(base_url, "/api/v1/metrics")
    _assert(status == 200, "metrics endpoint did not return 200")
    _assert("isolator_cpu_percent" in metrics, "metrics payload missing expected gauge")
    report["metrics_check"] = "ok"

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the supervisor API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Supervisor API base URL")
    args = parser.parse_args()

    try:
        report = run(args.base_url.rstrip("/"))
        print(json.dumps({"status": "ok", "report": report}, indent=2))
        return 0
    except urllib.error.HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
