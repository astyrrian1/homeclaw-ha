from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, HomeclawClient, InvalidAuth
from .const import DEFAULT_URL, DOMAIN


class HomeclawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input:
            client = HomeclawClient(
                async_get_clientsession(self.hass),
                user_input[CONF_URL],
                user_input[CONF_ACCESS_TOKEN],
            )
            try:
                await client.validate()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id("homeclaw")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Homeclaw", data=user_input)
        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=DEFAULT_URL): str,
                vol.Required(CONF_ACCESS_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
