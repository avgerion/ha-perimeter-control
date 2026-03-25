#!/usr/bin/env python3
"""
Network Isolator Quick View — Bokeh Dashboard
Main entry point for the real-time web interface.

Access methods:
  1. SSH tunnel (most secure):
     ssh -L 5006:localhost:5006 pi@isolator.local
     Browse to: http://localhost:5006

  2. Direct access on LAN:
     Browse to: http://isolator.local:5006
"""

import logging
from pathlib import Path

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from tornado.ioloop import IOLoop

from layouts import create_dashboard_layout
from callbacks import setup_callbacks
from data_sources import DataManager

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/log/isolator/dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('isolator.dashboard')

# Configuration
CONFIG_FILE = Path('/mnt/isolator/conf/isolator.conf.yaml')
BIND_ADDRESS = '127.0.0.1'  # Localhost only by default (SSH tunnel)
# BIND_ADDRESS = '0.0.0.0'  # Uncomment for direct LAN access
PORT = 5006


class IsolatorDashboard:
    """Main dashboard application."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.data_manager = DataManager(config_path)
        logger.info(f"Initialized dashboard with config: {config_path}")
    
    def create_app(self, doc):
        """
        Create the Bokeh document with layout and callbacks.
        Called once per connected client.
        """
        logger.info(f"New client connected: {doc.session_context.id}")
        
        # Create the main layout
        layout = create_dashboard_layout(self.data_manager)
        doc.add_root(layout)
        
        # Set up periodic callbacks for live updates
        setup_callbacks(doc, self.data_manager, layout)
        
        doc.title = "Network Isolator Quick View"


def main():
    """Start the Bokeh server."""
    logger.info("=" * 60)
    logger.info("Network Isolator Dashboard Starting")
    logger.info(f"Config: {CONFIG_FILE}")
    logger.info(f"Bind: {BIND_ADDRESS}:{PORT}")
    logger.info("=" * 60)
    
    # Check config file exists
    if not CONFIG_FILE.exists():
        logger.error(f"Config file not found: {CONFIG_FILE}")
        logger.error("Dashboard cannot start without configuration")
        return 1
    
    # Create dashboard instance
    dashboard = IsolatorDashboard(CONFIG_FILE)
    
    # Create Bokeh application
    handler = FunctionHandler(dashboard.create_app)
    app = Application(handler)
    
    # Configure server
    server = Server(
        {'/': app},
        port=PORT,
        address=BIND_ADDRESS,
        allow_websocket_origin=[
            f"{BIND_ADDRESS}:{PORT}",
            f"localhost:{PORT}",
            f"isolator.local:{PORT}",
            f"127.0.0.1:{PORT}"
        ],
        num_procs=1  # Single process on Pi 3
    )
    
    logger.info("Server configured, starting...")
    server.start()
    
    logger.info("=" * 60)
    logger.info("Dashboard is LIVE!")
    logger.info(f"Access via SSH tunnel: ssh -L {PORT}:localhost:{PORT} pi@isolator.local")
    logger.info(f"Then browse to: http://localhost:{PORT}")
    logger.info("=" * 60)
    
    # Start the IOLoop
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    finally:
        server.stop()
        logger.info("Dashboard stopped")
    
    return 0


if __name__ == '__main__':
    exit(main())
