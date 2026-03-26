#!/usr/bin/env python3
"""
BLE Sniffer - Captures Bluetooth Low Energy traffic for reverse engineering

Monitors BLE advertisements, connections, and data exchanges using btmon.
Captures all HCI (Host Controller Interface) traffic including:
  - BLE advertisements
  - Connection requests
  - Pairing/bonding
  - GATT service discovery
  - Characteristic reads/writes

Output formats:
  - Raw btmon log: /mnt/isolator/captures/ble/{target_name}.btsnoop
  - Human-readable: /var/log/isolator/ble/{target_name}.log
  - JSON structured: /var/log/isolator/ble/{target_name}.json

Usage:
    python3 ble-sniffer.py --target "DeviceName" --duration 300
    python3 ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF
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
from threading import Thread
import signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('ble-sniffer')


class BLESniffer:
    """Captures and parses BLE traffic using btmon"""
    
    def __init__(self, target_name=None, target_mac=None, output_dir=None):
        self.target_name = target_name
        self.target_mac = target_mac.lower() if target_mac else None
        self.output_dir = Path(output_dir or '/mnt/isolator/captures/ble')
        self.log_dir = Path('/var/log/isolator/ble')
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_slug = (target_name or target_mac or 'unknown').replace(':', '_').replace(' ', '_')
        self.btsnoop_file = self.output_dir / f"{target_slug}_{timestamp}.btsnoop"
        self.log_file = self.log_dir / f"{target_slug}_{timestamp}.log"
        self.json_file = self.log_dir / f"{target_slug}_{timestamp}.json"
        
        self.btmon_process = None
        self.parser_thread = None
        self.running = False
        
        logger.info(f"BLE Sniffer initialized for target: {target_name or target_mac or 'ANY'}")
        logger.info(f"Output files:")
        logger.info(f"  - btsnoop: {self.btsnoop_file}")
        logger.info(f"  - log: {self.log_file}")
        logger.info(f"  - json: {self.json_file}")
    
    def enable_bluetooth(self):
        """Enable Bluetooth interface"""
        try:
            # Bring up hci0
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=True, timeout=5)
            logger.info("✓ Bluetooth interface hci0 enabled")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to enable Bluetooth: {e}")
            return False
        except Exception as e:
            logger.error(f"Error enabling Bluetooth: {e}")
            return False
    
    def start_scan(self):
        """Start BLE scanning to discover devices"""
        try:
            # Start passive BLE scan
            subprocess.Popen(
                ['sudo', 'hcitool', 'lescan', '--duplicates'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info("✓ BLE scanning started")
        except Exception as e:
            logger.warning(f"Could not start BLE scan: {e}")
    
    def start_capture(self):
        """Start btmon capture"""
        if not self.enable_bluetooth():
            return False
        
        # Start BLE scanning in background
        self.start_scan()
        
        # Start btmon with btsnoop output
        cmd = [
            'sudo', 'btmon',
            '--write', str(self.btsnoop_file)
        ]
        
        try:
            self.btmon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.running = True
            logger.info("✓ btmon capture started")
            
            # Start parser thread to process btmon output
            self.parser_thread = Thread(target=self._parse_btmon_output)
            self.parser_thread.daemon = True
            self.parser_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start btmon: {e}")
            return False
    
    def _parse_btmon_output(self):
        """Parse btmon output in real-time"""
        
        log_handle = open(self.log_file, 'a')
        json_handle = open(self.json_file, 'a')
        
        current_packet = {}
        
        try:
            for line in self.btmon_process.stdout:
                if not self.running:
                    break
                
                # Write raw line to log
                log_handle.write(line)
                log_handle.flush()
                
                # Parse interesting events
                line = line.strip()
                
                # BLE Advertisement
                if 'LE Advertising Report' in line or 'ADV_IND' in line:
                    if current_packet:
                        self._write_json_event(json_handle, current_packet)
                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'advertisement',
                        'data': {}
                    }
                
                # Device address
                elif 'Address:' in line:
                    addr_match = re.search(r'Address:\s+([0-9A-Fa-f:]+)', line)
                    if addr_match:
                        addr = addr_match.group(1).lower()
                        current_packet['data']['address'] = addr
                        
                        # Filter by target MAC if specified
                        if self.target_mac and addr != self.target_mac:
                            current_packet = {}  # Discard
                
                # Device name
                elif 'Name:' in line or 'Complete local name:' in line:
                    name_match = re.search(r'(?:Name|Complete local name):\s+(.+)', line)
                    if name_match:
                        name = name_match.group(1).strip()
                        current_packet['data']['name'] = name
                        logger.info(f"📱 Found device: {name}")
                
                # GATT operations
                elif 'ATT:' in line or 'Read Request' in line or 'Write Request' in line:
                    if 'Read Request' in line:
                        current_packet['type'] = 'gatt_read'
                    elif 'Write Request' in line:
                        current_packet['type'] = 'gatt_write'
                    
                    # Extract handle
                    handle_match = re.search(r'Handle:\s+0x([0-9a-f]+)', line, re.IGNORECASE)
                    if handle_match:
                        current_packet['data']['handle'] = handle_match.group(1)
                
                # Connection events
                elif 'LE Connection Complete' in line:
                    if current_packet:
                        self._write_json_event(json_handle, current_packet)
                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'connection',
                        'data': {}
                    }
                    logger.info("🔗 BLE connection established")
                
        except Exception as e:
            logger.error(f"Error parsing btmon output: {e}")
        finally:
            if current_packet:
                self._write_json_event(json_handle, current_packet)
            log_handle.close()
            json_handle.close()
    
    def _write_json_event(self, handle, event):
        """Write JSON event to file"""
        if event and event.get('data'):
            try:
                handle.write(json.dumps(event) + '\n')
                handle.flush()
            except Exception as e:
                logger.warning(f"Failed to write JSON event: {e}")
    
    def stop_capture(self):
        """Stop btmon capture"""
        self.running = False
        
        if self.btmon_process:
            try:
                self.btmon_process.terminate()
                self.btmon_process.wait(timeout=5)
                logger.info("✓ btmon capture stopped")
            except Exception as e:
                logger.warning(f"Error stopping btmon: {e}")
                try:
                    self.btmon_process.kill()
                except:
                    pass
        
        # Wait for parser thread
        if self.parser_thread and self.parser_thread.is_alive():
            self.parser_thread.join(timeout=2)
        
        # Stop BLE scan
        try:
            subprocess.run(['sudo', 'killall', 'hcitool'], timeout=2)
        except:
            pass
        
        logger.info(f"Capture complete. Files saved:")
        logger.info(f"  - {self.btsnoop_file}")
        logger.info(f"  - {self.log_file}")
        logger.info(f"  - {self.json_file}")
    
    def run(self, duration=None):
        """Run capture for specified duration (seconds) or until interrupted"""
        
        if not self.start_capture():
            return 1
        
        def signal_handler(sig, frame):
            logger.info("Interrupt received, stopping capture...")
            self.stop_capture()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            if duration:
                logger.info(f"Capturing for {duration} seconds (press Ctrl+C to stop early)...")
                time.sleep(duration)
            else:
                logger.info("Capturing indefinitely (press Ctrl+C to stop)...")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_capture()
        
        return 0


def main():
    parser = argparse.ArgumentParser(description='BLE sniffer for IoT device reverse engineering')
    parser.add_argument('--target', help='Target device name to filter')
    parser.add_argument('--target-mac', help='Target device MAC address to filter')
    parser.add_argument('--duration', type=int, help='Capture duration in seconds (default: indefinite)')
    parser.add_argument('--output-dir', default='/mnt/isolator/captures/ble', help='Output directory for captures')
    
    args = parser.parse_args()
    
    if not args.target and not args.target_mac:
        logger.warning("No target specified - will capture ALL BLE traffic")
    
    sniffer = BLESniffer(
        target_name=args.target,
        target_mac=args.target_mac,
        output_dir=args.output_dir
    )
    
    return sniffer.run(duration=args.duration)


if __name__ == '__main__':
    sys.exit(main())
