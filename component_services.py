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
        
        # Add configuration from template files
        config_templates = {
            "ble_config.yaml": "config/templates/ble_config.yaml",
            "mqtt_config.yaml": "config/templates/mqtt_config.yaml", 
            "dashboard_config.yaml": "config/templates/ble_dashboard_config.yaml"
        }
        self.add_component(ConfigurationManager(config_templates, use_templates=True), 3)
        
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
        
        # Add configuration from template files
        config_templates = {
            "photo_booth_config.yaml": "config/templates/photo_booth_config.yaml",
            "dashboard_config.yaml": "config/templates/photo_booth_dashboard_config.yaml"
        }
        self.add_component(ConfigurationManager(config_templates, use_templates=True), 5)
        
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
        
        # Add configuration from template files
        config_templates = {
            "perimeterControl.conf.yaml": "config/templates/network_isolator.conf.yaml",
            "firewall_rules.yaml": "config/templates/firewall_rules.yaml"
        }
        self.add_component(ConfigurationManager(config_templates, use_templates=True), 5)


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
        
        # Add configuration from template files
        config_templates = {
            "wildlife_config.yaml": "config/templates/wildlife_config.yaml",
            "data_analysis.yaml": "config/templates/wildlife_data_analysis.yaml",
            "dashboard_config.yaml": "config/templates/wildlife_dashboard_config.yaml"
        }
        self.add_component(ConfigurationManager(config_templates, use_templates=True), 7)


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
        
        # Add configuration from template files
        config_templates = {
            "esl_config.yaml": "config/templates/esl_config.yaml",
            "layout_config.yaml": "config/templates/esl_layout_config.yaml",
            "dashboard_config.yaml": "config/templates/esl_dashboard_config.yaml"
        }
        self.add_component(ConfigurationManager(config_templates, use_templates=True), 5)


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