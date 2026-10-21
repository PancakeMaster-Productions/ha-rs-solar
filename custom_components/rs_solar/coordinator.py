
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

        # Persistent desired switch state.
        self._desired_state_store = Store(
            hass,
            1,
            f"{DOMAIN}_{entry.entry_id}_desired_state",
        )
        self._desired_state: int | None = None

        # Persistent desired power values.
        self._desired_power_store = Store(
            hass,
            1,
            f"{DOMAIN}_{entry.entry_id}_desired_power",
        )
        self._desired_block_power: int | None = None
        self._desired_load_power: int | None = None

        # Serialize switch writes and switch restoration.
        self._state_write_lock = asyncio.Lock()
        self._last_state_write: float | None = None

        # Power restoration has its own cooldown.
        self._last_block_power_write: float | None = None
        self._last_load_power_write: float | None = None

    async def async_load_desired_state(self) -> None:
        """Load the saved desired switch state."""
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

    async def async_load_desired_power(self) -> None:
        """Load saved desired power values."""
        stored = await self._desired_power_store.async_load()

        if not isinstance(stored, dict):
            return

        block_power = stored.get("block_power")
        load_power = stored.get("load_power")

        if (
            isinstance(block_power, int)
            and not isinstance(block_power, bool)
            and -9000 <= block_power <= 0
        ):
            self._desired_block_power = block_power

        if (
            isinstance(load_power, int)
            and not isinstance(load_power, bool)
            and 0 <= load_power <= 9000
        ):
            self._desired_load_power = load_power

        _LOGGER.debug(
            "RS Solar: loaded desired power values: block=%s, load=%s",
            self._desired_block_power,
            self._desired_load_power,
        )

    @property
    def desired_state(self) -> int | None:
        """Return the desired switch state."""
        return self._desired_state

    async def _async_update_data(self) -> dict:
        """Fetch API data and restore desired settings if needed."""
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

        # Restoration failures must not prevent sensor updates.
        await self._async_sync_desired_state(payload)
        await self._async_sync_desired_power(payload)

        return payload

    async def _async_sync_desired_state(
        self,
        payload: dict,
    ) -> None:
        """Initialize or restore the desired switch state."""
        reported_state = payload.get("state")

        if (
            not isinstance(reported_state, int)
            or isinstance(reported_state, bool)
            or reported_state < 0
        ):
            return

        async with self._state_write_lock:
            # First installation: adopt the current device state.
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

            if reported_state == desired_state:
                return

            now = asyncio.get_running_loop().time()

            if (
                self._last_state_write is not None
                and now - self._last_state_write < RESTORE_COOLDOWN
            ):
                return

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

    async def _async_sync_desired_power(
        self,
        payload: dict,
    ) -> None:
        """Initialize or restore the desired power values."""
        power_settings = (
            (
                "block_power",
                "_desired_block_power",
                self._charge_block_url,
                "charge block power",
            ),
            (
                "load_power",
                "_desired_load_power",
                self._charge_load_url,
                "charge load power",
            ),
        )

        for (
            key,
            desired_attribute,
            url,
            action,
        ) in power_settings:
            desired = getattr(self, desired_attribute)
            reported = payload.get(key)

            # Adopt API values on first installation only.
            if desired is None:
                if not isinstance(reported, (int, float)):
                    continue

                if isinstance(reported, bool):
                    continue

                if not float(reported).is_integer():
                    continue

                reported_int = int(reported)

                if key == "block_power":
                    if not -9000 <= reported_int <= 0:
                        continue
                elif not 0 <= reported_int <= 9000:
                    continue

                setattr(self, desired_attribute, reported_int)
                await self._async_save_desired_power()

                _LOGGER.debug(
                    "RS Solar: initialized desired %s to %s",
                    key,
                    reported_int,
                )
                continue

            if (
                not isinstance(reported, (int, float))
                or isinstance(reported, bool)
            ):
                continue

            if reported == desired:
                continue

            now = asyncio.get_running_loop().time()

            last_write_attribute = (
                "_last_block_power_write"
                if key == "block_power"
                else "_last_load_power_write"
            )
            last_write = getattr(self, last_write_attribute)

            if (
                last_write is not None
                and now - last_write < RESTORE_COOLDOWN
            ):
                continue

            setattr(self, last_write_attribute, now)

            _LOGGER.warning(
                "RS Solar: reported %s is %s, desired value is %s. "
                "Attempting restoration.",
                key,
                reported,
                desired,
            )

            try:
                await self._async_set_value(url, desired, action)
            except UpdateFailed:
                _LOGGER.warning(
                    "RS Solar: failed to restore %s; "
                    "will retry after cooldown",
                    action,
                    exc_info=True,
                )
            else:
                _LOGGER.info(
                    "RS Solar: restore command sent for %s: %s",
                    action,
                    desired,
                )

    async def _async_save_desired_power(self) -> None:
        """Persist the desired power values."""
        await self._desired_power_store.async_save(
            {
                "block_power": self._desired_block_power,
                "load_power": self._desired_load_power,
            }
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

            # Persist intention before attempting the API write.
            await self._desired_state_store.async_save(
                {"state": new_state}
            )
            self._desired_state = new_state
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
                            f"{resp.status}; "
                            f"response={response_text[:200]!r}"
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
                        "retrying once after 1 second",
                    )
                    await asyncio.sleep(1)
                    continue

                raise UpdateFailed(
                    "RS Solar disconnected during both state-write attempts"
                ) from None

            except UpdateFailed:
                raise

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as err:
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

        for attempt in range(2):
            try:
                async with session.post(
                    url,
                    json={"value": value},
                    headers={"Connection": "close"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    response_text = await resp.text()

                    if not 200 <= resp.status < 300:
                        raise UpdateFailed(
                            f"Unexpected HTTP status setting {action}: "
                            f"{resp.status}; "
                            f"response={response_text[:200]!r}"
                        )

                    _LOGGER.info(
                        "RS Solar: %s set to %s (HTTP %s)",
                        action,
                        value,
                        resp.status,
                    )
                    return

            except aiohttp.ServerDisconnectedError:
                if attempt == 0:
                    _LOGGER.warning(
                        "RS Solar disconnected while setting %s; "
                        "retrying once after 1 second",
                        action,
                    )
                    await asyncio.sleep(1)
                    continue

                raise UpdateFailed(
                    f"RS Solar disconnected during both attempts "
                    f"to set {action}"
                ) from None

            except UpdateFailed:
                raise

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as err:
                raise UpdateFailed(
                    f"Error setting RS Solar {action}: "
                    f"{type(err).__name__}: {err}"
                ) from err

    async def async_set_charge_block_power(
        self,
        power: int,
    ) -> None:
        """Set and persist charge block power."""
        if not -9000 <= power <= 0:
            raise ValueError(
                "Charge block power must be between -9000 and 0"
            )

        # Save the requested value before the API write. If the
        # connection drops after the device receives it, the desired
        # value remains available for reconciliation.
        self._desired_block_power = power
        await self._async_save_desired_power()

        self._last_block_power_write = (
            asyncio.get_running_loop().time()
        )
        await self._async_set_value(
            self._charge_block_url,
            power,
            "charge block power",
        )

    async def async_set_charge_load_power(
        self,
        power: int,
    ) -> None:
        """Set and persist charge load power."""
        if not 0 <= power <= 9000:
            raise ValueError(
                "Charge load power must be between 0 and 9000"
            )

        self._desired_load_power = power
        await self._async_save_desired_power()

        self._last_load_power_write = (
            asyncio.get_running_loop().time()
        )
        await self._async_set_value(
            self._charge_load_url,
            power,
            "charge load power",
        )
