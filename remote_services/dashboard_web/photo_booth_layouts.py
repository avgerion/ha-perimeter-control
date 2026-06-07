"""
Photo Booth service-specific layouts.
Move all logic from photo_booth_bokeh_layouts.py or layouts.py that is specific to photo_booth here.
"""

from bokeh.layouts import column
from bokeh.models import Div, Button, ColumnDataSource, DataTable, TableColumn
from bokeh.plotting import figure

def create_photo_booth_dashboard_layout(data_manager):
    """
    Bokeh layout for Photo Booth dashboard, with photo preview and capture button.
    """
    header = Div(text="<h1>Photo Booth Dashboard</h1>")
    camera_status_div = Div(text="<p>Camera service status: checking...</p>")
    photo_source = ColumnDataSource(data=dict(url=["/static/placeholder.jpg"], x=[0], y=[0], w=[400], h=[300]))
    # ImageURL is the correct glyph for displaying images from URLs in modern Bokeh
    from bokeh.models import ImageURL
    plot = figure(width=400, height=300, toolbar_location=None)
    plot.image_url(url="url", x="x", y="y", w="w", h="h", source=photo_source)

    camera_source = ColumnDataSource(data={"friendly_name": [], "state": [], "image_url": []})
    camera_columns = [
        TableColumn(field="friendly_name", title="Camera"),
        TableColumn(field="state", title="State"),
        TableColumn(field="image_url", title="Image URL"),
    ]
    camera_table = DataTable(source=camera_source, columns=camera_columns, height=180, sizing_mode="stretch_width")

    capture_button = Button(label="Capture Photo", button_type="success")
    layout = column(header, camera_status_div, plot, capture_button, camera_table, sizing_mode="stretch_width")
    widgets = {
        "plot": plot,
        "capture_button": capture_button,
        "photo_source": photo_source,
        "camera_source": camera_source,
        "camera_table": camera_table,
        "camera_status_div": camera_status_div,
    }
    return layout, widgets
