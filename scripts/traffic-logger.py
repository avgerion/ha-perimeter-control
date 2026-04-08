#!/usr/bin/env python3
"""
Traffic Logger - Monitors kernel netfilter logs and writes to device-specific files

Reads nftables log messages from journalctl and writes them to per-device log files
in /var/log/isolator/devices/{device_id}.log

Log format (JSON):
{
    "timestamp": "2026-03-26T14:52:30.123456",
    "device_id": "moto-g-2025",
    "action": "ALLOWED|BLOCKED",
    "protocol": "TCP|UDP|ICMP",
    "src_ip": "192.168.111.153",
    "dst_ip": "8.8.8.8",
    "src_port": 54321,
    "dst_port": 443,
    "bytes": 1234
}

Usage:
    python3 traffic-logger.py --config /path/to/isolator.conf.yaml
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
from typing import Dict, Optional
import yaml
import os

# ---------------- Configurable Constants ----------------
LOG_ROOT = os.environ.get('PERIMETERCONTROL_DEVICE_LOG_ROOT', '/var/log/PerimeterControl/devices')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.traffic-logger')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


class TrafficLogger:
    """Parse netfilter logs and write to per-device files"""
    
    def __init__(self, config_path: Path, log_dir: Path = None):
        self.config_path = config_path
        self.log_dir = Path(log_dir or LOG_ROOT)
        self.config = self._load_config()
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Device logs directory: {self.log_dir}")
        
        # Pattern to match nftables log messages
        # Example: IN=wlan0 OUT=eth0 ... SRC=192.168.111.153 DST=8.8.8.8 ... PROTO=TCP SPT=54321 DPT=443
        self.log_pattern = re.compile(
            r'(?P<prefix>DEVICE-(?P<device_id>[^\s:]+)|BLOCKED-(?P<blocked_device>[^\s:]+)|UNKNOWN-DEVICE):\s+'
            r'.*?'
            r'SRC=(?P<src_ip>[\d.]+)\s+'
            r'DST=(?P<dst_ip>[\d.]+)\s+'
            r'.*?'
            r'PROTO=(?P<protocol>\w+)'
            r'(?:.*?SPT=(?P<src_port>\d+))?'
            r'(?:.*?DPT=(?P<dst_port>\d+))?'
            r'(?:.*?LEN=(?P<len>\d+))?'
        )
    
    def _load_config(self) -> dict:
        """Load configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def _parse_log_line(self, line: str, timestamp: str) -> Optional[Dict]:
        """Parse a netfilter log line"""
        
        match = self.log_pattern.search(line)
        if not match:
            return None
        
        # Determine device ID and action
        device_id = match.group('device_id') or match.group('blocked_device')
        if not device_id:
            device_id = 'unknown'
        
        # Determine action (ALLOWED vs BLOCKED)
        if'BLOCKED' in match.group('prefix'):
            action = 'BLOCKED'
        else:
            action = 'ALLOWED'
        
        # Extract connection details
        entry = {
            'timestamp': timestamp,
            'device_id': device_id,
            'action': action,
            'protocol': match.group('protocol'),
            'src_ip': match.group('src_ip'),
            'dst_ip': match.group('dst_ip'),
            'src_port': int(match.group('src_port')) if match.group('src_port') else None,
            'dst_port': int(match.group('dst_port')) if match.group('dst_port') else None,
            'bytes': int(match.group('len')) if match.group('len') else None
        }
        
        return entry
    
    def _write_log_entry(self, entry: Dict):
        """Write log entry to device-specific file"""
        
        device_id = entry['device_id']
        log_file = self.log_dir / f"{device_id}.log"
        
        try:
            # Append JSON line to device log file
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write log for {device_id}: {e}")
    
    def _rotate_logs(self):
        """Rotate log files if they exceed size limit"""
        
        max_size_mb = self.config.get('logging', {}).get('rotate_mb', 50)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        for log_file in self.log_dir.glob('*.log'):
            try:
                if log_file.stat().st_size > max_size_bytes:
                    # Rotate: move current log to .1, .1 to .2, etc.
                    rotate_file = log_file.with_suffix('.log.1')
                    if rotate_file.exists():
                        rotate_file.unlink()
                    log_file.rename(rotate_file)
                    logger.info(f"Rotated log file: {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to rotate {log_file.name}: {e}")
    
    def monitor(self):
        """Monitor kernel logs for netfilter messages"""
        
        logger.info("Starting traffic logger...")
        logger.info(f"Monitoring netfilter logs from kernel")
        
        # Follow journalctl for kernel messages with nftables logs
        cmd = [
            'journalctl',
            '-kf',  # Follow kernel logs
            '--no-pager',
            '-o', 'short-iso'  # ISO timestamp format
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            logger.info("Monitoring kernel logs (press Ctrl+C to stop)...")
            
            rotate_counter = 0
            for line in process.stdout:
                # Extract timestamp from journalctl output
                # Format: "2026-03-26T14:52:30+0000 hostname kernel: ..."
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    log_content = parts[3]
                    
                    # Check if this is a netfilter log message
                    if 'DEVICE-' in log_content or 'BLOCKED-' in log_content or 'UNKNOWN-DEVICE' in log_content:
                        entry = self._parse_log_line(log_content, timestamp)
                        
                        if entry:
                            self._write_log_entry(entry)
                            
                            # Log summary (not every packet, just important ones)
                            if entry['action'] == 'BLOCKED':
                                logger.info(f"🔴 {entry['device_id']}: BLOCKED {entry['protocol']} {entry['src_ip']} → {entry['dst_ip']}:{entry['dst_port']}")
                
                # Rotate logs periodically (every 1000 lines checked)
                rotate_counter += 1
                if rotate_counter >= 1000:
                    self._rotate_logs()
                    rotate_counter = 0
            
        except KeyboardInterrupt:
            logger.info("Stopping traffic logger...")
            process.terminate()
        except Exception as e:
            logger.error(f"Error monitoring logs: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description='Monitor netfilter logs and write to device files')
    parser.add_argument('--config', default='/mnt/isolator/conf/isolator.conf.yaml', help='Path to config file')
    parser.add_argument('--log-dir', default='/var/log/isolator/devices', help='Directory for device log files')
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    log_dir = Path(args.log_dir)
    
    logger_instance = TrafficLogger(config_path, log_dir)
    logger_instance.monitor()


if __name__ == '__main__':
    main()
