"""Sensor platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAX_LENGTH_STATE_STATE
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
    """Set up all active sensors, grouped by system subentry."""
    del hass

    for coordinator in entry.runtime_data.coordinators.values():
        async_add_entities(
            [
                SystemSensor(coordinator, description)
                for description in DESCRIPTIONS
                if description.entity_type is EntityType.SENSOR
            ],
            config_subentry_id=coordinator.runtime.subentry_id,
        )


class SystemSensor(SystemEntity, SensorEntity):
    """Generic evaluated sensor."""

    def __init__(self, coordinator, description) -> None:
        super().__init__(coordinator, description)
        if description.options is not None:
            self._attr_options = list(description.options)

    def _unbounded_native_value(self) -> Any:
        """Return the converted value before applying HA's state limit."""
        value = self.system_value

        if (
            value is not None
            and self._description.device_class is SensorDeviceClass.TIMESTAMP
        ):
            try:
                if isinstance(value, datetime):
                    return value
                if isinstance(value, (int, float)) and not isinstance(
                    value,
                    bool,
                ):
                    return datetime.fromtimestamp(value, tz=timezone.utc)
                if isinstance(value, str):
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        return parsed.replace(tzinfo=timezone.utc)
                    return parsed
            except (OSError, OverflowError, ValueError):
                return None

            return None

        return value

    @property
    def native_value(self) -> Any:
        """Return the value, truncated only when HA cannot store it as state."""
        value = self._unbounded_native_value()
        if isinstance(value, str) and len(value) > MAX_LENGTH_STATE_STATE:
            return value[: MAX_LENGTH_STATE_STATE - 1] + "…"
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose coordinator attributes and preserve truncated source lines."""
        attributes = self.system_attributes
        value = self._unbounded_native_value()
        if isinstance(value, str) and len(value) > MAX_LENGTH_STATE_STATE:
            attributes.update(lines=value.splitlines(), truncated=True)
        return attributes or None
