# Perimeter Control — Home Assistant Integration

A reusable **Lit web component** for Home Assistant that enables end-to-end editing of service access profiles on a remote **Isolator Supervisor** instance.

## Features

- 🎛️ **Edit Access Profiles**: Mode, port, TLS settings, authentication, exposure scope
- 🔗 **CORS Origins Management**: Add/remove allowed origins with live preview
- 🎨 **Material Design**: Clean, accessible UI matching HA standards
- 📱 **Responsive**: Works on desktop and mobile clients
- ✅ **Validation**: Type-safe form inputs with field hints
- 🔄 **Real-time Sync**: Reflects server changes immediately
- 🚀 **Zero Dependencies**: Built with Lit, no heavy frameworks

## Installation

### Option 1: HACS (Recommended)

1. Add repository to HACS:
   ```yaml
   custom_repositories:
     - repository: https://github.com/isolator/isolator
       category: lovelace
   ```

2. Install "Perimeter Control" from HACS
3. Add to your Lovelace dashboard (see Usage below)

### Option 2: Manual Installation

```bash
# Clone and build
git clone https://github.com/isolator/isolator.git
cd ha-integration
npm install
npm run build

# Copy dist/ to your Home Assistant config
# .../config/www/isolator-service-access/
ls -la dist/
# dist/ha-integration.js
```

Then in your HA `configuration.yaml`:

```yaml
frontend:
  extra_module_url:
    - /local/isolator-service-access/ha-integration.js
```

## Usage

### Basic Card Configuration

Add to your Lovelace dashboard YAML:

```yaml
type: custom:perimeter-control-card
service_id: photo_booth
api_base_url: http://192.168.69.11:8080
```

### Multi-Service Fleet View (Advanced)

Create a view showing all services across multiple Pi instances:

```yaml
type: vertical-stack
cards:
  - type: heading
    heading: Service Fleet Configuration

  - type: entities
    title: Network Isolator Nodes
    entities:
      - entity_id: sensor.isolator_node_1_status

  - type: custom:layout-card
    layout_type: grid
    columns: 2
    cards:
      - type: custom:perimeter-control-card
        service_id: photo_booth
        api_base_url: http://pi-1.local:8080

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

- 🐛 Issues: [GitHub Issues](https://github.com/isolator/isolator/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/isolator/isolator/discussions)
- 📧 Email: isolator@example.com

