(from .gpio_control_callbacks import get_gpio_entities)

from bokeh.layouts import column
from bokeh.models import Div, DataTable, TableColumn, ColumnDataSource

def create_gpio_control_dashboard_layout(data_manager):
	entities = get_gpio_entities(data_manager.config)
	columns = [
		TableColumn(field="friendly_name", title="Name"),
		TableColumn(field="id", title="ID"),
		TableColumn(field="state", title="State"),
	]
	source = ColumnDataSource(entities)
	table = DataTable(source=source, columns=columns, width=600)
	layout = column(Div(text="<h1>GPIO Control Dashboard</h1>"), table)
	widgets = {"entity_table": table, "source": source}
	return layout, widgets
