# Perimeter Control

Manage your Raspberry Pi network gateway nodes directly from Home Assistant.

**What it does:**

- **Service Access Editor** — View and edit access profiles for services running on a Pi node (photo booth, BLE repeater, ESL AP, wildlife monitor, network isolator)
- **Fleet View** — Dashboard showing all Pi nodes, their hardware features (cameras, BLE adapters, GPIO, I²C), and service health at a glance
- **Deploy Panel** — Deploy updated code and configuration from HA to any Pi node with a single button tap — no Windows, no PowerShell, no separate terminal

**Key features:**

- Works entirely over SSH — no cloud, no extra broker
- Installs only the apt packages required by the services you've configured (GStreamer only if camera services are enabled, i2c-tools only if sensor services are present, etc.)
- Automatic rollback if a pushed update breaks the running service
- Safe HA integration — errors and API timeouts never affect Home Assistant itself

**Supported hardware:**

- Raspberry Pi (any model running Debian/Raspberry Pi OS)
- Multiple Pi nodes in a fleet (managed via separate card instances)

**Requirements:**

- [Isolator Supervisor](https://github.com/isolator/isolator) running on each Pi node
- Isolator Supervisor reachable from the HA host (direct route, SSH tunnel, or VPN)
- SSH key copied to the Pi (for deploy functionality)

**Setup:**

See [QUICKSTART.md](https://github.com/isolator/isolator/blob/main/ha-integration/QUICKSTART.md) for step-by-step instructions.

```yaml
type: custom:perimeter-control-card
api_base_url: "http://192.168.69.11:8080"
service_id: photo_booth

# Optional: show deploy panel
show_deploy_panel: true
entry_id: "<config_entry_id>"  # Find in HA Settings → Devices & Services → Perimeter Control
pi_host: "192.168.69.11"
services:
  - photo_booth
  - network_isolator
```

