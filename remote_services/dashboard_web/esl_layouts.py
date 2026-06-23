"""
ESL service-specific layouts.
"""
from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource


def create_esl_dashboard_layout(data_manager):
    """Bokeh layout for ESL (Electronic Shelf Label) dashboard."""
    header = Div(text="<h1 class='dashboard-h1'>ESL AP Dashboard</h1>", sizing_mode="stretch_width")

    # Populate from config if available
    config = getattr(data_manager, 'config', {})
    esl_devices = config.get('services', {}).get('esl_ap', {}).get('devices', [])
    source_data = {
        "address": [d.get('address', '') for d in esl_devices],
        "label": [d.get('label', '') for d in esl_devices],
        "status": [d.get('status', 'unknown') for d in esl_devices],
    }
    columns = [
        TableColumn(field="address", title="Address"),
        TableColumn(field="label", title="Label"),
        TableColumn(field="status", title="Status"),
    ]
    source = ColumnDataSource(source_data)
    table = DataTable(source=source, columns=columns, width=600)
    layout = column(header, table)
    widgets = {"device_table": table, "source": source}
    return layout, widgets
