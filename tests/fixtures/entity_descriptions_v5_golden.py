"""Generated static Solesta EntityDescriptions.

DO NOT EDIT MANUALLY.
Source: tools/sources/EntityDescriptions_fixture.xlsx
Source SHA-256: source-hash
Generator: tools/generate_thetruth.py
Generator SHA-256: generator-hash
Catalog revision: 7
"""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

from .description import Description, EntityType


DESCRIPTIONS: list[Description] = [
    Description(
        key='update_interval',
        translation_key='update_interval',
        name='status update_interval in seconds',
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement='s',
        state_class=None,
        entity_category=EntityCategory.CONFIG,
        icon='mdi:timer-sync-outline',
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
        suggested_display_precision=0,
        has_entity_name=True,
        native_min_value=15,
        native_max_value=3600,
        native_step=15,
        mode=NumberMode.SLIDER,
        entity_type=EntityType.NUMBER,
        options=None,
        default_source_expression='15',
    ),
]
