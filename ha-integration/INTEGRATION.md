# Isolator Home Assistant Integration — Complete Reference

This directory contains all Home Assistant integration components for the Isolator Supervisor platform.

## Overview

The integration provides three layers of functionality:

1. **Service Access Editor** — Component for editing individual service access profiles
2. **Fleet View** — Dashboard for managing multiple Pi nodes and their hardware features
3. **Home Assistant Card Wrapper** — Integration scaffolding for HA's custom card system

## Components

### 1. Service Access Editor (`service-access-editor.ts`)

**Standalone web component** for editing access profiles.

```typescript
// Direct usage (outside HA)
const editor = document.createElement('perimeter-control-service-access-editor');
editor.apiBaseUrl = 'http://192.168.69.11:8080';
editor.serviceId = 'photo_booth';
document.body.appendChild(editor);
```

**Features:**
- Edit mode (isolated/upstream/passthrough)
- Port configuration
- TLS/authentication settings
- CORS origins management
- Material Design UI
- Real-time validation
- Success/error feedback

**API Used:**
- `GET /api/v1/services/{service_id}/access`
- `PUT /api/v1/services/{service_id}/access`

### 2. Fleet View (`fleet-view.ts`)

**Dashboard component** for managing multiple Isolator nodes.

```typescript
// In Home Assistant YAML
type: custom:perimeter-control-fleet-view
nodes:
  - url: http://192.168.69.11:8080
    name: "Primary Pi"
  - url: http://pi-2.local:8080
    name: "Secondary Pi"
autoRefresh: true
refreshInterval: 30000
```

**Features:**
- Multi-node node list with status indicators
- Real-time online/offline status
- Hardware feature inventory display
  - GPIO chips
  - I2C buses
  - Audio cards
  - GStreamer availability
  - Device tree configuration
- Service listing per node
- Integrated Service Access Editor for each service
- Auto-refresh capability

**APIs Used:**
- `GET /api/v1/node/features`
- `GET /api/v1/services`
- `PUT /api/v1/services/{service_id}/access` (via embedded editor)

### 3. HA Card Wrapper (`home-assistant-card.ts`)

**Home Assistant custom card** registration and configuration.

```yaml
# In HA Lovelace dashboard
type: custom:perimeter-control-card
service_id: photo_booth
api_base_url: http://192.168.69.11:8080
```

Configuration options:
- `service_id` (required) — Service identifier
- `api_base_url` (optional) — Supervisor API URL (default: `http://localhost:8080`)

## Installation & Setup

### Quick Start (5 minutes)

```bash
cd ha-integration
npm install
npm run build

# Copy to HA
cp dist/home-assistant-card.js ~/.homeassistant/www/isolator/

# Add to configuration.yaml
# frontend:
#   extra_module_url:
#     - /local/isolator/home-assistant-card.js
```

### Full Install (with HACS)

1. Open Home Assistant
2. Go to HACS → Frontend
3. Add repository: `https://github.com/isolator/isolator`
4. Install "Perimeter Control"
5. Restart Home Assistant
6. Add cards to Lovelace dashboard

### Development Setup

```bash
npm install
npm run dev
# Visit http://localhost:8000/index.html
```

## Build & Distribution

### Build Output

```
dist/
├── service-access-editor.js
├── fleet-view.js
└── home-assistant-card.js
```

Each file is:
- Minified (production ready)
- Type-safe (compiled from TypeScript)
- With source maps for debugging
- ES2020 module compatible

### Build Commands

```bash
npm run build          # Compile TypeScript
npm run watch         # Watch mode
npm run dev           # Development server with hot reload
npm run lint          # ESLint check
npm clean             # Remove dist/
```

## Architecture

### Component Hierarchy

```
home-assistant-card (wrapper)
└── service-access-editor (embedded)

fleet-view (dashboard)
├── node-list (sidebar)
└── service-access-editor (embedded per service)
```

### Data Flow

```
┌─────────────────────────────────────────┐
│  Home Assistant Lovelace Dashboard      │
├─────────────────────────────────────────┤
│                                         │
│  Fleet View Component                   │
│  ┌─────────────────────────────────┐   │
│  │ Node List      │ Content Panel   │   │
│  │                │                 │   │
│  │ [Pi-1] ────────► Features View   │   │
│  │ [Pi-2] ────────► Services View   │   │
│  │                │  ┌────────────┐ │   │
│  │                │  │ Service    │ │   │
│  │                │  │ Editor     │ │   │
│  │                │  │ (settings) │ │   │
│  │                │  └────────────┘ │   │
│  └─────────────────────────────────┘   │
│                    ↓                    │
│  HTTP API Calls (fetch)                 │
│  GET /api/v1/node/features              │
│  GET /api/v1/services                   │
│  PUT /api/v1/services/{id}/access       │
│                    ↓                    │
│  JSON Request/Response                  │
│                                         │
│  Supervisor (Python Tornado)            │
│  /api/v1/node/features → NodeFeatures   │
│  /api/v1/services → ServiceList         │
│  /api/v1/services/{id}/access → modify  │
│                                         │
└─────────────────────────────────────────┘
```

## Configuration Examples

### Single Service (Basic)

```yaml
type: custom:perimeter-control-card
service_id: photo_booth
```

### Single Node with Fleet View

```yaml
type: custom:perimeter-control-fleet-view
nodes:
  - url: http://192.168.69.11:8080
    name: "Main Pi"
```

### Multi-Node Network

```yaml
type: custom:perimeter-control-fleet-view
nodes:
  - url: http://pi-1.local:8080
    name: "Living Room"
  - url: http://pi-2.local:8080
    name: "Kitchen"
  - url: http://pi-3.local:8080
    name: "Garage"
  - url: http://pi-4.local:8080
    name: "Bedroom"
autoRefresh: true
refreshInterval: 30000
```

### Themed Integration

```yaml
# home-assistant/themes/isolator.yaml
isolator_manager:
  --primary-color: '#00796b'
  --error-color: '#c62828'
  --success-color: '#2e7d32'
```

## API Contract

All communication is with the Supervisor REST API.

### Node Features Endpoint

```
GET /api/v1/node/features
```

Response:
```json
{
  "node_features": {
    "gpio": { "chips": [...], "available": true },
    "i2c": { "buses": [...], "available": true },
    "audio": { "cards": [...], "available": true },
    "ble_adapters": [...],
    "uart": { "ports": [...], "available": true },
    "cameras": [],
    "spi": { "devices": [...], "available": false },
    "pwm": { "chips": [...], "available": false },
    "gstreamer": { "available": true, "version": "1.0.21", "key_elements": [...] },
    "hardware_config": { "dt_overlays": [...], "dt_params": {...} },
    "storage": [...]
  }
}
```

### Services Endpoint

```
GET /api/v1/services
```

Response:
```json
{
  "services": [
    {
      "id": "photo_booth",
      "name": "Photo Booth",
      "version": "1.0.0",
      "descriptor_file": "/mnt/isolator/conf/services/photo_booth.service.yaml",
      "runtime": "python_module",
      "config_file": "/mnt/isolator/conf/photo-booth.yaml"
    },
    ...
  ],
  "count": 5
}
```

### Access Profile Endpoint

```
GET /api/v1/services/{service_id}/access
```

Response:
```json
{
  "service_id": "photo_booth",
  "access_profile": {
    "mode": "upstream",
    "bind_address": "",
    "port": 8093,
    "tls_mode": "self_signed",
    "cert_file": "/etc/isolator/tls/fullchain.pem",
    "key_file": "/etc/isolator/tls/privkey.pem",
    "auth_mode": "token",
    "allowed_origins": [],
    "exposure_scope": "lan_only"
  }
}
```

```
PUT /api/v1/services/{service_id}/access
Content-Type: application/json

Request body:
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

## Extending the Integration

### Adding a New Component

1. Create `src/my-component.ts`
2. Export from `src/index.ts`
3. Build: `npm run build`
4. Test in `index.html` dev environment

### Custom Styling

Override CSS custom properties:

```html
<style>
  isolator-fleet-view {
    --primary: #0066cc;
    --success: #00aa00;
    --error: #ff0000;
  }
</style>
```

### Conditional Rendering

Components support conditional logic:

```typescript
// Only show if node is online
if (node.status === 'online') {
  this.loadNodeFeatures(node);
}
```

## Troubleshooting

### Component Not Loading

1. Check browser console: `F12 → Console`
2. Verify API reachability: `curl http://192.168.69.11:8080/api/v1/services`
3. Check HA logs: Settings → Logs
4. Clear browser cache: `Ctrl+Shift+Delete`

### API Connection Issues

- **Port closed**: Check firewall rules
- **DNS resolution**: Use IP instead of hostname
- **CORS errors**: Ensure Supervisor listens on accessible network interface
- **Timeout**: Add `?timeout=30` to API URL

### Build Errors

```bash
# Clear and rebuild
rm -rf node_modules dist
npm install
npm run build
```

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

MIT — See [LICENSE](../../LICENSE)

