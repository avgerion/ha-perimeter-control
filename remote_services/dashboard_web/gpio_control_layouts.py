import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource

_GPIO_LOGGER = logging.getLogger("perimetercontrol.gpio_layouts")

def get_gpio_entities_from_config(config):
    """Extract GPIO entities from YAML config.
    
    Expected format (nested service architecture):
    services:
      gpio_control:
        <instance_name>:
          pins:
            - id: relay1
              gpio_pin: 17
              friendly_name: Relay 1
              type: switch
              initial_state: off
    """
    entities = []
    try:
        services = config.get("services", {})
        gpio_cfg_dict = services.get("gpio_control", {})
        
        if not isinstance(gpio_cfg_dict, dict):
            _GPIO_LOGGER.error("[GPIO] Config error: services.gpio_control must be a dict")
            return entities
        
        # Iterate over GPIO instances (e.g., "relays", "lights")
        for instance_name, instance_cfg in gpio_cfg_dict.items():
            if not isinstance(instance_cfg, dict):
                _GPIO_LOGGER.warning("[GPIO] Skipping instance '%s': not a dict", instance_name)
                continue
            
            pins_data = instance_cfg.get("pins", [])
            if not isinstance(pins_data, list):
                _GPIO_LOGGER.warning("[GPIO] Instance '%s' has no 'pins' list", instance_name)
                continue
            
            for pin_info in pins_data:
                if isinstance(pin_info, dict):
                    entities.append({
                        "id": str(pin_info.get("id", "unknown")),
                        "friendly_name": pin_info.get("friendly_name", pin_info.get("id", "unknown")),
                        "state": pin_info.get("initial_state", "unknown"),
                        "gpio_pin": pin_info.get("gpio_pin"),
                        "type": pin_info.get("type", "switch"),
                    })
        
        _GPIO_LOGGER.info("[GPIO] Loaded %d GPIO entities from config", len(entities))
        if entities:
            _GPIO_LOGGER.info("[GPIO] Parsed GPIO pins: %s", [f"{e['id']} (GPIO{e['gpio_pin']})" for e in entities])
    except Exception as e:
        _GPIO_LOGGER.error("[GPIO] Failed to parse GPIO config: %s", e)
    
    return entities

def create_gpio_control_dashboard_layout(data_manager):
    """Create GPIO control dashboard layout.
    
    Loads GPIO pins from:
    1. Supervisor API (if available)
    2. Config file (fallback)
    """
    _GPIO_LOGGER.info("[GPIO] Creating GPIO control dashboard layout")
    
    # Runtime entity rows are populated by periodic callbacks from supervisor API.
    source_data = {"friendly_name": [], "id": [], "state": [], "gpio_pin": [], "type": []}
    columns = [
        TableColumn(field="friendly_name", title="Name"),
        TableColumn(field="id", title="ID"),
        TableColumn(field="gpio_pin", title="GPIO Pin"),
        TableColumn(field="type", title="Type"),
        TableColumn(field="state", title="State"),
    ]
    source = ColumnDataSource(source_data)
    # Use responsive sizing to avoid fixed-width overflow which can cause
    # layout overlap when the page header or container styles change.
    table = DataTable(source=source, columns=columns, sizing_mode="stretch_width")
    
    # Bootstrap with config entities if available
    try:
        config_entities = get_gpio_entities_from_config(data_manager.config)
        if config_entities:
            _GPIO_LOGGER.info("[GPIO] Bootstrapping from config with %d pins", len(config_entities))
            source.data = {
                "friendly_name": [str(e.get("friendly_name", "")) for e in config_entities],
                "id": [str(e.get("id", "")) for e in config_entities],
                "gpio_pin": [str(e.get("gpio_pin", "")) for e in config_entities],
                "type": [str(e.get("type", "")) for e in config_entities],
                "state": [str(e.get("state", "unknown")) for e in config_entities],
            }
        else:
            _GPIO_LOGGER.warning("[GPIO] No GPIO pins found in config")
    except Exception as e:
        _GPIO_LOGGER.error("[GPIO] Failed to bootstrap from config: %s", e)
    
    layout = column(
        Div(text="<h1 class='dashboard-h1'>GPIO Control Dashboard</h1>", sizing_mode="stretch_width"),
        Div(text="<p class='dashboard-info'><small>GPIO pins are loaded from supervisor API with fallback to config file. Check logs if pins not showing.</small></p>", sizing_mode="stretch_width"),
        table
    )
    widgets = {"entity_table": table, "source": source}
    return layout, widgets
