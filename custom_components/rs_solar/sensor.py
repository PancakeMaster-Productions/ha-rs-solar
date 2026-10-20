
"""Sensor platform for RS Solar API."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RSLocalApiCoordinator


STATE_OPTIONS = {
    0: "Normal",
    1: "Charge Block",
    2: "Force Load",
    3: "Charge Block + Force Load",
}


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
    ),
    SensorEntityDescription(
        key="active_power_source_w",
        name="Active Power Source",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="active_power_user_w",
        name="Active Power User",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="power_source_status",
        name="Power Source Status",
    ),
    SensorEntityDescription(
        key="power_user_status",
        name="Power User Status",
    ),
    SensorEntityDescription(
        key="state",
        name="State",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATE_OPTIONS.values()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: RSLocalApiCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RSSolarSensor(coordinator, entry, description)
        for description in SENSOR_TYPES
    )


class RSSolarSensor(CoordinatorEntity[RSLocalApiCoordinator], SensorEntity):
    """Representation of an RS Solar API sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RSLocalApiCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self) -> str | int | float | None:
        """Return the current sensor value."""
        value = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.key == "state":
            if isinstance(value, int):
                return STATE_OPTIONS.get(value)

        return value
