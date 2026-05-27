#!/usr/bin/env python3
"""
BLE Proxy Profiler

Profiles a BLE target device for proxy/emulation workflows without MAC cloning.
It captures:
  1) Advertisement fingerprint observations
  2) Full GATT hierarchy (services, characteristics, descriptors)
  3) Readable characteristic values (best-effort)

The output profile JSON is intended for a future BLE GATT proxy that:
  - advertises similarly to the target (but with local controller MAC)
  - exposes a mirrored local GATT server
  - forwards ATT/GATT operations to the real target
  - logs all operations for analysis and replay

Usage examples:
  python3 ble-proxy-profiler.py --target-mac AA:BB:CC:DD:EE:FF
  python3 ble-proxy-profiler.py --target-name MyDevice --scan-duration 20
"""


import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("ERROR: bleak not installed in this environment", file=sys.stderr)
    sys.exit(1)

# ---------------- Configurable Constants ----------------
LOG_ROOT = os.environ.get('PERIMETERCONTROL_BLE_LOG_ROOT', '/var/log/PerimeterControl/ble')
LOGGER_NAME = os.environ.get('PERIMETERCONTROL_LOGGER', 'perimetercontrol.ble-proxy-profiler')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(LOGGER_NAME)


def _hex_bytes(data: bytes) -> str:
    return data.hex() if data else ""


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON atomically so readers never observe partially written files."""
    tmp_path = path.with_name(f".{path.name}.tmp")
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


class BLEProxyProfiler:
    def __init__(
        self,
        target_mac: Optional[str],
        target_name: Optional[str],
        scan_duration: float,
        connect_timeout: float,
        service_discovery_timeout: float,
        service_discovery_poll_interval: float,
        output_dir: Path = None,
        read_values: bool = True,
        max_gatt_attempts: int = 3,
        retry_backoff_initial: float = 1.0,
        retry_backoff_max: float = 10.0,
    ):
        self.target_mac = target_mac.upper() if target_mac else None
        self.target_name = target_name
        self.scan_duration = scan_duration
        self.connect_timeout = connect_timeout
        self.service_discovery_timeout = service_discovery_timeout
        self.service_discovery_poll_interval = service_discovery_poll_interval
        self.output_dir = Path(output_dir or LOG_ROOT)
        self.read_values = read_values
        self.max_gatt_attempts = max_gatt_attempts
        self.retry_backoff_initial = retry_backoff_initial
        self.retry_backoff_max = retry_backoff_max

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # MAC -> observation info
        self.seen: Dict[str, Dict[str, Any]] = {}

    def _is_gatt_discovery_success(self, gatt: Dict[str, Any]) -> bool:
        if not gatt.get('connected'):
            return False
        summary = gatt.get('summary', {})
        return int(summary.get('service_count', 0)) > 0

    def _match_target(self, mac: str, name: str) -> bool:
        if self.target_mac and mac == self.target_mac:
            return True
        if self.target_name:
            wanted = self.target_name.lower()
            if wanted in (name or '').lower():
                return True
        return False

    def _on_adv(self, device: BLEDevice, adv: AdvertisementData):
        mac = (device.address or "").upper()
        if not mac:
            return

        name = device.name or adv.local_name or f"Unknown_{mac.replace(':', '')[-6:]}"

        manufacturer_data = {
            str(company_id): _hex_bytes(payload)
            for company_id, payload in (adv.manufacturer_data or {}).items()
        }

        service_data = {
            str(uuid): _hex_bytes(payload)
            for uuid, payload in (adv.service_data or {}).items()
        }

        observation = {
            'timestamp': datetime.now().isoformat(),
            'mac': mac,
            'name': name,
            'rssi': adv.rssi,
            'tx_power': adv.tx_power,
            'local_name': adv.local_name,
            'service_uuids': list(adv.service_uuids or []),
            'manufacturer_data': manufacturer_data,
            'service_data': service_data,
        }

        if mac not in self.seen:
            logger.info(f"Discovered {name} ({mac}) RSSI={adv.rssi}")
            self.seen[mac] = {
                'first_seen': observation['timestamp'],
                'last_seen': observation['timestamp'],
                'name': name,
                'count': 1,
                'best_rssi': adv.rssi if adv.rssi is not None else -999,
                'latest_observation': observation,
                'observations': [observation],
            }
        else:
            entry = self.seen[mac]
            entry['last_seen'] = observation['timestamp']
            entry['count'] += 1
            if adv.rssi is not None and adv.rssi > entry.get('best_rssi', -999):
                entry['best_rssi'] = adv.rssi
            if device.name and entry['name'].startswith('Unknown_'):
                entry['name'] = device.name
            entry['latest_observation'] = observation
            # Keep profile files bounded
            if len(entry['observations']) < 50:
                entry['observations'].append(observation)

    async def _scan(self) -> Optional[Dict[str, Any]]:
        logger.info(f"Scanning for {self.scan_duration:.1f}s...")

        async with BleakScanner(
            detection_callback=self._on_adv,
            scanning_mode='active',
        ):
            await asyncio.sleep(self.scan_duration)

        if not self.seen:
            logger.error("No BLE devices discovered during scan")
            return None

        # Resolve target device
        selected_mac = None

        if self.target_mac and self.target_mac in self.seen:
            selected_mac = self.target_mac
        elif self.target_name:
            candidates = [
                mac for mac, info in self.seen.items()
                if self._match_target(mac, info.get('name', ''))
            ]
            if candidates:
                # choose strongest candidate by best RSSI
                selected_mac = max(candidates, key=lambda m: self.seen[m].get('best_rssi', -999))
        else:
            # fallback: strongest seen device
            selected_mac = max(self.seen.keys(), key=lambda m: self.seen[m].get('best_rssi', -999))

        if not selected_mac:
            logger.error("Target not found in scan results")
            return None

        info = self.seen[selected_mac]
        logger.info(
            f"Target selected: {info.get('name')} ({selected_mac}) "
            f"count={info.get('count')} best_rssi={info.get('best_rssi')}"
        )

        return {
            'mac': selected_mac,
            'name': info.get('name'),
            'scan_entry': info,
        }

    async def _forget_device(self, mac: str) -> None:
        """Remove device from BlueZ device cache so GATT discovery is always fresh."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'bluetoothctl', 'remove', mac,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            await asyncio.sleep(0.5)  # let BlueZ settle after removal
            logger.debug(f"Removed {mac} from BlueZ cache")
        except Exception as e:
            logger.debug(f"_forget_device({mac}): {e} (non-fatal)")

    async def _discover_services(self, client: BleakClient) -> List[Any]:
        """Poll GATT discovery on a connected link until services are visible or timeout."""
        deadline = asyncio.get_running_loop().time() + max(1.0, self.service_discovery_timeout)
        poll = max(0.2, self.service_discovery_poll_interval)

        last_error: Optional[str] = None

        while asyncio.get_running_loop().time() < deadline:
            try:
                services_obj = await client.get_services()
                services = list(services_obj or [])
                if services:
                    return services
            except Exception as e:
                # Some devices briefly reject discovery right after connect.
                last_error = str(e)

            await asyncio.sleep(poll)

        if last_error:
            logger.warning(f"Service discovery timeout with last error: {last_error}")
        else:
            logger.warning("Service discovery timeout with no services returned")

        return []

    async def _profile_gatt(self, target_mac: str) -> Dict[str, Any]:
        logger.info(f"Connecting to {target_mac} for GATT discovery...")

        gatt_result: Dict[str, Any] = {
            'connected': False,
            'services': [],
            'summary': {
                'service_count': 0,
                'characteristic_count': 0,
                'descriptor_count': 0,
                'read_success': 0,
                'read_fail': 0,
                'descriptor_read_success': 0,
                'descriptor_read_fail': 0,
            },
            'errors': [],
        }

        # Purge any stale BlueZ device cache entry (common cause of 0 services)
        await self._forget_device(target_mac)

        try:
            async with BleakClient(
                target_mac,
                timeout=self.connect_timeout,
                bluez={"use_cached_services": False},
            ) as client:
                gatt_result['connected'] = client.is_connected
                if not client.is_connected:
                    gatt_result['errors'].append('connect_failed')
                    return gatt_result

                # Give BlueZ a moment, then poll until services appear or timeout.
                await asyncio.sleep(1.0)
                services = await self._discover_services(client)

                if not services:
                    gatt_result['errors'].append('service_discovery_timeout')

                for svc in services:
                    svc_item: Dict[str, Any] = {
                        'uuid': str(svc.uuid),
                        'description': str(getattr(svc, 'description', '') or ''),
                        'handle': getattr(svc, 'handle', None),
                        'characteristics': [],
                    }
                    gatt_result['summary']['service_count'] += 1

                    for ch in svc.characteristics:
                        ch_item: Dict[str, Any] = {
                            'uuid': str(ch.uuid),
                            'description': str(getattr(ch, 'description', '') or ''),
                            'handle': getattr(ch, 'handle', None),
                            'properties': list(getattr(ch, 'properties', []) or []),
                            'read': {
                                'attempted': False,
                                'ok': False,
                                'value_hex': None,
                                'error': None,
                            },
                            'descriptors': [],
                        }
                        gatt_result['summary']['characteristic_count'] += 1

                        # Best-effort value read for read-capable chars
                        if self.read_values and 'read' in ch_item['properties']:
                            ch_item['read']['attempted'] = True
                            try:
                                value = await client.read_gatt_char(ch)
                                ch_item['read']['ok'] = True
                                ch_item['read']['value_hex'] = _hex_bytes(value)
                                gatt_result['summary']['read_success'] += 1
                            except Exception as read_err:
                                ch_item['read']['error'] = str(read_err)
                                gatt_result['summary']['read_fail'] += 1

                        for desc in ch.descriptors:
                            desc_item: Dict[str, Any] = {
                                'uuid': str(getattr(desc, 'uuid', '') or ''),
                                'handle': getattr(desc, 'handle', None),
                                'read': {
                                    'attempted': False,
                                    'ok': False,
                                    'value_hex': None,
                                    'error': None,
                                },
                            }
                            gatt_result['summary']['descriptor_count'] += 1

                            if self.read_values and desc_item['handle'] is not None:
                                desc_item['read']['attempted'] = True
                                try:
                                    value = await client.read_gatt_descriptor(desc_item['handle'])
                                    desc_item['read']['ok'] = True
                                    desc_item['read']['value_hex'] = _hex_bytes(value)
                                    gatt_result['summary']['descriptor_read_success'] += 1
                                except Exception as desc_err:
                                    desc_item['read']['error'] = str(desc_err)
                                    gatt_result['summary']['descriptor_read_fail'] += 1

                            ch_item['descriptors'].append(desc_item)

                        svc_item['characteristics'].append(ch_item)

                    gatt_result['services'].append(svc_item)

        except Exception as e:
            msg = f"gatt_profile_error: {e}"
            logger.error(msg)
            gatt_result['errors'].append(msg)

        return gatt_result

    async def _profile_gatt_until_success(self, target_mac: str) -> Dict[str, Any]:
        attempt = 1
        backoff = max(0.5, self.retry_backoff_initial)
        last_gatt: Optional[Dict[str, Any]] = None

        while True:
            logger.info(f"GATT attempt {attempt} for {target_mac}")
            gatt = await self._profile_gatt(target_mac)
            last_gatt = gatt

            if self._is_gatt_discovery_success(gatt):
                logger.info(
                    f"GATT discovery succeeded on attempt {attempt} "
                    f"(services={gatt['summary']['service_count']})"
                )
                return gatt

            logger.warning(
                "GATT discovery did not return services "
                f"(connected={gatt.get('connected')} services={gatt.get('summary', {}).get('service_count', 0)})."
            )

            if self.max_gatt_attempts > 0 and attempt >= self.max_gatt_attempts:
                logger.error(
                    f"Reached max GATT attempts ({self.max_gatt_attempts}) without service discovery"
                )
                return last_gatt or gatt

            logger.info(f"Retrying GATT discovery in {backoff:.1f}s...")
            await asyncio.sleep(backoff)
            backoff = min(max(0.5, self.retry_backoff_max), backoff * 1.5)
            attempt += 1

    def _build_profile_doc(self, target: Dict[str, Any], gatt: Dict[str, Any]) -> Dict[str, Any]:
        target_scan = target['scan_entry']
        adv_fingerprint = target_scan.get('latest_observation', {})

        # Fields commonly expected to rotate and therefore not strict match keys.
        mutable_adv_fields = [
            'rssi',
            'tx_power',
            'service_data',
            'manufacturer_data',
            'name',
        ]

        profile = {
            'profile_version': 1,
            'created_at': datetime.now().isoformat(),
            'mode': 'ble-gatt-proxy-no-mac-clone',
            'constraints': {
                'mac_clone_required': False,
                'mac_clone_enabled': False,
                'notes': [
                    'Proxy presents local controller identity (different MAC).',
                    'This profile captures ATT/GATT behavior, not RF-level channel-follow metadata.',
                    'If target enforces pairing/bonding or app-layer auth, forwarding logic must preserve session state.',
                ],
            },
            'target': {
                'mac': target['mac'],
                'name': target['name'],
            },
            'advertising': {
                'fingerprint': adv_fingerprint,
                'observations': target_scan.get('observations', []),
                'first_seen': target_scan.get('first_seen'),
                'last_seen': target_scan.get('last_seen'),
                'seen_count': target_scan.get('count', 0),
                'best_rssi': target_scan.get('best_rssi'),
                'mutable_fields': mutable_adv_fields,
            },
            'gatt': gatt,
        }

        return profile

    def _safe_slug(self, name: str) -> str:
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', name).strip('_') or 'unknown'

    def _write_profile(self, profile: Dict[str, Any]) -> Path:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_label = profile.get('target', {}).get('name') or profile.get('target', {}).get('mac', 'unknown')
        target_slug = self._safe_slug(str(target_label))

        profile_file = self.output_dir / f"profile_{target_slug}_{ts}.json"
        _atomic_write_json(profile_file, profile)

        # Keep a stable latest profile pointer by copy
        latest_file = self.output_dir / f"profile_{target_slug}_latest.json"
        _atomic_write_json(latest_file, profile)

        return profile_file

    async def run(self) -> int:
        target = await self._scan()
        if not target:
            return 2

        gatt = await self._profile_gatt_until_success(target['mac'])
        profile = self._build_profile_doc(target, gatt)
        profile_path = self._write_profile(profile)

        logger.info(f"Profile written: {profile_path}")
        logger.info(
            "Profile summary: "
            f"services={gatt['summary']['service_count']} "
            f"chars={gatt['summary']['characteristic_count']} "
            f"descriptors={gatt['summary']['descriptor_count']} "
            f"read_ok={gatt['summary']['read_success']} "
            f"read_fail={gatt['summary']['read_fail']}"
        )

        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Profile BLE target for GATT proxy/emulation (no MAC clone).'
    )
    parser.add_argument('--target-mac', help='Target MAC address (AA:BB:CC:DD:EE:FF)')
    parser.add_argument('--target-name', help='Target name substring match (case-insensitive)')
    parser.add_argument('--scan-duration', type=float, default=15.0,
                        help='Advertisement scan duration before selecting target (seconds)')
    parser.add_argument('--connect-timeout', type=float, default=20.0,
                        help='Connection timeout in seconds')
    parser.add_argument('--service-discovery-timeout', type=float, default=25.0,
                        help='How long to keep polling for GATT services after connect (seconds)')
    parser.add_argument('--service-discovery-poll-interval', type=float, default=1.0,
                        help='Polling interval while waiting for GATT services (seconds)')
    parser.add_argument('--output-dir', default='/var/log/isolator/ble/profiles',
                        help='Output directory for profile JSON files')
    parser.add_argument('--no-read-values', action='store_true',
                        help='Skip best-effort characteristic/descriptor reads')
    parser.add_argument('--max-gatt-attempts', type=int, default=0,
                        help='Maximum GATT profiling attempts; 0 means retry forever until services are discovered')
    parser.add_argument('--retry-backoff-initial', type=float, default=2.0,
                        help='Initial retry backoff in seconds after failed GATT discovery')
    parser.add_argument('--retry-backoff-max', type=float, default=20.0,
                        help='Maximum retry backoff in seconds')

    args = parser.parse_args()

    if not args.target_mac and not args.target_name:
        logger.warning('No explicit target provided; strongest seen device will be profiled')

    profiler = BLEProxyProfiler(
        target_mac=args.target_mac,
        target_name=args.target_name,
        scan_duration=args.scan_duration,
        connect_timeout=args.connect_timeout,
        service_discovery_timeout=args.service_discovery_timeout,
        service_discovery_poll_interval=args.service_discovery_poll_interval,
        output_dir=Path(args.output_dir),
        read_values=not args.no_read_values,
        max_gatt_attempts=args.max_gatt_attempts,
        retry_backoff_initial=args.retry_backoff_initial,
        retry_backoff_max=args.retry_backoff_max,
    )

    return asyncio.run(profiler.run())


if __name__ == '__main__':
    sys.exit(main())
