"""
Common Bokeh dashboard components shared across all PerimeterControl service dashboards.

Provides:
  - create_service_status_panel(service_name, log_dir, unit_name)
      Status card showing systemd service state, log file links, and quick SSH commands.
  - create_log_tail_panel(log_path)
      Scrolling pre-formatted log tail (auto-refreshed by callbacks).

Usage in a dashboard layout:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dashboard_common import create_service_status_panel, create_log_tail_panel
"""
from bokeh.layouts import column, row
from bokeh.models import Div, PreText, Button, Select, ColumnDataSource, DataTable, TableColumn


def create_service_status_panel(service_name: str, log_dir: str = "/var/log/PerimeterControl",
                                 unit_name: str | None = None) -> tuple:
    """
    Returns (layout, widgets) with a service health card and quick-action buttons.

    The layout contains:
      - Service name and unit name
      - systemd status badge (updated by periodic callback)
      - Log file links (clickable paths users can copy/tail)
      - Common SSH troubleshooting commands pre-filled for this service
    """
    if unit_name is None:
        unit_name = f"perimetercontrol-{service_name.lower().replace('_', '-')}-dashboard"

    service_log = f"{log_dir}/{service_name}_dashboard.log"
    supervisor_log = f"{log_dir}/supervisor.log"

    status_html = f"""
    <div style="background:#2c3e50;color:#ecf0f1;padding:14px;border-radius:6px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <h3 style="margin:0;font-size:16px;">🔧 Service Status — {service_name}</h3>
        <span id="svc-badge-{service_name}"
              style="background:#27ae60;color:white;padding:3px 10px;border-radius:12px;font-size:12px;">
          checking…
        </span>
      </div>
      <table style="font-size:12px;border-collapse:collapse;width:100%;">
        <tr>
          <td style="color:#bdc3c7;padding:3px 8px 3px 0;white-space:nowrap;">Unit</td>
          <td><code style="color:#3498db;">{unit_name}.service</code></td>
        </tr>
        <tr>
          <td style="color:#bdc3c7;padding:3px 8px 3px 0;white-space:nowrap;">Service log</td>
          <td><code style="color:#f39c12;">{service_log}</code></td>
        </tr>
        <tr>
          <td style="color:#bdc3c7;padding:3px 8px 3px 0;white-space:nowrap;">Supervisor log</td>
          <td><code style="color:#f39c12;">{supervisor_log}</code></td>
        </tr>
      </table>
      <hr style="border-color:#7f8c8d;margin:10px 0;">
      <p style="font-size:11px;color:#bdc3c7;margin:0 0 4px 0;">Quick SSH commands:</p>
      <code style="background:#1a252f;font-size:10px;padding:6px;display:block;border-radius:4px;white-space:pre-wrap;">
systemctl status {unit_name}
journalctl -u {unit_name} -n 50 --no-pager
tail -f {service_log}
tail -f {supervisor_log}</code>
    </div>
    """

    status_div = Div(text=status_html, sizing_mode="stretch_width")
    widgets = {"service_status_div": status_div}
    layout = column(status_div, sizing_mode="stretch_width")
    return layout, widgets


def create_log_tail_panel(log_path: str = "/var/log/PerimeterControl/supervisor.log",
                           title: str = "Recent Log Entries",
                           height: int = 220) -> tuple:
    """
    Returns (layout, widgets) with a scrollable pre-formatted log tail.

    The PreText widget is keyed as 'log_tail_text' in widgets.
    Wire a periodic callback to update it:

        def update_log():
            try:
                lines = subprocess.check_output(
                    ["tail", "-n", "40", log_path], text=True
                )
                doc.widgets["log_tail_text"].text = lines
            except Exception:
                pass
        doc.add_periodic_callback(update_log, 5000)
    """
    header = Div(
        text=f"<h4 style='margin:0 0 6px 0;color:#ecf0f1;'>📋 {title}</h4>"
             f"<p style='margin:0 0 6px 0;font-size:11px;color:#95a5a6;'>{log_path}</p>",
    )

    log_text = PreText(
        text="Loading log…",
        height=height,
        sizing_mode="stretch_width",
        styles={
            "background-color": "#1a252f",
            "color": "#ecf0f1",
            "font-family": "monospace",
            "font-size": "11px",
            "padding": "8px",
            "border-radius": "4px",
            "overflow-y": "auto",
        },
    )

    layout = column(
        Div(text="<div style='background:#2c3e50;padding:10px;border-radius:6px;'>",
            sizing_mode="stretch_width"),
        column(header, log_text, sizing_mode="stretch_width"),
        sizing_mode="stretch_width",
    )
    widgets = {"log_tail_text": log_text}
    return layout, widgets
