# Quick Start — Perimeter Control HA Integration

Get the Service Access Editor working in 5 minutes.

## 1. Install Dependencies

```bash
cd ha-integration
npm install
```

## 2. Build

```bash
npm run build
```

Output: `dist/ha-integration.js`

## 3. Deploy to Home Assistant


### Manual Integration Install (if not using HACS)

To install the Perimeter Control integration manually, copy the integration folder to your Home Assistant config:

```bash
scp -r custom_components/perimeter_control user@homeassistant:/config/custom_components/
```

After copying, restart Home Assistant and add the integration via Settings → Devices & Services.

#### SSH Key Input (secrets.yaml recommended)

When adding a Pi node, you will be prompted for an SSH private key. **Multi-line keys are now fully supported.**

- **Best practice:** Store your SSH key in `secrets.yaml` and reference it in the integration setup (e.g. `!secret perimeter_control_ssh_key`).
- You can also paste the full multi-line key directly in the UI if needed.
- The key must be in standard PEM or OpenSSH format, including the `-----BEGIN ...-----` and `-----END ...-----` lines.

**Troubleshooting:**
- If the UI only shows a single-line input, update Home Assistant to the latest version or use `secrets.yaml`.
- If you see a parsing error, check for extra spaces, missing header/footer, or line breaks.

Example `secrets.yaml` entry:

```yaml
perimeter_control_ssh_key: |
   -----BEGIN OPENSSH PRIVATE KEY-----
   ...
   -----END OPENSSH PRIVATE KEY-----
```

Then in the integration setup, use:

```
!secret perimeter_control_ssh_key
```

### Option A: Upload via UI (Easiest)

Home Assistant does not always create `www` by default. If it is missing, create it.

1. Create this folder in your HA config directory if it does not already exist:
   - `/config/www/perimeter-control/` (HA OS / Supervised / most Container installs)
   - `~/.homeassistant/www/perimeter-control/` (HA Core venv installs)
2. Copy `dist/ha-integration.js` to that folder
3. Add to `configuration.yaml`:
   ```yaml
   frontend:
     extra_module_url:
            - /local/perimeter-control/ha-integration.js
   ```

### Option B: SSH/SCP (Advanced)

```bash
scp dist/ha-integration.js user@homeassistant:/config/www/perimeter-control/
```

## 4. Add to Dashboard

Before creating the card, make sure the Perimeter Control Supervisor API is running and reachable.

You have two supported deployment paths:

- HA-native (recommended): use the Perimeter Control integration deploy panel in Home Assistant. This does not require PowerShell.
- Script-based (optional): use `scripts/deploy-dashboard-web.ps1` from this repo. Supervisor deployment is included by default unless you pass `-SkipSupervisor`.

Quick check from a machine that can reach your Pi:

```bash
curl http://<pi-ip>:8080/api/v1/services
```

If this does not return JSON, deploy/start the supervisor service on the Pi first.

Discover available service IDs from that response (for example: `network_isolator`, `wildlife_monitor`, `photo_booth`).

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

