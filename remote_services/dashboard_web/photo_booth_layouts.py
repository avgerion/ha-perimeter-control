"""
Photo Booth service-specific layouts.
Move all logic from photo_booth_bokeh_layouts.py or layouts.py that is specific to photo_booth here.
"""

from bokeh.layouts import column
from bokeh.models import Div, Button, ColumnDataSource, DataTable, TableColumn
from bokeh.plotting import figure

def create_photo_booth_dashboard_layout(data_manager):
    """
    Bokeh layout for Photo Booth dashboard with live MJPEG stream and capture button.
    """
    header = Div(text="<h1 class='dashboard-h1'>Photo Booth Dashboard</h1>", sizing_mode="stretch_width")
    camera_status_div = Div(text="<p class='dashboard-info'>Camera service status: checking...</p>", sizing_mode="stretch_width")
    
    # Live MJPEG stream container
    stream_div = Div(
        text="<img id='camera-stream' src='' style='max-width:100%; height:auto; border:1px solid #ccc;' alt='Camera stream' />",
        sizing_mode="stretch_width",
        height=400
    )
    
    # Capture button for snapshots
    capture_button = Button(label="Capture Photo", button_type="success")
    
    layout = column(header, camera_status_div, stream_div, capture_button, sizing_mode="stretch_width")
    widgets = {
        "stream_div": stream_div,
        "capture_button": capture_button,
        "camera_status_div": camera_status_div,
    }
    return layout, widgets
