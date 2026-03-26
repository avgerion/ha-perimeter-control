#!/usr/bin/env python3
"""
Callback handlers for the Network Isolator dashboard.
Manages periodic data updates and user interaction events.
"""

import logging
from datetime import datetime, timedelta
from functools import partial

from bokeh.models import ColumnDataSource

logger = logging.getLogger('isolator.callbacks')


def setup_callbacks(doc, data_manager):
    """
    Set up all periodic callbacks and event handlers.
    
    Args:
        doc: Bokeh document (widget references stored as doc attributes)
        data_manager: DataManager instance
    """
    
    # ── Periodic Update Callbacks ───────────────────────────────────────────
    
    def update_devices():
        """Update device grid and connection status (every 2 seconds)."""
        try:
            devices_df = data_manager.get_connected_devices()
            
            # Generate device cards HTML
            cards_html = '<div id="device-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; margin-bottom: 20px;">'
            
            for _, device in devices_df.iterrows():
                status_color = '#2ecc71' if device['connected'] else '#95a5a6'
                status_icon = '🟢' if device['connected'] else '⚪'
                
                internet_badge = {
                    'allow': '<span style="background:#2ecc71;color:white;padding:2px 6px;border-radius:3px;font-size:10px;">ALLOW</span>',
                    'deny': '<span style="background:#e74c3c;color:white;padding:2px 6px;border-radius:3px;font-size:10px;">DENY</span>',
                    'log-only': '<span style="background:#f39c12;color:white;padding:2px 6px;border-radius:3px;font-size:10px;">LOG</span>'
                }.get(device['internet'], '')
                
                capture_badge = '🔴 REC' if device['capture_enabled'] else ''
                
                card = f"""
                <div style="border: 2px solid {status_color}; border-radius: 8px; padding: 15px; background: #ecf0f1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0;">📱 {device['device_id']}</h4>
                        <span style="font-size: 20px;">{status_icon}</span>
                    </div>
                    <div style="font-size: 11px; color: #7f8c8d; margin-top: 5px;">
                        IP: {device['ip']}<br>
                        MAC: {device['mac']}<br>
                        Hostname: {device['hostname']}
                    </div>
                    <div style="margin-top: 8px; display: flex; justify-content: space-between; align-items: center;">
                        {internet_badge}
                        <span style="color: #e74c3c; font-weight: bold;">{capture_badge}</span>
                    </div>
                </div>
                """
                cards_html += card
            
            cards_html += '</div>'
            
            # Update device grid
            doc.device_grid.text = cards_html
            
            # Update config panel device dropdown dynamically
            if hasattr(doc, 'device_select'):
                current_options = [f"{d['device_id']} ({d['hostname']})" for _, d in devices_df.iterrows()]
                if doc.device_select.options != current_options:
                    current_value = doc.device_select.value
                    doc.device_select.options = current_options
                    # Keep current selection if still valid
                    if current_value not in current_options and current_options:
                        doc.device_select.value = current_options[0]
            
            logger.debug(f"Updated {len(devices_df)} devices")
        
        except Exception as e:
            logger.error(f"Error updating devices: {e}")
    
    def update_traffic():
        """Update bandwidth plots (every 1 second)."""
        try:
            stats_df = data_manager.get_traffic_stats(time_window_sec=30)
            
            if not stats_df.empty:
                # Aggregate by timestamp
                agg = stats_df.groupby('timestamp').agg({
                    'bytes_in': 'sum',
                    'bytes_out': 'sum'
                }).reset_index()
                
                # Convert to KB/s
                agg['download_kbps'] = agg['bytes_in'] / 1024
                agg['upload_kbps'] = agg['bytes_out'] / 1024
                
                # Update plot data source
                new_data = {
                    'time': agg['timestamp'].tolist(),
                    'total_download': agg['download_kbps'].tolist(),
                    'total_upload': agg['upload_kbps'].tolist()
                }
                
                doc.bandwidth_plot.renderers[0].data_source.data = new_data
                
                logger.debug(f"Updated traffic plot with {len(agg)} points")
        
        except Exception as e:
            logger.error(f"Error updating traffic: {e}")
    
    def update_connections():
        """Update active connections table (every 3 seconds)."""
        try:
            conn_df = data_manager.get_active_connections()
            
            if not conn_df.empty:
                # Format duration
                now = datetime.now()
                conn_df['duration_str'] = conn_df['start_time'].apply(
                    lambda t: str(now - t).split('.')[0] if isinstance(t, datetime) else '--'
                )
                
                new_data = {
                    'device': conn_df['device_id'].tolist(),
                    'protocol': conn_df['protocol'].tolist(),
                    'remote_ip': conn_df['remote_ip'].tolist(),
                    'remote_port': conn_df['remote_port'].astype(str).tolist(),
                    'state': conn_df['state'].tolist(),
                    'duration': conn_df['duration_str'].tolist(),
                    'packets': conn_df['packet_count'].astype(str).tolist()
                }
                
                doc.connections_table.source.data = new_data
                
                logger.debug(f"Updated {len(conn_df)} connections")
        
        except Exception as e:
            logger.error(f"Error updating connections: {e}")
    
    def update_logs():
        """Update events log (every 1 second)."""
        try:
            logs = data_manager.get_recent_logs(max_lines=30)
            
            # Format log entries
            log_lines = []
            for entry in logs:
                ts = entry.get('timestamp', '')
                if isinstance(ts, str) and 'T' in ts:
                    ts = ts.split('T')[1].split('.')[0]  # Extract HH:MM:SS
                
                level = entry.get('level', 'info')
                event_type = entry.get('event_type', '')
                message = entry.get('message', '')
                
                icon = {
                    'connection_blocked': '🔴',
                    'new_device': '🔵',
                    'capture_started': '🟢',
                    'capture_stopped': '⚪',
                    'config_reloaded': '🟡'
                }.get(event_type, 'ℹ️')
                
                log_lines.append(f"[{ts}] {icon} {message}")
            
            doc.events_log.text = '\n'.join(log_lines[-30:])  # Last 30 entries
        
        except Exception as e:
            logger.error(f"Error updating logs: {e}")
    
    def update_log_viewer():
        """Update log viewer panel (every 2 seconds)."""
        try:
            if hasattr(doc, 'log_viewer'):
                logs = data_manager.get_recent_logs(max_lines=100)
                
                # Format log entries for terminal-style display
                log_lines = []
                for entry in logs:
                    ts = entry.get('timestamp', '')
                    level = entry.get('level', 'info').upper()
                    device_id = entry.get('device_id', 'system')
                    message = entry.get('message', '')
                    
                    # Color codes based on level
                    level_color = {
                        'ERROR': '\x1b[31m',   # Red
                        'WARNING': '\x1b[33m',  # Yellow
                        'INFO': '\x1b[32m',     # Green
                    }.get(level, '')
                    reset = '\x1b[0m' if level_color else ''
                    
                    log_lines.append(f"{ts} [{level_color}{level:8s}{reset}] {device_id:20s} {message}")
                
                doc.log_viewer.text = '\n'.join(log_lines[-100:])
        
        except Exception as e:
            logger.error(f"Error updating log viewer: {e}")
    
    def update_system_status():
        """Update system status indicators (every 5 seconds)."""
        try:
            # Get all status information
            wifi_status = data_manager.get_wifi_ap_status()
            eth_status = data_manager.get_interface_status('eth0')
            wlan_status = data_manager.get_interface_status(wifi_status.get('interface', 'wlan0'))
            sys_stats = data_manager.get_system_stats()
            capture_status = data_manager.get_capture_status_all()
            
            active_captures = sum(1 for s in capture_status.values() if s['active'])
            
            wifi_icon = '🟢' if wifi_status.get('running') else '🔴'
            eth_icon = '🟢' if eth_status.get('up') else '🔴'
            wlan_icon = '🟢' if wlan_status.get('up') else '🔴'
            
            status_html = f"""
            <div style="background: #2c3e50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                    
                    <!-- WiFi AP Status -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{wifi_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">WiFi AP</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {wifi_status.get('ssid', 'Not configured')}
                        </div>
                        <div style="font-size: 12px; color: #3498db; margin-top: 3px;">
                            {wifi_status.get('clients', 0)} clients
                        </div>
                    </div>
                    
                    <!-- Ethernet Status -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{eth_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Ethernet</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {eth_status.get('ip', 'No IP')}
                        </div>
                        <div style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                            ↓{eth_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{eth_status.get('tx_bytes', 0) // (1024*1024)}MB
                        </div>
                    </div>
                    
                    <!-- WLAN Interface -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{wlan_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">wlan0</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {wlan_status.get('ip', 'No IP')}
                        </div>
                        <div style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                            ↓{wlan_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{wlan_status.get('tx_bytes', 0) // (1024*1024)}MB
                        </div>
                    </div>
                    
                    <!-- System Resources -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 20px;">💾</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Storage</div>
                        <div style="font-size: 16px; color: #2ecc71; margin-top: 3px;">
                            {sys_stats.get('disk_free_gb', 0)}GB free
                        </div>
                        <div style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                            RAM: {sys_stats.get('mem_used_mb', 0)}/{sys_stats.get('mem_total_mb', 0)}MB
                        </div>
                    </div>
                    
                    <!-- Uptime -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 20px;">⏱️</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Uptime</div>
                        <div style="font-size: 16px; color: #f39c12; margin-top: 3px;">
                            {sys_stats.get('uptime_hours', 0)}h
                        </div>
                    </div>
                    
                    <!-- Active Captures -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 20px;">🔴</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">Captures</div>
                        <div style="font-size: 16px; color: #e74c3c; margin-top: 3px;">
                            {active_captures} active
                        </div>
                    </div>
                    
                </div>
            </div>
            """
            
            doc.system_status.text = status_html
        
        except Exception as e:
            logger.error(f"Error updating system status: {e}")
    
    # ── Register Periodic Callbacks ─────────────────────────────────────────
    
    doc.add_periodic_callback(update_devices, 2000)      # 2 seconds
    doc.add_periodic_callback(update_traffic, 1000)      # 1 second
    doc.add_periodic_callback(update_connections, 3000)  # 3 seconds
    doc.add_periodic_callback(update_logs, 1000)         # 1 second    doc.add_periodic_callback(update_log_viewer, 2000)   # 2 seconds    doc.add_periodic_callback(update_system_status, 5000)  # 5 seconds
    
    # ── Button Click Handlers ───────────────────────────────────────────────
    
    def on_apply_changes():
        """Handle Apply Changes button click."""
        try:
            # Find config panel widgets
            for child in layout.children[1].children:
                if hasattr(child, 'device_select'):
                    device_id = child.device_select.value
                    internet = child.internet_toggle.value
                    capture_enabled = child.capture_toggle.active
                    logging_level = child.logging_select.value
                    
                    if device_id:
                        # Update rules
                        data_manager.update_device_rule(device_id, 'internet', internet)
                        data_manager.update_device_rule(device_id, 'logging', logging_level)
                        
                        # Update capture config
                        capture_config = {
                            'enabled': capture_enabled,
                            'filter': '',
                            'output': f'/mnt/isolator/captures/{device_id}',
                            'rotate_mb': 100,
                            'live': True
                        }
                        data_manager.update_device_rule(device_id, 'capture', capture_config)
                        
                        logger.info(f"Applied configuration changes for {device_id}")
                    
                    break
        
        except Exception as e:
            logger.error(f"Error applying changes: {e}")
    
    def on_reload_config():
        """Handle Reload Config button click."""
        try:
            data_manager.reload_config()
            logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
    
    # TODO: Register button callbacks (need widget references)
    # Currently buttons are not interactive - data updates periodically
    
    logger.info("All callbacks registered successfully")
