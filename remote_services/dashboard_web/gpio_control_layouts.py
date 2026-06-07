import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource

def get_gpio_entities(config):
    """Return GPIO entities from config. Stub until gpio_control_callbacks is implemented."""
    services = config.get("services", {})
    gpio_cfg = services.get("gpio_control", {})
    entities = []
    for pin_id, pin_info in gpio_cfg.get("pins", {}).items():
        entities.append({
            "id": str(pin_id),
            "friendly_name": pin_info.get("name", str(pin_id)),
            "state": pin_info.get("default_state", "unknown"),
        })
    return entities

def create_gpio_control_dashboard_layout(data_manager):
    # Runtime entity rows are populated by periodic callbacks from supervisor API.
    source_data = {"friendly_name": [], "id": [], "state": []}
    columns = [
        TableColumn(field="friendly_name", title="Name"),
        TableColumn(field="id", title="ID"),
        TableColumn(field="state", title="State"),
    ]
    source = ColumnDataSource(source_data)
    table = DataTable(source=source, columns=columns, width=600)
    layout = column(Div(text="<h1>GPIO Control Dashboard</h1>"), table)
    widgets = {"entity_table": table, "source": source}
    return layout, widgets
