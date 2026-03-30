# Isolator HA Integration: Safety Architecture

> **For Your Single HA Instance**: Three layers of protection ensure this integration can never break your home automation.

---

## Layer 1: Error Boundary 🛡️

**File**: `src/error-boundary.ts` (170 lines)

### What It Does
- **Catches all JavaScript exceptions** from child components
- **Renders safe fallback UI** (friendly error message, not blank/broken)
- **Prevents error propagation** to Home Assistant parent
- **Logs to console** for debugging without breaking anything

### How It Protects You
```
Component crash → Error Boundary catches it → Shows user-friendly message
                                          → HA continues running normally
```

### Example Scenarios

❌ **Without Error Boundary:**
- ServiceAccessEditor crashes → HA dashboard freezes
- User can't access any automations
- Home automation stops responding

✅ **With Error Boundary:**
- ServiceAccessEditor crashes → Error Boundary catches it
- Card shows: "⚠️ Failed to load integration"
- User can click "🔄 Retry" or navigate to other HA dashboards
- Home automation continues running normally
- Error logged to browser console for diagnosis

### UI Fallback
```
┌─ Perimeter Control ─┐
│ ⚠️ Failed to load integration     │
│ Check browser console for details │
│                                   │
│ Error Details (clickable):        │
│ <stack trace>                     │
│                                   │
│ [🔄 Retry] Attempt 1              │
│                                   │
│ Troubleshooting steps...          │
└───────────────────────────────────┘
```

---

## Layer 2: Safe Loader ⏱️

**File**: `src/safe-loader.ts` (280 lines)

### What It Does
- **Checks Isolator Supervisor API health** before rendering
- **Enforces maximum timeout** (default 10 seconds, configurable)
- **Auto-retries with exponential backoff** if API is temporarily down
- **Never blocks Home Assistant** from loading or functioning

### How It Protects You

```
HA loads → Safe Loader checks API (with 10s timeout)
             ├─ API responds ✅ → Component loads normally
             ├─ API times out ⏱️ → Shows timeout screen, auto-retries
             ├─ Network error 🔌 → Shows offline message, provides fix steps
             └─ After 3 retries → Shows permanent error, user can retry manually

In ALL cases → HA continues running, user never locked out
```

### State Transitions
```
LOADING (waiting for API)
   ├─ timeout (>10s) → TIMEOUT   [Show retry button]
   ├─ network error  → OFFLINE   [Show troubleshooting steps]
   ├─ API error      → ERROR     [Show error details]
   └─ success        → READY     [Load component]
```

### Example: What Happens If Supervisor Crashes?

**Scenario**: Supervisor crashes while user is viewing the card

1. **User sees** (after ~10 seconds):
   ```
   ⏱️ Connection Timeout
   Isolator Supervisor is not responding (timeout after 10000ms)
   
   This could mean:
   - Isolator Supervisor is not running
   - API URL is incorrect
   - Network connectivity issue
   
   [🔄 Retry Now]
   Will auto-retry...
   ```

2. **User experience**: Card shows friendly message, not frozen
3. **HA state**: All other automations, scenes, automations still work
4. **Recovery**: When Supervisor restarts, user clicks Retry or user waits for auto-retry
5. **No downtime**: HA never interrupted

---

## Layer 3: Graceful Degradation in Component Code

**Files**: `src/service-access-editor.ts`, `src/fleet-view.ts`

### Built-In Resilience

#### ServiceAccessEditor
```typescript
// API calls have timeouts
const response = await fetch(`${apiUrl}/api/v1/services?timeout=10`);

// Errors show in UI, not crash
if (!response.ok) {
    this.errors.push(`API Error: ${response.status}`);
    // Render error message, user can still see form
}
```

#### FleetView
```typescript
// Handles unreachable nodes gracefully
async loadNodeFeatures(node: NodeInfo) {
    try {
        const response = await fetch(`${node.url}/api/v1/node/features?timeout=10`);
        // ...
    } catch (err) {
        node.status = 'offline';  // ← Shows as red indicator, not crash
        node.error = err.message;
    }
}
```

---

## Security: Three-Level Protection

### Level 1: Component Level
- Try/catch blocks in all API calls
- Timeouts on fetch() requests
- Error states instead of exceptions

### Level 2: Card Level (Error Boundary)
- Catches unhandled JavaScript errors
- Catches rejected promises
- Renders safe fallback UI

### Level 3: Home Assistant Level
- If card fails to load, HA custom card system catches it
- Failed card doesn't affect other cards
- Other dashboards remain functional

```
Component Error
    ↓ (Error Boundary catches)
Component Fallback UI
    ↓ (Error still shown? LitElement error boundary)
Card renders with warning
    ↓ (Card still broken? HA custom card system)
Other HA features work normally
```

---

## Configuration Options

### Timeout Control
```yaml
- type: "custom:perimeter-control-card"
  api_base_url: "http://192.168.69.11:8080"
  service_id: "photo_booth"
  api_timeout_ms: 10000  # ← Adjust if network is slow
```

- **Default**: 10000 ms (10 seconds)
- **Slow Network**: Try 20000 ms (20 seconds)
- **Very Slow**: Try 30000 ms (30 seconds)
- **Always wait**: Never hangs HA, just the card

### Error Details (For Testing)
```yaml
- type: "custom:perimeter-control-card"
  api_base_url: "http://192.168.69.11:8080"
  service_id: "photo_booth"
  enable_error_details: false  # Set to true if debugging
```

- **false** (default): Hide error details, clean UI
- **true**: Show full stack traces in error card (for testing only)

---

## Monitoring & Diagnostics

### Browser Console
When card has issues, open browser DevTools (F12 → Console):

**Normal Operation:**
```
[Isolator Safe Loader] API health check passed: http://192.168.69.11:8080
```

**Timeout:**
```
[Isolator Safe Loader] Health check timeout: http://192.168.69.11:8080
```

**Network Error:**
```
[Isolator Safe Loader] Health check failed: Cannot reach API (network error or CORS issue)
```

**Recovery Attempt:**
```
[Isolator Safe Loader] Retrying in 1500ms (attempt 1/3)
```

### Home Assistant Logs
```
Settings → Developer Tools → Logs
```

Search for "isolator" to see integration logs without breaking anything.

---

## Testing the Safety Mechanisms (Optional)

### Test 1: Error Boundary
1. Add this URL to card:
   ```yaml
   api_base_url: "http://invalid-url-that-does-not-exist"
   ```
2. The card should show error (not crash HA)
3. Browser console shows error details

### Test 2: Timeout
1. In supervisor Pi, stop the API:
   ```bash
   sudo systemctl stop isolator-supervisor
   ```
2. Card should show "Connection Timeout" (after ~10s)
3. HA continues working normally
4. Restart supervisor:
   ```bash
   sudo systemctl start isolator-supervisor
   ```
5. Card auto-retries and loads

### Test 3: Network Issue
1. Temporarily disconnect supervisor from network
2. Card shows "API Offline" with troubleshooting steps
3. HA unaffected
4. Reconnect supervisor, card auto-recovers

---

## Comparison: With vs Without Safety

### Scenario: API Server Crashes (Supervisor Restarts)

| Aspect | Without Layers | With Safety Layers |
|--------|----------------|-------------------|
| **Card behavior** | Hangs indefinitely | Shows "timeout" after 10s, offers retry |
| **HA Dashboard** | May freeze | Continues responsive |
| **Other automations** | May be affected | Continue running normally |
| **User can navigate away** | Difficult/stuck | Easy (click other dashboard) |
| **Recovery** | Force reload HA | Click retry button or auto-retry |
| **Time to recovery** | 5-10 minutes | 5-10 seconds |

### Scenario: Component Has Broadcasting (Syntax Error)

| Aspect | Without Layers | With Safety Layers |
|--------|----------------|-------------------|
| **Card behavior** | Shows nothing / broken | Shows friendly error message |
| **HA Dashboard** | Broken | Continues responsive |
| **Other cards** | Affected | Unaffected |
| **Error visible** | Dev console only | User-friendly message |
| **Recovery** | Rollback integration | Update and retry |

---

## What's NOT Protected (Out of Scope)

❌ Isolator Supervisor itself crashing → (Not this layer's job)
- But: Card gracefully handles it with Safe Loader

❌ Home Assistant core issues → (Not this layer's job)
- But: Broken card won't trigger HA core issues

❌ Home Assistant extension config errors → (Not this layer's job)
- But: Broken card config will be isolated and not crash HA

---

## Deployment Safety Summary

✅ **Single HA Instance**: Can't be broken by card failure
✅ **Error Isolation**: One broken card ≠ all cards broken
✅ **Timeout Protection**: No indefinite hangs
✅ **Auto-Recovery**: Retries with backoff
✅ **User Control**: Easy disable/rollback
✅ **Logging**: Full debugging info without breaking
✅ **Graceful Degradation**: Card fails, HA continues

---

## Rollback if Something Goes Wrong

**Immediate Recovery** (5 seconds):
```yaml
# In configuration.yaml, comment out/delete the card:
# - type: "custom:perimeter-control-card"
#   api_base_url: "..."
```
Then reload dashboard or restart HA.

**Full Recovery** (1 minute):
```bash
# Restore from backup
cd /config
tar -xzf backup-YYYYMMDD-HHMMSS.tar.gz .
sudo systemctl restart home-assistant
```

**Version Rollback** (from HACS):
HACS → Custom Repositories → Isolator → Downgrade to previous version

---

## Next Steps

1. **Review this document** with your HA instance setup
2. **Read SAFE-DEPLOYMENT.md** for pre-deployment checklist
3. **Run `npm run build`** to generate dist files
4. **Follow incremental deployment** (not all at once)
5. **Monitor logs** for first week
6. **Enjoy safe integration! 🎉**

---

**You have three layers of protection. Your single HA instance is safe. Deploy with confidence! 🛡️**

