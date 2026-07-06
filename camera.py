"""Dynamic camera entities for Perimeter Control."""
from collections import defaultdict
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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
    
    known_unique_ids: set[str] = set()

    def _add_new_camera_entities() -> None:
        entities = []
        desired_unique_ids: set[str] = set()
        added_by_service: dict[str, int] = defaultdict(int)
        pruned_by_service: dict[str, int] = defaultdict(int)
        supervisor_entities = coordinator.data.get("supervisor_entities", [])

        for entity_schema in supervisor_entities:
            try:
                if entity_schema.get("type") != "camera":
                    continue

                service_id = str(
                    entity_schema.get("capability_id", "unknown")
                )
                new_entities = expand_templated_entities(coordinator, entity_schema)
                for new_entity in new_entities:
                    unique_id = getattr(new_entity, "unique_id", None)
                    if unique_id:
                        desired_unique_ids.add(unique_id)
                    if unique_id and unique_id in known_unique_ids:
                        continue
                    if unique_id:
                        known_unique_ids.add(unique_id)
                    entities.append(new_entity)
                    added_by_service[service_id] += 1
            except Exception as e:
                entity_id = entity_schema.get("id", "unknown_camera")
                _LOGGER.error(
                    "Failed to process camera entity '%s': %s. Continuing with other cameras.",
                    entity_id, e, exc_info=True
                )

        if entities:
            _LOGGER.info("Adding %d new camera entities from updated schema", len(entities))
            async_add_entities(entities)

        registry = er.async_get(hass)
        for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registry_entry.platform != DOMAIN or registry_entry.domain != "camera":
                continue
            unique_id = registry_entry.unique_id
            if not unique_id:
                continue
            if unique_id in desired_unique_ids:
                continue
            _LOGGER.info("Pruning stale camera entity %s", registry_entry.entity_id)
            registry.async_remove(registry_entry.entity_id)
            service_id = "unknown"
            prefix = f"{entry.entry_id}_"
            if unique_id.startswith(prefix):
                base_id = unique_id[len(prefix):]
                service_id = base_id.split(":", 1)[0]
            pruned_by_service[service_id] += 1

        if added_by_service:
            _LOGGER.warning("Camera entity sync added per service: %s", dict(added_by_service))
        if pruned_by_service:
            _LOGGER.warning("Camera entity sync pruned per service: %s", dict(pruned_by_service))

        known_unique_ids.clear()
        known_unique_ids.update(desired_unique_ids)

    _add_new_camera_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_camera_entities))