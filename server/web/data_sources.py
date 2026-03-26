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
    
    def get_recent_logs(self, max_lines: int = 50) -> List[Dict[str, Any]]:
        """
        Tail recent log events from /var/log/isolator/traffic.log.
        Falls back to dashboard.log if traffic.log doesn't exist yet.
        
        Returns list of log entries (newest first), each with:
          - timestamp: Event time
          - level: info/warning/error
          - device_id: Device involved
          - event_type: connection_blocked / new_device / capture_started / etc.
          - message: Human-readable description
        """
        traffic_log = Path('/var/log/isolator/traffic.log')
        dashboard_log = Path('/var/log/isolator/dashboard.log')
        logs = []
        
        # Prefer traffic.log, fall back to dashboard.log
        log_file = traffic_log if traffic_log.exists() else dashboard_log
        
        try:
            if log_file.exists():
                # Tail last N lines
                result = subprocess.run(
                    ['tail', '-n', str(max_lines), str(log_file)],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                # Parse log entries
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    
                    # Try JSON format first (traffic.log)
                    try:
                        entry = json.loads(line)
                        logs.append(entry)
                    except json.JSONDecodeError:
                        # Parse Python logging format (dashboard.log)
                        # Format: "2026-03-26 14:32:09,348 [INFO] logger.name: message"
                        try:
                            parts = line.split(' ', 2)
                            if len(parts) >= 3:
                                timestamp = f"{parts[0]}T{parts[1].replace(',', '.')}"
                                rest = parts[2]
                                
                                # Extract level
                                level_match = rest.split('[', 1)[1].split(']', 1)[0] if '[' in rest else 'INFO'
                                level = level_match.lower()
                                
                                # Extract message (everything after ": ")
                                message = rest.split(': ', 1)[1] if ': ' in rest else rest
                                
                                # Extract module name
                                module = rest.split(']', 1)[1].split(':', 1)[0].strip() if ']' in rest else 'system'
                                
                                logs.append({
                                    'timestamp': timestamp,
                                    'level': level,
                                    'device_id': module,
                                    'event_type': 'log',
                                    'message': message
                                })
                        except Exception:
                            # If parsing fails, just use the raw line
                            logs.append({
                                'timestamp': datetime.now().isoformat(),
                                'level': 'info',
                                'device_id': 'system',
                                'event_type': 'log',
                                'message': line
                            })
            else:
                # No logs available yet
                logs.append({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'info',
                    'device_id': 'system',
                    'event_type': 'log',
                    'message': 'Log files not available yet. Traffic logging will start when packets are captured.'
                })
                
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            logs.append({
                'timestamp': datetime.now().isoformat(),
                'level': 'error',
                'device_id': 'system',
                'event_type': 'error',
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
