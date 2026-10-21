
"""Data coordinator for RS Solar."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
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

# Minimum interval between automatic restore attempts.
RESTORE_COOLDOWN = 30.0


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

        self._entry = entry

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]

        self._base_url = f"http://{host}:{port}"
        self._data_url = f"{self._base_url}/api/v1/data"
        self._state_url = f"{self._base_url}/api/v1/state"
        self._charge_block_url = (
            f"{self._base_url}/api/v1/charge-block"
        )
        self._charge_load_url = (
            f"{self._base_url}/api/v1/charge-load"
        )

        # Persist the desired state independently of the API state.
        self._desired_state_store = Store(
            hass,
            1,
            f"{DOMAIN}_{entry.entry_id}_desired_state",
        )

        self._desired_state: int | None = None

        # Serializes switch changes and automatic restoration.
        self._state_write_lock = asyncio.Lock()

        # None means no write has been attempted yet.
        self._last_state_write: float | None = None

    async def async_load_desired_state(self) -> None:
        """Load the desired state saved by Home Assistant."""
        stored = await self._desired_state_store.async_load()

        if not isinstance(stored, dict):
            return

        state = stored.get("state")

        if (
            isinstance(state, int)
            and not isinstance(state, bool)
            and state >= 0
        ):
            self._desired_state = state

            _LOGGER.debug(
                "RS Solar: loaded desired state %s",
                state,
            )

    @property
    def desired_state(self) -> int | None:
        """Return the desired state."""
        return self._desired_state

    async def _async_update_data(self) -> dict:
        """Fetch data and reconcile the reported state."""
        session = async_get_clientsession(self.hass)

        _LOGGER.debug(
            "RS Solar: fetching data from %s",
            self._data_url,
        )

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
        ) as err:
            raise UpdateFailed(
                f"Error communicating with RS Solar API: {err}"
            ) from err

        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error fetching RS Solar data: {err!r}"
            ) from err

        if not isinstance(data, dict):
            raise UpdateFailed(
                "Invalid API response: expected a JSON object"
            )

        payload = data.get("data")

        if not isinstance(payload, dict) or not payload:
            raise UpdateFailed(
                "No valid data in RS Solar API response"
            )

        _LOGGER.debug(
            "RS Solar: received data: %s",
            payload,
        )

        # Do not let a failed restore prevent normal sensor updates.
        await self._async_sync_desired_state(payload)

        return payload

    async def _async_sync_desired_state(
        self,
        payload: dict,
    ) -> None:
        """Initialize or restore the desired device state."""
        reported_state = payload.get("state")

        if (
            not isinstance(reported_state, int)
            or isinstance(reported_state, bool)
            or reported_state < 0
        ):
            return

        async with self._state_write_lock:
            # On first installation, adopt the current device state.
            # An existing saved state must never be overwritten here.
            if self._desired_state is None:
                await self._desired_state_store.async_save(
                    {"state": reported_state}
                )
                self._desired_state = reported_state

                _LOGGER.debug(
                    "RS Solar: initialized desired state to %s",
                    reported_state,
                )
                return

            desired_state = self._desired_state

            # Nothing to do when the device already matches.
            if reported_state == desired_state:
                return

            now = asyncio.get_running_loop().time()

            if (
                self._last_state_write is not None
                and now - self._last_state_write < RESTORE_COOLDOWN
            ):
                return

            # Record the attempt before sending. If the device rejects
            # the command, do not retry on every polling cycle.
            self._last_state_write = now

            _LOGGER.warning(
                "RS Solar: reported state is %s, desired state is %s. "
                "Attempting restoration.",
                reported_state,
                desired_state,
            )

            try:
                await self.async_set_state(desired_state)
            except (UpdateFailed, ValueError):
                _LOGGER.warning(
                    "RS Solar: failed to restore state %s; "
                    "will retry after cooldown",
                    desired_state,
                    exc_info=True,
                )
            else:
                _LOGGER.info(
                    "RS Solar: restore command sent for state %s",
                    desired_state,
                )

    async def async_set_switch_bit(
        self,
        mask: int,
        enabled: bool,
    ) -> None:
        """Change one switch bit and persist the desired state."""
        if mask not in (1, 2):
            raise ValueError("Unsupported switch bit mask")

        async with self._state_write_lock:
            current = self._desired_state

            if current is None:
                reported = self.data.get("state") if self.data else None

                if (
                    isinstance(reported, int)
                    and not isinstance(reported, bool)
                    and reported >= 0
                ):
                    current = reported
                else:
                    current = 0

            if enabled:
                new_state = current | mask
            else:
                new_state = current & ~mask

            # Save the user's intention before attempting the API write.
            await self._desired_state_store.async_save(
                {"state": new_state}
            )
            self._desired_state = new_state

            # A manual command also counts as a write attempt.
            self._last_state_write = (
                asyncio.get_running_loop().time()
            )

            await self.async_set_state(new_state)

            _LOGGER.info(
                "RS Solar: desired state set to %s",
                new_state,
            )

    async def async_set_state(self, state: int) -> None:
        """Set the RS Solar state via the API."""
        if (
                not isinstance(state, int)
                or isinstance(state, bool)
                or state < 0
        ):
            raise ValueError(
                "State must be a non-negative integer bitmask"
            )

        session = async_get_clientsession(self.hass)

        for attempt in range(2):
            try:
                async with session.post(
                        self._state_url,
                        json={"value": state},
                        headers={"Connection": "close"},
                        timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    response_text = await resp.text()

                    if not 200 <= resp.status < 300:
                        raise UpdateFailed(
                            "Unexpected HTTP status setting state: "
                            f"{resp.status}; response={response_text[:200]!r}"
                        )

                    _LOGGER.info(
                        "RS Solar: state %s accepted (HTTP %s)",
                        state,
                        resp.status,
                    )
                    return

            except aiohttp.ServerDisconnectedError:
                if attempt == 0:
                    _LOGGER.warning(
                        "RS Solar disconnected during state write; "
                        "retrying once after 1 second"
                    )
                    await asyncio.sleep(1)
                    continue
                raise UpdateFailed(
                    "RS Solar disconnected during both state-write attempts"
                ) from None

            except UpdateFailed:
                raise

            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise UpdateFailed(
                    f"Error setting RS Solar state to {state}: "
                    f"{type(err).__name__}: {err}"
                ) from err

    async def _async_set_value(
        self,
        url: str,
        value: int,
        action: str,
    ) -> None:
        """Set a numeric value via an RS Solar API endpoint."""
        session = async_get_clientsession(self.hass)

        try:
            async with session.post(
                url,
                json={"value": value},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if not 200 <= resp.status < 300:
                    raise UpdateFailed(
                        f"Unexpected HTTP status setting {action}: "
                        f"{resp.status}"
                    )

                try:
                    response_json = await resp.json()

                    if isinstance(response_json, dict):
                        _LOGGER.debug(
                            "RS Solar: %s feedback: %s",
                            action,
                            response_json.get("data"),
                        )
                except Exception:
                    # Some endpoints may return an empty response.
                    pass

        except UpdateFailed:
            raise

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as err:
            raise UpdateFailed(
                f"Error setting RS Solar {action}: {err}"
            ) from err

        _LOGGER.debug(
            "RS Solar: %s set to %s",
            action,
            value,
        )

    async def async_set_charge_block_power(
        self,
        power: int,
    ) -> None:
        """Set the charge block power via the API."""
        await self._async_set_value(
            self._charge_block_url,
            power,
            "charge block power",
        )

    async def async_set_charge_load_power(
        self,
        power: int,
    ) -> None:
        """Set the charge load power via the API."""
        await self._async_set_value(
            self._charge_load_url,
            power,
            "charge load power",
        )
