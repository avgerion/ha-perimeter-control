"""
BLE GATT Repeater service-specific layouts.
Move all logic from layouts.py that is specific to ble_gatt_repeater here.
"""


from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource
from .ble_gatt_repeater_callbacks import get_ble_gatt_entities

def create_ble_gatt_repeater_dashboard_layout(data_manager):
    """
    Bokeh layout for BLE GATT dashboard, with entity table.
    """
    header = Div(text="<h1>BLE GATT Repeater Dashboard</h1>")
    entities = get_ble_gatt_entities(data_manager.config)
    columns = [
        TableColumn(field="friendly_name", title="Name"),
        TableColumn(field="type", title="Type"),
        TableColumn(field="state", title="State"),
    ]
    source = ColumnDataSource(entities)
    table = DataTable(source=source, columns=columns, width=600)
    layout = column(header, table)
    widgets = {"entity_table": table, "source": source}
    return layout, widgets
