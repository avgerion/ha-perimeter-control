        
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
