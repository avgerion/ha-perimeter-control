"""Dynamic entities created from Supervisor API entity schema."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.camera import Camera
from homeassistant.components.sensor import SensorEntity
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
        
        # Also check if we have current state data
        current_state = self._get_current_state()
        has_state = bool(current_state and current_state.get("state") != "unavailable")
        
        return entity_exists and has_state

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "entity_id": self._entity_id,
            "capability": self.entity_schema.get("capability"),
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
        entity_data = entity_states.get(self._entity_id, {})
        # Extract the actual state data - API returns nested structure
        if "state" in entity_data:
            return entity_data["state"]
        return entity_data


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
        capability = self.entity_schema.get("capability")
        
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
        state_value = current_state.get("state")
        # Camera is streaming if state is not 'unavailable' or 'offline'
        return state_value not in ["unavailable", "offline", "unknown", None]
    
    @property
    def available(self) -> bool:
        """Return True if camera is available."""
        current_state = self._get_current_state()
        state_value = current_state.get("state")
        return state_value != "unavailable"
        
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera image."""
        try:
            # Try to get image from supervisor API
            current_state = self._get_current_state()
            image_url = current_state.get("attributes", {}).get("image_url")
            
            if not image_url:
                # If no image URL, return a minimal placeholder image
                return self._generate_placeholder_image()
                
            # For now, return placeholder until we implement full image fetching
            return self._generate_placeholder_image()
            
        except Exception as e:
            _LOGGER.warning("Failed to get camera image for %s: %s", self._entity_id, e)
            return self._generate_placeholder_image()
            
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