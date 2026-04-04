"""Hardware Interface Components - Automatic entity generation for detected hardware."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from .service_framework import HardwareInterface, ResourceRequirement, ComponentConfig
from .ssh_client import SshClient


class BluetoothInterface(HardwareInterface):
    """Bluetooth hardware management with automatic BLE device entity creation."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        super().__init__("bluetooth_interface", config)
        self._conflicts.add("bluetooth_advertiser")  # Can't advertise and scan simultaneously
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.2, memory_mb=64, disk_mb=20)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if Bluetooth hardware is available."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping Bluetooth check")
                return True  # Allow deployment to proceed
            
            result = await ssh_client.async_run("bluetoothctl show 2>/dev/null | grep -q 'Controller' && echo 'available' || echo 'unavailable'")
            has_bluetooth = result.strip() == "available"
            if not has_bluetooth:
                self.logger.warning("Bluetooth controller not detected, deployment may install required packages")
            return True  # Always return True, let deployment handle hardware detection
        except Exception as exc:
            self.logger.warning(f"Bluetooth validation failed: {exc}")
            return True  # Allow deployment to proceed
    
    async def detect_hardware(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Detect available BLE devices and controllers."""
        devices = []
        try:
            # Get controller info
            result = await ssh_client.async_run("bluetoothctl show 2>/dev/null")
            if "Controller" in result:
                controller_lines = result.split('\n')
                controller_addr = None
                for line in controller_lines:
                    if "Controller" in line:
                        controller_addr = line.split()[-1]
                        break
                
                if controller_addr:
                    devices.append({
                        "type": "bluetooth_controller",
                        "address": controller_addr,
                        "name": "Bluetooth Controller",
                        "capabilities": ["scan", "connect"]
                    })
            
            # Scan for nearby devices (limited scan to avoid long delays)
            scan_result = await ssh_client.async_run("timeout 10 bluetoothctl scan on && sleep 5 && bluetoothctl devices 2>/dev/null || true")
            for line in scan_result.split('\n'):
                if line.startswith("Device "):
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        address = parts[1]
                        name = parts[2] if len(parts) > 2 else f"BLE Device {address}"
                        devices.append({
                            "type": "ble_device",
                            "address": address,
                            "name": name,
                            "capabilities": ["connect", "monitor"]
                        })
        
        except Exception as exc:
            self.logger.warning(f"BLE device detection failed: {exc}")
        
        return devices
    
    async def generate_entities(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate HA entities for BLE devices."""
        entities = []
        
        for device in devices:
            device_type = device.get("type")
            address = device.get("address", "unknown")
            name = device.get("name", "Unknown Device")
            
            if device_type == "ble_device":
                # Create connectivity sensor
                entities.append({
                    "id": f"ble:{address.replace(':', '_').lower()}:connected",
                    "type": "binary_sensor",
                    "name": f"{name} Connected",
                    "device_class": "connectivity",
                    "hardware_type": "bluetooth",
                    "template_params": {"device_address": address},
                })
                
                # Create signal strength sensor
                entities.append({
                    "id": f"ble:{address.replace(':', '_').lower()}:rssi",
                    "type": "sensor",
                    "name": f"{name} Signal Strength",
                    "device_class": "signal_strength",
                    "unit_of_measurement": "dBm",
                    "hardware_type": "bluetooth",
                    "template_params": {"device_address": address},
                })
        
        return entities
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy Bluetooth interface components."""
        try:
            # Install required packages
            packages = ["bluetooth", "bluez", "bluez-tools", "python3-bluetooth"]
            install_cmd = f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
            await ssh_client.async_run(install_cmd)
            
            # Enable Bluetooth service
            await ssh_client.async_run("sudo systemctl enable bluetooth")
            await ssh_client.async_run("sudo systemctl start bluetooth")
            
            # Install Python BLE packages
            pip_packages = ["bleak", "asyncio-mqtt"]
            pip_cmd = f"python3 -m pip install {' '.join(pip_packages)}"
            await ssh_client.async_run(pip_cmd)
            
            return True
        except Exception as exc:
            self.logger.error(f"Bluetooth deployment failed: {exc}")
            return False


class CameraInterface(HardwareInterface):
    """Camera hardware with automatic camera entity and controls."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        super().__init__("camera_interface", config)
        self._dependencies.add("system_dependencies")
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.4, memory_mb=256, disk_mb=200)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if camera hardware is available."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping camera check")
                return True  # Allow deployment to proceed
            
            # Check for video devices
            result = await ssh_client.async_run("ls /dev/video* 2>/dev/null | wc -l")
            has_camera = int(result.strip()) > 0
            if not has_camera:
                self.logger.warning("No camera devices detected, deployment may proceed without camera")
            return True  # Always return True, let deployment handle hardware detection
        except Exception as e:
            self.logger.warning(f"Camera validation failed: {e}")
            return True  # Allow deployment to proceed
    
    async def detect_hardware(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Detect available cameras."""
        devices = []
        try:
            result = await ssh_client.async_run("ls /dev/video* 2>/dev/null || true")
            for line in result.split('\n'):
                if line.startswith('/dev/video'):
                    device_num = line.replace('/dev/video', '')
                    devices.append({
                        "type": "camera",
                        "device": line,
                        "device_num": device_num,
                        "name": f"Camera {device_num}",
                        "capabilities": ["stream", "capture", "motion_detection"]
                    })
        except Exception as exc:
            self.logger.warning(f"Camera detection failed: {exc}")
        
        return devices
    
    async def generate_entities(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate HA entities for cameras."""
        entities = []
        
        for device in devices:
            device_num = device.get("device_num", "0")
            name = device.get("name", f"Camera {device_num}")
            
            # Camera entity
            entities.append({
                "id": f"camera:{device_num}:stream",
                "type": "camera", 
                "name": name,
                "hardware_type": "camera",
                "template_params": {"device_num": device_num},
            })
            
            # Motion detection sensor
            entities.append({
                "id": f"camera:{device_num}:motion",
                "type": "binary_sensor",
                "name": f"{name} Motion",
                "device_class": "motion",
                "hardware_type": "camera", 
                "template_params": {"device_num": device_num},
            })
            
            # Capture button
            entities.append({
                "id": f"camera:{device_num}:capture",
                "type": "button", 
                "name": f"{name} Capture",
                "device_class": "restart",
                "hardware_type": "camera",
                "template_params": {"device_num": device_num},
            })
        
        return entities
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy camera interface components."""
        try:
            # Install camera packages
            packages = ["v4l-utils", "ffmpeg", "python3-opencv"]
            install_cmd = f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
            await ssh_client.async_run(install_cmd)
            
            # Install Python camera packages
            pip_packages = ["opencv-python-headless", "pillow", "numpy"]
            pip_cmd = f"python3 -m pip install {' '.join(pip_packages)}"
            await ssh_client.async_run(pip_cmd)
            
            # Enable camera interface
            await ssh_client.async_run("sudo raspi-config nonint do_camera 0")
            
            return True
        except Exception as exc:
            self.logger.error(f"Camera deployment failed: {exc}")
            return False


class NetworkInterface(HardwareInterface):
    """Network hardware with automatic connectivity and stats entities."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        super().__init__("network_interface", config)
    
    @property  
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.2, memory_mb=96, disk_mb=30)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Network interface is always available."""
        return True
    
    async def detect_hardware(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Detect available network interfaces."""
        devices = []
        try:
            result = await ssh_client.async_run("ip link show | grep '^[0-9]' | awk -F': ' '{print $2}'")
            for interface in result.split('\n'):
                if interface and interface != 'lo':
                    devices.append({
                        "type": "network_interface",
                        "interface": interface,
                        "name": f"Network {interface}",
                        "capabilities": ["monitoring", "firewall", "bandwidth"]
                    })
        except Exception as exc:
            self.logger.warning(f"Network interface detection failed: {exc}")
        
        return devices
    
    async def generate_entities(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate HA entities for network interfaces."""
        entities = []
        
        for device in devices:
            interface = device.get("interface", "eth0")
            name = device.get("name", f"Network {interface}")
            
            # Connectivity sensor
            entities.append({
                "id": f"network:{interface}:connected",
                "type": "binary_sensor",
                "name": f"{name} Connected",
                "device_class": "connectivity",
                "hardware_type": "network",
                "template_params": {"interface": interface},
            })
            
            # Bandwidth sensors
            entities.append({
                "id": f"network:{interface}:rx_bytes",
                "type": "sensor",
                "name": f"{name} Received",
                "device_class": "data_size",
                "unit_of_measurement": "bytes",
                "hardware_type": "network",
                "template_params": {"interface": interface},
            })
            
            entities.append({
                "id": f"network:{interface}:tx_bytes",
                "type": "sensor", 
                "name": f"{name} Transmitted",
                "device_class": "data_size",
                "unit_of_measurement": "bytes",
                "hardware_type": "network",
                "template_params": {"interface": interface},
            })
        
        return entities
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy network interface components.""" 
        try:
            # Install network packages
            packages = ["iptables", "iptables-persistent", "netfilter-persistent"]
            install_cmd = f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
            await ssh_client.async_run(install_cmd)
            
            # Install Python network packages
            pip_packages = ["psutil", "netaddr", "scapy"]
            pip_cmd = f"python3 -m pip install {' '.join(pip_packages)}"
            await ssh_client.async_run(pip_cmd)
            
            return True
        except Exception as exc:
            self.logger.error(f"Network deployment failed: {exc}")
            return False


class I2CSensorInterface(HardwareInterface):
    """I2C sensors with automatic sensor entity creation based on device IDs."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        super().__init__("i2c_interface", config)
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.1, memory_mb=32, disk_mb=10)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if I2C interface is enabled."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping I2C check")
                return True  # Allow deployment to proceed
            
            result = await ssh_client.async_run("ls /dev/i2c-* 2>/dev/null | wc -l")
            has_i2c = int(result.strip()) > 0
            if not has_i2c:
                self.logger.warning("No I2C devices detected, deployment may proceed without I2C sensors")
            return True  # Always return True, let deployment handle hardware detection
        except Exception as e:
            self.logger.warning(f"I2C validation failed: {e}")
            return True  # Allow deployment to proceed
    
    async def detect_hardware(self, ssh_client: SshClient) -> List[Dict[str, Any]]:
        """Detect I2C sensors."""
        devices = []
        try:
            # Scan I2C buses
            result = await ssh_client.async_run("i2cdetect -y 1 2>/dev/null | grep -v '^     ' | tail -n +2 || true")
            addresses = []
            for line in result.split('\n'):
                for addr in line.split():
                    if addr and addr != '--' and len(addr) == 2:
                        addresses.append(addr)
            
            for addr in addresses:
                devices.append({
                    "type": "i2c_sensor",
                    "address": f"0x{addr}",
                    "name": f"I2C Sensor {addr}",
                    "capabilities": ["temperature", "humidity", "pressure"]  # Common sensor types
                })
        
        except Exception as exc:
            self.logger.warning(f"I2C sensor detection failed: {exc}")
        
        return devices
    
    async def generate_entities(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate HA entities for I2C sensors."""
        entities = []
        
        for device in devices:
            address = device.get("address", "0x00")
            name = device.get("name", f"I2C Sensor {address}")
            addr_clean = address.replace('0x', '').lower()
            
            # Generic sensor entity (type determined by actual sensor)
            entities.append({
                "id": f"i2c:{addr_clean}:value",
                "type": "sensor",
                "name": f"{name} Value",
                "hardware_type": "i2c_sensor",
                "template_params": {"i2c_address": address},
            })
            
            # Connectivity sensor
            entities.append({
                "id": f"i2c:{addr_clean}:connected",
                "type": "binary_sensor",
                "name": f"{name} Connected", 
                "device_class": "connectivity",
                "hardware_type": "i2c_sensor",
                "template_params": {"i2c_address": address},
            })
        
        return entities
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy I2C interface components."""
        try:
            # Install I2C packages
            packages = ["i2c-tools", "python3-smbus2"]
            install_cmd = f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
            await ssh_client.async_run(install_cmd)
            
            # Enable I2C interface
            await ssh_client.async_run("sudo raspi-config nonint do_i2c 0")
            
            # Install Python I2C packages
            pip_packages = ["smbus2", "adafruit-circuitpython-bme280"]
            pip_cmd = f"python3 -m pip install {' '.join(pip_packages)}"
            await ssh_client.async_run(pip_cmd)
            
            return True
        except Exception as exc:
            self.logger.error(f"I2C deployment failed: {exc}")
            return False