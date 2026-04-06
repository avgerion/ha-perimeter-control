# Known Issues for Perimeter Control Integration

## 1. SSH Key Handling in Config Flow
- **Issue:** If the user pastes an SSH private key into the text box during setup, the key content is stored directly in the config entry, which is not ideal for security and portability.
- **Proposed Solution:** When a user pastes a key, the integration should save the key content to a file (e.g., in /config/ssh/) and store only the file path (`ssh_key_path`) in the config entry. The key content should not be stored in Home Assistant's config entry data.
- **Status:** Not yet implemented. Requires update to config_flow.py to write the pasted key to a file and update the config entry accordingly.

## 2. Package Installation Should Be Service-Dependent
- **Issue:** Current deployment installs all Python packages (bleak, bokeh, tornado, pandas, etc.) regardless of which services are selected during setup. This wastes resources and requires more powerful hardware than necessary.
- **Impact:** Deployments consume unnecessary CPU, memory, and disk space on resource-constrained Pi devices. For example, `bleak` is only needed for BLE services but gets installed even for network-only deployments.
- **Proposed Solution:** Make package installation conditional based on selected services. Each service descriptor should specify its Python dependencies, and the deployer should only install packages required by the selected services.
- **Example:** If only `network_isolator` is selected, skip installing `bleak`, `bokeh`, and other service-specific packages.
- **Status:** Not yet implemented. Requires adding dependency mapping to service descriptors and updating deployer pip installation logic.

## 3. HA Integration Entity Discovery Bug (FIXED April 2026)
- **Issue:** Home Assistant integration showed no entities or services despite supervisor running correctly with active entities.
- **Root Cause:** Two critical bugs in the HA integration code:
  1. Coordinator was only polling `/api/v1/status` endpoint instead of `/api/v1/ha/integration` endpoint during regular updates
  2. Missing "camera" platform in `PLATFORMS` list prevented camera entities from loading
- **Impact:** Integration appeared broken even though supervisor API was working perfectly (7 entities available via `/api/v1/ha/integration`)
- **Fix Applied:** 
  - Updated `coordinator.py` `_async_update_data()` method to call `_fetch_ha_integration_data()` which fetches comprehensive entity data
  - Added "camera" to `PLATFORMS` list in `const.py`
  - Created `camera.py` platform file to handle camera entities
- **Status:** **RESOLVED** - Integration now properly discovers and loads all supervisor entities
- **Testing:** After fix, integration should show all active entities (sensors, binary sensors, buttons, cameras) from supervisor API
- **Debugging Note:** For similar issues, verify coordinator polling calls the correct endpoint and all entity platforms are registered
