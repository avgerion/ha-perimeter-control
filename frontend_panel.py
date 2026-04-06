"""Frontend panel registration for Perimeter Control."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "perimeter_control"
URL_BASE = "/perimeter_control_static"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Perimeter Control frontend panel and serve static files."""
    
    # Only register once
    if DOMAIN in hass.data.get("frontend_panels", {}):
        _LOGGER.info("Panel already registered, skipping")
        return
    
    _LOGGER.info("Starting panel registration process")
        
    # Find our built frontend files
    integration_path = Path(__file__).parent
    frontend_path = integration_path / "frontend"
    
    _LOGGER.info("Integration path: %s", integration_path)
    _LOGGER.info("Frontend path: %s", frontend_path)
    _LOGGER.info("Frontend path exists: %s", frontend_path.exists())
    
    # Check if frontend files exist
    js_file = frontend_path / "ha-integration.js"
    _LOGGER.info("JS file path: %s", js_file)
    _LOGGER.info("JS file exists: %s", js_file.exists())
    if not js_file.exists():
        _LOGGER.error(
            "Frontend JavaScript file not found at %s. "
            "Directory contents: %s. "
            "Frontend path: %s",
            js_file, 
            list(frontend_path.iterdir()) if frontend_path.exists() else "Directory does not exist",
            frontend_path
        )
        return
    
    # Register static file serving for our frontend assets
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path=URL_BASE,
            path=str(frontend_path),
            cache_headers=True  # Enable caching for production use
        )
    ])
    
    # Register the custom panel
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path="perimeter-control",
        webcomponent_name="perimeter-control-panel", 
        sidebar_title="Perimeter Control",
        sidebar_icon="mdi:shield-outline",
        module_url=f"{URL_BASE}/ha-integration.js",
        embed_iframe=False,
        require_admin=False,
    )
    
    _LOGGER.info("Registered Perimeter Control frontend panel")


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister the Perimeter Control frontend panel."""
    from homeassistant.components import frontend
    
    # Remove the panel
    frontend.async_remove_panel(hass, "perimeter-control", warn_if_unknown=False)
    
    _LOGGER.info("Unregistered Perimeter Control frontend panel")