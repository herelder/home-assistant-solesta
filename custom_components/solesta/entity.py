"""Common entity support."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MANUFACTURER, DOMAIN
from .coordinator import SystemCoordinator
from .description import Description


class SystemEntity(CoordinatorEntity[SystemCoordinator]):
    """Common implementation shared by all system entity platforms."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SystemCoordinator,
        description: Description,
    ) -> None:
        super().__init__(coordinator)

        runtime = coordinator.runtime
        self._system_uid = runtime.system_uid
        self._description = description

        # Registry identity is permanent and independent of the user-facing ID.
        self._attr_unique_id = f"{runtime.system_uid}_{description.key}"

        # Home Assistant owns entity_id generation and later user changes.
        self._attr_translation_key = description.translation_key
        self._attr_name = description.name
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = (
            description.native_unit_of_measurement
        )
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_entity_registry_visible_default = (
            description.entity_registry_visible_default
        )
        self._attr_suggested_display_precision = (
            description.suggested_display_precision
        )
        self._attr_has_entity_name = description.has_entity_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.system_uid)},
            name=runtime.system_id,
            manufacturer=DEFAULT_MANUFACTURER,
        )

    @property
    def system_value(self) -> Any:
        """Return this entity's latest evaluated value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._description.key)

    @property
    def system_attributes(self) -> dict[str, Any]:
        """Return attributes supplied through the generic coordinator contract."""
        getter = getattr(self.coordinator, "external_entity_attributes", None)
        if getter is None:
            return {}
        return dict(getter(self._description.key))
