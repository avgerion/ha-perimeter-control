#!/usr/bin/env python3
"""Standalone Photo Booth dashboard service (port 8093 by default)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

import tornado.ioloop
import tornado.web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("perimetercontrol.photo_booth_dashboard")

SUPERVISOR_API_BASE = os.environ.get("PERIMETERCONTROL_SUPERVISOR_API", "http://127.0.0.1:8080/api/v1")
DASHBOARD_PORT = int(os.environ.get("PERIMETERCONTROL_PHOTO_DASHBOARD_PORT", "8093"))


class DashboardHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        image_url = f"{SUPERVISOR_API_BASE}/cameras/photo_booth/latest.jpg"
        capture_api = "/api/capture"
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write(
            f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Photo Booth Dashboard</title>
<style>body{{font-family:sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}}img{{max-width:100%;border:1px solid #ccc;border-radius:8px}}button{{padding:.6rem 1rem;margin:.5rem 0}}</style>
</head><body>
<h1>Photo Booth Dashboard</h1>
<p>Standalone dashboard service (port {DASHBOARD_PORT}).</p>
<img id='shot' src='{image_url}' alt='latest photo'>
<div><button onclick='capture()'>Capture Photo</button> <button onclick='refreshShot()'>Refresh</button></div>
<pre id='out'></pre>
<script>
function refreshShot(){{document.getElementById('shot').src='{image_url}?t='+Date.now();}}
async function capture(){{
  const r=await fetch('{capture_api}',{{method:'POST'}});
  const t=await r.text();
  document.getElementById('out').textContent=t;
  refreshShot();
}}
setInterval(refreshShot,4000);
</script>
</body></html>"""
        )


class CaptureHandler(tornado.web.RequestHandler):
    def post(self) -> None:
        url = f"{SUPERVISOR_API_BASE}/capabilities/photo_booth/actions/capture_photo"
        req = urllib.request.Request(
            url,
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            self.set_header("Content-Type", "application/json")
            self.write(body)
        except Exception as exc:
            logger.warning("Capture action failed: %s", exc)
            self.set_status(502)
            self.write(json.dumps({"error": str(exc)}))


class HealthHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.write("ok")


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r"/", DashboardHandler),
        (r"/api/capture", CaptureHandler),
        (r"/health", HealthHandler),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(DASHBOARD_PORT, address="0.0.0.0")
    logger.info("Photo Booth dashboard listening on 0.0.0.0:%s", DASHBOARD_PORT)
    tornado.ioloop.IOLoop.current().start()
