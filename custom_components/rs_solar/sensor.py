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

from .const import DOMAIN
from .coordinator import RSLocalApiCoordinator

STATE_OPTIONS = {
    0: "Normal",
    1: "Charge Block",
}

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        device_class=None,
        state_class=None,
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
        device_class=None,
        state_class=None,
    ),
    SensorEntityDescription(
        key="power_user_status",
        name="Power User Status",
        device_class=None,
        state_class=None,
    ),
    SensorEntityDescription(
        key="state",
        name="State",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: RSLocalApiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RSSolarSensor(coordinator, entry, description) for description in SENSOR_TYPES
    )


class RSSolarSensor(SensorEntity):
    """Representation of an RS Solar API sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RSLocalApiCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RS Solar Energy",
            model="RS Solar API",
        )
        if description.key == "state":
            self._attr_options = list(STATE_OPTIONS.values())

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def state(self) -> str | int | float | None:
        """Return the state of the sensor."""
        value = self._coordinator.data.get(self.entity_description.key)
        if self.entity_description.key == "state" and value in STATE_OPTIONS:
            return STATE_OPTIONS[value]
        return value
