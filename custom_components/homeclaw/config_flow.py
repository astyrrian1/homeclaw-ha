import json
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, HomeclawClient, InvalidAuth
from .const import (
    CONF_CAPABILITY_MAPPINGS,
    CONF_EXECUTION_SECRET,
    CONF_HOUSE_MODE_ENTITY,
    DEFAULT_URL,
    DOMAIN,
)


class HomeclawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return HomeclawOptionsFlow(config_entry)

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


class HomeclawOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mappings = json.loads(user_input.pop("capability_mappings_json"))
                if not isinstance(mappings, dict):
                    raise ValueError("mapping must be an object")
            except (json.JSONDecodeError, ValueError):
                errors["base"] = "invalid_capability_mappings"
            else:
                return self.async_create_entry(
                    title="",
                    data={**user_input, CONF_CAPABILITY_MAPPINGS: mappings},
                )
        existing = self._entry.options
        mappings_json = json.dumps(existing.get(CONF_CAPABILITY_MAPPINGS, {}), indent=2)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXECUTION_SECRET,
                        default=existing.get(CONF_EXECUTION_SECRET, ""),
                    ): str,
                    vol.Optional(
                        CONF_HOUSE_MODE_ENTITY,
                        default=existing.get(CONF_HOUSE_MODE_ENTITY, ""),
                    ): str,
                    vol.Required("capability_mappings_json", default=mappings_json): str,
                }
            ),
            errors=errors,
        )
