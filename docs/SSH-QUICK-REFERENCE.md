# SSH Quick Reference — Network Isolator

This file contains commonly used SSH commands for remote management of the Network Isolator from your Windows/Mac/Linux machine.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Connection](#connection)
- [SSH Key Management](#ssh-key-management) ⭐ **Complete key generation, sharing, and storage guide**
- [Configuration Management](#configuration-management)
- [Monitoring](#monitoring)
- [Packet Captures](#packet-captures)
- [Bridge Mode](#bridge-mode)
- [System Maintenance](#system-maintenance)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)
- [Useful Aliases](#useful-aliases)
- [PowerShell Functions](#windows-powershell-functions)

## Prerequisites

**Windows:** Install OpenSSH Client
```powershell
# Install via winget
winget install Microsoft.OpenSSH.Beta

# Or via Windows Settings:
# Settings > Apps > Optional Features > Add OpenSSH Client
```

**Mac/Linux:** SSH is pre-installed

## Connection

### Basic SSH Connection
```bash
ssh pi@isolator.local
```

### SSH with Port Forwarding (for Web Dashboard)
```bash
# Forward dashboard port to your local machine
ssh -L 5006:localhost:5006 pi@isolator.local

# Then browse to: http://localhost:5006
```

### Multiple Port Forwarding
```bash
# Dashboard + additional services
ssh -L 5006:localhost:5006 -L 8080:localhost:8080 pi@isolator.local
```

## SSH Key Management

SSH keys provide secure, password-less authentication. This section covers generating, sharing, and managing SSH keys for the Network Isolator.

### Why Use SSH Keys?

**Benefits:**
- ✅ **More secure** than passwords (2048-4096 bit encryption)
- ✅ **No password typing** — seamless login
- ✅ **Automation-friendly** — scripts can SSH without interaction
- ✅ **Revocable** — disable a key without changing other credentials
- ✅ **Multi-device** — different keys for laptop, desktop, phone

### SSH Key Basics

An SSH key pair consists of:
- **Private key** — stays on YOUR machine, NEVER share this
- **Public key** — copied to the Pi's `~/.ssh/authorized_keys` file

**File locations:**
- Windows: `C:\Users\YourName\.ssh\`
- Mac/Linux: `~/.ssh/`

### Generating SSH Keys

#### Recommended: Ed25519 (Modern, Fast, Secure)

**Windows PowerShell / Mac / Linux:**
```bash
# Generate Ed25519 key (recommended for 2024+)
ssh-keygen -t ed25519 -C "isolator-key-$(whoami)@$(hostname)"

# Output:
# Generating public/private ed25519 key pair.
# Enter file in which to save the key (C:\Users\YourName\.ssh\id_ed25519):
```

**Press Enter** to accept default location, or specify custom name:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/isolator_key -C "isolator-access"
```

**Passphrase prompt:**
```
Enter passphrase (empty for no passphrase):
```

**Best practice:** Use a strong passphrase (protects key if your laptop is stolen)

**Output files:**
- `id_ed25519` — Private key (keep secret!)
- `id_ed25519.pub` — Public key (safe to share)

#### Alternative: RSA (Universal Compatibility)

If you need compatibility with older systems:

```bash
# Generate 4096-bit RSA key
ssh-keygen -t rsa -b 4096 -C "isolator-key-rsa"
```

**Notes:**
- Ed25519 is faster and more secure than RSA
- Only use RSA if required by legacy systems
- Never use RSA keys smaller than 2048 bits

#### Windows-Specific: Using PuTTYgen

If you use PuTTY instead of OpenSSH:

1. Download **PuTTYgen** from https://www.putty.org/
2. Run PuTTYgen
3. Click **"Generate"** and move mouse randomly
4. Set **Key comment** to identify the key
5. **Set a passphrase** (highly recommended)
6. Save **private key** as `isolator_key.ppk`
7. Copy **public key** text from the window

### Copying Keys to the Pi

#### Method 1: ssh-copy-id (Easiest — Linux/Mac/Windows 10+)

```bash
# Copy your default key
ssh-copy-id pi@isolator.local

# Copy a specific key
ssh-copy-id -i ~/.ssh/isolator_key.pub pi@isolator.local

# Specify custom SSH port (if changed)
ssh-copy-id -i ~/.ssh/isolator_key.pub -p 2222 pi@isolator.local
```

**What this does:**
1. Connects to Pi via SSH (using password)
2. Appends your public key to `~/.ssh/authorized_keys`
3. Sets correct permissions automatically

#### Method 2: Manual Copy (Windows PowerShell)

```powershell
# Read your public key
$pubKey = Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"

# Connect and append to authorized_keys
ssh pi@isolator.local "mkdir -p ~/.ssh && echo '$pubKey' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

#### Method 3: Manual Copy via SCP

```bash
# Copy public key to Pi
scp ~/.ssh/id_ed25519.pub pi@isolator.local:~/temp_key.pub

# SSH to Pi and install
ssh pi@isolator.local
mkdir -p ~/.ssh
cat ~/temp_key.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
rm ~/temp_key.pub
exit
```

#### Method 4: Raspberry Pi Imager (Before First Boot)

In Raspberry Pi Imager's advanced settings (⚙️):
1. ✅ Enable SSH
2. Choose **"Allow public-key authentication only"**
3. Paste your **public key** content
4. Write SD card

Your key will be pre-installed on first boot!

### Testing Key Authentication

```bash
# Test connection (should NOT prompt for password)
ssh pi@isolator.local

# Verbose output to debug issues
ssh -v pi@isolator.local

# Test specific key
ssh -i ~/.ssh/isolator_key pi@isolator.local
```

**Success indicators:**
```
debug1: Offering public key: /home/user/.ssh/id_ed25519 RSA SHA256:...
debug1: Server accepts key: /home/user/.ssh/id_ed25519 RSA SHA256:...
debug1: Authentication succeeded (publickey).
```

### Best Practices for Key Management

#### 1. Use Different Keys for Different Purposes

```bash
# Work laptop key
ssh-keygen -t ed25519 -f ~/.ssh/work_isolator -C "work-laptop-isolator"

# Home desktop key
ssh-keygen -t ed25519 -f ~/.ssh/home_isolator -C "home-desktop-isolator"

# Tablet/phone key (if using Termux)
ssh-keygen -t ed25519 -f ~/.ssh/mobile_isolator -C "mobile-isolator"
```

**Why?** If one device is compromised, revoke only that key.

#### 2. Configure SSH Client for Multiple Keys

Create/edit `~/.ssh/config`:

```bash
# Isolator configuration
Host isolator
    HostName isolator.local
    User pi
    IdentityFile ~/.ssh/isolator_key
    LocalForward 5006 localhost:5006
    ServerAliveInterval 60

# Shortcut: now just type "ssh isolator"
```

**Windows:** `%USERPROFILE%\.ssh\config`

**Benefits:**
- Type `ssh isolator` instead of full command
- Auto-forward dashboard port
- Keep connection alive (prevents timeout)

#### 3. Set Correct Permissions

**Linux/Mac:**
```bash
# Private key: only you can read/write
chmod 600 ~/.ssh/id_ed25519

# Public key: readable by others
chmod 644 ~/.ssh/id_ed25519.pub

# SSH directory: only you can access
chmod 700 ~/.ssh
```

**Windows:** Use PowerShell:
```powershell
# Remove inheritance and set owner-only access
$keyPath = "$env:USERPROFILE\.ssh\id_ed25519"
icacls $keyPath /inheritance:r
icacls $keyPath /grant:r "$env:USERNAME:(R)"
```

#### 4. Use SSH Agent (Cache Passphrase)

Avoid typing passphrase repeatedly:

**Linux/Mac:**
```bash
# Start agent (usually runs automatically)
eval "$(ssh-agent -s)"

# Add key to agent (enter passphrase once)
ssh-add ~/.ssh/id_ed25519

# List loaded keys
ssh-add -l

# Add key permanently (survives reboot — macOS)
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

**Windows:**
```powershell
# Start SSH Agent service
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent

# Add key
ssh-add $env:USERPROFILE\.ssh\id_ed25519

# Verify
ssh-add -l
```

#### 5. Backup Your Keys Securely

**Option A: Encrypted USB Drive**
```bash
# Copy to encrypted USB drive
cp ~/.ssh/id_ed25519* /mnt/encrypted_usb/ssh_keys/

# Store in safe location (not in cloud storage!)
```

**Option B: Password Manager**

Some password managers (1Password, Bitwarden) support storing SSH keys:
- Store private key as "Secure Note"
- Never store unencrypted in Dropbox/OneDrive!

**Option C: Hardware Security Key**

Use a YubiKey or similar:
```bash
# Generate key on YubiKey (cannot be extracted)
ssh-keygen -t ed25519-sk -C "isolator-yubikey"
```

**Note:** YubiKey requires physical presence to authenticate (ultra-secure)

### Storing and Organizing Keys

#### Directory Structure

```
~/.ssh/
├── config                  # SSH client configuration
├── known_hosts            # Server fingerprints (auto-generated)
├── id_ed25519             # Default private key
├── id_ed25519.pub         # Default public key
├── isolator_key           # Isolator-specific private key
├── isolator_key.pub       # Isolator-specific public key
├── work_servers           # Work private key
├── work_servers.pub       # Work public key
└── authorized_keys        # Public keys that can connect TO this machine
```

#### Key Naming Convention

Use descriptive names:
```bash
# Format: purpose_hostname_keytype
~/.ssh/isolator_pi3_ed25519
~/.ssh/homelab_server_rsa
~/.ssh/work_jump_ed25519
```

### Sharing Keys with Team Members

#### Scenario: Multiple People Managing the Isolator

**Option 1: Each Person Has Their Own Key (Recommended)**

Each team member generates their own key and adds it to the Pi:

```bash
# Person A
ssh-copy-id -i ~/.ssh/alice_isolator.pub pi@isolator.local

# Person B
ssh-copy-id -i ~/.ssh/bob_isolator.pub pi@isolator.local

# On the Pi, authorized_keys will contain both:
pi@isolator:~ $ cat ~/.ssh/authorized_keys
ssh-ed25519 AAAAC3...alice... alice@laptop
ssh-ed25519 AAAAC3...bob... bob@desktop
```

**Benefits:**
- Individual accountability (who did what)
- Revoke one person's access without affecting others
- Each person uses their own passphrase

**Option 2: Shared Key (Not Recommended)**

If you must share a single key:

1. Generate key on secure machine
2. Encrypt private key before sharing:
   ```bash
   # Encrypt with GPG
   gpg -c ~/.ssh/shared_isolator
   
   # Share the .gpg file (via secure channel)
   # Recipient decrypts:
   gpg -d shared_isolator.gpg > ~/.ssh/shared_isolator
   chmod 600 ~/.ssh/shared_isolator
   ```
3. Share decryption password via separate channel (Signal, 1Password)

**Risks:** If one person leaves, must regenerate and redistribute key

### Revoking SSH Keys

#### Remove a Specific Key from the Pi

```bash
# SSH to Pi
ssh pi@isolator.local

# Edit authorized_keys
nano ~/.ssh/authorized_keys

# Delete the line with the unwanted key
# (Look for key comment to identify: user@hostname)

# Save and exit (Ctrl+X, Y, Enter)
```

#### Revoke All Keys and Start Fresh

```bash
# SSH to Pi (must have password auth enabled or backdoor access)
ssh pi@isolator.local

# Backup old keys
mv ~/.ssh/authorized_keys ~/.ssh/authorized_keys.backup

# Create empty file
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Now add only current/valid keys
```

### Troubleshooting SSH Keys

#### Problem: Still Prompting for Password

**Check 1: Is key loaded?**
```bash
ssh-add -l
# If empty, add your key:
ssh-add ~/.ssh/id_ed25519
```

**Check 2: Using correct key?**
```bash
# Specify key explicitly
ssh -i ~/.ssh/isolator_key pi@isolator.local
```

**Check 3: Is public key on Pi?**
```bash
ssh pi@isolator.local "cat ~/.ssh/authorized_keys"
# Should show your public key
```

**Check 4: Permissions on Pi**
```bash
ssh pi@isolator.local "ls -la ~/.ssh/"
# Should be:
# drwx------  2 pi pi 4096 ... .ssh/
# -rw-------  1 pi pi  XXX ... authorized_keys
```

**Fix permissions:**
```bash
ssh pi@isolator.local "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

#### Problem: Permission Denied (publickey)

**Check 5: Is pubkey auth enabled on Pi?**
```bash
ssh pi@isolator.local "grep -i PubkeyAuthentication /etc/ssh/sshd_config"
# Should be: PubkeyAuthentication yes
```

**Check 6: SSH server logs**
```bash
ssh pi@isolator.local "sudo tail -50 /var/log/auth.log | grep sshd"
# Look for error messages
```

#### Problem: Too Many Authentication Failures

If you have many keys in ssh-agent:

```bash
# SSH tries only your specific key
ssh -o IdentitiesOnly=yes -i ~/.ssh/isolator_key pi@isolator.local

# Or add to ~/.ssh/config:
Host isolator
    IdentitiesOnly yes
    IdentityFile ~/.ssh/isolator_key
```

### Advanced: Certificates vs Keys

For large deployments, consider SSH certificates:

```bash
# Certificate Authority signs user keys (beyond scope of this guide)
# Benefits: Centralized expiration, automatic trust
# See: https://man.openbsd.org/ssh-keygen#CERTIFICATES
```

### Security Checklist

- [ ] SSH keys generated with passphrase
- [ ] Private keys have 600 permissions (owner read/write only)
- [ ] Private keys backed up securely (encrypted)
- [ ] Different keys for different devices
- [ ] Old/unused keys removed from Pi's authorized_keys
- [ ] Password authentication disabled on Pi (after keys work)
- [ ] SSH agent configured to cache passphrase
- [ ] ~/.ssh/config configured for convenience
- [ ] Keys stored in password manager or encrypted backup

### Quick Reference Table

| Task | Command |
|------|---------|
| Generate Ed25519 key | `ssh-keygen -t ed25519 -C "comment"` |
| Generate RSA key | `ssh-keygen -t rsa -b 4096 -C "comment"` |
| Copy key to Pi | `ssh-copy-id pi@isolator.local` |
| Test key auth | `ssh -v pi@isolator.local` |
| Add key to agent | `ssh-add ~/.ssh/id_ed25519` |
| List agent keys | `ssh-add -l` |
| View public key | `cat ~/.ssh/id_ed25519.pub` |
| View Pi's keys | `ssh pi@isolator.local "cat ~/.ssh/authorized_keys"` |
| Remove key from agent | `ssh-add -d ~/.ssh/id_ed25519` |
| Clear all agent keys | `ssh-add -D` |

## Configuration Management

### Edit Config Remotely
```bash
# Open config in nano editor
ssh pi@isolator.local "sudo nano /mnt/isolator/conf/isolator.conf.yaml"

# Or download, edit locally, and upload:
scp pi@isolator.local:/mnt/isolator/conf/isolator.conf.yaml ./isolator.conf.yaml
# Edit locally...
scp ./isolator.conf.yaml pi@isolator.local:/mnt/isolator/conf/isolator.conf.yaml
```

### Reload Rules
```bash
# Apply config changes without disconnecting clients
ssh pi@isolator.local "sudo systemctl reload isolator"
```

### Restart Services
```bash
# Restart main isolator service
ssh pi@isolator.local "sudo systemctl restart isolator"

# Restart web dashboard
ssh pi@isolator.local "sudo systemctl restart isolator-dashboard"

# Restart all network services
ssh pi@isolator.local "sudo systemctl restart hostapd dnsmasq isolator"
```

## Monitoring

### View Live Logs
```bash
# Traffic log (JSON format)
ssh pi@isolator.local "tail -f /var/log/isolator/traffic.log"

# Dashboard log
ssh pi@isolator.local "tail -f /var/log/isolator/dashboard.log"

# System log
ssh pi@isolator.local "sudo journalctl -u isolator -f"
```

### Check Service Status
```bash
# All isolator services
ssh pi@isolator.local "systemctl status isolator isolator-dashboard hostapd dnsmasq"

# Quick status check
ssh pi@isolator.local "systemctl is-active isolator"
```

### Connected Devices
```bash
# List DHCP leases (connected devices)
ssh pi@isolator.local "cat /var/lib/misc/dnsmasq.leases"

# Show current WiFi clients
ssh pi@isolator.local "iw dev wlan0 station dump"
```

### Network Statistics
```bash
# Show nftables rules and counters
ssh pi@isolator.local "sudo nft list ruleset"

# Show connection tracking
ssh pi@isolator.local "sudo conntrack -L"

# Interface statistics
ssh pi@isolator.local "ip -s link show wlan0"
```

## Packet Captures

### Download Captures
```bash
# Download all captures
scp -r pi@isolator.local:/mnt/isolator/captures/ ./captures/

# Download specific device captures
scp -r pi@isolator.local:/mnt/isolator/captures/target-device/ ./target-device-captures/

# Download bridge captures
scp -r pi@isolator.local:/mnt/isolator/captures/bridge/ ./bridge-captures/
```

### Live Wireshark Streaming
```bash
# Stream to Wireshark on Windows
ssh pi@isolator.local "sudo cat /run/isolator/target-device.pipe" | "C:\Program Files\Wireshark\Wireshark.exe" -k -i -

# Stream to Wireshark on Mac/Linux
ssh pi@isolator.local "sudo cat /run/isolator/target-device.pipe" | wireshark -k -i -

# Stream bridge traffic
ssh pi@isolator.local "sudo cat /run/isolator/bridge.pipe" | wireshark -k -i -
```

### Start/Stop Captures
```bash
# Start capture for a device
ssh pi@isolator.local "sudo systemctl start isolator-capture@target-device"

# Stop capture
ssh pi@isolator.local "sudo systemctl stop isolator-capture@target-device"

# Check capture status
ssh pi@isolator.local "ps aux | grep tcpdump"
```

## Bridge Mode

### Enable Bridge Mode
```bash
# Edit config to enable bridge
ssh pi@isolator.local "sudo nano /mnt/isolator/conf/isolator.conf.yaml"
# Set bridge.enabled: true, configure target_ap

# Reload to activate
ssh pi@isolator.local "sudo systemctl reload isolator"
```

### Check Bridge Status
```bash
# Check wlan1 connection
ssh pi@isolator.local "iwconfig wlan1"

# Test connectivity to target device
ssh pi@isolator.local "ping -c 3 192.168.43.1"  # example target IP

# View bridge routing
ssh pi@isolator.local "ip route show"
```

### Bridge Captures
```bash
# Stream bridge traffic live
ssh pi@isolator.local "sudo cat /run/isolator/bridge.pipe" | wireshark -k -i -

# Download bridge captures
scp -r pi@isolator.local:/mnt/isolator/captures/bridge/ ./bridge-analysis/
```

## System Maintenance

### Check Disk Space
```bash
# Show disk usage
ssh pi@isolator.local "df -h /mnt/isolator"

# Show capture folder sizes
ssh pi@isolator.local "du -sh /mnt/isolator/captures/*"
```

### Clean Old Captures
```bash
# Delete captures older than 7 days
ssh pi@isolator.local "find /mnt/isolator/captures -name '*.pcap' -mtime +7 -delete"

# Delete all captures (careful!)
ssh pi@isolator.local "sudo rm -rf /mnt/isolator/captures/*"
```

### System Updates
```bash
# Update Pi OS
ssh pi@isolator.local "sudo apt update && sudo apt upgrade -y"

# Update dashboard dependencies
ssh pi@isolator.local "pip3 install --upgrade bokeh pandas pyyaml"
```

## Troubleshooting

### WiFi Not Working
```bash
# Check hostapd status
ssh pi@isolator.local "sudo systemctl status hostapd"

# Restart hostapd
ssh pi@isolator.local "sudo systemctl restart hostapd"

# Check WiFi interface
ssh pi@isolator.local "iw dev wlan0 info"
```

### Dashboard Not Loading
```bash
# Check dashboard service
ssh pi@isolator.local "sudo systemctl status isolator-dashboard"

# View dashboard logs
ssh pi@isolator.local "tail -100 /var/log/isolator/dashboard.log"

# Restart dashboard
ssh pi@isolator.local "sudo systemctl restart isolator-dashboard"
```

### Firewall Issues
```bash
# Check nftables rules
ssh pi@isolator.local "sudo nft list ruleset"

# Reload firewall rules
ssh pi@isolator.local "sudo systemctl reload isolator"

# Reset to default (careful!)
ssh pi@isolator.local "sudo nft flush ruleset"
```

## Power Management

### Safe Shutdown
```bash
# Shutdown Pi safely
ssh pi@isolator.local "sudo shutdown -h now"
```

### Reboot
```bash
# Reboot Pi
ssh pi@isolator.local "sudo reboot"
```

## Advanced: One-Liner Commands

### Get List of All MAC Addresses
```bash
ssh pi@isolator.local "awk '{print \$2}' /var/lib/misc/dnsmasq.leases | sort -u"
```

### Count Active Connections Per Device
```bash
ssh pi@isolator.local "sudo conntrack -L | awk '{print \$5}' | sort | uniq -c | sort -rn"
```

### Top 10 Most Accessed Remote IPs
```bash
ssh pi@isolator.local "sudo nft list ruleset | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | sort | uniq -c | sort -rn | head -10"
```

### Generate Traffic Report
```bash
ssh pi@isolator.local "tail -1000 /var/log/isolator/traffic.log | jq -r '.device_id' | sort | uniq -c | sort -rn"
```

## Security Best Practices

### Change Default Password

Always change the default password immediately after first login:

```bash
# On the Pi
ssh pi@isolator.local
passwd
# Enter current password
# Enter new password (twice)
```

### Use SSH Keys (See SSH Key Management Section Above)

SSH keys are far more secure than passwords. See the comprehensive **[SSH Key Management](#ssh-key-management)** section above for:
- Generating keys (Ed25519 recommended)
- Copying keys to the Pi
- Managing multiple keys
- Storage and backup best practices
- Troubleshooting

**Quick setup:**
```bash
# Generate key
ssh-keygen -t ed25519 -C "isolator-key"

# Copy to Pi
ssh-copy-id pi@isolator.local

# Test (should login without password)
ssh pi@isolator.local
```

### Disable Password Authentication (After Keys Work)

Once SSH keys are working, disable password auth for maximum security:

```bash
# Test key auth first!
ssh pi@isolator.local "echo 'Keys work!'"

# If successful, disable passwords
ssh pi@isolator.local "sudo nano /etc/ssh/sshd_config"
```

Find and change these lines:
```
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
```

Restart SSH:
```bash
ssh pi@isolator.local "sudo systemctl restart sshd"
```

**Important:** Keep a backup way to access (physical keyboard, or leave password auth enabled from LAN only)

### Restrict SSH to Local Network Only

Edit sshd_config to only accept connections from your LAN:

```bash
ssh pi@isolator.local "sudo nano /etc/ssh/sshd_config"
```

Add:
```
# Only allow SSH from local network
ListenAddress 192.168.1.200
# or
Match Address 192.168.1.0/24
    PasswordAuthentication yes
Match Address !192.168.1.0/24
    PasswordAuthentication no
    PubkeyAuthentication yes
```

### Use SSH Tunnel for Dashboard (Never Direct LAN)

Always access the dashboard via SSH tunnel:

```bash
# Good: Encrypted tunnel
ssh -L 5006:localhost:5006 pi@isolator.local

# Bad: Direct access (unencrypted on LAN)
# http://isolator.local:5006  ❌ Don't do this
```

### Enable Automatic Security Updates

```bash
ssh pi@isolator.local "sudo apt install unattended-upgrades"
ssh pi@isolator.local "sudo dpkg-reconfigure -plow unattended-upgrades"
```

### Regular Security Maintenance

```bash
# Update system monthly
ssh pi@isolator.local "sudo apt update && sudo apt upgrade -y"

# Review authorized SSH keys quarterly
ssh pi@isolator.local "cat ~/.ssh/authorized_keys"

# Check for failed login attempts
ssh pi@isolator.local "sudo grep 'Failed password' /var/log/auth.log | tail -20"

# Review active SSH sessions
ssh pi@isolator.local "who"
```

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc` for quick access:

```bash
# SSH aliases
alias issh='ssh pi@isolator.local'
alias idash='ssh -L 5006:localhost:5006 pi@isolator.local'
alias ilogs='ssh pi@isolator.local "tail -f /var/log/isolator/traffic.log"'
alias ireload='ssh pi@isolator.local "sudo systemctl reload isolator"'

# Capture download
alias icaptures='scp -r pi@isolator.local:/mnt/isolator/captures/ ./isolator-captures-$(date +%Y%m%d)/'

# Quick status
alias istatus='ssh pi@isolator.local "systemctl status isolator isolator-dashboard"'
```

## Windows PowerShell Functions

Add to your PowerShell profile (`$PROFILE`):

```powershell
# Quick SSH to isolator
function issh { ssh pi@isolator.local }

# SSH with dashboard tunnel
function idash { 
    ssh -L 5006:localhost:5006 pi@isolator.local
    Start-Process "http://localhost:5006"
}

# Download captures
function Get-IsolatorCaptures {
    $date = Get-Date -Format "yyyyMMdd"
    scp -r pi@isolator.local:/mnt/isolator/captures/ ".\isolator-captures-$date\"
}

# Reload config
function Reload-Isolator {
    ssh pi@isolator.local "sudo systemctl reload isolator"
}
```

---

## SSH Key Management Cheat Sheet

### Essential SSH Key Commands

```bash
# ── GENERATE KEYS ──────────────────────────────────────────────────────
# Ed25519 (recommended - fast, secure, modern)
ssh-keygen -t ed25519 -C "isolator-$(whoami)" -f ~/.ssh/isolator_key

# RSA (legacy compatibility)
ssh-keygen -t rsa -b 4096 -C "isolator-$(whoami)" -f ~/.ssh/isolator_rsa

# ── COPY TO PI ─────────────────────────────────────────────────────────
# Automatic (Linux/Mac/Windows 10+)
ssh-copy-id -i ~/.ssh/isolator_key.pub pi@isolator.local

# Manual (Windows PowerShell)
$key = Get-Content "$env:USERPROFILE\.ssh\isolator_key.pub"
ssh pi@isolator.local "mkdir -p ~/.ssh && echo '$key' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"

# ── TEST KEY AUTH ──────────────────────────────────────────────────────
# Should NOT prompt for password
ssh -i ~/.ssh/isolator_key pi@isolator.local "echo 'Success!'"

# Verbose debugging
ssh -vv -i ~/.ssh/isolator_key pi@isolator.local

# ── SSH AGENT (Cache Passphrase) ───────────────────────────────────────
# Linux/Mac: Add key to agent
ssh-add ~/.ssh/isolator_key

# Windows: Start agent service first
Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\isolator_key

# List loaded keys
ssh-add -l

# ── SSH CONFIG (No More Typing!) ───────────────────────────────────────
# Create/edit ~/.ssh/config (Windows: %USERPROFILE%\.ssh\config)
cat >> ~/.ssh/config << 'EOF'
Host isolator
    HostName isolator.local
    User pi
    IdentityFile ~/.ssh/isolator_key
    LocalForward 5006 localhost:5006
    ServerAliveInterval 60
EOF

# Now just type: ssh isolator

# ── VIEW KEYS ──────────────────────────────────────────────────────────
# Your public key
cat ~/.ssh/isolator_key.pub

# Pi's authorized keys
ssh pi@isolator.local "cat ~/.ssh/authorized_keys"

# ── PERMISSIONS ────────────────────────────────────────────────────────
# Linux/Mac: Fix key permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub

# Windows: Owner-only access (PowerShell as Admin)
icacls "$env:USERPROFILE\.ssh\id_ed25519" /inheritance:r
icacls "$env:USERPROFILE\.ssh\id_ed25519" /grant:r "$env:USERNAME:(R)"

# ── REVOKE KEY ─────────────────────────────────────────────────────────
# Remove from Pi's authorized_keys
ssh pi@isolator.local
nano ~/.ssh/authorized_keys
# Delete the line with unwanted key, save, exit

# ── BACKUP KEYS ────────────────────────────────────────────────────────
# Encrypt before backing up (GPG)
gpg -c ~/.ssh/isolator_key
# Store isolator_key.gpg in secure location

# Decrypt when needed
gpg -d isolator_key.gpg > ~/.ssh/isolator_key
chmod 600 ~/.ssh/isolator_key
```

### Troubleshooting Quick Fix

```bash
# Still asking for password? Try this:
# 1. Check key is loaded
ssh-add -l

# 2. Add key if missing
ssh-add ~/.ssh/isolator_key

# 3. Fix permissions on Pi
ssh pi@isolator.local "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"

# 4. Disable strict host key checking (testing only!)
ssh -o StrictHostKeyChecking=no pi@isolator.local

# 5. View Pi's SSH logs for errors
ssh pi@isolator.local "sudo tail -50 /var/log/auth.log | grep sshd"
```

### Security Checklist

```bash
# [ ] Generate key with passphrase
ssh-keygen -t ed25519 -C "isolator-key"  # Enter strong passphrase

# [ ] Copy to Pi
ssh-copy-id pi@isolator.local

# [ ] Test key auth works
ssh pi@isolator.local "echo OK"

# [ ] Disable password auth on Pi
ssh pi@isolator.local "sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config"
ssh pi@isolator.local "sudo systemctl restart sshd"

# [ ] Backup private key (encrypted!)
gpg -c ~/.ssh/id_ed25519
# Store .gpg file securely

# [ ] Remove old/unused keys from Pi
ssh pi@isolator.local "nano ~/.ssh/authorized_keys"
```

---

**Pro Tip:** Keep this file open in a separate terminal/editor window for quick copy-paste access while working with the Network Isolator.
