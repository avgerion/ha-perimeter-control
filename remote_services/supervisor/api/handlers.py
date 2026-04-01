"""
Tornado REST API handlers for the Isolator Supervisor.

Route map
---------
GET  /api/v1/node/info                          → NodeInfoHandler
GET  /api/v1/entities                           → EntitiesHandler
GET  /api/v1/entities/{id}                      → EntityStateHandler
POST /api/v1/entities/states/query              → EntityStatesBulkHandler
GET  /api/v1/ha/integration                     → HAIntegrationHandler (combined schema+states)
GET  /api/v1/ha/dashboard-urls                  → HADashboardUrlsHandler
GET  /api/v1/ha/config-status                   → HAConfigStatusHandler
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

        # ---- GPIO (all chips) ------------------------------------------------
        gpio_chips = []
        for chip_path in sorted(glob.glob("/dev/gpiochip*")):
            chip_name = Path(chip_path).name
            info: Dict[str, Any] = {"device": chip_path}
            for attr in ("label", "ngpio"):
                p = Path(f"/sys/bus/gpio/devices/{chip_name}/{attr}")
                if p.exists():
                    val = p.read_text().strip()
                    info[attr] = int(val) if attr == "ngpio" else val
            gpio_chips.append(info)
        features["gpio"] = {"chips": gpio_chips, "available": len(gpio_chips) > 0}

        # ---- I2C buses -------------------------------------------------------
        i2c_buses = []
        for path in sorted(glob.glob("/dev/i2c-*")):
            bus_num = path.rsplit("-", 1)[-1]
            bus: Dict[str, Any] = {"device": path, "bus": int(bus_num)}
            # i2cdetect -y -r: read-mode scan, safe for most devices
            detect_out = self._run(["i2cdetect", "-y", "-r", bus_num])
            devices = []
            for row in detect_out.splitlines()[1:]:
                for token in row.split()[1:]:
                    if token not in ("--", "UU") and len(token) == 2:
                        try:
                            devices.append({"addr": f"0x{token}", "addr_int": int(token, 16)})
                        except ValueError:
                            pass
            bus["detected_devices"] = devices
            i2c_buses.append(bus)
        features["i2c"] = {"buses": i2c_buses, "available": len(i2c_buses) > 0}

        # ---- SPI devices ----------------------------------------------------
        spi_devs = [{"device": p} for p in sorted(glob.glob("/dev/spidev*"))]
        features["spi"] = {"devices": spi_devs, "available": len(spi_devs) > 0}

        # ---- I2S / Audio (ALSA cards) ----------------------------------------
        audio_cards = []
        cards_file = Path("/proc/asound/cards")
        if cards_file.exists():
            for line in cards_file.read_text().splitlines():
                line = line.strip()
                if line and line[0].isdigit():
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        name = parts[1].strip("[]:")
                        audio_cards.append({"card": int(parts[0]), "name": name, "description": parts[2].strip()})
        features["audio"] = {"cards": audio_cards, "available": len(audio_cards) > 0}

        # ---- UART / serial ports --------------------------------------------
        uart_ports = []
        seen = set()
        for pattern in ("/dev/serial*", "/dev/ttyAMA*", "/dev/ttyS[0-9]*"):
            for path in sorted(glob.glob(pattern)):
                real = str(Path(path).resolve())
                if real not in seen:
                    seen.add(real)
                    uart_ports.append({"device": path, "resolved": real})
        features["uart"] = {"ports": uart_ports, "available": len(uart_ports) > 0}

        # ---- PWM channels ---------------------------------------------------
        pwm_chips = []
        pwm_base = Path("/sys/class/pwm")
        if pwm_base.exists():
            for chip in sorted(pwm_base.iterdir()):
                info_pwm: Dict[str, Any] = {"chip": chip.name}
                npwm = chip / "npwm"
                if npwm.exists():
                    info_pwm["channels"] = int(npwm.read_text().strip())
                pwm_chips.append(info_pwm)
        features["pwm"] = {"chips": pwm_chips, "available": len(pwm_chips) > 0}

        # ---- Device tree overlays / params (from /boot/firmware/config.txt) --
        dt_overlays: List[str] = []
        dt_params: Dict[str, str] = {}
        for cfg in ("/boot/firmware/config.txt", "/boot/config.txt"):
            p = Path(cfg)
            if p.exists():
                for raw in p.read_text().splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("dtoverlay="):
                        overlay = line.split("=", 1)[1].split(",")[0]
                        dt_overlays.append(overlay)
                    elif line.startswith("dtparam="):
                        kv = line.split("=", 1)[1]
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            dt_params[k.strip()] = v.strip()
                break
        features["hardware_config"] = {"dt_overlays": dt_overlays, "dt_params": dt_params}

        # ---- GStreamer ------------------------------------------------------
        gst_version = self._run(["gst-inspect-1.0", "--version"]).strip()
        gst_available = bool(gst_version)
        gst_elements: List[Dict[str, Any]] = []
        if gst_available:
            _INTERESTING = (
                "v4l2src", "libcamerasrc", "autovideosrc", "videotestsrc",
                "alsasrc", "alsasink", "autoaudiosrc", "autoaudiosink",
                "x264enc", "nvh264enc", "v4l2h264enc", "avdec_h264",
                "jpegenc", "jpegdec", "vp8enc", "vp9enc",
                "rtspsrc", "rtspclientsink", "udpsrc", "udpsink",
                "rtph264pay", "rtph264depay",
                "audioconvert", "audioresample", "volume", "level",
                "matroskamux", "mp4mux", "oggmux",
                "pipewiresrc", "pipewiresink", "pulsesrc", "pulsesink",
            )
            all_elements = set(self._run(["gst-inspect-1.0", "--print-all"]).split())
            for elem in _INTERESTING:
                if elem in all_elements:
                    gst_elements.append({"element": elem})
        features["gstreamer"] = {
            "available": gst_available,
            "version": gst_version.splitlines()[0] if gst_version else None,
            "key_elements": gst_elements,
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
# Home Assistant Integration Optimized Endpoints
# ------------------------------------------------------------------

class HAIntegrationHandler(_Base):
    """Combined endpoint for HA integration - entities, states, and config in one call."""
    
    def get(self):
        # Get all entities from supervisor
        entities = self.supervisor.get_entities()
        
        # Get all entity states
        entity_ids = [e.get("id") for e in entities if e.get("id")]
        entity_states = self.supervisor.query_entity_states(entity_ids)
        
        # Convert to dict for easier lookup
        states_dict = {s["entity_id"]: s for s in entity_states if "entity_id" in s}
        
        # Get service info with dashboard URLs
        services_info = self._get_services_with_dashboard_urls()
        
        # Get config version info for change detection
        config_version = self._get_config_version()
        
        self._json({
            "entities": entities,
            "entity_states": states_dict,
            "services": services_info,
            "config_version": config_version,
            "node_info": self.supervisor.get_node_info(),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    def _get_services_with_dashboard_urls(self) -> List[Dict[str, Any]]:
        """Get service info with pre-computed dashboard URLs."""
        services_dir = self._services_dir()
        services = []
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                try:
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    metadata = descriptor.get("metadata", {})
                    spec = descriptor.get("spec", {})
                    access_profile = spec.get("access_profile", {})
                    
                    # Compute dashboard URL from access profile
                    dashboard_url = self._compute_dashboard_url(access_profile)
                    
                    services.append({
                        "id": metadata.get("id") or path.stem.replace(".service", ""),
                        "name": metadata.get("name", "unknown"),
                        "version": metadata.get("version"),
                        "dashboard_url": dashboard_url,
                        "status": "active" if self._service_is_active(metadata.get("id")) else "inactive",
                        "port": access_profile.get("port", 8080),
                        "access_mode": access_profile.get("mode", "localhost"),
                    })
                except Exception as exc:
                    continue
                    
        return services
    
    def _compute_dashboard_url(self, access_profile: Dict[str, Any]) -> Optional[str]:
        """Compute dashboard URL from access profile."""
        mode = access_profile.get("mode", "localhost")
        if mode == "isolated":
            return None  # Service not accessible
            
        port = access_profile.get("port", 8080)
        # In real deployment, this would use the actual hostname/IP
        return f"http://localhost:{port}/"
    
    def _service_is_active(self, service_id: str) -> bool:
        """Check if service is currently active via capability status."""
        if not service_id:
            return False
            
        capabilities = self.supervisor.db.list_capabilities()
        for cap in capabilities:
            if cap.get("id") == service_id:
                return cap.get("status") == "active"
        return False
    
    def _get_config_version(self) -> str:
        """Get current config version hash for change detection."""
        import hashlib
        
        # Create hash from all service config files
        config_content = ""
        services_dir = self._services_dir()
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                if path.exists():
                    config_content += path.read_text(encoding="utf-8")
        
        return hashlib.sha256(config_content.encode()).hexdigest()[:12]


class HADashboardUrlsHandler(_Base):
    """Endpoint providing dashboard URLs for all services."""
    
    def get(self):
        services = self._get_services_with_urls()
        self._json({
            "services": services,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    def _get_services_with_urls(self) -> Dict[str, Dict[str, Any]]:
        """Get dashboard URLs indexed by service ID."""
        services = {}
        services_dir = self._services_dir()
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                try:
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    metadata = descriptor.get("metadata", {})
                    spec = descriptor.get("spec", {})
                    access_profile = spec.get("access_profile", {})
                    
                    service_id = metadata.get("id") or path.stem.replace(".service", "")
                    dashboard_url = self._compute_dashboard_url(access_profile)
                    
                    if dashboard_url:  # Only include accessible services
                        services[service_id] = {
                            "url": dashboard_url,
                            "name": metadata.get("name", "unknown"),
                            "port": access_profile.get("port", 8080),
                            "mode": access_profile.get("mode", "localhost"),
                            "status": "active" if self._service_is_active(service_id) else "inactive"
                        }
                except Exception:
                    continue
                    
        return services
    
    def _compute_dashboard_url(self, access_profile: Dict[str, Any]) -> Optional[str]:
        """Compute dashboard URL from access profile."""
        mode = access_profile.get("mode", "localhost")
        if mode == "isolated":
            return None
            
        port = access_profile.get("port", 8080)
        return f"http://localhost:{port}/"
    
    def _service_is_active(self, service_id: str) -> bool:
        """Check if service is active."""
        capabilities = self.supervisor.db.list_capabilities()
        for cap in capabilities:
            if cap.get("id") == service_id:
                return cap.get("status") == "active"
        return False


class HAConfigStatusHandler(_Base):
    """Endpoint for config change detection and versioning."""
    
    def get(self):
        config_info = self._get_config_status()
        self._json(config_info)
    
    def _get_config_status(self) -> Dict[str, Any]:
        """Get config status with version and change information."""
        import hashlib
        
        services_config = {}
        overall_hash_content = ""
        
        services_dir = self._services_dir()
        
        if services_dir.exists():
            for path in sorted(services_dir.glob("*.service.yaml")):
                service_id = path.stem.replace(".service", "")
                
                try:
                    # Service descriptor
                    descriptor = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    descriptor_content = path.read_text(encoding="utf-8")
                    
                    # Service config file (if exists)
                    config_content = ""
                    config_path = self._service_config_path(descriptor)
                    if config_path and config_path.exists():
                        config_content = config_path.read_text(encoding="utf-8")
                    
                    # Combined hash for this service
                    combined_content = descriptor_content + config_content
                    service_hash = hashlib.sha256(combined_content.encode()).hexdigest()[:12]
                    
                    services_config[service_id] = {
                        "version": service_hash,
                        "config_path": str(config_path) if config_path else None,
                        "config_exists": config_path.exists() if config_path else False,
                        "last_modified": config_path.stat().st_mtime if config_path and config_path.exists() else None
                    }
                    
                    overall_hash_content += combined_content
                    
                except Exception as exc:
                    services_config[service_id] = {
                        "version": "error",
                        "error": str(exc)
                    }
        
        overall_version = hashlib.sha256(overall_hash_content.encode()).hexdigest()[:12]
        
        return {
            "overall_version": overall_version,
            "services": services_config,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


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
            # HA Integration-specific endpoints
            (r"/api/v1/ha/integration",                     HAIntegrationHandler),
            (r"/api/v1/ha/dashboard-urls",                  HADashboardUrlsHandler),
            (r"/api/v1/ha/config-status",                   HAConfigStatusHandler),
        ],
        supervisor=supervisor,
    )
