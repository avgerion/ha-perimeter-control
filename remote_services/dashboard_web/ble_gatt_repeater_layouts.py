"""
BLE GATT Repeater service-specific layouts.
Move all logic from layouts.py that is specific to ble_gatt_repeater here.
"""


from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource

def create_ble_gatt_repeater_dashboard_layout(data_manager):
    """
    Bokeh layout for BLE GATT dashboard, with entity table.
    """
    header = Div(text="<h1 class='dashboard-h1'>BLE GATT Repeater Dashboard</h1>", sizing_mode="stretch_width")
    columns = [
        TableColumn(field="friendly_name", title="Name"),
        TableColumn(field="type", title="Type"),
        TableColumn(field="state", title="State"),
    ]
    source = ColumnDataSource({"friendly_name": [], "type": [], "state": []})
    table = DataTable(source=source, columns=columns, width=600)
    layout = column(header, table)
    widgets = {"entity_table": table, "source": source}
    return layout, widgets
