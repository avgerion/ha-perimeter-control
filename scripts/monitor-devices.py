#!/usr/bin/env python3
"""
Device Monitor - Watches for new devices and starts captures

This script monitors dnsmasq.leases for new device connections and:
  1. Identifies the device from config (or marks as unknown)
  2. Starts packet capture if enabled
  3. Logs device connection events

Runs as a daemon watching the dnsmasq leases file.

Usage:
    python3 monitor-devices.py --config /path/to/isolator.conf.yaml
"""

import argparse
import time
import yaml
import logging
import subprocess
from pathlib import Path
from typing import Dict, Set
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('device-monitor')


class DeviceMonitor:
    """Monitor DHCP leases and manage device captures"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.known_devices: Dict[str, str] = {}  # MAC -> device_id
        self.active_macs: Set[str] = set()
        self._build_device_map()
    
    def _load_config(self) -> dict:
        """Load configuration file"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _build_device_map(self):
        """Build MAC -> device_id mapping"""
        for device in self.config.get('devices', []):
            mac = device.get('mac', '').lower()
            device_id = device.get('id', 'unknown')
            if mac:
                self.known_devices[mac] = device_id
        
        logger.info(f"Loaded {len(self.known_devices)} known devices")
    
    def _get_active_leases(self) -> Dict[str, Dict]:
        """Parse dnsmasq.leases file"""
        leases_file = Path('/var/lib/misc/dnsmasq.leases')
        
        if not leases_file.exists():
            return {}
        
        leases = {}
        with open(leases_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    timestamp, mac, ip, hostname, client_id = parts[0], parts[1], parts[2], parts[3], parts[4] if len(parts) > 4 else ''
                    leases[mac.lower()] = {
                        'ip': ip,
                        'hostname': hostname,
                        'timestamp': timestamp
                    }
        
        return leases
    
    def _start_capture_for_device(self, mac: str, device_id: str):
        """Start packet capture for a device"""
        
        # Check if capture is enabled in config
        capture_enabled = False
        for device in self.config.get('devices', []):
            if device.get('mac', '').lower() == mac:
                capture_enabled = device.get('capture', False)
                break
        
        # Unknown devices: check default policy
        if mac not in self.known_devices:
            default_policy = self.config.get('default_policy', {})
            capture_enabled = default_policy.get('capture', True)  # Default to enabled
        
        if not capture_enabled:
            logger.info(f"Capture disabled for {device_id} ({mac})")
            return
        
        # Start capture using helper script
        try:
            subprocess.run([
                'python3', '/opt/isolator/scripts/start-capture.py',
                '--mac', mac,
                '--device-id', device_id,
                '--action', 'start',
                '--enabled' if capture_enabled else '--no-enabled'
            ], check=True)
            
            logger.info(f"✓ Started capture for {device_id} ({mac})")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start capture for {device_id}: {e}")
    
    def _handle_new_device(self, mac: str, lease_info: dict):
        """Handle newly connected device"""
        
        device_id = self.known_devices.get(mac, f"unknown-{mac.replace(':', '')[-6:]}")
        ip = lease_info['ip']
        hostname = lease_info['hostname']
        
        logger.info(f"NEW DEVICE: {device_id}")
        logger.info(f"  MAC: {mac}")
        logger.info(f"  IP: {ip}")
        logger.info(f"  Hostname: {hostname}")
        
        # Start packet capture
        self._start_capture_for_device(mac, device_id)
        
        # Mark as active
        self.active_macs.add(mac)
    
    def _handle_device_disconnect(self, mac: str):
        """Handle device disconnection"""
        
        device_id = self.known_devices.get(mac, f"unknown-{mac.replace(':', '')[-6:]}")
        
        logger.info(f"DEVICE DISCONNECTED: {device_id} ({mac})")
        
        # Stop capture
        try:
            subprocess.run([
                'python3', '/opt/isolator/scripts/start-capture.py',
                '--mac', mac,
                '--device-id', device_id,
                '--action', 'stop'
            ], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to stop capture for {device_id}: {e}")
        
        # Remove from active set
        self.active_macs.discard(mac)
    
    def monitor(self, interval: int = 5):
        """Monitor for device changes"""
        
        logger.info("Starting device monitor...")
        logger.info(f"Monitoring dnsmasq leases every {interval}s")
        
        try:
            while True:
                current_leases = self._get_active_leases()
                current_macs = set(current_leases.keys())
                
                # Detect new devices
                new_macs = current_macs - self.active_macs
                for mac in new_macs:
                    self._handle_new_device(mac, current_leases[mac])
                
                # Detect disconnected devices
                disconnected_macs = self.active_macs - current_macs
                for mac in disconnected_macs:
                    self._handle_device_disconnect(mac)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Stopping device monitor...")


def main():
    parser = argparse.ArgumentParser(description='Monitor devices and manage captures')
    parser.add_argument('--config', default='/mnt/isolator/conf/isolator.conf.yaml', help='Path to config file')
    parser.add_argument('--interval', type=int, default=5, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    monitor = DeviceMonitor(config_path)
    monitor.monitor(interval=args.interval)


if __name__ == '__main__':
    main()
