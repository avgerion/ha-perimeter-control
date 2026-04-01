# Initial Setup — Raspberry Pi Network Isolator

This guide walks through setting up a Raspberry Pi 3 from scratch as a Network Isolator appliance using Raspberry Pi Imager.

## Prerequisites

### Hardware
- **Raspberry Pi 3** (Model B or B+)
- **microSD card** (16GB minimum, 32GB+ recommended for captures)
- **USB drive** for portable config and captures (32GB+ recommended)
- **Ethernet cable** for WAN connection
- **Power supply** (2.5A minimum)
- **Optional:** USB WiFi adapter for bridge mode (see [BRIDGE-MODE.md](BRIDGE-MODE.md))

### Software
- **Raspberry Pi Imager** (download from https://www.raspberrypi.com/software/)
- **SSH client** on your computer:
  - Windows: Built into Windows 10/11 or install via `winget install Microsoft.OpenSSH.Beta`
  - Mac/Linux: Pre-installed

### Network Requirements
- Ethernet connection to your router/upstream network
- Available subnet for the AP (default: `192.168.50.0/24`)

## Step 1: Write Raspberry Pi OS with Imager

### 1.1 Launch Raspberry Pi Imager

Download and run **Raspberry Pi Imager** from https://www.raspberrypi.com/software/

### 1.2 Choose OS

Click **"Choose OS"** and select:
- **Raspberry Pi OS (64-bit)** 
- Recommended: **Raspberry Pi OS Lite (64-bit)** — no desktop environment, ideal for headless server

### 1.3 Choose Storage

Click **"Choose Storage"** and select your microSD card.

### 1.4 Configure Advanced Options (CRITICAL!)

**Click the ⚙️ gear icon** (or press `Ctrl+Shift+X`) to access advanced options.

**Configure the following:**

#### Hostname
- ✅ **Set hostname:** `isolator` (or `isolator.local`)
- This allows you to connect via `ssh pi@isolator.local` instead of finding the IP

#### Enable SSH
- ✅ **Enable SSH**
- Choose: **"Use password authentication"** (or use public-key if you prefer)
- This is **ESSENTIAL** — without SSH enabled, you'd need to connect a monitor/keyboard

#### Set Username and Password
- ✅ **Set username and password**
- Username: `pi` (traditional, but you can use anything)
- Password: Choose a secure password
- **Remember this password!** You'll need it for SSH access

#### Configure Wireless LAN (Optional)
- If you want the Pi to connect to WiFi initially for setup (before it becomes an AP):
  - ✅ **Configure wireless LAN**
  - SSID: Your current WiFi network
  - Password: Your WiFi password
  - Country: Your country code (e.g., `US`, `GB`, `DE`)
- **Note:** The isolator will later *host* its own AP on `wlan0`, so this is only for initial setup convenience

#### Locale Settings
- ✅ **Set locale settings**
- Time zone: Your timezone
- Keyboard layout: Your keyboard layout

#### Disable Telemetry (Recommended)
- ✅ **Disable telemetry**

### 1.5 Write to SD Card

Click **"Write"** and confirm. This will:
1. Download Raspberry Pi OS
2. Write it to the microSD card
3. Apply your advanced settings

Wait for the process to complete (5-10 minutes).

### 1.6 Eject and Insert

- Safely eject the microSD card
- Insert it into your Raspberry Pi 3
- Connect ethernet cable to `eth0`
- Power on the Pi

## Step 2: First Boot and SSH Connection

### 2.1 Wait for Boot

The Pi will:
1. Boot for the first time (takes 30-60 seconds)
2. Resize the filesystem
3. Apply your Imager settings
4. Reboot automatically
5. Enable SSH service

**Total first boot time: ~2-3 minutes**

### 2.2 Find the Pi on Your Network

**Option A: Use hostname (if mDNS works)**
```bash
ping isolator.local
```

If this works, you can skip to SSH connection.

**Option B: Check your router's DHCP client list**
- Log into your router's admin interface
- Look for a device named "isolator" or "raspberrypi"
- Note its IP address

**Option C: Network scan (Windows)**
```powershell
# Scan your local network (replace 192.168.1.0 with your subnet)
1..254 | ForEach-Object { Test-Connection -ComputerName "192.168.1.$_" -Count 1 -Quiet } | Where-Object { $_ }
```

**Option D: Network scan (Linux/Mac)**
```bash
# Install nmap if needed
sudo apt install nmap  # Linux
brew install nmap      # Mac

# Scan your network
nmap -sn 192.168.1.0/24 | grep -i raspberry
```

### 2.3 SSH into the Pi

Once you know the hostname or IP:

```bash
# Using hostname (preferred)
ssh pi@isolator.local

# Or using IP address
ssh pi@192.168.1.xxx
```

**First connection will show a security prompt:**
```
The authenticity of host 'isolator.local' can't be established.
ECDSA key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no)?
```

Type `yes` and press Enter.

Enter the password you set in Raspberry Pi Imager.

**You should see:**
```
Linux isolator 6.1.0-rpi7-rpi-v8 #1 SMP PREEMPT Debian ...
...
pi@isolator:~ $
```

🎉 **Success!** You're connected via SSH.

## Step 3: Initial Pi Configuration

### 3.1 Update the System

```bash
# Update package lists
sudo apt update

# Upgrade all packages (may take 5-10 minutes)
sudo apt upgrade -y
```

### 3.2 Install Essential Tools

```bash
# Development tools
sudo apt install -y git python3-pip python3-venv

# Network tools
sudo apt install -y hostapd dnsmasq nftables conntrack tcpdump wireshark-common

# For Bokeh dashboard
sudo apt install -y python3-dev build-essential

# Text editor (choose one or install both)
sudo apt install -y nano vim
```

### 3.3 Configure USB Drive Mount Point

```bash
# Create mount point
sudo mkdir -p /mnt/isolator

# Get USB drive UUID (plug in USB drive first)
sudo blkid

# Look for your USB drive (e.g., /dev/sda1)
# Note the UUID value

# Edit fstab to auto-mount USB drive
sudo nano /etc/fstab

# Add this line (replace UUID with yours):
# UUID=YOUR-UUID-HERE /mnt/isolator ext4 defaults,nofail 0 2

# Or for exFAT (Windows-compatible):
# UUID=YOUR-UUID-HERE /mnt/isolator exfat defaults,nofail,uid=1000,gid=1000 0 0

# Mount the drive
sudo mount -a

# Verify
df -h /mnt/isolator
```

### 3.4 Set Up Isolator Directory Structure

```bash
# Create directories on USB drive
sudo mkdir -p /mnt/isolator/conf
sudo mkdir -p /mnt/isolator/captures
sudo mkdir -p /mnt/isolator/logs

# Set ownership
sudo chown -R pi:pi /mnt/isolator

# Create symlinks for easy access
sudo ln -s /mnt/isolator/conf /etc/isolator
sudo ln -s /mnt/isolator/logs /var/log/isolator
```

## Step 4: Clone Network Isolator Repository

```bash
# Clone the repository
cd ~
git clone https://github.com/avgerion/ha-perimeter-control.git
# Or if you copied files manually:
# scp -r ./NetworkIsolator pi@isolator.local:~/

# Navigate to the project
cd NetworkIsolator

# Copy default config to USB drive
cp config/isolator.conf.yaml /mnt/isolator/conf/

# Create Python virtual environment for dashboard
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r server/requirements.txt
```

## Step 5: Configure Static IP for eth0 (Optional but Recommended)

Give the Pi a predictable IP on your upstream network:

```bash
# Edit dhcpcd configuration
sudo nano /etc/dhcpcd.conf

# Add at the end (adjust for your network):
interface eth0
static ip_address=192.168.1.200/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

Reboot to apply:
```bash
sudo reboot
```

Wait 30 seconds, then reconnect:
```bash
ssh pi@192.168.1.200  # or ssh pi@isolator.local
```

## Step 6: Run Setup Script (Phase 2 - Coming Soon)

Once the setup script is complete, you'll run:

```bash
cd ~/NetworkIsolator
sudo bash server/setup-isolator.sh --config /mnt/isolator/conf/isolator.conf.yaml
```

This will:
- Configure `hostapd` for WiFi AP
- Set up `dnsmasq` for DHCP
- Generate and apply `nftables` rules
- Create systemd services
- Start the web dashboard

## Step 7: Enable Web Dashboard

```bash
# Copy systemd service
sudo cp ~/NetworkIsolator/server/isolator-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start dashboard
sudo systemctl enable isolator-dashboard
sudo systemctl start isolator-dashboard

# Check status
sudo systemctl status isolator-dashboard
```

## Step 8: Access the Dashboard

From your Windows/Mac/Linux machine:

```bash
# Create SSH tunnel
ssh -L 5006:localhost:5006 pi@isolator.local
```

Open browser to: `http://localhost:5006`

## Security Hardening (Recommended)

### Change Default Password

```bash
# On the Pi
passwd
```

### Set Up SSH Key Authentication (No Password Required)

**On your Windows/Mac/Linux machine:**
```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy public key to Pi
ssh-copy-id pi@isolator.local
```

**Test key-based login:**
```bash
ssh pi@isolator.local
# Should log in without password prompt
```

**Disable password authentication (optional, after key works):**
```bash
# On the Pi
sudo nano /etc/ssh/sshd_config

# Find and change:
# PasswordAuthentication no
# PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart sshd
```

### Enable Firewall on eth0 (Upstream Interface)

```bash
# The isolator's nftables rules will handle this,
# but for initial setup, you can use ufw:
sudo apt install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

## Troubleshooting

### Can't Connect via SSH

**Check if SSH is running:**
```bash
# If you have monitor/keyboard access:
sudo systemctl status ssh

# Restart SSH
sudo systemctl restart ssh
```

**If hostname doesn't work:**
- Use IP address instead: `ssh pi@192.168.1.xxx`
- Check if mDNS/Avahi is running: `sudo systemctl status avahi-daemon`

### Imager Settings Not Applied

If SSH or hostname wasn't configured:
1. Connect monitor and keyboard to Pi
2. Log in with default credentials (if you didn't set custom ones, try `pi` / `raspberry`)
3. Run: `sudo raspi-config`
4. Enable SSH: **Interface Options → SSH → Enable**
5. Change hostname: **System Options → Hostname**

### USB Drive Not Mounting

```bash
# Check if drive is detected
lsblk

# Check filesystem type
sudo blkid /dev/sda1

# Format if needed (WARNING: erases data!)
sudo mkfs.ext4 /dev/sda1

# Try manual mount
sudo mount /dev/sda1 /mnt/isolator
```

### WiFi Not Working

If the Pi's built-in WiFi isn't detected:
```bash
# Check WiFi interface
iw dev

# Should show wlan0

# If not, check if rfkill is blocking:
rfkill list

# Unblock if needed:
sudo rfkill unblock wifi
```

## Next Steps

1. ✅ Pi is running with SSH enabled
2. ✅ USB drive mounted at `/mnt/isolator`
3. ✅ Repository cloned
4. 🔄 Configure `isolator.conf.yaml` for your network
5. 🔄 Run setup script (when Phase 2 is complete)
6. ✅ Access web dashboard
7. 🔄 Connect devices to the AP
8. 🔄 Monitor and capture traffic

## Quick Reference

**Essential Commands:**
```bash
# Check isolator service status
sudo systemctl status isolator

# Reload configuration
sudo systemctl reload isolator

# View logs
sudo journalctl -u isolator -f

# Check connected devices
cat /var/lib/misc/dnsmasq.leases

# Access from Windows (PowerShell)
ssh -L 5006:localhost:5006 pi@isolator.local
```

See [SSH-QUICK-REFERENCE.md](SSH-QUICK-REFERENCE.md) for complete command reference.

## Resources

- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
- [hostapd Documentation](https://w1.fi/hostapd/)
- [nftables Wiki](https://wiki.nftables.org/)
- [Bokeh Documentation](https://docs.bokeh.org/)
