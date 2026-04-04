"""Component-based service implementations using the new service framework."""
from __future__ import annotations

from .service_framework import BaseService, ComponentConfig, component_registry
from .hardware_components import BluetoothInterface, CameraInterface, NetworkInterface, I2CSensorInterface
from .feature_components import (
    PythonDependencies, SystemDependencies, ConfigurationManager,
    DataLogging, MotionDetection, AlertSystem, BluetoothAdvertiser
)


class BleService(BaseService):
    """BLE GATT Repeater service using component composition."""
    
    def __init__(self):
        super().__init__("ble_gatt_repeater")
        
        # Add hardware interface
        self.add_component(BluetoothInterface(), 0)
        
        # Add Python dependencies
        self.add_component(PythonDependencies([
            "bleak", 
            "asyncio-mqtt", 
            "aiofiles",
            "bokeh",
            "tornado",
            "jinja2"
        ]), 1)
        
        # Add system dependencies
        self.add_component(SystemDependencies([
            "bluetooth", 
            "bluez", 
            "bluez-tools"
        ]), 2)
        
        # Add configuration management
        config_files = {
            "ble_config.yaml": """
# BLE GATT Repeater Configuration
scan_interval: 30
connection_timeout: 10
devices:
  - name: "Any Health Thermometer"
    service_uuid: "1809"
    characteristics:
      - "2a1c"  # Temperature Measurement
""",
            "mqtt_config.yaml": """
# MQTT Configuration for BLE
broker: localhost
port: 1883
topic_prefix: "ble"
""",
            "dashboard_config.yaml": """
# BLE GATT Repeater Dashboard Configuration
server:
  host: "0.0.0.0"
  port: 8091
  type: "bokeh"
features:
  device_scanner: true
  gatt_browser: true
  characteristic_monitor: true
  connection_status: true
data_refresh_interval: 5
"""
        }
        self.add_component(ConfigurationManager(config_files), 3)
        
        # Add data logging
        self.add_component(DataLogging(["sensor", "event"]), 4)


class PhotoBoothService(BaseService):
    """Photo Booth service using component composition."""
    
    def __init__(self):
        super().__init__("photo_booth")
        
        # Add hardware interfaces
        self.add_component(CameraInterface(), 0)
        
        # Add feature components
        self.add_component(MotionDetection(sensitivity=0.6), 1)
        self.add_component(AlertSystem(["webhook", "mqtt"]), 2)
        
        # Add dependencies
        self.add_component(SystemDependencies([
            "v4l-utils",
            "ffmpeg", 
            "python3-opencv"
        ]), 3)
        
        self.add_component(PythonDependencies([
            "opencv-python-headless",
            "pillow", 
            "numpy",
            "bokeh",
            "tornado"
        ]), 4)
        
        # Add configuration
        config_files = {
            "photo_booth_config.yaml": """
# Photo Booth Configuration
camera:
  device: 0
  resolution: [1920, 1080]
  fps: 30
motion:
  sensitivity: 0.6
  min_area: 500
storage:
  path: "/var/lib/photo_booth"
  max_photos: 1000
""",
            "dashboard_config.yaml": """
# Dashboard Configuration
server:
  host: "0.0.0.0"
  port: 8093
  type: "bokeh"
features:
  live_stream: true
  motion_detection: true
  manual_capture: true
"""
        }
        self.add_component(ConfigurationManager(config_files), 5)
        
        # Add data logging
        self.add_component(DataLogging(["event", "capture"]), 6)


class NetworkService(BaseService):
    """Network Isolator service using component composition."""
    
    def __init__(self):
        super().__init__("network_isolator")
        
        # Add hardware interface
        self.add_component(NetworkInterface(), 0)
        
        # Add dependencies
        self.add_component(SystemDependencies([
            "iptables",
            "iptables-persistent", 
            "netfilter-persistent",
            "tcpdump"
        ]), 1)
        
        self.add_component(PythonDependencies([
            "psutil",
            "netaddr",
            "scapy",
            "asyncio-mqtt"
        ]), 2)
        
        # Add features
        self.add_component(DataLogging(["network", "firewall"]), 3)
        self.add_component(AlertSystem(["webhook"]), 4)
        
        # Add configuration
        config_files = {
            "isolator.conf.yaml": """
# Network Isolator Configuration
interfaces:
  - name: eth0
    monitor: true
    firewall: true
  - name: wlan0
    monitor: true
    firewall: false
rules:
  default_policy: DROP
  allowed_ports: [22, 80, 443, 8080]
monitoring:
  interval: 60
  log_traffic: true
""",
            "firewall_rules.yaml": """
# Firewall Rules
chains:
  INPUT: DROP
  FORWARD: DROP
  OUTPUT: ACCEPT
rules:
  - action: ACCEPT
    source: 192.168.0.0/16
    ports: [22, 80, 443]
  - action: ACCEPT
    interface: lo
"""
        }
        self.add_component(ConfigurationManager(config_files), 5)


class WildlifeService(BaseService):
    """Wildlife Monitor service using component composition."""
    
    def __init__(self):
        super().__init__("wildlife_monitor")
        
        # Add hardware interfaces
        self.add_component(I2CSensorInterface(), 0)
        self.add_component(CameraInterface(), 1)
        
        # Add dependencies
        self.add_component(SystemDependencies([
            "i2c-tools",
            "python3-smbus2",
            "ffmpeg"
        ]), 2)
        
        self.add_component(PythonDependencies([
            "pandas",
            "numpy", 
            "scipy",
            "RPi.GPIO",
            "adafruit-circuitpython-bme280",
            "matplotlib",
            "bokeh",
            "tornado",
            "jinja2"
        ]), 3)
        
        # Add features
        self.add_component(DataLogging(["sensor", "wildlife", "environment"]), 4)
        self.add_component(MotionDetection(sensitivity=0.3), 5)  # More sensitive for wildlife
        self.add_component(AlertSystem(["email", "webhook"]), 6)
        
        # Add configuration
        config_files = {
            "wildlife_config.yaml": """
# Wildlife Monitor Configuration
sensors:
  - type: bme280
    address: 0x76
    metrics: [temperature, humidity, pressure]
  - type: motion_pir
    gpio_pin: 18
camera:
  trigger_on_motion: true
  record_duration: 30
  resolution: [1280, 720]
data:
  collection_interval: 300  # 5 minutes
  retention_days: 30
alerts:
  temperature_threshold: 35
  motion_cooldown: 600  # 10 minutes
""",
            "data_analysis.yaml": """
# Data Analysis Configuration
processing:
  enable_ml: false
  aggregation_interval: 3600  # 1 hour
visualization:
  charts: [temperature, humidity, motion_events]
  update_interval: 300
""",
            "dashboard_config.yaml": """
# Wildlife Monitor Dashboard Configuration  
server:
  host: "0.0.0.0"
  port: 8094
  type: "bokeh"
features:
  sensor_charts: true
  motion_timeline: true
  environmental_data: true
  wildlife_gallery: true
data_refresh_interval: 60
"""
        }
        self.add_component(ConfigurationManager(config_files), 7)


class EslService(BaseService):
    """ESL AP service using component composition."""
    
    def __init__(self):
        super().__init__("esl_ap")
        
        # Add hardware - ESL requires advertising, not scanning
        self.add_component(BluetoothAdvertiser(), 0)
        
        # Add dependencies
        self.add_component(SystemDependencies([
            "bluetooth",
            "bluez",
            "bluez-tools"
        ]), 1)
        
        self.add_component(PythonDependencies([
            "construct", 
            "cryptography",
            "bluepy",
            "asyncio-mqtt",
            "bokeh",
            "tornado",
            "jinja2"
        ]), 2)
        
        # Add features
        self.add_component(DataLogging(["esl", "advertising"]), 3)
        self.add_component(AlertSystem(["mqtt"]), 4)
        
        # Add configuration
        config_files = {
            "esl_config.yaml": """
# ESL AP Configuration
advertising:
  interval_ms: 1000
  tx_power: 0  # dBm
  company_id: 0x02E5  # Qualcomm
security:
  encryption_key: "default_key_change_me"
  auth_required: true
displays:
  max_concurrent: 50
  sync_interval: 3600
protocols:
  supported: ["esl_1.0", "esl_2.0"]
  default: "esl_2.0"
""",
            "layout_config.yaml": """
# ESL Layout Configuration
templates:
  - name: "price_tag"
    width: 296
    height: 128
    elements:
      - type: text
        position: [10, 10]
        font_size: 24
      - type: barcode
        position: [10, 60]
        format: "code128"
layouts:
  default: "price_tag"
""",
            "dashboard_config.yaml": """
# ESL AP Dashboard Configuration
server:
  host: "0.0.0.0"  
  port: 8092
  type: "bokeh"
features:
  display_management: true
  layout_editor: true
  advertising_status: true
  connected_displays: true
data_refresh_interval: 30
"""
        }
        self.add_component(ConfigurationManager(config_files), 5)


# Register all service types with the component registry
def register_service_components():
    """Register all component types for reuse."""
    from .service_framework import hardware_registry
    from .hardware_config import load_hardware_mappings
    
    # Hardware interfaces
    component_registry.register_component_type("bluetooth_interface", BluetoothInterface)
    component_registry.register_component_type("camera_interface", CameraInterface)
    component_registry.register_component_type("network_interface", NetworkInterface)
    component_registry.register_component_type("i2c_interface", I2CSensorInterface)
    
    # Feature components
    component_registry.register_component_type("python_dependencies", PythonDependencies)
    component_registry.register_component_type("system_dependencies", SystemDependencies)
    component_registry.register_component_type("config_manager", ConfigurationManager)
    component_registry.register_component_type("data_logging", DataLogging)
    component_registry.register_component_type("motion_detection", MotionDetection)
    component_registry.register_component_type("alert_system", AlertSystem)
    component_registry.register_component_type("bluetooth_advertiser", BluetoothAdvertiser)
    
    # Load and register hardware mappings from configuration
    hw_config = load_hardware_mappings()
    mappings = hw_config["mappings"]
    
    for hardware_type, (primary_service, alternatives) in mappings.items():
        # Register primary handler with priority
        hardware_registry.register_hardware_handler(hardware_type, primary_service, priority=True)
        
        # Register alternative handlers
        for alternative_service in alternatives:
            hardware_registry.register_hardware_handler(hardware_type, alternative_service, priority=False)


# Service factory for creating service instances
SERVICE_REGISTRY = {
    "ble_gatt_repeater": BleService,
    "photo_booth": PhotoBoothService,
    "network_isolator": NetworkService,
    "wildlife_monitor": WildlifeService,
    "esl_ap": EslService,
}


def create_service(service_id: str) -> BaseService:
    """Create a service instance by ID."""
    if service_id not in SERVICE_REGISTRY:
        raise ValueError(f"Unknown service: {service_id}")
    
    service_class = SERVICE_REGISTRY[service_id]
    return service_class()