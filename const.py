
import os
from pathlib import Path

DOMAIN = "perimeter_control"
PLATFORMS = [
    "sensor",
    "switch",
    "binary_sensor",
    "button",
    "camera",
    "light",
]



INTEGRATION_DIR = Path(__file__).parent
# Paths (resolved once)
service_prefix = "PerimeterControl"

# Dashboard and template directories (relative to integration dir)
DASHBOARD_WEB_DIR = INTEGRATION_DIR / "remote_services" / "dashboard_web"
TEMPLATES_DIR = INTEGRATION_DIR / "config" / "templates"
# Local supervisor source directory (single source of truth)
SUPERVISOR_SRC_DIR = INTEGRATION_DIR / "remote_services" / "supervisor"
# Unified service registry: all per-service config here
SERVICE_REGISTRY = {
    os.environ.get("PERIMETERCONTROL_NETWORK_ISOLATOR_SERVICE", "network_isolator"): {
        "unit": "perimetercontrol-network-isolator-dashboard",
        "template": "PerimeterControl-network-isolator-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/network_isolator_dashboard.py",
            "remote_services/dashboard_web/network_isolator_layouts.py",
            "remote_services/dashboard_web/network_isolator_callbacks.py",
            "system_services/web/data_sources.py",
        ],
        "script_files": [
            "remote_services/scripts/network_isolator/apply-rules.py",
            "remote_services/scripts/network_isolator/network-topology.py",
            "remote_services/scripts/network_isolator/topology_config.py"
        ],
        "pip_packages": ["bokeh", "tornado", "pyyaml", "pandas"],
        "deploy_api": None,
        "is_default_dashboard": True,  # This service is the default dashboard for generic/fallback logic
    },
    os.environ.get("PERIMETERCONTROL_PHOTO_BOOTH_SERVICE", "photo_booth"): {
        "unit": "perimetercontrol-photo-booth-dashboard",
        "template": "PerimeterControl-photo-booth-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/photo_booth_dashboard.py",
            "remote_services/dashboard_web/photo_booth_layouts.py",
            "remote_services/dashboard_web/photo_booth_callbacks.py",
        ],
        "script_files": [],
        "pip_packages": ["tornado"],
        "deploy_api": None,
    },
    os.environ.get("PERIMETERCONTROL_GPIO_CONTROL_SERVICE", "gpio_control"): {
        "unit": "perimetercontrol-gpio-dashboard",
        "template": "PerimeterControl-gpio-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/gpio_control_dashboard.py",
            "remote_services/dashboard_web/gpio_control_layouts.py",
            "remote_services/dashboard_web/gpio_control_callbacks.py",
        ],
        "script_files": [],
        "pip_packages": ["tornado"],
        # Use explicit placeholder for host so deployers can substitute the
        # actual node host when executing remote commands via SSH.
        # Replace `<host_ip>` with the node IP or hostname at runtime.
        "deploy_api": "http://<host_ip>:8080/api/v1/capabilities/gpio_control/deploy",
    },
    os.environ.get("PERIMETERCONTROL_BLE_GATT_REPEATER_SERVICE", "ble_gatt_repeater"): {
        "unit": "perimetercontrol-ble-dashboard",
        "template": "PerimeterControl-ble-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/ble_gatt_repeater_dashboard.py",
            "remote_services/dashboard_web/ble_gatt_repeater_layouts.py",
            "remote_services/dashboard_web/ble_gatt_repeater_callbacks.py",
        ],
        "script_files": [
            "remote_services/scripts/ble_gatt_repeater/ble-gatt-mirror.py",
            "remote_services/scripts/ble_gatt_repeater/ble-proxy-profiler.py",
            "remote_services/scripts/ble_gatt_repeater/ble-scanner-v2.py",
            "remote_services/scripts/ble_gatt_repeater/ble-scanner.py",
            "remote_services/scripts/ble_gatt_repeater/ble-sniffer.py"
        ],
        "pip_packages": ["tornado"],
        "deploy_api": None,
    },
    os.environ.get("PERIMETERCONTROL_ESL_AP_SERVICE", "esl_ap"): {
        "unit": "perimetercontrol-esl-dashboard",
        "template": "PerimeterControl-esl-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/esl_dashboard.py",
            "remote_services/dashboard_web/esl_layouts.py",
            "remote_services/dashboard_web/esl_callbacks.py",
        ],
        "script_files": [],
        "pip_packages": ["tornado"],
        "deploy_api": None,
    },
    os.environ.get("PERIMETERCONTROL_WILDLIFE_MONITOR_SERVICE", "wildlife_monitor"): {
        "unit": "perimetercontrol-wildlife-dashboard",
        "template": "PerimeterControl-wildlife-dashboard.service.template",
        "web_files": [
            "remote_services/dashboard_web/wildlife_dashboard.py",
            "remote_services/dashboard_web/wildlife_layouts.py",
            "remote_services/dashboard_web/wildlife_callbacks.py",
        ],
        "script_files": [],
        "pip_packages": ["tornado"],
        "deploy_api": None,
    },
}

# Supervisor deployment is handled as a special case in deployment logic and is NOT included as a service in SERVICE_REGISTRY.
# This avoids confusion and keeps SERVICE_REGISTRY focused on dashboard/capability services only.
# See deployer.py for supervisor deployment logic.

# Shared web files deployed to every Pi regardless of which services are selected.
# These are runtime dependencies imported by all dashboard entry-point scripts.
SHARED_WEB_FILES = [
    "remote_services/supervisor/data_manager.py",
    "remote_services/dashboard_web/dashboard_common.py",
    "remote_services/dashboard_web/static/css/pc-dashboard.css",
]

# List of all available service IDs (for Home Assistant integration compatibility)
AVAILABLE_SERVICES = list(SERVICE_REGISTRY.keys())

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER = "user"
CONF_SSH_KEY = "ssh_key"       # Private key content (stored in HA secrets)
CONF_SSH_KEY_PATH = "ssh_key_path"  # Alternative: path on HA host
CONF_SUPERVISOR_PORT = "supervisor_port"  # Supervisor API port
CONF_SERVICES = "services"     # List of enabled service IDs (legacy)

DEFAULT_SSH_PORT = 22
DEFAULT_API_PORT = 8080  # Supervisor API port
DEFAULT_USER = "pi"


# Paths (resolved once)


# Default config template paths
DEFAULT_CONF_TEMPLATE = 'config/templates/perimetercontrol_network_service.conf.yaml'
DEFAULT_FIREWALL_RULES_TEMPLATE = 'config/templates/firewall_rules.yaml'


# Explicit remote paths (hardcoded, not environment-derived)
remote_install_root = "/opt/PerimeterControl"
remote_state_root = "/mnt/PerimeterControl"
remote_log_root = "/var/log/PerimeterControl"
remote_temp_root = "/tmp"
remote_systemd_root = "/etc/systemd/system"
remote_web_dir = f"{remote_install_root}/web"
remote_scripts_dir = f"{remote_install_root}/scripts"
remote_supervisor_dir = f"{remote_install_root}/supervisor"
remote_state_dir = f"{remote_install_root}/state"
remote_venv_dir = f"{remote_install_root}/venv"
remote_conf_dir = f"{remote_state_root}/conf"
remote_services_dir = f"{remote_state_root}/conf/services"



def iter_services():
    """
    Yield (service_id, service_info) for all known services.
    
    Coordinator and all integration logic should be generic and treat all services equally.
    If a service requires special handling (e.g., default dashboard, health check, etc.),
    this MUST be indicated by a config flag in SERVICE_REGISTRY (e.g., 'is_default_dashboard').
    Hardcoding service IDs in logic is not allowed.
    """
    return SERVICE_REGISTRY.items()

# System dependency groups (maps apt group tag → actual packages)
APT_DEPENDENCY_GROUPS: dict[str, list[str]] = {
    "gstreamer": [
        "gstreamer1.0-tools",
        "gstreamer1.0-plugins-base",
        "gstreamer1.0-plugins-good",
    ],
}

# Helper functions for path management
def get_remote_path_config() -> dict[str, str]:
    """Get all configurable remote paths as a dictionary for templating, omitting None values."""
    return {k: v for k, v in {
        "INSTALL_ROOT": remote_install_root,
        "WEB_DIR": remote_web_dir,
        "SCRIPTS_DIR": remote_scripts_dir,
        "SUPERVISOR_DIR": remote_supervisor_dir,
        "STATE_DIR": remote_state_dir,
        "STATE_ROOT": remote_state_root,
        "CONF_DIR": remote_conf_dir,
        "SERVICES_DIR": remote_services_dir,
        "LOG_ROOT": remote_log_root,
        "TEMP_ROOT": remote_temp_root,
        "SYSTEMD_ROOT": remote_systemd_root,
        "VENV": remote_venv_dir,
        "SERVICE_PREFIX": service_prefix,
        "SUPERVISOR_SERVICE": "perimetercontrol-supervisor",
    }.items() if v is not None}


def get_remote_install_directories() -> list[str]:
    """Get list of all remote directories that need to be created during installation (on Pi)."""
    dirs = [
        remote_install_root,
        remote_web_dir,
        remote_scripts_dir,
        remote_supervisor_dir,
        remote_state_dir,
        remote_state_root,
        remote_conf_dir,
        remote_services_dir,
        remote_log_root,
    ]
    return [d for d in dirs if d is not None]

# Deploy phases
PHASE_PREFLIGHT = "preflight"
PHASE_UPLOAD = "upload"
PHASE_INSTALL = "install"
PHASE_SUPERVISOR = "supervisor"
PHASE_RESTART = "restart"
PHASE_VERIFY = "verify"
