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
    from dashboard_common import create_service_status_panel, create_log_tail_panel
    from bokeh.layouts import column as bk_column
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
    log_dir = config.get('log_root', '/var/log/PerimeterControl')
    supervisor_api_url = config.get('supervisor_api_url')
    final_supervisor_api_url = supervisor_api_url or data_manager.supervisor_api_url
    if not supervisor_api_url:
        logger.info(f"supervisor_api_url not set in config; using fallback {final_supervisor_api_url}")
    # Ensure log directory exists and enable file-based logging for dashboards
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'wildlife_dashboard.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )

    def create_app(doc):
        layout, widgets = create_wildlife_dashboard_layout(data_manager)
        status_layout, status_widgets = create_service_status_panel("wildlife_monitor", log_dir=log_dir)
        log_layout, log_widgets = create_log_tail_panel(
            f"{log_dir}/wildlife_dashboard.log", title="Wildlife Log"
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
        setup_wildlife_callbacks(doc, data_manager)
        doc.title = "Wildlife Dashboard"
                try:
                        tmpl_path = Path(__file__).parent / "static" / "html" / "pc-dashboard-template.html"
                        if tmpl_path.exists():
                                doc.template = tmpl_path.read_text(encoding="utf-8")
                except Exception:
                        pass

    port = int(config.get('port', 8094))

    handler = FunctionHandler(create_app)
    app = Application(handler)
    from dashboard_common import get_extra_static_patterns
    extra_patterns = get_extra_static_patterns()
    server = Server({'/': app}, port=port, address='0.0.0.0', allow_websocket_origin=["*"], extra_patterns=extra_patterns)
    server.start()
    server.io_loop.start()
    return 0

if __name__ == "__main__":
    import sys
    from pathlib import Path
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/perimeterControl.conf.yaml")
    sys.exit(main(config))
