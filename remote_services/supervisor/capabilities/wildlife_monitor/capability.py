"""
wildlife_monitor capability module.

Provides wildlife monitoring, motion detection, and environmental sensing.
Creates HA entities for wildlife activity monitoring, environmental data, and camera captures.

Features:
- Motion detection and trigger recording
- Environmental monitoring (temperature, humidity, light)
- Battery level monitoring for low-power deployment
- Wildlife activity logging
- Scheduled monitoring sessions

Entities created:
  wildlife_monitor:motion:detected        → binary_sensor (motion detection)
  wildlife_monitor:camera:last_trigger    → sensor (last motion trigger time)
  wildlife_monitor:env:temperature        → sensor (environmental temperature)
  wildlife_monitor:env:humidity           → sensor (relative humidity)
  wildlife_monitor:env:light_level        → sensor (ambient light level)
  wildlife_monitor:system:battery         → sensor (battery level)
  wildlife_monitor:system:active          → binary_sensor (monitoring active)

Actions:
  start_monitoring    — start wildlife monitoring session
  stop_monitoring     — stop monitoring session
  capture_on_motion   — take photo when motion detected
  set_sensitivity     — adjust motion detection sensitivity
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import CapabilityModule

logger = logging.getLogger(__name__)


class WildlifeMonitorCapability(CapabilityModule):
    """Wildlife monitoring capability for motion detection and environmental sensing."""

    def __init__(self, cap_id: str, config: Dict[str, Any], entity_cache, emit_event):
        super().__init__(cap_id, config, entity_cache, emit_event)
        
        # Configuration
        self.motion_sensitivity = config.get("motion_sensitivity", 0.85)
        self.capture_dir = Path(config.get("capture_directory", "/opt/isolator/wildlife"))
        self.monitoring_enabled = config.get("monitoring", {}).get("enabled", True)
        self.env_sensors = config.get("environmental_sensors", {})
        
        # State
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_motion_time: Optional[datetime] = None
        self._battery_level = None
        self._env_data = {
            "temperature": None,
            "humidity": None, 
            "light_level": None
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start wildlife monitoring capability.""" 
        logger.info("[%s] Starting Wildlife Monitor", self.cap_id)
        
        # Create capture directory
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        
        # Create initial entities
        await self._create_monitoring_entities()
        
        # Start monitoring if configured
        if self.monitoring_enabled:
            await self._start_monitoring_internal()
        
        logger.info("[%s] Wildlife Monitor started", self.cap_id)

    async def stop(self) -> None:
        """Stop wildlife monitoring capability."""
        logger.info("[%s] Stopping Wildlife Monitor", self.cap_id)
        
        # Stop monitoring
        await self._stop_monitoring_internal()
        
        # Clear entities
        self.entity_cache.clear_capability_entities(self.cap_id)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_entities(self) -> List[Dict[str, Any]]:
        """Return entities for wildlife monitoring."""
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
        """Simple health check - monitoring should be active if enabled."""
        if not self.monitoring_enabled:
            return None
        return {
            "type": "custom",
            "check": lambda: self._monitoring_active,
            "timeout_sec": 5,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        """Execute wildlife monitoring actions."""
        if action_id == "start_monitoring":
            await self._start_monitoring_internal()
            return {"message": "Wildlife monitoring started"}
            
        elif action_id == "stop_monitoring":
            await self._stop_monitoring_internal()
            return {"message": "Wildlife monitoring stopped"}
            
        elif action_id == "capture_on_motion":
            enabled = params.get("enabled", True)
            await self._set_motion_capture(enabled)
            return {"message": f"Motion capture {'enabled' if enabled else 'disabled'}"}
            
        elif action_id == "set_sensitivity":
            sensitivity = params.get("sensitivity", 0.85)
            if not (0.0 <= sensitivity <= 1.0):
                raise ValueError("sensitivity must be between 0.0 and 1.0")
            self.motion_sensitivity = sensitivity
            return {"message": f"Motion sensitivity set to {sensitivity}"}
            
        raise NotImplementedError(f"Unknown action: {action_id}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate wildlife monitoring configuration."""
        errors: List[str] = []
        
        sensitivity = config.get("motion_sensitivity", 0.85)
        if not isinstance(sensitivity, (int, float)) or not (0.0 <= sensitivity <= 1.0):
            errors.append("motion_sensitivity must be a number between 0.0 and 1.0")
            
        return errors

    # ------------------------------------------------------------------
    # Internal Implementation
    # ------------------------------------------------------------------

    async def _create_monitoring_entities(self) -> None:
        """Create all wildlife monitoring entities."""
        # Motion detection binary sensor
        motion_entity = {
            "id": "wildlife_monitor:motion:detected",
            "type": "binary_sensor",
            "friendly_name": "Motion Detected",
            "capability": self.cap_id,
            "state": "off",
            "device_class": "motion",
            "icon": "mdi:motion-sensor",
        }
        self._publish_entity(motion_entity)
        
        # System active status
        active_entity = {
            "id": "wildlife_monitor:system:active",
            "type": "binary_sensor",
            "friendly_name": "Monitoring Active",
            "capability": self.cap_id,
            "state": "on" if self._monitoring_active else "off",
            "device_class": "running",
            "icon": "mdi:eye",
        }
        self._publish_entity(active_entity)
        
        # Last motion trigger time
        trigger_entity = {
            "id": "wildlife_monitor:camera:last_trigger",
            "type": "sensor",
            "friendly_name": "Last Motion Trigger",
            "capability": self.cap_id,
            "state": self._last_motion_time.isoformat() if self._last_motion_time else "never",
            "device_class": "timestamp",
            "icon": "mdi:camera-timer",
        }
        self._publish_entity(trigger_entity)
        
        # Environmental sensors (if configured)
        if self.env_sensors.get("temperature", False):
            temp_entity = {
                "id": "wildlife_monitor:env:temperature",
                "type": "sensor",
                "friendly_name": "Environment Temperature",
                "capability": self.cap_id,
                "state": str(self._env_data["temperature"]) if self._env_data["temperature"] is not None else "unavailable",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "icon": "mdi:thermometer",
            }
            self._publish_entity(temp_entity)
        
        if self.env_sensors.get("humidity", False):
            humidity_entity = {
                "id": "wildlife_monitor:env:humidity", 
                "type": "sensor",
                "friendly_name": "Environment Humidity",
                "capability": self.cap_id,
                "state": str(self._env_data["humidity"]) if self._env_data["humidity"] is not None else "unavailable",
                "unit_of_measurement": "%",
                "device_class": "humidity",
                "icon": "mdi:water-percent",
            }
            self._publish_entity(humidity_entity)
        
        if self.env_sensors.get("light", False):
            light_entity = {
                "id": "wildlife_monitor:env:light_level",
                "type": "sensor", 
                "friendly_name": "Ambient Light Level",
                "capability": self.cap_id,
                "state": str(self._env_data["light_level"]) if self._env_data["light_level"] is not None else "unavailable",
                "unit_of_measurement": "lux",
                "device_class": "illuminance",
                "icon": "mdi:brightness-6",
            }
            self._publish_entity(light_entity)
        
        # Battery level (for low-power deployments)
        if self.config.get("low_power_profile", {}).get("enabled", False):
            battery_entity = {
                "id": "wildlife_monitor:system:battery",
                "type": "sensor",
                "friendly_name": "Battery Level",
                "capability": self.cap_id,
                "state": str(self._battery_level) if self._battery_level is not None else "unavailable",
                "unit_of_measurement": "%",
                "device_class": "battery",
                "icon": "mdi:battery",
            }
            self._publish_entity(battery_entity)

    async def _start_monitoring_internal(self) -> None:
        """Start the wildlife monitoring loop."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        
        async def monitoring_loop():
            """Main monitoring loop."""
            monitor_interval = self.config.get("monitoring", {}).get("interval_sec", 5)
            
            while self._monitoring_active:
                try:
                    # Check for motion (placeholder)
                    motion_detected = await self._check_motion()
                    if motion_detected:
                        await self._handle_motion_detected()
                    
                    # Read environmental sensors
                    if self.env_sensors:
                        await self._read_environmental_data()
                    
                    # Read battery level (if low power mode)
                    if self.config.get("low_power_profile", {}).get("enabled", False):
                        await self._read_battery_level()
                    
                    # Update entities
                    await self._update_monitoring_entities()
                    
                except Exception as e:
                    logger.warning("[%s] Monitoring loop error: %s", self.cap_id, e)
                
                await asyncio.sleep(monitor_interval)
        
        self._monitoring_task = asyncio.create_task(monitoring_loop())

    async def _stop_monitoring_internal(self) -> None:
        """Stop the wildlife monitoring loop."""
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    async def _check_motion(self) -> bool:
        """Check for motion detection (placeholder implementation)."""
        # This would integrate with actual motion detection hardware/software
        # For now, return False as placeholder
        return False

    async def _handle_motion_detected(self) -> None:
        """Handle motion detection event."""
        self._last_motion_time = datetime.now()
        logger.info("[%s] Motion detected at %s", self.cap_id, self._last_motion_time)
        
        # Capture photo if configured
        if self.config.get("motion_capture", {}).get("enabled", False):
            await self._trigger_capture()

    async def _read_environmental_data(self) -> None:
        """Read environmental sensor data (placeholder implementation)."""
        # This would integrate with actual environmental sensors
        # For now, set placeholder values
        if self.env_sensors.get("temperature", False):
            self._env_data["temperature"] = 22.5  # Placeholder
        if self.env_sensors.get("humidity", False):
            self._env_data["humidity"] = 65.0  # Placeholder
        if self.env_sensors.get("light", False):
            self._env_data["light_level"] = 150.0  # Placeholder

    async def _read_battery_level(self) -> None:
        """Read battery level (placeholder implementation)."""
        # This would integrate with actual battery monitoring
        self._battery_level = 85  # Placeholder

    async def _update_monitoring_entities(self) -> None:
        """Update all monitoring entities with current data."""
        # Update active status
        active_entity = {
            "id": "wildlife_monitor:system:active",
            "type": "binary_sensor",
            "friendly_name": "Monitoring Active", 
            "capability": self.cap_id,
            "state": "on" if self._monitoring_active else "off",
            "device_class": "running",
            "icon": "mdi:eye",
        }
        self._publish_entity(active_entity)
        
        # Update environmental entities as needed
        await self._create_monitoring_entities()

    async def _trigger_capture(self) -> None:
        """Trigger photo capture on motion (placeholder implementation)."""
        logger.info("[%s] Triggering motion capture", self.cap_id)

    async def _set_motion_capture(self, enabled: bool) -> None:
        """Enable/disable motion-triggered capture."""
        # This would configure motion capture settings
        logger.info("[%s] Motion capture %s", self.cap_id, "enabled" if enabled else "disabled")