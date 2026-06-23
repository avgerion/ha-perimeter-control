"""Wildlife service-specific layouts."""
from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource


def create_wildlife_dashboard_layout(data_manager):
    """Bokeh layout for Wildlife Monitor dashboard."""
    header = Div(text="<h1 class='dashboard-h1'>Wildlife Monitor Dashboard</h1>", sizing_mode="stretch_width")

    # Populate from config if available
    config = getattr(data_manager, 'config', {})
    cameras = config.get('services', {}).get('wildlife_monitor', {}).get('cameras', [])
    source_data = {
        "name": [c.get('name', '') for c in cameras],
        "location": [c.get('location', '') for c in cameras],
        "status": [c.get('status', 'unknown') for c in cameras],
    }
    columns = [
        TableColumn(field="name", title="Camera"),
        TableColumn(field="location", title="Location"),
        TableColumn(field="status", title="Status"),
    ]
    source = ColumnDataSource(source_data)
    table = DataTable(source=source, columns=columns, width=600)
    layout = column(header, table)
    widgets = {"camera_table": table, "source": source}
    return layout, widgets
