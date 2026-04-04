"""Wildlife Monitor service deployer.

Handles deployment of Wildlife Monitor service including:
- Sensor interface enablement (I2C, SPI)
- Data analysis packages (pandas, numpy)
- Wildlife monitoring scripts and configuration
"""
from __future__ import annotations

import logging

from .base_deployer import BaseDeployer, ProgressCallback
from .const import PHASE_SUPERVISOR
from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


class WildlifeDeployer(BaseDeployer):
    """Deployer for Wildlife Monitor service."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        self.service_id = "wildlife_monitor"

    async def deploy(self) -> bool:
        """Deploy Wildlife Monitor service."""
        deployment_id = id(self)
        _LOGGER.warning("=== WILDLIFE DEPLOYER STARTED === (ID: %s)", deployment_id)
        
        try:
            # Phase 1: Preflight with wildlife-specific resource requirements
            _LOGGER.info("Wildlife Phase 1: Preflight checks (ID: %s)", deployment_id)
            await self.phase_preflight(
                required_cpu=0.15,     # Data analysis moderately intensive
                required_memory=96,    # Conservative memory for data processing
                required_disk=75       # Reasonable space for sensor data and logs
            )
            
            # Phase 2: Upload wildlife-specific files
            _LOGGER.info("Wildlife Phase 2: Upload wildlife files (ID: %s)", deployment_id)
            await self.phase_upload_files({
                'scripts': [
                    # Wildlife monitoring scripts would go here
                    # Currently limited by available scripts
                ],
                'web': [
                    'data_sources.py',  # Data visualization components
                ]
            })
            
            # Phase 3: Install files
            _LOGGER.info("Wildlife Phase 3: Install files (ID: %s)", deployment_id)
            await self.phase_install()
            
            # Phase 4: Deploy wildlife configuration
            _LOGGER.info("Wildlife Phase 4: Deploy config (ID: %s)", deployment_id)
            await self.phase_config(['perimeterControl.conf.yaml'])  # Shared config
            
            # Phase 5: Enable sensor interfaces
            _LOGGER.info("Wildlife Phase 5: Enable sensor interfaces (ID: %s)", deployment_id)
            await self._enable_sensor_interfaces()
            
            # Phase 6: Install wildlife Python packages
            _LOGGER.info("Wildlife Phase 6: Install wildlife packages (ID: %s)", deployment_id)
            await self.install_python_packages([
                'pandas',      # Data analysis and manipulation
                'numpy',       # Numerical computing
                'scipy',       # Scientific computing
                'RPi.GPIO',    # Raspberry Pi GPIO control (if applicable)
                'adafruit-circuitpython-gpio',  # Hardware abstraction
            ], 'Wildlife Monitor')
            
            # Phase 7: Deploy service descriptors
            _LOGGER.info("Wildlife Phase 7: Deploy service descriptors (ID: %s)", deployment_id)
            await self.deploy_service_descriptors([self.service_id])
            
            _LOGGER.warning("=== WILDLIFE DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("Wildlife deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("wildlife_deploy", f"Wildlife deployment error: {exc}")
            return False

    async def _enable_sensor_interfaces(self) -> None:
        """Enable sensor interfaces for Wildlife Monitor operations."""
        self._emit(PHASE_SUPERVISOR, "Enabling sensor interfaces for Wildlife Monitor...", 75)
        
        try:
            _LOGGER.info("Checking sensor interface availability...")
            
            # Check for I2C interface (common for environmental sensors)
            i2c_devices = await self._client.async_run(
                "ls /dev/i2c-* 2>/dev/null || echo NO_I2C_DEVICES"
            )
            
            if "NO_I2C_DEVICES" not in i2c_devices:
                devices = i2c_devices.strip().split('\n')
                _LOGGER.info("I2C devices found: %s", devices)
                self._emit(PHASE_SUPERVISOR, f"Found {len(devices)} I2C interfaces", 76)
                
                # Test I2C access
                try:
                    i2c_test = await self._client.async_run(
                        "which i2cdetect >/dev/null 2>&1 && echo I2C_TOOLS_OK || echo NO_I2C_TOOLS"
                    )
                    if "I2C_TOOLS_OK" in i2c_test:
                        _LOGGER.info("I2C tools available for sensor detection")
                        # Quick scan for devices (non-blocking)
                        try:
                            i2c_scan = await self._client.async_run(
                                "timeout 3 i2cdetect -y 1 2>/dev/null | grep -v '^     ' | wc -l || echo SCAN_TIMEOUT"
                            )
                            if "SCAN_TIMEOUT" not in i2c_scan and i2c_scan.strip():
                                device_count = int(i2c_scan.strip()) - 1  # Subtract header line
                                if device_count > 0:
                                    _LOGGER.info("Detected %d I2C devices", device_count)
                                    
                        except Exception as scan_exc:
                            _LOGGER.debug("I2C scan failed (non-critical): %s", scan_exc)
                            
                except Exception as test_exc:
                    _LOGGER.debug("I2C tools check failed: %s", test_exc)
            else:
                _LOGGER.warning("No I2C devices found - sensors may not be connected")
                self._emit(PHASE_SUPERVISOR, "No I2C devices detected", 76)
            
            # Check for SPI interface (for high-speed sensors)
            spi_devices = await self._client.async_run(
                "ls /dev/spidev* 2>/dev/null || echo NO_SPI_DEVICES"
            )
            
            if "NO_SPI_DEVICES" not in spi_devices:
                devices = spi_devices.strip().split('\n')
                _LOGGER.info("SPI devices found: %s", devices)
                self._emit(PHASE_SUPERVISOR, f"Found {len(devices)} SPI interfaces", 76)
            else:
                _LOGGER.info("No SPI devices found (may not be needed)")
            
            # Check GPIO availability for simple sensors
            gpio_check = await self._client.async_run(
                "ls /sys/class/gpio 2>/dev/null && echo GPIO_OK || echo NO_GPIO"
            )
            
            if "GPIO_OK" in gpio_check:
                _LOGGER.info("GPIO interface available")
                self._emit(PHASE_SUPERVISOR, "GPIO interface available", 76)
            else:
                _LOGGER.warning("GPIO interface not available")
            
            # Check for environmental sensor modules
            sensor_modules = await self._client.async_run(
                "lsmod | grep -E '(w1_|dht|bmp|sht|ds18b20)' || echo NO_SENSOR_MODULES"
            )
            
            if "NO_SENSOR_MODULES" not in sensor_modules:
                modules = [line.split()[0] for line in sensor_modules.strip().split('\n')]
                _LOGGER.info("Sensor kernel modules detected: %s", modules)
                self._emit(PHASE_SUPERVISOR, f"Found {len(modules)} sensor modules", 77)
            else:
                _LOGGER.info("No specific sensor modules detected (generic interfaces available)")
            
            self._emit(PHASE_SUPERVISOR, "Sensor interface configuration completed", 77)
                
        except Exception as exc:
            _LOGGER.warning("Failed to configure sensor interfaces (non-critical): %s", exc)
            self._emit(PHASE_SUPERVISOR, "Sensor configuration failed, continuing...", 77)

    def get_required_services(self) -> list[str]:
        """Return list of systemd services required for wildlife functionality."""
        return []  # Wildlife monitoring typically doesn't require specific systemd services

    def get_hardware_requirements(self) -> dict[str, str]:
        """Return hardware requirements for wildlife functionality."""
        return {
            "gpio_interface": "preferred",
            "i2c_interface": "preferred",
            "spi_interface": "optional",
            "environmental_sensors": "preferred",
        }

    def get_package_dependencies(self) -> list[str]:
        """Return Python package dependencies for wildlife functionality."""
        return [
            "pandas",
            "numpy", 
            "scipy",
            "RPi.GPIO",
            "adafruit-circuitpython-gpio",
        ]

    def get_system_dependencies(self) -> list[str]:
        """Return system package dependencies for wildlife functionality."""
        return [
            "i2c-tools",      # I2C utilities
            "python3-dev",    # Development headers for native extensions
            "gcc",           # Compiler for native extensions
        ]