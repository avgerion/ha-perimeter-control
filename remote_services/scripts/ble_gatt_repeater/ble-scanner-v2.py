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
import os

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("ERROR: bleak not installed. Run: pip install bleak", file=sys.stderr)
    sys.exit(1)

# ---------------- Configurable Constants ----------------
LOG_ROOT = os.environ.get('PERIMETERCONTROL_BLE_LOG_ROOT', '/var/log/PerimeterControl/ble')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.ble-scanner')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


class BLEScannerV2:
    """BLE-only scanner using bleak (BlueZ D-Bus). Works non-interactively."""

    def __init__(self, output_dir=None):
        self.output_dir = Path(output_dir or LOG_ROOT)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.scan_file = self.output_dir / f"scan_{timestamp}.json"
        self.scan_start_time = datetime.now().isoformat()

        # MAC -> device record
        self.devices: dict = {}

        logger.info("BLE Scanner v2 (bleak) initialized")
        logger.info(f"Output: {self.scan_file}")

    @staticmethod
    def _serialize_adv(adv: AdvertisementData) -> dict:
        mfr = {str(k): v.hex() for k, v in adv.manufacturer_data.items()} if adv.manufacturer_data else {}
        svc = {k: v.hex() for k, v in adv.service_data.items()} if adv.service_data else {}
        return {
            'manufacturer_data': mfr,
            'service_data':      svc,
            'service_uuids':     list(adv.service_uuids or []),
            'local_name':        adv.local_name,
            'tx_power':          adv.tx_power,
        }

    def _detection_callback(self, device: BLEDevice, adv: AdvertisementData):
        mac = device.address.upper()
        name = device.name or adv.local_name or f"Unknown_{mac.replace(':', '')[-6:]}"
        rssi = adv.rssi
        tx_power = adv.tx_power
        phy = "LE 1M"
        adv_fields = self._serialize_adv(adv)

        if mac not in self.devices:
            logger.info(f"Discovered: {name} ({mac})  RSSI={rssi}  PHY={phy}")
            self.devices[mac] = {
                'mac': mac,
                'name': name,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'count': 1,
                'rssi': rssi,
                'tx_power': tx_power,
                'phy': phy,
                'adv_data': adv_fields,
            }
        else:
            self.devices[mac]['last_seen'] = datetime.now().isoformat()
            self.devices[mac]['count'] += 1
            self.devices[mac]['rssi'] = rssi
            self.devices[mac]['adv_data'] = adv_fields
            if tx_power is not None:
                self.devices[mac]['tx_power'] = tx_power
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
        # BlueZ caches discovered devices and stops emitting callbacks for
        # already-known devices.  Restarting the scanner every CYCLE seconds
        # forces BlueZ to flush its cache and re-report all advertisements.
        CYCLE = 25.0

        stop_event = asyncio.Event()

        def _sig(*_):
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _sig)

        async def _periodic_write_loop():
            while not stop_event.is_set():
                await asyncio.sleep(5)
                if not stop_event.is_set() and self.devices:
                    self._write_devices()

        writer_task = asyncio.create_task(_periodic_write_loop())

        start = time.monotonic()
        cycle_num = 0
        while not stop_event.is_set():
            elapsed = time.monotonic() - start
            if elapsed >= duration:
                break
            segment = min(CYCLE, duration - elapsed)
            cycle_num += 1
            logger.info(f"BLE scan cycle {cycle_num} starting ({elapsed:.0f}s elapsed, {segment:.0f}s segment)")
            async with BleakScanner(
                detection_callback=self._detection_callback,
                scanning_mode="active",
            ):
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=segment)
                    break  # stop signal
                except asyncio.TimeoutError:
                    pass  # segment done; restart scanner on next iteration

        stop_event.set()
        writer_task.cancel()
        try:
            await writer_task
        except asyncio.CancelledError:
            pass

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
