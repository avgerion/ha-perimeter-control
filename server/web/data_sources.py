#!/usr/bin/env python3
"""
Data source manager for the Network Isolator dashboard.
Fetches live data from nftables, dnsmasq, tcpdump, and config files.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import yaml

logger = logging.getLogger('isolator.data_sources')


class DataManager:
    """Manages all data sources for the dashboard."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.last_update = datetime.now()
        
        # Cache for performance
        self.device_cache = {}
        self.traffic_buffer = defaultdict(list)  # device_id -> [(timestamp, bytes_in, bytes_out)]
        self.connection_cache = []
        
    def _load_config(self) -> Dict[str, Any]:
        """Load isolator.conf.yaml."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.debug(f"Loaded config: {len(config.get('devices', []))} devices")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {'devices': [], 'default_policy': {}}
    
    def reload_config(self):
        """Reload configuration file (called on file change or manual refresh)."""
        logger.info("Reloading configuration...")
        self.config = self._load_config()
    
    def get_connected_devices(self) -> pd.DataFrame:
        """
        Get list of currently connected devices from dnsmasq leases.
        
        Returns DataFrame with columns:
          - mac: MAC address
          - ip: Assigned IP
          - hostname: Device hostname (if available)
          - lease_expires: Expiration timestamp
          - connected: True if lease is active
        """
        leases_file = Path('/var/lib/misc/dnsmasq.leases')
        devices = []
        
        try:
            if leases_file.exists():
                with open(leases_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            expires_ts, mac, ip, hostname = parts[:4]
                            expires = datetime.fromtimestamp(int(expires_ts))
                            connected = expires > datetime.now()
                            
                            devices.append({
                                'mac': mac.lower(),
                                'ip': ip,
                                'hostname': hostname if hostname != '*' else f'device-{ip.split(".")[-1]}',
                                'lease_expires': expires,
                                'connected': connected
                            })
        except Exception as e:
            logger.error(f"Failed to read dnsmasq leases: {e}")
        
        # Merge with config to get device IDs and rules
        df = pd.DataFrame(devices)
        if not df.empty:
            # Auto-add unknown devices to config
            for _, device in pd.DataFrame(devices).iterrows():
                mac = device['mac'].lower()
                if not self._device_exists_in_config(mac):
                    self._auto_add_device(mac, device['ip'], device['hostname'])
            
            # Reload config after auto-adding devices
            self.config = self._load_config()
            
            df['device_id'] = df['mac'].apply(self._get_device_id_from_mac)
            df['internet'] = df['device_id'].apply(self._get_device_rule, args=('internet',))
            df['capture_enabled'] = df['device_id'].apply(self._get_capture_status)
        else:
            # Empty DataFrame with expected schema
            df = pd.DataFrame(columns=['mac', 'ip', 'hostname', 'lease_expires', 'connected', 
                                      'device_id', 'internet', 'capture_enabled'])
        
        return df
    
    def _device_exists_in_config(self, mac: str) -> bool:
        """Check if device with this MAC already exists in config."""
        for device in self.config.get('devices', []):
            if device.get('mac', '').lower() == mac.lower():
                return True
        return False
    
    def _auto_add_device(self, mac: str, ip: str, hostname: str):
        """
        Auto-add a newly discovered device to the config file.
        Uses default_policy settings for the new device.
        """
        try:
            # Generate device ID from hostname or MAC
            device_id = hostname.replace(' ', '-').replace('_', '-').lower()
            if device_id == '*' or not device_id:
                device_id = f"device-{mac.replace(':', '')[-6:]}"
            
            # Get default policy
            default_policy = self.config.get('default_policy', {})
            
            # Create new device entry
            new_device = {
                'id': device_id,
                'mac': mac,
                'name': hostname if hostname != '*' else f'Device {mac[-8:]}',
                'internet': default_policy.get('internet', 'deny'),
                'lan_access': [],
                'logging': default_policy.get('logging', 'metadata')
            }
            
            # Add capture settings if enabled in default policy
            if default_policy.get('capture', {}).get('enabled', False):
                new_device['capture'] = {
                    'enabled': True,
                    'filter': '',
                    'output': f'/mnt/isolator/captures/{device_id}'
                }
            
            # Add to config
            if 'devices' not in self.config:
                self.config['devices'] = []
            self.config['devices'].append(new_device)
            
            # Write updated config
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Auto-added device: {device_id} (MAC: {mac}, IP: {ip})")
            
        except Exception as e:
            logger.error(f"Failed to auto-add device {mac}: {e}")
    
    def _get_device_id_from_mac(self, mac: str) -> str:
        """Look up device ID from MAC address in config."""
        for device in self.config.get('devices', []):
            if device.get('mac', '').lower() == mac.lower():
                return device.get('id', f'unknown-{mac[-5:]}')
        return f'unknown-{mac[-5:]}'
    
    def _get_device_rule(self, device_id: str, rule_key: str) -> Any:
        """Get a specific rule value for a device."""
        if device_id.startswith('unknown-'):
            # Apply default policy for unknown devices
            return self.config.get('default_policy', {}).get(rule_key, 'deny')
        
        for device in self.config.get('devices', []):
            if device.get('id') == device_id:
                return device.get(rule_key, 'deny')
        return 'deny'
    
    def _get_capture_status(self, device_id: str) -> bool:
        """Check if packet capture is enabled for this device."""
        if device_id.startswith('unknown-'):
            # Unknown devices get max sniff mode by default
            return self.config.get('default_policy', {}).get('capture', {}).get('enabled', True)
        
        for device in self.config.get('devices', []):
            if device.get('id') == device_id:
                return device.get('capture', {}).get('enabled', False)
        return False
    
    def get_traffic_stats(self, time_window_sec: int = 30) -> pd.DataFrame:
        """
        Get traffic statistics from nftables counters.
        
        Returns DataFrame with columns:
          - device_id: Device identifier
          - timestamp: Measurement time
          - bytes_in: Bytes received
          - bytes_out: Bytes transmitted
          - packets_in: Packets received
          - packets_out: Packets transmitted
        """
        # This would parse `nft list ruleset` to extract counter values
        # For now, return mock data structure
        # TODO: Implement actual nftables counter parsing
        
        cutoff_time = datetime.now() - timedelta(seconds=time_window_sec)
        
        # Example structure (real implementation would call subprocess.run(['nft', 'list', 'ruleset']))
        stats = []
        for device_id, data_points in self.traffic_buffer.items():
            for ts, bytes_in, bytes_out, packets_in, packets_out in data_points:
                if ts > cutoff_time:
                    stats.append({
                        'device_id': device_id,
                        'timestamp': ts,
                        'bytes_in': bytes_in,
                        'bytes_out': bytes_out,
                        'packets_in': packets_in,
                        'packets_out': packets_out
                    })
        
        return pd.DataFrame(stats)
    
    def get_active_connections(self) -> pd.DataFrame:
        """
        Get active connections from conntrack or nftables.
        
        Returns DataFrame with columns:
          - device_ip: Source IP (AP client)
          - device_id: Device identifier
          - protocol: TCP/UDP/ICMP
          - remote_ip: Destination IP
          - remote_port: Destination port
          - state: Connection state (ESTABLISHED, etc.)
          - start_time: Connection started
          - packet_count: Total packets
          - byte_count: Total bytes
        """
        connections = []
        
        try:
            # Use conntrack to get active connections
            # conntrack -L -o extended 2>/dev/null
            result = subprocess.run(
                ['conntrack', '-L', '-o', 'extended'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # Parse conntrack output (simplified)
            # Real implementation would parse the actual format
            # For now, return cached data
            connections = self.connection_cache
            
        except subprocess.TimeoutExpired:
            logger.warning("conntrack command timed out")
        except FileNotFoundError:
            logger.warning("conntrack not installed")
        except Exception as e:
            logger.error(f"Failed to get connections: {e}")
        
        df = pd.DataFrame(connections)
        if df.empty:
            df = pd.DataFrame(columns=['device_ip', 'device_id', 'protocol', 'remote_ip',
                                      'remote_port', 'state', 'start_time', 'packet_count', 'byte_count'])
        
        return df
    
    def get_device_logs(self, device_id: str = None, max_lines: int = 100) -> List[Dict[str, Any]]:
        """
        Get traffic logs for a specific device from /var/log/isolator/devices/{device_id}.log
        
        Args:
            device_id: Device ID to get logs for (e.g., 'moto-g-2025'). 
                       If None, returns list of available log files.
            max_lines: Maximum number of log lines to return
        
        Returns list of log entries (newest first), each with:
          - timestamp: Event time (ISO format)
          - device_id: Device ID
          - action: 'ALLOWED' or 'BLOCKED'
          - protocol: 'TCP', 'UDP', 'ICMP', etc.
          - src_ip: Source IP address
          - dst_ip: Destination IP address
          - src_port: Source port (optional)
          - dst_port: Destination port (optional)
          - bytes: Packet size in bytes (optional)
        """
        devices_log_dir = Path('/var/log/isolator/devices')
        logs = []
        
        try:
            # If no device specified, return list of available devices with logs
            if device_id is None:
                if devices_log_dir.exists():
                    available = [f.stem for f in devices_log_dir.glob('*.log')]
                    return [{
                        'timestamp': datetime.now().isoformat(),
                        'device_id': 'system',
                        'action': 'INFO',
                        'protocol': '',
                        'src_ip': '',
                        'dst_ip': '',
                        'message': f'Available device logs: {", ".join(available) if available else "None"}. Select a device to view its traffic logs.'
                    }]
                else:
                    return [{
                        'timestamp': datetime.now().isoformat(),
                        'device_id': 'system',
                        'action': 'INFO',
                        'protocol': '',
                        'src_ip': '',
                        'dst_ip': '',
                        'message': 'Traffic logging not started yet. Enable isolator-traffic.service to begin logging.'
                    }]
            
            # Get logs for specific device
            log_file = devices_log_dir / f"{device_id}.log"
            
            if not log_file.exists():
                return [{
                    'timestamp': datetime.now().isoformat(),
                    'device_id': device_id,
                    'action': 'INFO',
                    'protocol': '',
                    'src_ip': '',
                    'dst_ip': '',
                    'message': f'No traffic logs found for {device_id}. Device may not have sent/received any packets yet.'
                }]
            
            # Tail last N lines from device log file
            result = subprocess.run(
                ['tail', '-n', str(max_lines), str(log_file)],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # Parse JSON log entries
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                    logs.append(entry)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse log line for {device_id}: {e}")
                    continue
            
            if not logs:
                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'device_id': device_id,
                    'action': 'INFO',
                    'protocol': '',
                    'src_ip': '',
                    'dst_ip': '',
                    'message': f'Log file exists but contains no valid entries yet.'
                })
                
        except Exception as e:
            logger.error(f"Failed to read logs for {device_id}: {e}")
            logs.append({
                'timestamp': datetime.now().isoformat(),
                'device_id': device_id or 'system',
                'action': 'ERROR',
                'protocol': '',
                'src_ip': '',
                'dst_ip': '',
                'message': f'Error reading logs: {e}'
            })
        
        return logs[::-1]  # Reverse to get newest first
    
    def get_capture_status_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Get capture status for all devices.
        
        Returns dict: {device_id: {active: bool, output_dir: str, size_mb: float}}
        """
        status = {}
        
        for device in self.config.get('devices', []):
            device_id = device.get('id')
            capture_config = device.get('capture', {})
            
            if capture_config.get('enabled'):
                output_dir = Path(capture_config.get('output', f'/mnt/isolator/captures/{device_id}'))
                
                # Check if tcpdump is running for this device
                active = self._is_capture_active(device_id)
                
                # Calculate total capture file size
                size_mb = 0.0
                if output_dir.exists():
                    size_mb = sum(f.stat().st_size for f in output_dir.glob('*.pcap')) / (1024 * 1024)
                
                status[device_id] = {
                    'active': active,
                    'output_dir': str(output_dir),
                    'size_mb': round(size_mb, 2)
                }
        
        return status
    
    def _is_capture_active(self, device_id: str) -> bool:
        """Check if tcpdump process is running for device."""
        try:
            result = subprocess.run(
                ['pgrep', '-f', f'tcpdump.*{device_id}'],
                capture_output=True,
                timeout=1
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def update_device_rule(self, device_id: str, rule_key: str, value: Any) -> bool:
        """
        Update a device rule in the config file and trigger reload.
        
        Args:
            device_id: Target device
            rule_key: Rule to update (e.g., 'internet', 'logging')
            value: New value
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find and update device in config
            for device in self.config.get('devices', []):
                if device.get('id') == device_id:
                    device[rule_key] = value
                    break
            else:
                logger.error(f"Device not found: {device_id}")
                return False
            
            # Write updated config
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Updated {device_id}.{rule_key} = {value}")
            
            # Trigger isolator service reload
            subprocess.run(['sudo', 'systemctl', 'reload', 'isolator'], timeout=5)
            
            return True
        except Exception as e:
            logger.error(f"Failed to update device rule: {e}")
            return False
    
    def get_interface_status(self, interface: str) -> Dict[str, Any]:
        """
        Get status for a network interface.
        
        Args:
            interface: Interface name (e.g., 'wlan0', 'eth0')
            
        Returns:
            Dict with keys: up, ip, mac, rx_bytes, tx_bytes, rx_packets, tx_packets
        """
        status = {
            'up': False,
            'ip': None,
            'mac': None,
            'rx_bytes': 0,
            'tx_bytes': 0,
            'rx_packets': 0,
            'tx_packets': 0
        }
        
        try:
            # Check if interface exists and is up
            result = subprocess.run(
                ['ip', 'link', 'show', interface],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Parse state and MAC
                for line in result.stdout.split('\n'):
                    if 'state UP' in line or 'state UNKNOWN' in line:
                        status['up'] = True
                    if 'link/ether' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            status['mac'] = parts[1]
            
            # Get IP address
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show', interface],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            status['ip'] = parts[1].split('/')[0]
                            break
            
            # Get statistics
            stats_path = Path(f'/sys/class/net/{interface}/statistics')
            if stats_path.exists():
                try:
                    status['rx_bytes'] = int((stats_path / 'rx_bytes').read_text().strip())
                    status['tx_bytes'] = int((stats_path / 'tx_bytes').read_text().strip())
                    status['rx_packets'] = int((stats_path / 'rx_packets').read_text().strip())
                    status['tx_packets'] = int((stats_path / 'tx_packets').read_text().strip())
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to get interface status for {interface}: {e}")
        
        return status
    
    def get_wifi_ap_status(self) -> Dict[str, Any]:
        """
        Get WiFi AP status from hostapd.
        
        Returns:
            Dict with keys: running, ssid, channel, clients, interface
        """
        status = {
            'running': False,
            'ssid': None,
            'channel': None,
            'clients': 0,
            'interface': 'wlan0'
        }
        
        try:
            # Check if hostapd service is running
            result = subprocess.run(
                ['systemctl', 'is-active', 'hostapd'],
                capture_output=True,
                text=True,
                timeout=2
            )
            status['running'] = (result.returncode == 0 and 'active' in result.stdout)
            
            # Read hostapd config for SSID and channel
            hostapd_conf = Path('/etc/hostapd/hostapd.conf')
            if hostapd_conf.exists():
                with open(hostapd_conf, 'r') as f:
                    for line in f:
                        if line.startswith('ssid='):
                            status['ssid'] = line.split('=', 1)[1].strip()
                        elif line.startswith('channel='):
                            status['channel'] = line.split('=', 1)[1].strip()
                        elif line.startswith('interface='):
                            status['interface'] = line.split('=', 1)[1].strip()
            
            # Count connected clients from dnsmasq leases
            leases = self.get_connected_devices()
            status['clients'] = len(leases[leases['connected']])
            
        except Exception as e:
            logger.error(f"Failed to get WiFi AP status: {e}")
        
        return status
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics: CPU, memory, disk usage, uptime.
        
        Returns:
            Dict with keys: cpu_percent, mem_used_mb, mem_total_mb, disk_free_gb, uptime_hours
        """
        stats = {
            'cpu_percent': 0,
            'mem_used_mb': 0,
            'mem_total_mb': 0,
            'disk_free_gb': 0,
            'uptime_hours': 0
        }
        
        try:
            # Get disk usage for /mnt/isolator
            result = subprocess.run(
                ['df', '-BG', '/mnt/isolator'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        stats['disk_free_gb'] = int(parts[3].rstrip('G'))
            
            # Get memory info
            meminfo = Path('/proc/meminfo')
            if meminfo.exists():
                mem_total = mem_available = 0
                with open(meminfo, 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            mem_total = int(line.split()[1]) // 1024  # Convert KB to MB
                        elif line.startswith('MemAvailable:'):
                            mem_available = int(line.split()[1]) // 1024
                stats['mem_total_mb'] = mem_total
                stats['mem_used_mb'] = mem_total - mem_available
            
            # Get uptime
            uptime_file = Path('/proc/uptime')
            if uptime_file.exists():
                uptime_sec = float(uptime_file.read_text().split()[0])
                stats['uptime_hours'] = round(uptime_sec / 3600, 1)
                
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
        
        return stats
    
    def get_ble_captures(self) -> List[Dict[str, Any]]:
        """
        Get list of available BLE capture sessions.
        
        Returns list of capture info, each with:
          - filename: Capture file basename (e.g., 'DeviceName_2026-03-26_143022.json')
          - target: Target device name or MAC
          - timestamp: Capture start time
          - size_kb: File size in KB
          - event_count: Number of events in capture
        """
        ble_log_dir = Path('/var/log/isolator/ble')
        captures = []
        
        try:
            if not ble_log_dir.exists():
                return []
            
            # Find all JSON capture files
            for json_file in sorted(ble_log_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True):
                try:
                    stat = json_file.stat()
                    size_kb = stat.st_size / 1024
                    
                    # Count events in file
                    event_count = 0
                    with open(json_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                event_count += 1
                    
                    # Parse filename: target_YYYY-MM-DD_HHMMSS.json
                    basename = json_file.stem  # Remove .json
                    parts = basename.rsplit('_', 2)  # Split from right, max 2 splits
                    if len(parts) >= 3:
                        target = parts[0]
                        date_str = parts[1]
                        time_str = parts[2]
                        timestamp = f"{date_str} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                    else:
                        target = basename
                        timestamp = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    captures.append({
                        'filename': json_file.name,
                        'target': target,
                        'timestamp': timestamp,
                        'size_kb': round(size_kb, 1),
                        'event_count': event_count
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to process BLE capture {json_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to list BLE captures: {e}")
        
        return captures
    
    def get_ble_logs(self, capture_file: str = None, max_events: int = 200) -> List[Dict[str, Any]]:
        """
        Get BLE events from a capture file.
        
        Args:
            capture_file: Filename of capture (e.g., 'DeviceName_2026-03-26_143022.json')
                         If None, returns most recent capture
            max_events: Maximum number of events to return (newest first)
        
        Returns list of BLE events, each with:
          - timestamp: Event time (ISO format)
          - type: Event type (advertisement, connection, gatt_read, gatt_write, etc.)
          - data: Dict with event-specific data (address, name, handle, value, etc.)
        """
        ble_log_dir = Path('/var/log/isolator/ble')
        events = []
        
        try:
            if not ble_log_dir.exists():
                return [{
                    'timestamp': datetime.now().isoformat(),
                    'type': 'info',
                    'data': {'message': 'BLE logging directory not found. No captures available yet.'}
                }]
            
            # If no file specified, get most recent
            if capture_file is None:
                json_files = list(ble_log_dir.glob('*.json'))
                if not json_files:
                    return [{
                        'timestamp': datetime.now().isoformat(),
                        'type': 'info',
                        'data': {'message': 'No BLE captures found. Start a capture to begin.'}
                    }]
                capture_file = max(json_files, key=lambda f: f.stat().st_mtime).name
            
            log_file = ble_log_dir / capture_file
            
            if not log_file.exists():
                return [{
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error',
                    'data': {'message': f'Capture file not found: {capture_file}'}
                }]
            
            # Read JSON events
            with open(log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse BLE event: {e}")
                        continue
            
            if not events:
                return [{
                    'timestamp': datetime.now().isoformat(),
                    'type': 'info',
                    'data': {'message': f'Capture file exists but contains no events yet: {capture_file}'}
                }]
                
        except Exception as e:
            logger.error(f"Failed to read BLE logs: {e}")
            return [{
                'timestamp': datetime.now().isoformat(),
                'type': 'error',
                'data': {'message': f'Error reading BLE logs: {e}'}
            }]
        
        # Return newest first, limited to max_events
        return events[-max_events:][::-1]
    
    def start_ble_capture(self, target_name: str = None, target_mac: str = None, duration: int = 300) -> Dict[str, Any]:
        """
        Start a new BLE capture session.
        
        Args:
            target_name: Target device name to filter (optional)
            target_mac: Target device MAC address to filter (optional)
            duration: Capture duration in seconds (default: 300 = 5 minutes)
        
        Returns:
            Dict with 'success' (bool), 'message' (str), 'pid' (int if success)
        """
        try:
            # Check if already running
            status = self.get_ble_capture_status()
            if status['active']:
                return {
                    'success': False,
                    'message': f'BLE capture already running (PID {status["pid"]}). Stop it first.'
                }
            
            # Build command
            cmd = ['sudo', 'python3', '/opt/isolator/scripts/ble-sniffer.py']
            
            if target_name:
                cmd.extend(['--target', target_name])
            elif target_mac:
                cmd.extend(['--target-mac', target_mac])
            else:
                return {
                    'success': False,
                    'message': 'Either target_name or target_mac must be specified'
                }
            
            if duration:
                cmd.extend(['--duration', str(duration)])
            
            # Start capture in background
            result = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Give it a moment to start
            import time
            time.sleep(1)
            
            # Check if still running
            if result.poll() is None:
                target = target_name or target_mac
                logger.info(f"Started BLE capture for {target} (PID {result.pid})")
                return {
                    'success': True,
                    'message': f'BLE capture started for {target} (duration: {duration}s)',
                    'pid': result.pid
                }
            else:
                stderr = result.stderr.read().decode('utf-8', errors='ignore')
                return {
                    'success': False,
                    'message': f'BLE capture failed to start: {stderr[:200]}'
                }
                
        except Exception as e:
            logger.error(f"Failed to start BLE capture: {e}")
            return {
                'success': False,
                'message': f'Error starting BLE capture: {e}'
            }
    
    def stop_ble_capture(self) -> Dict[str, Any]:
        """
        Stop active BLE capture.
        
        Returns:
            Dict with 'success' (bool) and 'message' (str)
        """
        try:
            status = self.get_ble_capture_status()
            if not status['active']:
                return {
                    'success': False,
                    'message': 'No active BLE capture to stop'
                }
            
            # Kill the ble-sniffer process
            result = subprocess.run(
                ['sudo', 'pkill', '-f', 'ble-sniffer.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            logger.info("Stopped BLE capture")
            return {
                'success': True,
                'message': 'BLE capture stopped'
            }
            
        except Exception as e:
            logger.error(f"Failed to stop BLE capture: {e}")
            return {
                'success': False,
                'message': f'Error stopping BLE capture: {e}'
            }
    
    def get_ble_capture_status(self) -> Dict[str, Any]:
        """
        Check if BLE capture is currently running.
        
        Returns:
            Dict with 'active' (bool), 'pid' (int or None), 'target' (str or None)
        """
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'ble-sniffer.py'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip().split()[0])
                
                # Try to get target from command line
                try:
                    cmdline_result = subprocess.run(
                        ['ps', '-p', str(pid), '-o', 'args='],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    cmdline = cmdline_result.stdout.strip()
                    
                    # Parse target from command line
                    target = None
                    if '--target ' in cmdline:
                        target = cmdline.split('--target ')[1].split()[0]
                    elif '--target-mac ' in cmdline:
                        target = cmdline.split('--target-mac ')[1].split()[0]
                    
                    return {
                        'active': True,
                        'pid': pid,
                        'target': target
                    }
                except:
                    return {
                        'active': True,
                        'pid': pid,
                        'target': None
                    }
            else:
                return {
                    'active': False,
                    'pid': None,
                    'target': None
                }
                
        except Exception as e:
            logger.error(f"Failed to check BLE capture status: {e}")
            return {
                'active': False,
                'pid': None,
                'target': None
            }
    
    def start_ble_scan(self) -> Dict[str, Any]:
        """
        Start BLE device discovery scan (active scanning).
        
        Returns:
            Dict with 'success' (bool), 'message' (str), 'pid' (int if success)
        """
        try:
            # Check if already running
            status = self.get_ble_scan_status()
            if status['active']:
                return {
                    'success': False,
                    'message': f'BLE scan already running (PID {status["pid"]}). Stop it first.'
                }
            
            # Start scanner in background (no duration = run until stopped)
            result = subprocess.Popen(
                ['sudo', 'python3', '/opt/isolator/scripts/ble-scanner.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Give it a moment to start
            import time
            time.sleep(1)
            
            # Check if still running
            if result.poll() is None:
                logger.info(f"Started BLE scan (PID {result.pid})")
                return {
                    'success': True,
                    'message': 'BLE device scan started',
                    'pid': result.pid
                }
            else:
                stderr_text = ""
                if result.stderr:
                    stderr_text = result.stderr.read().decode('utf-8', errors='ignore')
                return {
                    'success': False,
                    'message': f'BLE scan failed to start: {stderr_text[:200]}'
                }
                
        except Exception as e:
            logger.error(f"Failed to start BLE scan: {e}")
            return {
                'success': False,
                'message': f'Error starting BLE scan: {e}'
            }
    
    def stop_ble_scan(self) -> Dict[str, Any]:
        """
        Stop active BLE device scan.
        
        Returns:
            Dict with 'success' (bool) and 'message' (str)
        """
        try:
            status = self.get_ble_scan_status()
            if not status['active']:
                return {
                    'success': False,
                    'message': 'No active BLE scan to stop'
                }
            
            # Kill the ble-scanner process
            result = subprocess.run(
                ['sudo', 'pkill', '-f', 'ble-scanner.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            logger.info("Stopped BLE scan")
            return {
                'success': True,
                'message': 'BLE scan stopped'
            }
            
        except Exception as e:
            logger.error(f"Failed to stop BLE scan: {e}")
            return {
                'success': False,
                'message': f'Error stopping BLE scan: {e}'
            }
    
    def get_ble_scan_status(self) -> Dict[str, Any]:
        """
        Check if BLE scan is currently running.
        
        Returns:
            Dict with 'active' (bool), 'pid' (int or None), 'device_count' (int)
        """
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'ble-scanner.py'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip().split()[0])
                
                # Get device count from latest scan file
                device_count = len(self.get_ble_scan_devices())
                
                return {
                    'active': True,
                    'pid': pid,
                    'device_count': device_count
                }
            else:
                return {
                    'active': False,
                    'pid': None,
                    'device_count': 0
                }
                
        except Exception as e:
            logger.error(f"Failed to check BLE scan status: {e}")
            return {
                'active': False,
                'pid': None,
                'device_count': 0
            }
    
    def get_ble_scan_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of devices discovered by active BLE scan.
        
        Returns list of discovered devices, each with:
          - mac: Device MAC address
          - name: Device name (or Unknown_XXXXXX)
          - first_seen: ISO timestamp when first discovered
          - last_seen: ISO timestamp of last advertisement
          - count: Number of times seen
        """
        ble_log_dir = Path('/var/log/isolator/ble')
        devices = []
        
        try:
            if not ble_log_dir.exists():
                return []
            
            # Find most recent scan_*.json file
            scan_files = list(ble_log_dir.glob('scan_*.json'))
            if not scan_files:
                return []
            
            latest_scan = max(scan_files, key=lambda f: f.stat().st_mtime)
            
            # Read device list
            with open(latest_scan, 'r') as f:
                scan_data = json.load(f)
                devices = scan_data.get('devices', [])
            
        except Exception as e:
            logger.error(f"Failed to read BLE scan devices: {e}")
        
        return devices
