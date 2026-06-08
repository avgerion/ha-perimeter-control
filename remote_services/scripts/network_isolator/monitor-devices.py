import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

logger = logging.getLogger("monitor-devices")
logging.basicConfig(level=logging.INFO)

CAPTURE_SCRIPT = os.environ.get(
    "CAPTURE_SCRIPT",
    str(Path(__file__).parent / "capture-device.py")
)


class DeviceMonitor:
    def __init__(self, config_path: Path):
        # Minimal initializer: load known devices map and active set
        self.config = {}
        self.known_devices = {}
        self.active_macs = set()
        try:
            import yaml
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
                self.known_devices = {d.get('mac'): d.get('id') for d in self.config.get('known_devices', [])}
        except Exception:
            logger.warning("Failed to load config, proceeding with defaults")

    def _get_active_leases(self) -> Dict[str, Dict]:
        # Placeholder: in real code this would parse dnsmasq leases
        return {}

    def _start_capture_for_device(self, mac: str, device_id: str, capture_enabled: bool = True):
        if not capture_enabled:
            logger.info(f"Capture disabled for {device_id} ({mac})")
            return

        # Start capture using helper script
        try:
            subprocess.run([
                'python3', CAPTURE_SCRIPT,
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
        ip = lease_info.get('ip')
        hostname = lease_info.get('hostname')

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
                'python3', CAPTURE_SCRIPT,
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
    parser.add_argument('--config', default=os.environ.get('PERIMETERCONTROL_CONFIG', '/mnt/PerimeterControl/conf/perimeterControl.conf.yaml'), help='Path to config file')
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
