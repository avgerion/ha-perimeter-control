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
    ColumnDataSource, DateFormatter, PreText
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
    log_panel, log_viewer = create_log_viewer_panel()
    
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
        'log_viewer': log_viewer,
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
    """Live log viewer showing recent events and alerts."""
    
    log_viewer = PreText(
        text="Loading logs...",
        width=800,
        height=400,
        styles={
            'background-color': '#1e1e1e',
            'color': '#d4d4d4',
            'font-family': 'Consolas, Monaco, monospace',
            'font-size': '11px',
            'padding': '10px',
            'border-radius': '5px',
            'overflow': 'auto'
        }
    )
    
    panel = column(
        Div(text="<h2>📋 Live Logs</h2>"),
        log_viewer,
        sizing_mode="stretch_width"
    )
    
    return panel, log_viewer
