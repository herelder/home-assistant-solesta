"""Race-safe writes for config entities backed by source expressions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .configuration import HubRuntime, LifecycleState, is_active_system_subentry
from .const import (
    CONF_CONFIG_REVISION,
    CONF_REQUIRED_SOURCE_KEYS,
    CONF_SOURCE_EXPRESSIONS,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
)
from .coordinator import SystemCoordinator


async def async_write_source_expression(
    *,
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
    hub_runtime: HubRuntime,
    coordinator: SystemCoordinator,
    subentry_id: str,
    system_uid: str,
    entity_key: str,
    literal: str,
) -> None:
    """Persist one literal expression without losing concurrent changes."""
    refresh_generation: int | None = None

    async with hub_runtime.mutation_lock:
        if getattr(entry, "runtime_data", None) is not hub_runtime:
            raise HomeAssistantError(
                "The system runtime changed; retry the entity write"
            )
        if hub_runtime.lifecycle_state is not LifecycleState.ACTIVE:
            raise HomeAssistantError(
                "The system runtime is not active; retry the entity write"
            )

        subentry = entry.subentries.get(subentry_id)
        if subentry is None or subentry.unique_id != system_uid:
            raise HomeAssistantError("The configured system no longer exists")
        if not is_active_system_subentry(entry, subentry):
            raise HomeAssistantError(
                "The configured system is not active; retry the entity write"
            )

        stored_expressions = subentry.data.get(CONF_SOURCE_EXPRESSIONS)
        if not isinstance(stored_expressions, Mapping):
            raise HomeAssistantError("The system source expressions are invalid")

        current_runtime = hub_runtime.systems.get(system_uid)
        if (
            current_runtime is None
            or current_runtime.subentry_id != subentry.subentry_id
            or current_runtime.system_id != subentry.data.get(CONF_SYSTEM_ID)
            or current_runtime.source_system_id
            != subentry.data.get(CONF_SOURCE_SYSTEM_ID)
            or current_runtime.config_revision
            != subentry.data.get(CONF_CONFIG_REVISION)
            or dict(current_runtime.configuration.source_expressions)
            != dict(stored_expressions)
            or hub_runtime.coordinators.get(system_uid) is not coordinator
        ):
            raise HomeAssistantError(
                "The system configuration changed; retry the entity write"
            )
        current_configuration = current_runtime.configuration

        candidate = current_configuration.with_source_expression(entity_key, literal)
        if not candidate.required_source_keys.issubset(
            current_configuration.required_source_keys
        ):
            raise HomeAssistantError(
                "The entity write may not introduce new provider keys"
            )
        if current_configuration.source_expressions[entity_key] == literal:
            return

        config_revision = subentry.data.get(CONF_CONFIG_REVISION)
        if (
            not isinstance(config_revision, int)
            or isinstance(config_revision, bool)
            or config_revision < 1
        ):
            raise HomeAssistantError("The system configuration revision is invalid")
        next_revision = config_revision + 1

        updated_data = dict(subentry.data)
        updated_data[CONF_SOURCE_EXPRESSIONS] = candidate.stored_source_expressions()
        updated_data[CONF_REQUIRED_SOURCE_KEYS] = sorted(candidate.required_source_keys)
        updated_data[CONF_CONFIG_REVISION] = next_revision
        hass.config_entries.async_update_subentry(entry, subentry, data=updated_data)

        if (
            hub_runtime.lifecycle_state is LifecycleState.ACTIVE
            and is_active_system_subentry(entry, entry.subentries[subentry_id])
            and hub_runtime.coordinators.get(system_uid) is coordinator
        ):
            replacement = replace(
                current_runtime,
                config_revision=next_revision,
                configuration=candidate,
            )
            hub_runtime.systems[system_uid] = replacement
            refresh_generation = replacement.runtime_generation

    if refresh_generation is not None:
        hub_runtime.schedule_system_refresh(hass, system_uid, refresh_generation)
