"""Per-system data update coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .configuration import HubRuntime, LifecycleState, SystemRuntime
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    UPDATE_INTERVAL_ENTITY_KEY,
)
from .evaluator import (
    EvaluationContext,
    EvaluationError,
    evaluate_source_expressions,
)
from .exceptions import (
    ProviderAuthenticationError,
    ProviderError,
)
from .external_value import ExternalEntityValue
from .thetruth import DESCRIPTIONS

_LOGGER = logging.getLogger(__name__)

_OFFLINE_RETAINED_KEYS = frozenset(
    {
        "last_report",
        "report_delay",
        "status_reporting",
        "alerts_system",
        *(
            description.key
            for description in DESCRIPTIONS
            if getattr(description, "entity_category", None) == "config"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class RawStatusSnapshot:
    """Immutable raw status belonging to one runtime generation."""

    runtime_generation: int
    values: Mapping[str, Any]
    last_report: datetime | None
    last_update: datetime | None


class SystemCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and evaluate one system without affecting sibling systems."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub_runtime: HubRuntime,
        system_uid: str,
    ) -> None:
        runtime = hub_runtime.systems[system_uid]
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{runtime.system_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._hub_runtime = hub_runtime
        self._system_uid = system_uid
        self._raw_status_snapshot: RawStatusSnapshot | None = None
        self._evaluation_errors: Mapping[str, EvaluationError] = (
            MappingProxyType({})
        )
        self._evaluation_errors_changed_at: datetime | None = None
        self._provider_error: str | None = None
        self._provider_error_changed_at: datetime | None = None
        self._evaluated_values: Mapping[str, Any] = MappingProxyType({})
        self._external_entity_values: Mapping[str, ExternalEntityValue] = (
            MappingProxyType({})
        )

    @property
    def runtime(self) -> SystemRuntime:
        """Return the currently active immutable system runtime."""
        try:
            return self._hub_runtime.systems[self._system_uid]
        except KeyError as err:
            raise RuntimeError(
                f"System runtime {self._system_uid!r} is no longer active"
            ) from err

    @property
    def raw_status_snapshot(self) -> RawStatusSnapshot | None:
        """Return the most recent raw status snapshot."""
        return self._raw_status_snapshot

    @property
    def evaluation_errors(self) -> Mapping[str, EvaluationError]:
        """Return classified entity failures from the latest status update."""
        return self._evaluation_errors

    @property
    def evaluation_errors_changed_at(self) -> datetime | None:
        """Return when the current evaluation-error set last changed."""
        return self._evaluation_errors_changed_at

    @property
    def provider_error(self) -> str | None:
        """Return the redacted current provider failure class."""
        return self._provider_error

    @property
    def provider_error_changed_at(self) -> datetime | None:
        """Return when the redacted provider failure state last changed."""
        return self._provider_error_changed_at

    def _set_provider_error(self, error: ProviderError | None) -> None:
        current = type(error).__name__ if error is not None else None
        if current == self._provider_error:
            return
        self._provider_error = current
        self._provider_error_changed_at = datetime.now(timezone.utc)

    def external_entity_attributes(self, key: str) -> Mapping[str, Any]:
        """Return immutable attributes for one externally supplied entity."""
        external = self._external_entity_values.get(key)
        return external.attributes if external is not None else MappingProxyType({})

    def _combined_entity_values(self) -> dict[str, Any]:
        """Combine evaluated and permitted externally supplied entity values."""
        combined = dict(self._evaluated_values)
        dropped = getattr(
            self.runtime.configuration,
            "dropped_keys",
            frozenset(),
        )
        combined.update(
            {
                key: external.value
                for key, external in self._external_entity_values.items()
                if key in dropped
            }
        )
        if combined.get("status_reporting") is False:
            combined = {
                key: value if key in _OFFLINE_RETAINED_KEYS else None
                for key, value in combined.items()
            }
        return combined

    def _evaluate_source_values(
        self,
        runtime: SystemRuntime,
        source_values: Mapping[str, Any],
        *,
        last_report: datetime | None,
        last_update: datetime | None,
    ) -> dict[str, Any]:
        """Evaluate and publish one raw snapshot against the current clock."""
        result = evaluate_source_expressions(
            runtime.configuration.compiled_source_expressions,
            source_values,
            EvaluationContext(
                last_report=last_report,
                last_update=last_update,
            ),
        )
        self._set_evaluation_errors(result.errors, set(source_values))
        evaluated = result.values
        interval = evaluated.get(UPDATE_INTERVAL_ENTITY_KEY)
        if isinstance(interval, (int, float)) and not isinstance(interval, bool):
            # Apply the per-system interval before the next scheduled poll.
            self.update_interval = timedelta(seconds=float(interval))
        self._evaluated_values = MappingProxyType(dict(evaluated))
        return self._combined_entity_values()

    def async_set_external_entity_values(
        self,
        values: Mapping[str, ExternalEntityValue],
    ) -> None:
        """Replace values supplied for the configuration's dropped keys."""
        dropped = self.runtime.configuration.dropped_keys
        unexpected = set(values) - dropped
        if unexpected:
            raise ValueError(
                "External entity values require drop() expressions: "
                + ", ".join(sorted(unexpected))
            )
        replacement = MappingProxyType(
            {
                key: ExternalEntityValue(
                    value=external.value,
                    attributes=MappingProxyType(dict(external.attributes)),
                )
                for key, external in values.items()
            }
        )
        if replacement == self._external_entity_values:
            return
        self._external_entity_values = replacement
        combined = self._combined_entity_values()
        if combined != self.data:
            self.data = combined
            self.async_update_listeners()

    def _set_evaluation_errors(
        self,
        errors: Mapping[str, EvaluationError],
        source_keys: set[str],
    ) -> None:
        previous = tuple(
            sorted((key, error.category.value) for key, error in self._evaluation_errors.items())
        )
        current = tuple(
            sorted((key, error.category.value) for key, error in errors.items())
        )
        self._evaluation_errors = errors
        if current == previous:
            return
        self._evaluation_errors_changed_at = datetime.now(timezone.utc)
        available = ", ".join(sorted(source_keys)) or "(none)"
        if current:
            classified = ", ".join(f"{key}:{category}" for key, category in current)
            _LOGGER.warning(
                "Source-expression errors changed for system %s: %s; available source keys: %s",
                self._system_uid,
                classified,
                available,
            )
        else:
            _LOGGER.info(
                "Source-expression errors cleared for system %s; available source keys: %s",
                self._system_uid,
                available,
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and evaluate one internally consistent runtime snapshot."""
        if self._hub_runtime.lifecycle_state is not LifecycleState.ACTIVE:
            raise UpdateFailed("Hub runtime is not active")

        runtime = self.runtime
        task = asyncio.current_task()
        if task is not None:
            self._hub_runtime.track_refresh_task(task)

        try:
            provider_snapshot = await runtime.system.status(
                runtime.configuration.required_source_keys,
                runtime.configuration.source_keys,
            )
        except ProviderAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ProviderError as err:
            self._set_provider_error(err)
            snapshot = self._raw_status_snapshot
            if (
                snapshot is not None
                and snapshot.runtime_generation == runtime.runtime_generation
            ):
                _LOGGER.debug(
                    "Provider update failed for %s; reevaluating cached status",
                    self._system_uid,
                    exc_info=True,
                )
                return self._evaluate_source_values(
                    runtime,
                    snapshot.values,
                    last_report=snapshot.last_report,
                    last_update=snapshot.last_update,
                )
            raise UpdateFailed(str(err)) from err

        source_values = provider_snapshot.values
        snapshot_last_report = provider_snapshot.last_report
        snapshot_last_update = provider_snapshot.last_update
        if not isinstance(source_values, Mapping):
            raise UpdateFailed("Provider status must be a mapping")
        self._set_provider_error(None)

        immutable_source_values = MappingProxyType(dict(source_values))
        self._raw_status_snapshot = RawStatusSnapshot(
            runtime_generation=runtime.runtime_generation,
            values=immutable_source_values,
            last_report=snapshot_last_report,
            last_update=snapshot_last_update,
        )

        return self._evaluate_source_values(
            runtime,
            immutable_source_values,
            last_report=snapshot_last_report,
            last_update=snapshot_last_update,
        )
