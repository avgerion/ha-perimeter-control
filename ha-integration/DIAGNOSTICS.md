# Common Configuration Errors & Diagnostics

> **If something doesn't work, these diagnostics will tell you EXACTLY why.**

---

## Error: "Cannot reach PerimeterControl Supervisor API"

### Symptom
Card shows red box:
```
🔌 API Offline
Cannot reach PerimeterControl Supervisor API at http://192.168.69.11:8080
Network error or CORS issue detected.
```

### Diagnosis

**Step 1: Verify API URL is correct**
```bash
# On HA machine, test each component:
curl http://192.168.69.11:8080  # Base URL
curl http://192.168.69.11:8080/api  # /api prefix
curl http://192.168.69.11:8080/api/v1  # /api/v1 endpoint
curl http://192.168.69.11:8080/api/v1/services  # Full path
```

```
Expected for each:
✅ curl http://192.168.69.11:8080 → Some response (or connection refused if no root)
✅ curl http://192.168.69.11:8080/api/v1/services → HTTP 200 + JSON

Problematic:
❌ Connection refused → Wrong IP or port, or Supervisor not running
❌ Connection timeout → Network unreachable or firewall blocking
❌ HTTP 404 → API path wrong, verify Supervisor version
```

**Step 2: Verify Supervisor is actually running**
```bash
ssh pi@192.168.69.11
sudo systemctl status perimetercontrol-supervisor
```

```
Expected:
● perimetercontrol-supervisor.service - PerimeterControl Supervisor
   Loaded: loaded (...)
   Active: active (running) since Today HH:MM:SS UTC; Xm ago

Problematic:
● perimetercontrol-supervisor.service
   Loaded: loaded (...)
   Active: inactive (dead)  ← Service not running!
     
Solution: Start it
sudo systemctl start perimetercontrol-supervisor
```

**Step 3: Check IP is correct**
```bash
# Get Pi's actual IP:
ssh pi@<your-pi-ip>
hostname -I
# Compare with card's `api_base_url`
```

```
If mismatch:
- Check DHCP lease (may have expired)
- Use mDNS hostname (perimetercontrol-pi.local) instead of hardcoded IP
- Reserve IP in router for this Pi
```

**Step 4: Check firewall**
```bash
# On Pi:
sudo ufw status
# If UFW is running, verify 8080 is allowed:
sudo ufw allow 8080
```

**Step 5: Check network path**
```bash
# From HA machine:
ping 192.168.69.11
traceroute 192.168.69.11

# Results:
✅ ping responds in < 100ms → Network OK
❌ 100% packet loss → Network unreachable
❌ traceroute shows many hops → Different network/VPN needed
```

**Step 6: If still failing — check browser console for CORS**
```javascript
// F12 → Console in HA
// Look for errors like:
// "Access to XMLHttpRequest at 'http://...' from origin 'http://ha-ip:8123' 
//  has been blocked by CORS policy"

// Solution: Configure CORS on Supervisor (see Section 6 in PRE-DEPLOYMENT-CHECKLIST)
```

### Quick Fix Checklist
- [ ] Verify IP with: `ssh pi@<ip> hostname -I`
- [ ] Verify Supervisor running: `systemctl status isolator-supervisor`
- [ ] Verify accessible: `curl http://<ip>:8080/api/v1/services`
- [ ] Check firewall: `ufw status` (should allow 8080)
- [ ] Check CORS if different machines: See configuration section

---

## Error: "Connection Timeout" (After 10-30 seconds)

### Symptom
Card shows orange box:
```
⏱️ Connection Timeout
Isolator Supervisor is not responding (timeout after 10000ms)
```

### Root Causes (in order of likelihood)

1. **Supervisor is running, but slow to respond**
   - Check Pi CPU/memory: `top`
   - Increase timeout: `api_timeout_ms: 20000`

2. **Supervisor crashed recently and is restarting**
   - Wait 10-15 seconds and click Retry
   - Check logs: `journalctl -u isolator-supervisor -n 50`

3. **Network latency is high**
   - Measure: `ping -c 10 <pi-ip>` (look at avg)
   - If avg > 10ms, increase timeout accordingly

4. **Supervisor process is stuck/hung**
   - Restart: `sudo systemctl restart isolator-supervisor`
   - Check if certain API call hangs: Might need Supervisor code fix

### Diagnosis

```bash
# Check Supervisor status while card shows timeout:
watch -n 1 systemctl status isolator-supervisor
# If status shows "running" but request times out → Supervisor hung

# Check Supervisor logs for errors:
sudo journalctl -u isolator-supervisor -n 100 | tail -20

# Look for:
- Exception or Traceback → Supervisor code error
- hung or timeout → Process stuck
- "INFO" with no errors → Process OK, could be latency issue
```

### Quick Fix Checklist
- [ ] Click blue "🔄 Retry Now" button
- [ ] Wait 10 seconds (Supervisor may be restarting)
- [ ] Check network latency: `ping <pi-ip>`
- [ ] Increase timeout if consistently slow: `api_timeout_ms: 20000`
- [ ] If persists, check Pi resources: `ssh pi@<ip> free -h && df -h`

---

## Error: "Failed to load integration"

### Symptom
Card shows error box:
```
⚠️ Failed to load integration
Check browser console for details
```

### Diagnosis

**Step 1: Check browser console (F12 → Console)**
```javascript
// Look for errors like:

"TypeError: Cannot read property 'services' of undefined"
// → API response missing expected fields

"SyntaxError: Unexpected token < in JSON position 0"
// → API returned HTML instead of JSON (404 error page?)

"ReferenceError: isolator_service_access_editor is not defined"
// → Component not loaded correctly

"Failed to fetch (TypeError: NetworkError when attempting to fetch resource)"
// → Network or CORS issue (usually more specific message)
```

**Step 2: Test API response format**
```bash
curl http://<pi-ip>:8080/api/v1/services | python3 -m json.tool

# Expected:
{
  "services": {
    "photo_booth": { ... },
    "wildlife_monitor": { ... },
    ...
  }
}

# Problematic:
<html><error>404 Not Found</error></html>  ← API path wrong!
```

**Step 3: Check which component is failing**
```yaml
# Enable error details to see stack trace:
- type: custom:perimeter-control-card
  ...
  enable_error_details: true  # ← Add this
```

Then reload and check stack trace in the card.

**Step 4: Verify dist files are correct**
```bash
# Check file sizes (shouldn't be tiny):
ls -lh dist/*.js   # Should all be > 10 KB

# Check for valid JavaScript:
head -c 100 dist/home-assistant-card.js  # Should start with valid JS or comment
```

### Quick Fix Checklist
- [ ] Check browser console for specific error
- [ ] Enable `enable_error_details: true` to see stack trace
- [ ] Test API directly: `curl http://<ip>:8080/api/v1/services`
- [ ] Verify dist files exist and aren't empty
- [ ] Rebuild if needed: `npm run build`

---

## Error: "Invalid Configuration"

### Symptom
Card shows error immediately on load, or HA won't load dashboard:
```
Invalid Configuration
error: Card configuration incorrect
```

### Root Causes

1. **YAML syntax error**
   ```yaml
   ❌ api_base_url: http://192.168.69.11:8080  (unquoted, breaks if : in value)
   ✅ api_base_url: "http://192.168.69.11:8080"
   ```

2. **Missing required field**
   ```yaml
   ❌ type: custom:perimeter-control-card
      api_base_url: "http://..."
      # Missing: service_id (required!)
   
   ✅ type: custom:perimeter-control-card
      service_id: photo_booth
      api_base_url: "http://..."
   ```

3. **Wrong field name**
   ```yaml
   ❌ apiUrl: "http://..."  (camelCase, but expects snake_case)
   ✅ api_base_url: "http://..."
   
   ❌ timeout_ms: 10000  (should be api_timeout_ms)
   ✅ api_timeout_ms: 10000
   ```

4. **Indentation error**
   ```yaml
   ❌  - type: custom:perimeter-control-card
       service_id: photo_booth  (indentation not consistent)
      api_base_url: "..."
   
   ✅  - type: custom:perimeter-control-card
         service_id: photo_booth
         api_base_url: "..."
   ```

### Diagnosis

**Step 1: Validate YAML syntax**
```bash
# Online validator: https://www.yamllint.com/
# Or install locally:
pip install yamllint
yamllint your-dashboard.yaml
```

**Step 2: Check field names are correct**
```yaml
# Required fields (case-sensitive, snake_case):
- type: custom:perimeter-control-card
  service_id: photo_booth              # ← snake_case, required
  api_base_url: "http://..."           # ← snake_case, required

# Optional fields:
  api_timeout_ms: 10000                # ← underscore_version
  enable_error_details: false
  title: "📸 Photo Booth"
```

**Step 3: Check quotes and colons**
```yaml
# Each key: value pair must have space after colon
❌ api_base_url:"http://..."
✅ api_base_url: "http://..."

# Values with colons must be quoted (YAML rule)
❌ api_base_url: http://192.168.69.11:8080  (colon breaks YAML)
✅ api_base_url: "http://192.168.69.11:8080"
```

### Quick Fix Checklist
- [ ] Validate YAML: `yamllint` or online tool
- [ ] Verify field names are snake_case: `service_id`, `api_base_url`
- [ ] Verify all required fields present
- [ ] Quotes around URLs (YAML requires it)
- [ ] Consistent indentation (2 spaces)

---

## Error: Card Renders But Does Nothing

### Symptom
Card appears with no data, or clicking buttons does nothing.

### Root Causes

1. **Service ID doesn't exist on Supervisor**
   ```bash
   # Check available services:
   curl http://<pi-ip>:8080/api/v1/services
   
   # If "photo_booth" not in list:
   ❌ Service named differently or not running
   ✅ Use exact service name from API response
   ```

2. **Edition API URL is incomplete/wrong**
   - Card loads → Shows services list fine → but "Edit" button fails
   - Check: `api_base_url` is correct for that service

3. **JavaScript console errors** (silent failures)
   ```javascript
   // F12 → Console
   // Look for yellow warnings or red errors
   // May indicate:
   // - Missing dependencies
   // - Incorrect API response fields
   // - State management issue
   ```

### Diagnosis

```bash
# 1. Verify service exists:
curl http://<pi-ip>:8080/api/v1/services | grep photo_booth
# Should find it in response

# 2. Verify service has access profile:
curl http://<pi-ip>:8080/api/v1/services/photo_booth/access
# Should return access profile JSON

# 3. Check browser console for JavaScript errors:
# F12 → Console → Look for red errors
```

### Quick Fix Checklist
- [ ] Verify service_id matches exact name from API
- [ ] Verify service is in the services list
- [ ] Check browser console for JavaScript errors
- [ ] Try different service to verify card works

---

## Error: Changes Don't Save

### Symptom
Edit access profile → Click "Save Changes" → No confirmation, changes don't stick

### Root Causes

1. **API returned error but card didn't show it**
   - Check browser console for fetch errors
  - Enable `enable_error_details: true` to see responses

2. **Supervisor doesn't support PUT requests for that field**
   - Check Supervisor documentation for editable fields

3. **Permission issue** (future feature with auth)
   - API might require credentials

### Diagnosis

```bash
# 1. Check browser console (F12 → Network tab):
# - Click "Save Changes"
# - Look for "PUT /api/v1/services/{id}/access" request
# - Check response status: 200 (OK), 400 (bad request), 403 (forbidden), 500 (error)

# 2. Test API PUT request manually:
curl -X PUT http://<pi-ip>:8080/api/v1/services/photo_booth/access \
  -H "Content-Type: application/json" \
  -d '{"mode": "isolated", "port": 8000}'

# Response should be: 200 OK or 400 Bad Request (if invalid)
# Not: 500 Internal Server Error or timeout
```

### Quick Fix Checklist
- [ ] Check browser Network tab for API response
- [ ] Verify server returned 200 OK
- [ ] Test API PUT request manually with curl
- [ ] Check Supervisor logs for errors during save

---

## Error: CORS Error in Browser Console

### Symptom
Browser console shows:
```
Access to XMLHttpRequest at 'http://...' from origin 'http://...' 
has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### Root Cause
HA (at one IP:port) trying to access Supervisor (at different IP:port), but Supervisor not configured to allow it

### Solution

**Edit Supervisor config on Pi:**
```bash
ssh pi@<pi-ip>
sudo nano /opt/isolator/config/isolator.conf.yaml

# Add CORS section:
server:
  port: 8080
  cors:
    allowed_origins:
      - "http://192.168.69.10:8123"  # HA IP:port
      - "http://ha.local:8123"
      - "https://example.com"
```

**Restart Supervisor:**
```bash
sudo systemctl restart isolator-supervisor
# Wait 5 seconds
systemctl status isolator-supervisor  # Verify running
```

**Test CORS headers:**
```bash
curl -i http://<pi-ip>:8080/api/v1/services | grep -i access-control-allow-origin
# Should show: access-control-allow-origin: *  (or specific origin)
```

### Quick Fix Checklist
- [ ] Identify Supervisor and HA IPs
- [ ] Add CORS to Supervisor config
- [ ] Restart Supervisor
- [ ] Verify CORS header in curl response

---

## Diagnostic Command Reference

```bash
# 1. QUICK CHECK (from HA machine):
curl -s http://<pi-ip>:8080/api/v1/services | python3 -m json.tool | head -20

# 2. FULL DIAGNOSTIC (run all):
ping -c 3 <pi-ip>                          # Network reachable?
curl -v http://<pi-ip>:8080/                        # Port 8080 open?
curl -i http://<pi-ip>:8080/api/v1/services        # API accessible? (check headers)
curl -s http://<pi-ip>:8080/api/v1/services | wc -l # Response size

# 3. SUPERVISOR STATUS (from Pi):
ssh pi@<pi-ip>
systemctl status isolator-supervisor
journalctl -u isolator-supervisor -n 50
free -h && df -h  # Resources

# 4. NETWORK DEBUG (from both machines):
traceroute <other-ip>
mtr -c 10 <other-ip>  # Latency over 10 pings
netstat -tlnp | grep 8080  # Port listening?
```

---

## When Nothing Else Works

1. **Collect debugging info**:
   ```bash
   # Save these outputs to a file:
   curl -v http://<pi-ip>:8080/api/v1/services > /tmp/debug.txt 2>&1
   systemctl status isolator-supervisor >> /tmp/debug.txt
   ```

2. **Check HA logs**:
   ```
   Settings → Developer Tools → Logs (search "isolator")
   ```

3. **Check browser console**:
   ```
   F12 → Console → Copy errors and stack trace
   ```

4. **Create GitHub issue** with:
   - Screenshot of error
   - Browser console errors
   - HA logs
   - Output from diagnostic commands above
   - Your network setup (single Pi, multi-Pi, etc.)
   - Supervisor version and HA version

---

## Summary

**Error shows up immediately?** → YAML syntax or configuration issue (Section: "Invalid Configuration")

**Error shows after 3-10 seconds?** → Network/CORS/firewall issue (Sections: "Cannot reach API" or "CORS Error")

**Error shows after 30+ seconds?** → Timeout issue (Section: "Connection Timeout")

**Card loads but doesn't work?** → API content issue (Section: "Card Renders But Does Nothing" or "Changes Don't Save")

**Follow the diagnostic steps for your error type, and you'll know exactly why it's failing within 5 minutes.** 🔍

