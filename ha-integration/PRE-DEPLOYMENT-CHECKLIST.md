# Pre-Deployment Configuration Checklist

> **Before deploying to Home Assistant**, verify this checklist item by item. Each unchecked item is a risk.

---

## Section 1: Supervisor Discovery & Accessibility

### 1.1: Find Supervisor IP/Hostname

- [ ] **SSH to Pi and get IP**
  ```bash
  ssh pi@<your-pi-ip>
  hostname -I
  # Output: 192.168.69.11 (write this down)
  ```

- [ ] **Verify hostname is accessible via mDNS (Optional but Recommended)**
  ```bash
  # On Pi:
  hostnamectl status
  # Should show hostname

  # From HA machine:
  ping <hostname>.local
  # Should respond (if mDNS working)
  ```

- [ ] **Choose ONE URL format for your setup**:
  - [ ] IP address (e.g., `192.168.69.11:8080`) — fastest, DHCP-dependent
  - [ ] mDNS(e.g., `isolator-pi.local:8080`) — stable, recommended ✅
  - [ ] Public domain (e.g., `isolator.example.com:8443`) — remote access, requires HTTPS

### 1.2: Verify Supervisor Process

- [ ] **Check Supervisor is running**
  ```bash
  ssh pi@<pi-ip>
  sudo systemctl status isolator-supervisor
  # Should show: Active: active (running)
  ```

- [ ] **Check Supervisor is listening on expected port**
  ```bash
  ssh pi@<pi-ip>
  sudo netstat -tlnp | grep python3
  # Look for: tcp  ...  0.0.0.0:8080  ... LISTEN ...python3
  # Verify port (default 8080, might be different)
  ```

- [ ] **Check Supervisor has not stopped recently**
  ```bash
  ssh pi@<pi-ip>
  sudo systemctl status isolator-supervisor
  # Check "Active for:" duration — should be > current session
  ```

---

## Section 2: Network Connectivity & Firewall

### 2.1: Verify Network Path

- [ ] **Ping from HA to Pi**
  ```bash
  # From HA machine:
  ping <your-pi-ip>
  # Should respond (no timeout, no "unreachable")
  ```

- [ ] **Check firewall allows port 8080**
  ```bash
  # On Pi:
  sudo ufw status numbered
  # If UFW enabled, verify port 8080 is NOT blocked
  # If blocked:
  sudo ufw allow 8080
  ```

- [ ] **If HA and Pi on different networks, verify routing**
  ```bash
  # From HA machine:
  traceroute <pi-ip>
  # Verify path reaches Pi (< 15 hops)
  ```

- [ ] **If behind corporate/school network, check CORS restrictions**
  - [ ] CORS is explicitly blocked (you'll see CORS errors in browser console)
  - [ ] If yes, configure Supervisor CORS or use reverse proxy

### 2.2: Test API Baseline

- [ ] **Test API is accessible from wherever you are**
  ```bash
  # From HA machine:
  curl -v http://<your-pi-ip>:8080/api/v1/services
  
  # Expected:
  # HTTP/1.1 200 OK
  # Content-Type: application/json
  # { "services": { "photo_booth": {...}, ... } }
  
  # If you get:
  # "Connection refused" → Firewall/routing issue, port wrong
  # "Connection timeout" → Network unreachable or no route
  # "404 Not Found" → API path different, verify Supervisor version
  # "Unauthorized" → Authentication required (future feature)
  ```

- [ ] **Save API response for reference**
  ```bash
  curl http://<your-pi-ip>:8080/api/v1/services > /tmp/api-baseline.json
  cat /tmp/api-baseline.json  # Should show all services
  ```

---

## Section 3: Single vs Multi-Pi Configuration

### 3.1: Determine Your Topology

- [ ] **Single Pi (Most Common)**
  - [ ] All cards use `api_base_url: "http://<pi-ip>:8080"`
  - [ ] All services on same Pi share same port
  - Goes to **Section 4.1 (Single Pi Deployment)**

- [ ] **Multiple Pis (Fleet)**
  - [ ] First Pi: `http://pi-1.local:8080`
  - [ ] Second Pi: `http://pi-2.local:8080` (DIFFERENT IP, NOT different port!)
  - [ ] Third Pi: `http://pi-3.local:8080` (each Pi is different)
  - Goes to **Section 4.2 (Multi-Pi Deployment)**

- [ ] **If Multiple Pis**: Verify each is accessible
  ```bash
  # For each Pi:
  curl http://<pi-ip>:8080/api/v1/services
  # Should return JSON from THAT specific Pi
  ```

---

## Section 4: Configuration File Preparation

### 4.1: Single Pi Configuration

- [ ] **Create lovelace view YAML** (or update existing)
  - [ ] Replace `SUPERVISOR_IP` with your Pi's IP or mDNS hostname
  - [ ] Replace `8080` if using different port
  - [ ] Verify syntax (proper indentation, no quotes around URLs)

  ```yaml
  - type: custom:perimeter-control-card
    title: "📸 Photo Booth"
    service_id: photo_booth
    api_base_url: "http://192.168.69.11:8080"  # ← Your values here
    api_timeout_ms: 10000
  ```

- [ ] **Verify all 5 services are listed**
  - [ ] photo_booth
  - [ ] wildlife_monitor
  - [ ] ble_gatt_repeater
  - [ ] pawr_esl_ap
  - [ ] network_isolator

### 4.2: Multi-Pi Configuration (If Applicable)

- [ ] **Mapping: Services to Pis**
  - [ ] Determined which services run on which Pi
  - [ ] Created list:
    ```
    Pi-1 (192.168.69.11):
      - photo_booth
      - wildlife_monitor
    
    Pi-2 (192.168.69.12):
      - ble_gatt_repeater
      - network_isolator
    ```

- [ ] **Created separate card sections per Pi**
  ```yaml
  # Pi-1 Services
  - type: custom:perimeter-control-card
    api_base_url: "http://192.168.69.11:8080"
    service_id: photo_booth

  # Pi-2 Services (DIFFERENT IP!)
  - type: custom:perimeter-control-card
    api_base_url: "http://192.168.69.12:8080"  # ← Different IP
    service_id: ble_gatt_repeater
  ```

---

## Section 5: Timeout & Network Performance

### 5.1: Determine Appropriate Timeout

- [ ] **Measure network latency from HA to Pi**
  ```bash
  ping -c 10 <pi-ip>
  # Look at "avg" latency (milliseconds)
  # Note: 5ms, 15ms, 50ms, etc.
  ```

- [ ] **Set api_timeout_ms accordingly**
  - [ ] Latency < 10ms: `api_timeout_ms: 10000` (default) ✅
  - [ ] Latency 10-30ms: `api_timeout_ms: 15000`
  - [ ] Latency 30-50ms: `api_timeout_ms: 20000`
  - [ ] Latency > 50ms: `api_timeout_ms: 30000`
  - [ ] WiFi or slow networks: `api_timeout_ms: 20000-30000`

- [ ] **Document your timeout values**
  ```
  Network: Local LAN (Ethernet)
  Latency: 2ms
  Timeout: 10000ms (default)
  ```

---

## Section 6: CORS Configuration (If Multi-Machine)

### 6.1: Determine if CORS is Needed

- [ ] **On same machine?** (HA and Supervisor on same Pi) → Skip to Section 7
- [ ] **On different machines?** → Continue with 6.2

### 6.2: Configure CORS on Supervisor

- [ ] **Check if CORS already configured**
  ```bash
  ssh pi@<pi-ip>
  grep -A 10 "cors:" /opt/isolator/config/isolator.conf.yaml
  # If section exists and looks good, skip to 6.3
  ```

- [ ] **If not configured, add CORS section**
  ```yaml
  # Edit /opt/isolator/config/isolator.conf.yaml on Pi:
  server:
    port: 8080
    cors:
      allowed_origins:
        - "http://192.168.69.10:8123"  # Your HA IP:port
        - "http://ha.local:8123"        # HA mDNS (if available)
        - "https://example.com"         # If remote access needed
  ```

- [ ] **Restart Supervisor to apply CORS changes**
  ```bash
  ssh pi@<pi-ip>
  sudo systemctl restart isolator-supervisor
  # Wait 5 seconds
  systemctl status isolator-supervisor  # Verify running
  ```

### 6.3: Verify CORS Headers in Response

- [ ] **Test CORS headers are present**
  ```bash
  curl -i http://<pi-ip>:8080/api/v1/services | grep -i access-control
  
  # Expected output:
  # access-control-allow-origin: *
  # (or specific origin if restricted to HA IP)
  ```

---

## Section 7: API URL Robustness Check

### 7.1: Verify URL Format

- [ ] **All URLs have scheme** (http:// or https://)
  ```yaml
  ✅ http://192.168.69.11:8080
  ❌ 192.168.69.11:8080  (missing http://)
  ```

- [ ] **All URLs have port number**
  ```yaml
  ✅ http://192.168.69.11:8080
  ❌ http://192.168.69.11  (missing port, might use default 80 instead)
  ```

- [ ] **No trailing slashes** (optional but consistent)
  ```yaml
  ✅ http://192.168.69.11:8080
  ~ http://192.168.69.11:8080/  (works but inconsistent)
  ```

- [ ] **Quotes present for YAML accuracy** (if using special characters)
  ```yaml
  ✅ api_base_url: "http://192.168.69.11:8080"
  ~ api_base_url: http://192.168.69.11:8080  (works but less safe)
  ```

### 7.2: Fallback Plan

- [ ] **Know backup URL formats** (if primary fails)
  ```
  Primary:  http://192.168.69.11:8080
  Fallback1: http://isolator-pi.local:8080
  Fallback2: IP from router admin panel
  Fallback3: SSH in and run `hostname -I` again
  ```

### 7.3: Test Each URL Before Deployment

- [ ] **Test PRIMARY URL**
  ```bash
  curl http://<primary-url>:8080/api/v1/services
  # Should return JSON
  ```

- [ ] **Test FALLBACK URLs** (at least one)
  ```bash
  curl http://isolator-pi.local:8080/api/v1/services
  # Should return JSON
  ```

---

## Section 8: HTTP vs HTTPS Decision

### 8.1: Determine Protocol

- [ ] **Local network only?** → Use HTTP
  ```yaml
  api_base_url: "http://192.168.69.11:8080"
  ```

- [ ] **Remote access needed?** → Use HTTPS
  ```yaml
  api_base_url: "https://isolator.example.com:8443"
  # Requires:
  # - Valid SSL certificate (Let's Encrypt recommended)
  # - Supervisor configured with TLS
  # - Port 8443 or custom HTTPS port
  ```

- [ ] **If HTTPS needed**: Verify certificate setup
  ```bash
  ssh pi@<pi-ip>
  ls -la /opt/isolator/certs/
  # Should contain cert.pem, key.pem (or similar)
  ```

---

## Section 9: Build & File Generation

- [ ] **Run build command**
  ```bash
  cd ha-integration
  npm run build
  ```

- [ ] **Verify no build errors**
  - [ ] Build completed without errors
  - [ ] No TypeScript compilation errors
  - [ ] No missing dependencies

- [ ] **Verify dist files exist**
  ```bash
  ls -la dist/
  # Should contain:
  # -rw-r--r-- ... dist/service-access-editor.js
  # -rw-r--r-- ... dist/safe-loader.js
  # -rw-r--r-- ... dist/home-assistant-card.js
  # (plus .map files)
  ```

- [ ] **Verify dist files are not empty**
  ```bash
  wc -l dist/*.js
  # Should all be > 100 lines
  ```

---

## Section 10: HA Configuration Backup

- [ ] **Backup Home Assistant configuration**
  ```bash
  # Via HA UI: Settings → System → Backups → Create Backup
  # OR via SSH:
  ssh {user}@{ha-ip}
  cd /config
  tar -czf backup-before-isolator-$(date +%Y%m%d-%H%M%S).tar.gz . --exclude=.git
  ```

- [ ] **Backup is accessible and can be restored**
  - [ ] Located in safe place (external drive, cloud)
  - [ ] Can restore in < 5 minutes if needed
  - [ ] Tested restore procedure at least once

---

## Section 11: HA Dashboard Syntax Validation

- [ ] **YAML syntax is valid**
  - [ ] Proper indentation (2 spaces, not tabs)
  - [ ] All colons followed by space
  - [ ] Quotes balanced
  - [ ] No unescaped special characters

- [ ] **Use YAML validator**
  ```bash
  # Online: https://www.yamllint.com/
  # Or install locally:
  pip install yamllint
  yamllint example-lovelace-view.yaml
  ```

- [ ] **Each card has required fields**
  ```yaml
  type: custom:perimeter-control-card  ✅ type field
  service_id: photo_booth                    ✅ service_id (which service)
  api_base_url: "http://..."                 ✅ api_base_url (where is API)
  ```

---

## Section 12: Error Handling Verification

### 12.1: Verify Safety Wrappers Are In Place

- [ ] **Error Boundary component is bundled**
  ```bash
  grep -i "error-boundary" dist/home-assistant-card.js
  # Should find reference to error boundary
  ```

- [ ] **Safe Loader component is bundled**
  ```bash
  grep -i "safe-loader" dist/home-assistant-card.js
  # Should find reference to safe loader
  ```

- [ ] **Timeout protection is configured**
  ```yaml
  - type: custom:perimeter-control-card
    api_timeout_ms: 10000  # ← Timeout is set
  ```

### 12.2: Verify Recovery is Possible

- [ ] **Know how to disable card if broken**
  - [ ] Can remove card from YAML quickly
  - [ ] Can restart HA if needed

- [ ] **Know how to restore HA if deployment fails**
  - [ ] Have backup ready
  - [ ] Know restore procedure
  - [ ] Can execute in < 5 minutes

---

## Section 13: Documentation & Logging

- [ ] **Screen shot your configuration**
  - [ ] Saved image of your lovelace YAML
  - [ ] Saved image of API baseline response
  - [ ] Can reference if issues occur

- [ ] **Document your specific setup**
  ```
  Setup: Single Pi Fleet
  Pi Hostname: isolator-primary
  Pi IP: 192.168.69.11
  Supervisor Port: 8080
  API URL: http://isolator-primary.local:8080
  Network Latency: 2ms
  Timeout Setting: 10000ms
  HA Location: Same LAN
  Backup: /backups/backup-before-isolator.tar.gz
  ```

- [ ] **Create troubleshooting reference**
  - [ ] Print/save NETWORK-ARCHITECTURE.md
  - [ ] Print/save SAFE-DEPLOYMENT.md
  - [ ] Keep browser console access knowledge fresh

---

## Final Verification

- [ ] **All 13 sections completed** ✅
- [ ] **No red flags or "CHANGE THIS" items remaining** ✅
- [ ] **Backup created and tested** ✅
- [ ] **Safety wrappers verified** ✅
- [ ] **api_base_url is correct and tested** ✅
- [ ] **Timeout is appropriate for network** ✅
- [ ] **CORS configured if needed** ✅
- [ ] **dist/ files built and validated** ✅
- [ ] **You understand the architecture** ✅

---

## Ready to Deploy!

✅ You're ready for **Phase 1: Deploy to HACS or Manual Install** (see SAFE-DEPLOYMENT.md)

If ANY item is not checked, **DO NOT DEPLOY YET** — identify the issue and resolve it first.

Your single Home Assistant instance is protected by error boundaries, safe loading, and timeout handling. Deploy with confidence! 🛡️

