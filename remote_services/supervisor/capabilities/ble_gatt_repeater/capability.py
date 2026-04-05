"""
ble_gatt_repeater capability module.

Implements a Bluetooth Proxy that:
- Scans for BLE devices and advertisements
- Creates HA entities for discovered devices
- Forwards sensor data (especially weight from scales)
- Supports passive scanning and active connections
- Auto-discovers common device types (scales, thermometers, etc.)

Entities created:
  ble_gatt_repeater:<device_id>:rssi          → sensor (signal strength)
  ble_gatt_repeater:<device_id>:battery       → sensor (battery level)
  ble_gatt_repeater:<device_id>:weight        → sensor (for scales)
  ble_gatt_repeater:<device_id>:temperature   → sensor (for thermometers)
  ble_gatt_repeater:<device_id>:connected     → binary_sensor (connection status)

Actions:
  scan_devices     — trigger manual scan for new devices
  connect_device   — establish active connection to specific device
  disconnect_device — disconnect from specific device
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    
from ..base import CapabilityModule

logger = logging.getLogger(__name__)

# Known BLE device types and their characteristics
BLE_DEVICE_TYPES = {
    "weight_scale": {
        "services": ["0000181b-0000-1000-8000-00805f9b34fb"],  # Weight Scale Service
        "characteristics": {
            "weight": "00002a9c-0000-1000-8000-00805f9b34fb",  # Weight Measurement
            "body_composition": "00002a9b-0000-1000-8000-00805f9b34fb"
        },
        "name_patterns": ["scale", "weight", "kg", "lb", "omron", "tanita", "withings"]
    },
    "thermometer": {
        "services": ["00001809-0000-1000-8000-00805f9b34fb"],  # Health Thermometer
        "characteristics": {
            "temperature": "00002a1c-0000-1000-8000-00805f9b34fb",  # Temperature Measurement
        },
        "name_patterns": ["temp", "thermometer", "fever", "thermal"]
    },
    "heart_rate": {
        "services": ["0000180d-0000-1000-8000-00805f9b34fb"],  # Heart Rate Service
        "characteristics": {
            "heart_rate": "00002a37-0000-1000-8000-00805f9b34fb",  # Heart Rate Measurement
        },
        "name_patterns": ["heart", "hr", "pulse", "cardio", "polar", "garmin"]
    },
    "battery": {
        "services": ["0000180f-0000-1000-8000-00805f9b34fb"],  # Battery Service  
        "characteristics": {
            "battery_level": "00002a19-0000-1000-8000-00805f9b34fb",  # Battery Level
        }
    }
}


class BleGattRepeaterCapability(CapabilityModule):
    """Bluetooth Proxy capability module."""

    def __init__(self, cap_id: str, config: Dict[str, Any], entity_cache, emit_event):
        super().__init__(cap_id, config, entity_cache, emit_event)
        self._scanning = False
        self._scan_task: Optional[asyncio.Task] = None
        self._connected_devices: Dict[str, BleakClient] = {}
        self._discovered_devices: Dict[str, Dict[str, Any]] = {}
        
    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start BLE scanning and device discovery."""
        logger.info("[%s] Starting BLE GATT Repeater", self.cap_id)
        
        if not BLEAK_AVAILABLE:
            raise RuntimeError("bleak library not available - install with: pip install bleak")
            
        # Start continuous BLE scanning
        await self._start_scanning()
        
        logger.info("[%s] BLE GATT Repeater started", self.cap_id)

    async def stop(self) -> None:
        """Stop BLE scanning and disconnect devices."""
        logger.info("[%s] Stopping BLE GATT Repeater", self.cap_id)
        
        # Stop scanning
        await self._stop_scanning()
        
        # Disconnect all devices
        for device_id, client in list(self._connected_devices.items()):
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception as e:
                logger.warning("[%s] Error disconnecting %s: %s", self.cap_id, device_id, e)
        
        self._connected_devices.clear()
        self.entity_cache.clear_capability_entities(self.cap_id)

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_entities(self) -> List[Dict[str, Any]]:
        """Return entities for all discovered BLE devices."""
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
        """Simple health check - scanning should be active."""
        return {
            "type": "custom",
            "check": lambda: self._scanning,
            "timeout_sec": 5,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        """Execute BLE actions."""
        if action_id == "scan_devices":
            await self._trigger_discovery_scan()
            return {"message": "Device scan triggered"}
            
        elif action_id == "connect_device":
            device_id = params.get("device_id")
            if not device_id:
                raise ValueError("device_id parameter required")
            return await self._connect_device(device_id)
            
        elif action_id == "disconnect_device":
            device_id = params.get("device_id")
            if not device_id:
                raise ValueError("device_id parameter required")
            return await self._disconnect_device(device_id)
            
        raise NotImplementedError(f"Unknown action: {action_id}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate BLE configuration."""
        errors: List[str] = []
        
        scan_interval = config.get("scan_interval", 30)
        if not isinstance(scan_interval, (int, float)) or scan_interval < 5:
            errors.append("scan_interval must be a number >= 5 seconds")
            
        return errors

    # ------------------------------------------------------------------
    # BLE Scanning
    # ------------------------------------------------------------------

    async def _start_scanning(self) -> None:
        """Start continuous BLE scanning."""
        if self._scanning:
            return
            
        self._scanning = True
        scan_interval = self.config.get("scan_interval", 30)
        
        async def scan_loop():
            """Continuous scanning loop."""
            while self._scanning:
                try:
                    await self._perform_scan()
                except Exception as e:
                    logger.warning("[%s] Scan error: %s", self.cap_id, e)
                
                # Wait before next scan
                await asyncio.sleep(scan_interval)
        
        self._scan_task = asyncio.create_task(scan_loop())

    async def _stop_scanning(self) -> None:
        """Stop BLE scanning."""
        self._scanning = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

    async def _perform_scan(self) -> None:
        """Perform BLE device scan and update entities."""
        try:
            devices = await BleakScanner.discover()
            
            for device in devices:
                device_id = self._get_device_id(device)
                
                # Update device info
                self._discovered_devices[device_id] = {
                    "address": device.address,
                    "name": device.name or "Unknown Device",
                    "rssi": device.rssi if hasattr(device, 'rssi') else None,
                    "last_seen": datetime.now(),
                    "device_type": self._detect_device_type(device),
                }
                
                # Create/update entities for this device
                await self._update_device_entities(device_id, device)
                
        except Exception as e:
            logger.error("[%s] BLE scan failed: %s", self.cap_id, e)

    async def _trigger_discovery_scan(self) -> None:
        """Trigger immediate discovery scan."""
        await self._perform_scan()

    # ------------------------------------------------------------------
    # Device Management
    # ------------------------------------------------------------------

    def _get_device_id(self, device: BLEDevice) -> str:
        """Generate consistent device ID from BLE device."""
        # Use MAC address as device ID, normalize format
        return device.address.lower().replace(":", "_")

    def _detect_device_type(self, device: BLEDevice) -> str:
        """Detect BLE device type based on services and name."""
        device_name = (device.name or "").lower()
        
        # Check name patterns first
        for device_type, info in BLE_DEVICE_TYPES.items():
            if device_type == "battery":  # Skip generic battery service
                continue
            name_patterns = info.get("name_patterns", [])
            if any(pattern in device_name for pattern in name_patterns):
                return device_type
        
        # TODO: Check service UUIDs when available in advertisement data
        # This would require connecting to device to discover services
        
        return "generic"

    async def _update_device_entities(self, device_id: str, device: BLEDevice) -> None:
        """Create/update entities for a BLE device."""
        device_info = self._discovered_devices[device_id]
        device_name = device_info["name"]
        device_type = device_info["device_type"]
        
        # RSSI sensor (signal strength)
        if device_info.get("rssi") is not None:
            rssi_entity = {
                "id": f"ble_gatt_repeater:{device_id}:rssi",
                "type": "sensor",
                "friendly_name": f"{device_name} Signal Strength",
                "capability": self.cap_id,
                "state": str(device_info["rssi"]),
                "unit_of_measurement": "dBm",
                "device_class": "signal_strength",
                "icon": "mdi:bluetooth",
                "attributes": {
                    "address": device.address,
                    "device_type": device_type,
                    "last_seen": device_info["last_seen"].isoformat(),
                }
            }
            self._publish_entity(rssi_entity)

        # Connection status binary sensor
        connected_entity = {
            "id": f"ble_gatt_repeater:{device_id}:connected",
            "type": "binary_sensor", 
            "friendly_name": f"{device_name} Connected",
            "capability": self.cap_id,
            "state": "on" if device_id in self._connected_devices else "off",
            "device_class": "connectivity",
            "icon": "mdi:bluetooth-connect",
            "attributes": {
                "address": device.address,
                "device_type": device_type,
            }
        }
        self._publish_entity(connected_entity)

        # Create device-type-specific entities
        if device_type == "weight_scale":
            await self._create_weight_scale_entities(device_id, device_name)
        elif device_type == "thermometer":
            await self._create_thermometer_entities(device_id, device_name)
        elif device_type == "heart_rate":
            await self._create_heart_rate_entities(device_id, device_name)

    async def _create_weight_scale_entities(self, device_id: str, device_name: str) -> None:
        """Create entities specific to weight scales."""
        # Weight measurement sensor (placeholder value - updated when connected)
        weight_entity = {
            "id": f"ble_gatt_repeater:{device_id}:weight",
            "type": "sensor",
            "friendly_name": f"{device_name} Weight",
            "capability": self.cap_id,
            "state": "unavailable",  # Will be updated when device is connected
            "unit_of_measurement": "kg",
            "device_class": "weight", 
            "icon": "mdi:scale-bathroom",
            "attributes": {
                "measurement_unit": self.config.get("weight_unit", "kg"),
            }
        }
        self._publish_entity(weight_entity)

    async def _create_thermometer_entities(self, device_id: str, device_name: str) -> None:
        """Create entities specific to thermometers."""
        temp_entity = {
            "id": f"ble_gatt_repeater:{device_id}:temperature",
            "type": "sensor",
            "friendly_name": f"{device_name} Temperature", 
            "capability": self.cap_id,
            "state": "unavailable",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "icon": "mdi:thermometer",
        }
        self._publish_entity(temp_entity)

    async def _create_heart_rate_entities(self, device_id: str, device_name: str) -> None:
        """Create entities for heart rate monitors."""
        hr_entity = {
            "id": f"ble_gatt_repeater:{device_id}:heart_rate",
            "type": "sensor", 
            "friendly_name": f"{device_name} Heart Rate",
            "capability": self.cap_id,
            "state": "unavailable",
            "unit_of_measurement": "bpm",
            "icon": "mdi:heart-pulse",
        }
        self._publish_entity(hr_entity)

    # ------------------------------------------------------------------
    # Device Connection & Data Reading
    # ------------------------------------------------------------------

    async def _connect_device(self, device_id: str) -> Dict[str, Any]:
        """Connect to a BLE device and start reading data."""
        if device_id in self._connected_devices:
            return {"message": "Device already connected"}
            
        device_info = self._discovered_devices.get(device_id)
        if not device_info:
            raise ValueError("Device not found - run scan first")
            
        try:
            client = BleakClient(device_info["address"])
            await client.connect()
            
            self._connected_devices[device_id] = client
            
            # Update connection status entity
            connected_entity_id = f"ble_gatt_repeater:{device_id}:connected"
            if connected_entity_id in self.entity_cache._entities:
                entity = self.entity_cache._entities[connected_entity_id].copy()
                entity["id"] = connected_entity_id  # Add missing id field
                entity["state"] = "on"
                self._publish_entity(entity)
            
            # Start reading device-specific data
            await self._start_device_data_reading(device_id, client)
            
            logger.info("[%s] Connected to device %s", self.cap_id, device_id)
            return {"message": f"Connected to {device_info['name']}"}
            
        except Exception as e:
            logger.error("[%s] Failed to connect to %s: %s", self.cap_id, device_id, e)
            raise

    async def _disconnect_device(self, device_id: str) -> Dict[str, Any]:
        """Disconnect from a BLE device."""
        client = self._connected_devices.get(device_id)
        if not client:
            return {"message": "Device not connected"}
            
        try:
            await client.disconnect()
            del self._connected_devices[device_id]
            
            # Update connection status
            connected_entity_id = f"ble_gatt_repeater:{device_id}:connected"
            if connected_entity_id in self.entity_cache._entities:
                entity = self.entity_cache._entities[connected_entity_id].copy()
                entity["id"] = connected_entity_id  # Add missing id field
                entity["state"] = "off"
                self._publish_entity(entity)
            
            return {"message": "Device disconnected"}
            
        except Exception as e:
            logger.error("[%s] Failed to disconnect %s: %s", self.cap_id, device_id, e)
            raise

    async def _start_device_data_reading(self, device_id: str, client: BleakClient) -> None:
        """Start reading data from connected device based on its type."""
        device_info = self._discovered_devices[device_id]
        device_type = device_info["device_type"]
        
        if device_type == "weight_scale":
            await self._read_scale_data(device_id, client)
        elif device_type == "thermometer":
            await self._read_temperature_data(device_id, client) 
        elif device_type == "heart_rate":
            await self._read_heart_rate_data(device_id, client)
            
        # Always try to read battery level
        await self._read_battery_data(device_id, client)

    async def _read_scale_data(self, device_id: str, client: BleakClient) -> None:
        """Read weight data from scale."""
        try:
            weight_char_uuid = BLE_DEVICE_TYPES["weight_scale"]["characteristics"]["weight"]
            
            def weight_notification_handler(sender, data):
                """Handle weight measurement notifications."""
                try:
                    # Parse weight measurement (simplified - real parsing depends on device)
                    # Standard weight measurement format: flags(1) + weight(2) + ...
                    if len(data) >= 3:
                        weight_raw = struct.unpack('<H', data[1:3])[0]  # Little-endian 16-bit
                        weight_kg = weight_raw / 100.0  # Convert to kg (depends on device)
                        
                        # Update weight entity
                        weight_entity_id = f"ble_gatt_repeater:{device_id}:weight"
                        if weight_entity_id in self.entity_cache._entities:
                            entity = self.entity_cache._entities[weight_entity_id].copy()
                            entity["id"] = weight_entity_id  # Add missing id field
                            entity["state"] = f"{weight_kg:.1f}"
                            entity["attributes"]["last_measurement"] = datetime.now().isoformat()
                            self._publish_entity(entity)
                            
                        logger.info("[%s] Weight reading: %.1f kg", self.cap_id, weight_kg)
                except Exception as e:
                    logger.warning("[%s] Error parsing weight data: %s", self.cap_id, e)
            
            # Subscribe to weight notifications
            await client.start_notify(weight_char_uuid, weight_notification_handler)
            
        except Exception as e:
            logger.warning("[%s] Could not set up weight notifications: %s", self.cap_id, e)

    async def _read_temperature_data(self, device_id: str, client: BleakClient) -> None:
        """Read temperature data from thermometer.""" 
        try:
            temp_char_uuid = BLE_DEVICE_TYPES["thermometer"]["characteristics"]["temperature"]
            
            def temp_notification_handler(sender, data):
                """Handle temperature measurement notifications."""
                try:
                    if len(data) >= 5:
                        # Temperature measurement format: flags(1) + temp(4)
                        temp_raw = struct.unpack('<I', data[1:5])[0] 
                        temp_celsius = temp_raw / 100.0  # Device-specific scaling
                        
                        # Update temperature entity
                        temp_entity_id = f"ble_gatt_repeater:{device_id}:temperature"
                        if temp_entity_id in self.entity_cache._entities:
                            entity = self.entity_cache._entities[temp_entity_id].copy()
                            entity["id"] = temp_entity_id  # Add missing id field
                            entity["state"] = f"{temp_celsius:.1f}"
                            entity["attributes"]["last_measurement"] = datetime.now().isoformat()
                            self._publish_entity(entity)
                            
                        logger.info("[%s] Temperature reading: %.1f°C", self.cap_id, temp_celsius)
                except Exception as e:
                    logger.warning("[%s] Error parsing temperature data: %s", self.cap_id, e)
            
            await client.start_notify(temp_char_uuid, temp_notification_handler)
            
        except Exception as e:
            logger.warning("[%s] Could not set up temperature notifications: %s", self.cap_id, e)

    async def _read_heart_rate_data(self, device_id: str, client: BleakClient) -> None:
        """Read heart rate data."""
        try:
            hr_char_uuid = BLE_DEVICE_TYPES["heart_rate"]["characteristics"]["heart_rate"]
            
            def hr_notification_handler(sender, data):
                """Handle heart rate notifications."""
                try:
                    if len(data) >= 2:
                        # Heart rate format: flags(1) + hr(1 or 2 bytes)
                        flags = data[0]
                        if flags & 0x01:  # 16-bit heart rate 
                            hr_value = struct.unpack('<H', data[1:3])[0]
                        else:  # 8-bit heart rate
                            hr_value = data[1]
                        
                        # Update heart rate entity
                        hr_entity_id = f"ble_gatt_repeater:{device_id}:heart_rate"
                        if hr_entity_id in self.entity_cache._entities:
                            entity = self.entity_cache._entities[hr_entity_id].copy()
                            entity["id"] = hr_entity_id  # Add missing id field
                            entity["state"] = str(hr_value)
                            entity["attributes"]["last_measurement"] = datetime.now().isoformat()
                            self._publish_entity(entity)
                            
                        logger.info("[%s] Heart rate reading: %d bpm", self.cap_id, hr_value)
                except Exception as e:
                    logger.warning("[%s] Error parsing heart rate data: %s", self.cap_id, e)
            
            await client.start_notify(hr_char_uuid, hr_notification_handler)
            
        except Exception as e:
            logger.warning("[%s] Could not set up heart rate notifications: %s", self.cap_id, e)

    async def _read_battery_data(self, device_id: str, client: BleakClient) -> None:
        """Read battery level if available."""
        try:
            battery_char_uuid = BLE_DEVICE_TYPES["battery"]["characteristics"]["battery_level"]
            
            # Read battery level (single read, not notification)
            battery_data = await client.read_gatt_char(battery_char_uuid)
            battery_level = battery_data[0]  # Single byte 0-100%
            
            # Create battery entity if not exists
            battery_entity_id = f"ble_gatt_repeater:{device_id}:battery"
            device_name = self._discovered_devices[device_id]["name"]
            
            battery_entity = {
                "id": battery_entity_id,
                "type": "sensor",
                "friendly_name": f"{device_name} Battery",
                "capability": self.cap_id,
                "state": str(battery_level),
                "unit_of_measurement": "%",
                "device_class": "battery",
                "icon": "mdi:battery",
                "attributes": {
                    "last_reading": datetime.now().isoformat(),
                }
            }
            self._publish_entity(battery_entity)
            
            logger.info("[%s] Battery level: %d%%", self.cap_id, battery_level)
            
        except Exception as e:
            logger.debug("[%s] No battery service available: %s", self.cap_id, e)