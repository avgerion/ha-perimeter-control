# Safe Deployment Guide for Isolator HA Integration

**IMPORTANT: This guide protects your single Home Assistant instance from downtime.**

> **User Context**: You have ONE HA instance (production, no failover). We've implemented multiple layers of protection to ensure a broken Perimeter Control card won't break your Home Assistant.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Build & Validation](#build--validation)
3. [Incremental Deployment Strategy](#incremental-deployment-strategy)
4. [Emergency Rollback Procedures](#emergency-rollback-procedures)
5. [Monitoring After Deployment](#monitoring-after-deployment)
6. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

**Do NOT deploy to production until all items are checked:**


### Step 1: Verify PerimeterControl Supervisor is Stable
```bash
# On your PerimeterControl Supervisor Pi:
sudo systemctl status perimetercontrol-supervisor
curl http://localhost:8080/api/v1/services  # Should return JSON
curl http://localhost:8080/api/v1/node/features  # Should return JSON
```

- [ ] Supervisor is running and responding to API calls
- [ ] All 5 service descriptors are deployed
- [ ] Node features API returns valid JSON

### Step 2: Build the Integration
```bash
cd ha-integration
npm run build
```

- [ ] Build completes WITHOUT errors
- [ ] `dist/` folder contains all `.js` files (3 files minimum: service-access-editor.js, safe-loader.js, home-assistant-card.js)
- [ ] No TypeScript compilation errors
- [ ] Source maps present for debugging

### Step 3: Backup Your Home Assistant Configuration
**CRITICAL BEFORE ANY DEPLOYMENT:**

```bash
# On your Home Assistant device:
# Via Home Assistant UI: Settings → System → Backups → Create Backup
# OR
cd /config
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz . --exclude=.git
# Keep this backup accessible
```

- [ ] Full HA backup created and accessible
- [ ] Backup includes `configuration.yaml` and all automations
- [ ] Backup stored securely (external drive, cloud)
- [ ] You can locate and restore this backup quickly

### Step 4: Verify Browser Console is Accessible
In Home Assistant:
1. Press `F12` to open Developer Tools
2. Go to **Console** tab
3. Clear any existing messages

- [ ] Browser console is accessible and working
- [ ] You know how to access it again for troubleshooting

### Step 5: Verify API URL Configuration
```yaml
# This is what you'll use in your card YAML:
api_base_url: "http://192.168.69.11:8080"  # Replace with YOUR Supervisor IP:port
api_timeout_ms: 10000  # 10 seconds (adjust if network is slow)
enable_error_details: false  # Set to true if debugging issues
```

- [ ] API URL is correct (HTTP or HTTPS?)
- [ ] You can access `http://YOUR_API/api/v1/services` from HA via browser
- [ ] Timeout value is reasonable for your network

---

## Build & Validation

### Run the Build

```bash
cd ha-integration
npm install  # If dependencies changed
npm run build
```

**Expected output:**
```
> isolator-ha-integration@1.0.0 build
> tsc && esbuild dist/service-access-editor.ts --bundle --format=esm --outfile=dist/service-access-editor.js
...
✓ built successfully
```

### Validate Generated Files

```bash
ls -la ha-integration/dist/
```

**Must contain:**
- ✅ `service-access-editor.js` (~50-100 KB)
- ✅ `safe-loader.js` (~20-50 KB)
- ✅ `home-assistant-card.js` (~10-20 KB)
- ✅ Source maps (`.js.map` files)

If any file is missing or empty, **DO NOT DEPLOY**.

### Quick Functional Test (Optional but Recommended)

In `ha-integration/index.html`, edit to test locally:

```html
<!-- Add this for quick testing -->
<script>
  // Test error boundary catches errors
  window.addEventListener('error', (e) => {
    console.log('[TEST] Error caught:', e.error);
  });
</script>

<perimeter-control-error-boundary>
  <perimeter-control-safe-loader .config=${{apiUrl: 'http://localhost:8080', timeout: 5000}}>
    <perimeter-control-service-access-editor 
      .apiBaseUrl=${'http://localhost:8080'} 
      .serviceId=${'photo_booth'}></perimeter-control-service-access-editor>
  </perimeter-control-safe-loader>
</perimeter-control-error-boundary>
```

Run locally: `npm run dev` and verify the component renders without errors.

---

## Incremental Deployment Strategy

### Phase 1: Deploy to HACS (or Manual Install)

**Option A: HACS (Recommended if properly configured)**

1. Go to Home Assistant → HACS → Custom repositories
2. Add: `https://github.com/{your-repo}/ha-integration` (type: `integration`)
3. Search for "Perimeter Control"
4. Click "Install"
5. Restart Home Assistant (⚠️ First time only)

**Option B: Manual Install (Safe alternative)**

```bash
# On your Home Assistant device:
cd /config/www/
git clone https://github.com/avgerion/ha-perimeter-control isolator-integration
# OR manually upload the dist/ folder to /config/www/isolator-integration/
```

**Configure in `configuration.yaml`:**

```yaml
# YAML Dashboard configuration
title: Home Automations

views:
  - title: Isolator Control
    path: isolator
    cards:
      - type: custom:perimeter-control-card
        api_base_url: "http://192.168.69.11:8080"
        service_id: "photo_booth"
        api_timeout_ms: 10000
        enable_error_details: false
```

Then restart HA:
```
Settings → Developer Tools → YAML → Automations → Restart Home Assistant
```

- [ ] Deployment to /www/ or HACS successful
- [ ] YAML configuration added to dashboard
- [ ] HA restarted cleanly

### Phase 2: Verify Card Loads

1. Go to your dashboard and reload the page (`Ctrl+Shift+R` for hard refresh)
2. Open browser console (`F12 → Console`)

**Look for one of these:**

✅ **Success**: Card renders, no errors in console
```
[Isolator Safe Loader] API health check passed: http://192.168.69.11:8080
```

⚠️ **Expected**: "Loading..." screen with timeout message
```
[Isolator Safe Loader] Health check timeout: http://192.168.69.11:8080
→ This is OK! Click the blue "🔄 Retry Now" button
```

❌ **Problem**: Red error box in card
```
[Isolator Error Boundary] Component crashed...
→ Read the error details
→ Check HA logs: Settings → Developer Tools → Logs
```

### Phase 3: Test Basic Functionality

If card loaded successfully:

1. **Test Edit Mode**: Try to edit an access profile (if you have one configured)
2. **Test Timeout Handling**: (Optional) Temporarily stop Supervisor:
   ```bash
   ssh paul@192.168.69.11 sudo systemctl stop isolator-supervisor
   ```
   - Card should show "API Offline" message
   - HA should still work normally (check other dashboards/automations)
   - No errors in HA logs

3. **Restart Supervisor**:
   ```bash
   ssh paul@192.168.69.11 sudo systemctl start isolator-supervisor
   ```
   - Card should say "Retrying..."
   - Click blue "🔄 Retry Now" button
   - Card should load normally again

- [ ] Card renders without crashing HA
- [ ] Timeout handling works
- [ ] Supervisor restart recovery works

### Phase 4: Add More Cards (If Desired)

Once you're confident, add more service cards:

```yaml
# Add to your dashboard YAML:
views:
  - title: Isolator Control
    path: isolator
    cards:
      - type: "custom:perimeter-control-card"
        api_base_url: "http://192.168.69.11:8080"
        service_id: "photo_booth"
        api_timeout_ms: 10000

      - type: "custom:perimeter-control-card"
        api_base_url: "http://192.168.69.11:8080"
        service_id: "face_recognition"
        api_timeout_ms: 10000
```

---

## Emergency Rollback Procedures

### Scenario 1: Card Works But Has Issues

**Problem**: Card loads but behaves unexpectedly

**Step 1: Disable Error Details First**
```yaml
# In configuration.yaml:
- type: "custom:perimeter-control-card"
  api_base_url: "http://192.168.69.11:8080"
  service_id: "photo_booth"
  enable_error_details: false  # ← Set to false to hide error stack
```

**Step 2: Adjust Timeout**
```yaml
# If timeout errors occur:
api_timeout_ms: 20000  # Increase from 10000 to 20000
```

**Step 3: Check HA Logs**
```
Settings → Developer Tools → Logs (search for "isolator" or "error")
```

**Step 4: Restart HA**
```
Settings → System → System Options → Restart Home Assistant
```

### Scenario 2: Browser Crashes or Freezes When Viewing Card

**This is low-risk** because the error boundary catches it:

**Immediate Actions**:
1. Hard refresh browser: `Ctrl+Shift+R`
2. If still frozen, navigate away: `Settings → System`
3. Open developer console: `F12 → Console`
4. Look for red error messages in console

**Recovery**:
1. **Option A - Restart Service:**
   ```bash
   ssh {your-ha-user}@{your-ha-ip}
   sudo systemctl restart home-assistant
   ```

2. **Option B - Temporarily Disable Card:**
   ```yaml
   # In configuration.yaml, comment out the card:
   # - type: "custom:perimeter-control-card"
   #   api_base_url: "http://192.168.69.11:8080"
   #   service_id: "photo_booth"
   ```
   Then restart HA.

3. **Option C - Nuclear Option (Last Resort):**
   ```bash
   # SSH into HA, restore from backup
   cd /config
   tar -xzf backup-YYYYMMDD-HHMMSS.tar.gz .
   sudo systemctl restart home-assistant
   ```

### Scenario 3: HA Dashboard Won't Load

**Worst case, but STILL recoverable** (error boundary prevents this):

**Immediate Check**:
1. Can you access **other HA dashboards**? (Settings, Automations, etc.)
2. Check browser console for JavaScript errors

**If Only Isolator Dashboard Broken**:
```yaml
# Remove the entire view from configuration.yaml:
views:
  # - title: Isolator Control  ← DELETE THIS
  #   path: isolator
  #   cards:
  #     - type: custom:perimeter-control-card
  #       ...

  # Keep your other views:
  - title: Home
    path: home
    cards: [...]
```

Then reload HA → Check if other dashboards work.

**If Multiple Dashboards Broken**:
1. SSH into HA, restore backup:
   ```bash
   cd /config
   tar -xzf backup-LATEST.tar.gz .
   sudo systemctl restart home-assistant
   ```

2. After restore, add card one at a time, testing between each

---

## Monitoring After Deployment

### Week 1: Close Monitoring

- [ ] Daily check: Dashboard loads without errors
- [ ] Daily check: No new entries in HA logs related to "isolator"
- [ ] Test once: Manual Supervisor restart, verify card recovers
- [ ] Test once: Intentional API timeout (stop supervisor briefly), verify safe handling

### Week 2-4: Standard Monitoring

- [ ] Check HA logs weekly for errors
- [ ] Verify card still loads after HA updates
- [ ] Monitor browser console for warnings

### Ongoing: Monthly

- [ ] Update integration if new versions available
- [ ] Check for Isolator Supervisor updates
- [ ] Verify backups still accessible

---

## Troubleshooting

### "Isolator Supervisor is not responding (timeout after 10000ms)"

**Cause**: API not reachable or slow network

**Solutions**:
1. Verify Supervisor is running:
   ```bash
   ssh paul@192.168.69.11 curl http://localhost:8080/api/v1/services
   ```

2. Verify IP/port in card config is correct:
   ```yaml
   api_base_url: "http://192.168.69.11:8080"  # Check this!
   ```

3. Increase timeout:
   ```yaml
   api_timeout_ms: 20000  # Try 20 seconds instead of 10
   ```

4. Check firewall rules on both HA and Supervisor:
   ```bash
   # On Supervisor:
   sudo ufw status
   sudo ufw allow 8080
   ```

### "Cannot reach Isolator Supervisor API (network error or CORS issue)"

**Cause**: CORS or network isolation

**Solutions**:
1. Test from HA machine:
   ```bash
   ssh {user}@{ha-ip}
   curl -i http://192.168.69.11:8080/api/v1/services
   # Should return 200 OK
   ```

2. Check if using HTTPS:
   ```yaml
   api_base_url: "https://192.168.69.11:8080"  # Try https?
   api_base_url: "http://192.168.69.11:8080"   # Or plain http?
   ```

3. Verify CORS is enabled in Supervisor config:
   ```bash
   ssh paul@192.168.69.11
   cat config/isolator.conf.yaml | grep -i cors
   ```

### Card Renders Red Error Box

**Immediate**: Check browser console (F12 → Console) for stack trace

**Steps**:
1. Enable error details in YAML:
   ```yaml
   enable_error_details: true
   ```

2. Reload card and screenshot the error details

3. Check HA logs:
   ```
   Settings → Developer Tools → Logs
   ```

4. Check browser console warnings/errors

5. If stuck, disable card and restart HA:
   ```bash
   sudo systemctl restart home-assistant
   ```

---

## Version & Upgrade Path

### Current Version
- **Integration**: 1.0.0
- **Required HA**: 2024.1.0 or later
- **Required Supervisor**: 0.1.0 or later (check with `/api/v1/version`)

### Upgrading Integration

**When New Version Available**:

1. Backup: `tar -czf backup-pre-upgrade.tar.gz /config`
2. If via HACS: HACS → Custom Repositories → Click "Update"
3. If Manual: `cd /config/www/isolator-integration && git pull`
4. Restart HA: `Settings → System → Restart`
5. Test card loads
6. If issues, restore backup (see Rollback Procedures above)

---

## Support: Getting Help

**If something goes wrong**:

1. **Collect Information**:
   ```bash
   # Browser console (F12 → Console)
   # HA logs (Settings → Developer Tools → Logs)
   # Supervisor logs: ssh paul@{ip} sudo journalctl -u isolator-supervisor -n 50
   ```

2. **Check Existing Issues**:
   https://github.com/avgerion/ha-perimeter-control/issues

3. **Create Issue with**:
   - Error message from card
   - Full HA log entries
   - Browser console messages
   - API URL and timeout settings
   - HA version and Supervisor version
   - Network setup (same LAN? WiFi? Wired?)

---

## Summary: Safety Guarantees

✅ **Error Boundary**: Component crashes won't break HA
✅ **Safe Loader**: API timeouts won't hang cards
✅ **Timeout Protection**: Never waits more than 10 (or configured) seconds
✅ **Graceful Fallback**: Card shows friendly message, not blank/frozen
✅ **Auto-Retry**: Card retries with exponential backoff
✅ **Easy Disable**: Remove from YAML, HA unaffected
✅ **Easy Rollback**: Restore from backup anytime
✅ **Logging**: All issues logged to console + HA logs

---

**You're protected. Deploy with confidence! 🛡️**

