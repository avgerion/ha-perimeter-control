# Quick Start — Isolator HA Integration

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

Output: `dist/service-access-editor.js` and `dist/home-assistant-card.js`

## 3. Deploy to Home Assistant

### Option A: Upload via UI (Easiest)

1. In HA, go to **Settings** → **Developer Tools** → **Template**
2. Paste this template to get your `www` folder:
   ```
   {{ data_dir + '/www' }}
   ```
3. Copy `dist/home-assistant-card.js` to `<HA_CONFIG>/www/isolator/`
4. Add to `configuration.yaml`:
   ```yaml
   frontend:
     extra_module_url:
       - /local/isolator/home-assistant-card.js
   ```

### Option B: SSH/SCP (Advanced)

```bash
scp dist/home-assistant-card.js user@homeassistant:/config/www/isolator/
```

## 4. Add to Dashboard

Create a new card in Lovelace:

```yaml
type: custom:perimeter-control-card
service_id: photo_booth
api_base_url: http://192.168.69.11:8080
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

