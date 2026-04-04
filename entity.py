"""Entities for Perimeter Control services and dashboards."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, AVAILABLE_SERVICES, DEFAULT_API_PORT, CONF_SUPERVISOR_PORT

class PerimeterControlServiceEntity(Entity):
    def __init__(self, coordinator, service_id: str):
        self.coordinator = coordinator
        self.service_id = service_id
        self._attr_unique_id = f"{coordinator._entry.entry_id}_{service_id}"
        self._attr_name = f"{service_id.replace('_', ' ').title()} Dashboard"
        self._attr_should_poll = False

    @property
    def available(self):
        # Mark entity as available if the service is deployed
        return self.service_id in self.coordinator._selected_services

    @property
    def state(self):
        # Optionally, return 'active' if the dashboard is up
        data = self.coordinator.data or {}
        return "active" if data.get("dashboard_active", False) else "inactive"

    @property
    def extra_state_attributes(self):
        # Provide a dashboard URL for this service
        host = self.coordinator._entry.data.get("host")
        
        # Get service-specific port from service descriptor if available
        service_descriptor = self.coordinator._service_descriptors.get(self.service_id)
        if service_descriptor and hasattr(service_descriptor, 'access_profile'):
            port = service_descriptor.access_profile.get("port", DEFAULT_API_PORT)
        else:
            # Fallback to supervisor API port for unknown services
            port = self.coordinator._entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)
            
        url = f"http://{host}:{port}/{self.service_id}"
        return {"dashboard_url": url}

    @property
    def device_info(self) -> DeviceInfo:
        entry = self.coordinator._entry
        return DeviceInfo(
            identifiers = {(DOMAIN, entry.entry_id)},
            name = entry.title or f"Perimeter Node {entry.data.get('host')}",
            manufacturer = "Isolator",
            model = "Pi Node",
            configuration_url = f"http://{entry.data.get('host')}:{entry.data.get(CONF_SUPERVISOR_PORT, DEFAULT_API_PORT)}/",
            sw_version = None,
        )
