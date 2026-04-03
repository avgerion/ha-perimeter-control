"""Perimeter Control — HA custom component for managing Isolator Pi edge nodes."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import PerimeterControlCoordinator
from .frontend_panel import async_register_panel, async_unregister_panel
from .http_views import async_register_views

_LOGGER = logging.getLogger(__name__)

# Service schemas
DEPLOY_SCHEMA = vol.Schema({
    vol.Optional("force", default=False): cv.boolean,
})

TRIGGER_CAPABILITY_SCHEMA = vol.Schema({
    vol.Required("capability"): cv.string,
    vol.Required("action"): cv.string,
    vol.Optional("config"): cv.string,
})

CAPABILITY_SCHEMA = vol.Schema({
    vol.Required("capability"): cv.string,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Perimeter Control integration."""
    hass.data.setdefault(DOMAIN, {})
    async_register_views(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Perimeter Control from a config entry."""
    # Diagnostic: Log loaded config entry data (redact SSH key)
    entry_data_redacted = dict(entry.data)
    if "ssh_key" in entry_data_redacted:
        key = entry_data_redacted["ssh_key"]
        entry_data_redacted["ssh_key"] = f"<redacted, len={len(key) if key else 0}>"
    _LOGGER.info("Setting up Perimeter Control for %s", entry_data_redacted.get("host"))

    # Register services FIRST - this ensures they're available even if coordinator fails
    if len(hass.data[DOMAIN]) == 0:  # Only on first integration setup
        await _register_services(hass)
        _LOGGER.info("Registered Perimeter Control services")
        
    # Register frontend panel early
    try:
        await async_register_panel(hass)
        _LOGGER.info("Registered Perimeter Control frontend panel")
    except Exception as exc:
        _LOGGER.warning("Failed to register frontend panel: %s", exc)

    # Try to create coordinator, but don't fail if it doesn't work initially
    try:
        coordinator = await PerimeterControlCoordinator.create(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = coordinator
        _LOGGER.info("Successfully created coordinator for %s", entry.data.get("host"))
        
        # Try initial refresh but don't fail setup if it doesn't work
        try:
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.info("Initial coordinator refresh succeeded")
        except Exception as exc:
            _LOGGER.warning("Initial coordinator refresh failed: %s. Will retry later.", exc)
            
    except Exception as exc:
        _LOGGER.error("Failed to create coordinator for %s: %s", entry.data.get("host"), exc)
        # Create a placeholder coordinator that can retry later
        from .coordinator import PerimeterControlCoordinator
        coordinator = PerimeterControlCoordinator(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = coordinator
        _LOGGER.info("Created placeholder coordinator, will retry connection later")

    # Set up platforms with dynamic entity discovery
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    async def handle_deploy(call: ServiceCall) -> None:
        """Handle deploy service call."""
        force = call.data.get("force", False)
        
        # Deploy to all configured devices
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                _LOGGER.info("Deploying to device %s (force=%s)", coordinator._entry.data.get("host"), force)
                success = await coordinator.async_deploy()
                if success:
                    _LOGGER.info("Deployment to %s completed successfully", coordinator._entry.data.get("host"))
                else:
                    _LOGGER.error("Deployment to %s failed", coordinator._entry.data.get("host"))

    async def handle_trigger_capability(call: ServiceCall) -> None:
        """Handle trigger_capability service call."""
        capability = call.data["capability"]
        action = call.data["action"]
        config = call.data.get("config")
        
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                try:
                    data = {"action": action}
                    if config:
                        import json
                        data["config"] = json.loads(config)
                    
                    result = await coordinator._supervisor_post(
                        f"/capabilities/{capability}/actions/{action}", 
                        data
                    )
                    _LOGGER.info("Triggered %s.%s on %s: %s", capability, action, 
                               coordinator._entry.data.get("host"), result)
                except Exception as exc:
                    _LOGGER.error("Failed to trigger %s.%s on %s: %s", capability, action,
                                coordinator._entry.data.get("host"), exc)

    async def handle_reload_config(call: ServiceCall) -> None:
        """Handle reload_config service call."""
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                await coordinator.async_request_refresh()
                _LOGGER.info("Reloaded config for %s", coordinator._entry.data.get("host"))

    async def handle_get_device_info(call: ServiceCall) -> None:
        """Handle get_device_info service call."""
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                try:
                    info = await coordinator._supervisor_get("/node/info")
                    _LOGGER.info("Device info for %s: %s", coordinator._entry.data.get("host"), info)
                except Exception as exc:
                    _LOGGER.error("Failed to get device info for %s: %s", 
                                coordinator._entry.data.get("host"), exc)

    async def handle_start_capability(call: ServiceCall) -> None:
        """Handle start_capability service call."""
        capability = call.data["capability"]
        
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                try:
                    result = await coordinator._supervisor_post(f"/capabilities/{capability}/deploy", {})
                    _LOGGER.info("Started capability %s on %s: %s", capability,
                               coordinator._entry.data.get("host"), result)
                except Exception as exc:
                    _LOGGER.error("Failed to start capability %s on %s: %s", capability,
                                coordinator._entry.data.get("host"), exc)

    async def handle_stop_capability(call: ServiceCall) -> None:
        """Handle stop_capability service call.""" 
        capability = call.data["capability"]
        
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, PerimeterControlCoordinator):
                try:
                    result = await coordinator._supervisor_post(f"/capabilities/{capability}/actions/stop", {})
                    _LOGGER.info("Stopped capability %s on %s: %s", capability,
                               coordinator._entry.data.get("host"), result)
                except Exception as exc:
                    _LOGGER.error("Failed to stop capability %s on %s: %s", capability,
                                coordinator._entry.data.get("host"), exc)

    # Register all services
    hass.services.async_register(DOMAIN, "deploy", handle_deploy, schema=DEPLOY_SCHEMA)
    hass.services.async_register(DOMAIN, "trigger_capability", handle_trigger_capability, schema=TRIGGER_CAPABILITY_SCHEMA)
    hass.services.async_register(DOMAIN, "reload_config", handle_reload_config)
    hass.services.async_register(DOMAIN, "get_device_info", handle_get_device_info)
    hass.services.async_register(DOMAIN, "start_capability", handle_start_capability, schema=CAPABILITY_SCHEMA)
    hass.services.async_register(DOMAIN, "stop_capability", handle_stop_capability, schema=CAPABILITY_SCHEMA)
    
    _LOGGER.info("Registered %d Perimeter Control services", 6)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: PerimeterControlCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        
        # Unregister services if this is the last entry
        if not hass.data[DOMAIN]:
            for service in ["deploy", "trigger_capability", "reload_config", "get_device_info", "start_capability", "stop_capability"]:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
            _LOGGER.info("Unregistered Perimeter Control services")
            
            # Unregister frontend panel  
            await async_unregister_panel(hass)
    return unloaded
