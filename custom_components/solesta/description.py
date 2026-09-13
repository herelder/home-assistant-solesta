"""Static entity-description types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory


class EntityType(StrEnum):
    """Supported entity platforms."""

    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    NUMBER = "number"
    SWITCH = "switch"


@dataclass(frozen=True, kw_only=True, slots=True)
class Description:
    """Generated metadata and factory expression for one entity."""

    key: str
    translation_key: str | None = None
    name: str | None = None
    device_class: (
        SensorDeviceClass
        | BinarySensorDeviceClass
        | NumberDeviceClass
        | None
    ) = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    suggested_display_precision: int | None = None
    has_entity_name: bool = True
    native_min_value: float | None = None
    native_max_value: float | None = None
    native_step: float | None = None
    mode: NumberMode | None = None
    entity_type: EntityType = EntityType.SENSOR
    options: tuple[str, ...] | None = None
    default_source_expression: str | None = None
