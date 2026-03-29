"""
Tornado REST API handlers for the Isolator Supervisor.

Route map
---------
GET  /api/v1/node/info                          → NodeInfoHandler
GET  /api/v1/entities                           → EntitiesHandler
GET  /api/v1/entities/{id}                      → EntityStateHandler
POST /api/v1/entities/states/query              → EntityStatesBulkHandler
GET  /api/v1/capabilities                       → CapabilitiesHandler
POST /api/v1/capabilities/{id}/deploy           → CapabilityDeployHandler
POST /api/v1/capabilities/{id}/actions/{action} → CapabilityActionHandler
GET  /api/v1/deployments                        → DeploymentsHandler
POST /api/v1/deployments                        → DeploymentsHandler (bulk deploy)
GET  /api/v1/health                             → HealthHandler
GET  /api/v1/metrics                            → MetricsHandler  (Prometheus text)
WS   /api/v1/events                             → EventsWebSocketHandler
"""

from __future__ import annotations

import json
import logging
from typing import List

import tornado.web
import tornado.websocket

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Base
# ------------------------------------------------------------------

class _Base(tornado.web.RequestHandler):
    @property
    def supervisor(self):
        return self.application.settings["supervisor"]

    def set_default_headers(self) -> None:
        self.set_header("Content-Type", "application/json")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, *_args, **_kwargs):
        """Handle pre-flight CORS."""
        self.set_status(204)

    def _json(self, data) -> None:
        self.write(json.dumps(data, default=str))

    def _err(self, status: int, message: str) -> None:
        self.set_status(status)
        self._json({"error": message})

    def _parse_body(self):
        try:
            return json.loads(self.request.body) if self.request.body else {}
        except json.JSONDecodeError:
            return None


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

class NodeInfoHandler(_Base):
    def get(self):
        self._json(self.supervisor.get_node_info())


class EntitiesHandler(_Base):
    def get(self):
        entities = self.supervisor.get_entities()
        cap_filter = self.get_argument("capability", None)
        if cap_filter:
            entities = [e for e in entities if e.get("capability_id") == cap_filter]
        self._json({"entities": entities, "count": len(entities)})


class EntityStateHandler(_Base):
    def get(self, entity_id: str):
        state = self.supervisor.get_entity_state(entity_id)
        if state is None:
            self._err(404, f"Entity '{entity_id}' not found")
            return
        self._json(state)


class EntityStatesBulkHandler(_Base):
    def post(self):
        body = self._parse_body()
        if body is None:
            self._err(400, "Invalid JSON body")
            return
        entity_ids = body.get("entity_ids", [])
        if not isinstance(entity_ids, list):
            self._err(400, "'entity_ids' must be a list")
            return
        states = self.supervisor.query_entity_states(entity_ids)
        self._json({"states": states, "count": len(states)})


class CapabilitiesHandler(_Base):
    def get(self):
        capabilities = self.supervisor.db.list_capabilities()
        self._json({"capabilities": capabilities, "count": len(capabilities)})


class CapabilityDeployHandler(_Base):
    async def post(self, cap_id: str):
        config = self._parse_body()
        if config is None:
            self._err(400, "Invalid JSON body")
            return
        dry_run = self.get_argument("dry_run", "false").lower() == "true"
        result = await self.supervisor.deploy({cap_id: config}, initiator="api", dry_run=dry_run)
        code = 200 if result["status"] in ("succeeded", "preview") else 422
        self.set_status(code)
        self._json(result)


class CapabilityActionHandler(_Base):
    async def post(self, cap_id: str, action_id: str):
        params = self._parse_body() or {}
        result = await self.supervisor.trigger_action(cap_id, action_id, params)
        code = 200 if result.get("success") else 422
        self.set_status(code)
        self._json(result)


class DeploymentsHandler(_Base):
    def get(self):
        limit = int(self.get_argument("limit", "50"))
        deployments = self.supervisor.db.list_deployments(limit=limit)
        self._json({"deployments": deployments, "count": len(deployments)})

    async def post(self):
        body = self._parse_body()
        if body is None:
            self._err(400, "Invalid JSON body")
            return
        capabilities = body.get("capabilities", {})
        if not capabilities:
            self._err(400, "'capabilities' must be a non-empty object")
            return
        dry_run = body.get("dry_run", False)
        result = await self.supervisor.deploy(capabilities, initiator="api", dry_run=dry_run)
        code = 200 if result["status"] in ("succeeded", "preview") else 422
        self.set_status(code)
        self._json(result)


class HealthHandler(_Base):
    def get(self):
        self._json(self.supervisor.get_health_summary())


class MetricsHandler(_Base):
    def get(self):
        """Prometheus text format metrics."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu_val = cpu
            mem_val = mem.used // (1024 * 1024)
            disk_free = disk.free // (1024 * 1024)
        except ImportError:
            cpu_val = mem_val = disk_free = 0

        res = self.supervisor.resources.get_usage_summary()
        caps = self.supervisor.db.list_capabilities()

        lines = [
            "# HELP isolator_cpu_percent Host CPU usage percent",
            "# TYPE isolator_cpu_percent gauge",
            f"isolator_cpu_percent {cpu_val}",
            "",
            "# HELP isolator_memory_mb_used Host memory used MB",
            "# TYPE isolator_memory_mb_used gauge",
            f"isolator_memory_mb_used {mem_val}",
            "",
            "# HELP isolator_disk_free_mb Host disk free MB",
            "# TYPE isolator_disk_free_mb gauge",
            f"isolator_disk_free_mb {disk_free}",
            "",
            f"# HELP isolator_capability_cpu_cores Capability allocated CPU cores",
            f"# TYPE isolator_capability_cpu_cores gauge",
            f"isolator_capability_cpu_cores_used {res['cpu_cores_used']}",
            f"isolator_capability_cpu_cores_total {res['cpu_cores_total']}",
            "",
            "# HELP isolator_capability_health 1=active/ok 0=failed/degraded",
            "# TYPE isolator_capability_health gauge",
        ]
        for cap in caps:
            val = 1 if cap["status"] == "active" else 0
            lines.append(f'isolator_capability_health{{capability="{cap["id"]}"}} {val}')

        self.set_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------
# WebSocket event stream
# ------------------------------------------------------------------

class EventsWebSocketHandler(tornado.websocket.WebSocketHandler):
    """
    Stream supervisor events to connected clients.

    Clients can optionally send a JSON subscription filter::

        {"event_types": ["entity_updated", "deployment_completed"]}

    If no filter is sent (or an empty list), all events are forwarded.
    """

    _connections: List["EventsWebSocketHandler"] = []

    def check_origin(self, origin: str) -> bool:
        return True  # Local-network-only; permissive CORS is acceptable

    def open(self) -> None:
        self.__class__._connections.append(self)
        self._filter: List[str] = []
        self._unsub = self.application.settings["supervisor"].subscribe_events(self._on_event)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def on_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            self._filter = data.get("event_types", [])
        except (json.JSONDecodeError, AttributeError):
            pass

    def on_close(self) -> None:
        self.__class__._connections.remove(self)
        self._unsub()
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    def _on_event(self, event: dict) -> None:
        if self._filter and event.get("type") not in self._filter:
            return
        try:
            self.write_message(json.dumps(event, default=str))
        except tornado.websocket.WebSocketClosedError:
            pass


# ------------------------------------------------------------------
# Application factory
# ------------------------------------------------------------------

def make_app(supervisor) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/api/v1/node/info",                          NodeInfoHandler),
            (r"/api/v1/entities/states/query",              EntityStatesBulkHandler),
            (r"/api/v1/entities/([^/]+)",                   EntityStateHandler),
            (r"/api/v1/entities",                           EntitiesHandler),
            (r"/api/v1/capabilities/([^/]+)/actions/([^/]+)", CapabilityActionHandler),
            (r"/api/v1/capabilities/([^/]+)/deploy",        CapabilityDeployHandler),
            (r"/api/v1/capabilities",                       CapabilitiesHandler),
            (r"/api/v1/deployments",                        DeploymentsHandler),
            (r"/api/v1/health",                             HealthHandler),
            (r"/api/v1/metrics",                            MetricsHandler),
            (r"/api/v1/events",                             EventsWebSocketHandler),
        ],
        supervisor=supervisor,
    )
