"""Button entities for opening Perimeter Control service dashboards."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, AVAILABLE_SERVICES
from .coordinator import PerimeterControlCoordinator
import webbrowser

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: PerimeterControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PerimeterControlDashboardButton(coordinator, service_id)
        for service_id in AVAILABLE_SERVICES
    ]
    async_add_entities(entities)

class PerimeterControlDashboardButton(ButtonEntity):
    def __init__(self, coordinator, service_id: str):
        self.coordinator = coordinator
        self.service_id = service_id
        self._attr_unique_id = f"{coordinator._entry.entry_id}_{service_id}_dashboard_button"
        self._attr_name = f"Open {service_id.replace('_', ' ').title()} Dashboard"
        self._attr_should_poll = False

    @property
    def available(self):
        return self.service_id in self.coordinator._selected_services

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

    @property
    def extra_state_attributes(self):
        host = self.coordinator._entry.data.get("host")
        data = self.coordinator.data or {}
        ports = data.get("service_ports", {})
        port = ports.get(self.service_id, 8080)
        url = f"http://{host}:{port}/"
        return {"dashboard_url": url, "service_id": self.service_id, "port": port}

    async def async_press(self) -> None:
        host = self.coordinator._entry.data.get("host")
        data = self.coordinator.data or {}
        ports = data.get("service_ports", {})
        port = ports.get(self.service_id, 8080)
        url = f"http://{host}:{port}/"
        self.hass.bus.async_fire(
            "perimeter_control_dashboard_open",
            {"url": url, "service_id": self.service_id, "entry_id": self.coordinator._entry.entry_id}
        )
