# Perimeter Control HA Integration: Network Architecture & Configuration Guide

> **For Your Installation**: Understanding the network topology is critical for correct setup and troubleshooting.

---

## Architecture Overview

### The Port Confusion Problem (And Why It's Actually OK)

#### What You Might Think ❌
```
Multiple services → Multiple ports (8080, 8081, 8082, ...)
Website → photo_booth on 8080
Website → wildlife_monitor on 8081  
Website → ble_gatt_repeater on 8082
```

#### What Actually Happens ✅
```
Multiple services → Single Supervisor endpoint (port 8080)
Website → api/v1/services/photo_booth on 8080
Website → api/v1/services/wildlife_monitor on 8080  
Website → api/v1/services/ble_gatt_repeater on 8080
```

### Real Architecture

```
┌─ Home Assistant (192.168.69.X) ─────────────────────────┐
│  HA Dashboard with Perimeter Control Cards              │
│  ├─ Service Access Card for photo_booth               │
│  ├─ Service Access Card for wildlife_monitor          │
│  ├─ Service Access Card for ble_gatt_repeater         │
│  └─ Service Access Card for network_isolator          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/HTTPS
                         v
        Isolator Supervisor (port: 8080)
        ├─ /api/v1/services  (list all services)
        ├─ /api/v1/services/photo_booth/access  (edit photo_booth)
        ├─ /api/v1/services/wildlife_monitor/access  (edit wildlife_monitor)
        ├─ /api/v1/services/ble_gatt_repeater/access
        ├─ /api/v1/services/network_isolator/access
        ├─ /api/v1/services/pawr_esl_ap/access
        └─ /api/v1/node/features  (hardware info)
```

**Key Point**: All services are accessed through ONE Supervisor port, not different ports.

---

## Network Configuration Patterns

### Pattern 1: Single Pi (Most Common)

**Setup**: One Raspberry Pi running Isolator Supervisor

```yaml
# All services point to the SAME Pi, SAME port
cards:
  - type: custom:perimeter-control-card
    service_id: photo_booth
    api_base_url: http://192.168.69.11:8080  # Pi's internal IP

  - type: custom:perimeter-control-card
    service_id: wildlife_monitor
    api_base_url: http://192.168.69.11:8080  # Same Pi, same port

  - type: custom:perimeter-control-card
    service_id: network_isolator
    api_base_url: http://192.168.69.11:8080  # Same Pi, same port
```

**How to Find Your Pi's IP**:
```bash
# On your Pi:
hostname -I
# Output: 192.168.69.11 (or similar)

# From HA terminal if on same network:
ping isolator-pi.local
# Or use your router's admin page to find DHCP client list
```

### Pattern 2: Multiple Pis (Fleet Setup)

**Setup**: Multiple Raspberry Pis, each running Isolator Supervisor

```yaml
# Each Pi has its own Supervisor on its own IP
# But each Supervisor might use the same port (8080)

cards:
  # Services on PRIMARY Pi (pi-1)
  - type: custom:perimeter-control-card
    service_id: photo_booth
    api_base_url: http://pi-1.local:8080  # Pi-1, port 8080

  - type: custom:perimeter-control-card
    service_id: wildlife_monitor
    api_base_url: http://pi-1.local:8080  # Pi-1, port 8080

  # Services on SECONDARY Pi (pi-2)
  - type: custom:perimeter-control-card
    service_id: ble_gatt_repeater
    api_base_url: http://pi-2.local:8080  # Pi-2, port 8080 (different physical device!)

  - type: custom:perimeter-control-card
    service_id: network_isolator
    api_base_url: http://pi-2.local:8080  # Pi-2, port 8080
```

**Key**: Same port (8080) on different devices ✅  
**Not**: Same IP with different ports ❌

---

## Finding Your Supervisor Configuration

### Step 1: Verify Supervisor is Running

```bash
# On your Pi:
ssh pi@192.168.69.11

# Check if supervisor is running:
sudo systemctl status isolator-supervisor

# Output should show:
# ● isolator-supervisor.service - Isolator Supervisor
#      Loaded: loaded (...)
#      Active: active (running) since...
#        Main PID: 12345 (python3)
```

### Step 2: Verify API Port

```bash
# On your Pi, check the config:
cat /opt/isolator/config/isolator.conf.yaml | grep -A 5 api:

# Or check the listening port:
sudo netstat -tlnp | grep python3
# Look for lines like: tcp  ...  0.0.0.0:8080  0.0.0.0:*  LISTEN  pid/python3

# Or from HA, try to reach it:
curl http://192.168.69.11:8080/api/v1/services
# Should return JSON, not "Connection refused"
```

### Step 3: Determine Your Network URL

**For devices on the same local network**, choose ONE:

| Method | Example | Advantages | Disadvantages |
|--------|---------|------------|---------------|
| **IP Address** | `http://192.168.69.11:8080` | Fastest, most reliable | Changes if DHCP lease renews |
| **mDNS Hostname** | `http://pi-name.local:8080` | Stable, human-readable | Requires mDNS setup, slightly slower |
| **DNS Name** | `http://isolator-pi.home.local:8080` | Most stable if static | Requires DNS configuration |
| **Reverse Proxy** | `http://isolator.home.local:8080` | Single URL for fleet | Requires separate proxy server |

**Recommendation**: Use **mDNS hostname** (`pi-name.local`) or **static IP + hostname**

**How to set hostname**:
```bash
# On your Pi:
sudo hostnamectl set-hostname isolator-primary
# Restart for mDNS to pick it up
sudo systemctl restart avahi-daemon
```

Then use: `http://isolator-primary.local:8080`

---

## Configuration Issues & Solutions

### Issue 1: Hardcoded IP (Original Problem)

**Problem**: 
```yaml
api_base_url: http://192.168.69.11:8080  # My IP, not yours!
```

**Solution**: Use variables or environment-specific configs

#### Option A: Home Assistant Secrets (Recommended)

Create `secrets.yaml`:
```yaml
isolator_primary_ip: 192.168.69.11
isolator_primary_port: 8080
```

Use in dashboard:
```yaml
- type: custom:perimeter-control-card
  service_id: photo_booth
  api_base_url: http://!secret isolator_primary_ip:!secret isolator_primary_port
```

**Note**: This doesn't work in Lovelace YAML directly. Use HA's built-in substitution:

#### Option B: Template (Better for Lovelace)

```yaml
- type: custom:perimeter-control-card
  service_id: photo_booth
  api_base_url: "{{ 'http://isolator-pi.local:8080' }}"
  # Replace with YOUR Pi's hostname
```

#### Option C: Environment-Specific Files

Create separate dashboard files per environment:
- `lovelace-home.yaml` (home network, mDNS)
- `lovelace-vpn.yaml` (remote access, public IP)
- `lovelace-staging.yaml` (test config)

---

### Issue 2: HTTP vs HTTPS

**Local Network**: Use HTTP (simpler, HA and Pi on same network)
```yaml
api_base_url: http://192.168.69.11:8080
```

**Remote Access or Strict Networks**: Use HTTPS (requires certificate)
```yaml
api_base_url: https://isolator.example.com:8443
# Requires:
# - Let's Encrypt or self-signed certificate
# - Supervisor configured with TLS
# - Port 8443 or custom port
```

**Check if Supervisor supports HTTPS**:
```bash
# On your Pi:
grep -A 10 "server:" /opt/isolator/config/isolator.conf.yaml
# Look for "ssl:" or "tls:" section
```

---

### Issue 3: Firewall & Port Access

**Symptom**: "Cannot reach API" or timeout error

**Troubleshoot**:

```bash
# 1. Check port is open on Pi:
sudo ufw status numbered  # Check UFW (Uncomplicated Firewall)
sudo ufw allow 8080       # Allow port if needed

# 2. Check from HA machine:
curl -v http://192.168.69.11:8080/api/v1/services
# Look for "Connected" or "Connection refused"

# 3. Check if on different networks:
ping 192.168.69.11
# If unreachable, Pi is on different network or behind firewall

# 4. If remote access: Check router port forwarding
# Forward external port (e.g., 8443) to Pi:8080
```

---

### Issue 4: CORS Issues (Remote/Different Origin)

**Symptom**: Browser console shows "CORS error" or "blocked by CORS policy"

**Cause**: Default CORS only allows requests from same origin

**Solutions**:

1. **If HA is on same device as Supervisor** (localhost):
   - Use `http://localhost:8080` or `http://127.0.0.1:8080`
   - CORS whitelisted automatically

2. **If HA is on different device**:
   - Supervisor must have CORS configured

   ```bash
   # Edit Supervisor config:
   sudo nano /opt/isolator/config/isolator.conf.yaml
   
   # Add CORS section:
   server:
     cors:
       allowed_origins:
         - "http://192.168.69.10:8123"  # HA IP:port
         - "http://ha.local:8123"
         - "https://example.com"
   
   # Restart:
   sudo systemctl restart isolator-supervisor
   ```

3. **If using reverse proxy**:
   - Proxy should handle CORS headers
   ```nginx
   add_header 'Access-Control-Allow-Origin' '$http_origin' always;
   add_header 'Access-Control-Allow-Credentials' 'true' always;
   ```

---

### Issue 5: Multiple Supervisors on Same Host (Port Conflict)

**Scenario**: Two Supervisors on same Pi, need different ports

**Solution**: Use different ports in config

```bash
# Supervisor 1 config:
# /opt/isolator/config/isolator.conf.yaml
server:
  port: 8080

# Supervisor 2 config (different directory):
# /opt/isolator2/config/isolator.conf.yaml
server:
  port: 8081
```

Then in HA:
```yaml
- type: custom:perimeter-control-card
  service_id: photo_booth
  api_base_url: http://192.168.69.11:8080  # Supervisor 1

- type: custom:perimeter-control-card
  service_id: archive
  api_base_url: http://192.168.69.11:8081  # Supervisor 2 (different port!)
```

---

### Issue 6: Timeout & Slow Networks

**Symptom**: Cards show "timeout" after 10 seconds even though API works

**Solutions**:

1. Check network latency:
   ```bash
   ping -c 4 192.168.69.11
   # Look for latency (ms)
   # If > 100ms, increase timeout
   ```

2. Increase timeout in card:
   ```yaml
   - type: custom:perimeter-control-card
     service_id: photo_booth
     api_base_url: http://192.168.69.11:8080
     api_timeout_ms: 20000  # 20 seconds instead of 10
   ```

3. Check Supervisor performance:
   ```bash
   # On Pi:
   free -h  # Memory usage
   df -h    # Disk space
   top -b -n1 | head -20  # CPU usage
   ```

---

### Issue 7: Service Discovery

**Problem**: Can't find Supervisor IP on first setup

**Solution: Automated Discovery**

```bash
#!/bin/bash
# Find all Isolator Supervisors on local network:

# Method 1: mDNS (requires avahi)
avahi-browse -all -p -r | grep isolator

# Method 2: Manual port scan
for i in {1..254}; do
  timeout 0.5 bash -c "echo >/dev/tcp/192.168.69.$i/8080" 2>/dev/null && \
  echo "Supervisor found: 192.168.69.$i:8080"
done

# Method 3: Router/DHCP server
# Access router admin panel, look in DHCP client list
```

---

### Issue 8: Authentication & API Keys

**Current**: No authentication (only for local networks)

**If adding authentication later**:

```yaml
# This will be added in future versions:
- type: custom:perimeter-control-card
  service_id: photo_booth
  api_base_url: http://192.168.69.11:8080
  api_token: !secret isolator_api_token  # Future feature
  api_auth_method: bearer  # or basic, or custom
```

**Current workaround for remote access**:
- Use reverse proxy with authentication
- Or VPN to access HA UI only from home network

---

## Configuration Template

### For Single Pi (Most Common Setup)

Save this as `lovelace-isolator-single.yaml`:

```yaml
# Replace THESE with your actual values:
# - SUPERVISOR_IP: Your Pi's IP or hostname (e.g., 192.168.69.11 or isolator-pi.local)
# - SUPERVISOR_PORT: Supervisor port (usually 8080, check with: netstat -tlnp | grep python3)

title: Isolator Network Control
path: isolator
icon: mdi:shield-network

views:
  - title: Services
    path: services
    cards:
      - type: markdown
        content: |
          # Isolator Service Management
          
          **Supervisor Endpoint**: http://SUPERVISOR_IP:SUPERVISOR_PORT
          
          Tip: Verify access with `curl http://SUPERVISOR_IP:SUPERVISOR_PORT/api/v1/services`

      - type: custom:perimeter-control-card
        title: "📸 Photo Booth"
        service_id: photo_booth
        api_base_url: http://SUPERVISOR_IP:SUPERVISOR_PORT
        api_timeout_ms: 10000

      - type: custom:perimeter-control-card
        title: "🦁 Wildlife Monitor"
        service_id: wildlife_monitor
        api_base_url: http://SUPERVISOR_IP:SUPERVISOR_PORT
        api_timeout_ms: 10000

      - type: custom:perimeter-control-card
        title: "📡 BLE GATT Repeater"
        service_id: ble_gatt_repeater
        api_base_url: http://SUPERVISOR_IP:SUPERVISOR_PORT
        api_timeout_ms: 10000

      - type: custom:perimeter-control-card
        title: "🏷️ ESL Access Point"
        service_id: pawr_esl_ap
        api_base_url: http://SUPERVISOR_IP:SUPERVISOR_PORT
        api_timeout_ms: 10000

      - type: custom:perimeter-control-card
        title: "🔒 Network Isolator"
        service_id: network_isolator
        api_base_url: http://SUPERVISOR_IP:SUPERVISOR_PORT
        api_timeout_ms: 10000
```

---

## Verification Checklist

Before deployment, verify:

- [ ] Supervisor is running: `sudo systemctl status isolator-supervisor` → "active (running)"
- [ ] API responds: `curl http://SUPERVISOR_IP:SUPERVISOR_PORT/api/v1/services` → JSON response
- [ ] Services listed: Response contains `"photo_booth"`, `"wildlife_monitor"`, etc.
- [ ] CORS allowed: If HA on different machine, CORS configured in isolator.conf.yaml
- [ ] Firewall open: `sudo ufw status` and `sudo ufw allow SUPERVISOR_PORT`
- [ ] Network reachable: `ping SUPERVISOR_IP` from HA machine
- [ ] Timeout appropriate: `api_timeout_ms` set based on network latency

---

## Emergency Debugging

If cards don't load:

### Step 1: Browser Console
```javascript
// F12 → Console in HA dashboard

// Check for CORS errors:
// "Access-Control-Allow-Origin missing"
// → CORS not configured on Supervisor side

// Check for timeout:
// "[Isolator Safe Loader] Health check timeout"
// → API not responding, increase timeout or check Supervisor

// Check for connection errors:
// "Failed to fetch"
// → Check IP, port, firewall, network connectivity
```

### Step 2: HA Logs
```
Settings → Developer Tools → Logs
Search for "isolator" or "custom:isolator"
```

### Step 3: Supervisor Logs
```bash
ssh pi@SUPERVISOR_IP
sudo journalctl -u isolator-supervisor -f  # Follow logs
sudo journalctl -u isolator-supervisor -n 50  # Last 50 entries
```

### Step 4: Network Test
```bash
# From HA machine:
curl -v http://SUPERVISOR_IP:SUPERVISOR_PORT/api/v1/services

# Check response headers for CORS:
# Access-Control-Allow-Origin: *
# (or specific value like http://ha-ip:8123)
```

---

## Summary

**Remember**:
- All services on a Pi share ONE Supervisor port (usually 8080)
- Each Pi needs its own IP (or hostname)
- Use hostnames (`pi-name.local`) instead of IPs for stability
- Verify configuration with `curl` before HA deployment
- Check browser console and HA logs first when troubleshooting

**You now understand the architecture. Deploy with confidence! 🚀**

