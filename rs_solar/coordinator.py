"""Data coordinator for RS Solar."""

from __future__ import annotations

from datetime import timedelta
import asyncio
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
    DataUpdateCoordinator,
)

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ArduinoLocalApiCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls the RS Solar."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        poll_interval = entry.data.get(CONF_POLL_INTERVAL, 30)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._url = f"http://{host}:{port}/api/v1/data"

    async def _async_update_data(self) -> dict:
        """Fetch data from the API."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Unexpected status code {resp.status}"
                    )
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        payload = data.get("data")
        if not payload:
            raise UpdateFailed("No data in response")

        return payload
