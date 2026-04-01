"""Constants for Perimeter Control integration."""

DOMAIN = "perimeter_control"
PLATFORMS: list[str] = ["sensor", "button"]

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER = "user"
CONF_SSH_KEY = "ssh_key"       # private key content (stored in HA secrets)
CONF_SSH_KEY_PATH = "ssh_key_path"  # alternative: path on HA host
CONF_SERVICES = "services"     # list of enabled service IDs

DEFAULT_SSH_PORT = 22
DEFAULT_API_PORT = 8080
DEFAULT_USER = "pi"

# Known service IDs (must match config/services/*.service.yaml metadata.id)
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

# Remote install paths
REMOTE_INSTALL_ROOT = "/opt/isolator"
REMOTE_WEB_DIR = "/opt/isolator/web"
REMOTE_SCRIPTS_DIR = "/opt/isolator/scripts"
REMOTE_SUPERVISOR_DIR = "/opt/isolator/supervisor"
REMOTE_CONF_DIR = "/mnt/isolator/conf"
REMOTE_SERVICES_DIR = "/mnt/isolator/conf/services"
REMOTE_VENV = "/opt/isolator/venv"

# Systemd services
SYSTEMD_DASHBOARD = "isolator-dashboard"
SYSTEMD_SUPERVISOR = "isolator-supervisor"

# Deploy phases
PHASE_PREFLIGHT = "preflight"
PHASE_UPLOAD = "upload"
PHASE_INSTALL = "install"
PHASE_SUPERVISOR = "supervisor"
PHASE_RESTART = "restart"
PHASE_VERIFY = "verify"
