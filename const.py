"""Constants for Perimeter Control integration."""
import os
from pathlib import Path

DOMAIN = "perimeter_control"
PLATFORMS: list[str] = ["sensor", "button", "binary_sensor"]

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER = "user"
CONF_SSH_KEY = "ssh_key"       # Private key content (stored in HA secrets)
CONF_SSH_KEY_PATH = "ssh_key_path"  # Alternative: path on HA host
CONF_SERVICES = "services"     # List of enabled service IDs (legacy)

DEFAULT_SSH_PORT = 22
DEFAULT_API_PORT = 8080
DEFAULT_USER = "pi"

# Legacy static service list - will be replaced by dynamic discovery
# TODO: Remove once all platforms use dynamic entity discovery
AVAILABLE_SERVICES = [
    "network_isolator",
    "photo_booth", 
    "wildlife_monitor",
    "ble_gatt_repeater",
    "esl_ap",
]

# System dependency groups (maps apt group tag → actual packages)
APT_DEPENDENCY_GROUPS: dict[str, list[str]] = {
    "gstreamer": [
        "gstreamer1.0-tools",
        "gstreamer1.0-plugins-base",
        "gstreamer1.0-plugins-good",
        "gstreamer1.0-plugins-bad",
        "gstreamer1.0-libav",
        "gstreamer1.0-alsa",
        "python3-gi",
        "python3-gi-cairo",
        "python3-gst-1.0",
        "gir1.2-gst-plugins-base-1.0",
    ],
    "i2c": [
        "i2c-tools",
        "python3-smbus2",
    ],
}

# Configurable remote paths (can be overridden via environment variables)
# Base paths
REMOTE_INSTALL_ROOT = os.getenv("PERIMETER_INSTALL_ROOT", "/opt/PerimeterControl")
REMOTE_STATE_ROOT = os.getenv("PERIMETER_STATE_ROOT", "/mnt/PerimeterControl")
REMOTE_LOG_ROOT = os.getenv("PERIMETER_LOG_ROOT", "/var/log/PerimeterControl")
REMOTE_TEMP_ROOT = os.getenv("PERIMETER_TEMP_ROOT", "/tmp")
REMOTE_SYSTEMD_ROOT = os.getenv("PERIMETER_SYSTEMD_ROOT", "/etc/systemd/system")

# Derived paths (built from base paths)
REMOTE_WEB_DIR = f"{REMOTE_INSTALL_ROOT}/web"
REMOTE_SCRIPTS_DIR = f"{REMOTE_INSTALL_ROOT}/scripts"
REMOTE_SUPERVISOR_DIR = f"{REMOTE_INSTALL_ROOT}/supervisor"
REMOTE_STATE_DIR = f"{REMOTE_INSTALL_ROOT}/state"
REMOTE_VENV = f"{REMOTE_INSTALL_ROOT}/venv"
REMOTE_CONF_DIR = f"{REMOTE_STATE_ROOT}/conf"
REMOTE_SERVICES_DIR = f"{REMOTE_STATE_ROOT}/conf/services"

# Configurable systemd services (can be overridden via environment variables)
SYSTEMD_SERVICE_PREFIX = os.getenv("PERIMETER_SERVICE_PREFIX", "PerimeterControl")
SYSTEMD_DASHBOARD = f"{SYSTEMD_SERVICE_PREFIX}-dashboard"
SYSTEMD_SUPERVISOR = f"{SYSTEMD_SERVICE_PREFIX}-supervisor"

# Helper functions for path management
def get_remote_path_config() -> dict[str, str]:
    """Get all configurable remote paths as a dictionary for templating."""
    return {
        "INSTALL_ROOT": REMOTE_INSTALL_ROOT,
        "STATE_ROOT": REMOTE_STATE_ROOT, 
        "LOG_ROOT": REMOTE_LOG_ROOT,
        "TEMP_ROOT": REMOTE_TEMP_ROOT,
        "SYSTEMD_ROOT": REMOTE_SYSTEMD_ROOT,
        "WEB_DIR": REMOTE_WEB_DIR,
        "SCRIPTS_DIR": REMOTE_SCRIPTS_DIR,
        "SUPERVISOR_DIR": REMOTE_SUPERVISOR_DIR,
        "STATE_DIR": REMOTE_STATE_DIR,
        "VENV": REMOTE_VENV,
        "CONF_DIR": REMOTE_CONF_DIR,
        "SERVICES_DIR": REMOTE_SERVICES_DIR,
        "SERVICE_PREFIX": SYSTEMD_SERVICE_PREFIX,
        "DASHBOARD_SERVICE": SYSTEMD_DASHBOARD,
        "SUPERVISOR_SERVICE": SYSTEMD_SUPERVISOR,
    }

def get_install_directories() -> list[str]:
    """Get list of all directories that need to be created during installation."""
    return [
        REMOTE_INSTALL_ROOT,
        REMOTE_WEB_DIR,
        REMOTE_SCRIPTS_DIR,
        REMOTE_SUPERVISOR_DIR,
        REMOTE_STATE_DIR,
        REMOTE_STATE_ROOT,
        REMOTE_CONF_DIR,
        REMOTE_SERVICES_DIR,
        REMOTE_LOG_ROOT,
    ]

# Deploy phases
PHASE_PREFLIGHT = "preflight"
PHASE_UPLOAD = "upload"
PHASE_INSTALL = "install"
PHASE_SUPERVISOR = "supervisor"
PHASE_RESTART = "restart"
PHASE_VERIFY = "verify"
