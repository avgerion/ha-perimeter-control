"""Options flow for Perimeter Control integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_USER, CONF_SSH_KEY_PATH, CONF_HOST, CONF_PORT, CONF_SERVICES

class PerimeterControlOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_USER, default=data.get(CONF_USER, "")): str,
                vol.Required(CONF_SSH_KEY_PATH, default=data.get(CONF_SSH_KEY_PATH, "")): str,
                vol.Required(CONF_HOST, default=data.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=data.get(CONF_PORT, 22)): int,
                vol.Optional(CONF_SERVICES, default=data.get(CONF_SERVICES, [])): list,
            })
        )

@callback
def async_get_options_flow(config_entry):
    return PerimeterControlOptionsFlowHandler(config_entry)
