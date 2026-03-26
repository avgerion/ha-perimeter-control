#!/usr/bin/env python3
"""
BLE Scanner v2 - Active Bluetooth LE device discovery using bleak

Uses bleak (BlueZ D-Bus) for LE-only scanning. Works correctly when
launched non-interactively (unlike bluetoothctl piped stdout).

Output:
  - JSON file: /var/log/isolator/ble/scan_{timestamp}.json
  - Written once on completion

Usage:
    python3 ble-scanner-v2.py
    python3 ble-scanner-v2.py --duration 60
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("ERROR: bleak not installed. Run: pip install bleak", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('ble-scanner')


class BLEScannerV2:
    """BLE-only scanner using bleak (BlueZ D-Bus). Works non-interactively."""

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or '/var/log/isolator/ble')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.scan_file = self.output_dir / f"scan_{timestamp}.json"
        self.scan_start_time = datetime.now().isoformat()

        # MAC -> device record
        self.devices: dict = {}

        logger.info("BLE Scanner v2 (bleak) initialized")
        logger.info(f"Output: {self.scan_file}")

    def _detection_callback(self, device: BLEDevice, adv: AdvertisementData):
        mac = device.address.upper()
        name = device.name or f"Unknown_{mac.replace(':', '')[-6:]}"
        rssi = adv.rssi

        if mac not in self.devices:
            logger.info(f"Discovered: {name} ({mac})  RSSI={rssi}")
            self.devices[mac] = {
                'mac': mac,
                'name': name,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'count': 1,
                'rssi': rssi,
            }
        else:
            self.devices[mac]['last_seen'] = datetime.now().isoformat()
            self.devices[mac]['count'] += 1
            self.devices[mac]['rssi'] = rssi
            # Prefer a real name over Unknown_ placeholder
            if device.name and self.devices[mac]['name'].startswith('Unknown_'):
                self.devices[mac]['name'] = device.name

    def _write_devices(self):
        data = {
            'scan_started': self.scan_start_time,
            'last_updated': datetime.now().isoformat(),
            'device_count': len(self.devices),
            'devices': list(self.devices.values()),
        }
        with open(self.scan_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Wrote {len(self.devices)} devices to {self.scan_file}")

    async def _run_async(self, duration: float):
        stop_event = asyncio.Event()

        def _sig(*_):
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _sig)

        async with BleakScanner(
            detection_callback=self._detection_callback,
            scanning_mode="active",   # LE active scan (requests scan-response packets)
        ):
            logger.info(f"Scanning BLE for {duration}s ...")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=duration)
                logger.info("Scan stopped by signal.")
            except asyncio.TimeoutError:
                logger.info(f"Scan duration ({duration}s) elapsed.")

        self._write_devices()
        logger.info(f"Scan complete: {len(self.devices)} device(s) found.")

    def run(self, duration: float = 30.0) -> int:
        try:
            asyncio.run(self._run_async(duration))
            return 0
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            return 1


def main():
    parser = argparse.ArgumentParser(description='BLE-only device scanner (bleak)')
    parser.add_argument('--duration', type=float, default=30.0,
                        help='Scan duration in seconds (default: 30)')
    parser.add_argument('--output-dir', default='/var/log/isolator/ble',
                        help='Output directory')
    args = parser.parse_args()

    scanner = BLEScannerV2(output_dir=args.output_dir)
    return scanner.run(duration=args.duration)


if __name__ == '__main__':
    sys.exit(main())
