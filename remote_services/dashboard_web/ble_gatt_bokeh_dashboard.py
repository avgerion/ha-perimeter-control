#!/usr/bin/env python3
"""
BLE GATT Repeater Bokeh Dashboard
Serves the BLE GATT dashboard at the same port as the old Tornado dashboard (default: 8091).
"""
import os
import logging
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from ble_gatt_bokeh_layouts import create_ble_gatt_dashboard_layout
try:
    from callbacks import setup_ble_gatt_callbacks
except ImportError:
    def setup_ble_gatt_callbacks(doc, data_manager):
        pass  # Stub if not implemented
from data_sources import DataManager
from pathlib import Path

DASHBOARD_PORT = int(os.environ.get("PERIMETERCONTROL_BLE_DASHBOARD_PORT", "8091"))
LOG_ROOT = os.environ.get('PERIMETERCONTROL_DASHBOARD_LOG_ROOT', '/var/log/PerimeterControl')
DASHBOARD_LOG_FILE = os.path.join(LOG_ROOT, 'ble_gatt_dashboard.log')
LOGGER_NAME = 'perimetercontrol.ble_gatt_dashboard'

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
    data_manager = DataManager()
    layout, widgets = create_ble_gatt_dashboard_layout(data_manager)
    doc.add_root(layout)
    for key, value in widgets.items():
        setattr(doc, key, value)
    setup_ble_gatt_callbacks(doc, data_manager)
    doc.title = "BLE GATT Repeater Dashboard"

if __name__ == "__main__":
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=DASHBOARD_PORT, address="0.0.0.0")
    logger.info(f"BLE GATT Bokeh dashboard running on port {DASHBOARD_PORT}")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down BLE GATT dashboard...")
        server.stop()
