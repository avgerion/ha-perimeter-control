"""
photo_booth capability module.

Provides camera functionality for wildlife monitoring, security, and photo captures.
Creates HA camera entities and supports image capture, streaming, and motion detection.

Features:
- Camera control and image capture
- Motion detection (with optional triggers)
- Scheduled captures (timelapse)
- Image storage and management
- Camera settings control (resolution, quality, etc.)

Entities created:
  photo_booth:camera:stream          → camera (live camera feed)
  photo_booth:camera:motion          → binary_sensor (motion detection)
  photo_booth:camera:last_capture    → sensor (timestamp of last photo)
  photo_booth:camera:storage_used    → sensor (storage space used)
  photo_booth:camera:available       → binary_sensor (camera availability)

Actions:
  capture_photo    — take a single photo
  start_timelapse  — start scheduled photo captures
  stop_timelapse   — stop scheduled captures
  set_resolution   — change camera resolution
  clear_storage    — delete old photos
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import CapabilityModule

logger = logging.getLogger(__name__)


class PhotoBoothCapability(CapabilityModule):
    """Photo booth capability for camera functionality."""

    def __init__(self, cap_id: str, config: Dict[str, Any], entity_cache, emit_event):
        super().__init__(cap_id, config, entity_cache, emit_event)
        
        # Configuration
        self.camera_device = config.get("camera_device", "/dev/video0")
        self.photo_dir = Path(config.get("photo_directory", "/opt/isolator/photos"))
        self.resolution = config.get("resolution", "1920x1080")
        self.quality = config.get("quality", 85)
        self.max_storage_mb = config.get("max_storage_mb", 1000)
        
        # State
        self._camera_available = False
        self._timelapse_task: Optional[asyncio.Task] = None
        self._timelapse_active = False
        self._motion_detection = config.get("motion_detection", False)
        self._last_capture_time: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start photo booth capability.""" 
        logger.info("[%s] Starting Photo Booth", self.cap_id)
        
        # Create photo directory
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        
        # Check camera availability
        await self._check_camera_availability()
        
        # Create initial entities
        await self._create_camera_entities()
        
        # Start timelapse if configured
        if self.config.get("timelapse", {}).get("enabled", False):
            await self._start_timelapse_internal()
        
        logger.info("[%s] Photo Booth started", self.cap_id)

    async def stop(self) -> None:
        """Stop photo booth capability."""
        logger.info("[%s] Stopping Photo Booth", self.cap_id)
        
        # Stop timelapse
        await self._stop_timelapse_internal()
        
        # Clear entities
        self.entity_cache.clear_capability_entities(self.cap_id)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_entities(self) -> List[Dict[str, Any]]:
        """Return camera entities."""
        entities = []
        for entity_id, entity_data in self.entity_cache.get_by_capability(self.cap_id).items():
            entity = entity_data.copy()
            entity["id"] = entity_id
            entities.append(entity)
        return entities

    # ------------------------------------------------------------------
    # Health probe  
    # ------------------------------------------------------------------

    def get_health_probe(self) -> Optional[Dict[str, Any]]:
        """Health check - camera should be available."""
        return {
            "type": "custom",
            "check": lambda: self._camera_available,
            "timeout_sec": 5,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        """Execute photo booth actions."""
        if action_id == "capture_photo":
            return await self._capture_photo(params.get("filename"))
            
        elif action_id == "start_timelapse":
            interval = params.get("interval_sec", 60)
            return await self._start_timelapse(interval)
            
        elif action_id == "stop_timelapse":
            return await self._stop_timelapse()
            
        elif action_id == "set_resolution":
            resolution = params.get("resolution")
            if not resolution:
                raise ValueError("resolution parameter required")
            return await self._set_resolution(resolution)
            
        elif action_id == "clear_storage":
            days_old = params.get("days_old", 7)
            return await self._clear_old_photos(days_old)
            
        raise NotImplementedError(f"Unknown action: {action_id}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate photo booth configuration."""
        errors: List[str] = []
        
        quality = config.get("quality", 85)
        if not isinstance(quality, int) or not (1 <= quality <= 100):
            errors.append("quality must be an integer between 1 and 100")
            
        max_storage = config.get("max_storage_mb", 1000)
        if not isinstance(max_storage, (int, float)) or max_storage <= 0:
            errors.append("max_storage_mb must be a positive number")
            
        return errors

    # ------------------------------------------------------------------
    # Camera Operations
    # ------------------------------------------------------------------

    async def _check_camera_availability(self) -> None:
        """Check if camera device is available."""
        try:
            # Check if camera device exists
            camera_exists = os.path.exists(self.camera_device)
            
            if camera_exists:
                # Try to capture a test image to verify camera works
                test_result = await self._run_camera_command([
                    "fswebcam", "-d", self.camera_device, 
                    "--no-banner", "-r", "640x480", "/tmp/test_capture.jpg"
                ])
                self._camera_available = (test_result.returncode == 0)
                
                # Clean up test file
                if os.path.exists("/tmp/test_capture.jpg"):
                    os.remove("/tmp/test_capture.jpg")
            else:
                self._camera_available = False
                
        except Exception as e:
            logger.warning("[%s] Camera availability check failed: %s", self.cap_id, e)
            self._camera_available = False

    async def _run_camera_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run camera command asynchronously."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr
        )

    async def _capture_photo(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """Capture a single photo."""
        if not self._camera_available:
            raise RuntimeError("Camera not available")
            
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{timestamp}.jpg"
            
        photo_path = self.photo_dir / filename
        
        try:
            # Capture photo using fswebcam
            cmd = [
                "fswebcam",
                "-d", self.camera_device,
                "--no-banner", 
                "-r", self.resolution,
                "--jpeg", str(self.quality),
                str(photo_path)
            ]
            
            result = await self._run_camera_command(cmd)
            
            if result.returncode == 0:
                self._last_capture_time = datetime.now()
                
                # Update entities
                await self._update_capture_entities()
                
                # Emit event
                self._emit_event("photo_captured", {
                    "filename": filename,
                    "path": str(photo_path),
                    "size_bytes": photo_path.stat().st_size,
                    "timestamp": self._last_capture_time.isoformat()
                })
                
                logger.info("[%s] Photo captured: %s", self.cap_id, filename)
                return {
                    "status": "success",
                    "filename": filename,
                    "path": str(photo_path),
                    "timestamp": self._last_capture_time.isoformat()
                }
            else:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                raise RuntimeError(f"Photo capture failed: {error_msg}")
                
        except Exception as e:
            logger.error("[%s] Photo capture error: %s", self.cap_id, e)
            raise

    async def _set_resolution(self, resolution: str) -> Dict[str, Any]:
        """Set camera resolution."""
        if not resolution.count('x') == 1:
            raise ValueError("Resolution must be in format WIDTHxHEIGHT (e.g., 1920x1080)")
            
        try:
            width, height = resolution.split('x')
            int(width), int(height)  # Validate they're numbers
        except ValueError:
            raise ValueError("Invalid resolution format")
            
        self.resolution = resolution
        
        # Update camera entity if it exists
        camera_entity_id = "photo_booth:camera:stream"
        if camera_entity_id in self.entity_cache._entities:
            entity = self.entity_cache._entities[camera_entity_id].copy()
            entity["id"] = camera_entity_id  # Add missing id field
            entity["attributes"]["resolution"] = resolution
            self._publish_entity(entity)
        
        return {"message": f"Resolution set to {resolution}"}

    # ------------------------------------------------------------------
    # Timelapse
    # ------------------------------------------------------------------

    async def _start_timelapse(self, interval_sec: int) -> Dict[str, Any]:
        """Start timelapse photography."""
        if self._timelapse_active:
            return {"message": "Timelapse already active"}
            
        await self._start_timelapse_internal(interval_sec)
        return {"message": f"Timelapse started (interval: {interval_sec}s)"}

    async def _stop_timelapse(self) -> Dict[str, Any]:
        """Stop timelapse photography."""
        if not self._timelapse_active:
            return {"message": "Timelapse not active"}
            
        await self._stop_timelapse_internal()
        return {"message": "Timelapse stopped"}

    async def _start_timelapse_internal(self, interval_sec: Optional[int] = None) -> None:
        """Internal timelapse start."""
        if self._timelapse_active:
            return
            
        interval = interval_sec or self.config.get("timelapse", {}).get("interval_sec", 300)
        self._timelapse_active = True
        
        async def timelapse_loop():
            """Continuous timelapse capture loop."""
            while self._timelapse_active:
                try:
                    if self._camera_available:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"timelapse_{timestamp}.jpg"
                        await self._capture_photo(filename)
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.warning("[%s] Timelapse capture error: %s", self.cap_id, e)
                    await asyncio.sleep(interval)  # Continue despite errors
                    
        self._timelapse_task = asyncio.create_task(timelapse_loop())

    async def _stop_timelapse_internal(self) -> None:
        """Internal timelapse stop."""
        self._timelapse_active = False
        if self._timelapse_task:
            self._timelapse_task.cancel()
            try:
                await self._timelapse_task
            except asyncio.CancelledError:
                pass
            self._timelapse_task = None

    # ------------------------------------------------------------------
    # Storage Management
    # ------------------------------------------------------------------

    async def _clear_old_photos(self, days_old: int = 7) -> Dict[str, Any]:
        """Clear photos older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0
        freed_bytes = 0
        
        try:
            for photo_file in self.photo_dir.glob("*.jpg"):
                if photo_file.stat().st_mtime < cutoff_date.timestamp():
                    freed_bytes += photo_file.stat().st_size
                    photo_file.unlink()
                    deleted_count += 1
                    
            await self._update_storage_entities()
            
            return {
                "deleted_count": deleted_count,
                "freed_mb": round(freed_bytes / (1024 * 1024), 2),
                "message": f"Deleted {deleted_count} photos, freed {freed_bytes // (1024*1024)} MB"
            }
            
        except Exception as e:
            logger.error("[%s] Storage cleanup error: %s", self.cap_id, e)
            raise

    def _get_storage_usage(self) -> Dict[str, Any]:
        """Get current storage usage statistics."""
        try:
            total_bytes = 0
            photo_count = 0
            
            for photo_file in self.photo_dir.glob("*.jpg"):
                total_bytes += photo_file.stat().st_size
                photo_count += 1
                
            return {
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / (1024 * 1024), 2),
                "photo_count": photo_count,
                "usage_percent": (total_bytes / (1024 * 1024)) / self.max_storage_mb * 100
            }
            
        except Exception as e:
            logger.warning("[%s] Storage usage calculation error: %s", self.cap_id, e)
            return {"total_bytes": 0, "total_mb": 0, "photo_count": 0, "usage_percent": 0}

    # ------------------------------------------------------------------
    # Entity Management
    # ------------------------------------------------------------------

    async def _create_camera_entities(self) -> None:
        """Create all camera-related entities."""
        
        # Main camera entity (placeholder for now - real MJPEG streaming would need more setup)
        camera_entity = {
            "id": "photo_booth:camera:stream",
            "type": "camera",
            "friendly_name": "Wildlife Camera",
            "capability": self.cap_id,
            "state": "available" if self._camera_available else "unavailable",
            "attributes": {
                "device": self.camera_device,
                "resolution": self.resolution,
                "quality": self.quality,
                "last_image": str(self.photo_dir / "latest.jpg") if self._camera_available else None,
            }
        }
        self._publish_entity(camera_entity)

        # Camera availability binary sensor
        available_entity = {
            "id": "photo_booth:camera:available",
            "type": "binary_sensor",
            "friendly_name": "Camera Available",
            "capability": self.cap_id,
            "state": "on" if self._camera_available else "off",
            "device_class": "connectivity",
            "icon": "mdi:camera",
        }
        self._publish_entity(available_entity)

        # Update capture and storage entities
        await self._update_capture_entities()
        await self._update_storage_entities()

        # Motion detection binary sensor (if enabled)
        if self._motion_detection:
            motion_entity = {
                "id": "photo_booth:camera:motion",
                "type": "binary_sensor",
                "friendly_name": "Motion Detected",
                "capability": self.cap_id,
                "state": "off",  # Updated by motion detection logic
                "device_class": "motion",
                "icon": "mdi:motion-sensor",
            }
            self._publish_entity(motion_entity)

    async def _update_capture_entities(self) -> None:
        """Update entities related to photo captures."""
        
        # Last capture timestamp sensor
        last_capture_entity = {
            "id": "photo_booth:camera:last_capture",
            "type": "sensor",
            "friendly_name": "Last Photo Capture",
            "capability": self.cap_id,
            "state": self._last_capture_time.isoformat() if self._last_capture_time else "never",
            "device_class": "timestamp",
            "icon": "mdi:camera-timer",
            "attributes": {
                "timelapse_active": self._timelapse_active,
            }
        }
        self._publish_entity(last_capture_entity)

    async def _update_storage_entities(self) -> None:
        """Update entities related to storage usage."""
        storage_info = self._get_storage_usage()
        
        # Storage usage sensor
        storage_entity = {
            "id": "photo_booth:camera:storage_used",
            "type": "sensor",
            "friendly_name": "Photo Storage Usage",
            "capability": self.cap_id,
            "state": str(storage_info["total_mb"]),
            "unit_of_measurement": "MB",
            "icon": "mdi:harddisk",
            "attributes": {
                "photo_count": storage_info["photo_count"],
                "usage_percent": round(storage_info["usage_percent"], 1),
                "max_storage_mb": self.max_storage_mb,
                "directory": str(self.photo_dir),
            }
        }
        self._publish_entity(storage_entity)