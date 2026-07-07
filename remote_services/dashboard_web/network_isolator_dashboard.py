#!/usr/bin/env python3
"""
Network Isolator Dashboard implementation (service-specific).
This file contains all logic previously in dashboard.py for the network_isolator service.
"""
import logging
import os
from pathlib import Path
from collections import Counter
from typing import Any, Dict, Optional
import yaml
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop
from network_isolator_layouts import create_dashboard_layout
from network_isolator_callbacks import setup_callbacks
from data_sources import DataManager
from bokeh.models import Div

def _load_config(path: Path) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"Failed to parse config {path}: {exc}; using defaults")
        return {}

def main(config_path: Path):
    config = _load_config(config_path)
    dashboard_cfg = config.get('dashboard', {}) or {}
    log_root = dashboard_cfg.get('log_root', '/var/log/PerimeterControl')
    log_file = dashboard_cfg.get('log_file', 'dashboard.log')
    logger_name = dashboard_cfg.get('logger_name', 'perimetercontrol.dashboard')
    os.makedirs(log_root, exist_ok=True)
    log_path = os.path.join(log_root, log_file)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(logger_name)
    # --- Network/port binding logic ---
    bind_address = dashboard_cfg.get('bind_address', '127.0.0.1')
    port = int(dashboard_cfg.get('port', 5006))
    allow_websocket_origin = dashboard_cfg.get('allow_websocket_origin', [f'localhost:{port}'])
    # --- Dashboard logic ---
    data_manager = DataManager(config_path)
    supervisor_api_url = data_manager.supervisor_api_url
    def create_app(doc):
        layout, widgets = create_dashboard_layout(data_manager)
        # Ensure shared dashboard stylesheet is available via common helper
        try:
            from dashboard_common import _get_style_div, get_loader_div
            doc.add_root(_get_style_div())
            # Add loader script to ensure jQuery/jQuery UI are available
            doc.add_root(get_loader_div())
        except Exception:
            # Fallback to link tag if helper import fails
            css_div = Div(text="<link rel='stylesheet' href='/css/pc-dashboard.css'>", sizing_mode="stretch_width")
            doc.add_root(css_div)
        doc.supervisor_api_url = supervisor_api_url
        for key, value in widgets.items():
            setattr(doc, key, value)
        setup_callbacks(doc, data_manager)
        doc.title = "Network Isolator Quick View"
        # Ensure document uses a minimal HTML template without restrictive
        # global styles that interfere with our layout.
        try:
            tmpl_path = Path(__file__).parent / "static" / "html" / "pc-dashboard-template.html"
            if tmpl_path.exists():
                tmpl_text = tmpl_path.read_text(encoding="utf-8")
                doc.template = tmpl_text
                logger.info("Loaded custom dashboard template %s (len=%d)", tmpl_path, len(tmpl_text))
            else:
                logger.warning("Custom dashboard template not found: %s", tmpl_path)
        except Exception as e:
            logger.exception("Failed to load custom dashboard template: %s", e)
    handler = FunctionHandler(create_app)
    # Load template at Application level so Bokeh's index uses our template
    try:
        tmpl_path = Path(__file__).parent / "static" / "html" / "pc-dashboard-template.html"
        app_template = None
        if tmpl_path.exists():
            app_template = tmpl_path.read_text(encoding="utf-8")
            logger.info("Application-level template loaded %s (len=%d)", tmpl_path, len(app_template))
        else:
            logger.warning("Application-level template not found: %s", tmpl_path)
    except Exception as e:
        logger.exception("Failed to load application template: %s", e)
        app_template = None
    app = Application(handler, template=app_template)
    from dashboard_common import get_extra_static_patterns
    extra_patterns = get_extra_static_patterns()
    if app_template:
        logger.info("Starting server with application index template present (len=%d)", len(app_template))
    else:
        logger.info("Starting server without application index template; Bokeh default index will be used")
    server = Server(
        {'/': app},
        port=port,
        address=bind_address,
        allow_websocket_origin=allow_websocket_origin,
        session_token_expiration=86400000,
        num_procs=1,
        index=app_template,
        extra_patterns=extra_patterns,
    )
    logger.info(f"Network Isolator Dashboard running on {bind_address}:{port}")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    finally:
        server.stop()
        logger.info("Dashboard stopped")
    return 0

if __name__ == "__main__":
    import sys
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/perimeterControl.conf.yaml")
    sys.exit(main(config))
