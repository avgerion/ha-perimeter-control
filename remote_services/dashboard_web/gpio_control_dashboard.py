"""
GPIO Control service-specific dashboard entry point.
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
from gpio_control_layouts import create_gpio_control_dashboard_layout
from data_manager import DataManager
from dashboard_common import create_service_status_panel, create_log_tail_panel
from bokeh.layouts import column as bk_column
from pathlib import Path


def main(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    instances = config.get('services', {}).get('gpio_control', {})
    instance_name, instance_config = next(iter(instances.items())) if instances else (None, {})
    port = int(instance_config.get('port', 8095))
    log_root = instance_config.get('log_root', '/var/log/PerimeterControl')
    os.makedirs(log_root, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger('perimetercontrol.gpio_dashboard')
    data_manager = DataManager(config_path)

    def create_app(doc):
        layout, widgets = create_gpio_control_dashboard_layout(data_manager)
        status_layout, status_widgets = create_service_status_panel(
            "gpio_control", log_dir=log_root
        )
        log_layout, log_widgets = create_log_tail_panel(
            f"{log_root}/gpio_dashboard.log", title="GPIO Log"
        )
        full_layout = bk_column(layout, status_layout, log_layout, sizing_mode="stretch_width")
        doc.add_root(full_layout)
        for key, value in {**widgets, **status_widgets, **log_widgets}.items():
            setattr(doc, key, value)
        doc.title = f"GPIO Control Dashboard - {instance_name or 'default'}"

    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=port, address="0.0.0.0", allow_websocket_origin=["*"])
    logger.info(f"GPIO Control dashboard running on port {port}")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down GPIO Control dashboard...")
    return 0


if __name__ == "__main__":
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/gpio-control.yaml")
    sys.exit(main(config))
