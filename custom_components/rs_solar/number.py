"""Number platform for RS Solar API."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RSLocalApiCoordinator


CHARGE_BLOCK_POWER_NUMBER_DESCRIPTION = NumberEntityDescription(
    key="charge_block_power",
    name="Charge Block Power",
    native_min_value=-9000,
    native_max_value=0,
    native_step=1,
    native_unit_of_measurement=UnitOfPower.WATT,
)

CHARGE_LOAD_POWER_NUMBER_DESCRIPTION = NumberEntityDescription(
    key="charge_load_power",
    name="Charge Load Power",
    native_min_value=0,
    native_max_value=9000,
    native_step=1,
    native_unit_of_measurement=UnitOfPower.WATT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator: RSLocalApiCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            RSChargeBlockPowerNumber(
                coordinator,
                entry,
                CHARGE_BLOCK_POWER_NUMBER_DESCRIPTION,
            ),
            RSChargeLoadPowerNumber(
                coordinator,
                entry,
                CHARGE_LOAD_POWER_NUMBER_DESCRIPTION,
            ),
        ]
    )


class RSChargeBlockPowerNumber(
    CoordinatorEntity[RSLocalApiCoordinator],
    NumberEntity,
):
    """Number entity that controls the RS Solar charge block power."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RSLocalApiCoordinator,
        entry: ConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RS Solar Energy",
            model="RS Solar API",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current charge block power setpoint."""
        value = self.coordinator.data.get("block_power")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the charge block power."""
        await self.coordinator.async_set_charge_block_power(int(value))
        await self.coordinator.async_request_refresh()


class RSChargeLoadPowerNumber(
    CoordinatorEntity[RSLocalApiCoordinator],
    NumberEntity,
):
    """Number entity that controls the RS Solar charge load power."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RSLocalApiCoordinator,
        entry: ConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RS Solar Energy",
            model="RS Solar API",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current charge load power setpoint."""
        value = self.coordinator.data.get("load_power")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the charge load power."""
        await self.coordinator.async_set_charge_load_power(int(value))
        await self.coordinator.async_request_refresh()
