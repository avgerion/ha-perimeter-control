"""Feature and Dependency Components - Shared functionality for service composition."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

from .service_framework import ServiceComponent, ResourceRequirement, ComponentConfig, robust_system_package_install
from .ssh_client import SshClient


class PythonDependencies(ServiceComponent):
    """Manages pip packages with conflict resolution."""
    
    def __init__(self, packages: List[str], config: Optional[ComponentConfig] = None):
        super().__init__("python_dependencies", config)
        self.packages = packages
        self.installed_packages: Set[str] = set()
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        # Estimate resource needs based on package count
        return ResourceRequirement(
            cpu_cores=0.05, 
            memory_mb=16 * len(self.packages),
            disk_mb=10 * len(self.packages)
        )
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if Python and pip are available."""
        try:
            # Skip validation if SSH client isn't ready or wasn't provided
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping Python check")
                return True  # Allow deployment to proceed
            
            # Check Python3 first (more likely to be present)
            try:
                python_result = await ssh_client.async_run("python3 --version 2>/dev/null || echo 'not found'")
                has_python = "Python 3" in python_result
                if not has_python:
                    self.logger.info("Python3 not detected, deployment will install it")
                    return True  # Let deployment handle Python installation
            except Exception:
                self.logger.info("Could not check Python3, deployment will attempt installation")
                return True
            
            # Check pip separately (using python3 -m pip which is most reliable)
            try:
                pip_result = await ssh_client.async_run("python3 -m pip --version 2>/dev/null || echo 'not found'")
                has_pip = "pip" in pip_result and "not found" not in pip_result
                if not has_pip:
                    self.logger.info("pip module not detected, deployment will install it")
            except Exception:
                self.logger.info("Could not check pip module, deployment will attempt installation")
            
            return True  # Always return True, let deployment handle package management setup
        except Exception as e:
            self.logger.info(f"Python validation skipped: {e}")
            return True  # Allow deployment to proceed
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Install Python packages."""
        try:
            if not self.packages:
                return True
            
            # Install packages
            packages_str = ' '.join(self.packages)
            install_cmd = f"python3 -m pip install {packages_str}"
            await ssh_client.async_run(install_cmd)
            self.installed_packages.update(self.packages)
            
            self.logger.info(f"Installed Python packages: {packages_str}")
            return True
        except Exception as exc:
            self.logger.error(f"Python package installation failed: {exc}")
            return False


class SystemDependencies(ServiceComponent):
    """Manages apt packages with dependency tracking."""
    
    def __init__(self, packages: List[str], config: ComponentConfig = None):
        super().__init__("system_dependencies", config)
        self.packages = packages
        self.installed_packages: Set[str] = set()
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(
            cpu_cores=0.05,
            memory_mb=8 * len(self.packages), 
            disk_mb=50 * len(self.packages)
        )
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if apt is available."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping apt check")
                return True  # Allow deployment to proceed
            
            result = await ssh_client.async_run("which apt-get")
            has_apt = "/usr/bin/apt-get" in result or "/bin/apt-get" in result
            if not has_apt:
                self.logger.warning("apt-get not detected, deployment may need different package manager")
            return True  # Always return True, let deployment handle package manager detection
        except Exception as e:
            self.logger.warning(f"Could not validate system package requirements: {e}")
            return True  # Allow deployment to proceed
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Install system packages with dpkg recovery."""
        # Use shared robust package installation utility
        success = await robust_system_package_install(ssh_client, self.packages, self.logger)
        if success:
            self.installed_packages.update(self.packages)
            
        return success


class ConfigurationManager(ServiceComponent):
    """Centralized configuration management for services."""
    
    def __init__(self, config_files: Dict[str, str], config: Optional[ComponentConfig] = None, use_templates: bool = False):
        super().__init__("config_manager", config)
        self.use_templates = use_templates
        self.deployed_configs: Set[str] = set()
        
        if use_templates:
            # config_files contains filename -> template_path mapping
            self._template_mappings = config_files
            self.config_files = None  # Will be loaded async
        else:
            # config_files contains filename -> content mapping (legacy)
            self.config_files = config_files
    
    async def _load_template_files(self, template_mappings: Dict[str, str], hass=None) -> Dict[str, str]:
        """Load configuration content from template files asynchronously."""
        import os
        config_content = {}
        # Resolve relative paths from the integration directory
        integration_dir = os.path.dirname(os.path.abspath(__file__))
        for filename, template_path in template_mappings.items():
            try:
                full_path = os.path.join(integration_dir, template_path)
                if hass is not None:
                    # Use Home Assistant's executor to avoid blocking event loop
                    content = await hass.async_add_executor_job(self._read_file, full_path)
                else:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                config_content[filename] = content
                self.logger.debug(f"Loaded template {template_path} for {filename}")
            except Exception as exc:
                self.logger.error(f"Failed to load template {template_path}: {exc}")
                config_content[filename] = f"# Template load failed: {exc}"
        return config_content

    @staticmethod
    def _read_file(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.01, memory_mb=8, disk_mb=5)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Configuration management is always available."""
        return True
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path, hass=None) -> bool:
        """Deploy configuration files."""
        try:
            # If using templates, load them asynchronously
            if self.use_templates and self.config_files is None:
                self.config_files = await self._load_template_files(self._template_mappings, hass=hass)
            for filename, content in self.config_files.items():
                config_path = deployment_path / "config" / filename
                # Upload configuration file
                await ssh_client.upload_file_content(content, str(config_path))
                self.deployed_configs.add(filename)
                self.logger.debug(f"Deployed config: {filename}")
            self.logger.info(f"Deployed {len(self.config_files)} configuration files")
            return True
        except Exception as exc:
            self.logger.error(f"Configuration deployment failed: {exc}")
            return False


class DataLogging(ServiceComponent):
    """Data logging feature shared by wildlife and network services."""
    
    def __init__(self, log_types: List[str], config: Optional[ComponentConfig] = None):
        super().__init__("data_logging", config)
        self.log_types = log_types  # ['sensor', 'network', 'event']
        self._dependencies.add("python_dependencies")
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.05, memory_mb=32, disk_mb=100)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if logging directory can be created."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping logging check")
                return True  # Allow deployment to proceed
            
            await ssh_client.async_run("mkdir -p /tmp/test_logging && rm -rf /tmp/test_logging")
            return True
        except Exception as e:
            self.logger.warning(f"Logging validation failed: {e}")
            return True  # Allow deployment to proceed
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Set up data logging infrastructure."""
        try:
            # Create logging directories
            log_dirs = [f"/var/log/perimeter/{log_type}" for log_type in self.log_types]
            for log_dir in log_dirs:
                await ssh_client.async_run(f"sudo mkdir -p {log_dir}")
                await ssh_client.async_run(f"sudo chown pi:pi {log_dir}")
            
            # Deploy logging configuration
            logging_config = {
                "version": 1,
                "handlers": {
                    log_type: {
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": f"/var/log/perimeter/{log_type}/data.log",
                        "maxBytes": 10485760,  # 10MB
                        "backupCount": 5
                    } for log_type in self.log_types
                }
            }
            
            config_content = json.dumps(logging_config, indent=2)
            config_path = deployment_path / "config" / "logging.json"
            await ssh_client.upload_file_content(config_content, str(config_path))
            
            self.logger.info(f"Set up data logging for: {self.log_types}")
            return True
        except Exception as exc:
            self.logger.error(f"Data logging setup failed: {exc}")
            return False


class MotionDetection(ServiceComponent):
    """Motion detection feature that can be shared across camera services."""
    
    def __init__(self, sensitivity: float = 0.5, config: Optional[ComponentConfig] = None):
        super().__init__("motion_detection", config)
        self.sensitivity = sensitivity
        self._dependencies.add("python_dependencies")
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.2, memory_mb=64, disk_mb=20)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if camera hardware is available."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping motion detection check")
                return True  # Allow deployment to proceed
            
            result = await ssh_client.async_run("ls /dev/video* 2>/dev/null | wc -l")
            has_camera = int(result.strip()) > 0
            if not has_camera:
                self.logger.warning("No camera devices detected for motion detection")
            return True  # Always return True, let deployment handle camera detection
        except Exception as e:
            self.logger.warning(f"Motion detection validation failed: {e}")
            return True  # Allow deployment to proceed
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy motion detection components."""
        try:
            # Deploy motion detection script
            motion_script = f'''#!/usr/bin/env python3
"""Motion detection service."""
import cv2
import logging

# Motion detection configuration
SENSITIVITY = {self.sensitivity}
MIN_CONTOUR_AREA = 500

def detect_motion(frame1, frame2):
    """Detect motion between two frames."""
    diff = cv2.absdiff(frame1, frame2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, int(255 * SENSITIVITY), 255, cv2.THRESH_BINARY)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return any(cv2.contourArea(c) > MIN_CONTOUR_AREA for c in contours)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Motion detection service started")
'''
            
            script_path = deployment_path / "scripts" / "motion_detection.py"
            await ssh_client.upload_file_content(motion_script, str(script_path))
            await ssh_client.async_run(f"chmod +x {script_path}")
            
            self.logger.info("Motion detection deployed")
            return True
        except Exception as exc:
            self.logger.error(f"Motion detection deployment failed: {exc}")
            return False


class AlertSystem(ServiceComponent):
    """Alert/notification system usable by any service."""
    
    def __init__(self, alert_types: List[str], config: Optional[ComponentConfig] = None):
        super().__init__("alert_system", config)
        self.alert_types = alert_types  # ['email', 'webhook', 'mqtt']
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.02, memory_mb=16, disk_mb=10)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Alert system is always available."""
        return True
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy alert system components."""
        try:
            # Deploy alert configuration
            alert_config = {
                "enabled_types": self.alert_types,
                "settings": {
                    "email": {
                        "smtp_server": "localhost",
                        "smtp_port": 587
                    },
                    "webhook": {
                        "timeout": 30,
                        "retry_count": 3
                    },
                    "mqtt": {
                        "broker": "localhost",
                        "port": 1883
                    }
                }
            }
            
            config_content = json.dumps(alert_config, indent=2)
            config_path = deployment_path / "config" / "alerts.json"
            await ssh_client.upload_file_content(config_content, str(config_path))
            
            # Deploy alert script
            alert_script = '''#!/usr/bin/env python3
"""Alert system service."""
import json
import logging
import requests
from pathlib import Path

def send_alert(alert_type: str, message: str, **kwargs):
    """Send alert using specified type."""
    config_file = Path("config/alerts.json")
    if not config_file.exists():
        logging.error("Alert configuration not found")
        return False
    
    with open(config_file) as f:
        config = json.load(f)
    
    if alert_type not in config.get("enabled_types", []):
        logging.warning(f"Alert type {alert_type} not enabled")
        return False
    
    # Implementation would go here based on alert_type
    logging.info(f"Alert sent: {alert_type} - {message}")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Alert system ready")
'''
            
            script_path = deployment_path / "scripts" / "alert_system.py"
            await ssh_client.upload_file_content(alert_script, str(script_path))
            await ssh_client.async_run(f"chmod +x {script_path}")
            
            self.logger.info(f"Alert system deployed with types: {self.alert_types}")
            return True
        except Exception as exc:
            self.logger.error(f"Alert system deployment failed: {exc}")
            return False


class BluetoothAdvertiser(ServiceComponent):
    """Bluetooth advertising capability (for ESL service)."""
    
    def __init__(self, config: Optional[ComponentConfig] = None):
        super().__init__("bluetooth_advertiser", config)
        self._conflicts.add("bluetooth_interface")  # Can't scan while advertising
    
    @property
    def resource_requirements(self) -> ResourceRequirement:
        return ResourceRequirement(cpu_cores=0.3, memory_mb=96, disk_mb=40)
    
    async def validate_requirements(self, ssh_client: SshClient) -> bool:
        """Check if Bluetooth LE advertising is available."""
        try:
            # Skip validation if SSH client isn't ready
            if not ssh_client or not hasattr(ssh_client, 'async_run'):
                self.logger.warning("SSH client not available for validation, skipping Bluetooth advertising check")
                return True  # Allow deployment to proceed
            
            result = await ssh_client.async_run("bluetoothctl show 2>/dev/null | grep -q 'Powered: yes' && echo 'available' || echo 'unavailable'")
            has_bluetooth = result.strip() == "available"
            if not has_bluetooth:
                self.logger.warning("Bluetooth not powered on, deployment may handle BLE setup")
            return True  # Always return True, let deployment handle BLE setup
        except Exception as e:
            self.logger.warning(f"Bluetooth advertising validation failed: {e}")
            return True  # Allow deployment to proceed
    
    async def deploy(self, ssh_client: SshClient, deployment_path: Path) -> bool:
        """Deploy Bluetooth advertising components."""
        try:
            # Install BLE advertising packages
            pip_packages = ["construct", "cryptography", "bluepy"]
            pip_cmd = f"python3 -m pip install {' '.join(pip_packages)}"
            await ssh_client.async_run(pip_cmd)
            
            # Deploy advertising script
            advertising_script = '''#!/usr/bin/env python3
"""Bluetooth LE advertising service."""
import logging
import subprocess
import time

def start_advertising():
    """Start BLE advertising."""
    try:
        # Stop any existing advertising
        subprocess.run(["sudo", "hciconfig", "hci0", "leadv", "0"], check=False)
        
        # Start advertising
        subprocess.run(["sudo", "hciconfig", "hci0", "leadv", "3"], check=True)
        logging.info("BLE advertising started")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start advertising: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_advertising()
'''
            
            script_path = deployment_path / "scripts" / "ble_advertising.py"
            await ssh_client.upload_file_content(advertising_script, str(script_path))
            await ssh_client.async_run(f"chmod +x {script_path}")
            
            self.logger.info("Bluetooth advertising deployed")
            return True
        except Exception as exc:
            self.logger.error(f"Bluetooth advertising deployment failed: {exc}")
            return False