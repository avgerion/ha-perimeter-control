"""
Photo Booth service-specific layouts.
Move all logic from photo_booth_bokeh_layouts.py or layouts.py that is specific to photo_booth here.
"""

from bokeh.layouts import column
from bokeh.models import Div, Button, ColumnDataSource
from bokeh.plotting import figure

def create_photo_booth_dashboard_layout(data_manager):
    """
    Bokeh layout for Photo Booth dashboard, with photo preview and capture button.
    """
    header = Div(text="<h1>Photo Booth Dashboard</h1>")
    photo_source = ColumnDataSource(data=dict(url=["/static/placeholder.jpg"], x=[0], y=[0], w=[400], h=[300]))
    # ImageURL is the correct glyph for displaying images from URLs in modern Bokeh
    from bokeh.models import ImageURL
    plot = figure(width=400, height=300, toolbar_location=None)
    plot.image_url(url="url", x="x", y="y", w="w", h="h", source=photo_source)
    capture_button = Button(label="Capture Photo", button_type="success")
    layout = column(header, plot, capture_button)
    widgets = {"plot": plot, "capture_button": capture_button, "photo_source": photo_source}
    return layout, widgets
