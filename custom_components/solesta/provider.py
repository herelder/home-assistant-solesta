"""Backend-independent status-provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Collection, Mapping
from copy import deepcopy
import math
import re
from typing import Any

from .exceptions import (
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderSystemError,
)

_SOURCE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_SOURCE_SYSTEM_ID_LENGTH = 256


def _normalise_source_keys(keys: Collection[str]) -> tuple[str, ...]:
    """Return a deterministic, validated source-key tuple."""
    normalised: set[str] = set()
    for key in keys:
        if not isinstance(key, str) or not _SOURCE_KEY_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid source key: {key!r}")
        normalised.add(key)
    return tuple(sorted(normalised))


def _normalise_source_system_id(value: Any) -> str:
    """Return an opaque provider ID without imposing a textual format."""
    if value is None or isinstance(value, bool):
        raise ProviderResponseError("source-system ID is null or invalid")
    if isinstance(value, str):
        normalised = value.strip()
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ProviderResponseError("source-system ID number must be finite")
        normalised = str(value)
    else:
        raise ProviderResponseError("source-system ID must be text or a number")
    if not normalised:
        raise ProviderResponseError("source-system ID cannot be empty")
    if len(normalised) > _MAX_SOURCE_SYSTEM_ID_LENGTH:
        raise ProviderResponseError(
            "source-system ID exceeds the 256-character safety limit"
        )
    return normalised


def _normalise_configured_id(value: Any, label: str) -> str:
    """Return one bounded opaque identifier from trusted configuration."""
    try:
        return _normalise_source_system_id(value)
    except ProviderResponseError as err:
        raise ProviderConfigurationError(f"{label} is invalid") from err


def _normalise_duplicate_systems(
    duplicate_systems: Mapping[Any, Any],
) -> dict[str, str]:
    """Validate direct local-to-communication source-system aliases."""
    if not isinstance(duplicate_systems, Mapping):
        raise ProviderConfigurationError("duplicate_systems must be a mapping")
    result: dict[str, str] = {}
    for local_value, communication_value in duplicate_systems.items():
        local_id = _normalise_configured_id(
            local_value, "duplicate source-system ID"
        )
        communication_id = _normalise_configured_id(
            communication_value, "communication source-system ID"
        )
        if local_id == communication_id:
            raise ProviderConfigurationError(
                "duplicate and communication source-system IDs must differ"
            )
        if local_id in result:
            raise ProviderConfigurationError(
                "duplicate source-system IDs must be unique"
            )
        result[local_id] = communication_id
    if set(result) & set(result.values()):
        raise ProviderConfigurationError(
            "duplicate source-system mappings must be direct"
        )
    return result


class Provider(ABC):
    """Abstract provider with one-shot discovery and key-contract handling."""

    def __init__(
        self,
        *,
        provider_id: Any,
        duplicate_systems: Mapping[Any, Any] | None = None,
        configured_available_keys: Collection[str] = (),
    ) -> None:
        self._provider_id = _normalise_configured_id(
            provider_id, "provider ID"
        )
        self._duplicate_systems = _normalise_duplicate_systems(
            {} if duplicate_systems is None else duplicate_systems
        )
        try:
            configured = _normalise_source_keys(configured_available_keys)
        except ValueError as err:
            raise ProviderConfigurationError(
                "configured available_keys contains an invalid source key"
            ) from err
        self._configured_available_keys = configured
        self._effective_available_keys: frozenset[str] | None = (
            frozenset(configured) if configured else None
        )

        self._profile: dict[str, Any] | None = None
        self._communication_systems: tuple[str, ...] | None = None
        self._systems: tuple[str, ...] | None = None
        self._primed_status: dict[str, dict[str, Any]] = {}
        self._initialize_task: asyncio.Task[None] | None = None

    @property
    def provider_id(self) -> str:
        """Return this hub's local provider identity."""
        return self._provider_id

    @property
    def duplicate_systems(self) -> dict[str, str]:
        """Return a defensive copy of local-to-communication system aliases."""
        return dict(self._duplicate_systems)

    @property
    def configured_available_keys(self) -> tuple[str, ...]:
        """Return the persisted key override; empty means auto-discovery."""
        return self._configured_available_keys

    @property
    def available_keys(self) -> tuple[str, ...] | None:
        """Return effective keys, or None while no reliable set is known."""
        if self._effective_available_keys is None:
            return None
        return tuple(sorted(self._effective_available_keys))

    def unavailable_keys(self, source_keys: Collection[str]) -> list[str]:
        """Return requested keys that the current provider cannot confirm.

        This method is deliberately synchronous and provider-independent. An
        unknown effective keyset is conservative: every requested key is
        reported as unavailable.
        """
        required = _normalise_source_keys(source_keys)
        if not required:
            return []
        if self._effective_available_keys is None:
            return list(required)
        return [key for key in required if key not in self._effective_available_keys]

    @property
    def initialized(self) -> bool:
        """Return whether profile and systems discovery completed."""
        return self._profile is not None and self._systems is not None

    @property
    def profile(self) -> dict[str, Any]:
        """Return a defensive copy of the lifecycle-cached profile."""
        if self._profile is None:
            raise RuntimeError("Provider has not been initialized")
        return deepcopy(self._profile)

    @property
    def systems(self) -> tuple[str, ...]:
        """Return discovered source-system IDs plus configured local aliases."""
        if self._systems is None:
            raise RuntimeError("Provider has not been initialized")
        return self._systems

    @property
    def communication_systems(self) -> tuple[str, ...]:
        """Return only the source-system IDs reported by the remote provider."""
        if self._communication_systems is None:
            raise RuntimeError("Provider has not been initialized")
        return self._communication_systems

    async def async_initialize(self) -> None:
        """Open, connect, and perform discovery at most once per lifecycle.

        Concurrent callers share the same task. A failed task remains failed;
        retrying discovery therefore requires a fresh Provider instance and
        starts a new lifecycle.
        """
        if self._initialize_task is None:
            self._initialize_task = asyncio.create_task(
                self._async_initialize_once(),
                name=f"{type(self).__name__}.initialize",
            )
        await asyncio.shield(self._initialize_task)

    async def async_cancel_initialization(self) -> None:
        """Cancel and retrieve an in-flight initialization task."""
        task = self._initialize_task
        if (
            task is None
            or task.done()
            or task is asyncio.current_task()
        ):
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            # Closing owns resource cleanup; the original initializer owns
            # reporting its failure.
            pass

    async def _async_initialize_once(self) -> None:
        await self.async_open()
        await self.async_connect()

        raw_profile = await self._async_fetch_profile()
        if not isinstance(raw_profile, Mapping):
            raise ProviderResponseError("profile_flow did not return a mapping")
        profile = deepcopy(dict(raw_profile))

        raw_systems = await self._async_fetch_systems()
        if isinstance(raw_systems, (str, bytes, Mapping)):
            raise ProviderResponseError(
                "systems_flow did not return a collection of system IDs"
            )
        systems: list[str] = []
        seen: set[str] = set()
        for raw_source_system_id in raw_systems:
            source_system_id = _normalise_source_system_id(
                raw_source_system_id
            )
            if source_system_id not in seen:
                seen.add(source_system_id)
                systems.append(source_system_id)

        duplicate_collisions = set(systems) & set(self._duplicate_systems)
        if duplicate_collisions:
            raise ProviderResponseError(
                "duplicate source-system ID collides with provider discovery"
            )
        unknown_targets = set(self._duplicate_systems.values()) - set(systems)
        if unknown_targets:
            raise ProviderResponseError(
                "communication source-system ID is absent from provider discovery"
            )

        if not self._configured_available_keys and systems:
            await self._async_discover_available_keys(systems[0])

        # Publish both caches together only after all initialization work that
        # can fail definitively has succeeded.
        self._profile = profile
        self._communication_systems = tuple(systems)
        self._systems = (
            *self._communication_systems,
            *tuple(sorted(self._duplicate_systems)),
        )

    async def _async_discover_available_keys(
        self,
        source_system_id: str,
    ) -> None:
        """Best-effort discovery through exactly one source-system status."""
        try:
            status = await self._async_fetch_system_status(
                source_system_id,
                (),
            )
        except (ProviderCommunicationError, ProviderSystemError):
            # The provider/account is valid even if this individual system is
            # temporarily offline or cannot provide a status during setup.
            return

        if not isinstance(status, Mapping):
            raise ProviderResponseError(
                "system_status_flow did not return a mapping"
            )

        status_copy = deepcopy(dict(status))
        try:
            discovered = _normalise_source_keys(tuple(status_copy))
        except ValueError as err:
            raise ProviderResponseError(
                "system status contains an invalid source key"
            ) from err
        self._effective_available_keys = frozenset(discovered)
        self._primed_status[source_system_id] = status_copy

    async def get_system_status(
        self,
        source_system_id: str | int | float,
        source_keys: Collection[str],
    ) -> dict[str, Any]:
        """Return provider values for one source-system ID."""
        source_system_id = _normalise_source_system_id(source_system_id)
        await self.async_initialize()
        _normalise_source_keys(source_keys)

        primed = self._primed_status.pop(source_system_id, None)
        if primed is not None:
            return deepcopy(primed)

        communication_source_system_id = self._duplicate_systems.get(
            source_system_id, source_system_id
        )
        status = await self._async_fetch_system_status(
            communication_source_system_id,
            source_keys,
        )
        if not isinstance(status, Mapping):
            raise ProviderResponseError(
                "system_status_flow did not return a mapping"
            )
        status_copy = deepcopy(dict(status))
        try:
            _normalise_source_keys(tuple(status_copy))
        except ValueError as err:
            raise ProviderResponseError(
                "system status contains an invalid source key"
            ) from err
        return status_copy

    @abstractmethod
    async def async_open(self) -> None:
        """Open local provider resources; idempotent within a lifecycle."""

    @abstractmethod
    async def async_connect(self) -> None:
        """Establish the authenticated provider connection; idempotent."""

    @abstractmethod
    async def async_disconnect(self) -> None:
        """Disconnect remotely on best-effort basis; idempotent."""

    @abstractmethod
    async def async_close(self) -> None:
        """Close local provider resources; idempotent."""

    @abstractmethod
    async def _async_fetch_profile(self) -> Mapping[str, Any]:
        """Execute profile discovery once for this lifecycle."""

    @abstractmethod
    async def _async_fetch_systems(self) -> Collection[Any]:
        """Execute system discovery once for this lifecycle."""

    @abstractmethod
    async def _async_fetch_system_status(
        self,
        source_system_id: str,
        source_keys: Collection[str],
    ) -> Mapping[str, Any]:
        """Fetch one raw, expression-visible status mapping."""
