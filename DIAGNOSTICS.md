# NetworkIsolator Diagnostics & Fixes

## Issues Fixed

### 1. ✅ Dashboard Import Errors (ERR_CONNECTION_REFUSED)
**Root Cause**: All dashboard entry points had incorrect import path for `DataManager`
- ❌ Wrong: `from data_manager import DataManager`
- ✅ Fixed: `from ..supervisor.data_manager import DataManager`

**Files Updated**:
- `remote_services/dashboard_web/photo_booth_dashboard.py`
- `remote_services/dashboard_web/ble_gatt_repeater_dashboard.py`
- `remote_services/dashboard_web/esl_dashboard.py`
- `remote_services/dashboard_web/wildlife_dashboard.py`

**Impact**: GPIO dashboard ERR_CONNECTION_REFUSED should now be resolved. All dashboards should start correctly.

---

### 2. ✅ Photo Booth Dashboard - Overlapping Sections
**Root Cause**: Insufficient spacing between layout sections when stacking multiple panels

**Fixes Applied**:
- Increased spacer heights from 8px to 12px for better visual separation
- Enhanced CSS positioning rules to prevent absolute positioning overlaps
- Ensured PreText elements use static positioning in the layout flow

**File Updated**: `remote_services/dashboard_web/dashboard_common.py`

**Result**: Log sections should no longer overlap. The `bk-Spacer` CSS class now enforces proper block flow layout.

---

### 3. 🔍 HA Entities Missing (Except 2 URLs)
**Status**: Enhanced Logging Added - Manual Diagnosis Needed

**Root Cause**: Unknown. Could be one of:
1. Supervisor `/ha/integration` endpoint not returning entities
2. Entities being filtered due to service selection mismatch
3. Supervisor service not running or misconfigured
4. Entity schema from supervisor is empty

**Enhanced Logging Added**:

#### In `coordinator.py`:
```
[HA_INTEGRATION] Raw response from /ha/integration: X total entities, Y services
[HA_INTEGRATION] Selected services: ['service1', 'service2']
[HA_INTEGRATION] Entities from /ha/integration (post-filter): ['entity1', 'entity2']
[COORDINATOR_UPDATE] Successfully fetched N entities from supervisor
```

#### In `sensor.py`:
```
[SENSOR_SETUP] Starting sensor entity setup for entry_id
[SENSOR_SETUP] Coordinator data keys: [...]
[SENSOR_SETUP] Found N supervisor_entities from coordinator
[SENSOR_SETUP] Entity types in supervisor_entities: ['sensor', 'switch', ...]
[SENSOR_SETUP] Adding M new sensor entities from updated schema
```

---

## Diagnostic Steps

### Step 1: Check Dashboard Startup (logs for ERR_CONNECTION_REFUSED)
1. Check if GPIO/Photo Booth dashboards now start without import errors
2. Look for logs from the dashboard services (e.g., `journalctl -u perimetercontrol-gpio-dashboard -n 50`)
3. Expected: Should see "Dashboard running on port XXXX" message

### Step 2: Verify HA Entities Are Being Fetched
Enable DEBUG logging in Home Assistant and check for:

**In HA logs, look for**:
```
[HA_INTEGRATION] Raw response from /ha/integration: X total entities, Y services
```

**What this tells you**:
- `X = 0` → Supervisor not returning entities from `/ha/integration` endpoint
- `X > 2` → Entities are available but may be getting filtered
- Only 2 entities → Only dashboard URLs are being created (supervisor entities are empty)

### Step 3: Check Service Selection
Run this in HA to see what services are selected:
```
Home Assistant > Settings > Devices & Services > PerimeterControl > Configuration
Check "Services" field to see what's enabled
```

**Issue**: If services are selected but coordinator shows different services, there's a mismatch.

### Step 4: Check Supervisor API Directly
SSH to the Pi and test the supervisor API:
```bash
curl http://localhost:8080/api/v1/ha/integration | jq '.entities | length'
```

**Expected Output**:
- Should return the count of entities available
- If returns `0` or error, supervisor isn't providing entities

### Step 5: Manual Log Collection
After the fixes, perform these steps to gather logs:

1. **Restart GPIO Dashboard**:
   ```bash
   systemctl restart perimetercontrol-gpio-dashboard
   ```
   
2. **Collect Dashboard Logs**:
   ```bash
   journalctl -u perimetercontrol-gpio-dashboard -n 100 --no-pager
   ```

3. **Collect Supervisor Logs**:
   ```bash
   journalctl -u perimetercontrol-supervisor -n 50 --no-pager
   ```

4. **Reload HA Integration**:
   - Home Assistant > Settings > Devices & Services > Perimeter Control > (three dots) > Reload
   
5. **Check HA Logs for Entity Setup**:
   - Look for `[SENSOR_SETUP]` messages in HA logs

---

## Expected Log Output (After Fixes)

### GPIO Dashboard Startup:
```
GPIO Control dashboard running on port 8095
[GPIO_DASH] CSS will be loaded from /css/pc-dashboard.css
[CSS_HANDLER] Request for /css/pc-dashboard.css - serving 3421 bytes
```

### Coordinator First Refresh:
```
[HA_INTEGRATION] Raw response from /ha/integration: 42 total entities, 5 services
[HA_INTEGRATION] Entities from /ha/integration (post-filter): ['sensor.temperature', 'switch.relay1', ...]
[COORDINATOR_UPDATE] Successfully fetched 44 entities from supervisor (42 + 2 dashboard URLs)
```

### Sensor Platform Setup:
```
[SENSOR_SETUP] Found 44 supervisor_entities from coordinator
[SENSOR_SETUP] Entity types in supervisor_entities: ['sensor', 'sensor', 'switch', ...]
[SENSOR_SETUP] Adding 25 new sensor entities from updated schema
```

---

## If Issues Persist

1. **GPIO Dashboard Still Shows ERR_CONNECTION_REFUSED**:
   - Check if the import fix was applied correctly
   - Verify the service can parse the config file at startup
   - Check `/var/log/PerimeterControl/gpio_dashboard.log` for errors

2. **Photos Booth Log Sections Still Overlapping**:
   - Check browser DevTools to see if custom CSS is loading
   - Verify `/css/pc-dashboard.css` is being served (check network tab)
   - May need to clear browser cache

3. **Only 2 URL Entities (No Sensor/Switch/Light Entities)**:
   - Supervisor `/ha/integration` endpoint is not returning entities
   - Check supervisor logs for errors during entity schema generation
   - Verify capability services are actually running and exposing entities
   - Check if service selection matches actual deployed services

---

## Files Modified

- ✅ `photo_booth_dashboard.py` - Fixed import
- ✅ `ble_gatt_repeater_dashboard.py` - Fixed import
- ✅ `esl_dashboard.py` - Fixed import
- ✅ `wildlife_dashboard.py` - Fixed import
- ✅ `dashboard_common.py` - Improved spacing
- ✅ `coordinator.py` - Enhanced logging
- ✅ `sensor.py` - Enhanced logging
