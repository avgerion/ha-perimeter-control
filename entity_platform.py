"""Entity platform setup for Perimeter Control service dashboard entities."""
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .coordinator import PerimeterControlCoordinator
from .entity import PerimeterControlServiceEntity
from .const import DOMAIN, AVAILABLE_SERVICES

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PerimeterControlServiceEntity(coordinator, service_id)
        for service_id in AVAILABLE_SERVICES
    ]
    async_add_entities(entities)
