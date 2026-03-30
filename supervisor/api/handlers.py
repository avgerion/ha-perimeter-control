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
GET  /api/v1/services                           → ServicesHandler
GET  /api/v1/services/{id}/config               → ServiceConfigHandler
PUT  /api/v1/services/{id}/config               → ServiceConfigHandler
GET  /api/v1/services/{id}/access               → ServiceAccessHandler
PUT  /api/v1/services/{id}/access               → ServiceAccessHandler
GET  /api/v1/node/features                      → NodeFeaturesHandler
WS   /api/v1/events                             → EventsWebSocketHandler
"""

from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tornado.web
import tornado.websocket
import yaml

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

    def _services_dir(self) -> Path:
        return Path(self.supervisor.config_dir) / "services"

    def _service_descriptor_path(self, service_id: str) -> Path:
        return self._services_dir() / f"{service_id}.service.yaml"

    def _load_service_descriptor(self, service_id: str) -> Optional[dict]:
        path = self._service_descriptor_path(service_id)
        if not path.exists():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _save_service_descriptor(self, service_id: str, descriptor: dict) -> Path:
        path = self._service_descriptor_path(service_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        return path

    def _service_config_path(self, descriptor: dict) -> Optional[Path]:
        try:
            cfg_path = descriptor["spec"]["config_file"]["path"]
            return Path(cfg_path)
        except Exception:
            return None


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

class NodeInfoHandler(_Base):
    def get(self):
        self._json(self.supervisor.get_node_info())


class NodeFeaturesHandler(_Base):
    """Detect hardware features present on this Pi node."""

    @staticmethod
    def _run(cmd: List[str]) -> str:
        try:
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode()
        except Exception:
            return ""

    def get(self):
        features: Dict[str, Any] = {}

        # ---- Cameras --------------------------------------------------------
        # Internal bcm2835 codec/ISP pipeline nodes are not capture cameras
        _CODEC_SKIP = ("codec", "isp", "image_fx")
        cameras = []
        # V4L2 USB/ISP cameras
        for path in sorted(glob.glob("/dev/video*")):
            cam: Dict[str, Any] = {"device": path, "type": "v4l2"}
            name_out = self._run(["v4l2-ctl", "--device", path, "--info"])
            for line in name_out.splitlines():
                if "Card type" in line:
                    cam["name"] = line.split(":", 1)[-1].strip()
                    break
            name_lc = cam.get("name", "").lower()
            if any(skip in name_lc for skip in _CODEC_SKIP):
                continue  # skip internal encoder/ISP nodes
            cameras.append(cam)
        # Raspberry Pi CSI (libcamera)
        libcam_out = self._run(["libcamera-hello", "--list-cameras"])
        if "Available cameras" in libcam_out:
            for line in libcam_out.splitlines():
                line = line.strip()
                if line and line[0].isdigit():
                    cameras.append({"type": "csi", "name": line})
        features["cameras"] = cameras

        # ---- BLE adapters ---------------------------------------------------
        ble_adapters = []
        hciconfig_out = self._run(["hciconfig"])
        current: Optional[Dict[str, Any]] = None
        for line in hciconfig_out.splitlines():
            if line and not line[0].isspace():
                if current:
                    ble_adapters.append(current)
                parts = line.split(":", 1)
                current = {"device": parts[0].strip(), "info": parts[1].strip() if len(parts) > 1 else ""}
            elif current and "BD Address" in line:
                current["bd_address"] = line.split("BD Address:")[-1].split()[0]
            elif current and "UP RUNNING" in line:
                current["running"] = True
        if current:
            ble_adapters.append(current)
        # Serial Bluetooth dongles (ttyACM, ttyUSB)
        for path in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
            ble_adapters.append({"device": path, "type": "serial"})
        features["ble_adapters"] = ble_adapters

        # ---- GPIO -----------------------------------------------------------
        gpio_chip = Path("/dev/gpiochip0")
        features["gpio"] = {
            "available": gpio_chip.exists(),
            "chip": str(gpio_chip) if gpio_chip.exists() else None,
        }

        # ---- Storage --------------------------------------------------------
        storage = []
        df_out = self._run(["df", "-h", "--output=source,size,used,avail,pcent,target"])
        lines = df_out.strip().splitlines()
        if len(lines) > 1:
            for row in lines[1:]:
                cols = row.split()
                if len(cols) >= 6 and not cols[0].startswith("tmpfs") and not cols[0].startswith("devtmpfs"):
                    storage.append({"device": cols[0], "size": cols[1], "used": cols[2], "avail": cols[3], "use_pct": cols[4], "mount": cols[5]})
        features["storage"] = storage

        # ---- Network interfaces ---------------------------------------------
        net_ifaces = []
        for iface_path in sorted(Path("/sys/class/net").iterdir()):
            iface = iface_path.name
            if iface == "lo":
                continue
            operstate = (iface_path / "operstate").read_text().strip() if (iface_path / "operstate").exists() else "unknown"
            net_ifaces.append({"name": iface, "state": operstate})
        features["network_interfaces"] = net_ifaces

        self._json({"node_features": features})


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


class ServicesHandler(_Base):
    def get(self):
        services_dir = self._services_dir()
        services = []
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                try:
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    metadata = descriptor.get("metadata", {})
                    spec = descriptor.get("spec", {})
                    services.append(
                        {
                            "id": metadata.get("id") or path.stem.replace(".service", ""),
                            "name": metadata.get("name", "unknown"),
                            "version": metadata.get("version"),
                            "descriptor_file": str(path),
                            "runtime": (spec.get("runtime") or {}).get("type"),
                            "config_file": (spec.get("config_file") or {}).get("path"),
                        }
                    )
                except Exception as exc:
                    services.append(
                        {
                            "id": path.stem.replace(".service", ""),
                            "name": "invalid_descriptor",
                            "error": str(exc),
                            "descriptor_file": str(path),
                        }
                    )

        self._json({"services": services, "count": len(services)})


class ServiceConfigHandler(_Base):
    def get(self, service_id: str):
        descriptor = self._load_service_descriptor(service_id)
        if descriptor is None:
            self._err(404, f"Service descriptor not found: {service_id}")
            return

        cfg_path = self._service_config_path(descriptor)
        if cfg_path is None:
            self._err(422, "Descriptor missing spec.config_file.path")
            return

        if not cfg_path.exists():
            self._json(
                {
                    "service_id": service_id,
                    "config_file": str(cfg_path),
                    "exists": False,
                    "format": descriptor.get("spec", {}).get("config_file", {}).get("format", "yaml"),
                    "content": "",
                }
            )
            return

        self._json(
            {
                "service_id": service_id,
                "config_file": str(cfg_path),
                "exists": True,
                "format": descriptor.get("spec", {}).get("config_file", {}).get("format", "yaml"),
                "content": cfg_path.read_text(encoding="utf-8"),
            }
        )

    def put(self, service_id: str):
        body = self._parse_body()
        if body is None:
            self._err(400, "Invalid JSON body")
            return

        descriptor = self._load_service_descriptor(service_id)
        if descriptor is None:
            self._err(404, f"Service descriptor not found: {service_id}")
            return

        cfg_path = self._service_config_path(descriptor)
        if cfg_path is None:
            self._err(422, "Descriptor missing spec.config_file.path")
            return

        content = body.get("content")
        if not isinstance(content, str):
            self._err(400, "'content' must be a string")
            return

        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if cfg_path.exists():
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = cfg_path.with_suffix(cfg_path.suffix + f".bak.{ts}")
            backup_path.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")

        cfg_path.write_text(content, encoding="utf-8")
        self._json(
            {
                "success": True,
                "service_id": service_id,
                "config_file": str(cfg_path),
                "bytes_written": len(content.encode("utf-8")),
            }
        )


class ServiceAccessHandler(_Base):
    def get(self, service_id: str):
        descriptor = self._load_service_descriptor(service_id)
        if descriptor is None:
            self._err(404, f"Service descriptor not found: {service_id}")
            return

        access = descriptor.get("spec", {}).get("access_profile", {})
        self._json({"service_id": service_id, "access_profile": access})

    _VALID_MODES       = {"localhost", "upstream", "isolated", "all", "explicit"}
    _VALID_TLS_MODES   = {False, "off", "self_signed", "provided_cert"}
    _VALID_AUTH_MODES  = {"none", "token", "mTLS"}
    _VALID_SCOPES      = {"lan_only", "vpn_only", "tunnel_only", "any"}

    def put(self, service_id: str):
        body = self._parse_body()
        if body is None:
            self._err(400, "Invalid JSON body")
            return

        descriptor = self._load_service_descriptor(service_id)
        if descriptor is None:
            self._err(404, f"Service descriptor not found: {service_id}")
            return

        access = body.get("access_profile")
        if not isinstance(access, dict):
            self._err(400, "'access_profile' must be an object")
            return

        # Enum validation
        errors = []
        if "mode" in access and access["mode"] not in self._VALID_MODES:
            errors.append(f"invalid mode '{access['mode']}'; allowed: {sorted(self._VALID_MODES)}")
        if "tls_mode" in access and access["tls_mode"] not in self._VALID_TLS_MODES:
            errors.append(f"invalid tls_mode '{access['tls_mode']}'; allowed: {sorted(str(v) for v in self._VALID_TLS_MODES)}")
        if "auth_mode" in access and access["auth_mode"] not in self._VALID_AUTH_MODES:
            errors.append(f"invalid auth_mode '{access['auth_mode']}'; allowed: {sorted(self._VALID_AUTH_MODES)}")
        if "exposure_scope" in access and access["exposure_scope"] not in self._VALID_SCOPES:
            errors.append(f"invalid exposure_scope '{access['exposure_scope']}'; allowed: {sorted(self._VALID_SCOPES)}")
        if "port" in access:
            port = access["port"]
            if not isinstance(port, int) or not (1 <= port <= 65535):
                errors.append(f"invalid port '{port}'; must be integer 1-65535")
        if errors:
            self._err(400, "; ".join(errors))
            return

        spec = descriptor.setdefault("spec", {})
        spec["access_profile"] = access
        path = self._save_service_descriptor(service_id, descriptor)

        self._json(
            {
                "success": True,
                "service_id": service_id,
                "descriptor_file": str(path),
                "access_profile": access,
            }
        )


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
            (r"/api/v1/node/features",                      NodeFeaturesHandler),
            (r"/api/v1/entities/states/query",              EntityStatesBulkHandler),
            (r"/api/v1/entities/([^/]+)",                   EntityStateHandler),
            (r"/api/v1/entities",                           EntitiesHandler),
            (r"/api/v1/capabilities/([^/]+)/actions/([^/]+)", CapabilityActionHandler),
            (r"/api/v1/capabilities/([^/]+)/deploy",        CapabilityDeployHandler),
            (r"/api/v1/capabilities",                       CapabilitiesHandler),
            (r"/api/v1/deployments",                        DeploymentsHandler),
            (r"/api/v1/health",                             HealthHandler),
            (r"/api/v1/metrics",                            MetricsHandler),
            (r"/api/v1/services/([^/]+)/config",            ServiceConfigHandler),
            (r"/api/v1/services/([^/]+)/access",            ServiceAccessHandler),
            (r"/api/v1/services",                           ServicesHandler),
            (r"/api/v1/events",                             EventsWebSocketHandler),
        ],
        supervisor=supervisor,
    )
