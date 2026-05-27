def get_network_topology(config):
    """Resolve effective isolated/upstream roles from config, with legacy fallbacks."""
    topology = config.get('topology', {}) or {}
    upstream = topology.get('upstream', {}) or {}
    isolated = topology.get('isolated', {}) or {}
    ap = config.get('ap', {}) or {}
    wan = config.get('wan', {}) or {}
    lan = config.get('lan', {}) or {}

    isolated_kind = isolated.get('kind') or ('wifi-ap' if ap else 'ethernet')
    isolated_interface = (
        isolated.get('interface')
        or lan.get('interface')
        or ap.get('interface')
        or ('wlan0' if isolated_kind == 'wifi-ap' else 'eth0')
    )
    upstream_interface = upstream.get('interface') or wan.get('interface')
    if not upstream_interface:
        upstream_interface = 'eth0' if isolated_interface != 'eth0' else 'wlan0'
    upstream_kind = upstream.get('kind') or wan.get('kind') or ('wifi-client' if upstream_interface.startswith('wl') else 'ethernet')

    return {
        'isolated': {
            'interface': isolated_interface,
            'kind': isolated_kind,
            'label': isolated.get('label', 'Isolated')
        },
        'upstream': {
            'interface': upstream_interface,
            'kind': upstream_kind,
            'label': upstream.get('label', 'Upstream')
        },
        'ap': ap,
    }

def setup_network_isolator_callbacks(doc, data_manager):
    # Example: attach network-specific callbacks to doc here
    pass
#!/usr/bin/env python3
"""
Network Isolator service-specific callbacks.
Migrated from callbacks.py.
"""

import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Dict, Optional

from bokeh.models import ColumnDataSource
from bokeh.events import ButtonClick

# ─── Configurable Constants ─────────────────────────────────────────────
BLE_SCAN_LOG_DIR = '/var/log/PerimeterControl/ble'
BLE_SCAN_LOG_PATTERN = BLE_SCAN_LOG_DIR + '/scan_*.json'

LOGGER_NAME = 'PerimeterControl.callbacks'
logger = logging.getLogger(LOGGER_NAME)

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
            raw = bytes.fromhex(uuid_str.replace('-', ''))
            if len(raw) == 16:
                out += bytes([len(raw) + 1, 0x07]) + raw[::-1]
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
    adv = device.get('adv_data', {})
    if not adv:
        return ("<p style='color:#7f8c8d;font-style:italic;'>"
                "No advertisement data — rescan after deploying the updated scanner</p>")
    raw_bytes = _reconstruct_ad_bytes(adv)
    hexdump   = _hexdump(raw_bytes)
    raw_hex   = ' '.join(f'{b:02X}' for b in raw_bytes) or '(none)'
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
    # ...existing setup_callbacks and periodic update logic from callbacks.py...
    # (copy all update_devices, update_traffic, update_connections, update_logs, update_log_viewer, update_system_status, and their scheduling)
    # ...existing code from callbacks.py...
    pass  # (Insert all periodic update and event handler logic here)
