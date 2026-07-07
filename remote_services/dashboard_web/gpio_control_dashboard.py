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
from gpio_control_callbacks import setup_gpio_control_callbacks
from data_manager import DataManager
from dashboard_common import create_service_status_panel, create_log_tail_panel, setup_common_dashboard_callbacks
from bokeh.layouts import column as bk_column
from pathlib import Path


def main(config_path):
    config_path = Path(config_path)
    if not config_path.exists():
        # Fallback: create minimal bootstrap config if file not deployed yet
        logger = logging.getLogger('perimetercontrol.gpio_dashboard')
        logger.warning(f"Config file not found: {config_path}. Using bootstrap defaults.")
        config = {
            'services': {'gpio_control': {}},
            'log_root': '/var/log/PerimeterControl'
        }
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    instances = config.get('services', {}).get('gpio_control', {})
    instance_name, instance_config = next(iter(instances.items())) if instances else (None, {})
    port = int(instance_config.get('port', 8095))
    log_root = instance_config.get('log_root', '/var/log/PerimeterControl')
    os.makedirs(log_root, exist_ok=True)
    log_file = os.path.join(log_root, 'gpio_dashboard.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logger = logging.getLogger('perimetercontrol.gpio_dashboard')
    logger.info("[GPIO_DASH] Starting GPIO Control dashboard")
    logger.info("[GPIO_DASH] Config path: %s", config_path)
    logger.info("[GPIO_DASH] Log file: %s", log_file)
    logger.debug("[GPIO_DASH] Config loaded successfully")
    data_manager = DataManager(config_path)
    supervisor_api_url = instance_config.get('supervisor_api_url') or config.get('supervisor_api_url')
    final_supervisor_api_url = supervisor_api_url or data_manager.supervisor_api_url
    if not supervisor_api_url:
        logging.info(f"supervisor_api_url not set in config; using fallback {final_supervisor_api_url}")
    unit_name = "perimetercontrol-gpio-dashboard"
    service_log_path = f"{log_root}/gpio_dashboard.log"
    supervisor_log_path = f"{log_root}/supervisor.log"

    def create_app(doc):
        layout, widgets = create_gpio_control_dashboard_layout(data_manager)
        status_layout, status_widgets = create_service_status_panel(
            "gpio_control", log_dir=log_root, unit_name=unit_name
        )
        log_layout, log_widgets = create_log_tail_panel(
            service_log_path, title="GPIO Log"
        )
        full_layout = bk_column(layout, status_layout, log_layout, sizing_mode="stretch_width")
        doc.add_root(full_layout)
        # Provide a minimal HTML template for the Bokeh document to avoid
        # server-default headers that inject restrictive global styles
        # (e.g. `display: flow-root; height:100%`) which break layout.
        # Load shared minimal HTML template from static/html to avoid
        # embedding the template directly in Python files and to ensure
        # the document head does not inject restrictive global styles.
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
            service_name="gpio_control",
            unit_name=unit_name,
            service_log_path=service_log_path,
            supervisor_log_path=supervisor_log_path,
        )
        setup_gpio_control_callbacks(doc, data_manager)
        doc.title = f"GPIO Control Dashboard - {instance_name or 'default'}"

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
    app = Application(handler)
    from dashboard_common import get_extra_static_patterns
    extra_patterns = get_extra_static_patterns()
    if app_template:
        logger.info("Starting server with application index template (len=%d)", len(app_template))
    else:
        logger.info("Starting server without application index template; Bokeh default index will be used")
    server = Server({'/': app}, port=port, address="0.0.0.0", allow_websocket_origin=["*"], index=app_template, extra_patterns=extra_patterns)
    logger.info(f"GPIO Control dashboard running on port {port}")
    logger.info("[GPIO_DASH] CSS will be loaded from /css/pc-dashboard.css via HTTP (custom handler, not Bokeh /static/)")
    logger.info("[GPIO_DASH] Check server logs for GET /css/pc-dashboard.css requests")
    logger.debug("[GPIO_DASH] Extra static patterns: %s", extra_patterns)
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down GPIO Control dashboard...")
    return 0


if __name__ == "__main__":
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/perimeterControl.conf.yaml")
    sys.exit(main(config))
