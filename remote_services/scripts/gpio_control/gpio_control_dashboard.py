"""
GPIO Control service-specific dashboard entry point.
Migrated from gpio_bokeh_dashboard.py.
"""
import os
import yaml
import logging
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from .gpio_control_layouts import create_gpio_control_dashboard_layout
from .gpio_control_callbacks import setup_gpio_control_callbacks
from data_sources import DataManager
from pathlib import Path

def main(config_path):
    # Load config and instance
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    instances = config.get('services', {}).get('gpio_control', {})
    instance_name, instance_config = next(iter(instances.items())) if instances else (None, {})
    log_root = instance_config.get('log_root', '/var/log/PerimeterControl')
    port = int(instance_config.get('port', 8095))
    log_file = os.path.join(log_root, 'gpio_dashboard.log')
    logger_name = 'perimetercontrol.gpio_dashboard'
    os.makedirs(log_root, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logger = logging.getLogger(logger_name)
    data_manager = DataManager(config_path)
    def create_app(doc):
        layout, widgets = create_gpio_control_dashboard_layout(data_manager)
        doc.add_root(layout)
        for key, value in widgets.items():
            setattr(doc, key, value)
        setup_gpio_control_callbacks(doc, data_manager)
        doc.title = "GPIO Control Dashboard"
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=port, address="0.0.0.0")
    logger.info(f"GPIO Bokeh dashboard running on port {port} (instance: {instance_name})")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down GPIO dashboard...")
    return 0