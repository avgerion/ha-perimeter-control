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
    direction: str  # "input" or "output"
    pull_mode: str  # "none", "pull_up", or "pull_down" (inputs only)


class GpioControlCapability(CapabilityModule):
    """Capability module for GPIO-backed switch/light entities."""

    def __init__(self, cap_id: str, config: Dict[str, Any], entity_cache, emit_event):
        super().__init__(cap_id, config, entity_cache, emit_event)
        self._pins: Dict[str, PinConfig] = {}
        self._states: Dict[str, bool] = {}
        self._brightness: Dict[str, int] = {}
        self._driver = "none"
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_input_states: Dict[str, bool] = {}  # Track last known state for change detection

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
        
        # Start async monitoring for input pins
        input_pins = [p for p in self._pins.values() if p.direction == "input"]
        if input_pins:
            self._monitor_task = asyncio.create_task(self._monitor_input_pins())
            logger.info("[%s] Started monitoring %d input pins", self.cap_id, len(input_pins))

    async def stop(self) -> None:
        logger.info("[%s] Stopping GPIO control", self.cap_id)
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
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

        # Input pins do not support control actions
        if pin.direction == "input":
            return {"success": False, "error": f"Input pin {entity_id} is read-only"}

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
            if entity_type not in {"switch", "light", "binary_sensor"}:
                errors.append(f"pins[{idx}] type must be 'switch', 'light', or 'binary_sensor'")

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

            # Direction: infer from entity_type or use explicit config
            direction = str(item.get("direction", "")).lower()
            if not direction:
                # Infer: binary_sensor → input, others → output
                direction = "input" if entity_type == "binary_sensor" else "output"
            elif direction not in {"input", "output"}:
                direction = "output"  # Default to output if invalid

            # Pull mode for input pins
            pull_mode = str(item.get("pull_mode", "none")).lower()
            if pull_mode not in {"none", "pull_up", "pull_down"}:
                pull_mode = "none"

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
                direction=direction,
                pull_mode=pull_mode,
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
            "direction": pin.direction,
        }

        # Output pins only
        if pin.direction == "output":
            attrs["turn_on_action_id"] = "turn_on"
            attrs["turn_off_action_id"] = "turn_off"

        if pin.entity_type == "light":
            attrs["brightness"] = brightness
            attrs["brightness_pct"] = round((brightness / 255.0) * 100)

        entity = {
            "id": pin.entity_id,
            "type": pin.entity_type,
            "friendly_name": pin.friendly_name,
            "state": "on" if state_on else "off",
            "icon": pin.icon,
            "attributes": attrs,
        }
        
        # Add action IDs only for output pins
        if pin.direction == "output":
            entity["turn_on_action_id"] = "turn_on"
            entity["turn_off_action_id"] = "turn_off"
        
        logger.info("[%s] Publishing entity: id=%s, type=%s, direction=%s, state=%s", 
                   self.cap_id, pin.entity_id, pin.entity_type, pin.direction, entity["state"])
        self._publish_entity(entity)

    async def _monitor_input_pins(self) -> None:
        """Async task to monitor input pins and publish state changes."""
        poll_interval = 0.5  # Poll input pins every 500ms
        logger.debug("[%s] Input pin monitoring started (interval: %sms)", self.cap_id, poll_interval * 1000)
        
        try:
            while True:
                await asyncio.sleep(poll_interval)
                
                async with self._lock:
                    for entity_id, pin in self._pins.items():
                        if pin.direction != "input":
                            continue
                        
                        # Read current pin state
                        current_state = self._read_pin_state(pin)
                        if current_state is None:
                            continue
                        
                        # Check if state changed
                        last_state = self._last_input_states.get(entity_id)
                        if last_state != current_state:
                            self._last_input_states[entity_id] = current_state
                            self._states[entity_id] = current_state
                            self._publish_pin_entity(pin)
                            logger.info("[%s] Input pin state changed: %s → %s", 
                                       self.cap_id, pin.friendly_name, 
                                       "on" if current_state else "off")
        except asyncio.CancelledError:
            logger.debug("[%s] Input pin monitoring stopped", self.cap_id)
            raise
        except Exception as exc:
            logger.error("[%s] Input pin monitoring error: %s", self.cap_id, exc)

    def _coerce_brightness(self, params: Dict[str, Any]) -> Optional[int]:
        if "brightness" in params:
            value = int(params["brightness"])
            return max(0, min(255, value))
        if "brightness_pct" in params:
            pct = float(params["brightness_pct"])
            pct = max(0.0, min(100.0, pct))
            return round((pct / 100.0) * 255)
        return None

    def _read_pin_state(self, pin: PinConfig) -> Optional[bool]:
        """Read current state of an input pin. Returns True if high, False if low, None if error."""
        if pin.direction != "input":
            return None
        
        if self._driver == "raspi-gpio":
            return self._read_with_raspi_gpio(pin.gpio_pin, pin.active_high)
        elif self._driver == "sysfs":
            return self._read_with_sysfs(pin.gpio_pin, pin.active_high)
        return None

    def _read_with_raspi_gpio(self, gpio_pin: int, active_high: bool) -> Optional[bool]:
        """Read GPIO value using raspi-gpio. Returns state: True if high, False if low."""
        try:
            res = subprocess.run(
                ["raspi-gpio", "get", str(gpio_pin)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2
            )
            if res.returncode == 0:
                # Output format: GPIO 23: level=0 fsel=0
                if "level=1" in res.stdout:
                    level = 1
                elif "level=0" in res.stdout:
                    level = 0
                else:
                    return None
                return bool(level) == active_high
            return None
        except Exception as exc:
            logger.warning("raspi-gpio read failed for GPIO%d: %s", gpio_pin, exc)
            return None

    def _read_with_sysfs(self, gpio_pin: int, active_high: bool) -> Optional[bool]:
        """Read GPIO value from sysfs. Returns state: True if high, False if low."""
        try:
            gpio_path = _SYSFS_GPIO / f"gpio{gpio_pin}"
            value_file = gpio_path / "value"
            if value_file.exists():
                value_str = value_file.read_text(encoding="utf-8").strip()
                level = int(value_str)
                return bool(level) == active_high
            return None
        except Exception as exc:
            logger.warning("sysfs GPIO read failed for GPIO%d: %s", gpio_pin, exc)
            return None

    def _set_pin_state(self, pin: PinConfig, on: bool) -> None:
        # Input pins are read-only; skip state changes
        if pin.direction == "input":
            logger.debug("[%s] Ignoring state change for input pin %s", self.cap_id, pin.friendly_name)
            return
        
        level = 1 if on == pin.active_high else 0
        success = False

        if self._driver == "raspi-gpio":
            success = self._set_with_raspi_gpio(pin.gpio_pin, level, direction="out")
        elif self._driver == "sysfs":
            success = self._set_with_sysfs(pin.gpio_pin, level, direction="out")

        if not success:
            logger.warning("[%s] Failed to drive GPIO%d using %s; state tracked in memory only", self.cap_id, pin.gpio_pin, self._driver)

        self._states[pin.entity_id] = on

    def _setup_pin(self, pin: PinConfig, on: bool) -> None:
        if pin.direction == "input":
            # Setup input pin (level parameter ignored)
            if self._driver == "raspi-gpio":
                self._set_with_raspi_gpio(pin.gpio_pin, 0, direction="in", pull_mode=pin.pull_mode)
            elif self._driver == "sysfs":
                self._set_with_sysfs(pin.gpio_pin, 0, direction="in", pull_mode=pin.pull_mode)
        else:
            # Setup output pin with initial state
            level = 1 if on == pin.active_high else 0
            if self._driver == "raspi-gpio":
                self._set_with_raspi_gpio(pin.gpio_pin, level, direction="out")
            elif self._driver == "sysfs":
                self._set_with_sysfs(pin.gpio_pin, level, direction="out")

    def _set_with_raspi_gpio(self, gpio_pin: int, level: int, direction: str = "out", pull_mode: str = "none") -> bool:
        try:
            if direction == "in":
                # Setup input with optional pull mode: raspi-gpio set <pin> ip [pu|pd|pn]
                pull_arg = ""
                if pull_mode == "pull_up":
                    pull_arg = " pu"
                elif pull_mode == "pull_down":
                    pull_arg = " pd"
                else:
                    pull_arg = " pn"
                cmd = ["raspi-gpio", "set", str(gpio_pin), "ip" + pull_arg]
            else:
                # Setup output: raspi-gpio set <pin> op dh|dl
                cmd = ["raspi-gpio", "set", str(gpio_pin), "op", "dh" if level else "dl"]
            
            res = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                return True
            logger.warning("raspi-gpio failed for GPIO%d: %s", gpio_pin, res.stderr.strip())
            return False
        except Exception as exc:
            logger.warning("raspi-gpio exception for GPIO%d: %s", gpio_pin, exc)
            return False

    def _set_with_sysfs(self, gpio_pin: int, level: int, direction: str = "out", pull_mode: str = "none") -> bool:
        try:
            gpio_path = _SYSFS_GPIO / f"gpio{gpio_pin}"
            export_path = _SYSFS_GPIO / "export"
            if not gpio_path.exists() and export_path.exists():
                export_path.write_text(str(gpio_pin), encoding="utf-8")

            direction_file = gpio_path / "direction"
            value_file = gpio_path / "value"
            
            if direction_file.exists():
                direction_file.write_text(direction, encoding="utf-8")
            
            # Set pull mode via sysfs if available (some implementations support this)
            if direction == "in" and pull_mode != "none":
                pull_file = gpio_path / "bias"
                if pull_file.exists():
                    pull_value = "pull_up" if pull_mode == "pull_up" else "pull_down"
                    try:
                        pull_file.write_text(pull_value, encoding="utf-8")
                    except Exception:
                        # Pull mode not supported, continue anyway
                        pass
            
            # For output pins, set the value
            if direction == "out" and value_file.exists():
                value_file.write_text("1" if level else "0", encoding="utf-8")
                return True
            elif direction == "in":
                # Input pin setup successful
                return True
            return False
        except Exception as exc:
            logger.warning("sysfs GPIO setup failed for GPIO%d: %s", gpio_pin, exc)
            return False
