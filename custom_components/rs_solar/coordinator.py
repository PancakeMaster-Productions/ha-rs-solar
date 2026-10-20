
"""Data coordinator for RS Solar."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RSLocalApiCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls the RS Solar API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=timedelta(
                seconds=max(
                    5,
                    int(
                        entry.data.get(
                            CONF_POLL_INTERVAL,
                            DEFAULT_POLL_INTERVAL,
                        )
                    ),
                )
            ),
        )

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]

        self._base_url = f"http://{host}:{port}"
        self._data_url = f"{self._base_url}/api/v1/data"
        self._state_url = f"{self._base_url}/api/v1/state"

    async def _async_update_data(self) -> dict:
        """Fetch data from the RS Solar API."""
        session = async_get_clientsession(self.hass)

        _LOGGER.debug("RS Solar: fetching data from %s", self._data_url)

        try:
            async with session.get(
                self._data_url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Unexpected HTTP status: {resp.status}"
                    )

                data = await resp.json()

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            aiohttp.ContentTypeError,
        ) as err:
            raise UpdateFailed(
                f"Error communicating with RS Solar API: {err}"
            ) from err

        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error fetching RS Solar data: {err!r}"
            ) from err

        if not isinstance(data, dict):
            raise UpdateFailed("Invalid API response: expected a JSON object")

        payload = data.get("data")

        if not isinstance(payload, dict) or not payload:
            raise UpdateFailed("No valid data in RS Solar API response")

        _LOGGER.debug("RS Solar: received data: %s", payload)

        return payload

    async def async_set_state(self, state: int) -> None:
        """Set the RS Solar state via the API."""
        if not isinstance(state, int) or state < 0:
            raise ValueError("State must be a non-negative integer bitmask")

        session = async_get_clientsession(self.hass)

        try:
            async with session.post(
                self._state_url,
                json={"value": state},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if not 200 <= resp.status < 300:
                    raise UpdateFailed(
                        f"Unexpected HTTP status setting state: {resp.status}"
                    )

                await resp.read()

        except UpdateFailed:
            raise

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as err:
            raise UpdateFailed(
                f"Error setting RS Solar state: {err}"
            ) from err

        _LOGGER.debug("RS Solar: state changed to %s", state)
