"""
gpio_control capability module.

Creates switch and light entities backed by Raspberry Pi GPIO output pins.
Configuration example:

pins:
  - id: relay1
    gpio_pin: 17
    type: switch
    friendly_name: Relay 1
    active_high: true
    initial_state: off

  - id: led1
    gpio_pin: 18
    type: light
    friendly_name: Indicator LED
    active_high: true
    initial_brightness: 255
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import CapabilityModule

logger = logging.getLogger(__name__)

_SYSFS_GPIO = Path("/sys/class/gpio")


@dataclass
class PinConfig:
    entity_id: str
    pin_id: str
    gpio_pin: int
    entity_type: str
    friendly_name: str
    icon: str
    active_high: bool
    initial_state: str
    initial_brightness: int


class GpioControlCapability(CapabilityModule):
    """Capability module for GPIO-backed switch/light entities."""

    def __init__(self, cap_id: str, config: Dict[str, Any], entity_cache, emit_event):
        super().__init__(cap_id, config, entity_cache, emit_event)
        self._pins: Dict[str, PinConfig] = {}
        self._states: Dict[str, bool] = {}
        self._brightness: Dict[str, int] = {}
        self._driver = "none"
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("[%s] Starting GPIO control", self.cap_id)
        self._driver = self._detect_driver()
        self._pins = self._load_pin_configs(self.config)

        if not self._pins:
            logger.warning("[%s] No GPIO pins configured (checked nested format services.gpio_control.<instance>.pins and flat format pins)", self.cap_id)
            return

        for entity_id, pin in self._pins.items():
            initial_on = pin.initial_state == "on"
            brightness = pin.initial_brightness if pin.entity_type == "light" else 255
            if not initial_on and pin.entity_type == "light":
                brightness = 0

            self._states[entity_id] = initial_on
            self._brightness[entity_id] = brightness

            self._setup_pin(pin, initial_on)
            self._publish_pin_entity(pin)
            logger.info("[%s] Registered GPIO entity: %s (pin=%d, type=%s, state=%s)", 
                       self.cap_id, pin.friendly_name, pin.gpio_pin, pin.entity_type, pin.initial_state)

        logger.info("[%s] GPIO control started with %d entities using %s", self.cap_id, len(self._pins), self._driver)

    async def stop(self) -> None:
        logger.info("[%s] Stopping GPIO control", self.cap_id)
        self.entity_cache.clear_capability_entities(self.cap_id)

    def get_entities(self) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        for entity_id, entity_data in self.entity_cache.get_by_capability(self.cap_id).items():
            entity = entity_data.copy()
            entity["id"] = entity_id
            entities.append(entity)
        return entities

    async def execute_action(self, action_id: str, params: Dict[str, Any]) -> Any:
        entity_id = str(params.get("entity_id", "")).strip()
        if entity_id not in self._pins:
            return {"success": False, "error": f"Unknown GPIO entity: {entity_id}"}

        pin = self._pins[entity_id]

        async with self._lock:
            if action_id == "turn_on":
                brightness = self._coerce_brightness(params)
                if pin.entity_type == "light" and brightness is not None:
                    self._brightness[entity_id] = brightness
                elif pin.entity_type == "light" and self._brightness.get(entity_id, 0) == 0:
                    self._brightness[entity_id] = 255
                self._set_pin_state(pin, True)

            elif action_id == "turn_off":
                self._set_pin_state(pin, False)
                if pin.entity_type == "light":
                    self._brightness[entity_id] = 0

            elif action_id == "toggle":
                next_state = not self._states.get(entity_id, False)
                self._set_pin_state(pin, next_state)
                if pin.entity_type == "light":
                    self._brightness[entity_id] = 255 if next_state else 0

            elif action_id == "set_brightness":
                if pin.entity_type != "light":
                    raise ValueError(f"set_brightness only supported for light entities: {entity_id}")
                brightness = self._coerce_brightness(params)
                if brightness is None:
                    raise ValueError("set_brightness requires brightness or brightness_pct")
                self._brightness[entity_id] = brightness
                self._set_pin_state(pin, brightness > 0)

            else:
                raise NotImplementedError(f"Unknown action: {action_id}")

            self._publish_pin_entity(pin)

        return {
            "success": True,
            "entity_id": entity_id,
            "state": "on" if self._states.get(entity_id, False) else "off",
            "brightness": self._brightness.get(entity_id),
            "driver": self._driver,
        }

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        
        # Extract pins from nested format (new standard) or flat format (legacy)
        pins_list = []
        
        # Try nested format first
        services = config.get("services", {})
        gpio_control_cfg = services.get("gpio_control", {})
        if isinstance(gpio_control_cfg, dict):
            for instance_name, instance_cfg in gpio_control_cfg.items():
                if isinstance(instance_cfg, dict):
                    instance_pins = instance_cfg.get("pins", [])
                    if isinstance(instance_pins, list):
                        pins_list.extend(instance_pins)
        
        # Fall back to flat format
        if not pins_list:
            pins = config.get("pins", [])
            if isinstance(pins, list):
                pins_list = pins
            else:
                return ["pins must be a list or services.gpio_control.<instance>.pins must be a list"]

        seen_ids: set[str] = set()
        seen_gpio: set[int] = set()

        for idx, item in enumerate(pins_list):
            if not isinstance(item, dict):
                errors.append(f"pins[{idx}] must be a mapping")
                continue

            pin_id = str(item.get("id", "")).strip()
            if not pin_id:
                errors.append(f"pins[{idx}] id is required")
            elif pin_id in seen_ids:
                errors.append(f"pins[{idx}] duplicate id: {pin_id}")
            else:
                seen_ids.add(pin_id)

            gpio_pin = item.get("gpio_pin")
            if not isinstance(gpio_pin, int) or gpio_pin < 0:
                errors.append(f"pins[{idx}] gpio_pin must be a non-negative integer")
            elif gpio_pin in seen_gpio:
                errors.append(f"pins[{idx}] duplicate gpio_pin: {gpio_pin}")
            else:
                seen_gpio.add(gpio_pin)

            entity_type = str(item.get("type", "switch")).lower()
            if entity_type not in {"switch", "light"}:
                errors.append(f"pins[{idx}] type must be 'switch' or 'light'")

        return errors

    def _detect_driver(self) -> str:
        if shutil.which("raspi-gpio"):
            return "raspi-gpio"
        if _SYSFS_GPIO.exists():
            return "sysfs"
        return "none"

    def _load_pin_configs(self, config: Dict[str, Any]) -> Dict[str, PinConfig]:
        out: Dict[str, PinConfig] = {}
        
        # Extract pins from nested format (new standard):
        # services:
        #   gpio_control:
        #     relays:
        #       pins: [...]
        #     lights:
        #       pins: [...]
        pins_list = []
        
        # Try nested format first
        services = config.get("services", {})
        gpio_control_cfg = services.get("gpio_control", {})
        if isinstance(gpio_control_cfg, dict):
            # Iterate over instances (relays, lights, inputs, etc.)
            for instance_name, instance_cfg in gpio_control_cfg.items():
                if isinstance(instance_cfg, dict):
                    instance_pins = instance_cfg.get("pins", [])
                    if isinstance(instance_pins, list):
                        pins_list.extend(instance_pins)
        
        # Fall back to flat format (old):
        # pins: [...]
        if not pins_list:
            pins_list = config.get("pins", [])
        
        for item in pins_list:
            if not isinstance(item, dict):
                continue

            pin_id = str(item.get("id", "")).strip()
            if not pin_id:
                continue

            gpio_pin = int(item.get("gpio_pin"))
            entity_type = str(item.get("type", "switch")).lower()
            friendly_name = str(item.get("friendly_name") or pin_id.replace("_", " ").title())
            icon = str(item.get("icon") or ("mdi:lightbulb" if entity_type == "light" else "mdi:toggle-switch"))
            active_high = bool(item.get("active_high", True))
            initial_state = str(item.get("initial_state", "off")).strip().lower()
            if initial_state not in {"on", "off"}:
                initial_state = "off"
            initial_brightness = int(item.get("initial_brightness", 255))
            initial_brightness = max(0, min(255, initial_brightness))

            slug = re.sub(r"[^a-z0-9_]+", "_", pin_id.lower()).strip("_")
            if not slug:
                slug = f"pin_{gpio_pin}"
            entity_id = f"gpio_control:{entity_type}:{slug}"

            out[entity_id] = PinConfig(
                entity_id=entity_id,
                pin_id=pin_id,
                gpio_pin=gpio_pin,
                entity_type=entity_type,
                friendly_name=friendly_name,
                icon=icon,
                active_high=active_high,
                initial_state=initial_state,
                initial_brightness=initial_brightness,
            )
        return out

    def _publish_pin_entity(self, pin: PinConfig) -> None:
        state_on = self._states.get(pin.entity_id, False)
        brightness = self._brightness.get(pin.entity_id, 255 if state_on else 0)
        attrs: Dict[str, Any] = {
            "gpio_pin": pin.gpio_pin,
            "pin_id": pin.pin_id,
            "active_high": pin.active_high,
            "driver": self._driver,
            "turn_on_action_id": "turn_on",
            "turn_off_action_id": "turn_off",
        }

        if pin.entity_type == "light":
            attrs["brightness"] = brightness
            attrs["brightness_pct"] = round((brightness / 255.0) * 100)

        entity = {
            "id": pin.entity_id,
            "type": pin.entity_type,
            "friendly_name": pin.friendly_name,
            "capability": self.cap_id,
            "state": "on" if state_on else "off",
            "icon": pin.icon,
            "attributes": attrs,
            "turn_on_action_id": "turn_on",
            "turn_off_action_id": "turn_off",
        }
        self._publish_entity(entity)

    def _coerce_brightness(self, params: Dict[str, Any]) -> Optional[int]:
        if "brightness" in params:
            value = int(params["brightness"])
            return max(0, min(255, value))
        if "brightness_pct" in params:
            pct = float(params["brightness_pct"])
            pct = max(0.0, min(100.0, pct))
            return round((pct / 100.0) * 255)
        return None

    def _set_pin_state(self, pin: PinConfig, on: bool) -> None:
        level = 1 if on == pin.active_high else 0
        success = False

        if self._driver == "raspi-gpio":
            success = self._set_with_raspi_gpio(pin.gpio_pin, level)
        elif self._driver == "sysfs":
            success = self._set_with_sysfs(pin.gpio_pin, level)

        if not success:
            logger.warning("[%s] Failed to drive GPIO%d using %s; state tracked in memory only", self.cap_id, pin.gpio_pin, self._driver)

        self._states[pin.entity_id] = on

    def _setup_pin(self, pin: PinConfig, on: bool) -> None:
        level = 1 if on == pin.active_high else 0
        if self._driver == "raspi-gpio":
            self._set_with_raspi_gpio(pin.gpio_pin, level)
        elif self._driver == "sysfs":
            self._set_with_sysfs(pin.gpio_pin, level)

    def _set_with_raspi_gpio(self, gpio_pin: int, level: int) -> bool:
        cmd = ["raspi-gpio", "set", str(gpio_pin), "op", "dh" if level else "dl"]
        try:
            res = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                return True
            logger.warning("raspi-gpio failed for GPIO%d: %s", gpio_pin, res.stderr.strip())
            return False
        except Exception as exc:
            logger.warning("raspi-gpio exception for GPIO%d: %s", gpio_pin, exc)
            return False

    def _set_with_sysfs(self, gpio_pin: int, level: int) -> bool:
        try:
            gpio_path = _SYSFS_GPIO / f"gpio{gpio_pin}"
            export_path = _SYSFS_GPIO / "export"
            if not gpio_path.exists() and export_path.exists():
                export_path.write_text(str(gpio_pin), encoding="utf-8")

            direction = gpio_path / "direction"
            value = gpio_path / "value"
            if direction.exists():
                direction.write_text("out", encoding="utf-8")
            if value.exists():
                value.write_text("1" if level else "0", encoding="utf-8")
                return True
            return False
        except Exception as exc:
            logger.warning("sysfs GPIO write failed for GPIO%d: %s", gpio_pin, exc)
            return False
