"""Binary-sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .configuration import HubRuntime
from .description import EntityType
from .entity import SystemEntity
from .thetruth import DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all active binary sensors, grouped by system subentry."""
    del hass

    for coordinator in entry.runtime_data.coordinators.values():
        async_add_entities(
            [
                SystemBinarySensor(coordinator, description)
                for description in DESCRIPTIONS
                if description.entity_type is EntityType.BINARY_SENSOR
            ],
            config_subentry_id=coordinator.runtime.subentry_id,
        )


class SystemBinarySensor(SystemEntity, BinarySensorEntity):
    """Generic evaluated binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return a strict boolean state."""
        value = self.system_value
        return value if isinstance(value, bool) else None
