"""Dynamic button entities for Perimeter Control."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PerimeterControlCoordinator
from .dynamic_entity import expand_templated_entities

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entities from Supervisor API schema."""
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Wait for initial coordinator data
    await coordinator.async_config_entry_first_refresh()
    
    # Create entities from current Supervisor schema
    entities = []
    supervisor_entities = coordinator.data.get("supervisor_entities", [])
    
    for entity_schema in supervisor_entities:
        entity_type = entity_schema.get("type")
        if entity_type == "button":
            # Expand templated entities (handles both single and multi-dimensional)
            entities.extend(expand_templated_entities(coordinator, entity_schema))
    
    if entities:
        async_add_entities(entities)
    
    # TODO: Add listener for schema changes to add/remove entities dynamically
