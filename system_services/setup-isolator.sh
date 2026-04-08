#!/bin/bash
################################################################################
# Network Isolator Setup Script
# 
# This script configures a Raspberry Pi 3 as a WiFi access point with
# per-device firewall rules, traffic capture, and web dashboard.
#
# Usage:
#   sudo bash setup-isolator.sh --config /path/to/network_isolator.conf.yaml
#
# What it does:
#   - Installs required packages (hostapd, dnsmasq, nftables, etc.)
#   - Configures WiFi AP on wlan0
#   - Sets up DHCP server for AP clients
#   - Enables IP forwarding and NAT
#   - Creates systemd services
#   - Installs Python dashboard
#
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="/mnt/PerimeterControl/conf/network_isolator.conf.yaml"
INSTALL_DIR="/opt/PerimeterControl"
LOG_DIR="/var/log/PerimeterControl"
RUN_DIR="/run/PerimeterControl"
ISOLATED_INTERFACE=""
ISOLATED_KIND=""
UPSTREAM_INTERFACE=""
UPSTREAM_KIND=""

INSTALL_GSTREAMER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --with-gstreamer)
            INSTALL_GSTREAMER=true
            shift
            ;;
        --help)
            echo "Usage: sudo bash setup-isolator.sh --config /path/to/network_isolator.conf.yaml [--with-gstreamer]"
            echo ""
            echo "Options:"
            echo "  --config PATH          Path to network_isolator.conf.yaml"
            echo "  --with-gstreamer       Install GStreamer and PyGObject bindings (photo booth, wildlife monitor, audio capture)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Config file not found: $CONFIG_FILE"
        log_info "Copy config/network_isolator.conf.yaml to $CONFIG_FILE and customize it"
        exit 1
    fi
    log_success "Config file found: $CONFIG_FILE"
}

load_topology_from_config() {
    eval "$(python3 "$PROJECT_ROOT/scripts/network-topology.py" --config "$CONFIG_FILE" summary --format shell)"

    ISOLATED_INTERFACE="$ISOLATED_INTERFACE"
    ISOLATED_KIND="$ISOLATED_KIND"
    UPSTREAM_INTERFACE="$UPSTREAM_INTERFACE"
    UPSTREAM_KIND="$UPSTREAM_KIND"

    log_info "Resolved topology: isolated=$ISOLATED_INTERFACE ($ISOLATED_KIND), upstream=$UPSTREAM_INTERFACE ($UPSTREAM_KIND)"
}

################################################################################
# Main Installation Steps
################################################################################

banner() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Network Isolator Setup"
    echo "  Raspberry Pi WiFi AP with Traffic Analysis"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
}

step_install_packages() {
    log_info "Installing required packages..."
    
    apt update
    
    # Network services
    apt install -y hostapd dnsmasq iw
    
    # Firewall and networking
    apt install -y nftables iptables iproute2 bridge-utils
    
    # Traffic capture and analysis
    apt install -y tcpdump tshark wireshark-common conntrack

    # Bluetooth LE scanning (bleak requires BlueZ D-Bus + python3-bleak for system fallback)
    apt install -y bluez python3-bleak

    # Python for dashboard and scripts
    apt install -y python3 python3-pip python3-venv python3-dev python3-yaml
    
    # Utilities
    apt install -y git vim nano htop iftop nethogs jq pv

    # Hardware interface detection (used by supervisor node/features API)
    apt install -y i2c-tools v4l-utils gpiod libgpiod-dev

    if [[ "$INSTALL_GSTREAMER" == "true" ]]; then
        # GStreamer core + plugins (audio, video, I2S, V4L2, RTSP, HW codec)
        # Note: V4L2 support is bundled in gstreamer1.0-plugins-good on Pi OS
        apt install -y \
            gstreamer1.0-tools \
            gstreamer1.0-plugins-base \
            gstreamer1.0-plugins-good \
            gstreamer1.0-plugins-bad \
            gstreamer1.0-libav \
            gstreamer1.0-alsa \
            libgstreamer1.0-dev \
            libgstreamer-plugins-base1.0-dev

        # Python GStreamer / GObject bindings (must be apt - not pip-installable)
        apt install -y python3-gi python3-gi-cairo python3-gst-1.0 gir1.2-gst-plugins-base-1.0
        log_info "GStreamer installed"
    else
        log_info "Skipping GStreamer (pass --with-gstreamer to install)"
    fi

    log_success "Packages installed"
}

step_create_directories() {
    log_info "Creating directory structure..."
    
    # Installation directory
    mkdir -p "$INSTALL_DIR"/{scripts,templates,services}
    
    # Log directory
    mkdir -p "$LOG_DIR"
    
    # Runtime directory (pipes, pid files)
    mkdir -p "$RUN_DIR"
    
    # Capture directories
    mkdir -p /mnt/PerimeterControl/captures/{unknown,bridge}
    
    # Config directory (if using USB drive)
    mkdir -p /mnt/PerimeterControl/conf
    
    log_success "Directories created"
}

step_copy_files() {
    log_info "Copying project files..."
    
    # Copy scripts
    cp "$PROJECT_ROOT/scripts"/*.py "$INSTALL_DIR/scripts/" 2>/dev/null || true
    
    # Copy templates
    cp "$PROJECT_ROOT/server/templates"/* "$INSTALL_DIR/templates/" 2>/dev/null || true
    
    # Copy web dashboard
    cp -r "$PROJECT_ROOT/server/web" "$INSTALL_DIR/"
    
    # Copy requirements.txt
    cp "$PROJECT_ROOT/server/requirements.txt" "$INSTALL_DIR/"
    
    # Make scripts executable
    chmod +x "$INSTALL_DIR/scripts"/*.py
    
    log_success "Files copied to $INSTALL_DIR"
}

step_setup_python_env() {
    log_info "Setting up Python virtual environment for dashboard..."
    
    cd "$INSTALL_DIR"
    python3 -m venv --system-site-packages venv
    source venv/bin/activate
    
    pip install --upgrade pip
    pip install -r requirements.txt
    
    deactivate
    
    log_success "Python environment ready"
}

step_enable_ip_forwarding() {
    log_info "Enabling IP forwarding..."
    
    # Enable now
    sysctl -w net.ipv4.ip_forward=1
    
    # Persist across reboots
    if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    
    log_success "IP forwarding enabled"
}

step_disable_default_services() {
    log_info "Configuring network managers..."
    
    # Configure NetworkManager to ignore the isolated interface only.
    if systemctl is-active --quiet NetworkManager; then
        log_info "Configuring NetworkManager to ignore $ISOLATED_INTERFACE..."
        
        python3 - <<PY
from pathlib import Path

iface = ${ISOLATED_INTERFACE@Q}
path = Path('/etc/NetworkManager/NetworkManager.conf')
content = path.read_text() if path.exists() else ''
block = f"[keyfile]\nunmanaged-devices=interface-name:{iface}\n"

if f"interface-name:{iface}" not in content:
    if '[keyfile]' in content:
        lines = content.splitlines()
        updated = []
        inserted = False
        for line in lines:
            updated.append(line)
            if line.strip() == '[keyfile]' and not inserted:
                updated.append(f'unmanaged-devices=interface-name:{iface}')
                inserted = True
        path.write_text('\n'.join(updated) + '\n')
    else:
        path.write_text(content + ('\n' if content and not content.endswith('\n') else '') + block)
PY
        systemctl restart NetworkManager
        
        log_success "NetworkManager configured to ignore $ISOLATED_INTERFACE"
    fi
    
    # Stop default dnsmasq if running
    systemctl stop dnsmasq 2>/dev/null || true
    systemctl disable dnsmasq 2>/dev/null || true
    
    # Stop default hostapd if running
    systemctl stop hostapd 2>/dev/null || true
    systemctl unmask hostapd 2>/dev/null || true
    
    log_success "Network services configured"
}

step_generate_configs() {
    log_info "Generating configuration files from $CONFIG_FILE..."
    
    # Run the rules generator to create configs
    cd "$INSTALL_DIR"
    source venv/bin/activate
    
    python3 scripts/apply-rules.py \
        --config "$CONFIG_FILE" \
        --output-dir /etc/PerimeterControl \
        --templates-dir "$INSTALL_DIR/templates"
    
    deactivate
    
    log_success "Configuration files generated in /etc/PerimeterControl"
}

step_install_systemd_services() {
    log_info "Installing systemd services..."
    
    # Copy service files
    cp "$PROJECT_ROOT/server"/*.service /etc/systemd/system/
    
    # Create isolator.service if not exists
    if [[ ! -f /etc/systemd/system/isolator.service ]]; then
        cat > /etc/systemd/system/isolator.service <<'EOF'
[Unit]
Description=Network Isolator - WiFi AP with Traffic Isolation
After=network.target
Wants=hostapd.service dnsmasq.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/PerimeterControl/scripts/apply-rules.py --config /mnt/PerimeterControl/conf/network_isolator.conf.yaml
ExecReload=/opt/PerimeterControl/scripts/apply-rules.py --config /mnt/PerimeterControl/conf/network_isolator.conf.yaml
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    # Reload systemd
    systemctl daemon-reload
    
    log_success "Systemd services installed"
}

step_start_services() {
    log_info "Starting network isolator services..."
    
    # Prepare isolated interface, rules, and generated configs first.
    systemctl enable isolator
    systemctl start isolator
    sleep 2

    if [[ "$ISOLATED_KIND" == "wifi-ap" ]]; then
        systemctl enable hostapd
        systemctl start hostapd
        sleep 2
    else
        systemctl stop hostapd 2>/dev/null || true
        systemctl disable hostapd 2>/dev/null || true
    fi

    systemctl enable dnsmasq
    systemctl start dnsmasq
    sleep 2
    
    # Start dashboard
    systemctl enable isolator-dashboard
    systemctl start isolator-dashboard
    
    log_success "Services started"
}

step_verify_installation() {
    log_info "Verifying installation..."
    
    echo ""
    echo "Service Status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check each service
    for service in hostapd dnsmasq isolator isolator-dashboard; do
        if systemctl is-active --quiet $service; then
            echo -e "  ${GREEN}✓${NC} $service: running"
        else
            echo -e "  ${RED}✗${NC} $service: NOT running"
        fi
    done
    
    echo ""
    echo "Network Interfaces:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ip addr show "$ISOLATED_INTERFACE" | grep "inet " || echo "  $ISOLATED_INTERFACE: No IP assigned yet"
    ip addr show "$UPSTREAM_INTERFACE" | grep "inet " || echo "  $UPSTREAM_INTERFACE: No IP assigned yet"
    
    echo ""
    if [[ "$ISOLATED_KIND" == "wifi-ap" ]]; then
        echo "Access Point:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        SSID=$(python3 - <<PY
import yaml
with open(${CONFIG_FILE@Q}) as f:
    cfg = yaml.safe_load(f) or {}
print((cfg.get('ap') or {}).get('ssid', 'Unknown'))
PY
)
        echo "  SSID: $SSID"
        echo "  Connect devices to test the AP on $ISOLATED_INTERFACE"
    else
        echo "Isolated Ethernet Segment:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Isolated interface: $ISOLATED_INTERFACE"
        echo "  Upstream interface: $UPSTREAM_INTERFACE"
    fi
    
    echo ""
    echo "Web Dashboard:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Access via SSH tunnel:"
    echo "  ssh -L 5006:localhost:5006 paul@$(hostname -I | awk '{print $1}')"
    echo "  Then browse to: http://localhost:5006"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    banner
    
    check_root
    check_config
    
    log_info "Starting installation..."
    echo ""
    
    step_install_packages
    step_create_directories
    step_copy_files
    load_topology_from_config
    step_setup_python_env
    step_enable_ip_forwarding
    step_disable_default_services
    step_generate_configs
    step_install_systemd_services
    step_start_services
    step_verify_installation
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    log_success "Network Isolator installation complete!"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    log_info "Next steps:"
    echo "  1. Connect devices to the AP (SSID from config)"
    echo "  2. Access dashboard via SSH tunnel (see above)"
    echo "  3. Monitor traffic in /var/log/PerimeterControl/traffic.log"
    echo "  4. View captures in /mnt/PerimeterControl/captures/"
    echo ""
    log_info "Useful commands:"
    echo "  sudo systemctl status isolator"
    echo "  sudo systemctl reload isolator  # Reload config"
    echo "  sudo journalctl -u isolator -f  # View logs"
    echo "  iw dev wlan0 station dump       # Show connected clients"
    echo ""
}

main "$@"
