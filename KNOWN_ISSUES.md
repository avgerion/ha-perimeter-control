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
