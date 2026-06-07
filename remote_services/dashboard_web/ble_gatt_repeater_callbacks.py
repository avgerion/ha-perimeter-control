"""
BLE GATT Repeater service-specific callbacks.
Move all logic from callbacks.py that is specific to ble_gatt_repeater here.
"""

def get_ble_gatt_entities(config):
    """Return a list of BLE GATT entities for the dashboard table."""
    # Config-only fallback before supervisor state is fetched.
    return []

def setup_ble_gatt_repeater_callbacks(doc, data_manager):
    def _update_ble_entities() -> None:
        rows = data_manager.get_entities_with_state("ble_gatt_repeater")
        doc.source.data = {
            "friendly_name": [str(r.get("friendly_name") or r.get("id") or "") for r in rows],
            "type": [str(r.get("type") or "") for r in rows],
            "state": [str(r.get("state") or "unknown") for r in rows],
        }

    doc.add_periodic_callback(_update_ble_entities, 5000)
    _update_ble_entities()
