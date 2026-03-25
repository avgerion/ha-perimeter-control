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
            df['device_id'] = df['mac'].apply(self._get_device_id_from_mac)
            df['internet'] = df['device_id'].apply(self._get_device_rule, args=('internet',))
            df['capture_enabled'] = df['device_id'].apply(self._get_capture_status)
        else:
            # Empty DataFrame with expected schema
            df = pd.DataFrame(columns=['mac', 'ip', 'hostname', 'lease_expires', 'connected', 
                                      'device_id', 'internet', 'capture_enabled'])
        
        return df
    
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
        
        Returns list of log entries (newest first), each with:
          - timestamp: Event time
          - level: info/warning/error
          - device_id: Device involved
          - event_type: connection_blocked / new_device / capture_started / etc.
          - message: Human-readable description
        """
        log_file = Path('/var/log/isolator/traffic.log')
        logs = []
        
        try:
            if log_file.exists():
                # Tail last N lines
                result = subprocess.run(
                    ['tail', '-n', str(max_lines), str(log_file)],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                # Parse JSON log entries
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            entry = json.loads(line)
                            logs.append(entry)
                        except json.JSONDecodeError:
                            # Plain text log line
                            logs.append({
                                'timestamp': datetime.now().isoformat(),
                                'level': 'info',
                                'device_id': 'system',
                                'event_type': 'log',
                                'message': line
                            })
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
        
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
