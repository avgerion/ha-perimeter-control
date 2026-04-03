"""ESL AP service deployer.

Handles deployment of ESL (Electronic Shelf Label) AP service including:
- Advanced Bluetooth configuration for ESL
- ESL-specific packages and protocols
- AP configuration and ESL management
"""
from __future__ import annotations

import logging

from .base_deployer import BaseDeployer, ProgressCallback
from .const import PHASE_SUPERVISOR
from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


class EslDeployer(BaseDeployer):
    """Deployer for ESL AP service."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        self.service_id = "esl_ap"

    async def deploy(self) -> bool:
        """Deploy ESL AP service."""
        deployment_id = id(self)
        _LOGGER.warning("=== ESL DEPLOYER STARTED === (ID: %s)", deployment_id)
        
        try:
            # Phase 1: Preflight with ESL-specific resource requirements
            _LOGGER.info("ESL Phase 1: Preflight checks (ID: %s)", deployment_id)
            await self.phase_preflight(
                required_cpu=0.4,      # ESL management can be CPU intensive
                required_memory=160,   # Moderate memory for ESL protocol handling
                required_disk=80       # ESL configuration and label data
            )
            
            # Phase 2: Upload ESL-specific files
            _LOGGER.info("ESL Phase 2: Upload ESL files (ID: %s)", deployment_id)
            await self.phase_upload_files({
                'scripts': [
                    # ESL-specific scripts would go here
                    # Currently limited by available scripts
                ],
                'web': [
                    'layouts.py',    # ESL layout management UI
                    'callbacks.py',  # ESL event handling
                ]
            })
            
            # Phase 3: Install files
            _LOGGER.info("ESL Phase 3: Install files (ID: %s)", deployment_id)
            await self.phase_install()
            
            # Phase 4: Deploy ESL configuration
            _LOGGER.info("ESL Phase 4: Deploy config (ID: %s)", deployment_id)
            await self.phase_config(['perimeterControl.conf.yaml'])  # Shared config
            
            # Phase 5: Enable ESL Bluetooth configuration
            _LOGGER.info("ESL Phase 5: Enable ESL Bluetooth (ID: %s)", deployment_id)
            await self._enable_esl_bluetooth()
            
            # Phase 6: Install ESL Python packages
            _LOGGER.info("ESL Phase 6: Install ESL packages (ID: %s)", deployment_id)
            await self.install_python_packages([
                'bleak',       # BLE communication for ESL
                'construct',   # Protocol construction for ESL packets
                'cryptography', # Security for ESL communications
            ], 'ESL AP')
            
            # Phase 7: Deploy service descriptors
            _LOGGER.info("ESL Phase 7: Deploy service descriptors (ID: %s)", deployment_id)
            await self.deploy_service_descriptors([self.service_id])
            
            _LOGGER.warning("=== ESL DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("ESL deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("esl_deploy", f"ESL deployment error: {exc}")
            return False

    async def _enable_esl_bluetooth(self) -> None:
        """Enable and configure Bluetooth for ESL AP operations."""
        self._emit(PHASE_SUPERVISOR, "Configuring Bluetooth for ESL AP service...", 75)
        
        try:
            _LOGGER.info("Setting up Bluetooth for ESL operations...")
            
            # Check if Bluetooth service exists
            bt_exists = await self._client.async_run(
                "systemctl list-unit-files | grep -q bluetooth.service && echo EXISTS || echo MISSING"
            )
            
            if "MISSING" in bt_exists:
                _LOGGER.warning("Bluetooth service not available on this system")
                self._emit(PHASE_SUPERVISOR, "Bluetooth service not available", 76)
                return
            
            # Enable and start Bluetooth service
            await self._client.async_run("sudo systemctl enable bluetooth")
            await self._client.async_run("sudo systemctl start bluetooth")
            
            # Verify Bluetooth is running
            bt_status = await self._client.async_run("systemctl is-active bluetooth || echo INACTIVE")
            if "active" not in bt_status:
                _LOGGER.warning("Bluetooth may not be running properly: %s", bt_status)
                self._emit(PHASE_SUPERVISOR, "Bluetooth status uncertain", 76)
                return
                
            _LOGGER.info("Bluetooth enabled successfully")
            
            # Check for Bluetooth LE advertising capability (critical for ESL AP)
            try:
                hci_info = await self._client.async_run(
                    "timeout 5 hciconfig -a 2>/dev/null | head -20 || echo HCI_TIMEOUT"
                )
                
                if "HCI_TIMEOUT" not in hci_info:
                    if "LE" in hci_info or "Low Energy" in hci_info:
                        _LOGGER.info("Bluetooth LE capability detected")
                        self._emit(PHASE_SUPERVISOR, "Bluetooth LE capability verified", 76)
                    else:
                        _LOGGER.warning("Bluetooth LE capability not clearly detected")
                        
                    # Check advertising capabilities specifically
                    adv_check = await self._client.async_run(
                        "timeout 3 hcitool lescan --duplicates 2>/dev/null | head -1 || echo NO_LE_SCAN"
                    )
                    
                    if "NO_LE_SCAN" not in adv_check:
                        _LOGGER.info("Bluetooth LE scanning capability confirmed")
                        # Stop the scan (it may continue in background)
                        try:
                            await self._client.async_run("sudo pkill hcitool 2>/dev/null || true")
                        except:
                            pass
                    else:
                        _LOGGER.warning("Bluetooth LE scanning not available or failed")
                        
                else:
                    _LOGGER.warning("Could not check Bluetooth adapter details")
                    
            except Exception as hci_exc:
                _LOGGER.debug("HCI configuration check failed: %s", hci_exc)
            
            # Check for ESL-specific Bluetooth features (extended advertising, periodic advertising)
            try:
                # Check if bluetoothctl is available for advanced features
                bluetoothctl_check = await self._client.async_run(
                    "which bluetoothctl >/dev/null 2>&1 && echo AVAILABLE || echo MISSING"
                )
                
                if "AVAILABLE" in bluetoothctl_check:
                    _LOGGER.info("bluetoothctl available for advanced ESL features")
                    
                    # Check adapter capabilities
                    adapter_info = await self._client.async_run(
                        "timeout 5 bluetoothctl show 2>/dev/null || echo ADAPTER_TIMEOUT"
                    )
                    
                    if "ADAPTER_TIMEOUT" not in adapter_info and adapter_info.strip():
                        _LOGGER.debug("Bluetooth adapter info: %s", adapter_info[:200])
                        self._emit(PHASE_SUPERVISOR, "Bluetooth adapter configured", 77)
                    else:
                        _LOGGER.warning("Could not get Bluetooth adapter information")
                else:
                    _LOGGER.warning("bluetoothctl not available - limited ESL functionality")
                    
            except Exception as ctrl_exc:
                _LOGGER.debug("Bluetooth control check failed: %s", ctrl_exc)
            
            self._emit(PHASE_SUPERVISOR, "ESL Bluetooth configuration completed", 77)
                
        except Exception as exc:
            _LOGGER.warning("Failed to configure ESL Bluetooth (critical for ESL): %s", exc)
            self._emit(PHASE_SUPERVISOR, "ESL Bluetooth configuration failed", 77)
            # ESL functionality will be severely limited without proper Bluetooth

    def get_required_services(self) -> list[str]:
        """Return list of systemd services required for ESL functionality."""
        return ["bluetooth.service"]

    def get_hardware_requirements(self) -> dict[str, str]:
        """Return hardware requirements for ESL functionality."""
        return {
            "bluetooth_le": "required",
            "bluetooth_5_0": "preferred",  # For extended advertising
            "hci_interface": "required",
            "advertising_support": "required",
        }

    def get_package_dependencies(self) -> list[str]:
        """Return Python package dependencies for ESL functionality."""
        return [
            "bleak",
            "construct", 
            "cryptography",
        ]

    def get_system_dependencies(self) -> list[str]:
        """Return system package dependencies for ESL functionality."""
        return [
            "bluez",          # Bluetooth protocol stack
            "bluez-tools",    # Additional Bluetooth utilities  
            "bluetooth",      # Bluetooth service
        ]

    def conflicts_with(self) -> list[str]:
        """Return list of services that conflict with ESL AP."""
        # ESL AP typically conflicts with other BLE services due to advertising limitations
        return ["ble_gatt_repeater"]