"""Switch platform for RS Solar API."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RSLocalApiCoordinator

CHARGE_BLOCK_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="charge_block",
    name="Charge Block",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: RSLocalApiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [RSChargeBlockSwitch(coordinator, entry, CHARGE_BLOCK_SWITCH_DESCRIPTION)]
    )


class RSChargeBlockSwitch(SwitchEntity):
    """Switch that controls the RS Solar charge block state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RSLocalApiCoordinator,
        entry: ConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
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
    def is_on(self) -> bool | None:
        """Return True if charge block is enabled."""
        state = self._coordinator.data.get("state")
        if state in (0, 1):
            return state == 1
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charge block."""
        await self._coordinator.async_set_state(1)
        await self._coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charge block."""
        await self._coordinator.async_set_state(0)
        await self._coordinator.async_request_refresh()
