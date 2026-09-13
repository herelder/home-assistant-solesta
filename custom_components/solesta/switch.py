"""Switch platform for config entities backed by source expressions."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .configuration import HubRuntime
from .configuration_write import async_write_source_expression
from .description import Description, EntityType
from .entity import SystemEntity
from .thetruth import DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all active switches, grouped by system subentry."""
    del hass

    for coordinator in entry.runtime_data.coordinators.values():
        async_add_entities(
            [
                SystemSwitch(coordinator, description, entry)
                for description in DESCRIPTIONS
                if description.entity_type is EntityType.SWITCH
            ],
            config_subentry_id=coordinator.runtime.subentry_id,
        )


class SystemSwitch(SystemEntity, SwitchEntity):
    """Writable Switch whose persisted value is a source expression."""

    def __init__(
        self,
        coordinator,
        description: Description,
        entry: ConfigEntry[HubRuntime],
    ) -> None:
        super().__init__(coordinator, description)
        self._entry = entry
        self._hub_runtime = entry.runtime_data
        self._subentry_id = coordinator.runtime.subentry_id

    @property
    def is_on(self) -> bool | None:
        """Return a strict boolean state."""
        value = self.system_value
        return value if type(value) is bool else None

    async def _async_write(self, value: bool) -> None:
        await async_write_source_expression(
            hass=self.hass,
            entry=self._entry,
            hub_runtime=self._hub_runtime,
            coordinator=self.coordinator,
            subentry_id=self._subentry_id,
            system_uid=self._system_uid,
            entity_key=self._description.key,
            literal="True" if value else "False",
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Persist the enabled literal."""
        await self._async_write(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Persist the disabled literal."""
        await self._async_write(False)
