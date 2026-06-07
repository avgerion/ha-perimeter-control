"""GPIO Control service-specific callbacks."""


def setup_gpio_control_callbacks(doc, data_manager):
    """Populate GPIO entity table from supervisor API and refresh periodically."""

    def _update_gpio_entities() -> None:
        rows = data_manager.get_entities_with_state("gpio_control")
        doc.source.data = {
            "friendly_name": [str(r.get("friendly_name") or r.get("id") or "") for r in rows],
            "id": [str(r.get("id") or "") for r in rows],
            "state": [str(r.get("state") or "unknown") for r in rows],
        }

    doc.add_periodic_callback(_update_gpio_entities, 5000)
    _update_gpio_entities()
