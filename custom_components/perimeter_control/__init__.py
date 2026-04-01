"""Perimeter Control — HA custom component for managing Isolator Pi edge nodes."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import PerimeterControlCoordinator
from .http_views import async_register_views

_LOGGER = logging.getLogger(__name__)


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

    # Create coordinator with dynamic entity discovery
    coordinator = await PerimeterControlCoordinator.create(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms with dynamic entity discovery
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: PerimeterControlCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unloaded
