"""BLE GATT Repeater service deployer.

Handles deployment of BLE GATT Repeater service including:
- Bluetooth hardware enablement
- BLE-specific Python packages (bleak)
- BLE configuration and scripts
"""
from __future__ import annotations

import logging

from .base_deployer import BaseDeployer, ProgressCallback
from .const import PHASE_SUPERVISOR
from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


class BleDeployer(BaseDeployer):
    """Deployer for BLE GATT Repeater service."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        import os
        self.service_id = os.environ.get('PERIMETERCONTROL_BLE_GATT_REPEATER_SERVICE', 'ble_gatt_repeater')

    async def deploy(self) -> bool:
        """Deploy BLE GATT Repeater service."""
        deployment_id = id(self)
        _LOGGER.warning("=== BLE DEPLOYER STARTED === (ID: %s)", deployment_id)
        
        try:
            # Phase 1: Preflight with BLE-specific resource requirements
            _LOGGER.info("BLE Phase 1: Preflight checks (ID: %s)", deployment_id)
            await self.phase_preflight(
                required_cpu=0.15,     # BLE scanning is moderately intensive
                required_memory=64,    # Conservative memory requirement
                required_disk=30       # Light disk usage
            )
            
            # Phase 2: Upload BLE-specific files
            _LOGGER.info("BLE Phase 2: Upload BLE files (ID: %s)", deployment_id)
            await self.phase_upload_files({
                'scripts': [
                    'ble-scanner-v2.py',
                    'ble-sniffer.py', 
                    'ble-debug.sh',
                    'ble-proxy-profiler.py',
                    'ble-gatt-mirror.py',
                ]
            })
            
            # Phase 3: Install files
            _LOGGER.info("BLE Phase 3: Install files (ID: %s)", deployment_id)
            await self.phase_install()
            
            # Phase 4: Deploy BLE configuration
            _LOGGER.info("BLE Phase 4: Deploy config (ID: %s)", deployment_id)
            await self.phase_config(['ble_config.yaml'])
            
            # Phase 5: Enable Bluetooth hardware
            _LOGGER.info("BLE Phase 5: Enable Bluetooth hardware (ID: %s)", deployment_id)
            await self._enable_bluetooth_hardware()
            
            # Phase 6: Install BLE Python packages
            _LOGGER.info("BLE Phase 6: Install BLE packages (ID: %s)", deployment_id)
            await self.install_python_packages(['bleak'], 'BLE GATT Repeater')
            
            # Phase 7: Deploy service descriptors
            _LOGGER.info("BLE Phase 7: Deploy service descriptors (ID: %s)", deployment_id)
            await self.deploy_service_descriptors([self.service_id])
            
            _LOGGER.warning("=== BLE DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("BLE deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("ble_deploy", f"BLE deployment error: {exc}")
            return False

    async def _enable_bluetooth_hardware(self) -> None:
        """Enable Bluetooth hardware for BLE operations."""
        self._emit(PHASE_SUPERVISOR, "Enabling Bluetooth hardware for BLE service...", 75)
        
        try:
            _LOGGER.info("Enabling Bluetooth service...")
            
            # Check if Bluetooth service exists
            bt_exists = await self._client.async_run(
                "systemctl list-unit-files | grep -q bluetooth.service && echo EXISTS || echo MISSING"
            )
            
            if "MISSING" in bt_exists:
                _LOGGER.warning("Bluetooth service not available on this system")
                self._emit(PHASE_SUPERVISOR, "Bluetooth service not available, continuing...", 76)
                return
            
            # Enable and start Bluetooth service
            await self._client.async_run("sudo systemctl enable bluetooth")
            await self._client.async_run("sudo systemctl start bluetooth")
            
            # Verify Bluetooth is running
            bt_status = await self._client.async_run("systemctl is-active bluetooth || echo INACTIVE")
            if "active" in bt_status:
                _LOGGER.info("Bluetooth enabled and started successfully")
                self._emit(PHASE_SUPERVISOR, "Bluetooth hardware enabled", 77)
            else:
                _LOGGER.warning("Bluetooth may not be running properly: %s", bt_status)
                self._emit(PHASE_SUPERVISOR, "Bluetooth status uncertain", 77)
                
            # Check Bluetooth adapter availability
            try:
                hci_output = await self._client.async_run("hciconfig 2>/dev/null || echo NO_HCI")
                if "NO_HCI" not in hci_output and "hci" in hci_output:
                    _LOGGER.info("Bluetooth adapter detected")
                    self._emit(PHASE_SUPERVISOR, "Bluetooth adapter verified", 77)
                else:
                    _LOGGER.warning("No Bluetooth adapter detected or hciconfig not available")
                    
            except Exception as hci_exc:
                _LOGGER.debug("Could not check Bluetooth adapter: %s", hci_exc)
                
        except Exception as exc:
            _LOGGER.warning("Failed to enable Bluetooth (non-critical): %s", exc)
            self._emit(PHASE_SUPERVISOR, "Bluetooth enablement failed, continuing...", 77)

    def get_required_services(self) -> list[str]:
        """Return list of systemd services required for BLE functionality."""
        return ["bluetooth.service"]

    def get_hardware_requirements(self) -> dict[str, str]:
        """Return hardware requirements for BLE functionality."""
        return {
            "bluetooth": "required",
            "hci_interface": "preferred",
        }

    def get_package_dependencies(self) -> list[str]:
        """Return Python package dependencies for BLE functionality."""
        return ["bleak"]