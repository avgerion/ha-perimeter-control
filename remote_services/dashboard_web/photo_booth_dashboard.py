"""
Photo Booth service-specific dashboard entry point.
Migrated from photo_booth_bokeh_dashboard.py.
"""
import os
import sys
import logging
# Ensure the directory containing this file is on sys.path so that
# sibling modules (photo_booth_layouts, etc.) are importable when
# this script is executed directly by systemd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from photo_booth_layouts import create_photo_booth_dashboard_layout
from photo_booth_callbacks import setup_photo_booth_callbacks
from data_manager import DataManager
from pathlib import Path
import yaml

def main(config_path):
    # Use the unified config file and select the correct instance config
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    booth_instances = config.get('services', {}).get('photo_booth', {})
    instance_name, instance_config = next(iter(booth_instances.items())) if booth_instances else (None, {})
    supervisor_api_url = config.get('supervisor_api_url')
    if not supervisor_api_url:
        logging.warning("supervisor_api_url not set in config! Supervisor API calls will fail.")
    port = int(instance_config.get('port', 8093))
    logger_name = 'perimetercontrol.photo_booth_dashboard'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger(logger_name)
    data_manager = DataManager(config_path)
    def create_app(doc):
        layout, widgets = create_photo_booth_dashboard_layout(data_manager)
        doc.add_root(layout)
        for key, value in widgets.items():
            setattr(doc, key, value)
        doc.supervisor_api_url = supervisor_api_url
        setup_photo_booth_callbacks(doc, data_manager)
        doc.title = f"Photo Booth Dashboard - {instance_name or 'default'}"
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=port, address="0.0.0.0")
    logger.info(f"Photo Booth Bokeh dashboard running on port {port} (instance: {instance_name})")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down Photo Booth dashboard...")
    return 0

if __name__ == "__main__":
    import sys
    config = Path("/mnt/PerimeterControl/conf/photo-booth.yaml")
    sys.exit(main(config))
