#!/usr/bin/env python3
"""
Dashboard layout definitions using Bokeh widgets and plots.
Creates the visual structure of the Network Isolator Quick View.
"""

import logging
from datetime import datetime

from bokeh.layouts import column, row, gridplot
from bokeh.models import (
    Div, Button, Select, Toggle, DataTable, TableColumn, 
    ColumnDataSource, DateFormatter, PreText, HoverTool, RangeTool, TextInput
)
from bokeh.plotting import figure
from bokeh.palettes import Category20_20

logger = logging.getLogger('isolator.layouts')


def create_dashboard_layout(data_manager):
    """Create the complete dashboard layout."""
    
    # ── Header ──────────────────────────────────────────────────────────────
    header = Div(
        text="""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">🛡️ Network Isolator Quick View</h1>
            <p style="color: #f0f0f0; margin: 5px 0 0 0;">
                Real-time device monitoring and traffic analysis
            </p>
        </div>
        """,
        sizing_mode="stretch_width"
    )
    
    # ── System Status Panel ─────────────────────────────────────────────────
    system_status = create_system_status_panel(data_manager)
    
    # ── Device Cards Grid ───────────────────────────────────────────────────
    device_grid = create_device_grid(data_manager)
    
    # ── Live Traffic Graphs ─────────────────────────────────────────────────
    bandwidth_plot = create_bandwidth_plot()
    protocol_pie = create_protocol_distribution()
    
    traffic_row = row(bandwidth_plot, protocol_pie, sizing_mode="stretch_width")
    
    # ── Active Connections Table ────────────────────────────────────────────
    connections_table = create_connections_table()
    
    # ── Events & Alerts Log ─────────────────────────────────────────────────
    events_log = create_events_log()
    
    bottom_row = row(
        column(Div(text="<h3>Active Connections</h3>"), connections_table, width=700),
        column(Div(text="<h3>Events & Alerts</h3>"), events_log, width=500),
        sizing_mode="stretch_width"
    )
    
    # ── Configuration Sidebar ───────────────────────────────────────────────
    config_panel, config_widgets = create_config_panel(data_manager)
    
    # ── SSH Helper Panel ────────────────────────────────────────────────────
    ssh_panel = create_ssh_helper_panel()
    
    # ── Log Viewer Panel ────────────────────────────────────────────────────
    log_panel, log_widgets = create_log_viewer_panel()
    
    # ── BLE Viewer Panel ────────────────────────────────────────────────────
    ble_panel, ble_widgets = create_ble_viewer_panel()
    
    # ── Main Layout ─────────────────────────────────────────────────────────
    main_content = column(
        header,
        system_status,
        Div(text="<h2>Connected Devices</h2>"),
        device_grid,
        Div(text="<h2>Live Traffic</h2>"),
        traffic_row,
        bottom_row,
        log_panel,
        ble_panel,
        sizing_mode="stretch_width"
    )
    
    sidebar = column(
        config_panel,
        ssh_panel,
        width=350
    )
    
    layout = row(main_content, sidebar, sizing_mode="stretch_both")
    
    # Return layout and widget references for callbacks
    widgets = {
        'data_manager': data_manager,
        'device_grid': device_grid,
        'bandwidth_plot': bandwidth_plot,
        'connections_table': connections_table,
        'events_log': events_log,
        'system_status': system_status,
        **log_widgets,  # Include log viewer widgets
        **ble_widgets,  # Include BLE viewer widgets
        **config_widgets  # Include device_select, internet_toggle, etc.
    }
    
    return layout, widgets


def create_system_status_panel(data_manager):
    """System health indicators and network status."""
    # Get initial network status
    wifi_status = data_manager.get_wifi_ap_status()
    eth_status = data_manager.get_interface_status('eth0')
    wlan_status = data_manager.get_interface_status(wifi_status.get('interface', 'wlan0'))
    sys_stats = data_manager.get_system_stats()
    
    wifi_icon = '🟢' if wifi_status.get('running') else '🔴'
    eth_icon = '🟢' if eth_status.get('up') else '🔴'
    wlan_icon = '🟢' if wlan_status.get('up') else '🔴'
    
    status_html = f"""
    <div style="background: #2c3e50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
            
            <!-- WiFi AP Status -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div id="wifi-icon" style="font-size: 24px;">{wifi_icon}</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">WiFi AP</div>
                <div id="wifi-ssid" style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                    {wifi_status.get('ssid', 'Not configured')}
                </div>
                <div id="wifi-clients" style="font-size: 12px; color: #3498db; margin-top: 3px;">
                    {wifi_status.get('clients', 0)} clients
                </div>
            </div>
            
            <!-- Ethernet Status -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div id="eth-icon" style="font-size: 24px;">{eth_icon}</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Ethernet</div>
                <div id="eth-ip" style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                    {eth_status.get('ip', 'No IP')}
                </div>
                <div id="eth-traffic" style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                    ↓{eth_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{eth_status.get('tx_bytes', 0) // (1024*1024)}MB
                </div>
            </div>
            
            <!-- WLAN Interface -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div id="wlan-icon" style="font-size: 24px;">{wlan_icon}</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">wlan0</div>
                <div id="wlan-ip" style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                    {wlan_status.get('ip', 'No IP')}
                </div>
                <div id="wlan-traffic" style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                    ↓{wlan_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{wlan_status.get('tx_bytes', 0) // (1024*1024)}MB
                </div>
            </div>
            
            <!-- System Resources -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div style="font-size: 20px;">💾</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Storage</div>
                <div id="disk-free" style="font-size: 16px; color: #2ecc71; margin-top: 3px;">
                    {sys_stats.get('disk_free_gb', 0)}GB free
                </div>
                <div id="mem-usage" style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                    RAM: {sys_stats.get('mem_used_mb', 0)}/{sys_stats.get('mem_total_mb', 0)}MB
                </div>
            </div>
            
            <!-- Uptime -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div style="font-size: 20px;">⏱️</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Uptime</div>
                <div id="uptime" style="font-size: 16px; color: #f39c12; margin-top: 3px;">
                    {sys_stats.get('uptime_hours', 0)}h
                </div>
            </div>
            
            <!-- Active Captures -->
            <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                <div style="font-size: 20px;">🔴</div>
                <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Captures</div>
                <div id="capture-count" style="font-size: 16px; color: #e74c3c; margin-top: 3px;">
                    0 active
                </div>
            </div>
            
        </div>
    </div>
    """
    return Div(text=status_html, sizing_mode="stretch_width")


def create_device_grid(data_manager):
    """Grid of device status cards."""
    # Placeholder - will be populated by callbacks with live data
    device_cards_html = """
    <div id="device-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); 
                                   gap: 15px; margin-bottom: 20px;">
        <div style="border: 2px solid #3498db; border-radius: 8px; padding: 15px; background: #ecf0f1;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0;">📱 Loading...</h4>
                <span style="width: 12px; height: 12px; background: #95a5a6; border-radius: 50%;"></span>
            </div>
            <div style="font-size: 11px; color: #7f8c8d; margin-top: 8px;">
                Fetching connected devices...
            </div>
        </div>
    </div>
    """
    return Div(text=device_cards_html, sizing_mode="stretch_width")


def create_bandwidth_plot():
    """Real-time bandwidth graph."""
    p = figure(
        title="Bandwidth (last 30s)",
        x_axis_type="datetime",
        height=300,
        width=700,
        toolbar_location="above",
        tools="pan,box_zoom,reset,save"
    )
    
    p.title.text_font_size = "14pt"
    p.xaxis.axis_label = "Time"
    p.yaxis.axis_label = "KB/s"
    
    # Create empty data source (will be populated by callbacks)
    source = ColumnDataSource(data={
        'time': [],
        'total_download': [],
        'total_upload': []
    })
    
    p.line('time', 'total_download', source=source, line_width=2, 
           color='#3498db', legend_label="Download")
    p.line('time', 'total_upload', source=source, line_width=2, 
           color='#e74c3c', legend_label="Upload")
    
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"
    
    return p


def create_protocol_distribution():
    """Protocol breakdown pie chart (using vbar as placeholder)."""
    p = figure(
        title="Protocol Distribution",
        height=300,
        width=400,
        toolbar_location=None
    )
    
    source = ColumnDataSource(data={
        'protocols': ['HTTP', 'HTTPS', 'DNS', 'MQTT', 'Other'],
        'counts': [0, 0, 0, 0, 0],
        'colors': ['#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#95a5a6']
    })
    
    p.vbar(x='protocols', top='counts', source=source, width=0.8, 
           color='colors', alpha=0.8)
    
    p.xaxis.major_label_orientation = 0.8
    p.yaxis.axis_label = "Packet Count"
    
    return p


def create_connections_table():
    """Table showing active network connections."""
    source = ColumnDataSource(data={
        'device': [],
        'protocol': [],
        'remote_ip': [],
        'remote_port': [],
        'state': [],
        'duration': [],
        'packets': []
    })
    
    columns = [
        TableColumn(field='device', title='Device'),
        TableColumn(field='protocol', title='Proto'),
        TableColumn(field='remote_ip', title='Remote IP'),
        TableColumn(field='remote_port', title='Port'),
        TableColumn(field='state', title='State'),
        TableColumn(field='duration', title='Duration'),
        TableColumn(field='packets', title='Packets')
    ]
    
    table = DataTable(
        source=source,
        columns=columns,
        height=250,
        sizing_mode="stretch_width",
        index_position=None
    )
    
    return table


def create_events_log():
    """Live log of firewall events and alerts."""
    log_text = PreText(
        text="Waiting for events...\n",
        height=250,
        sizing_mode="stretch_width",
        styles={
            'background-color': '#2c3e50',
            'color': '#ecf0f1',
            'font-family': 'monospace',
            'font-size': '12px',
            'padding': '10px',
            'border-radius': '5px',
            'overflow-y': 'scroll'
        }
    )
    return log_text


def create_config_panel(data_manager):
    """Configuration sidebar for quick rule changes."""
    
    device_select = Select(
        title="Select Device:",
        value="",
        options=[],
        width=300
    )
    
    internet_toggle = Select(
        title="Internet Access:",
        value="allow",
        options=["allow", "deny", "log-only"],
        width=300
    )
    
    capture_toggle = Toggle(
        label="Enable Packet Capture",
        active=False,
        width=300
    )
    
    logging_select = Select(
        title="Logging Level:",
        value="metadata",
        options=["none", "metadata", "full"],
        width=300
    )
    
    apply_button = Button(
        label="Apply Changes",
        button_type="success",
        width=300
    )
    
    reload_button = Button(
        label="Reload Config",
        button_type="warning",
        width=300
    )
    
    panel = column(
        Div(text="<h3>⚙️ Configuration</h3>"),
        device_select,
        internet_toggle,
        capture_toggle,
        logging_select,
        apply_button,
        reload_button,
        Div(text="<hr>"),
        sizing_mode="stretch_width"
    )
    
    # Return both panel and widget references
    config_widgets = {
        'device_select': device_select,
        'internet_toggle': internet_toggle,
        'capture_toggle': capture_toggle,
        'logging_select': logging_select,
        'apply_button': apply_button,
        'reload_button': reload_button
    }
    
    return panel, config_widgets


def create_ssh_helper_panel():
    """SSH commands and quick access helpers for remote management."""
    
    ssh_commands = """
    <div style="background: #34495e; color: #ecf0f1; padding: 15px; border-radius: 5px;">
        <h3 style="margin-top: 0;">🔐 SSH Quick Access</h3>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>Connect to Pi:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        ssh pi@isolator.local
        </code>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>Access Dashboard via SSH tunnel:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        ssh -L 5006:localhost:5006 pi@isolator.local
        </code>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>Stream live Wireshark capture:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        ssh pi@isolator.local "cat /run/isolator/device.pipe" | wireshark -k -i -
        </code>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>Download capture files:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        scp -r pi@isolator.local:/mnt/isolator/captures/ ./captures/
        </code>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>View live logs:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        ssh pi@isolator.local "tail -f /var/log/isolator/traffic.log"
        </code>
        
        <p style="font-size: 12px; margin: 5px 0;"><strong>Reload firewall rules:</strong></p>
        <code style="background: #2c3e50; padding: 5px; display: block; border-radius: 3px; font-size: 11px; margin-bottom: 10px;">
        ssh pi@isolator.local "sudo systemctl reload isolator"
        </code>
        
        <hr style="border-color: #7f8c8d; margin: 15px 0;">
        
        <p style="font-size: 11px; color: #95a5a6; margin: 0;">
        💡 <strong>Tip:</strong> Use Windows Terminal or PowerShell with OpenSSH for best experience.
        Install OpenSSH: <code style="font-size: 10px;">winget install Microsoft.OpenSSH.Beta</code>
        </p>
    </div>
    """
    
    return Div(text=ssh_commands, sizing_mode="stretch_width")


def create_log_viewer_panel():
    """Interactive log viewer with timeline and device selection."""
    
    # Device selector for logs
    log_device_select = Select(
        title="Select Device to View Logs:",
        value="",
        options=[],
        width=300
    )
    
    # Action filter
    log_action_filter = Select(
        title="Filter by Action:",
        value="ALL",
        options=["ALL", "ALLOWED", "BLOCKED"],
        width=200
    )
    
    # Log data table
    log_source = ColumnDataSource(data={
        'timestamp': [],
        'time_str': [],
        'action': [],
        'protocol': [],
        'src_ip': [],
        'dst_ip': [],
        'dst_port': [],
        'bytes': []
    })
    
    log_columns = [
        TableColumn(field='time_str', title='Time', width=150),
        TableColumn(field='action', title='Action', width=80),
        TableColumn(field='protocol', title='Proto', width=60),
        TableColumn(field='src_ip', title='Source IP', width=130),
        TableColumn(field='dst_ip', title='Destination IP', width=130),
        TableColumn(field='dst_port', title='Port', width=60),
        TableColumn(field='bytes', title='Bytes', width=80)
    ]
    
    log_table = DataTable(
        source=log_source,
        columns=log_columns,
        width=900,
        height=400,
        sizing_mode="stretch_width"
    )
    
    # Timeline plot showing log activity
    timeline_source = ColumnDataSource(data={
        'timestamp': [],
        'value': [],
        'action': [],
        'color': []
    })
    
    timeline_plot = figure(
        title="Traffic Log Timeline (last 100 events)",
        x_axis_type='datetime',
        height=150,
        width=900,
        tools="pan,wheel_zoom,box_zoom,reset",
        active_drag="pan",
        active_scroll="wheel_zoom",
        sizing_mode="stretch_width"
    )
    
    timeline_plot.circle(
        'timestamp', 'value',
        source=timeline_source,
        size=8,
        color='color',
        alpha=0.7,
        legend_field='action'
    )
    
    timeline_plot.xaxis.axis_label = "Time"
    timeline_plot.yaxis.visible = False
    timeline_plot.legend.location = "top_right"
    timeline_plot.legend.click_policy = "hide"
    
    # Hover tool for timeline
    hover = HoverTool(
        tooltips=[
            ('Time', '@timestamp{%F %T}'),
            ('Action', '@action'),
        ],
        formatters={'@timestamp': 'datetime'}
    )
    timeline_plot.add_tools(hover)
    
    # Info div
    log_info = Div(
        text="<p style='color: #7f8c8d; font-size: 12px;'>Select a device from the dropdown to view its traffic logs. Logs show real-time packet-level activity.</p>",
        sizing_mode="stretch_width"
    )
    
    # Control row
    controls = row(
        log_device_select,
        log_action_filter,
        sizing_mode="stretch_width"
    )
    
    panel = column(
        Div(text="<h2>📊 Device Traffic Logs</h2>"),
        log_info,
        controls,
        timeline_plot,
        Div(text="<h3 style='margin-top: 20px;'>Log Entries</h3>"),
        log_table,
        sizing_mode="stretch_width"
    )
    
    # Return panel and widget references
    log_widgets = {
        'log_device_select': log_device_select,
        'log_action_filter': log_action_filter,
        'log_table': log_table,
        'log_source': log_source,
        'timeline_plot': timeline_plot,
        'timeline_source': timeline_source
    }
    
    return panel, log_widgets


def create_ble_viewer_panel():
    """Interactive BLE scanner and capture with 2-stage workflow: scan → select → capture."""
    
    # ═══════════════════════════════════════════════════════════════════
    # STAGE 1: DEVICE DISCOVERY (Active Scan)
    # ═══════════════════════════════════════════════════════════════════
    
    ble_scan_button = Button(
        label="🔍 Start Scan",
        button_type="primary",
        width=120
    )
    
    ble_scan_stop_button = Button(
        label="⏹️ Stop Scan",
        button_type="warning",
        width=120,
        disabled=True
    )
    
    ble_scan_status = Div(
        text="<p style='color: #7f8c8d;'>⚪ Not scanning - Click 'Start Scan' to discover devices</p>",
        width=400
    )
    
    # Discovered devices table
    ble_scan_source = ColumnDataSource(data={
        'mac': [],
        'name': [],
        'last_seen': [],
        'count': [],
        'selected': []
    })
    
    ble_scan_columns = [
        TableColumn(field='name', title='Device Name', width=200),
        TableColumn(field='mac', title='MAC Address', width=150),
        TableColumn(field='last_seen', title='Last Seen', width=150),
        TableColumn(field='count', title='Count', width=80)
    ]
    
    ble_scan_table = DataTable(
        source=ble_scan_source,
        columns=ble_scan_columns,
        width=900,
        height=250,
        sizing_mode="stretch_width",
        selectable='checkbox',
        index_position=None
    )
    
    ble_scan_info = Div(
        text="""<p style='color: #7f8c8d; font-size: 12px;'>
        <b>Step 1: Device Discovery</b><br>
        Click 'Start Scan' to perform active BLE scanning and discover nearby devices.
        Devices will appear in the table below as they're discovered.
        Select a device, then proceed to Step 2 to start targeted capture.
        </p>""",
        sizing_mode="stretch_width"
    )
    
    scan_controls = row(
        ble_scan_button,
        ble_scan_stop_button,
        ble_scan_status,
        sizing_mode="stretch_width"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # STAGE 2: TARGETED CAPTURE (Sniff selected device)
    # ═══════════════════════════════════════════════════════════════════
    
    ble_selected_device = Div(
        text="<p style='color: #7f8c8d;'>No device selected</p>",
        width=400
    )
    
    ble_capture_button = Button(
        label="🔴 Start Capture",
        button_type="success",
        width=130,
        disabled=True
    )
    
    ble_capture_stop_button = Button(
        label="🛑 Stop Capture",
        button_type="danger",
        width=130,
        disabled=True
    )
    
    ble_capture_status = Div(
        text="<p style='color: #7f8c8d;'>⚪ Not capturing - Select a device from scan results first</p>",
        width=500
    )
    
    ble_capture_info = Div(
        text="""<p style='color: #7f8c8d; font-size: 12px;'>
        <b>Step 2: Targeted Capture</b><br>
        After selecting a device above, click 'Start Capture' to begin sniffing that device's BLE traffic.
        Capture runs indefinitely until you click 'Stop Capture' - no timeout.
        All traffic (advertisements, connections, GATT operations) will be captured.
        </p>""",
        sizing_mode="stretch_width"
    )
    
    capture_device_row = row(
        Div(text="<b>Selected Device:</b>", width=120),
        ble_selected_device,
        sizing_mode="stretch_width"
    )
    
    capture_controls = row(
        ble_capture_button,
        ble_capture_stop_button,
        ble_capture_status,
        sizing_mode="stretch_width"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # STAGE 3: VIEW PAST CAPTURES
    # ═══════════════════════════════════════════════════════════════════
    
    ble_capture_select = Select(
        title="View Capture Session:",
        value="",
        options=[],
        width=400
    )
    
    ble_event_filter = Select(
        title="Filter by Event Type:",
        value="ALL",
        options=["ALL", "advertisement", "connection", "gatt_read", "gatt_write"],
        width=200
    )
    
    # BLE event data table
    ble_source = ColumnDataSource(data={
        'timestamp': [],
        'time_str': [],
        'type': [],
        'address': [],
        'name': [],
        'handle': [],
        'info': []
    })
    
    ble_columns = [
        TableColumn(field='time_str', title='Time', width=150),
        TableColumn(field='type', title='Event Type', width=120),
        TableColumn(field='address', title='Address', width=130),
        TableColumn(field='name', title='Device Name', width=150),
        TableColumn(field='handle', title='Handle', width=80),
        TableColumn(field='info', title='Additional Info', width=200)
    ]
    
    ble_table = DataTable(
        source=ble_source,
        columns=ble_columns,
        width=900,
        height=300,
        sizing_mode="stretch_width"
    )
    
    # Timeline plot for BLE events
    ble_timeline_source = ColumnDataSource(data={
        'timestamp': [],
        'value': [],
        'type': [],
        'color': []
    })
    
    ble_timeline_plot = figure(
        title="BLE Event Timeline",
        x_axis_type='datetime',
        height=120,
        width=900,
        tools="pan,wheel_zoom,box_zoom,reset",
        active_drag="pan",
        active_scroll="wheel_zoom",
        sizing_mode="stretch_width"
    )
    
    ble_timeline_plot.circle(
        'timestamp', 'value',
        source=ble_timeline_source,
        size=8,
        color='color',
        alpha=0.7,
        legend_field='type'
    )
    
    ble_timeline_plot.xaxis.axis_label = "Time"
    ble_timeline_plot.yaxis.visible = False
    ble_timeline_plot.legend.location = "top_right"
    ble_timeline_plot.legend.click_policy = "hide"
    
    # Hover tool for timeline
    hover = HoverTool(
        tooltips=[
            ('Time', '@timestamp{%F %T}'),
            ('Type', '@type'),
        ],
        formatters={'@timestamp': 'datetime'}
    )
    ble_timeline_plot.add_tools(hover)
    
    view_controls = row(
        ble_capture_select,
        ble_event_filter,
        sizing_mode="stretch_width"
    )
    
    ble_view_info = Div(
        text="""<p style='color: #7f8c8d; font-size: 12px;'>
        <b>Step 3: Analysis</b><br>
        Select a past capture session from the dropdown to view its events.
        Use the timeline and table to analyze BLE traffic patterns.
        </p>""",
        sizing_mode="stretch_width"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # ASSEMBLE PANEL
    # ═══════════════════════════════════════════════════════════════════
    
    panel = column(
        Div(text="<h2>📡 BLE Traffic Analyzer</h2>"),
        
        # Stage 1: Scan
        Div(text="<h3>Step 1: Device Discovery</h3>"),
        ble_scan_info,
        scan_controls,
        ble_scan_table,
        
        # Stage 2: Capture
        Div(text="<h3 style='margin-top: 30px;'>Step 2: Targeted Capture</h3>"),
        ble_capture_info,
        capture_device_row,
        capture_controls,
        
        # Stage 3: View
        Div(text="<h3 style='margin-top: 30px;'>Step 3: View Past Captures</h3>"),
        ble_view_info,
        view_controls,
        ble_timeline_plot,
        ble_table,
        
        sizing_mode="stretch_width"
    )
    
    # Return panel and widget references
    ble_widgets = {
        # Stage 1: Scan widgets
        'ble_scan_button': ble_scan_button,
        'ble_scan_stop_button': ble_scan_stop_button,
        'ble_scan_status': ble_scan_status,
        'ble_scan_table': ble_scan_table,
        'ble_scan_source': ble_scan_source,
        
        # Stage 2: Capture widgets
        'ble_selected_device': ble_selected_device,
        'ble_capture_button': ble_capture_button,
        'ble_capture_stop_button': ble_capture_stop_button,
        'ble_capture_status': ble_capture_status,
        
        # Stage 3: View widgets
        'ble_capture_select': ble_capture_select,
        'ble_event_filter': ble_event_filter,
        'ble_table': ble_table,
        'ble_source': ble_source,
        'ble_timeline_plot': ble_timeline_plot,
        'ble_timeline_source': ble_timeline_source
    }
    
    return panel, ble_widgets
