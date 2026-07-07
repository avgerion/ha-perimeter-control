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
from dashboard_common import create_service_status_panel, create_log_tail_panel, setup_common_dashboard_callbacks
from bokeh.layouts import column as bk_column
from pathlib import Path
import yaml

def main(config_path):
    # Use the unified config file and select the correct instance config
    config_path = Path(config_path)
    if not config_path.exists():
        # Fallback: create minimal bootstrap config if file not deployed yet
        logger = logging.getLogger('perimetercontrol.photo_booth_dashboard')
        logger.warning(f"Config file not found: {config_path}. Using bootstrap defaults.")
        config = {
            'services': {'photo_booth': {}},
            'log_root': '/var/log/PerimeterControl'
        }
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    booth_instances = config.get('services', {}).get('photo_booth', {})
    instance_name, instance_config = next(iter(booth_instances.items())) if booth_instances else (None, {})
    log_root = instance_config.get('log_root') or config.get('log_root', '/var/log/PerimeterControl')
    supervisor_api_url = config.get('supervisor_api_url')
    port = int(instance_config.get('port', 8093))
    logger_name = 'perimetercontrol.photo_booth_dashboard'
    os.makedirs(log_root, exist_ok=True)
    log_file = os.path.join(log_root, 'photo_booth_dashboard.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logger = logging.getLogger(logger_name)
    data_manager = DataManager(config_path)
    # Ensure a usable supervisor API URL is always available for dashboards.
    # Prefer explicit config value, otherwise fall back to what DataManager computes.
    final_supervisor_api_url = supervisor_api_url or data_manager.supervisor_api_url
    if not supervisor_api_url:
        logging.info(f"supervisor_api_url not set in config; using fallback {final_supervisor_api_url}")
    unit_name = "perimetercontrol-photo-booth-dashboard"
    service_log_path = f"{log_root}/photo_booth_dashboard.log"
    supervisor_log_path = f"{log_root}/supervisor.log"
    def create_app(doc):
        layout, widgets = create_photo_booth_dashboard_layout(data_manager)
        status_layout, status_widgets = create_service_status_panel(
            "photo_booth", log_dir=log_root, unit_name=unit_name
        )
        log_layout, log_widgets = create_log_tail_panel(
            service_log_path, title="Photo Booth Log"
        )
        full_layout = bk_column(layout, status_layout, log_layout, sizing_mode="stretch_width")
        doc.add_root(full_layout)
        try:
            from dashboard_common import _get_style_div, get_loader_div
            doc.add_root(_get_style_div())
            doc.add_root(get_loader_div())
        except Exception:
            pass
        for key, value in {**widgets, **status_widgets, **log_widgets}.items():
            setattr(doc, key, value)
        doc.supervisor_api_url = final_supervisor_api_url
        setup_common_dashboard_callbacks(
            doc,
            service_name="photo_booth",
            unit_name=unit_name,
            service_log_path=service_log_path,
            supervisor_log_path=supervisor_log_path,
        )
        setup_photo_booth_callbacks(doc, data_manager)
        doc.title = f"Photo Booth Dashboard - {instance_name or 'default'}"
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
    server = Server({'/': app}, port=port, address="0.0.0.0", allow_websocket_origin=["*"], index=app_template, extra_patterns=extra_patterns)
    logger.info(f"Photo Booth Bokeh dashboard running on port {port} (instance: {instance_name})")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down Photo Booth dashboard...")
    return 0

if __name__ == "__main__":
    import sys
    config = Path("/mnt/PerimeterControl/conf/perimeterControl.conf.yaml")
    sys.exit(main(config))
