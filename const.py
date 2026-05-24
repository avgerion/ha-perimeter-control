import os

DOMAIN = "perimeter_control"
PLATFORMS = [
    "sensor",
    "switch",
    "binary_sensor",
    "button",
    "camera",
    "light",
]
"""Constants for Perimeter Control integration."""


def _env(key, default):
    return os.environ.get(key, default)

# Paths (resolved once)
install_root = _env("PERIMETER_INSTALL_ROOT", "/opt/PerimeterControl")
state_root = _env("PERIMETER_STATE_ROOT", "/mnt/PerimeterControl")
log_root = _env("PERIMETER_LOG_ROOT", "/var/log/PerimeterControl")
temp_root = _env("PERIMETER_TEMP_ROOT", "/tmp")
systemd_root = _env("PERIMETER_SYSTEMD_ROOT", "/etc/systemd/system")

install_root = _env("PERIMETER_INSTALL_ROOT", "/opt/PerimeterControl")  # Local (controller/HA) paths
state_root = _env("PERIMETER_STATE_ROOT", "/mnt/PerimeterControl") 
log_root = _env("PERIMETER_LOG_ROOT", "/var/log/PerimeterControl") 
temp_root = _env("PERIMETER_TEMP_ROOT", "/tmp") 
systemd_root = _env("PERIMETER_SYSTEMD_ROOT", "/etc/systemd/system") 
conf_dir = f"{state_root}/conf"
services_dir = f"{state_root}/conf/services"

service_prefix = _env("PERIMETER_SERVICE_PREFIX", "PerimeterControl")

remote_install_root = _env("PERIMETER_REMOTE_INSTALL_ROOT", "/opt/PerimeterControl")
remote_state_root = _env("PERIMETER_REMOTE_STATE_ROOT", "/mnt/PerimeterControl")
remote_log_root = _env("PERIMETER_REMOTE_LOG_ROOT", "/var/log/PerimeterControl")
remote_temp_root = _env("PERIMETER_REMOTE_TEMP_ROOT", "/tmp")
remote_systemd_root = _env("PERIMETER_REMOTE_SYSTEMD_ROOT", "/etc/systemd/system")
remote_web_dir = f"{remote_install_root}/web"
remote_scripts_dir = f"{remote_install_root}/scripts"
remote_supervisor_dir = f"{remote_install_root}/supervisor"
remote_state_dir = f"{remote_install_root}/state"
remote_venv_dir = f"{remote_install_root}/venv"
remote_conf_dir = f"{remote_state_root}/conf"
remote_services_dir = f"{remote_state_root}/conf/services"

remote_install_root = _env("PERIMETER_REMOTE_INSTALL_ROOT", "/opt/PerimeterControl")
remote_state_root = _env("PERIMETER_REMOTE_STATE_ROOT", "/mnt/PerimeterControl")
remote_log_root = _env("PERIMETER_REMOTE_LOG_ROOT", "/var/log/PerimeterControl")
remote_temp_root = _env("PERIMETER_REMOTE_TEMP_ROOT", "/tmp")
remote_systemd_root = _env("PERIMETER_REMOTE_SYSTEMD_ROOT", "/etc/systemd/system")
remote_web_dir = f"{remote_install_root}/web"
remote_scripts_dir = f"{remote_install_root}/scripts"
remote_supervisor_dir = f"{remote_install_root}/supervisor"
remote_state_dir = f"{remote_install_root}/state"
remote_venv_dir = f"{remote_install_root}/venv"
remote_conf_dir = f"{remote_state_root}/conf"
remote_services_dir = f"{remote_state_root}/conf/services"

# Unified service registry: all per-service config here
SERVICE_REGISTRY = {
    _env("PERIMETERCONTROL_NETWORK_ISOLATOR_SERVICE", "network_isolator"): {
        "unit": f"{service_prefix}-dashboard",
        "port": int(_env("PERIMETERCONTROL_DASHBOARD_PORT", 5006) or 5006),
        "template": "PerimeterControl-dashboard.service.template",
        "web_files": ["dashboard.py", "layouts.py", "callbacks.py", "data_sources.py"],
        "pip_packages": ["bokeh", "tornado", "pyyaml", "pandas"],
        "config_template": None,
        "config_target": None,
        "deploy_api": None,
    },
    _env("PERIMETERCONTROL_PHOTO_BOOTH_SERVICE", "photo_booth"): {
        "unit": "PerimeterControl-photo-booth-dashboard",
        "port": 8093,
        "template": "PerimeterControl-photo-booth-dashboard.service.template",
        "web_files": ["photo_booth_dashboard.py"],
        "pip_packages": ["tornado"],
        "config_template": "config/templates/photo_booth_config.yaml",
        "config_target": "photo-booth.yaml",
        "deploy_api": None,
    },
    _env("PERIMETERCONTROL_GPIO_CONTROL_SERVICE", "gpio_control"): {
        "unit": "PerimeterControl-gpio-dashboard",
        "port": 8095,
        "template": "PerimeterControl-gpio-dashboard.service.template",
        "web_files": ["gpio_control_dashboard.py"],
        "pip_packages": ["tornado"],
        "config_template": "config/templates/gpio_control_config.yaml",
        "config_target": "gpio-control.yaml",
        "deploy_api": "http://127.0.0.1:8080/api/v1/capabilities/gpio_control/deploy",
    },
    _env("PERIMETERCONTROL_BLE_GATT_REPEATER_SERVICE", "ble_gatt_repeater"): {
        "unit": "PerimeterControl-ble-dashboard",
        "port": 8091,
        "template": "PerimeterControl-ble-dashboard.service.template",
        "web_files": ["ble_gatt_dashboard.py"],
        "pip_packages": ["tornado"],
        "config_template": None,
        "config_target": None,
        "deploy_api": None,
    },
    _env("PERIMETERCONTROL_ESL_AP_SERVICE", "esl_ap"): {
        "unit": "PerimeterControl-esl-dashboard",
        "port": 8092,
        "template": "PerimeterControl-esl-dashboard.service.template",
        "web_files": ["esl_ap_dashboard.py"],
        "pip_packages": ["tornado"],
        "config_template": None,
        "config_target": None,
        "deploy_api": None,
    },
    _env("PERIMETERCONTROL_WILDLIFE_MONITOR_SERVICE", "wildlife_monitor"): {
        "unit": "PerimeterControl-wildlife-dashboard",
        "port": 8094,
        "template": "PerimeterControl-wildlife-dashboard.service.template",
        "web_files": ["wildlife_monitor_dashboard.py"],
        "pip_packages": ["tornado"],
        "config_template": None,
        "config_target": None,
        "deploy_api": None,
    },
}

def iter_services():
    """Yield (service_id, service_info) for all known services."""
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
    }.items() if v is not None}

def get_local_install_directories() -> list[str]:
    """Get list of all local directories that need to be created during installation (controller/HA)."""
    # Only use defined variables, filter out None
    dirs = [
        install_root,
        state_root,
        conf_dir,
        services_dir,
        log_root,
        temp_root,
        systemd_root,
    ]
    return [d for d in dirs if d is not None]

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
