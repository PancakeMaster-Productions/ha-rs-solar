"""Config flow for RS Solar integration."""

from __future__ import annotations

import asyncio
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_PORT,
    CONF_POLL_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
)


async def _test_connection(hass: HomeAssistant, host: str, port: int) -> str | None:
    """Test the connection and return firmware version or None on failure."""
    url = f"http://{host}:{port}/api/v1/data"
    try:
        session = async_get_clientsession(hass)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            payload = data.get("data", {})
            return payload.get("firmware_version")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None


class ArduinoLocalApiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RS Solar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            poll_interval = user_input[CONF_POLL_INTERVAL]

            firmware = await _test_connection(self.hass, host, port)
            if firmware is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_POLL_INTERVAL: poll_interval,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    cv.positive_int, vol.Range(min=5, max=3600)
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
