#!/usr/bin/env python3
"""
Network Isolator Rules Generator

Reads isolator.conf.yaml and generates:
  - hostapd.conf (WiFi AP configuration)
  - dnsmasq.conf (DHCP/DNS configuration)
  - isolator.nft (nftables firewall rules)

Usage:
    python3 apply-rules.py --config /path/to/isolator.conf.yaml
"""

import argparse
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any
import yaml
import ipaddress

from topology_config import resolve_topology, validate_topology

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('apply-rules')


class RulesGenerator:
    """Generates configuration files from isolator.conf.yaml"""
    
    def __init__(self, config_path: Path, output_dir: Path, templates_dir: Path, apply_live: bool = True):
        self.config_path = config_path
        self.output_dir = output_dir
        self.templates_dir = templates_dir
        self.apply_live = apply_live
        self.config = self._load_config()
        self.topology = resolve_topology(self.config)
        validate_topology(self.config, self.topology)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded config from {self.config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)
    
    def _detect_wifi_capabilities(self, interface: str, band: str) -> Dict[str, bool]:
        """
        Detect WiFi hardware capabilities using iw.
        
        Args:
            interface: WiFi interface name (e.g., 'wlan0')
            band: '2.4GHz' or '5GHz'
            
        Returns:
            Dict with capability flags: {'ht40': bool, 'short_gi_20': bool, 'short_gi_40': bool}
        """
        caps = {
            'ht40': False,
            'short_gi_20': False,
            'short_gi_40': False
        }
        
        try:
            # Get phy device for interface
            result = subprocess.run(
                ['cat', f'/sys/class/net/{interface}/phy80211/name'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                logger.warning(f"Could not determine phy for {interface}, using conservative settings")
                return caps
            
            phy = result.stdout.strip()
            
            # Query capabilities
            result = subprocess.run(
                ['/usr/sbin/iw', 'phy', phy, 'info'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                logger.warning(f"Could not query WiFi capabilities, using conservative settings")
                return caps
            
            # Parse capabilities for the relevant band
            in_correct_band = False
            band_line = 'Band 1:' if band == '2.4GHz' else 'Band 2:'
            
            for line in result.stdout.split('\n'):
                if band_line in line:
                    in_correct_band = True
                elif 'Band' in line and ':' in line:
                    in_correct_band = False
                
                if in_correct_band:
                    if 'HT20/HT40' in line or ('HT40' in line and 'HT20' not in line):
                        caps['ht40'] = True
                    if 'RX HT20 SGI' in line:
                        caps['short_gi_20'] = True
                    if 'RX HT40 SGI' in line:
                        caps['short_gi_40'] = True
            
            logger.info(f"WiFi capabilities for {interface} on {band}: HT40={caps['ht40']}, SGI-20={caps['short_gi_20']}, SGI-40={caps['short_gi_40']}")
            
        except Exception as e:
            logger.warning(f"Error detecting WiFi capabilities: {e}, using conservative settings")
        
        return caps
    
    def generate_all(self):
        """Generate all configuration files"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Generating configuration files...")
        
        if self.topology['isolated']['kind'] == 'wifi-ap':
            self.generate_hostapd()
        self.generate_dnsmasq()
        self.generate_nftables()
        
        logger.info("Configuration generation complete")
    
    def generate_hostapd(self):
        """Generate hostapd.conf for WiFi AP"""
        ap_config = self.topology.get('ap', {})
        interface = self.topology['isolated']['interface']
        band = ap_config.get('band', '2.4GHz')
        
        # Detect hardware capabilities
        caps = self._detect_wifi_capabilities(interface, band)
        
        # Build ht_capab string based on detected capabilities
        ht_capab_flags = []
        if caps['short_gi_20']:
            ht_capab_flags.append('SHORT-GI-20')
        if caps['ht40'] and caps['short_gi_40']:
            ht_capab_flags.append('SHORT-GI-40')
            # Add HT40+ or HT40- based on channel (simplified: use HT40+ for lower channels)
            channel = ap_config.get('channel', 6)
            if channel <= 7:
                ht_capab_flags.append('HT40+')
            else:
                ht_capab_flags.append('HT40-')
        
        ht_capab_line = f"ht_capab=[{']['.join(ht_capab_flags)}]" if ht_capab_flags else "# ht_capab disabled (no capabilities detected)"
        
        hostapd_conf = f"""# hostapd configuration - Generated by Network Isolator
# DO NOT EDIT MANUALLY - Changes will be overwritten

interface={interface}
driver=nl80211

# AP Identity
ssid={ap_config.get('ssid', 'NetworkIsolator')}
hw_mode={'g' if band == '2.4GHz' else 'a'}
channel={ap_config.get('channel', 6)}
country_code=US

# WPA2 Security
wpa=2
wpa_passphrase={ap_config.get('password', 'ChangeMeNow!')}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP

# Performance
wmm_enabled=1
ieee80211n=1
{ht_capab_line}

# Logging
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
"""
        
        output_file = self.output_dir / 'hostapd.conf'
        output_file.write_text(hostapd_conf)
        logger.info(f"Generated hostapd.conf")
        
        # Link to system location
        system_file = Path('/etc/hostapd/hostapd.conf')
        if not system_file.exists() or system_file.is_symlink():
            system_file.unlink(missing_ok=True)
            system_file.symlink_to(output_file)
    
    def generate_dnsmasq(self):
        """Generate dnsmasq.conf for DHCP/DNS"""
        lan_config = self.topology['lan']
        isolated_interface = self.topology['isolated']['interface']
        
        # Calculate DHCP range
        subnet = ipaddress.IPv4Network(lan_config.get('subnet', '192.168.111.0/24'))
        gateway = lan_config.get('gateway', '192.168.111.1')
        dhcp_range = lan_config.get('dhcp_range', '192.168.111.100-192.168.111.200')
        # Convert dash to comma for dnsmasq format
        dhcp_range = dhcp_range.replace('-', ',')
        lease_hours = lan_config.get('lease_hours', 24)
        
        dnsmasq_conf = f"""# dnsmasq configuration - Generated by Network Isolator
# DO NOT EDIT MANUALLY - Changes will be overwritten

# Listen only on isolated interface
interface={isolated_interface}
bind-interfaces

# DHCP configuration
dhcp-range={dhcp_range},{lease_hours}h
dhcp-option=option:router,{gateway}
dhcp-option=option:dns-server,{gateway}

# Authoritative DHCP server
dhcp-authoritative

# DNS configuration
domain=isolator.local
local=/isolator.local/

# Logging
log-queries
log-dhcp
log-facility=/var/log/isolator/dnsmasq.log

# DHCP host reservations
"""
        
        # Add static IP reservations for known devices
        for device in self.config.get('devices', []):
            if 'static_ip' in device and 'mac' in device:
                device_id = device.get('id', 'unknown')
                mac = device['mac']
                ip = device['static_ip']
                dnsmasq_conf += f"dhcp-host={mac},{ip},{device_id}\n"
        
        output_file = self.output_dir / 'dnsmasq.conf'
        output_file.write_text(dnsmasq_conf)
        logger.info(f"Generated dnsmasq.conf")
        
        # Link to system location
        system_file = Path('/etc/dnsmasq.d/isolator.conf')
        system_file.parent.mkdir(parents=True, exist_ok=True)
        if system_file.exists() or system_file.is_symlink():
            system_file.unlink()
        system_file.symlink_to(output_file)
    
    def generate_nftables(self):
        """Generate nftables firewall rules"""
        
        lan_config = self.topology['lan']
        upstream_interface = self.topology['upstream']['interface']
        isolated_interface = self.topology['isolated']['interface']
        isolated_subnet = lan_config.get('subnet', '192.168.111.0/24')
        dashboard_cfg = self.config.get('dashboard', {}) or {}
        dashboard_exposure = (dashboard_cfg.get('exposure', {}) or {})
        dashboard_mode = str(dashboard_exposure.get('mode', 'localhost')).lower()
        dashboard_port = int(dashboard_cfg.get('port', 5006))
        
        nft_rules = f"""#!/usr/sbin/nft -f
# nftables ruleset - Generated by Network Isolator
# DO NOT EDIT MANUALLY - Changes will be overwritten

flush ruleset

# Define variables
define ISOLATED_INTERFACE = {isolated_interface}
define UPSTREAM_INTERFACE = {upstream_interface}
define ISOLATED_SUBNET = {isolated_subnet}

table inet isolator {{
    # ── INPUT: Traffic to the Pi itself ──────────────────────────────────
    chain input {{
        type filter hook input priority 0; policy drop;
        
        # Allow established connections
        ct state established,related accept
        
        # Allow loopback
        iif lo accept
        
        # Allow SSH from the upstream / management interface
        iif $UPSTREAM_INTERFACE tcp dport 22 accept
        
        # Allow DHCP, DNS from isolated-side clients
        iif $ISOLATED_INTERFACE udp dport {{ 53, 67 }} accept

        # Optional dashboard access (config-driven)
"""

        if dashboard_mode in ('upstream', 'all'):
            nft_rules += f"        iif $UPSTREAM_INTERFACE tcp dport {dashboard_port} accept\n"
        if dashboard_mode in ('isolated', 'all'):
            nft_rules += f"        iif $ISOLATED_INTERFACE tcp dport {dashboard_port} accept\n"
        if dashboard_mode == 'explicit':
            # explicit bind can map to either side; allow both interfaces by default
            nft_rules += f"        iif $UPSTREAM_INTERFACE tcp dport {dashboard_port} accept\n"
            nft_rules += f"        iif $ISOLATED_INTERFACE tcp dport {dashboard_port} accept\n"

        nft_rules += f"""
        
        # Allow ping
        icmp type echo-request limit rate 10/second accept
        
        # Log dropped packets
        log prefix "INPUT-DROP: " level info
    }}
    
    # ── FORWARD: Traffic through the Pi (routing) ────────────────────────
    chain forward {{
        type filter hook forward priority 0; policy drop;
        
        # Allow established connections
        ct state established,related accept
        
        # Process per-device rules for isolated-side traffic
        iif $ISOLATED_INTERFACE jump isolated_clients
        
        # Log dropped packets
        log prefix "FORWARD-DROP: " level info
    }}
    
    # ── OUTPUT: Traffic from the Pi itself ───────────────────────────────
    chain output {{
        type filter hook output priority 0; policy accept;
    }}
    
    # ── Isolated Clients Chain ───────────────────────────────────────────
    chain isolated_clients {{
"""
        
        # Generate per-device rules
        for device in self.config.get('devices', []):
            device_id = device.get('id')
            mac = device.get('mac')
            static_ip = device.get('static_ip')
            internet = device.get('internet', 'deny')
            lan_access = device.get('lan_access', [])
            
            if not mac:
                continue
            
            nft_rules += f"        # Device: {device_id}\n"
            
            # Match by MAC address
            nft_rules += f"        ether saddr {mac} jump device_{device_id.replace('-', '_')}\n"
        
        # Default policy for unknown devices
        nft_rules += f"        # Unknown devices (default policy)\n"
        nft_rules += f"        jump default_policy\n"
        nft_rules += f"    }}\n\n"
        
        # Generate device-specific chains
        for device in self.config.get('devices', []):
            device_id = device.get('id')
            mac = device.get('mac')
            internet = device.get('internet', 'deny')
            lan_access = device.get('lan_access', [])
            
            if not mac:
                continue
            
            chain_name = f"device_{device_id.replace('-', '_')}"
            nft_rules += f"    # Chain for: {device_id}\n"
            nft_rules += f"    chain {chain_name} {{\n"
            
            # LAN access rules
            if lan_access:
                for rule in lan_access:
                    host = rule.get('host')
                    ports = rule.get('ports', [])
                    if host and ports:
                        port_list = ','.join(map(str, ports))
                        nft_rules += f"        oif $UPSTREAM_INTERFACE ip daddr {host} tcp dport {{ {port_list} }} accept\n"
            
            # Internet access
            if internet == 'allow':
                nft_rules += f"        oif $UPSTREAM_INTERFACE accept\n"
            elif internet == 'log-only':
                nft_rules += f"        oif $UPSTREAM_INTERFACE log prefix \"DEVICE-{device_id}: \" accept\n"
            else:  # deny
                nft_rules += f"        oif $UPSTREAM_INTERFACE log prefix \"BLOCKED-{device_id}: \" drop\n"
            
            nft_rules += f"    }}\n\n"
        
        # Default policy chain for unknown devices
        default_policy = self.config.get('default_policy', {})
        default_internet = default_policy.get('internet', 'deny')
        
        nft_rules += f"    # Default policy for unknown devices\n"
        nft_rules += f"    chain default_policy {{\n"
        
        if default_internet == 'allow':
            nft_rules += f"        oif $UPSTREAM_INTERFACE accept\n"
        elif default_internet == 'log-only':
            nft_rules += f"        oif $UPSTREAM_INTERFACE log prefix \"UNKNOWN-DEVICE: \" accept\n"
        else:  # deny
            nft_rules += f"        oif $UPSTREAM_INTERFACE log prefix \"BLOCKED-UNKNOWN: \" drop\n"
        
        nft_rules += f"    }}\n"
        nft_rules += f"}}\n\n"
        
        # NAT table for internet access
        nft_rules += f"""# NAT table for internet masquerading
table ip nat {{
    chain postrouting {{
        type nat hook postrouting priority 100; policy accept;
        oifname "{upstream_interface}" masquerade
    }}
}}
"""
        
        output_file = self.output_dir / 'isolator.nft'
        output_file.write_text(nft_rules)
        output_file.chmod(0o755)
        logger.info(f"Generated isolator.nft")
        
        # Apply the rules
        if self.apply_live:
            try:
                subprocess.run(['nft', '-f', str(output_file)], check=True, capture_output=True)
                logger.info("Applied nftables rules successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to apply nftables rules: {e.stderr.decode()}")
                raise
        else:
            logger.info("Skipped live nftables apply (--no-apply)")


def main():
    parser = argparse.ArgumentParser(description='Generate Network Isolator configuration')
    parser.add_argument('--config', required=True, help='Path to isolator.conf.yaml')
    parser.add_argument('--output-dir', default='/etc/isolator', help='Output directory for generated configs')
    parser.add_argument('--templates-dir', default='/opt/isolator/templates', help='Templates directory')
    parser.add_argument('--no-apply', action='store_true', help='Generate configs without applying nftables rules')
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    templates_dir = Path(args.templates_dir)
    
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    generator = RulesGenerator(config_path, output_dir, templates_dir, apply_live=not args.no_apply)
    generator.generate_all()
    
    logger.info("✓ Configuration applied successfully")


if __name__ == '__main__':
    main()
