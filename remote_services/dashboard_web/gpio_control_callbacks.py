"""GPIO Control service-specific callbacks."""
import logging

_GPIO_CALLBACKS_LOGGER = logging.getLogger("perimetercontrol.gpio_callbacks")

def setup_gpio_control_callbacks(doc, data_manager):
    """Populate GPIO entity table from supervisor API and refresh periodically.
    
    Fetches GPIO entities with their state from supervisor API every 5 seconds.
    Falls back to current data if supervisor API is unavailable.
    """
    _GPIO_CALLBACKS_LOGGER.info("[GPIO_CB] Setting up GPIO control callbacks")

    def _update_gpio_entities() -> None:
        try:
            rows = data_manager.get_entities_with_state("gpio_control")
            _GPIO_CALLBACKS_LOGGER.debug("[GPIO_CB] Fetched %d GPIO entities from supervisor API", len(rows))
            
            if rows:
                doc.source.data = {
                    "friendly_name": [str(r.get("friendly_name") or r.get("id") or "") for r in rows],
                    "id": [str(r.get("id") or "") for r in rows],
                    "state": [str(r.get("state") or "unknown") for r in rows],
                    "gpio_pin": [str(r.get("attributes", {}).get("gpio_pin", "")) for r in rows],
                    "type": [str(r.get("type", "switch")) for r in rows],
                }
                _GPIO_CALLBACKS_LOGGER.debug("[GPIO_CB] Updated UI with GPIO entities: %s", 
                                            [r.get("id") for r in rows])
            else:
                _GPIO_CALLBACKS_LOGGER.warning("[GPIO_CB] No GPIO entities returned from supervisor API")
        except Exception as e:
            _GPIO_CALLBACKS_LOGGER.error("[GPIO_CB] Error updating GPIO entities: %s", e)

    doc.add_periodic_callback(_update_gpio_entities, 5000)
    _GPIO_CALLBACKS_LOGGER.info("[GPIO_CB] Initial GPIO entity refresh starting...")
    _update_gpio_entities()
