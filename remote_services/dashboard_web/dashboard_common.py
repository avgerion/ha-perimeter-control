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
import subprocess
import logging
from pathlib import Path

_DC_LOGGER = logging.getLogger("perimetercontrol.dashboard_common")


def _tail_file(path: str, lines: int = 40) -> str:
  """Return a small tail from a local log file with friendly error text."""
  try:
    file_path = Path(path)
    if not file_path.exists():
      return f"Log not found: {path}"
    content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not content:
      return f"Log is empty: {path}"
    return "\n".join(content[-lines:])
  except Exception as exc:
    return f"Failed to read log {path}: {exc}"


def _run_shell(command: str, timeout: int = 8) -> str:
  """Execute a local shell command and return combined output."""
  try:
    result = subprocess.run(
      command,
      shell=True,
      check=False,
      capture_output=True,
      text=True,
      timeout=timeout,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    output = output.strip() or "<no output>"
    return f"$ {command}\n[exit={result.returncode}]\n{output}"
  except Exception as exc:
    return f"$ {command}\n[error] {exc}"


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

    # Add a small inline style to ensure the header occupies normal flow
    # even if external CSS hasn't loaded yet (defensive fallback).
    header = Div(
        text=(
            "<div class='pc-header' style='position:relative; z-index:2; margin-bottom:12px;'>"
            f"<h3>Service Status - {service_name}</h3>"
            f"<p>Unit: <code>{unit_name}.service</code></p>"
            f"<p>Service log: <code>{service_log}</code><br>"
            f"Supervisor log: <code>{supervisor_log}</code></p>"
            "</div>"
        ),
        sizing_mode="stretch_width",
    )
    status_badge = Div(text="<b>Status:</b> checking...", sizing_mode="stretch_width")
    status_details = PreText(text="Waiting for first health check...", height=90, sizing_mode="stretch_width")

    # Use PreText widgets for log content and style them via CSS classes so
    # they behave consistently and avoid overlapping other Divs.
    service_log_text = PreText(
        text="Loading service log...",
        height=140,
        sizing_mode="stretch_width",
        css_classes=["pc-log"],
    )
    supervisor_log_text = PreText(
        text="Loading supervisor log...",
        height=140,
        sizing_mode="stretch_width",
        css_classes=["pc-log"],
    )

    # Provide a simple link to the shared static CSS file. Widgets that need
    # per-dashboard overrides can still inject small inline style blocks.
    style_div = Div(text="<link rel='stylesheet' href='/static/css/pc-dashboard.css'>", sizing_mode="stretch_width")

    ssh_command_select = Select(
        title="Run service command",
        value=f"systemctl status {unit_name} --no-pager",
        options=[
            f"systemctl status {unit_name} --no-pager",
            f"journalctl -u {unit_name} -n 50 --no-pager",
            f"tail -n 60 {service_log}",
            f"tail -n 60 {supervisor_log}",
            f"systemctl restart {unit_name}",
        ],
        sizing_mode="stretch_width",
    )
    ssh_run_button = Button(label="Run Command", button_type="primary", sizing_mode="stretch_width")
    ssh_command_output = PreText(
        text="Command output will appear here.",
        height=140,
        sizing_mode="stretch_width",
        css_classes=["pc-command-output"],
    )

    # Group status and logs into explicit vertical sections so Bokeh's
    # layout engine stacks them reliably instead of attempting absolute
    # positioning that can overlap dynamic preformatted text.
    status_section = column(status_badge, status_details, sizing_mode="stretch_width")
    # Ensure section titles provide spacing even without external CSS
    service_log_section = column(
        Div(text="<div class='pc-section-title' style='margin-top:12px; margin-bottom:6px;'><b>Service Log</b></div>"),
        service_log_text,
        sizing_mode="stretch_width",
    )
    supervisor_log_section = column(
        Div(text="<div class='pc-section-title' style='margin-top:12px; margin-bottom:6px;'><b>Supervisor Log</b></div>"),
        supervisor_log_text,
        sizing_mode="stretch_width",
    )

    layout = column(
        style_div,
        header,
        status_section,
        service_log_section,
        supervisor_log_section,
        ssh_command_select,
        row(ssh_run_button, sizing_mode="stretch_width"),
        ssh_command_output,
        sizing_mode="stretch_width",
    )
    widgets = {
        "service_status_badge": status_badge,
        "service_status_details": status_details,
        "service_log_text": service_log_text,
        "supervisor_log_text": supervisor_log_text,
        "ssh_command_select": ssh_command_select,
        "ssh_run_button": ssh_run_button,
        "ssh_command_output": ssh_command_output,
    }
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
    header_html = (
        f"<div style='background:#2c3e50;padding:10px;border-radius:6px;'>"
        f"<h4 style='margin:0 0 6px 0;color:#ecf0f1;'>📋 {title}</h4>"
        f"<p style='margin:0 0 6px 0;font-size:11px;color:#95a5a6;'>{log_path}</p>"
        f"</div>"
    )

    header = Div(text=header_html, sizing_mode="stretch_width")

    log_text = PreText(
        text="Loading log…",
        height=height,
        sizing_mode="stretch_width",
    )

    # Wrap header and log text in a container so layout HTML remains well-formed
    container = column(header, log_text, sizing_mode="stretch_width")
    layout = column(container, sizing_mode="stretch_width")
    widgets = {"log_tail_text": log_text}
    return layout, widgets


def setup_common_dashboard_callbacks(
    doc,
    service_name: str,
    unit_name: str,
    service_log_path: str,
    supervisor_log_path: str,
    refresh_ms: int = 5000,
) -> None:
    """Attach polling callbacks shared by all service dashboards."""

    def _update_status_and_logs() -> None:
        status = _run_shell(f"systemctl is-active {unit_name}", timeout=4).lower()
        if "active" in status and "inactive" not in status and "failed" not in status:
            doc.service_status_badge.text = "<b>Status:</b> <span style='color:#27ae60;'>active</span>"
        elif "activating" in status:
            doc.service_status_badge.text = "<b>Status:</b> <span style='color:#f39c12;'>activating</span>"
        else:
            doc.service_status_badge.text = "<b>Status:</b> <span style='color:#e74c3c;'>inactive/failing</span>"

        doc.service_status_details.text = _run_shell(f"systemctl status {unit_name} --no-pager", timeout=6)

        service_tail = _tail_file(service_log_path, lines=60)
        supervisor_tail = _tail_file(supervisor_log_path, lines=60)
        doc.service_log_text.text = service_tail
        doc.supervisor_log_text.text = supervisor_tail

        if hasattr(doc, "log_tail_text"):
            doc.log_tail_text.text = service_tail

    def _run_selected_command() -> None:
        cmd = doc.ssh_command_select.value
        doc.ssh_command_output.text = _run_shell(cmd, timeout=10)

    # Run commands in a background thread to avoid blocking the Bokeh IOLoop.
    # Use add_next_tick_callback to safely update document models from the
    # IOLoop thread after the background work completes.
    def _on_ssh_run_click():
        cmd = doc.ssh_command_select.value
        _DC_LOGGER.info("Run Command clicked: %s", cmd)

        # Immediate feedback in UI
        try:
            doc.ssh_command_output.text = f"Running: {cmd}"
        except Exception:
            pass

        def _worker():
            out = _run_shell(cmd, timeout=10)

            def _update_output():
                doc.ssh_command_output.text = out

            try:
                doc.add_next_tick_callback(_update_output)
            except Exception:
                # Fallback: set directly if scheduling fails
                try:
                    doc.ssh_command_output.text = out
                except Exception:
                    pass

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    doc.ssh_run_button.on_click(_on_ssh_run_click)
    doc.add_periodic_callback(_update_status_and_logs, refresh_ms)
    _update_status_and_logs()
