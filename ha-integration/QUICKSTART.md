# Quick Start — Perimeter Control HA Integration

Get the Perimeter Control integration working in 5 minutes.

## 1. Install the Integration

### Option A: HACS (Easiest)

1. Go to **HACS → Integrations**
2. Click **⋮ Menu → Custom repositories**  
3. Add repository: `https://github.com/avgerion/ha-perimeter-control`
4. Category: `Integration`
5. Install **Perimeter Control**
6. **Restart Home Assistant**

### Option B: Manual Install

```bash
# Copy integration to Home Assistant
cd PerimeterControl  # This repository root
cp -r . /path/to/homeassistant/config/custom_components/perimeter_control/
```

**Restart Home Assistant** after copying files.

## 2. Add Your Pi Device

1. In Home Assistant: **Settings → Devices & Services**
2. Click **"Add Integration"** 
3. Search for **"Perimeter Control"**
4. Enter your Pi details:
   - **Host**: `192.168.50.47` (your Pi's IP)
   - **Port**: `22` (SSH port)  
   - **Username**: `paul` (SSH username)
   - **SSH Key**: Your private key (see below)
   - **Supervisor Port**: `8080`

### SSH Key Setup

**Recommended:** Use `secrets.yaml` for your SSH key:

```yaml
# In secrets.yaml
perimeter_ssh_key: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ...
  -----END OPENSSH PRIVATE KEY-----
```

During setup, enter: `!secret perimeter_ssh_key`

**Alternative:** Paste the key directly (multiline supported).

## 3. Verify Installation

After setup completes:

### Check the Panel
- **"Perimeter Control"** should appear in your HA sidebar
- Click it to access the device management interface

### Check Services  
- Go to **Developer Tools → Services**
- Search for `perimeter_control` — you should see 6 services:
  - `perimeter_control.deploy`
  - `perimeter_control.start_capability` 
  - `perimeter_control.stop_capability`
  - `perimeter_control.trigger_capability`
  - `perimeter_control.reload_config`
  - `perimeter_control.get_device_info`

## 4. Deploy to Your Pi

### From the UI Panel
1. Click **"Perimeter Control"** in the HA sidebar
2. Click **"Deploy"** next to your Pi device
3. Wait for deployment to complete

### From Services
```yaml
# In Developer Tools → Services
service: perimeter_control.deploy  
data:
  force: true  # Optional: force redeploy
```

## 5. Manage Services

Once deployed, you can:

- **Start services**: Use `perimeter_control.start_capability`
- **Stop services**: Use `perimeter_control.stop_capability`  
- **View device info**: Check device capabilities and hardware
- **Monitor status**: Real-time service status in the UI

### Example Service Calls

```yaml
# Start photo booth service
service: perimeter_control.start_capability
data:
  capability: photo_booth

# Trigger BLE scan  
service: perimeter_control.trigger_capability
data:
  capability: ble_scanner
  action: start_scan  
  config: '{"duration": 30}'
```

## Troubleshooting

**Integration not found after restart:**
- Verify files are in `config/custom_components/perimeter_control/`
- Check Home Assistant logs for errors

**SSH connection fails:**  
- Verify Pi is reachable: `ping 192.168.50.47`
- Test SSH manually: `ssh paul@192.168.50.47`
- Check SSH key format (include BEGIN/END lines)

**Supervisor API unreachable:**
- SSH to Pi and check: `systemctl status isolator-supervisor`  
- Test API: `curl http://192.168.50.47:8080/api/v1/services`

**Panel doesn't appear:**
- Refresh browser (F5)
- Check browser console for errors
- Restart Home Assistant

## Next Steps

- Read [Full Documentation](README.md) for advanced features
- Check [Integration Details](INTEGRATION.md) for technical information
- Review [Safety Guidelines](SAFE-DEPLOYMENT.md) for production use

### If you only know `pi_host` right now (deploy-only bootstrap)

Use this minimal YAML first. This allows HA-native deploy without `api_base_url` or `service_id`.

Required fields for HA-native deploy panel:
- `show_deploy_panel: true`
- `entry_id: <perimeter-control-config-entry-id>`

Optional display fields:
- `pi_host`
- `services`

What `entry_id` is:
- The Home Assistant config entry ID for your **Perimeter Control** integration instance.
- It is not a service ID, hostname, or API URL.
- It usually looks like a long lowercase hex string.

How to find `entry_id`:
1. In HA, open **Settings -> Devices & Services**.
2. Open **Perimeter Control**.
3. Open the device/integration details page and copy the entry ID shown there.

Example `entry_id` values:
- `0d5f9e7c3a6b4d0f9a1c2e3b4f5a6d7c`
- `3f7a0b91c6e24f3e9c0d1a2b3c4d5e6f`

```yaml
type: custom:perimeter-control-card
show_deploy_panel: true
entry_id: <perimeter-control-config-entry-id>
pi_host: <pi-ip-or-hostname>
```

Example with a real-looking ID:

```yaml
type: custom:perimeter-control-card
show_deploy_panel: true
entry_id: 0d5f9e7c3a6b4d0f9a1c2e3b4f5a6d7c
pi_host: 192.168.69.11
```


To update the dashboard JS file from your dev machine, use:

```bash
scp dist/ha-integration.js user@homeassistant:/config/www/perimeter-control/
```

After deploy succeeds and `/api/v1/services` is reachable, switch to full card config:

```yaml
type: custom:perimeter-control-card
service_id: <service-id-from-api>
api_base_url: http://<pi-ip>:8080
show_deploy_panel: true
entry_id: <perimeter-control-config-entry-id>
pi_host: <pi-ip-or-hostname>
```

## 5. Test

- Refresh HA (`F5`)
- You should see the Service Access Editor card
- Try editing a field and clicking "Save Changes"

## Development

For live reload while developing:

```bash
npm run dev
```

Visit `http://localhost:8000` and open `index.html`

## Troubleshooting

**"Component not found"**
- Clear browser cache: `Ctrl+Shift+Delete`
- Check browser console: `F12` → Console
- Verify API URL is reachable from HA client

**"API returned 401"**
- Ensure Supervisor is running: `ssh paul@192.168.69.11 "systemctl status isolator-supervisor"`
- Check firewall: `curl http://192.168.69.11:8080/api/v1/services`

**Build fails**
- Ensure Node 18+: `node --version`
- Delete `node_modules`: `rm -rf node_modules`
- Reinstall: `npm install`

## Next Steps

- Read [Full Documentation](./README.md)
- Check [Component API Reference](./README.md#api-reference)
- View [Example Lovelace View](./example-lovelace-view.yaml)

