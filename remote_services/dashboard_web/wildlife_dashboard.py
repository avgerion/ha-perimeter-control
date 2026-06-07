"""
Wildlife service-specific dashboard entry point.
All logic previously in dashboard.py for wildlife should be moved here.
"""
import os
import sys
# Ensure the directory containing this file is on sys.path so that
# sibling modules are importable when this script is executed directly by systemd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main(config_path):
    # Import service-specific modules
    from wildlife_layouts import create_wildlife_dashboard_layout
    from wildlife_callbacks import setup_wildlife_callbacks
    from data_manager import DataManager
    from bokeh.application import Application
    from bokeh.application.handlers.function import FunctionHandler
    from bokeh.server.server import Server
    import logging
    import yaml
    from pathlib import Path

    logger = logging.getLogger("wildlife_dashboard")
    config = None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning(f"Failed to parse config {config_path}: {exc}; using defaults")
        config = {}

    # TODO: Implement network binding logic if needed
    data_manager = DataManager(config_path)

    def create_app(doc):
        layout, widgets = create_wildlife_dashboard_layout(data_manager)
        for key, value in widgets.items():
            setattr(doc, key, value)
        setup_wildlife_callbacks(doc, data_manager)
        doc.title = "Wildlife Dashboard"

    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server({'/': app}, port=5006, address='127.0.0.1', allow_websocket_origin=["localhost:5006"])
    server.start()
    server.io_loop.start()
    return 0
