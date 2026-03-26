#!/usr/bin/env python3
"""
BLE Scanner v2 - Active Bluetooth device discovery using bluetoothctl

Uses bluetoothctl for BLE scanning (more reliable than hcitool on modern systems).
Performs active BLE scanning to discover nearby devices and their properties.

Output:
  - JSON file: /var/log/isolator/ble/scan_{timestamp}.json
  - Continuously updated while scanning

Usage:
    python3 ble-scanner-v2.py
    python3 ble-scanner-v2.py --duration 60
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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('ble-scanner')


class BLEScannerV2:
    """BLE scanner using bluetoothctl for device discovery"""
    
    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or '/var/log/isolator/ble')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.scan_file = self.output_dir / f"scan_{timestamp}.json"
        
        # Device cache: MAC -> device info
        self.devices = {}
        self.devices_lock = Lock()
        self.scan_start_time = datetime.now().isoformat()
        
        self.scan_process = None
        self.parser_thread = None
        self.running = False
        
        logger.info(f"BLE Scanner v2 initialized")
        logger.info(f"Output: {self.scan_file}")
        
        # Write initial empty file
        self._write_devices()
    
    def enable_bluetooth(self):
        """Enable Bluetooth and power on the controller"""
        try:
            # Power on the Bluetooth controller
            result = subprocess.run(
                ['sudo', 'bluetoothctl', 'power', 'on'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "Changing power on succeeded" in result.stdout or "power on" in result.stdout:
                logger.info("✓ Bluetooth powered on")
                return True
            else:
                logger.warning(f"Bluetooth power on: {result.stdout.strip()}")
                return True  # Might already be on
                
        except Exception as e:
            logger.error(f"Failed to enable Bluetooth: {e}")
            return False
    
    def start_scan(self):
        """Start BLE scanning with bluetoothctl"""
        try:
            logger.info("Starting BLE scan with bluetoothctl...")
            
            # Start bluetoothctl scan on
            self.scan_process = subprocess.Popen(
                ['sudo', 'bluetoothctl', 'scan', 'on'],
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
        """Parse bluetoothctl scan output"""
        try:
            logger.info("Parser thread started")
            
            # Pattern for device discovery: [NEW] Device MAC Name
            # Pattern for device changes: [CHG] Device MAC RSSI: -XX
            device_pattern = re.compile(r'\[(NEW|CHG)\]\s+Device\s+([0-9A-F:]{17})(?:\s+(.+))?', re.IGNORECASE)
            rssi_pattern = re.compile(r'RSSI:\s*(-?\d+)', re.IGNORECASE)
            
            for line in self.scan_process.stdout:
                if not self.running:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Debug: log all output lines
                logger.debug(f"BT Output: {line}")
                
                # Match device line
                match = device_pattern.search(line)
                if match:
                    event_type = match.group(1)  # NEW or CHG
                    mac = match.group(2).upper()
                    name = match.group(3).strip() if match.group(3) else None
                    
                    # Extract RSSI if present
                    rssi = None
                    rssi_match = rssi_pattern.search(line)
                    if rssi_match:
                        rssi = int(rssi_match.group(1))
                    
                    with self.devices_lock:
                        if mac not in self.devices:
                            # New device
                            device_name = name if name and name != mac else f"Unknown_{mac.replace(':', '')[-6:]}"
                            logger.info(f"📱 Discovered: {device_name} ({mac})")
                            
                            self.devices[mac] = {
                                'mac': mac,
                                'name': device_name,
                                'first_seen': datetime.now().isoformat(),
                                'last_seen': datetime.now().isoformat(),
                                'count': 1,
                                'rssi': rssi
                            }
                        else:
                            # Update existing device
                            self.devices[mac]['last_seen'] = datetime.now().isoformat()
                            self.devices[mac]['count'] += 1
                            
                            # Update name if we got a better one
                            if name and name != mac and not self.devices[mac]['name'].startswith('Unknown_'):
                                self.devices[mac]['name'] = name
                            
                            # Update RSSI
                            if rssi is not None:
                                self.devices[mac]['rssi'] = rssi
                        
                        # Write updated device list
                        self._write_devices()
        
        except Exception as e:
            logger.error(f"Error parsing scan output: {e}")
    
    def _write_devices(self):
        """Write current device list to JSON file"""
        try:
            data = {
                'scan_started': self.scan_start_time,
                'last_updated': datetime.now().isoformat(),
                'device_count': len(self.devices),
                'devices': list(self.devices.values())
            }
            
            with open(self.scan_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Wrote {len(self.devices)} devices to {self.scan_file}")
        except Exception as e:
            logger.error(f"Failed to write device list: {e}")
    
    def get_devices(self):
        """Get current list of discovered devices"""
        with self.devices_lock:
            return list(self.devices.values())
    
    def stop_scan(self):
        """Stop BLE scanning"""
        logger.info("Stopping BLE scan...")
        self.running = False
        
        if self.scan_process:
            try:
                # Stop bluetoothctl scan (might fail if already stopped)
                result = subprocess.run(
                    ['sudo', 'bluetoothctl', 'scan', 'off'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if "Failed to stop discovery" not in result.stdout and "Failed to stop discovery" not in result.stderr:
                    logger.info("✓ BLE scan stopped via bluetoothctl")
                
                self.scan_process.terminate()
                self.scan_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Scan process didn't terminate, killing...")
                try:
                    self.scan_process.kill()
                except:
                    pass
            except Exception as e:
                logger.warning(f"Error stopping scan (might be already stopped): {e}")
                try:
                    self.scan_process.kill()
                except:
                    pass
        
        # Final write (even if no devices found)
        with self.devices_lock:
            self._write_devices()
            logger.info(f"✓ Scan complete: {len(self.devices)} devices discovered")
            logger.info(f"✓ Results saved to: {self.scan_file}")
    
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
    parser = argparse.ArgumentParser(description='BLE device scanner using bluetoothctl')
    parser.add_argument('--duration', type=int, help='Scan duration in seconds (default: indefinite)')
    parser.add_argument('--output-dir', default='/var/log/isolator/ble', help='Output directory')
    
    args = parser.parse_args()
    
    scanner = BLEScannerV2(output_dir=args.output_dir)
    
    return scanner.run(duration=args.duration)


if __name__ == '__main__':
    sys.exit(main())
