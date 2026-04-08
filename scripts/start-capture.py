#!/usr/bin/env python3
"""
Start Packet Capture for a Device

This script is called when a new device connects to the AP.
It starts a tcpdump instance specific to that device's MAC address.

Usage:
    python3 start-capture.py --mac AA:BB:CC:DD:EE:FF --device-id my-camera

The capture service (isolator-capture@.service) will be started with the device ID.
"""


import argparse
import subprocess
import logging
import sys
from pathlib import Path
import os

# ---------------- Configurable Constants ----------------
SERVICE_TEMPLATE = os.environ.get('PERIMETERCONTROL_CAPTURE_SERVICE_TEMPLATE', 'perimetercontrol-capture@{mac}.service')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.start-capture')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


def normalize_mac(mac: str) -> str:
    """
    Normalize MAC address for use in systemd service name.
    
    Converts AA:BB:CC:DD:EE:FF to aa-bb-cc-dd-ee-ff
    """
    return mac.lower().replace(':', '-')


def start_capture(mac: str, device_id: str, enabled: bool = True):
    """Start packet capture service for a device"""
    
    if not enabled:
        logger.info(f"Capture disabled for {device_id}")
        return
    
    # Normalize MAC for service name
    mac_normalized = normalize_mac(mac)
    service_name = SERVICE_TEMPLATE.format(mac=mac_normalized)
    
    logger.info(f"Starting capture for {device_id} (MAC: {mac})")
    
    try:
        # Check if already running
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip() == 'active':
            logger.info(f"Capture already running for {device_id}")
            return
        
        # Start the service
        subprocess.run(
            ['systemctl', 'start', service_name],
            check=True,
            capture_output=True
        )
        
        logger.info(f"✓ Started capture service: {service_name}")
        logger.info(f"  Captures will be saved to: /mnt/isolator/captures/{mac_normalized}/")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start capture: {e.stderr.decode()}")
        sys.exit(1)


def stop_capture(mac: str, device_id: str):
    """Stop packet capture service for a device"""
    
    mac_normalized = normalize_mac(mac)
    service_name = f"isolator-capture@{mac_normalized}.service"
    
    logger.info(f"Stopping capture for {device_id} (MAC: {mac})")
    
    try:
        subprocess.run(
            ['systemctl', 'stop', service_name],
            check=True,
            capture_output=True
        )
        
        logger.info(f"✓ Stopped capture service: {service_name}")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop capture: {e.stderr.decode()}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Manage packet capture for devices')
    parser.add_argument('--mac', required=True, help='MAC address of device (AA:BB:CC:DD:EE:FF)')
    parser.add_argument('--device-id', required=True, help='Device identifier')
    parser.add_argument('--action', choices=['start', 'stop'], default='start', help='Action to perform')
    parser.add_argument('--enabled', action='store_true', default=True, help='Whether capture is enabled')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        start_capture(args.mac, args.device_id, args.enabled)
    elif args.action == 'stop':
        stop_capture(args.mac, args.device_id)


if __name__ == '__main__':
    main()
