"""Dynamic camera entities for Perimeter Control."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PerimeterControlCoordinator
from .dynamic_entity import expand_templated_entities

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up camera entities from Supervisor API schema."""
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Wait for initial coordinator data
    await coordinator.async_config_entry_first_refresh()
    
    # Create entities from current Supervisor schema
    entities = []
    supervisor_entities = coordinator.data.get("supervisor_entities", [])
    
    for entity_schema in supervisor_entities:
        try:
            entity_type = entity_schema.get("type")
            if entity_type == "camera":
                # Expand templated entities (handles both single and multi-dimensional)
                new_entities = expand_templated_entities(coordinator, entity_schema)
                entities.extend(new_entities)
        except Exception as e:
            entity_id = entity_schema.get("id", "unknown_camera")
            _LOGGER.error(
                "Failed to process camera entity '%s': %s. Continuing with other cameras.",
                entity_id, e, exc_info=True
            )
    
    if entities:
        async_add_entities(entities)
    
    # TODO: Add listener for schema changes to add/remove entities dynamically