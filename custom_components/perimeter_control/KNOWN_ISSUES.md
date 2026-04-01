# Known Issues for Perimeter Control Integration

## 1. SSH Key Handling in Config Flow
- **Issue:** If the user pastes an SSH private key into the text box during setup, the key content is stored directly in the config entry, which is not ideal for security and portability.
- **Proposed Solution:** When a user pastes a key, the integration should save the key content to a file (e.g., in /config/ssh/) and store only the file path (`ssh_key_path`) in the config entry. The key content should not be stored in Home Assistant's config entry data.
- **Status:** Not yet implemented. Requires update to config_flow.py to write the pasted key to a file and update the config entry accordingly.
