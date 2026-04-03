# Perimeter Control — Home Assistant Integration

A **native Home Assistant integration** that provides complete management of **Isolator Pi edge nodes** through a clean, integrated user interface.

## Architecture

This integration connects your **Home Assistant server** to **remote Raspberry Pi target devices** running the Isolator Supervisor:

```
Home Assistant Server ──SSH Deploy──► Pi Target (192.168.50.47)
                      ◄─────API────── Supervisor (port 8080)
```

The integration provides:
- **Native HA Integration**: Appears in Settings → Devices & Services
- **Automated Setup**: No manual configuration.yaml editing required
- **Frontend Panel**: Integrated UI panel in HA sidebar
- **Service Discovery**: Automatic detection of Pi devices and their capabilities
- **SSH Deployment**: Deploy services directly from Home Assistant
- **Real-time Monitoring**: Live device status and service management

## Features

- 🏠 **Native HA Integration**: Full integration with Home Assistant's device & service management
- 📡 **Multi-Device Support**: Manage multiple Pi targets from one HA instance  
- 🚀 **One-Click Deployment**: Deploy and manage Pi services directly from HA
- 📊 **Service Management**: Start, stop, configure, and monitor Pi services
- 🔧 **Device Discovery**: Automatic detection of device capabilities and hardware
- ⚙️ **Configuration Flow**: Guided setup with SSH key management
- 📱 **Responsive UI**: Clean, mobile-friendly interface integrated into HA

## Installation

### Option 1: HACS (Recommended)

1. Add custom repository to HACS:
   ```yaml
   custom_repositories:
     - repository: https://github.com/avgerion/ha-perimeter-control
       category: integration
   ```

2. Install "Perimeter Control" from HACS
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Perimeter Control" and follow the setup

### Option 2: Manual Installation

1. Download/clone this repository
2. Copy the entire project directory to your Home Assistant custom_components:
   ```bash
   # Copy integration files
   cp -r /path/to/NetworkIsolator /config/custom_components/perimeter_control/
   ```
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "Perimeter Control" and configure

## Setup

### Adding a Pi Device

1. In Home Assistant, go to **Settings → Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Perimeter Control"**
4. Enter your Pi device details:
   - **Host**: IP address or hostname (e.g., `192.168.50.47`)
   - **Port**: SSH port (usually `22`)
   - **Username**: SSH username (e.g., `pi` or `paul`)
   - **SSH Key**: Your private key (multiline supported)
   - **Supervisor Port**: API port (usually `8080`)

### SSH Key Configuration

**Recommended approach** - use `secrets.yaml`:

```yaml
# secrets.yaml
perimeter_ssh_key: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAA...
  -----END OPENSSH PRIVATE KEY-----
```

Then reference it during setup: `!secret perimeter_ssh_key`

## Usage

### Accessing the Interface

Once configured:

1. **Perimeter Control** will appear as a **panel in your HA sidebar**
2. Click it to access the management interface
3. View all your configured Pi devices and their services
4. Deploy, start, stop, and configure services with one click

### Available Services

The integration registers these services in **Developer Tools → Services**:

- `perimeter_control.deploy` - Deploy supervisor and services to Pi
- `perimeter_control.trigger_capability` - Trigger specific capability actions
- `perimeter_control.start_capability` - Start a capability/service
- `perimeter_control.stop_capability` - Stop a capability/service  
- `perimeter_control.reload_config` - Reload device configuration
- `perimeter_control.get_device_info` - Get device hardware information

### Example Service Calls

```yaml
# Deploy to all configured devices
service: perimeter_control.deploy
data:
  force: true

# Start the photo booth service
service: perimeter_control.start_capability 
data:
  capability: photo_booth

# Trigger a BLE scan
service: perimeter_control.trigger_capability
data:
  capability: ble_scanner
  action: start_scan
  config: '{"duration": 30}'
```

      - type: custom:perimeter-control-card
        service_id: wildlife_monitor
        api_base_url: http://pi-1.local:8080

      - type: custom:perimeter-control-card
        service_id: ble_gatt_repeater
        api_base_url: http://pi-2.local:8080
```

## Configuration

All configuration happens in the YAML card definition:

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `type` | string | ✓ | - | Must be `custom:perimeter-control-card` |
| `service_id` | string | ✓ | - | Service ID from supervisor (`photo_booth`, etc.) |
| `api_base_url` | string | ✗ | `http://localhost:8080` | Supervisor API base URL |
| `service_name` | string | ✗ | Auto-loaded | Display name override |

## API Reference

The component communicates with the Supervisor API endpoints:

### Fetch Access Profile
```
GET /api/v1/services/{service_id}/access
```

Returns:
```json
{
  "service_id": "photo_booth",
  "access_profile": {
    "mode": "upstream",
    "bind_address": "",
    "port": 8093,
    "tls_mode": "self_signed",
    "auth_mode": "token",
    "allowed_origins": [],
    "exposure_scope": "lan_only"
  }
}
```

### Update Access Profile
```
PUT /api/v1/services/{service_id}/access
Content-Type: application/json

{
  "mode": "upstream",
  "bind_address": "",
  "port": 8093,
  "tls_mode": "self_signed",
  "auth_mode": "token",
  "allowed_origins": ["https://example.com"],
  "exposure_scope": "lan_only"
}
```

## Building from Source

### Prerequisites

- Node.js 18+
- npm 9+

### Build Steps

```bash
cd ha-integration

# Install dependencies
npm install

# Development mode (watch + dev server)
npm run dev

# Production build
npm run build

# Clean build artifacts
npm clean

# Lint code
npm run lint
```

**VS Code Integration:**
- **Ctrl+Shift+P → "Tasks: Run Task" → "Build HA Integration"** for one-time builds
- **Ctrl+Shift+P → "Tasks: Run Task" → "Watch HA Integration"** for auto-rebuild during development

Build output goes to `dist/`:
- `ha-integration.js` — Bundled HA card + editor component

## Development

### Project Structure

```
ha-integration/
├── src/
│   ├── service-access-editor.ts    # Main Lit component
│   └── home-assistant-card.ts      # HA card wrapper
├── dist/                            # Compiled output (build target)
├── package.json
├── tsconfig.json
├── manifest.json                    # HA integration metadata
└── README.md
```

### Component API

```typescript
// Direct web component usage (outside HA)
const editor = document.createElement('perimeter-control-service-access-editor');
editor.apiBaseUrl = 'http://192.168.69.11:8080';
editor.serviceId = 'photo_booth';
document.body.appendChild(editor);
```

### Styling Customization

Override CSS custom properties in your HA theme:

```yaml
# home-assistant/themes/isolator.yaml
isolator_service_editor:
  --primary-color: '#0066cc'
  --error-color: '#ff3333'
  --success-color: '#33cc33'
```

## Troubleshooting

### Component not loading

1. **Check browser console**: `F12` → Console tab for errors
2. **Verify API URL**: Can you reach `http://192.168.69.11:8080/api/v1/services` from your HA client?
3. **Check HA logs**: Look for JavaScript errors in Home Assistant dev console

### "API returned 401"

- Ensure Supervisor API is accessible from your HA client
- Check firewall rules blocking port 8080
- Verify service exists: `curl http://192.168.69.11:8080/api/v1/services`

### "Access profile updated but changes not reflected"

- Service may be restarting; wait a few seconds
- Reload the HA page (`F5`)
- Check Supervisor logs: `journalctl -u isolator-supervisor`

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

MIT — See [LICENSE](../../LICENSE) for details

## Contact

- 🐛 Issues: [GitHub Issues](https://github.com/avgerion/ha-perimeter-control/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/avgerion/ha-perimeter-control/discussions)
- 📧 Email: isolator@example.com

