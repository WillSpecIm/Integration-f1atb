"""Config flow pour F1ATB Solar Router."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import F1atbApiError, F1atbClient
from .const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class F1atbConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ajout d'un routeur F1ATB (saisie de son IP/hostname)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = F1atbClient(async_get_clientsession(self.hass), host)
            try:
                config = await client.async_get_config()
            except F1atbApiError:
                errors["base"] = "cannot_connect"
            else:
                name = config.get("Routeur") or config.get("hostname") or host
                unique = config.get("hostname") or host
                await self.async_set_unique_id(str(unique))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=name, data={CONF_HOST: host})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
            description_placeholders={"exemple": "192.168.1.101"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return F1atbOptionsFlow()


class F1atbOptionsFlow(OptionsFlow):
    """Options : intervalle d'interrogation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=2, max=120)
                    )
                }
            ),
        )
