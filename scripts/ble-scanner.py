#!/usr/bin/env python3
"""
BLE Scanner - Active Bluetooth device discovery

Performs active BLE scanning to discover nearby devices and their properties.
Outputs JSON with device information: name, MAC, RSSI, device type, services.

This is used for device discovery BEFORE starting targeted capture.
Active scanning = sends scan requests to get full device info including scan responses.

Output:
  - JSON file: /var/log/isolator/ble/scan_{timestamp}.json
  - Continuously updated while scanning

Usage:
    python3 ble-scanner.py
    python3 ble-scanner.py --duration 60
"""


import argparse
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock
import signal
import os

# ---------------- Configurable Constants ----------------
LOG_ROOT = os.environ.get('PERIMETERCONTROL_BLE_LOG_ROOT', '/var/log/PerimeterControl/ble')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.ble-scanner')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


class BLEScanner:
    """Active BLE scanner for device discovery"""
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or LOG_ROOT)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.scan_file = self.output_dir / f"scan_{timestamp}.json"
        
        # Device cache: MAC -> device info
        self.devices = {}
        self.devices_lock = Lock()
        
        self.scan_process = None
        self.running = False
        
        logger.info(f"BLE Scanner initialized")
        logger.info(f"Output: {self.scan_file}")
    
    def enable_bluetooth(self):
        """Enable Bluetooth interface"""
        try:
            # Unblock Bluetooth
            subprocess.run(['sudo', 'rfkill', 'unblock', 'bluetooth'], timeout=5)
            
            # Bring up hci0
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=True, timeout=5)
            
            logger.info("✓ Bluetooth interface hci0 enabled")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to enable Bluetooth: {e}")
            return False
    
    def start_scan(self):
        """Start active BLE scanning"""
        try:
            logger.info("Starting active BLE scan...")
            
            # Use hcitool for active scanning with duplicates
            # --duplicates = show each advertisement (not just first)
            # lescan = LE scan (active scan by default)
            self.scan_process = subprocess.Popen(
                ['sudo', 'hcitool', 'lescan', '--duplicates'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Start parser thread
            self.running = True
            self.parser_thread = Thread(target=self._parse_scan_output, daemon=True)
            self.parser_thread.start()
            
            logger.info("✓ BLE scanning active")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start BLE scan: {e}")
            return False
    
    def _parse_scan_output(self):
        """Parse hcitool lescan output"""
        try:
            logger.info("Parser thread started")
            
            # Pattern: MAC Address Name
            # Example: AA:BB:CC:DD:EE:FF MyDevice
            device_pattern = re.compile(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})\s+(.*)', re.IGNORECASE)
            
            for line in self.scan_process.stdout:
                if not self.running:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Skip header line
                if line.startswith('LE Scan'):
                    continue
                
                # Match device advertisement
                match = device_pattern.match(line)
                if match:
                    mac = match.group(1).upper()
                    name = match.group(2).strip()
                    
                    # Default name if empty
                    if not name or name == '(unknown)':
                        name = f"Unknown_{mac.replace(':', '')[-6:]}"
                    
                    with self.devices_lock:
                        # Update or add device
                        if mac not in self.devices:
                            logger.info(f"📱 Discovered: {name} ({mac})")
                            self.devices[mac] = {
                                'mac': mac,
                                'name': name,
                                'first_seen': datetime.now().isoformat(),
                                'last_seen': datetime.now().isoformat(),
                                'count': 1
                            }
                        else:
                            # Update existing device
                            self.devices[mac]['last_seen'] = datetime.now().isoformat()
                            self.devices[mac]['count'] += 1
                            
                            # Update name if we got a better one
                            if name != f"Unknown_{mac.replace(':', '')[-6:]}":
                                self.devices[mac]['name'] = name
                        
                        # Write updated device list to file
                        self._write_devices()
        
        except Exception as e:
            logger.error(f"Error parsing scan output: {e}")
    
    def _write_devices(self):
        """Write current device list to JSON file"""
        try:
            with open(self.scan_file, 'w') as f:
                json.dump({
                    'scan_started': min(d['first_seen'] for d in self.devices.values()) if self.devices else datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'device_count': len(self.devices),
                    'devices': list(self.devices.values())
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write device list: {e}")
    
    def get_devices(self):
        """Get current list of discovered devices"""
        with self.devices_lock:
            return list(self.devices.values())
    
    def stop_scan(self):
        """Stop BLE scanning"""
        self.running = False
        
        if self.scan_process:
            try:
                self.scan_process.terminate()
                self.scan_process.wait(timeout=5)
                logger.info("✓ BLE scan stopped")
            except Exception as e:
                logger.warning(f"Error stopping scan: {e}")
                try:
                    self.scan_process.kill()
                except:
                    pass
        
        # Stop hcitool
        try:
            subprocess.run(['sudo', 'killall', 'hcitool'], timeout=2)
        except:
            pass
        
        # Final write
        with self.devices_lock:
            if self.devices:
                self._write_devices()
                logger.info(f"Scan complete: {len(self.devices)} devices discovered")
    
    def run(self, duration=None):
        """
        Run the BLE scanner.
        
        Args:
            duration: Scan duration in seconds (None = run until interrupted)
        """
        # Set up signal handlers
        def signal_handler(signum, frame):
            logger.info("Received signal to stop...")
            self.stop_scan()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Enable Bluetooth
        if not self.enable_bluetooth():
            logger.error("Failed to enable Bluetooth - aborting")
            return 1
        
        # Start scanning
        if not self.start_scan():
            logger.error("Failed to start scan - aborting")
            return 1
        
        try:
            if duration:
                logger.info(f"Scanning for {duration} seconds...")
                time.sleep(duration)
            else:
                logger.info("Scanning until interrupted (Ctrl+C)...")
                while self.running:
                    time.sleep(1)
        finally:
            self.stop_scan()
        
        return 0


def main():
    parser = argparse.ArgumentParser(description='BLE device scanner for discovery')
    parser.add_argument('--duration', type=int, help='Scan duration in seconds (default: indefinite)')
    parser.add_argument('--output-dir', default='/var/log/isolator/ble', help='Output directory')
    
    args = parser.parse_args()
    
    scanner = BLEScanner(output_dir=args.output_dir)
    
    return scanner.run(duration=args.duration)


if __name__ == '__main__':
    sys.exit(main())
