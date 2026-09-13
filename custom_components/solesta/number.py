"""Number platform and race-safe expression writes."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .configuration import HubRuntime
from .configuration_write import async_write_source_expression
from .const import DOMAIN
from .description import Description, EntityType
from .entity import SystemEntity
from .number_validation import NumberValidationError, validate_number_value
from .thetruth import DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all active numbers, grouped by system subentry."""
    del hass

    for coordinator in entry.runtime_data.coordinators.values():
        async_add_entities(
            [
                SystemNumber(coordinator, description, entry)
                for description in DESCRIPTIONS
                if description.entity_type is EntityType.NUMBER
            ],
            config_subentry_id=coordinator.runtime.subentry_id,
        )


class SystemNumber(SystemEntity, NumberEntity):
    """Writable Number whose persisted value is a source expression."""

    def __init__(
        self,
        coordinator,
        description: Description,
        entry: ConfigEntry[HubRuntime],
    ) -> None:
        super().__init__(coordinator, description)
        runtime = coordinator.runtime
        self._entry = entry
        self._hub_runtime = entry.runtime_data
        self._subentry_id = runtime.subentry_id

        if description.native_min_value is not None:
            self._attr_native_min_value = description.native_min_value
        if description.native_max_value is not None:
            self._attr_native_max_value = description.native_max_value
        if description.native_step is not None:
            self._attr_native_step = description.native_step
        if description.mode is not None:
            self._attr_mode = description.mode

    @property
    def native_value(self) -> float | None:
        """Return a finite, in-range evaluated Number value."""
        try:
            numeric, _ = validate_number_value(
                self.system_value,
                self._description,
            )
        except NumberValidationError:
            return None
        return numeric

    async def async_set_native_value(self, value: float) -> None:
        """Freeze only this Number expression to a validated numeric literal."""
        try:
            _, literal = validate_number_value(value, self._description)
        except NumberValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err
        await async_write_source_expression(
            hass=self.hass,
            entry=self._entry,
            hub_runtime=self._hub_runtime,
            coordinator=self.coordinator,
            subentry_id=self._subentry_id,
            system_uid=self._system_uid,
            entity_key=self._description.key,
            literal=literal,
        )
