"""Sensor entities for Perimeter Control services and dashboards."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, AVAILABLE_SERVICES
from .coordinator import PerimeterControlCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PerimeterControlServiceSensor(coordinator, service_id)
        for service_id in AVAILABLE_SERVICES
    ]
    async_add_entities(entities)

class PerimeterControlServiceSensor(Entity):
    def __init__(self, coordinator, service_id: str):
        self.coordinator = coordinator
        self.service_id = service_id
        self._attr_unique_id = f"{coordinator._entry.entry_id}_{service_id}"
        self._attr_name = f"{service_id.replace('_', ' ').title()} Dashboard"
        self._attr_should_poll = False

    @property
    def available(self):
        return self.service_id in self.coordinator._selected_services

    @property
    def state(self):
        data = self.coordinator.data or {}
        # Use per-service status if available
        service_status = data.get("service_status", {})
        return "active" if service_status.get(self.service_id, False) else "inactive"

    @property
    def extra_state_attributes(self):
        host = self.coordinator._entry.data.get("host")
        # Use per-service port if available
        data = self.coordinator.data or {}
        ports = data.get("service_ports", {})
        port = ports.get(self.service_id, 8080)
        url = f"http://{host}:{port}/"
        return {"dashboard_url": url, "service_id": self.service_id, "port": port}

    @property
    def device_info(self) -> DeviceInfo:
        entry = self.coordinator._entry
        return DeviceInfo(
            identifiers = {(DOMAIN, entry.entry_id)},
            name = entry.title or f"Perimeter Node {entry.data.get('host')}",
            manufacturer = "Isolator",
            model = "Pi Node",
            configuration_url = f"http://{entry.data.get('host')}:8080/",
            sw_version = None,
        )
