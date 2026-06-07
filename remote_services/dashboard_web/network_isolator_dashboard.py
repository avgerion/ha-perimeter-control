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
        doc.supervisor_api_url = supervisor_api_url
        for key, value in widgets.items():
            setattr(doc, key, value)
        setup_callbacks(doc, data_manager)
        doc.title = "Network Isolator Quick View"
    handler = FunctionHandler(create_app)
    app = Application(handler)
    server = Server(
        {'/': app},
        port=port,
        address=bind_address,
        allow_websocket_origin=allow_websocket_origin,
        session_token_expiration=86400000,
        num_procs=1
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
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/network-isolator.yaml")
    sys.exit(main(config))
