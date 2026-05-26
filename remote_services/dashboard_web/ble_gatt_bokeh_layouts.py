from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource

def create_ble_gatt_dashboard_layout(data_manager):
    """
    Bokeh layout for BLE GATT dashboard, with entity table.
    """
    header = Div(text="<h1>BLE GATT Repeater Dashboard</h1>")
    entities = data_manager.get_ble_gatt_entities() if hasattr(data_manager, 'get_ble_gatt_entities') else []
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
