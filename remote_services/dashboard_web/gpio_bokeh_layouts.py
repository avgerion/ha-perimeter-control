from bokeh.layouts import column
from bokeh.models import Div, Button, DataTable, TableColumn, ColumnDataSource

def create_gpio_dashboard_layout(data_manager):
    """
    Bokeh layout for GPIO dashboard, with entity table and diagnostics.
    """
    header = Div(text="<h1>GPIO Control Dashboard</h1>")
    # Fetch entities from supervisor
    entities = data_manager.get_gpio_entities() if hasattr(data_manager, 'get_gpio_entities') else []
    columns = [
        TableColumn(field="friendly_name", title="Name"),
        TableColumn(field="id", title="Entity ID"),
        TableColumn(field="state", title="State"),
    ]
    source = ColumnDataSource(entities)
    table = DataTable(source=source, columns=columns, width=600)
    # Diagnostic panel if no entities
    diagnostics = Div(text="")
    if not entities:
        diagnostics.text = """
        <div style='color: red; font-weight: bold;'>No GPIO entities published by supervisor.</div>
        <div>Check supervisor status, configuration, and logs. Ensure the GPIO capability is enabled and entities are defined.</div>
        <div>Raw supervisor API response:</div>
        <pre id='raw-entities'></pre>
        """
    layout = column(header, diagnostics, table)
    widgets = {"entity_table": table, "diagnostics": diagnostics, "source": source}
    return layout, widgets
