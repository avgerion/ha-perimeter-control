#!/usr/bin/env python3
"""Standalone GPIO Control dashboard service (port 8095 by default)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

import tornado.escape
import tornado.ioloop
import tornado.web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("perimetercontrol.gpio_dashboard")

SUPERVISOR_API_BASE = os.environ.get("PERIMETERCONTROL_SUPERVISOR_API", "http://127.0.0.1:8080/api/v1")
DASHBOARD_PORT = int(os.environ.get("PERIMETERCONTROL_GPIO_DASHBOARD_PORT", "8095"))


def _http_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw or "{}")


class DashboardHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write(
            f"""<!doctype html>
<html><head><meta charset='utf-8'><title>GPIO Control Dashboard</title>
<style>body{{font-family:sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}}.row{{display:flex;gap:.5rem;align-items:center;margin:.5rem 0}}button{{padding:.35rem .8rem}}</style>
</head><body>
<h1>GPIO Control Dashboard</h1>
<p>Standalone dashboard service (port {DASHBOARD_PORT}).</p>
<div id='rows'>Loading...</div>
<script>
async function load(){{
  const r=await fetch('/api/entities');
  const d=await r.json();
  const entities=(d.entities||[]);
  const rows=document.getElementById('rows');
  rows.innerHTML='';
  for(const e of entities){{
    const div=document.createElement('div');div.className='row';
    div.innerHTML='<strong>'+(e.friendly_name||e.id)+' ('+(e.state||'unknown')+')</strong>';
    const on=document.createElement('button');on.textContent='ON';
    on.onclick=()=>act(e.id,'turn_on');
    const off=document.createElement('button');off.textContent='OFF';
    off.onclick=()=>act(e.id,'turn_off');
    div.appendChild(on);div.appendChild(off);rows.appendChild(div);
  }}
  if(!entities.length)rows.textContent='No GPIO entities published by supervisor.';
}}
async function act(entityId,action){{
  await fetch('/api/action',{{
    method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{entity_id:entityId, action:action}})
  }});
  setTimeout(load,250);
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
            gpio_entities = [
                entity for entity in entities
                if isinstance(entity, dict)
                and (entity.get("capability") == "gpio_control" or entity.get("capability_id") == "gpio_control")
                and entity.get("type") in {"switch", "light"}
            ]
            self.write({"entities": gpio_entities})
        except Exception as exc:
            logger.warning("Failed to fetch GPIO entities: %s", exc)
            self.set_status(502)
            self.write({"error": str(exc), "entities": []})


class ActionHandler(tornado.web.RequestHandler):
    def post(self) -> None:
        try:
            body = tornado.escape.json_decode(self.request.body or b"{}")
            entity_id = str(body.get("entity_id", "")).strip()
            action = str(body.get("action", "")).strip()
            if not entity_id or not action:
                self.set_status(400)
                self.write({"error": "entity_id and action are required"})
                return

            response = _http_json(
                f"{SUPERVISOR_API_BASE}/capabilities/gpio_control/actions/{action}",
                method="POST",
                payload={"entity_id": entity_id},
            )
            self.write(response)
        except Exception as exc:
            logger.warning("GPIO action failed: %s", exc)
            self.set_status(502)
            self.write({"error": str(exc)})


class HealthHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.write("ok")


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r"/", DashboardHandler),
        (r"/api/entities", EntitiesHandler),
        (r"/api/action", ActionHandler),
        (r"/health", HealthHandler),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(DASHBOARD_PORT, address="0.0.0.0")
    logger.info("GPIO dashboard listening on 0.0.0.0:%s", DASHBOARD_PORT)
    tornado.ioloop.IOLoop.current().start()
