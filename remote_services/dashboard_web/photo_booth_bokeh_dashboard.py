#!/usr/bin/env python3
"""
Photo Booth Bokeh Dashboard
Serves the Photo Booth dashboard at the same port as the old Tornado dashboard (default: 8093).
"""
import os
import logging
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from photo_booth_bokeh_layouts import create_photo_booth_dashboard_layout
from callbacks import setup_photo_booth_callbacks
from data_sources import DataManager
from pathlib import Path

DASHBOARD_PORT = int(os.environ.get("PERIMETERCONTROL_PHOTO_DASHBOARD_PORT", "8093"))
LOG_ROOT = os.environ.get('PERIMETERCONTROL_DASHBOARD_LOG_ROOT', '/var/log/PerimeterControl')
DASHBOARD_LOG_FILE = os.path.join(LOG_ROOT, 'photo_booth_dashboard.log')
LOGGER_NAME = 'perimetercontrol.photo_booth_dashboard'

os.makedirs(LOG_ROOT, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(DASHBOARD_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(LOGGER_NAME)

def create_app(doc):
    config_path = Path(os.environ.get("PERIMETERCONTROL_CONFIG_PATH", "/etc/PerimeterControl/isolator.conf.yaml"))
    data_manager = DataManager(config_path)
    layout, widgets = create_photo_booth_dashboard_layout(data_manager)
    doc.add_root(layout)
    for key, value in widgets.items():
        setattr(doc, key, value)
    setup_photo_booth_callbacks(doc, data_manager)
    doc.title = "Photo Booth Dashboard"

if __name__ == "__main__":
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=DASHBOARD_PORT, address="0.0.0.0")
    logger.info(f"Photo Booth Bokeh dashboard running on port {DASHBOARD_PORT}")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down Photo Booth dashboard...")
        server.stop()
