"""Sensor platform for RS Solar API."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArduinoLocalApiCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: ArduinoLocalApiCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        ArduinoSensor(
            coordinator=coordinator,
            entry=entry,
            unique_id=f"{entry.entry_id}_firmware_version",
            key="firmware_version",
            name="Firmware Version",
            device_class=None,
            state_class=None,
            unit=None,
        ),
        ArduinoSensor(
            coordinator=coordinator,
            entry=entry,
            unique_id=f"{entry.entry_id}_active_power_source_w",
            key="active_power_source_w",
            name="Active Power Source",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfPower.WATT,
        ),
        ArduinoSensor(
            coordinator=coordinator,
            entry=entry,
            unique_id=f"{entry.entry_id}_active_power_user_w",
            key="active_power_user_w",
            name="Active Power User",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfPower.WATT,
        ),
        ArduinoSensor(
            coordinator=coordinator,
            entry=entry,
            unique_id=f"{entry.entry_id}_power_source_status",
            key="power_source_status",
            name="Power Source Status",
            device_class=None,
            state_class=None,
            unit=None,
        ),
        ArduinoSensor(
            coordinator=coordinator,
            entry=entry,
            unique_id=f"{entry.entry_id}_power_user_status",
            key="power_user_status",
            name="Power User Status",
            device_class=None,
            state_class=None,
            unit=None,
        ),
    ]

    async_add_entities(entities)


class ArduinoSensor(SensorEntity):
    """Representation of an RS Solar API sensor."""

    def __init__(
        self,
        coordinator: ArduinoLocalApiCoordinator,
        entry: ConfigEntry,
        unique_id: str,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._attr_unique_id = unique_id
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="RS Solar Energy",
            model="RS Solar API",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def state(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self._coordinator.data.get(self._key)
