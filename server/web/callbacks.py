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
        """Update device log viewer with timeline and table (every 3 seconds)."""
        try:
            if not hasattr(doc, 'log_device_select'):
                return
            
            # Update device selector options if changed
            devices_df = data_manager.get_connected_devices()
            device_options = [""] + [f"{d['device_id']}" for _, d in devices_df.iterrows()]
            
            if doc.log_device_select.options != device_options:
                current_value = doc.log_device_select.value
                doc.log_device_select.options = device_options
                # Keep current selection if still valid
                if current_value and current_value not in device_options:
                    doc.log_device_select.value = device_options[0] if device_options else ""
            
            # Get selected device
            selected_device = doc.log_device_select.value
            if not selected_device:
                # No device selected, show info message
                doc.log_source.data = {
                    'timestamp': [0],
                    'time_str': ['Select a device above to view logs'],
                    'action': [''],
                    'protocol': [''],
                    'src_ip': [''],
                    'dst_ip': [''],
                    'dst_port': [''],
                    'bytes': ['']
                }
                doc.timeline_source.data = {
                    'timestamp': [],
                    'value': [],
                    'action': [],
                    'color': []
                }
                return
            
            # Get logs for selected device
            logs = data_manager.get_device_logs(selected_device, max_lines=100)
            
            # Get action filter
            action_filter = doc.log_action_filter.value if hasattr(doc, 'log_action_filter') else 'ALL'
            
            # Filter logs by action if needed
            if action_filter != 'ALL':
                logs = [log for log in logs if log.get('action') == action_filter]
            
            if not logs:
                doc.log_source.data = {
                    'timestamp': [0],
                    'time_str': [f'No {action_filter} logs found for {selected_device}'],
                    'action': [''],
                    'protocol': [''],
                    'src_ip': [''],
                    'dst_ip': [''],
                    'dst_port': [''],
                    'bytes': ['']
                }
                doc.timeline_source.data = {
                    'timestamp': [],
                    'value': [],
                    'action': [],
                    'color': []
                }
                return
            
            # Prepare table data
            timestamps = []
            time_strs = []
            actions = []
            protocols = []
            src_ips = []
            dst_ips = []
            dst_ports = []
            byte_counts = []
            
            for entry in logs:
                ts = entry.get('timestamp', '')
                try:
                    # Parse ISO timestamp
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    timestamps.append(dt)
                    time_strs.append(dt.strftime('%H:%M:%S.%f')[:-3])  # HH:MM:SS.mmm
                except Exception:
                    timestamps.append(datetime.now())
                    time_strs.append(ts)
                
                actions.append(entry.get('action', 'INFO'))
                protocols.append(entry.get('protocol', ''))
                src_ips.append(entry.get('src_ip', ''))
                dst_ips.append(entry.get('dst_ip', ''))
                
                dst_port = entry.get('dst_port')
                dst_ports.append(str(dst_port) if dst_port else '')
                
                byte_count = entry.get('bytes')
                byte_counts.append(str(byte_count) if byte_count else '')
            
            # Update table
            doc.log_source.data = {
                'timestamp': timestamps,
                'time_str': time_strs,
                'action': actions,
                'protocol': protocols,
                'src_ip': src_ips,
                'dst_ip': dst_ips,
                'dst_port': dst_ports,
                'bytes': byte_counts
            }
            
            # Update timeline (scatter plot)
            # Y-axis: 0 for BLOCKED, 1 for ALLOWED, 2 for others
            timeline_values = []
            timeline_colors = []
            
            for action in actions:
                if action == 'BLOCKED':
                    timeline_values.append(0)
                    timeline_colors.append('#e74c3c')  # Red
                elif action == 'ALLOWED':
                    timeline_values.append(1)
                    timeline_colors.append('#2ecc71')  # Green
                else:
                    timeline_values.append(2)
                    timeline_colors.append('#3498db')  # Blue
            
            doc.timeline_source.data = {
                'timestamp': timestamps,
                'value': timeline_values,
                'action': actions,
                'color': timeline_colors
            }
            
            logger.debug(f"Updated log viewer for {selected_device}: {len(logs)} entries")
        
        except Exception as e:
            logger.error(f"Error updating log viewer: {e}", exc_info=True)
    
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
    
    def update_ble_viewer():
        """Update BLE viewer with scan results, capture status, and past captures (every 3 seconds)."""
        try:
            # ═══════════════════════════════════════════════════════════════
            # STAGE 1: Update scan status and discovered devices
            # ═══════════════════════════════════════════════════════════════
            
            if not hasattr(doc, 'ble_scan_status'):
                return
            
            scan_status = data_manager.get_ble_scan_status()
            
            if scan_status['active']:
                device_count = scan_status['device_count']
                doc.ble_scan_status.text = f"<p style='color: #2ecc71;'>🟢 Scanning active - {device_count} devices found (PID {scan_status['pid']})</p>"
                doc.ble_scan_button.disabled = True
                doc.ble_scan_stop_button.disabled = False
                
                # Update discovered devices table
                devices = data_manager.get_ble_scan_devices()
                if devices:
                    # Format last_seen timestamps
                    for device in devices:
                        try:
                            dt = datetime.fromisoformat(device['last_seen'])
                            device['last_seen'] = dt.strftime('%H:%M:%S')
                        except:
                            pass
                    
                    doc.ble_scan_source.data = {
                        'mac': [d['mac'] for d in devices],
                        'name': [d['name'] for d in devices],
                        'last_seen': [d['last_seen'] for d in devices],
                        'count': [str(d['count']) for d in devices],
                        'selected': [False] * len(devices)
                    }
                else:
                    doc.ble_scan_source.data = {
                        'mac': [],
                        'name': [],
                        'last_seen': [],
                        'count': [],
                        'selected': []
                    }
            else:
                doc.ble_scan_status.text = "<p style='color: #7f8c8d;'>⚪ Not scanning - Click 'Start Scan' to discover devices</p>"
                doc.ble_scan_button.disabled = False
                doc.ble_scan_stop_button.disabled = True
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 2: Handle device selection and capture controls
            # ═══════════════════════════════════════════════════════════════
            
            # Check if user selected a device from scan table
            selected_indices = doc.ble_scan_source.selected.indices if hasattr(doc.ble_scan_source.selected, 'indices') else []
            
            if selected_indices and len(selected_indices) > 0:
                # Get selected device info
                idx = selected_indices[0]
                devices = data_manager.get_ble_scan_devices()
                if idx < len(devices):
                    selected_device = devices[idx]
                    doc.ble_selected_device.text = f"<p style='color: #2ecc71;'><b>{selected_device['name']}</b> ({selected_device['mac']})</p>"
                    doc.ble_capture_button.disabled = False
                else:
                    doc.ble_selected_device.text = "<p style='color: #7f8c8d;'>No device selected</p>"
                    doc.ble_capture_button.disabled = True
            else:
                doc.ble_selected_device.text = "<p style='color: #7f8c8d;'>No device selected</p>"
                doc.ble_capture_button.disabled = True
            
            # Update capture status
            capture_status = data_manager.get_ble_capture_status()
            if capture_status['active']:
                target = capture_status['target'] or 'Unknown'
                doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>🔴 Capturing {target} (PID {capture_status['pid']}) - Running until stopped</p>"
                doc.ble_capture_button.disabled = True
                doc.ble_capture_stop_button.disabled = False
            else:
                doc.ble_capture_status.text = "<p style='color: #7f8c8d;'>⚪ Not capturing - Select a device and click 'Start Capture'</p>"
                doc.ble_capture_stop_button.disabled = True
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 3: Update past captures list and viewer
            # ═══════════════════════════════════════════════════════════════
            
            # Update capture session list
            captures = data_manager.get_ble_captures()
            capture_options = [""] + [f"{c['filename']} ({c['event_count']} events)" for c in captures]
            
            if doc.ble_capture_select.options != capture_options:
                current_value = doc.ble_capture_select.value
                doc.ble_capture_select.options = capture_options
                # Keep current selection if still valid
                if current_value and current_value not in capture_options and capture_options:
                    doc.ble_capture_select.value = capture_options[0] if len(capture_options) > 1 else ""
            
            # Get selected capture for viewing
            selected_capture = doc.ble_capture_select.value
            if not selected_capture:
                # No capture selected, show info message
                doc.ble_source.data = {
                    'timestamp': [0],
                    'time_str': ['Select a capture session above to view events'],
                    'type': [''],
                    'address': [''],
                    'name': [''],
                    'handle': [''],
                    'info': ['']
                }
                doc.ble_timeline_source.data = {
                    'timestamp': [],
                    'value': [],
                    'type': [],
                    'color': []
                }
                return
            
            # Extract filename from selection (format: "filename.json (N events)")
            capture_file = selected_capture.split(' (')[0]
            
            # Get events for selected capture
            events = data_manager.get_ble_logs(capture_file, max_events=200)
            
            # Get event filter
            event_filter = doc.ble_event_filter.value if hasattr(doc, 'ble_event_filter') else 'ALL'
            
            # Filter events by type if needed
            if event_filter != 'ALL':
                events = [evt for evt in events if evt.get('type') == event_filter]
            
            if not events:
                doc.ble_source.data = {
                    'timestamp': [0],
                    'time_str': [f'No {event_filter} events found in {capture_file}'],
                    'type': [''],
                    'address': [''],
                    'name': [''],
                    'handle': [''],
                    'info': ['']
                }
                doc.ble_timeline_source.data = {
                    'timestamp': [],
                    'value': [],
                    'type': [],
                    'color': []
                }
                return
            
            # Prepare table data
            timestamps = []
            time_strs = []
            types = []
            addresses = []
            names = []
            handles = []
            infos = []
            
            for event in events:
                ts = event.get('timestamp', '')
                try:
                    # Parse ISO timestamp
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    timestamps.append(dt)
                    time_strs.append(dt.strftime('%H:%M:%S.%f')[:-3])  # HH:MM:SS.mmm
                except Exception:
                    timestamps.append(datetime.now())
                    time_strs.append(ts)
                
                event_type = event.get('type', 'unknown')
                types.append(event_type)
                
                data = event.get('data', {})
                addresses.append(data.get('address', ''))
                names.append(data.get('name', ''))
                handles.append(data.get('handle', ''))
                
                # Build info string from remaining data fields
                info_parts = []
                for key, value in data.items():
                    if key not in ['address', 'name', 'handle'] and value:
                        info_parts.append(f"{key}={value}")
                infos.append(', '.join(info_parts[:3]))  # Limit to first 3 fields
            
            # Update table
            doc.ble_source.data = {
                'timestamp': timestamps,
                'time_str': time_strs,
                'type': types,
                'address': addresses,
                'name': names,
                'handle': handles,
                'info': infos
            }
            
            # Update timeline (scatter plot)
            # Color by event type
            event_colors = {
                'advertisement': '#3498db',  # Blue
                'connection': '#2ecc71',     # Green
                'gatt_read': '#f39c12',      # Orange
                'gatt_write': '#e74c3c',     # Red
                'pairing': '#9b59b6',        # Purple
                'error': '#e74c3c',          # Red
                'info': '#95a5a6'            # Gray
            }
            
            timeline_values = list(range(len(types)))  # Use index as Y value for spread
            timeline_colors = [event_colors.get(evt_type, '#95a5a6') for evt_type in types]
            
            doc.ble_timeline_source.data = {
                'timestamp': timestamps,
                'value': timeline_values,
                'type': types,
                'color': timeline_colors
            }
            
            logger.debug(f"Updated BLE viewer: scan={scan_status['active']}, capture={capture_status['active']}, viewing={capture_file if selected_capture else 'none'}")
        
        except Exception as e:
            logger.error(f"Error updating BLE viewer: {e}", exc_info=True)
    
    # ── Register Periodic Callbacks ─────────────────────────────────────────
    
    doc.add_periodic_callback(update_devices, 2000)      # 2 seconds
    doc.add_periodic_callback(update_traffic, 1000)      # 1 second
    doc.add_periodic_callback(update_connections, 3000)  # 3 seconds
    # doc.add_periodic_callback(update_logs, 1000)         # 1 second (disabled - replaced by device logs)
    doc.add_periodic_callback(update_log_viewer, 3000)   # 3 seconds
    doc.add_periodic_callback(update_ble_viewer, 3000)   # 3 seconds
    doc.add_periodic_callback(update_system_status, 5000)  # 5 seconds
    
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
    
    def on_ble_scan_start():
        """Handle BLE Scan Start button click."""
        import sys
        print("===== PYTHON CALLBACK FIRED =====", file=sys.stderr, flush=True)
        logger.info("===== BLE Scan Start button clicked =====")
        try:
            # Start BLE device discovery scan
            logger.info("Starting BLE scan...")
            result = data_manager.start_ble_scan()
            
            if result['success']:
                doc.ble_scan_status.text = f"<p style='color: #2ecc71;'>🟢 Scanning started - discovering devices...</p>"
                doc.ble_scan_button.disabled = True
                doc.ble_scan_stop_button.disabled = False
                logger.info(f"BLE scan started: {result['message']}")
            else:
                doc.ble_scan_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {result['message']}</p>"
                logger.warning(f"BLE scan failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error starting BLE scan: {e}")
            doc.ble_scan_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {e}</p>"
    
    def on_ble_scan_stop():
        """Handle BLE Scan Stop button click."""
        try:
            result = data_manager.stop_ble_scan()
            
            if result['success']:
                doc.ble_scan_status.text = f"<p style='color: #7f8c8d;'>⚪ {result['message']}</p>"
                doc.ble_scan_button.disabled = False
                doc.ble_scan_stop_button.disabled = True
                logger.info("BLE scan stopped")
            else:
                doc.ble_scan_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {result['message']}</p>"
                logger.warning(f"BLE scan stop failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error stopping BLE scan: {e}")
            doc.ble_scan_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {e}</p>"
    
    def on_ble_capture_start():
        """Handle BLE Capture Start button click."""
        try:
            # Get selected device from scan table
            selected_indices = doc.ble_scan_source.selected.indices if hasattr(doc.ble_scan_source.selected, 'indices') else []
            
            if not selected_indices or len(selected_indices) == 0:
                doc.ble_capture_status.text = "<p style='color: #e74c3c;'>⚠️ Error: Please select a device from scan results first</p>"
                return
            
            # Get device info
            idx = selected_indices[0]
            devices = data_manager.get_ble_scan_devices()
            if idx >= len(devices):
                doc.ble_capture_status.text = "<p style='color: #e74c3c;'>⚠️ Error: Invalid device selection</p>"
                return
            
            selected_device = devices[idx]
            target_mac = selected_device['mac']
            target_name = selected_device['name']
            
            # Start capture (no duration = runs until stopped)
            result = data_manager.start_ble_capture(
                target_name=None,  # Use MAC for more reliable targeting
                target_mac=target_mac,
                duration=None  # Indefinite
            )
            
            if result['success']:
                doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>🔴 Capturing {target_name} - Running until stopped</p>"
                doc.ble_capture_button.disabled = True
                doc.ble_capture_stop_button.disabled = False
                logger.info(f"BLE capture started: {target_name} ({target_mac})")
            else:
                doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {result['message']}</p>"
                logger.warning(f"BLE capture failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error starting BLE capture: {e}")
            doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {e}</p>"
    
    def on_ble_capture_stop():
        """Handle BLE Capture Stop button click."""
        try:
            result = data_manager.stop_ble_capture()
            
            if result['success']:
                doc.ble_capture_status.text = f"<p style='color: #7f8c8d;'>⚪ {result['message']}</p>"
                doc.ble_capture_button.disabled = False
                doc.ble_capture_stop_button.disabled = True
                logger.info("BLE capture stopped")
            else:
                doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {result['message']}</p>"
                logger.warning(f"BLE capture stop failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error stopping BLE capture: {e}")
            doc.ble_capture_status.text = f"<p style='color: #e74c3c;'>⚠️ Error: {e}</p>"
    
    # TEST BUTTON - Simple callback to verify buttons work
    import datetime
    test_click_count = [0]  # Mutable to allow modification in closure
    
    def on_test_button_click():
        """Minimal test callback."""
        test_click_count[0] += 1
        import sys
        print(f"===== TEST BUTTON CLICKED {test_click_count[0]} =====", file=sys.stderr, flush=True)
        logger.info(f"===== TEST button clicked {test_click_count[0]} times =====")
        doc.ble_test_status.text = f"<p style='color: green;'>✓ Test button clicked {test_click_count[0]} times at {datetime.datetime.now().strftime('%H:%M:%S')}</p>"
    
    # Register button handlers
    logger.info("Registering BLE button handlers...")
    
    # Test button first
    if hasattr(doc, 'ble_test_button'):
        logger.info("  - Registering ble_test_button callback")
        doc.ble_test_button.on_click(on_test_button_click)
    else:
        logger.warning("  - ble_test_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_scan_button'):
        logger.info("  - Registering ble_scan_button callback")
        doc.ble_scan_button.on_click(on_ble_scan_start)
    else:
        logger.warning("  - ble_scan_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_scan_stop_button'):
        logger.info("  - Registering ble_scan_stop_button callback")
        doc.ble_scan_stop_button.on_click(on_ble_scan_stop)
    else:
        logger.warning("  - ble_scan_stop_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_capture_button'):
        logger.info("  - Registering ble_capture_button callback")
        doc.ble_capture_button.on_click(on_ble_capture_start)
    else:
        logger.warning("  - ble_capture_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_capture_stop_button'):
        logger.info("  - Registering ble_capture_stop_button callback")
        doc.ble_capture_stop_button.on_click(on_ble_capture_stop)
    else:
        logger.warning("  - ble_capture_stop_button NOT FOUND in doc")
    
    # TODO: Register other button callbacks (need widget references)
    # Currently other buttons are not interactive - data updates periodically
    
    logger.info("All callbacks registered successfully")
