#!/usr/bin/env python3
"""Standalone BLE GATT Repeater dashboard service (port 8091 by default)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

import tornado.ioloop
import tornado.web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("perimetercontrol.ble_dashboard")

SUPERVISOR_API_BASE = os.environ.get("PERIMETERCONTROL_SUPERVISOR_API", "http://127.0.0.1:8080/api/v1")
DASHBOARD_PORT = int(os.environ.get("PERIMETERCONTROL_BLE_DASHBOARD_PORT", "8091"))


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw or "{}")


class DashboardHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write(
            f"""<!doctype html>
<html><head><meta charset='utf-8'><title>BLE Dashboard</title>
<style>body{{font-family:sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:.45rem}}th{{background:#f4f4f4}}</style>
</head><body>
<h1>BLE GATT Repeater Dashboard</h1>
<p>Standalone dashboard service (port {DASHBOARD_PORT}).</p>
<div id='status'>Loading...</div>
<table><thead><tr><th>Entity</th><th>Type</th><th>State</th></tr></thead><tbody id='rows'></tbody></table>
<script>
async function load(){{
  const r=await fetch('/api/entities');
  const d=await r.json();
  const entities=d.entities||[];
  document.getElementById('status').textContent='Entities: '+entities.length;
  const tbody=document.getElementById('rows');tbody.innerHTML='';
  for(const e of entities){{
    const tr=document.createElement('tr');
    tr.innerHTML='<td>'+ (e.friendly_name||e.id) +'</td><td>'+ (e.type||'') +'</td><td>'+ (e.state||'unknown') +'</td>';
    tbody.appendChild(tr);
  }}
}}
load();setInterval(load,5000);
</script>
</body></html>"""
        )


class EntitiesHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        try:
            payload = _http_json(f"{SUPERVISOR_API_BASE}/ha/integration")
            entities = payload.get("entities", [])
            ble_entities = [
                entity for entity in entities
                if isinstance(entity, dict)
                and (entity.get("capability") == "ble_gatt_repeater" or entity.get("capability_id") == "ble_gatt_repeater")
            ]
            self.write({"entities": ble_entities})
        except Exception as exc:
            logger.warning("Failed to fetch BLE entities: %s", exc)
            self.set_status(502)
            self.write({"error": str(exc), "entities": []})


class HealthHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.write("ok")


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r"/", DashboardHandler),
        (r"/api/entities", EntitiesHandler),
        (r"/health", HealthHandler),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(DASHBOARD_PORT, address="0.0.0.0")
    logger.info("BLE dashboard listening on 0.0.0.0:%s", DASHBOARD_PORT)
    tornado.ioloop.IOLoop.current().start()
