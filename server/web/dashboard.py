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
from collections import Counter

from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.document.callbacks import DocumentCallbackManager
from bokeh.server.session import ServerSession
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
logging.getLogger('bokeh.server.views.ws').setLevel(logging.DEBUG)
logging.getLogger('bokeh.server.session').setLevel(logging.DEBUG)
logging.getLogger('bokeh.server.protocol_handler').setLevel(logging.DEBUG)


def _install_bokeh_event_dispatch_diagnostics():
    """Log callback-manager change and event dispatch paths for client messages."""
    if getattr(DocumentCallbackManager, '_isolator_diag_installed', False):
        return

    original_trigger_on_change = DocumentCallbackManager.trigger_on_change
    original_trigger_event = DocumentCallbackManager.trigger_event

    def _wrapped_trigger_on_change(self, event):
        try:
            event_name = type(event).__name__
            msg_type = getattr(event, 'msg_type', None)
            logger.info(
                f"CallbackManager trigger_on_change event={event_name} msg_type={msg_type}"
            )
        except Exception as diag_err:
            logger.warning(f"CallbackManager trigger_on_change diagnostic failed: {diag_err}")

        return original_trigger_on_change(self, event)

    def _wrapped_trigger_event(self, event):
        try:
            event_name = type(event).__name__
            # ModelEvent stores the source widget as .model (not .origin)
            model = getattr(event, 'model', None)
            model_id = getattr(model, 'id', None)
            model_type = type(model).__name__ if model is not None else None
            # How many models are subscribed for this event name?
            subscribed = self._subscribed_models.get(getattr(event, 'event_name', ''), set())
            subscribed_ids = [getattr(r(), 'id', '(dead)') for r in subscribed if r() is not None]
            logger.info(
                f"CallbackManager trigger_event event={event_name} "
                f"model_id={model_id} model_type={model_type} "
                f"subscribed_count={len(subscribed)} subscribed_ids={subscribed_ids}"
            )
        except Exception as diag_err:
            logger.warning(f"CallbackManager trigger_event diagnostic failed: {diag_err}")

        return original_trigger_event(self, event)

    DocumentCallbackManager.trigger_on_change = _wrapped_trigger_on_change
    DocumentCallbackManager.trigger_event = _wrapped_trigger_event
    DocumentCallbackManager._isolator_diag_installed = True


_install_bokeh_event_dispatch_diagnostics()


def _install_patch_doc_diagnostics():
    """Log inbound PATCH-DOC event payload summary before document apply."""
    if getattr(ServerSession, '_isolator_patch_diag_installed', False):
        return

    original_handle_patch = ServerSession._handle_patch

    def _wrapped_handle_patch(self, message, connection):
        try:
            content = getattr(message, 'content', {}) or {}
            events = content.get('events', []) if isinstance(content, dict) else []
            kinds = []
            msg_types = []
            message_sent_details = []
            for event in events:
                if not isinstance(event, dict):
                    continue
                kind = event.get('kind')
                if kind:
                    kinds.append(kind)
                if kind == 'MessageSent':
                    msg_type = event.get('msg_type')
                    msg_types.append(msg_type)
                    msg_data = event.get('msg_data', {}) if isinstance(event.get('msg_data'), dict) else {}
                    values = msg_data.get('values', {}) if isinstance(msg_data, dict) else {}
                    entries = values.get('entries', []) if isinstance(values, dict) else []
                    model_id = None
                    for entry in entries:
                        if not isinstance(entry, list) or len(entry) != 2:
                            continue
                        if entry[0] == 'model' and isinstance(entry[1], dict):
                            model_id = entry[1].get('id')
                            break
                    message_sent_details.append((msg_data.get('name'), model_id))

            if events:
                logger.info(
                    f"PATCH-DOC inbound session={self.id} event_count={len(events)} kinds={kinds[:6]} msg_types={msg_types[:6]} msg_sent_details={message_sent_details[:6]}"
                )
        except Exception as diag_err:
            logger.warning(f"PATCH-DOC diagnostic failed: {diag_err}")

        return original_handle_patch(self, message, connection)

    ServerSession._handle_patch = _wrapped_handle_patch
    ServerSession._isolator_patch_diag_installed = True


_install_patch_doc_diagnostics()

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
        session_id = doc.session_context.id
        request = getattr(doc.session_context, 'request', None)
        remote_ip = getattr(request, 'remote_ip', 'unknown') if request else 'unknown'
        user_agent = ''
        if request and getattr(request, 'headers', None):
            user_agent = request.headers.get('User-Agent', '')
        logger.info(f"New client connected: session={session_id} remote_ip={remote_ip} user_agent={user_agent}")
        
        # Create the main layout and get widget references
        layout, widgets = create_dashboard_layout(self.data_manager)

        # Detect reused model objects in layout tree (can cause "reference already known" warnings).
        seen_nodes = []

        def walk(node):
            if node is None:
                return
            seen_nodes.append(node)
            children = getattr(node, 'children', None)
            if children:
                for child in children:
                    walk(child)

        walk(layout)
        py_id_counts = Counter(id(node) for node in seen_nodes)
        duplicates = [node for node in seen_nodes if py_id_counts[id(node)] > 1]
        if duplicates:
            unique_dupes = {}
            for node in duplicates:
                unique_dupes[id(node)] = node
            for node in unique_dupes.values():
                model_id = getattr(node, 'id', 'n/a')
                logger.warning(
                    f"Duplicate model in layout tree: type={type(node).__name__}, model_id={model_id}, occurrences={py_id_counts[id(node)]}"
                )

        doc.add_root(layout)

        # Diagnostic: compare message callback channels available for this document.
        try:
            cb_mgr = getattr(doc, 'callbacks', None)
            logger.info(f"Callback manager session={session_id} type={type(cb_mgr).__name__}")
            msg_callbacks = getattr(cb_mgr, '_message_callbacks', None)
            if isinstance(msg_callbacks, dict):
                logger.info(f"Document message callback keys session={session_id}: {list(msg_callbacks.keys())}")
            else:
                logger.info(f"Document message callbacks unavailable session={session_id} type={type(msg_callbacks).__name__}")
        except Exception as e:
            logger.warning(f"Failed to inspect document message callbacks session={session_id}: {e}")
        
        # Store widget references on document for callbacks
        for key, value in widgets.items():
            setattr(doc, key, value)
        
        # Set up periodic callbacks for live updates
        setup_callbacks(doc, self.data_manager)

        def _on_session_destroyed(session_context):
            logger.info(f"Client session destroyed: session={session_context.id}")

        doc.on_session_destroyed(_on_session_destroyed)
        
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
        session_token_expiration=86400000,  # 24 hours (in milliseconds)
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
