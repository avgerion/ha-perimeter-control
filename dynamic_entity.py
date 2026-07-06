"""Dynamic entities created from Supervisor API entity schema."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.camera import Camera
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, CONF_SUPERVISOR_PORT, DEFAULT_API_PORT
from .coordinator import PerimeterControlCoordinator

_LOGGER = logging.getLogger(__name__)


class SupervisorEntity(Entity):
    """Base entity class for entities created from Supervisor API schema."""

    def __init__(
        self,
        coordinator: PerimeterControlCoordinator,
        entity_schema: Dict[str, Any],
        dimension_values: Optional[Dict[str, str]] = None,
    ) -> None:
        self.coordinator = coordinator
        self.entity_schema = entity_schema
        self.dimension_values = dimension_values or {}
        
        # Build entity ID from schema + dimensions
        base_id = entity_schema.get("id", "unknown")
        if dimension_values:
            dimension_suffix = "_".join(f"{k}_{v}" for k, v in dimension_values.items())
            self._entity_id = f"{base_id}_{dimension_suffix}"
        else:
            self._entity_id = base_id
        
        self._attr_unique_id = f"{coordinator._entry.entry_id}_{self._entity_id}"
        
        # Generate name from template or schema
        name_template = entity_schema.get("friendly_name_template")
        if name_template and dimension_values:
            try:
                self._attr_name = name_template.format(**dimension_values)
            except (KeyError, ValueError):
                self._attr_name = entity_schema.get("friendly_name", self._entity_id)
        else:
            self._attr_name = entity_schema.get("friendly_name", self._entity_id)
        
        self._attr_should_poll = False
        self._attr_icon = entity_schema.get("icon")

    @property
    def available(self) -> bool:
        """Return True if entity should be available."""
        # Check if entity appears in current Supervisor entity list
        supervisor_entities = self.coordinator.data.get("supervisor_entities", [])
        entity_exists = any(
            entity.get("id") == self.entity_schema.get("id")
            for entity in supervisor_entities
        )

        # Treat schema presence + healthy supervisor as available.
        # State payloads can arrive after entity discovery and should not force
        # entities into a permanent unavailable/disconnected state.
        supervisor_active = bool(self.coordinator.data.get("supervisor_active", False))
        return entity_exists and supervisor_active

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "entity_id": self._entity_id,
            "capability": self.entity_schema.get("capability_id"),
            "entity_type": self.entity_schema.get("type"),
        }
        
        # Add dimension values as attributes
        if self.dimension_values:
            attrs.update(self.dimension_values)
            
        # Add any additional attributes from current state
        entity_states = self.coordinator.data.get("entity_states", {})
        current_state = entity_states.get(self._entity_id, {})
        if "attributes" in current_state:
            attrs.update(current_state["attributes"])

        pin_label = self._gpio_pin_label()
        if pin_label:
            attrs["gpio_pin_label"] = pin_label
            
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        entry = self.coordinator._entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or f"Perimeter Node {entry.data.get('host')}",
            manufacturer="PerimeterControl",
            model="Pi Node",
            configuration_url=f"http://{entry.data.get('host')}:{entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)}/",
            sw_version=None,
        )

    def _get_current_state(self) -> Dict[str, Any]:
        """Get current state from coordinator data."""
        entity_states = self.coordinator.data.get("entity_states", {})
        entity_data = entity_states.get(self._entity_id)

        if entity_data is None:
            base_id = self.entity_schema.get("id")
            if isinstance(base_id, str) and base_id:
                entity_data = entity_states.get(base_id)
            _LOGGER.debug(
                "[DEBUG] Entity %s (expanded ID: %s) missing state, tried base ID: %s. State found: %s",
                getattr(self, '_attr_name', self._entity_id),
                self._entity_id,
                base_id,
                bool(entity_data)
            )

        if entity_data is None:
            entity_data = {}

        current: Any = entity_data
        # Defensively unwrap nested payloads like {"state": {"state": "...", ...}}.
        for _ in range(3):
            if not isinstance(current, dict):
                break
            nested_state = current.get("state")
            if isinstance(nested_state, dict):
                current = nested_state
                continue
            break

        if isinstance(current, dict):
            return current
        return {"state": current}

    def _gpio_pin_label(self) -> str | None:
        """Return normalized GPIO pin label from schema/state attributes."""
        attrs = self._get_current_state().get("attributes", {})

        gpio_pin = attrs.get("gpio_pin")
        if gpio_pin is None:
            gpio_pin = attrs.get("pin")
        if gpio_pin is None:
            gpio_pin = attrs.get("bcm_pin")
        if gpio_pin is None:
            gpio_pin = attrs.get("gpio")
        if gpio_pin is None:
            gpio_pin = self.entity_schema.get("gpio_pin")

        if gpio_pin is not None:
            return f"GPIO {gpio_pin}"

        line = attrs.get("line")
        if line is None:
            line = attrs.get("line_offset")
        if line is None:
            line = attrs.get("gpio_line")
        chip = attrs.get("chip") or attrs.get("gpio_chip")

        if line is not None and chip is not None:
            return f"{chip} line {line}"
        if line is not None:
            return f"line {line}"

        # Fallback: infer GPIO pin from entity ID patterns like gpio17, gpio_17, gpio-17.
        match = re.search(r"gpio[_:-]?(\d+)", self._entity_id, re.IGNORECASE)
        if match:
            return f"GPIO {match.group(1)}"

        return None

    def _append_gpio_pin_to_name(self) -> None:
        """Append GPIO pin identifier to entity display name when available."""
        pin_label = self._gpio_pin_label()
        if not pin_label:
            return

        current_name = self._attr_name or self._entity_id
        if pin_label in current_name:
            return

        self._attr_name = f"{current_name} ({pin_label})"


class DynamicSensorEntity(SupervisorEntity, SensorEntity):
    """Sensor entity created from Supervisor schema."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        current_state = self._get_current_state()
        return current_state.get("state")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        # Try template from schema with dimension values
        unit_template = self.entity_schema.get("unit_of_measurement_template")
        if unit_template and self.dimension_values:
            try:
                return unit_template.format(**self.dimension_values)
            except (KeyError, ValueError):
                pass
        
        # Fall back to static unit or current state
        schema_unit = self.entity_schema.get("unit_of_measurement")
        if schema_unit:
            return schema_unit
            
        current_state = self._get_current_state()
        return current_state.get("unit_of_measurement")

    @property
    def state_class(self) -> str | None:
        """Return state class."""
        current_state = self._get_current_state()
        return current_state.get("state_class")


class DynamicBinarySensorEntity(SupervisorEntity, BinarySensorEntity):
    """Binary sensor entity created from Supervisor schema."""

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        current_state = self._get_current_state()
        state_value = current_state.get("state")
        
        if isinstance(state_value, bool):
            return state_value
        elif isinstance(state_value, str):
            return state_value.lower() in ("true", "on", "1", "active", "yes")
        
        return None

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self.entity_schema.get("device_class")


class DynamicButtonEntity(SupervisorEntity, ButtonEntity):
    """Button entity created from Supervisor schema."""

    async def async_press(self) -> None:
        """Handle button press."""
        # For now, just fire an event - can be extended to trigger Supervisor actions
        action_id = self.entity_schema.get("action_id", "button_press")
        capability = self.entity_schema.get("capability_id")
        
        self.hass.bus.async_fire(
            "perimeter_control_button_press",
            {
                "entity_id": self._entity_id,
                "action_id": action_id,
                "capability": capability,
                "entry_id": self.coordinator._entry.entry_id,
                "dimension_values": self.dimension_values,
            }
        )


class DynamicSwitchEntity(SupervisorEntity, SwitchEntity):
    """Switch entity created from Supervisor schema."""

    def __init__(
        self,
        coordinator: PerimeterControlCoordinator,
        entity_schema: Dict[str, Any],
        dimension_values: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(coordinator, entity_schema, dimension_values)
        self._append_gpio_pin_to_name()

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        current_state = self._get_current_state()
        value = current_state.get("state")

        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)

        state = str(value).strip().lower()
        return state in {"on", "true", "1", "active", "enabled", "open"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on via capability action."""
        await self._call_capability_action(
            self.entity_schema.get("turn_on_action_id")
            or self.entity_schema.get("turn_on_action")
            or "turn_on",
            {"entity_id": self._entity_id},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off via capability action."""
        await self._call_capability_action(
            self.entity_schema.get("turn_off_action_id")
            or self.entity_schema.get("turn_off_action")
            or "turn_off",
            {"entity_id": self._entity_id},
        )

    async def _call_capability_action(self, action_id: str, payload: Dict[str, Any]) -> None:
        """Call supervisor capability action for this entity."""
        capability = self.entity_schema.get("capability_id")
        if not capability:
            _LOGGER.debug("No capability found for switch entity %s", self._entity_id)
            return

        await self.coordinator._supervisor_post(
            f"/capabilities/{capability}/actions/{action_id}",
            payload,
        )
        await self.coordinator.async_request_refresh()


class DynamicLightEntity(SupervisorEntity, LightEntity):
    """Light entity created from Supervisor schema."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: PerimeterControlCoordinator,
        entity_schema: Dict[str, Any],
        dimension_values: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(coordinator, entity_schema, dimension_values)
        self._append_gpio_pin_to_name()

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        current_state = self._get_current_state()
        value = current_state.get("state")

        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)

        state = str(value).strip().lower()
        return state in {"on", "true", "1", "active", "enabled"}

    @property
    def brightness(self) -> int | None:
        """Return brightness on a 0-255 scale when provided by supervisor."""
        attrs = self._get_current_state().get("attributes", {})

        if isinstance(attrs.get("brightness"), (int, float)):
            level = int(attrs["brightness"])
            return max(0, min(255, level))

        if isinstance(attrs.get("brightness_pct"), (int, float)):
            pct = float(attrs["brightness_pct"])
            return max(0, min(255, round((pct / 100.0) * 255)))

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on via capability action."""
        payload: Dict[str, Any] = {"entity_id": self._entity_id}

        if "brightness" in kwargs and kwargs["brightness"] is not None:
            brightness = int(kwargs["brightness"])
            brightness = max(0, min(255, brightness))
            payload["brightness"] = brightness
            payload["brightness_pct"] = round((brightness / 255.0) * 100)

        await self._call_capability_action(
            self.entity_schema.get("turn_on_action_id")
            or self.entity_schema.get("turn_on_action")
            or "turn_on",
            payload,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off via capability action."""
        await self._call_capability_action(
            self.entity_schema.get("turn_off_action_id")
            or self.entity_schema.get("turn_off_action")
            or "turn_off",
            {"entity_id": self._entity_id},
        )

    async def _call_capability_action(self, action_id: str, payload: Dict[str, Any]) -> None:
        """Call supervisor capability action for this entity."""
        capability = self.entity_schema.get("capability_id")
        if not capability:
            _LOGGER.debug("No capability found for light entity %s", self._entity_id)
            return

        await self.coordinator._supervisor_post(
            f"/capabilities/{capability}/actions/{action_id}",
            payload,
        )
        await self.coordinator.async_request_refresh()


class DynamicCameraEntity(SupervisorEntity, Camera):
    """Camera entity created from Supervisor schema."""

    def __init__(
        self,
        coordinator: PerimeterControlCoordinator,
        entity_schema: Dict[str, Any], 
        dimension_values: Optional[Dict[str, str]] = None,
    ) -> None:
        try:
            super().__init__(coordinator, entity_schema, dimension_values)
            # Initialize Camera with required parameters
            Camera.__init__(self)
        except Exception as e:
            _LOGGER.error("Failed to initialize camera entity: %s", e, exc_info=True)
            # Re-raise to let the parent error handler deal with it
            raise
        
    @property
    def is_streaming(self) -> bool:
        """Return True if the camera is streaming."""
        current_state = self._get_current_state()
        attrs = current_state.get("attributes", {})

        # Prefer explicit streaming flags from API attributes when present.
        for key in ("streaming", "is_streaming"):
            if key in attrs and isinstance(attrs[key], bool):
                return attrs[key]

        state_value = str(current_state.get("state", "")).strip().lower()
        # Camera is considered streaming unless explicitly offline.
        return state_value not in {"", "unavailable", "offline", "unknown", "disconnected", "stopped"}
    
    @property
    def available(self) -> bool:
        """Return True if camera is available."""
        if not super().available:
            return False

        current_state = self._get_current_state()
        attrs = current_state.get("attributes", {})

        # If state data has not arrived yet, keep entity available as long as
        # schema + supervisor health gates pass.
        if not current_state:
            return True

        # Prefer explicit connectivity flags from API attributes when present.
        for key in ("connected", "is_connected", "online"):
            if key in attrs and isinstance(attrs[key], bool):
                return attrs[key]

        state_value = str(current_state.get("state", "")).strip().lower()
        return state_value not in {"", "unavailable", "offline", "unknown", "disconnected", "stopped"}
        
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera image."""
        try:
            current_state = self._get_current_state()
            attrs = current_state.get("attributes", {})

            image_url = attrs.get("image_url") or attrs.get("snapshot_url")
            if not image_url:
                capability = self.entity_schema.get("capability_id")
                if capability:
                    image_url = f"/api/v1/cameras/{capability}/latest.jpg"

            if not image_url:
                return self._generate_placeholder_image()

            image_url = self._resolve_camera_url(str(image_url))

            session = self.coordinator._http_session
            if not session or session.closed:
                _LOGGER.debug("HTTP session unavailable for camera %s", self._entity_id)
                return self._generate_placeholder_image()

            async with session.get(image_url) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Camera image fetch returned HTTP %s for %s (%s)",
                        response.status,
                        self._entity_id,
                        image_url,
                    )
                    return self._generate_placeholder_image()
                data = await response.read()
                return data or self._generate_placeholder_image()
            
        except Exception as e:
            _LOGGER.warning("Failed to get camera image for %s: %s", self._entity_id, e)
            return self._generate_placeholder_image()

    def _resolve_camera_url(self, image_url: str) -> str:
        """Resolve relative camera URLs against the supervisor base URL."""
        if image_url.startswith("http://") or image_url.startswith("https://"):
            return image_url

        host = self.coordinator._entry.data.get("host")
        port = self.coordinator._entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)
        base = f"http://{host}:{port}"

        if image_url.startswith("/"):
            return f"{base}{image_url}"

        return urljoin(f"{base}/", image_url)
            
    def _generate_placeholder_image(self) -> bytes:
        """Generate a minimal placeholder image."""
        # Create a minimal 1x1 PNG image
        import base64
        # This is a 1x1 transparent PNG encoded as base64
        placeholder_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        return base64.b64decode(placeholder_b64)
        
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes specific to camera."""
        attrs = super().extra_state_attributes
        current_state = self._get_current_state()
        
        # Add camera-specific attributes from current state
        camera_attrs = current_state.get("attributes", {})
        for attr in ["resolution", "quality", "device", "last_image", "fps"]:
            if attr in camera_attrs:
                attrs[attr] = camera_attrs[attr]
                
        return attrs


def create_entity_from_schema(
    coordinator: PerimeterControlCoordinator,
    entity_schema: Dict[str, Any],
    dimension_values: Optional[Dict[str, str]] = None,
) -> SupervisorEntity | None:
    """Create appropriate entity instance from schema."""
    entity_type = entity_schema.get("type")
    entity_id = entity_schema.get("id", "unknown")
    
    try:
        if entity_type == "sensor":
            return DynamicSensorEntity(coordinator, entity_schema, dimension_values)
        elif entity_type == "binary_sensor":
            return DynamicBinarySensorEntity(coordinator, entity_schema, dimension_values)
        elif entity_type == "button":
            return DynamicButtonEntity(coordinator, entity_schema, dimension_values)
        elif entity_type == "camera":
            return DynamicCameraEntity(coordinator, entity_schema, dimension_values)
        elif entity_type == "switch":
            return DynamicSwitchEntity(coordinator, entity_schema, dimension_values)
        elif entity_type == "light":
            return DynamicLightEntity(coordinator, entity_schema, dimension_values)
        else:
            _LOGGER.warning("Unknown entity type '%s' in schema: %s", entity_type, entity_schema)
            return None
    except Exception as e:
        _LOGGER.error(
            "Failed to create %s entity '%s': %s. Continuing with other entities.",
            entity_type, entity_id, e, exc_info=True
        )
        return None


def expand_templated_entities(
    coordinator: PerimeterControlCoordinator,
    entity_schema: Dict[str, Any],
) -> list[SupervisorEntity]:
    """Expand templated entities with dimensions into multiple entities."""
    entity_id = entity_schema.get("id", "unknown")
    dimensions = entity_schema.get("dimensions", {})
    
    try:
        if not dimensions:
            # Non-templated entity - create single instance
            entity = create_entity_from_schema(coordinator, entity_schema)
            return [entity] if entity else []
        
        # Templated entity - create one instance per dimension combination
        entities = []
        for dim_name, dim_values in dimensions.items():
            for dim_value in dim_values:
                entity = create_entity_from_schema(
                    coordinator, 
                    entity_schema, 
                    {dim_name: dim_value}
                )
                if entity:
                    entities.append(entity)
        
        return entities
    except Exception as e:
        _LOGGER.error(
            "Failed to expand entity schema '%s': %s. Skipping this entity.",
            entity_id, e, exc_info=True
        )
        return []