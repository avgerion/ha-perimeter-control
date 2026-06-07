"""
BLE GATT Repeater service-specific dashboard entry point.
Migrated from ble_gatt_bokeh_dashboard.py.
"""

import os
import sys
import yaml
import logging
# Ensure the directory containing this file is on sys.path so that
# sibling modules are importable when this script is executed directly by systemd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from ble_gatt_repeater_layouts import create_ble_gatt_repeater_dashboard_layout
from ble_gatt_repeater_callbacks import setup_ble_gatt_repeater_callbacks
from data_manager import DataManager
from pathlib import Path

def main(config_path):
    # Load config and instance
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    instances = config.get('services', {}).get('ble_gatt_repeater', {})
    instance_name, instance_config = next(iter(instances.items())) if instances else (None, {})
    log_root = instance_config.get('log_root', '/var/log/PerimeterControl')
    port = int(instance_config.get('port', 8091))
    log_file = os.path.join(log_root, 'ble_gatt_dashboard.log')
    logger_name = 'perimetercontrol.ble_gatt_dashboard'
    os.makedirs(log_root, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logger = logging.getLogger(logger_name)
    data_manager = DataManager(config_path)
    def create_app(doc):
        layout, widgets = create_ble_gatt_repeater_dashboard_layout(data_manager)
        doc.add_root(layout)
        for key, value in widgets.items():
            setattr(doc, key, value)
        setup_ble_gatt_repeater_callbacks(doc, data_manager)
        doc.title = f"BLE GATT Repeater Dashboard - {instance_name or 'default'}"
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=port, address="0.0.0.0")
    logger.info(f"BLE GATT Bokeh dashboard running on port {port} (instance: {instance_name})")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down BLE GATT dashboard...")
    return 0
if __name__ == "__main__":
    import sys
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/ble-gatt-repeater.yaml")
    sys.exit(main(config))