"""
BLE GATT Repeater service-specific dashboard entry point.
Migrated from ble_gatt_bokeh_dashboard.py.
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
from tornado.ioloop import IOLoop
from ble_gatt_repeater_layouts import create_ble_gatt_repeater_dashboard_layout
from ble_gatt_repeater_callbacks import setup_ble_gatt_repeater_callbacks
from data_manager import DataManager
from dashboard_common import create_service_status_panel, create_log_tail_panel, setup_common_dashboard_callbacks
from bokeh.layouts import column as bk_column
from pathlib import Path

def main(config_path):
    # Load config and instance
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    instances = config.get('services', {}).get('ble_gatt_repeater', {})
    instance_name, instance_config = next(iter(instances.items())) if instances else (None, {})
    log_root = instance_config.get('log_root', '/var/log/PerimeterControl')
    port = int(instance_config.get('port', 8091))
    log_file = os.path.join(log_root, 'ble_gatt_dashboard.log')
    logger_name = 'perimetercontrol.ble_gatt_dashboard'
    os.makedirs(log_root, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    logger = logging.getLogger(logger_name)
    data_manager = DataManager(config_path)
    supervisor_api_url = instance_config.get('supervisor_api_url') or config.get('supervisor_api_url')
    final_supervisor_api_url = supervisor_api_url or data_manager.supervisor_api_url
    if not supervisor_api_url:
        logging.info(f"supervisor_api_url not set in config; using fallback {final_supervisor_api_url}")
    unit_name = "perimetercontrol-ble-dashboard"
    service_log_path = f"{log_root}/ble_gatt_dashboard.log"
    supervisor_log_path = f"{log_root}/supervisor.log"
    def create_app(doc):
        layout, widgets = create_ble_gatt_repeater_dashboard_layout(data_manager)
        status_layout, status_widgets = create_service_status_panel(
            "ble_gatt_repeater", log_dir=log_root, unit_name=unit_name
        )
        log_layout, log_widgets = create_log_tail_panel(
            service_log_path, title="BLE Log"
        )
        full_layout = bk_column(layout, status_layout, log_layout, sizing_mode="stretch_width")
        doc.add_root(full_layout)
        # Ensure jQuery/jQuery UI loader is present for DataTable features
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
            service_name="ble_gatt_repeater",
            unit_name=unit_name,
            service_log_path=service_log_path,
            supervisor_log_path=supervisor_log_path,
        )
        setup_ble_gatt_repeater_callbacks(doc, data_manager)
        doc.title = f"BLE GATT Repeater Dashboard - {instance_name or 'default'}"
    handler = FunctionHandler(create_app)
    app = Application(handler)
    from dashboard_common import get_extra_static_patterns
    extra_patterns = get_extra_static_patterns()
    server = Server({'/': app}, port=port, address="0.0.0.0", allow_websocket_origin=["*"], extra_patterns=extra_patterns)
    logger.info(f"BLE GATT Bokeh dashboard running on port {port} (instance: {instance_name})")
    server.start()
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        logger.info("Shutting down BLE GATT dashboard...")
    return 0
if __name__ == "__main__":
    import sys
    config = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/PerimeterControl/conf/ble-gatt-repeater.yaml")
    sys.exit(main(config))