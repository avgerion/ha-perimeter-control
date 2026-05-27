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
  - Raw btmon log:      /var/log/isolator/ble/{target}.raw.log   (all btmon lines)
  - Human-readable:     /var/log/isolator/ble/{target}.log
  - JSON structured:    /var/log/isolator/ble/{target}.json
  - btsnoop binary:     /mnt/isolator/captures/ble/{target}.btsnoop

Usage:
    python3 ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF
    python3 ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF --debug          # verbose
    python3 ble-sniffer.py --target-mac AA:BB:CC:DD:EE:FF --no-filter      # capture all
    python3 ble-sniffer.py --target "DeviceName" --duration 300

Debugging:
    # Watch raw btmon output live:
    tail -f /var/log/isolator/ble/*.raw.log
    # Watch parsed events live:
    tail -f /var/log/isolator/ble/*.log
    # Count JSON events:
    wc -l /var/log/isolator/ble/*.json
"""


import argparse
import json
import logging
import os
import pty
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
import signal

# ---------------- Configurable Constants ----------------
LOG_ROOT = os.environ.get('PERIMETERCONTROL_BLE_LOG_ROOT', '/var/log/PerimeterControl/ble')
CAPTURE_ROOT = os.environ.get('PERIMETERCONTROL_BLE_CAPTURE_ROOT', '/mnt/PerimeterControl/captures/ble')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.ble-sniffer')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


class BLESniffer:
    """Captures and parses BLE traffic using btmon.

    Key design choices:
    - btmon stdout is read via a PTY (pseudo-terminal) so btmon uses line
      buffering instead of block buffering when its output is piped.
    - btmon stderr is drained by a background thread to prevent pipe deadlock.
    - All raw btmon lines are written to .raw.log regardless of filter setting.
    - When --debug is set, every raw line is also emitted to the Python logger.
    - When --no-filter is set, ALL addresses are captured (useful for debugging).
    """


    def __init__(self, target_name=None, target_mac=None, output_dir=None,
                 debug=False, no_filter=False):
        self.target_name = target_name
        self.target_mac = target_mac.upper() if target_mac else None
        self.output_dir = Path(output_dir or CAPTURE_ROOT)
        self.log_dir = Path(LOG_ROOT)
        self.debug = debug
        self.no_filter = no_filter

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Generate filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_slug = (
            (target_name or target_mac or 'unknown')
            .replace(':', '_').replace(' ', '_')
        )
        self.btsnoop_file = self.output_dir / f"{target_slug}_{timestamp}.btsnoop"
        self.log_file    = self.log_dir / f"{target_slug}_{timestamp}.log"
        self.json_file   = self.log_dir / f"{target_slug}_{timestamp}.json"
        self.raw_log_file = self.log_dir / f"{target_slug}_{timestamp}.raw.log"

        self.btmon_process = None
        self._btmon_stdout_fd = None   # PTY master fd
        self.parser_thread = None
        self._stderr_thread = None
        self._heartbeat_thread = None
        self.running = False

        # Stats
        self._raw_lines = 0
        self._events_written = 0
        self._events_discarded = 0
        self._scan_proc = None

        logger.info("=" * 60)
        logger.info(f"BLE Sniffer starting")
        logger.info(f"  Target     : {target_name or target_mac or 'ANY (no filter)'}")
        logger.info(f"  Debug mode : {debug}")
        logger.info(f"  No-filter  : {no_filter}")
        logger.info(f"  btsnoop    : {self.btsnoop_file}")
        logger.info(f"  raw log    : {self.raw_log_file}")
        logger.info(f"  human log  : {self.log_file}")
        logger.info(f"  JSON events: {self.json_file}")
        logger.info("=" * 60)

    # ── Bluetooth activation ─────────────────────────────────────────────────

    def enable_bluetooth(self):
        """Bring up hci0 and confirm it is ready."""
        try:
            r = subprocess.run(
                ['sudo', 'hciconfig', 'hci0', 'up'],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                logger.info("✓ hci0 brought up (hciconfig hci0 up)")
            else:
                logger.warning(f"hciconfig hci0 up returned {r.returncode}: {r.stderr.strip()}")
        except Exception as e:
            logger.error(f"enable_bluetooth: hciconfig failed: {e}")

        # Confirm adapter is UP
        try:
            r = subprocess.run(
                ['hciconfig', 'hci0'],
                capture_output=True, text=True, timeout=3
            )
            if 'UP RUNNING' in r.stdout:
                logger.info("✓ hci0 is UP RUNNING")
                return True
            elif 'hci0' in r.stdout:
                logger.warning(f"hci0 found but not UP RUNNING: {r.stdout.strip()[:120]}")
                return True   # proceed anyway; btmon may still work
            else:
                logger.error("hci0 not found in hciconfig output")
                return False
        except Exception as e:
            logger.error(f"hciconfig check failed: {e}")
            return False

    def start_scan(self):
        """Activate LE scanning so that btmon sees advertising events.

        Tries modern btmgmt first, then falls back to hcitool lescan.
        Both approaches are tried so we get best coverage regardless of
        BlueZ version on the Pi.
        """
        # --- Method 1: btmgmt (BlueZ 5.x, preferred) ---
        if shutil.which('btmgmt'):
            try:
                for cmd_args in [
                    ['sudo', 'btmgmt', '--index', '0', 'power', 'on'],
                    ['sudo', 'btmgmt', '--index', '0', 'le', 'on'],
                    ['sudo', 'btmgmt', '--index', '0', 'discov', 'on'],
                ]:
                    r = subprocess.run(
                        cmd_args, capture_output=True, text=True, timeout=4
                    )
                    logger.debug(
                        f"btmgmt {cmd_args[3:]}: rc={r.returncode} "
                        f"stdout={r.stdout.strip()[:80]} stderr={r.stderr.strip()[:80]}"
                    )
                logger.info("✓ btmgmt scan commands issued")
            except Exception as e:
                logger.warning(f"btmgmt scan failed: {e}")
        else:
            logger.warning("btmgmt not found — skipping modern scan activation")

        # --- Method 2: hcitool lescan (legacy fallback) ---
        # Still needed on older kernels / BlueZ versions.
        try:
            proc = subprocess.Popen(
                ['sudo', 'hcitool', 'lescan', '--duplicates'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._scan_proc = proc
            # Give it 1s to start
            time.sleep(1)
            if proc.poll() is None:
                logger.info(f"✓ hcitool lescan running (PID {proc.pid})")
            else:
                stderr = proc.stderr.read().decode('utf-8', errors='ignore')
                logger.warning(f"hcitool lescan exited early: {stderr[:120]}")
                self._scan_proc = None
        except Exception as e:
            logger.warning(f"hcitool lescan failed: {e} (may be OK if btmgmt worked)")
            self._scan_proc = None

    # ── btmon capture ─────────────────────────────────────────────────────────

    def start_capture(self):
        """Start btmon capture via PTY to avoid pipe output buffering."""
        if not self.enable_bluetooth():
            return False

        self.start_scan()

        # Build btmon command.
        # Use stdbuf if available (belt-and-suspenders with PTY).
        use_stdbuf = shutil.which('stdbuf') is not None
        if use_stdbuf:
            cmd = ['stdbuf', '-oL', '-eL',
                   'sudo', 'btmon', '--write', str(self.btsnoop_file)]
            logger.info("Using stdbuf -oL for line-buffered btmon output")
        else:
            cmd = ['sudo', 'btmon', '--write', str(self.btsnoop_file)]
            logger.warning("stdbuf not found — using PTY only for line buffering")

        logger.info(f"btmon command: {' '.join(cmd)}")

        try:
            # Open a PTY pair so btmon thinks stdout is a terminal and uses
            # line buffering instead of block buffering.
            master_fd, slave_fd = pty.openpty()

            self.btmon_process = subprocess.Popen(
                cmd,
                stdout=slave_fd,
                stderr=subprocess.PIPE,
                close_fds=True,
            )
            os.close(slave_fd)          # Parent does not need the slave end
            self._btmon_stdout_fd = master_fd

            self.running = True

            # Give btmon a moment to start
            time.sleep(0.5)
            poll = self.btmon_process.poll()
            if poll is not None:
                # btmon exited immediately
                stderr_bytes = self.btmon_process.stderr.read()
                stderr_text = stderr_bytes.decode('utf-8', errors='ignore')
                logger.error(
                    f"btmon exited immediately (rc={poll}). stderr: {stderr_text[:400]}"
                )
                os.close(master_fd)
                self.running = False
                return False

            logger.info(f"✓ btmon started (PID {self.btmon_process.pid})")

            # Stderr reader thread (prevents pipe deadlock)
            self._stderr_thread = Thread(
                target=self._drain_stderr, name='btmon-stderr', daemon=True
            )
            self._stderr_thread.start()

            # Main parser thread
            self.parser_thread = Thread(
                target=self._parse_btmon_output, name='btmon-parser', daemon=True
            )
            self.parser_thread.start()

            # Heartbeat thread
            self._heartbeat_thread = Thread(
                target=self._heartbeat, name='btmon-heartbeat', daemon=True
            )
            self._heartbeat_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to start btmon: {e}", exc_info=True)
            return False

    def _drain_stderr(self):
        """Read btmon stderr and log it. Prevents stderr pipe from filling up."""
        try:
            for raw_line in self.btmon_process.stderr:
                line = raw_line.decode('utf-8', errors='replace').rstrip()
                if line:
                    logger.info(f"[btmon stderr] {line}")
        except Exception as e:
            logger.debug(f"_drain_stderr ended: {e}")

    def _heartbeat(self):
        """Log stats every 10 s so we can see if the sniffer is alive."""
        while self.running:
            time.sleep(10)
            if not self.running:
                break
            alive = self.btmon_process and self.btmon_process.poll() is None
            btsnoop_sz = 0
            try:
                btsnoop_sz = self.btsnoop_file.stat().st_size
            except Exception:
                pass
            logger.info(
                f"[heartbeat] btmon_alive={alive} "
                f"raw_lines={self._raw_lines} "
                f"events_written={self._events_written} "
                f"events_discarded={self._events_discarded} "
                f"btsnoop_size={btsnoop_sz}B "
                f"json_file={self.json_file.name}"
            )
            if not alive and self.running:
                rc = self.btmon_process.returncode if self.btmon_process else 'N/A'
                logger.error(
                    f"btmon process has exited (rc={rc}) while sniffer is "
                    f"still supposed to be running! No new events will be captured."
                )

    # ── btmon output parser ────────────────────────────────────────────────────

    def _parse_btmon_output(self):
        """Read btmon output from the PTY master fd and parse HCI events."""
        raw_handle = None
        log_handle = None
        json_handle = None

        try:
            raw_handle  = open(self.raw_log_file, 'a', buffering=1)
            log_handle  = open(self.log_file, 'a', buffering=1)
            json_handle = open(self.json_file, 'a', buffering=1)

            # Wrap the PTY master fd as a text stream
            pty_stream = os.fdopen(self._btmon_stdout_fd, 'r',
                                   encoding='utf-8', errors='replace')

            current_packet = {}   # accumulates fields for the current HCI event
            active_mac = None     # MAC address of the event being assembled

            for raw_line in pty_stream:
                if not self.running:
                    break

                self._raw_lines += 1

                # Always write raw line to .raw.log
                raw_handle.write(raw_line)

                if self.debug:
                    logger.debug(f"[raw] {raw_line.rstrip()}")

                line = raw_line.strip()
                if not line:
                    continue

                # ── Human-readable log (mirrors old .log behaviour) ───
                log_handle.write(raw_line)

                # Keep compact raw line context for the current packet.
                if current_packet:
                    rl = current_packet.setdefault('raw_lines', [])
                    if len(rl) < 80:
                        rl.append(line)

                # ── Event boundary detection ─────────────────────────

                hci_boundary = re.match(r'^[<>]\s+HCI\s+(Event|Command):', line)
                mgmt_boundary = re.match(r'^[@]\s+MGMT\s+(Event|Command):', line)
                if hci_boundary or mgmt_boundary:
                    self._flush_packet(json_handle, current_packet)

                    if hci_boundary:
                        pkt_type = 'hci_event' if line.startswith('>') else 'hci_command'
                    else:
                        pkt_type = 'mgmt_event' if 'Event' in line else 'mgmt_command'

                    lower = line.lower()
                    if 'le advertising report' in lower or 'adv_' in lower or 'scan_rsp' in lower:
                        pkt_type = 'advertisement'
                    elif 'le enhanced connection complete' in lower or 'le connection complete' in lower:
                        pkt_type = 'connection'
                    elif 'disconnection complete' in lower:
                        pkt_type = 'disconnection'
                    elif 'att read by type' in lower:
                        pkt_type = 'gatt_read_by_type'
                    elif 'att read request' in lower or 'read request' in lower:
                        pkt_type = 'gatt_read'
                    elif 'att write request' in lower or 'att write command' in lower or 'write request' in lower:
                        pkt_type = 'gatt_write'
                    elif 'att handle value notification' in lower or 'handle value notification' in lower:
                        pkt_type = 'gatt_notify'
                    elif 'att error response' in lower:
                        pkt_type = 'att_error'

                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': pkt_type,
                        'raw': line,
                        'raw_lines': [line],
                        'data': {}
                    }
                    if active_mac:
                        current_packet['data']['address'] = active_mac

                # LE Advertising Report
                if 'LE Advertising Report' in line or 'ADV_IND' in line or 'ADV_NONCONN_IND' in line or 'SCAN_RSP' in line:
                    self._flush_packet(json_handle, current_packet)
                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'advertisement',
                        'raw': line,
                        'raw_lines': [line],
                        'data': {}
                    }
                    active_mac = None

                # LE Connection Complete
                elif 'LE Connection Complete' in line or 'LE Enhanced Connection Complete' in line:
                    self._flush_packet(json_handle, current_packet)
                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'connection',
                        'raw': line,
                        'raw_lines': [line],
                        'data': {}
                    }
                    active_mac = None
                    logger.info("🔗 LE connection event seen")

                # Disconnection
                elif 'Disconnection Complete' in line:
                    self._flush_packet(json_handle, current_packet)
                    current_packet = {
                        'timestamp': datetime.now().isoformat(),
                        'type': 'disconnection',
                        'raw': line,
                        'raw_lines': [line],
                        'data': {}
                    }
                    active_mac = None

                # GATT operations
                elif 'ATT Read By Type Request' in line or 'ATT Read By Type Response' in line:
                    if not current_packet:
                        current_packet = {'timestamp': datetime.now().isoformat(),
                                          'type': 'gatt_read_by_type', 'raw_lines': [line], 'data': {}}
                    else:
                        current_packet['type'] = 'gatt_read_by_type'
                elif 'ATT Read Request' in line or 'Read Request' in line:
                    if not current_packet:
                        current_packet = {'timestamp': datetime.now().isoformat(),
                                          'type': 'gatt_read', 'raw_lines': [line], 'data': {}}
                    else:
                        current_packet['type'] = 'gatt_read'
                elif 'ATT Write Request' in line or 'Write Request' in line or 'ATT Write Command' in line:
                    if not current_packet:
                        current_packet = {'timestamp': datetime.now().isoformat(),
                                          'type': 'gatt_write', 'raw_lines': [line], 'data': {}}
                    else:
                        current_packet['type'] = 'gatt_write'
                elif 'ATT Handle Value Notification' in line or 'Handle Value Notification' in line:
                    if not current_packet:
                        current_packet = {'timestamp': datetime.now().isoformat(),
                                          'type': 'gatt_notify', 'raw_lines': [line], 'data': {}}
                    else:
                        current_packet.setdefault('type', 'gatt_notify')
                elif 'ATT Error Response' in line:
                    if not current_packet:
                        current_packet = {'timestamp': datetime.now().isoformat(),
                                          'type': 'att_error', 'raw_lines': [line], 'data': {}}
                    else:
                        current_packet['type'] = 'att_error'

                # ── Field extraction ──────────────────────────────────

                if not current_packet:
                    continue

                # Address line  (e.g. "Address: AA:BB:CC:DD:EE:FF (Public)")
                addr_match = re.search(
                    r'Address:\s+([0-9A-Fa-f:]{17})', line
                )
                if addr_match:
                    addr = addr_match.group(1).upper()
                    active_mac = addr
                    current_packet['data']['address'] = addr

                    if self.target_mac and not self.no_filter:
                        if addr != self.target_mac:
                            # Wrong device — discard and skip to next event
                            self._events_discarded += 1
                            if self.debug:
                                logger.debug(
                                    f"[filter] discarding {addr} "
                                    f"(want {self.target_mac})"
                                )
                            current_packet = {}
                            active_mac = None
                        else:
                            logger.info(f"🎯 Target device seen: {addr}")

                # Device name ("Name (complete): Foobar" or "Complete Local Name: Foobar")
                name_match = re.search(
                    r'(?:Complete [Ll]ocal [Nn]ame|Name \((?:complete|short)\)|Complete name|Short name):\s+(.+)',
                    line
                )
                if name_match and current_packet:
                    name = name_match.group(1).strip()
                    current_packet['data']['name'] = name
                    if self.debug:
                        logger.debug(f"Parsed name: {name}")

                # RSSI
                rssi_match = re.search(r'RSSI:\s+(-?\d+)\s*dBm', line)
                if rssi_match and current_packet:
                    current_packet['data']['rssi'] = int(rssi_match.group(1))

                # GATT handle
                handle_match = re.search(r'Handle:\s+0x([0-9a-fA-F]+)', line)
                if handle_match and current_packet:
                    current_packet['data']['handle'] = handle_match.group(1)

                # GATT value
                value_match = re.search(r'Value:\s+([0-9a-fA-F ]+)', line)
                if value_match and current_packet:
                    current_packet['data']['value'] = value_match.group(1).strip()

                # ACL/HCI plen/dlen field captures the declared payload length,
                # useful for framing even when btmon doesn't decode body bytes.
                plen_match = re.search(r'(?:plen|dlen)\s+(\d+)', line)
                if plen_match and current_packet:
                    current_packet['data'].setdefault('plen', int(plen_match.group(1)))

                # Capture common status/error fields for debugging and filtering.
                status_match = re.search(r'^Status:\s+(.+)$', line)
                if status_match and current_packet:
                    current_packet['data']['status'] = status_match.group(1).strip()

                reason_match = re.search(r'^Reason:\s+(.+)$', line)
                if reason_match and current_packet:
                    current_packet['data']['reason'] = reason_match.group(1).strip()

                error_match = re.search(r'^Error:\s+(.+)$', line)
                if error_match and current_packet:
                    current_packet['data']['error'] = error_match.group(1).strip()

                opcode_match = re.search(r'^Opcode:\s+(.+)$', line)
                if opcode_match and current_packet:
                    current_packet['data']['opcode'] = opcode_match.group(1).strip()

                # Generic key/value extraction keeps useful lines without bespoke parser code.
                kv_match = re.match(r'^([A-Za-z][A-Za-z0-9 _()/.-]{1,40}):\s+(.+)$', line)
                if kv_match and current_packet:
                    key = re.sub(r'[^a-z0-9_]+', '_', kv_match.group(1).strip().lower()).strip('_')
                    value = kv_match.group(2).strip()
                    if key and key not in current_packet['data']:
                        current_packet['data'][key] = value

        except OSError as e:
            # PTY master fd closed (btmon exited)
            logger.info(f"btmon PTY stream closed ({e}) — parser thread ending")
        except Exception as e:
            logger.error(f"_parse_btmon_output error: {e}", exc_info=True)
        finally:
            # Flush any in-progress packet
            if current_packet:
                self._flush_packet(json_handle, current_packet)
            for h in [raw_handle, log_handle, json_handle]:
                try:
                    if h:
                        h.close()
                except Exception:
                    pass
            logger.info(
                f"Parser thread finished. "
                f"raw_lines={self._raw_lines} "
                f"events_written={self._events_written} "
                f"events_discarded={self._events_discarded}"
            )

    def _flush_packet(self, handle, packet):
        """Write a completed packet to the JSON events file."""
        if not packet:
            return
        # Only write if we have meaningful data
        if not packet.get('data') and not packet.get('type'):
            return
        # Don't write bare advertisement packets with no address unless no_filter
        if not self.no_filter and not packet.get('data', {}).get('address'):
            if packet.get('type') == 'advertisement':
                return   # no address means we can't associate it yet
        try:
            out = dict(packet)
            data = out.setdefault('data', {})
            raw = out.pop('raw', None)
            raw_lines = out.pop('raw_lines', None)
            if raw and 'summary' not in data:
                data['summary'] = raw
            if raw_lines:
                data['raw_lines'] = raw_lines[-25:]
            handle.write(json.dumps(out) + '\n')
            handle.flush()
            self._events_written += 1
            if self.debug:
                logger.debug(f"[json] wrote event type={out.get('type')} data={out.get('data')}")
        except Exception as e:
            logger.warning(f"_flush_packet write error: {e}")

    # ── Teardown ───────────────────────────────────────────────────────────────

    def stop_capture(self):
        """Gracefully stop btmon, scanner, and all threads."""
        logger.info("Stopping capture...")
        self.running = False

        # Stop btmon
        if self.btmon_process:
            try:
                self.btmon_process.terminate()
                self.btmon_process.wait(timeout=5)
                logger.info(f"✓ btmon stopped (rc={self.btmon_process.returncode})")
            except Exception as e:
                logger.warning(f"btmon terminate failed: {e}")
                try:
                    self.btmon_process.kill()
                except Exception:
                    pass

        # Close PTY master fd (wakes up parser thread if blocked)
        if self._btmon_stdout_fd is not None:
            try:
                os.close(self._btmon_stdout_fd)
            except OSError:
                pass
            self._btmon_stdout_fd = None

        # Stop LE scan processes
        if self._scan_proc and self._scan_proc.poll() is None:
            try:
                self._scan_proc.terminate()
            except Exception:
                pass
        try:
            subprocess.run(['sudo', 'killall', '-q', 'hcitool'],
                           capture_output=True, timeout=3)
        except Exception:
            pass
        try:
            subprocess.run(['sudo', 'btmgmt', '--index', '0', 'discov', 'off'],
                           capture_output=True, timeout=3)
        except Exception:
            pass

        # Join threads
        for t in [self.parser_thread, self._stderr_thread, self._heartbeat_thread]:
            if t and t.is_alive():
                t.join(timeout=3)

        # Final file sizes
        for f in [self.raw_log_file, self.log_file, self.json_file, self.btsnoop_file]:
            try:
                sz = f.stat().st_size
                logger.info(f"  {f.name}: {sz:,} bytes")
            except Exception:
                logger.info(f"  {f.name}: not found")

        logger.info(
            f"Capture complete: "
            f"{self._events_written} events written, "
            f"{self._events_discarded} discarded, "
            f"{self._raw_lines} raw btmon lines"
        )

    # ── Main run loop ─────────────────────────────────────────────────────────

    def run(self, duration=None):
        """Run capture for `duration` seconds (or indefinitely if None)."""
        if not self.start_capture():
            logger.error("start_capture failed — exiting")
            return 1

        def _signal_handler(sig, frame):
            logger.info(f"Signal {sig} received — stopping...")
            self.stop_capture()
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        try:
            if duration:
                logger.info(f"Capturing for {duration}s (Ctrl+C to stop early)...")
                deadline = time.monotonic() + duration
                while time.monotonic() < deadline and self.running:
                    time.sleep(1)
                    # Bail early if btmon died
                    if self.btmon_process and self.btmon_process.poll() is not None:
                        logger.error(
                            f"btmon exited prematurely (rc={self.btmon_process.returncode}). "
                            f"Check /var/log/isolator/ble/*.raw.log for details."
                        )
                        break
            else:
                logger.info("Capturing indefinitely (Ctrl+C or SIGTERM to stop)...")
                while self.running:
                    time.sleep(1)
                    if self.btmon_process and self.btmon_process.poll() is not None:
                        logger.error(
                            f"btmon exited prematurely (rc={self.btmon_process.returncode}). "
                            f"Check {self.raw_log_file} for raw output."
                        )
                        break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_capture()

        return 0


def main():
    parser = argparse.ArgumentParser(
        description='BLE sniffer for IoT device reverse engineering',
        epilog=(
            'Debug tip: run with --debug --no-filter to capture everything and '  
            'see all raw btmon output in /var/log/isolator/ble/*.raw.log'
        )
    )
    parser.add_argument('--target', help='Target device name to filter')
    parser.add_argument('--target-mac', help='Target device MAC address (e.g. AA:BB:CC:DD:EE:FF)')
    parser.add_argument('--duration', type=int,
                        help='Capture duration in seconds (default: run until stopped)')
    parser.add_argument('--output-dir', default='/mnt/isolator/captures/ble',
                        help='Output directory for btsnoop captures')
    parser.add_argument('--debug', action='store_true',
                        help='Log every raw btmon line to the Python logger (very verbose)')
    parser.add_argument('--no-filter', action='store_true',
                        help='Capture all BLE addresses instead of filtering to target')

    args = parser.parse_args()

    if not args.target and not args.target_mac:
        logger.warning("No target specified — will capture ALL BLE traffic (use --no-filter to ensure nothing is discarded)")

    sniffer = BLESniffer(
        target_name=args.target,
        target_mac=args.target_mac,
        output_dir=args.output_dir,
        debug=args.debug,
        no_filter=args.no_filter,
    )

    return sniffer.run(duration=args.duration)


if __name__ == '__main__':
    sys.exit(main())
