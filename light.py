"""Dynamic light entities for Perimeter Control."""
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light entities from Supervisor API schema."""
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    entities = []
    supervisor_entities = coordinator.data.get("supervisor_entities", [])

    for entity_schema in supervisor_entities:
        try:
            if entity_schema.get("type") == "light":
                entities.extend(expand_templated_entities(coordinator, entity_schema))
        except Exception as exc:
            entity_id = entity_schema.get("id", "unknown_light")
            _LOGGER.error(
                "Failed to process light entity '%s': %s. Continuing with other lights.",
                entity_id,
                exc,
                exc_info=True,
            )

    if entities:
        async_add_entities(entities)
