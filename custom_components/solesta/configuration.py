"""Persistent-schema and runtime-construction helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONFIG_REVISION,
    CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
    CONF_ENABLED,
    CONF_EXPRESSION_SCHEMA_VERSION,
    CONF_PROVIDER_REVISION,
    CONF_SOURCE_EXPRESSIONS,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
    CONF_VALIDATED_HUB_UID,
    CONF_VALIDATED_PROVIDER_REVISION,
    DOMAIN,
    EXPRESSION_SCHEMA_VERSION,
    SUBENTRY_TYPE_DUPLICATE_SYSTEM,
    SYSTEM_SUBENTRY_TYPES,
)
from .provider import Provider
from .runtime_configuration import RuntimeConfiguration
from .system import System
from .thetruth import DESCRIPTIONS

if TYPE_CHECKING:
    from .coordinator import SystemCoordinator

_LOGGER = logging.getLogger(__name__)


class LifecycleState(StrEnum):
    """Lifecycle of a loaded hub runtime."""

    ACTIVE = "active"
    QUIESCING = "quiescing"
    UNLOADED = "unloaded"


@dataclass(frozen=True, slots=True)
class SystemRuntime:
    """One immutable and internally consistent active-system snapshot."""

    subentry_id: str
    system_uid: str
    system_id: str
    source_system_id: str
    config_revision: int
    runtime_generation: int
    system: System
    configuration: RuntimeConfiguration


@dataclass(slots=True)
class HubRuntime:
    """All non-persistent state owned by one loaded hub entry."""

    hub_uid: str
    provider: Provider
    config_revision: int
    provider_revision: int
    runtime_generation: int = 1
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    systems: dict[str, SystemRuntime] = field(default_factory=dict)
    coordinators: dict[str, SystemCoordinator] = field(default_factory=dict)
    mutation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    refresh_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    reconcile_task: asyncio.Task[None] | None = None
    reconcile_requested: bool = False

    def begin_quiescing(self) -> None:
        """Close the gate for new runtime changes before unload awaits."""
        if self.lifecycle_state is LifecycleState.ACTIVE:
            self.lifecycle_state = LifecycleState.QUIESCING
            self.runtime_generation += 1

    def restore_active(self) -> None:
        """Restore a runtime after Home Assistant refused platform unload."""
        if self.lifecycle_state is not LifecycleState.QUIESCING:
            return

        self.lifecycle_state = LifecycleState.ACTIVE
        self.systems = {
            system_uid: replace(
                runtime,
                runtime_generation=self.runtime_generation,
            )
            for system_uid, runtime in self.systems.items()
        }

    def finish_unload(self) -> None:
        """Mark the runtime unusable after all resources have been closed."""
        self.lifecycle_state = LifecycleState.UNLOADED
        self.reconcile_requested = False
        if (
            self.reconcile_task is not None
            and self.reconcile_task is not asyncio.current_task()
            and not self.reconcile_task.done()
        ):
            self.reconcile_task.cancel()
        self.systems.clear()
        self.coordinators.clear()

    def track_refresh_task(self, task: asyncio.Task[Any]) -> None:
        """Track provider work so unload can wait before closing the provider."""
        self.refresh_tasks.add(task)
        task.add_done_callback(self.refresh_tasks.discard)

    async def async_wait_for_refreshes(self) -> None:
        """Wait for all provider updates that started before quiescing."""
        current = asyncio.current_task()
        pending = [
            task
            for task in self.refresh_tasks
            if task is not current and not task.done()
        ]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def schedule_system_refresh(
        self,
        hass: HomeAssistant,
        system_uid: str,
        runtime_generation: int,
    ) -> None:
        """Refresh one system only if the same active generation still exists."""

        async def _async_refresh_if_current() -> None:
            async with self.mutation_lock:
                runtime = self.systems.get(system_uid)
                coordinator = self.coordinators.get(system_uid)
                if (
                    self.lifecycle_state is not LifecycleState.ACTIVE
                    or runtime is None
                    or coordinator is None
                    or runtime.runtime_generation != runtime_generation
                ):
                    return

            await coordinator.async_request_refresh()

        task = hass.async_create_task(
            _async_refresh_if_current(),
            f"{DOMAIN} refresh {system_uid}",
        )
        self.track_refresh_task(task)

    def schedule_reconcile(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Coalesce config writes and reload only when runtime is stale."""
        self.reconcile_requested = True
        if self.reconcile_task is not None and not self.reconcile_task.done():
            return

        async def _async_reconcile() -> None:
            while self.reconcile_requested:
                self.reconcile_requested = False
                await asyncio.sleep(0)
                async with self.mutation_lock:
                    should_reload = (
                        self.lifecycle_state is LifecycleState.ACTIVE
                        and not self.matches_persistence(entry)
                    )

                if should_reload and entry.runtime_data is self:
                    await hass.config_entries.async_reload(entry.entry_id)
                    return

        task = hass.async_create_task(
            _async_reconcile(),
            f"{DOMAIN} reconcile {entry.entry_id}",
        )
        self.reconcile_task = task

        def _clear_reconcile(done: asyncio.Task[None]) -> None:
            if self.reconcile_task is done:
                self.reconcile_task = None
            if (
                self.reconcile_requested
                and self.lifecycle_state is LifecycleState.ACTIVE
            ):
                self.schedule_reconcile(hass, entry)

        task.add_done_callback(_clear_reconcile)

    def matches_persistence(self, entry: ConfigEntry) -> bool:
        """Return whether this runtime already represents current entry data."""
        if entry.unique_id != self.hub_uid:
            return False
        if entry.data.get(CONF_CONFIG_REVISION) != self.config_revision:
            return False
        if entry.data.get(CONF_PROVIDER_REVISION) != self.provider_revision:
            return False

        persistent_aliases = {
            str(subentry.data.get(CONF_SOURCE_SYSTEM_ID)): str(
                subentry.data.get(CONF_COMMUNICATION_SOURCE_SYSTEM_ID)
            )
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_DUPLICATE_SYSTEM
        }
        if persistent_aliases != self.provider.duplicate_systems:
            return False

        active = {
            str(subentry.unique_id): subentry
            for subentry in entry.subentries.values()
            if is_active_system_subentry(entry, subentry)
        }
        if set(active) != set(self.systems):
            return False

        for system_uid, subentry in active.items():
            runtime = self.systems[system_uid]
            if (
                runtime.subentry_id != subentry.subentry_id
                or runtime.system_id != subentry.data.get(CONF_SYSTEM_ID)
                or runtime.source_system_id
                != subentry.data.get(CONF_SOURCE_SYSTEM_ID)
                or runtime.config_revision
                != subentry.data.get(CONF_CONFIG_REVISION)
            ):
                return False

        return True


def default_source_expressions() -> dict[str, str]:
    """Return a fresh copy of all factory source expressions."""
    result: dict[str, str] = {}

    for description in DESCRIPTIONS:
        if description.default_source_expression is None:
            raise ValueError(
                f"Description {description.key!r} has no default source expression"
            )
        result[description.key] = description.default_source_expression

    return result


def is_active_system_subentry(
    entry: ConfigEntry,
    subentry: ConfigSubentry,
) -> bool:
    """Apply the complete persistent predicate for an active system."""
    provider_revision = entry.data.get(CONF_PROVIDER_REVISION)
    config_revision = subentry.data.get(CONF_CONFIG_REVISION)

    return (
        subentry.subentry_type in SYSTEM_SUBENTRY_TYPES
        and isinstance(subentry.unique_id, str)
        and bool(subentry.unique_id)
        and subentry.data.get(CONF_ENABLED) is True
        and isinstance(config_revision, int)
        and not isinstance(config_revision, bool)
        and config_revision >= 1
        and subentry.data.get(CONF_EXPRESSION_SCHEMA_VERSION)
        == EXPRESSION_SCHEMA_VERSION
        and subentry.data.get(CONF_VALIDATED_HUB_UID) == entry.unique_id
        and subentry.data.get(CONF_VALIDATED_PROVIDER_REVISION)
        == provider_revision
    )


def build_system_runtimes(
    entry: ConfigEntry,
    provider: Provider,
    runtime_generation: int,
    *,
    invalid_subentry_ids: set[str] | frozenset[str] = frozenset(),
) -> dict[str, SystemRuntime]:
    """Build all active systems from ConfigSubentries."""
    systems: dict[str, SystemRuntime] = {}

    for subentry in entry.subentries.values():
        if (
            subentry.subentry_id in invalid_subentry_ids
            or not is_active_system_subentry(entry, subentry)
        ):
            continue

        system_uid = str(subentry.unique_id)
        if system_uid in systems:
            raise ValueError(f"Duplicate system_uid in hub: {system_uid}")

        try:
            system_id = _required_non_empty_string(
                subentry.data,
                CONF_SYSTEM_ID,
            )
            source_system_id = _required_non_empty_string(
                subentry.data,
                CONF_SOURCE_SYSTEM_ID,
            )
            config_revision = _required_positive_int(
                subentry.data,
                CONF_CONFIG_REVISION,
            )
            source_expressions = subentry.data.get(CONF_SOURCE_EXPRESSIONS)
            if not isinstance(source_expressions, Mapping):
                raise ValueError("source_expressions must be a mapping")

            configuration = RuntimeConfiguration.compile(source_expressions)
            system = System(
                system_uid=system_uid,
                system_id=system_id,
                source_system_id=source_system_id,
                provider=provider,
            )
        except (KeyError, TypeError, ValueError):
            _LOGGER.error(
                "System subentry %s has invalid local configuration",
                subentry.subentry_id,
                exc_info=True,
            )
            continue

        systems[system_uid] = SystemRuntime(
            subentry_id=subentry.subentry_id,
            system_uid=system_uid,
            system_id=system_id,
            source_system_id=source_system_id,
            config_revision=config_revision,
            runtime_generation=runtime_generation,
            system=system,
            configuration=configuration,
        )

    return systems


def _required_non_empty_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_positive_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value
