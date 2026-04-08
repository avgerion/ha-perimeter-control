#!/usr/bin/env python3
"""
Callback handlers for the PerimeterControl dashboard.
Manages periodic data updates and user interaction events.
"""

import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Dict, Optional

from bokeh.models import ColumnDataSource
from bokeh.events import ButtonClick


# ─── Configurable Constants ─────────────────────────────────────────────
import os


# Default log directory for BLE scan results (can be overridden by env/config)
BLE_SCAN_LOG_DIR = os.environ.get('PERIMETERCONTROL_BLE_SCAN_LOG_DIR', '/var/log/PerimeterControl/ble')
BLE_SCAN_LOG_PATTERN = os.path.join(BLE_SCAN_LOG_DIR, 'scan_*.json')

LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'PerimeterControl.callbacks')
logger = logging.getLogger(LOGGER_NAME)

# ─── BLE Advertisement decode helpers ────────────────────────────────────────

_COMPANY_IDS = {
    0x004C: "Apple",
    0x0006: "Microsoft",
    0x0171: "Amazon",
    0x0075: "Samsung Electronics",
    0x0059: "Nordic Semiconductor",
    0x0499: "Ruuvi Innovations",
    0x02E5: "Espressif Systems",
    0x0ABE: "Silicon Labs",
    0x00E0: "Google",
    0x0087: "Garmin",
    0x00D7: "Bose",
    0x0157: "FITBIT",
    0x04F7: "Tile",
    0x008C: "Texas Instruments",
}

_FLAGS_BITS = {
    0: "LE Limited Discoverable",
    1: "LE General Discoverable",
    2: "BR/EDR Not Supported",
    3: "LE+BR/EDR Controller",
    4: "LE+BR/EDR Host",
}


def _reconstruct_ad_bytes(adv: dict) -> bytes:
    """Reconstruct BLE AD payload bytes from bleak structured adv fields."""
    out = bytearray()

    local_name = adv.get('local_name')
    if local_name:
        name_b = local_name.encode('utf-8', errors='replace')
        out += bytes([len(name_b) + 1, 0x09]) + name_b

    tx_power = adv.get('tx_power')
    if tx_power is not None:
        out += bytes([2, 0x0A, tx_power & 0xFF])

    for uuid_str in (adv.get('service_uuids') or []):
        try:
            # 128-bit UUID
            raw = bytes.fromhex(uuid_str.replace('-', ''))
            if len(raw) == 16:
                out += bytes([len(raw) + 1, 0x07]) + raw[::-1]  # little-endian
        except Exception:
            pass

    for uuid_str, data_hex in (adv.get('service_data') or {}).items():
        data = bytes.fromhex(data_hex) if data_hex else b''
        try:
            u = uuid_str.replace('-', '')
            if len(u) == 4:
                uuid_b = bytes.fromhex(u)[::-1]
                ad_type = 0x16
            elif len(u) == 8:
                uuid_b = bytes.fromhex(u)[::-1]
                ad_type = 0x20
            else:
                uuid_b = bytes.fromhex(u)[::-1]
                ad_type = 0x21
            payload = uuid_b + data
            out += bytes([len(payload) + 1, ad_type]) + payload
        except Exception:
            pass

    for cid_str, data_hex in (adv.get('manufacturer_data') or {}).items():
        data = bytes.fromhex(data_hex) if data_hex else b''
        try:
            cid = int(cid_str)
            cid_b = bytes([cid & 0xFF, (cid >> 8) & 0xFF])
            payload = cid_b + data
            out += bytes([len(payload) + 1, 0xFF]) + payload
        except Exception:
            pass

    return bytes(out)


def _hexdump(b: bytes, width: int = 16) -> str:
    """Format bytes as annotated hex dump."""
    if not b:
        return '(empty)'
    lines = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hex_part = ' '.join(f'{x:02X}' for x in chunk)
        asc_part = ''.join(chr(x) if 32 <= x < 127 else '.' for x in chunk)
        lines.append(f'{i:04X}  {hex_part:<{width*3}}  {asc_part}')
    return '\n'.join(lines)


def _format_adv_detail_html(device: dict) -> str:
    """Return HTML showing raw AD bytes (reconstructed) and decoded LTV fields."""
    adv = device.get('adv_data', {})
    if not adv:
        return ("<p style='color:#7f8c8d;font-style:italic;'>"
                "No advertisement data — rescan after deploying the updated scanner</p>")

    raw_bytes = _reconstruct_ad_bytes(adv)
    hexdump   = _hexdump(raw_bytes)
    raw_hex   = ' '.join(f'{b:02X}' for b in raw_bytes) or '(none)'

    # Build decoded rows
    rows = []

    local_name = adv.get('local_name')
    if local_name:
        rows.append(('0x09', 'Complete Local Name', f'<b>{local_name}</b>'))

    tx_power = adv.get('tx_power')
    if tx_power is not None:
        rows.append(('0x0A', 'TX Power Level', f'{tx_power} dBm'))

    for uuid in (adv.get('service_uuids') or []):
        rows.append(('0x06/07', '128-bit Service UUID', f'<code>{uuid}</code>'))

    for uuid_str, data_hex in (adv.get('service_data') or {}).items():
        if not data_hex:
            continue
        spaced = ' '.join(data_hex[i:i+2].upper() for i in range(0, len(data_hex), 2))
        n_bytes = len(data_hex) // 2
        rows.append(('0x16/20/21', f'Service Data [{uuid_str}]',
                     f'<code>{spaced}</code>&nbsp;<span style="color:#888">({n_bytes}B)</span>'))

    for cid_str, data_hex in (adv.get('manufacturer_data') or {}).items():
        try:
            cid = int(cid_str)
            company = _COMPANY_IDS.get(cid, f'Unknown')
            spaced = ' '.join(data_hex[i:i+2].upper() for i in range(0, len(data_hex), 2)) if data_hex else ''
            n_bytes = len(data_hex) // 2 if data_hex else 0
            rows.append(('0xFF', f'Manufacturer Specific',
                         f'<span style="color:#4ec9b0;">Company 0x{cid:04X} ({company})</span>'
                         f'&nbsp;&nbsp;<code>{spaced}</code>'
                         f'&nbsp;<span style="color:#888">({n_bytes}B)</span>'))
        except Exception:
            rows.append(('0xFF', 'Manufacturer Specific', f'<code>{data_hex}</code>'))

    name = device.get('name', device.get('mac', '?'))
    mac  = device.get('mac', '')
    rssi = device.get('rssi', '')

    tr = ''.join(
        f"<tr style='border-bottom:1px solid #333;'>"
        f"<td style='padding:3px 10px;color:#ce9178;font-family:monospace;white-space:nowrap;'>{t}</td>"
        f"<td style='padding:3px 10px;color:#9cdcfe;white-space:nowrap;'>{n}</td>"
        f"<td style='padding:3px 10px;'>{v}</td></tr>"
        for t, n, v in rows
    )
    if not tr:
        tr = "<tr><td colspan='3' style='padding:4px 10px;color:#666;'>No decodable fields in this advertisement</td></tr>"

    return f"""
    <div style='background:#1e1e1e;color:#d4d4d4;padding:10px 14px;border-radius:4px;
                font-size:12px;border:1px solid #333;margin-top:6px;'>
      <span style='color:#9cdcfe;font-weight:bold;'>{name}</span>
      &nbsp;<span style='color:#888;'>{mac}</span>
      &nbsp;<span style='color:#4ec9b0;'>{rssi} dBm</span>
      <br><br>
      <span style='color:#888;'>Reconstructed AD payload ({len(raw_bytes)} bytes):</span><br>
      <pre style='color:#ce9178;margin:4px 0 10px 0;font-size:11px;line-height:1.4;'>{hexdump}</pre>
      <table style='border-collapse:collapse;width:100%;'>
        <tr style='border-bottom:1px solid #444;'>
          <th style='color:#4ec9b0;text-align:left;padding:3px 10px;'>AD Type</th>
          <th style='color:#4ec9b0;text-align:left;padding:3px 10px;'>Field</th>
          <th style='color:#4ec9b0;text-align:left;padding:3px 10px;'>Value</th>
        </tr>
        {tr}
      </table>
    </div>"""


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
            if not hasattr(doc.bandwidth_plot, 'renderers') or len(doc.bandwidth_plot.renderers) == 0:
                return

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
                
                # Keep X values as numeric ms for predictable client-side ranges
                times_ms = []
                for ts in agg['timestamp'].tolist():
                    if hasattr(ts, 'timestamp'):
                        times_ms.append(ts.timestamp() * 1000)
                    else:
                        times_ms.append(float(ts))
                
                # Update plot data source
                new_data = {
                    'time': times_ms,
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
            if not hasattr(doc.connections_table, 'source'):
                return

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
                now_ms = datetime.now().timestamp() * 1000
                doc.timeline_source.data = {
                    'timestamp': [now_ms - 5000, now_ms],
                    'value': [0, 1],
                    'action': ['', ''],
                    'color': ['#888888', '#888888']
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
                now_ms = datetime.now().timestamp() * 1000
                doc.timeline_source.data = {
                    'timestamp': [now_ms - 5000, now_ms],
                    'value': [0, 1],
                    'action': ['', ''],
                    'color': ['#888888', '#888888']
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
            topology = data_manager.get_network_topology()
            wifi_status = data_manager.get_wifi_ap_status()
            upstream_status = data_manager.get_interface_status(topology['upstream']['interface'])
            isolated_status = data_manager.get_interface_status(topology['isolated']['interface'])
            sys_stats = data_manager.get_system_stats()
            capture_status = data_manager.get_capture_status_all()
            
            active_captures = sum(1 for s in capture_status.values() if s['active'])
            
            wifi_icon = '🟢' if wifi_status.get('running') else '🔴'
            upstream_icon = '🟢' if upstream_status.get('up') else '🔴'
            isolated_icon = '🟢' if isolated_status.get('up') else '🔴'
            
            status_html = f"""
            <div style="background: #2c3e50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                    
                    <!-- Access Side Status -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{wifi_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{'WiFi AP' if wifi_status.get('enabled') else 'Access Side'}</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {wifi_status.get('ssid') if wifi_status.get('enabled') else topology['isolated']['interface']}
                        </div>
                        <div style="font-size: 12px; color: #3498db; margin-top: 3px;">
                            {f"{wifi_status.get('clients', 0)} clients" if wifi_status.get('enabled') else topology['isolated']['kind']}
                        </div>
                    </div>
                    
                    <!-- Upstream Status -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{upstream_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{topology['upstream']['label']}</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {topology['upstream']['interface']} · {upstream_status.get('ip', 'No IP')}
                        </div>
                        <div style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                            ↓{upstream_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{upstream_status.get('tx_bytes', 0) // (1024*1024)}MB
                        </div>
                    </div>
                    
                    <!-- Isolated Interface -->
                    <div style="text-align: center; padding: 10px; background: #34495e; border-radius: 5px;">
                        <div style="font-size: 24px;">{isolated_icon}</div>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{topology['isolated']['label']}</div>
                        <div style="font-size: 11px; color: #bdc3c7; margin-top: 3px;">
                            {topology['isolated']['interface']} · {isolated_status.get('ip', 'No IP')}
                        </div>
                        <div style="font-size: 10px; color: #95a5a6; margin-top: 3px;">
                            ↓{isolated_status.get('rx_bytes', 0) // (1024*1024)}MB ↑{isolated_status.get('tx_bytes', 0) // (1024*1024)}MB
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
    
    def _get_selected_ble_scan_device() -> Optional[Dict[str, Any]]:
        """Return selected device from the table source, independent of scanner process state."""
        try:
            selected_indices = doc.ble_scan_source.selected.indices if hasattr(doc.ble_scan_source.selected, 'indices') else []
            if not selected_indices:
                return None

            idx = selected_indices[0]
            data = doc.ble_scan_source.data or {}
            macs = data.get('mac', [])
            names = data.get('name', [])
            if idx < 0 or idx >= len(macs):
                return None

            return {
                'mac': macs[idx],
                'name': names[idx] if idx < len(names) else macs[idx],
                'last_seen': (data.get('last_seen') or [None] * len(macs))[idx] if idx < len((data.get('last_seen') or [])) else None,
                'count': (data.get('count') or [None] * len(macs))[idx] if idx < len((data.get('count') or [])) else None,
                'rssi': (data.get('rssi') or [None] * len(macs))[idx] if idx < len((data.get('rssi') or [])) else None,
                'tx_power': (data.get('tx_power') or [None] * len(macs))[idx] if idx < len((data.get('tx_power') or [])) else None,
                'phy': (data.get('phy') or [None] * len(macs))[idx] if idx < len((data.get('phy') or [])) else None,
            }
        except Exception:
            return None

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
                        'mac':      [d['mac'] for d in devices],
                        'name':     [d['name'] for d in devices],
                        'last_seen':[d['last_seen'] for d in devices],
                        'count':    [str(d['count']) for d in devices],
                        'rssi':     [d.get('rssi') or 0 for d in devices],
                        'tx_power': [d.get('tx_power') for d in devices],
                        'phy':      [d.get('phy', 'LE 1M') for d in devices],
                        'selected': [False] * len(devices)
                    }
                    doc.ble_rssi_plot.y_range.factors = [d['name'] for d in devices]
                else:
                    doc.ble_scan_source.data = {
                        'mac': [], 'name': [], 'last_seen': [], 'count': [],
                        'rssi': [], 'tx_power': [], 'phy': [], 'selected': []
                    }
                    doc.ble_rssi_plot.y_range.factors = []
            else:
                doc.ble_scan_status.text = "<p style='color: #7f8c8d;'>⚪ Not scanning - Click 'Start Scan' to discover devices</p>"
                doc.ble_scan_button.disabled = False
                doc.ble_scan_stop_button.disabled = True
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 2: Handle device selection and capture controls
            # ═══════════════════════════════════════════════════════════════
            
            selected_device = _get_selected_ble_scan_device()

            if selected_device:
                doc.ble_selected_device.text = f"<p style='color: #2ecc71;'><b>{selected_device['name']}</b> ({selected_device['mac']})</p>"
                doc.ble_capture_button.disabled = False
                if hasattr(doc, 'ble_adv_detail'):
                    doc.ble_adv_detail.text = _format_adv_detail_html(selected_device)
                if hasattr(doc, 'ble_profiler_button'):
                    profiler_status = data_manager.get_ble_profiler_status()
                    doc.ble_profiler_button.disabled = profiler_status['active']
            else:
                doc.ble_selected_device.text = "<p style='color: #7f8c8d;'>No device selected</p>"
                doc.ble_capture_button.disabled = True
                if hasattr(doc, 'ble_adv_detail'):
                    doc.ble_adv_detail.text = "<p style='color:#7f8c8d;font-style:italic;'>&#x2191; Select a device above to view its advertisement data</p>"
                if hasattr(doc, 'ble_profiler_button'):
                    doc.ble_profiler_button.disabled = True
            
            # Update capture status
            capture_status = data_manager.get_ble_capture_status()
            if capture_status['active']:
                target = capture_status['target'] or 'Unknown'
                log_tail = capture_status.get('log_tail', [])
                tail_html = ''
                if log_tail:
                    # Show last 3 lines of sniffer log as a debug hint
                    tail_lines = '<br>'.join(
                        f"<code style='font-size:10px;'>{l[-120:]}</code>"
                        for l in log_tail[-3:]
                    )
                    tail_html = f"<div style='margin-top:4px;color:#aaa;'>{tail_lines}</div>"
                doc.ble_capture_status.text = (
                    f"<p style='color: #e74c3c;'>🔴 Capturing {target} "
                    f"(PID {capture_status['pid']}) — running until stopped</p>"
                    f"{tail_html}"
                )
                doc.ble_capture_button.disabled = True
                doc.ble_capture_stop_button.disabled = False
            else:
                doc.ble_capture_status.text = "<p style='color: #7f8c8d;'>⚪ Not capturing — select a device and click 'Start Capture'</p>"
                doc.ble_capture_stop_button.disabled = True
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 3: Update past captures list and viewer
            # ═══════════════════════════════════════════════════════════════
            
            # Update capture session list
            captures = data_manager.get_ble_captures()
            # Keep option values stable (filename) while labels can change
            # as event_count grows during active capture.
            capture_options = [("", "Select capture session...")] + [
                (c['filename'], f"{c['filename']} ({c['event_count']} events)")
                for c in captures
            ]
            
            if doc.ble_capture_select.options != capture_options:
                current_value = doc.ble_capture_select.value
                doc.ble_capture_select.options = capture_options
                # Keep current selection if still valid
                valid_values = {value for value, _label in capture_options}
                if current_value and current_value not in valid_values:
                    doc.ble_capture_select.value = ""
            
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
                    'raw_bytes': [''],
                    'info': ['']
                }
                doc.ble_timeline_source.data = {
                    'timestamp': [0],
                    'value': [0],
                    'type': [''],
                    'color': ['#888888']
                }
                return
            
            # Value is the stable capture filename.
            capture_file = selected_capture
            
            # Get events for selected capture
            events = data_manager.get_ble_logs(capture_file, max_events=200)
            
            # Get event filter
            event_filter = doc.ble_event_filter.value if hasattr(doc, 'ble_event_filter') else 'ALL'
            
            # Filter events by type if needed
            if event_filter != 'ALL':
                events = [evt for evt in events if evt.get('type') == event_filter]
            
            if not events:
                # Show a diagnostic hint from the sniffer log
                log_tail = data_manager.get_ble_sniffer_log_tail(n=5)
                BLE_SNIFFER_LOG_PATH = os.environ.get('PERIMETERCONTROL_BLE_SNIFFER_LOG_PATH', '/var/log/perimetercontrol/ble/*.raw.log')
                hint = ' | '.join(log_tail[-3:]) if log_tail else f'No log output yet — check {BLE_SNIFFER_LOG_PATH} on the Pi'
                doc.ble_source.data = {
                    'timestamp': [0],
                    'time_str': [
                        f'No {event_filter} events in {capture_file}  '
                        f'(raw lines in sniffer log: run ble-debug.sh on Pi)'
                    ],
                    'type': [''],
                    'address': [''],
                    'name': [''],
                    'handle': [''],
                    'raw_bytes': [''],
                    'info': [hint[:200]]
                }
                now_ms = datetime.now().timestamp() * 1000
                doc.ble_timeline_source.data = {
                    'timestamp': [now_ms - 5000, now_ms],
                    'value': [0, 1],
                    'type': ['', ''],
                    'color': ['#888888', '#888888']
                }
                return
            
            # Prepare table data
            timestamps = []
            time_strs = []
            types = []
            addresses = []
            names = []
            handles = []
            raw_bytes_col = []
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

                # Payload column: prefer explicit Value bytes, then fall back
                # to the decoded btmon lines for the event (raw_lines).
                payload = ''
                gatt_value = data.get('value', '')
                if gatt_value:
                    payload = gatt_value  # already space-separated hex from btmon
                else:
                    raw_lines = data.get('raw_lines', [])
                    if raw_lines:
                        # Join decoded lines, strip common leading whitespace, cap length
                        joined = ' | '.join(l.strip() for l in raw_lines if l.strip())
                        payload = joined[:200] + ('…' if len(joined) > 200 else '')
                raw_bytes_col.append(payload)

                # Build info string from non-bytes fields
                info_parts = []
                skip_in_info = {'address', 'name', 'handle', 'packet_bytes_hex', 'raw_lines', 'summary'}
                preferred_keys = ['status', 'reason', 'error', 'opcode', 'value']
                for key in preferred_keys:
                    value = data.get(key)
                    if value:
                        info_parts.append(f"{key}={value}")

                if len(info_parts) < 4:
                    for key, value in data.items():
                        if key in skip_in_info or not value:
                            continue
                        if key not in preferred_keys:
                            info_parts.append(f"{key}={value}")
                        if len(info_parts) >= 4:
                            break

                infos.append(', '.join(info_parts[:4]))
            
            # Update table
            doc.ble_source.data = {
                'timestamp': timestamps,
                'time_str': time_strs,
                'type': types,
                'address': addresses,
                'name': names,
                'handle': handles,
                'raw_bytes': raw_bytes_col,
                'info': infos
            }
            
            # Update timeline (scatter plot)
            # Color by event type
            event_colors = {
                'advertisement': '#3498db',  # Blue
                'connection': '#2ecc71',     # Green
                'disconnection': '#7f8c8d',  # Gray
                'gatt_read': '#f39c12',      # Orange
                'gatt_read_by_type': '#d35400',  # Dark orange
                'gatt_write': '#e74c3c',     # Red
                'gatt_notify': '#1abc9c',    # Teal
                'hci_event': '#8e44ad',      # Violet
                'hci_command': '#5e35b1',    # Indigo
                'mgmt_event': '#34495e',     # Dark blue-gray
                'mgmt_command': '#2c3e50',   # Midnight blue
                'att_error': '#c0392b',      # Dark red
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

            # Profiler status update
            if hasattr(doc, 'ble_profiler_status') and hasattr(doc, 'ble_profiler_button'):
                prof_st = data_manager.get_ble_profiler_status()
                if prof_st['active']:
                    target = prof_st.get('target') or ''
                    doc.ble_profiler_status.text = (
                        f"<p style='color:#f39c12;'>&#x23F3; Profiling {target} "
                        f"(PID {prof_st['pid']}) &mdash; please wait&hellip;</p>"
                    )
                    doc.ble_profiler_stop_button.disabled = False
                    doc.ble_profiler_button.disabled = True
                else:
                    # Only reset to 'not profiling' if status still says running
                    if 'Profiling' in doc.ble_profiler_status.text and '23F3' in doc.ble_profiler_status.text:
                        doc.ble_profiler_status.text = "<p style='color:#2ecc71;'>&#x2705; Profiling complete &mdash; profile saved. Reload the proxy profile list.</p>"
                    doc.ble_profiler_stop_button.disabled = True

            # ═══════════════════════════════════════════════════════════════
            # STAGE 4: Proxy status and profile list
            # ═══════════════════════════════════════════════════════════════

            if not hasattr(doc, 'ble_proxy_profile_select'):
                return

            # Refresh profile dropdown
            profiles = data_manager.get_ble_profiles()
            proxy_options = [("", "— select profile —")] + [
                (p['path'], f"{p['name']}  ({p['mac']})  [{p['svc_count']} svcs]")
                for p in profiles
            ]
            if doc.ble_proxy_profile_select.options != proxy_options:
                current = doc.ble_proxy_profile_select.value
                doc.ble_proxy_profile_select.options = proxy_options
                valid = {v for v, _ in proxy_options}
                if current and current not in valid:
                    doc.ble_proxy_profile_select.value = ""

            selected_profile = doc.ble_proxy_profile_select.value
            proxy_status = data_manager.get_ble_proxy_status()

            if proxy_status['active']:
                doc.ble_proxy_status.text = (
                    f"<p style='color:#2ecc71;'>🟢 Proxy running "
                    f"(PID {proxy_status['pid']})</p>"
                )
                doc.ble_proxy_start_button.disabled = True
                doc.ble_proxy_stop_button.disabled = False
            else:
                doc.ble_proxy_status.text = "<p style='color:#7f8c8d;'>⚪ Proxy not running</p>"
                doc.ble_proxy_start_button.disabled = not bool(selected_profile)
                doc.ble_proxy_stop_button.disabled = True

            # Live ops log tail
            ops_lines = data_manager.get_proxy_ops_tail(n=20)
            doc.ble_proxy_ops_log.text = '\n'.join(ops_lines) if ops_lines else '(no ops logged yet)'

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
    
    def refresh_active_config_view():
        """Refresh the read-only runtime config text panel."""
        try:
            if not hasattr(doc, 'active_config_text'):
                return

            result = data_manager.get_active_config_text()
            if result.get('success'):
                doc.active_config_text.text = result.get('text', '')
                if hasattr(doc, 'active_config_meta'):
                    suffix = ' (truncated)' if result.get('truncated') else ''
                    doc.active_config_meta.text = (
                        f"<p style='color:#7f8c8d;font-size:12px;'>"
                        f"{result.get('path')} · {result.get('size_bytes', 0)} bytes · "
                        f"updated {result.get('mtime', 'unknown')}{suffix}</p>"
                    )
            else:
                doc.active_config_text.text = result.get('error', 'Failed to load config')
                if hasattr(doc, 'active_config_meta'):
                    doc.active_config_meta.text = (
                        "<p style='color:#e74c3c;font-size:12px;'>"
                        f"Unable to read active config: {result.get('path', 'unknown path')}</p>"
                    )
        except Exception as e:
            logger.error(f"Error refreshing active config view: {e}")

    def on_apply_changes():
        """Handle Apply Changes button click."""
        try:
            if not all(hasattr(doc, attr) for attr in ['device_select', 'internet_toggle', 'capture_toggle', 'logging_select']):
                logger.warning("Config widgets not available on document; skipping apply")
                return

            selected_device = doc.device_select.value
            device_id = selected_device.split(' ', 1)[0] if selected_device else ''
            internet = doc.internet_toggle.value
            capture_enabled = doc.capture_toggle.active
            logging_level = doc.logging_select.value

            if device_id:
                # Update rules
                data_manager.update_device_rule(device_id, 'internet', internet)
                data_manager.update_device_rule(device_id, 'logging', logging_level)

                # Update capture config
                capture_config = {
                    'enabled': capture_enabled,
                    'filter': '',
                    CAPTURE_OUTPUT_PATH = os.environ.get('PERIMETERCONTROL_CAPTURE_OUTPUT_PATH', '/mnt/perimetercontrol/captures')
                    'output': f'{CAPTURE_OUTPUT_PATH}/{device_id}',
                    'rotate_mb': 100,
                    'live': True
                }
                data_manager.update_device_rule(device_id, 'capture', capture_config)

                refresh_active_config_view()
                logger.info(f"Applied configuration changes for {device_id}")

        except Exception as e:
            logger.error(f"Error applying changes: {e}")

    def on_reload_config():
        """Handle Reload Config button click."""
        try:
            data_manager.reload_config()
            refresh_active_config_view()
            logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")

    def on_refresh_active_config(event=None):
        """Handle manual refresh for the runtime config panel."""
        refresh_active_config_view()

    def on_ble_profiler_start(event=None):
        """Start the GATT profiler for the currently selected scan device."""
        try:
            device = _get_selected_ble_scan_device()
            if not device:
                if hasattr(doc, 'ble_profiler_status'):
                    doc.ble_profiler_status.text = "<p style='color:#e74c3c;'>&#x26A0; Select a device from Step 1 first</p>"
                return
            mac  = device.get('mac', '')
            name = device.get('name', '')
            if hasattr(doc, 'ble_profiler_status'):
                doc.ble_profiler_status.text = f"<p style='color:#f39c12;'>&#x23F3; Profiling {name} ({mac})&hellip;</p>"
            doc.ble_profiler_button.disabled = True
            result = data_manager.start_ble_profiler(target_mac=mac)
            if result['success']:
                doc.ble_profiler_status.text = f"<p style='color:#2ecc71;'>&#x1F7E2; {result['message']} (PID {result.get('pid','')})</p>"
                doc.ble_profiler_stop_button.disabled = False
            else:
                doc.ble_profiler_status.text = f"<p style='color:#e74c3c;'>&#x274C; {result['message']}</p>"
                doc.ble_profiler_button.disabled = False
        except Exception as e:
            logger.error(f'on_ble_profiler_start: {e}')

    def on_ble_profiler_stop(event=None):
        """Stop the running GATT profiler."""
        try:
            result = data_manager.stop_ble_profiler()
            if hasattr(doc, 'ble_profiler_status'):
                if result['success']:
                    doc.ble_profiler_status.text = "<p style='color:#7f8c8d;'>&#x26AA; Profiler stopped</p>"
                else:
                    doc.ble_profiler_status.text = f"<p style='color:#e74c3c;'>&#x274C; {result['message']}</p>"
            doc.ble_profiler_stop_button.disabled = True
            doc.ble_profiler_button.disabled = False
        except Exception as e:
            logger.error(f'on_ble_profiler_stop: {e}')

    def on_ble_proxy_start(event=None):
        """Start the BLE GATT mirror server for the selected profile."""
        try:
            if not hasattr(doc, 'ble_proxy_profile_select'):
                return
            profile_path = doc.ble_proxy_profile_select.value
            if not profile_path:
                doc.ble_proxy_status.text = "<p style='color:#e74c3c;'>⚠ Select a profile first</p>"
                return
            doc.ble_proxy_status.text = "<p style='color:#f39c12;'>⏳ Starting proxy...</p>"
            doc.ble_proxy_start_button.disabled = True
            result = data_manager.start_ble_proxy(profile_path)
            if result['success']:
                doc.ble_proxy_status.text = f"<p style='color:#2ecc71;'>🟢 {result['message']}</p>"
                doc.ble_proxy_stop_button.disabled = False
            else:
                doc.ble_proxy_status.text = f"<p style='color:#e74c3c;'>❌ {result['message']}</p>"
                doc.ble_proxy_start_button.disabled = False
        except Exception as e:
            logger.error(f"on_ble_proxy_start: {e}")
            if hasattr(doc, 'ble_proxy_status'):
                doc.ble_proxy_status.text = f"<p style='color:#e74c3c;'>Error: {e}</p>"

    def on_ble_proxy_stop(event=None):
        """Stop the running BLE GATT mirror server."""
        try:
            if not hasattr(doc, 'ble_proxy_status'):
                return
            doc.ble_proxy_status.text = "<p style='color:#f39c12;'>⏳ Stopping proxy...</p>"
            result = data_manager.stop_ble_proxy()
            if result['success']:
                doc.ble_proxy_status.text = "<p style='color:#7f8c8d;'>⚪ Proxy stopped</p>"
            else:
                doc.ble_proxy_status.text = f"<p style='color:#e74c3c;'>❌ {result['message']}</p>"
            doc.ble_proxy_start_button.disabled = False
            doc.ble_proxy_stop_button.disabled = True
        except Exception as e:
            logger.error(f"on_ble_proxy_stop: {e}")

    def on_ble_scan_start(event=None):
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
    
    def on_ble_scan_stop(event=None):
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
    
    def on_ble_capture_start(event=None):
        """Handle BLE Capture Start button click."""
        try:
            # Get selected device from scan table
            selected_device = _get_selected_ble_scan_device()
            if not selected_device:
                doc.ble_capture_status.text = "<p style='color: #e74c3c;'>⚠️ Error: Please select a device from scan results first</p>"
                return

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
    
    def on_ble_capture_stop(event=None):
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
    
    def on_ble_scan_clear(event=None):
        """Clear displayed scan results without stopping an active scan."""
        empty = {
            'mac': [], 'name': [], 'last_seen': [], 'count': [],
            'rssi': [], 'tx_power': [], 'phy': [], 'selected': []
        }
        doc.ble_scan_source.data = empty
        doc.ble_rssi_plot.y_range.factors = []
        # Also delete all existing scan JSON files so get_ble_scan_devices
        # doesn't reload stale results on the next poll tick.
        try:
            import glob as _glob
            for f in _glob.glob(BLE_SCAN_LOG_PATTERN):
                import os as _os
                _os.remove(f)
        except Exception as _e:
            logger.warning(f"Clear scan: could not remove scan files: {_e}")
        doc.ble_scan_status.text = "<p style='color: #7f8c8d;'>🗑️ Scan results cleared</p>"
        logger.info("BLE scan results cleared")
    
    # Register button handlers
    session_id = None
    if getattr(doc, 'session_context', None) is not None:
        session_id = doc.session_context.id

    logger.info(f"Registering dashboard button handlers for session={session_id}")

    # Prime active config view on session start.
    refresh_active_config_view()

    if hasattr(doc, 'apply_button'):
        doc.apply_button.on_click(on_apply_changes)
    if hasattr(doc, 'reload_button'):
        doc.reload_button.on_click(on_reload_config)
    if hasattr(doc, 'refresh_active_config_button'):
        doc.refresh_active_config_button.on_click(on_refresh_active_config)

    event_logger_refs = []

    # Clear Scan button (repurposed from TEST)
    if hasattr(doc, 'ble_test_button'):
        logger.info(f"  - Registering ble_test_button (Clear Scan) callback model_id={doc.ble_test_button.id}")
        doc.ble_test_button.on_click(on_ble_scan_clear)
        doc.ble_test_button._update_event_callbacks()
    else:
        logger.warning("  - ble_test_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_scan_button'):
        logger.info(f"  - Registering ble_scan_button callback model_id={doc.ble_scan_button.id}")
        doc.ble_scan_button.on_click(on_ble_scan_start)
        doc.ble_scan_button._update_event_callbacks()
        logger.info(f"  - ble_scan_button subscribed_events={list(doc.ble_scan_button.subscribed_events)}")

        def _log_scan_event(event):
            logger.info(f"ButtonClick event received: ble_scan_button session={session_id} model_id={doc.ble_scan_button.id}")

        doc.ble_scan_button.on_event(ButtonClick, _log_scan_event)
        doc.ble_scan_button._update_event_callbacks()
        event_logger_refs.append(_log_scan_event)
    else:
        logger.warning("  - ble_scan_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_scan_stop_button'):
        logger.info(f"  - Registering ble_scan_stop_button callback model_id={doc.ble_scan_stop_button.id}")
        doc.ble_scan_stop_button.on_click(on_ble_scan_stop)
        doc.ble_scan_stop_button._update_event_callbacks()
        logger.info(f"  - ble_scan_stop_button subscribed_events={list(doc.ble_scan_stop_button.subscribed_events)}")

        def _log_scan_stop_event(event):
            logger.info(f"ButtonClick event received: ble_scan_stop_button session={session_id} model_id={doc.ble_scan_stop_button.id}")

        doc.ble_scan_stop_button.on_event(ButtonClick, _log_scan_stop_event)
        doc.ble_scan_stop_button._update_event_callbacks()
        event_logger_refs.append(_log_scan_stop_event)
    else:
        logger.warning("  - ble_scan_stop_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_capture_button'):
        logger.info(f"  - Registering ble_capture_button callback model_id={doc.ble_capture_button.id}")
        doc.ble_capture_button.on_click(on_ble_capture_start)
        doc.ble_capture_button._update_event_callbacks()
        logger.info(f"  - ble_capture_button subscribed_events={list(doc.ble_capture_button.subscribed_events)}")

        def _log_capture_event(event):
            logger.info(f"ButtonClick event received: ble_capture_button session={session_id} model_id={doc.ble_capture_button.id}")

        doc.ble_capture_button.on_event(ButtonClick, _log_capture_event)
        doc.ble_capture_button._update_event_callbacks()
        event_logger_refs.append(_log_capture_event)
    else:
        logger.warning("  - ble_capture_button NOT FOUND in doc")
    
    if hasattr(doc, 'ble_capture_stop_button'):
        logger.info(f"  - Registering ble_capture_stop_button callback model_id={doc.ble_capture_stop_button.id}")
        doc.ble_capture_stop_button.on_click(on_ble_capture_stop)
        doc.ble_capture_stop_button._update_event_callbacks()
        logger.info(f"  - ble_capture_stop_button subscribed_events={list(doc.ble_capture_stop_button.subscribed_events)}")

        def _log_capture_stop_event(event):
            logger.info(f"ButtonClick event received: ble_capture_stop_button session={session_id} model_id={doc.ble_capture_stop_button.id}")

        doc.ble_capture_stop_button.on_event(ButtonClick, _log_capture_stop_event)
        doc.ble_capture_stop_button._update_event_callbacks()
        event_logger_refs.append(_log_capture_stop_event)
    else:
        logger.warning("  - ble_capture_stop_button NOT FOUND in doc")

    if hasattr(doc, 'ble_profiler_button'):
        logger.info("  - Registering ble_profiler_button")
        doc.ble_profiler_button.on_click(on_ble_profiler_start)
        doc.ble_profiler_button._update_event_callbacks()
    else:
        logger.warning("  - ble_profiler_button NOT FOUND in doc")

    if hasattr(doc, 'ble_profiler_stop_button'):
        logger.info("  - Registering ble_profiler_stop_button")
        doc.ble_profiler_stop_button.on_click(on_ble_profiler_stop)
        doc.ble_profiler_stop_button._update_event_callbacks()
    else:
        logger.warning("  - ble_profiler_stop_button NOT FOUND in doc")

    if hasattr(doc, 'ble_proxy_start_button'):
        logger.info(f"  - Registering ble_proxy_start_button")
        doc.ble_proxy_start_button.on_click(on_ble_proxy_start)
        doc.ble_proxy_start_button._update_event_callbacks()
    else:
        logger.warning("  - ble_proxy_start_button NOT FOUND in doc")

    if hasattr(doc, 'ble_proxy_stop_button'):
        logger.info(f"  - Registering ble_proxy_stop_button")
        doc.ble_proxy_stop_button.on_click(on_ble_proxy_stop)
        doc.ble_proxy_stop_button._update_event_callbacks()
    else:
        logger.warning("  - ble_proxy_stop_button NOT FOUND in doc")

    def _register_value_debug(attr_name):
        if hasattr(doc, attr_name):
            model = getattr(doc, attr_name)
            if hasattr(model, 'on_change'):
                logger.info(f"  - Registering value-change debug for {attr_name} model_id={getattr(model, 'id', 'n/a')}")

                def _on_value_change(attr, old, new, _attr_name=attr_name):
                    logger.info(f"Client->server value change: {_attr_name} old={old!r} new={new!r} session={session_id}")

                model.on_change('value', _on_value_change)

    _register_value_debug('log_action_filter')
    _register_value_debug('log_device_select')
    _register_value_debug('ble_event_filter')
    _register_value_debug('ble_capture_select')

    # Keep strong references to callback closures for the life of this session.
    # Some callback registries can hold weak refs, which can drop local closures.
    callback_refs = [
        on_apply_changes,
        on_reload_config,
        on_refresh_active_config,
        on_ble_scan_clear,
        on_ble_scan_start,
        on_ble_scan_stop,
        on_ble_capture_start,
        on_ble_capture_stop,
        on_ble_profiler_start,
        on_ble_profiler_stop,
        on_ble_proxy_start,
        on_ble_proxy_stop,
        *event_logger_refs,
    ]

    # Store callback refs in a generic attribute for PerimeterControl
    if hasattr(doc, '_perimetercontrol_callback_refs'):
        doc._perimetercontrol_callback_refs.extend(callback_refs)
    else:
        doc._perimetercontrol_callback_refs = callback_refs

    logger.info("All callbacks registered successfully")
