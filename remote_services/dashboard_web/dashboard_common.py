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
from bokeh.layouts import column, row, Spacer
from bokeh.models import Div, PreText, Button, Select, ColumnDataSource, DataTable, TableColumn
from bokeh.io import curdoc
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
            f"<p class='pc-header-item'>Unit: <code>{unit_name}.service</code></p>"
            f"<p class='pc-header-item'>Service log: <code>{service_log}</code></p>"
            f"<p class='pc-header-item'>Supervisor log: <code>{supervisor_log}</code></p>"
            "</div>"
        ),
        sizing_mode="stretch_width",
    )
    status_badge = Div(
        text="<b>Status:</b> <span class='status-checking'>checking...</span>",
        sizing_mode="stretch_width",
        css_classes=["status-badge"]
    )
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

    def _get_style_div() -> Div:
        """Return a Div with a <link> tag to load CSS via HTTP request.

        Uses /css/ path instead of /static/ to avoid Bokeh's default static handler.
        This allows CSS to be served with a custom handler that we control.
        """
        _DC_LOGGER.debug("[CSS] Preparing style div for client-side CSS loading")
        
        # Use /css/ path instead of /static/css/ to avoid Bokeh's default handler
        css_link_html = (
            "<link rel='stylesheet' href='/css/pc-dashboard.css' "
            "onerror=\"console.error('CSS failed to load'); this.remove();\">"
        )
        _DC_LOGGER.debug("[CSS] Returning external CSS link tag: /css/pc-dashboard.css")
        return Div(text=css_link_html, sizing_mode="stretch_width")

    # Style + controls belong to the service panel; build them here.
    style_div = _get_style_div()

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

    # Attach a local click handler so the button works even if external
    # wiring isn't performed. Uses curdoc().add_next_tick_callback to
    # update the UI from a background thread safely.
    def _local_on_ssh_run_click():
        cmd = ssh_command_select.value
        _DC_LOGGER.info("Local Run Command clicked: %s", cmd)
        try:
            ssh_command_output.text = f"Running: {cmd}"
        except Exception:
            pass

        def _worker():
            out = _run_shell(cmd, timeout=10)

            def _update_output():
                try:
                    ssh_command_output.text = out
                except Exception:
                    pass

            try:
                curdoc().add_next_tick_callback(_update_output)
            except Exception:
                # Last-resort: set directly
                try:
                    ssh_command_output.text = out
                except Exception:
                    pass

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    try:
        ssh_run_button.on_click(_local_on_ssh_run_click)
    except Exception:
        _DC_LOGGER.exception("Failed to bind local Run Command handler")

    # Flatten the layout: avoid nested columns to prevent Bokeh layout engine bugs
    # Use wrapper Divs with CSS classes instead of inline styles
    layout = column(
        style_div,
        header,
        Spacer(height=12),
        status_badge,
        status_details,
        Spacer(height=12),
        Div(
            text="<div class='pc-section-title'><b>Service Log</b></div>",
            sizing_mode="stretch_width",
            css_classes=["pc-section-title-container"],
        ),
        service_log_text,
        Spacer(height=12),
        Div(
            text="<div class='pc-section-title'><b>Supervisor Log</b></div>",
            sizing_mode="stretch_width",
            css_classes=["pc-section-title-container"],
        ),
        supervisor_log_text,
        Spacer(height=12),
        ssh_command_select,
        Spacer(height=6),
        row(ssh_run_button, sizing_mode="stretch_width"),
        Spacer(height=6),
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


def get_loader_div() -> Div:
    """Return a Div that loads jQuery UI support for DataTable.reorderable.
    
    Loads datatable-loader.js which ensures jQuery UI is ready and injects
    minimal CSS for drag/drop column support.
    """
    loader_html = '<script src="/js/datatable-loader.js"></script>'
    return Div(text=loader_html, sizing_mode="stretch_width")


def get_extra_static_patterns():
    """Return Tornado extra_patterns to serve static files (CSS, JS) directly.
    
    Uses /css/ and /js/ paths to avoid Bokeh's built-in static handler.
    Serves from: remote_services/dashboard_web/static/{css,js}/ (dev)
                  or /opt/PerimeterControl/web/static/{css,js}/ (deployed)
    """
    from tornado.web import RequestHandler
    from mimetypes import guess_type
    
    # Determine paths at startup
    local_base = Path(__file__).parent / "static"
    deployed_base = Path("/opt/PerimeterControl/web/static")
    
    static_base = None
    if local_base.exists():
        static_base = local_base
        _DC_LOGGER.info("[STATIC_SETUP] Using local dev static path: %s", local_base)
    elif deployed_base.exists():
        static_base = deployed_base
        _DC_LOGGER.info("[STATIC_SETUP] Using deployed static path: %s", deployed_base)
    else:
        _DC_LOGGER.error("[STATIC_SETUP] Static base not found at %s or %s", local_base, deployed_base)
    
    class StaticFileHandler(RequestHandler):
        """Serve static files (CSS, JS, HTML) with proper MIME types."""
        def get(self, file_type, file_name):
            if static_base is None:
                _DC_LOGGER.error("[STATIC_HANDLER] Static base not found at startup")
                self.set_status(404)
                return
            
            file_path = static_base / file_type / file_name
            
            # Security check: prevent path traversal
            try:
                file_path = file_path.resolve()
                if not str(file_path).startswith(str(static_base.resolve())):
                    _DC_LOGGER.error("[STATIC_HANDLER] Path traversal attempt: %s", file_path)
                    self.set_status(403)
                    return
            except Exception as e:
                _DC_LOGGER.error("[STATIC_HANDLER] Path resolution error: %s", e)
                self.set_status(400)
                return
            
            if not file_path.exists():
                _DC_LOGGER.warning("[STATIC_HANDLER] File not found: %s", file_path)
                self.set_status(404)
                return
            
            try:
                content = file_path.read_bytes()
                mime_type, _ = guess_type(str(file_path))
                if mime_type is None:
                    # Fallback MIME types
                    if file_path.suffix == ".css":
                        mime_type = "text/css"
                    elif file_path.suffix == ".js":
                        mime_type = "application/javascript"
                    elif file_path.suffix == ".html":
                        mime_type = "text/html"
                    else:
                        mime_type = "application/octet-stream"
                
                _DC_LOGGER.debug("[STATIC_HANDLER] Serving /%s/%s (%s) - %d bytes", 
                                file_type, file_name, mime_type, len(content))
                self.set_header("Content-Type", mime_type)
                self.write(content)
            except Exception as e:
                _DC_LOGGER.error("[STATIC_HANDLER] Error reading file %s: %s", file_path, e)
                self.set_status(500)
    
    if static_base:
        _DC_LOGGER.info("[STATIC_SETUP] Registering static file handler for /css/, /js/, /html/")
        return [(r"/(css|js|html)/(.+)", StaticFileHandler, {})]
    else:
        _DC_LOGGER.error("[STATIC_SETUP] Static handler NOT registered - base path not found")
        return None
 


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
        text=(
            "<div class='pc-header' style='position:relative; z-index:2;'>"
            f"<h4 class='pc-h4-no-margin'>📋 {title}</h4>"
            f"<p class='pc-muted'>{log_path}</p>"
            "</div>"
        ),
        sizing_mode="stretch_width"
    )

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
            doc.service_status_badge.text = "<b>Status:</b> <span class='status-active'>active</span>"
        elif "activating" in status:
            doc.service_status_badge.text = "<b>Status:</b> <span class='status-activating'>activating</span>"
        else:
            doc.service_status_badge.text = "<b>Status:</b> <span class='status-inactive'>inactive/failing</span>"

        doc.service_status_details.text = _run_shell(f"systemctl status {unit_name} --no-pager", timeout=6)

        service_tail = _tail_file(service_log_path, lines=60)
        supervisor_tail = _tail_file(supervisor_log_path, lines=60)

        # If files are missing or unreadable, fall back to reading the
        # systemd journal for the relevant unit. This covers services
        # that log only to the journal (common on modern systems).
        if (service_tail.startswith("Log not found:") or service_tail.startswith("Failed to read log") or service_tail.startswith("Log is empty:")):
            try:
                j = subprocess.run(
                    ["journalctl", "-u", unit_name, "-n", "60", "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                service_tail = j.stdout.strip() or f"<no journal entries for {unit_name}>"
            except Exception as exc:  # pragma: no cover - defensive
                service_tail = f"Failed to read journal for {unit_name}: {exc}"

        if (supervisor_tail.startswith("Log not found:") or supervisor_tail.startswith("Failed to read log") or supervisor_tail.startswith("Log is empty:")):
            # Supervisor logs may be provided by a dedicated unit; try
            # the conventional perimetercontrol-supervisor unit as a
            # best-effort fallback.
            try:
                j2 = subprocess.run(
                    ["journalctl", "-u", "perimetercontrol-supervisor", "-n", "60", "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                supervisor_tail = j2.stdout.strip() or f"<no journal entries for perimetercontrol-supervisor>"
            except Exception as exc:  # pragma: no cover - defensive
                supervisor_tail = f"Failed to read journal for perimetercontrol-supervisor: {exc}"
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
