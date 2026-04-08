"""Photo Booth service deployer.

Handles deployment of Photo Booth service including:
- Camera hardware enablement
- Photo processing packages (PIL, opencv)
- Camera configuration and scripts
"""
from __future__ import annotations

import logging

from .base_deployer import BaseDeployer, ProgressCallback
from .const import PHASE_SUPERVISOR
from .ssh_client import SshClient

_LOGGER = logging.getLogger(__name__)


class CameraDeployer(BaseDeployer):
    """Deployer for Photo Booth service."""

    def __init__(
        self,
        client: SshClient,
        progress_cb: ProgressCallback | None = None,
    ) -> None:
        super().__init__(client, progress_cb)
        import os
        self.service_id = os.environ.get('PERIMETERCONTROL_PHOTO_BOOTH_SERVICE', 'photo_booth')

    async def deploy(self) -> bool:
        """Deploy Photo Booth service."""
        deployment_id = id(self)
        _LOGGER.warning("=== CAMERA DEPLOYER STARTED === (ID: %s)", deployment_id)
        
        try:
            # Phase 1: Preflight with camera-specific resource requirements
            _LOGGER.info("Camera Phase 1: Preflight checks (ID: %s)", deployment_id)
            await self.phase_preflight(
                required_cpu=0.2,      # Image processing moderately intensive 
                required_memory=128,   # Reasonable memory for image processing
                required_disk=100      # Moderate space for photos and temp files
            )
            
            # Phase 2: Upload camera-specific files
            _LOGGER.info("Camera Phase 2: Upload camera files (ID: %s)", deployment_id)
            await self.phase_upload_files({
                'scripts': [
                    # Camera-specific scripts would go here
                    # Currently using dashboard files as placeholder
                ],
                'web': [
                    'dashboard.py',  # Photo booth UI components
                ]
            })
            
            # Phase 3: Install files
            _LOGGER.info("Camera Phase 3: Install files (ID: %s)", deployment_id)
            await self.phase_install()
            
            # Phase 4: Deploy camera configuration
            _LOGGER.info("Camera Phase 4: Deploy config (ID: %s)", deployment_id)
            await self.phase_config(['photo_booth_config.yaml'])
            
            # Phase 5: Enable camera hardware
            _LOGGER.info("Camera Phase 5: Enable camera hardware (ID: %s)", deployment_id)
            await self._enable_camera_hardware()
            
            # Phase 6: Install camera Python packages
            _LOGGER.info("Camera Phase 6: Install camera packages (ID: %s)", deployment_id)
            await self.install_python_packages([
                'pillow',      # PIL for image processing
                'opencv-python-headless',  # Computer vision without GUI deps
                'numpy',       # Numerical operations for image processing
            ], 'Photo Booth')
            
            # Phase 7: Deploy service descriptors
            _LOGGER.info("Camera Phase 7: Deploy service descriptors (ID: %s)", deployment_id)
            await self.deploy_service_descriptors([self.service_id])
            
            _LOGGER.warning("=== CAMERA DEPLOYMENT COMPLETED === (ID: %s)", deployment_id)
            return True
            
        except Exception as exc:
            _LOGGER.error("Camera deployment failed (ID: %s): %s", deployment_id, exc)
            self._emit_error("camera_deploy", f"Camera deployment error: {exc}")
            return False

    async def _enable_camera_hardware(self) -> None:
        """Enable camera hardware for Photo Booth operations."""
        self._emit(PHASE_SUPERVISOR, "Enabling camera hardware for Photo Booth service...", 75)
        
        try:
            _LOGGER.info("Checking camera hardware availability...")
            
            # Check if camera module is loaded (on Raspberry Pi)
            camera_modules = await self._client.async_run(
                "lsmod | grep -E '(bcm2835_v4l2|uvcvideo|v4l2)' || echo NO_CAMERA_MODULES"
            )
            
            if "NO_CAMERA_MODULES" not in camera_modules:
                _LOGGER.info("Camera kernel modules detected: %s", camera_modules.strip())
                self._emit(PHASE_SUPERVISOR, "Camera kernel modules available", 76)
            else:
                _LOGGER.info("No camera kernel modules detected, checking USB cameras...")
            
            # Check for available video devices
            video_devices = await self._client.async_run(
                "ls /dev/video* 2>/dev/null | head -5 || echo NO_VIDEO_DEVICES"
            )
            
            if "NO_VIDEO_DEVICES" not in video_devices:
                devices = video_devices.strip().split('\n')
                _LOGGER.info("Video devices found: %s", devices)
                self._emit(PHASE_SUPERVISOR, f"Found {len(devices)} video devices", 76)
                
                # Test camera access (non-blocking check)
                try:
                    camera_test = await self._client.async_run(
                        "timeout 3 v4l2-ctl --list-devices 2>/dev/null | head -10 || echo CAMERA_TEST_TIMEOUT"
                    )
                    if "CAMERA_TEST_TIMEOUT" not in camera_test and camera_test.strip():
                        _LOGGER.info("Camera access test successful")
                        self._emit(PHASE_SUPERVISOR, "Camera access verified", 77)
                    else:
                        _LOGGER.warning("Camera access test timed out or failed")
                        
                except Exception as test_exc:
                    _LOGGER.debug("Camera test failed (non-critical): %s", test_exc)
            else:
                _LOGGER.warning("No video devices found - camera may not be connected")
                self._emit(PHASE_SUPERVISOR, "No camera devices detected", 76)
            
            # Check GPU memory split for Raspberry Pi camera (if applicable)
            try:
                gpu_mem = await self._client.async_run(
                    "vcgencmd get_mem gpu 2>/dev/null || echo NO_GPU_INFO"
                )
                if "NO_GPU_INFO" not in gpu_mem:
                    _LOGGER.info("GPU memory configuration: %s", gpu_mem.strip())
                    # Check if GPU memory is sufficient for camera operations
                    if "gpu=" in gpu_mem:
                        gpu_mb = int(gpu_mem.split("gpu=")[1].split("M")[0])
                        if gpu_mb >= 128:
                            _LOGGER.info("GPU memory sufficient for camera operations")
                        else:
                            _LOGGER.warning("GPU memory may be insufficient for camera operations (found %dMB, recommend 128MB+)", gpu_mb)
                
            except Exception as gpu_exc:
                _LOGGER.debug("Could not check GPU memory (not critical): %s", gpu_exc)
                
            # Enable camera interface if on Raspberry Pi
            try:
                raspi_config_check = await self._client.async_run(
                    "which raspi-config >/dev/null 2>&1 && echo RASPI || echo NO_RASPI"
                )
                if "RASPI" in raspi_config_check:
                    _LOGGER.info("Raspberry Pi detected, checking camera interface...")
                    # Note: We don't auto-enable camera interface as it requires reboot
                    # This should be documented as a manual step
                    _LOGGER.info("Camera interface enablement may require manual configuration via raspi-config")
                    
            except Exception as raspi_exc:
                _LOGGER.debug("Raspberry Pi check failed: %s", raspi_exc)
                
            self._emit(PHASE_SUPERVISOR, "Camera hardware configuration completed", 77)
                
        except Exception as exc:
            _LOGGER.warning("Failed to configure camera hardware (non-critical): %s", exc)
            self._emit(PHASE_SUPERVISOR, "Camera configuration failed, continuing...", 77)

    def get_required_services(self) -> list[str]:
        """Return list of systemd services required for camera functionality."""
        return []  # Camera typically doesn't require specific systemd services

    def get_hardware_requirements(self) -> dict[str, str]:
        """Return hardware requirements for camera functionality."""
        return {
            "camera_device": "required",
            "video_devices": "required", 
            "gpu_memory": "preferred",  # For Raspberry Pi
        }

    def get_package_dependencies(self) -> list[str]:
        """Return Python package dependencies for camera functionality."""
        return [
            "pillow",
            "opencv-python-headless", 
            "numpy",
        ]

    def get_system_dependencies(self) -> list[str]:
        """Return system package dependencies for camera functionality."""
        return [
            "v4l-utils",      # Video4Linux utilities
            "ffmpeg",         # Video processing
            "libcamera-apps", # Raspberry Pi camera apps (if applicable)
        ]