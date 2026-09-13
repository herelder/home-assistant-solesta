"""Set up and unload provider hubs."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from collections.abc import Mapping
import logging
from uuid import UUID

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .configuration import (
    HubRuntime,
    LifecycleState,
    build_system_runtimes,
)
from .const import (
    CONF_AVAILABLE_KEYS,
    CONF_BASE_URL,
    CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
    CONF_CONFIG_REVISION,
    CONF_CONNECTION,
    CONF_KIND,
    CONF_PROVIDER_ID,
    CONF_PROVIDER_REVISION,
    CONF_PROTOCOL,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
    DATA_ARCHIVE_MANAGER,
    DOMAIN,
    HUB_KIND_PROVIDER,
    PROTOCOL_WEB_API,
    SUBENTRY_TYPE_DUPLICATE_SYSTEM,
    SYSTEM_SUBENTRY_TYPES,
)
from .coordinator import SystemCoordinator
from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderError,
    ProviderRateLimitError,
)
from .provider import Provider
from .provider_defaults import SOLESTA_WEB_API_DEFAULT
from .web_api import WebApiProvider

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the dashboard card and archiving once for all provider hubs."""
    from .archive import async_setup_archiving
    from .frontend import async_setup_frontend

    await async_setup_frontend(hass)
    await async_setup_archiving(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
) -> bool:
    """Set up one hub and its active system subentries."""
    hub_uid = _canonical_uuid4(entry.unique_id, "hub unique ID")
    try:
        provider = _build_provider(hass, entry)
    except ProviderError as err:
        raise ConfigEntryError(str(err)) from err
    provider_started = False
    hub_runtime: HubRuntime | None = None

    stored_provider_id = provider.provider_id
    if any(
        other.entry_id != entry.entry_id
        and _entry_provider_id(other) == stored_provider_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        raise ConfigEntryError("The local provider ID is used by another hub")

    try:
        provider_started = True
        # This runs profile and systems once per provider lifecycle and may use
        # one discovered system to establish the effective source-key contract.
        await provider.async_initialize()

        hub_runtime = HubRuntime(
            hub_uid=hub_uid,
            provider=provider,
            config_revision=_positive_revision(entry, CONF_CONFIG_REVISION),
            provider_revision=_positive_revision(
                entry,
                CONF_PROVIDER_REVISION,
            ),
        )
        invalid_subentries = _invalid_identity_subentries(hass, entry)
        hub_runtime.systems = build_system_runtimes(
            entry,
            provider,
            hub_runtime.runtime_generation,
            invalid_subentry_ids=invalid_subentries,
        )
        hub_runtime.coordinators = {
            system_uid: SystemCoordinator(
                hass,
                entry,
                hub_runtime,
                system_uid,
            )
            for system_uid in hub_runtime.systems
        }
        entry.runtime_data = hub_runtime

        # Normal first-refresh errors remain local to their system coordinator.
        # Authentication was already established at hub level above.
        await asyncio.gather(
            *(
                coordinator.async_refresh()
                for coordinator in hub_runtime.coordinators.values()
            )
        )
        for coordinator in hub_runtime.coordinators.values():
            if isinstance(
                coordinator.last_exception,
                ConfigEntryAuthFailed,
            ):
                raise ConfigEntryAuthFailed(
                    str(coordinator.last_exception)
                ) from coordinator.last_exception

        archive_manager = getattr(hass, "data", {}).get(DATA_ARCHIVE_MANAGER)
        if archive_manager is not None:
            for coordinator in hub_runtime.coordinators.values():
                archive_manager.attach_coordinator(coordinator)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    except ProviderAuthenticationError as err:
        await _async_cleanup_failed_setup(
            hass, entry, hub_runtime, provider, provider_started
        )
        raise ConfigEntryAuthFailed(str(err)) from err
    except (ProviderCommunicationError, ProviderRateLimitError) as err:
        await _async_cleanup_failed_setup(
            hass, entry, hub_runtime, provider, provider_started
        )
        raise ConfigEntryNotReady(str(err)) from err
    except ProviderError as err:
        await _async_cleanup_failed_setup(
            hass, entry, hub_runtime, provider, provider_started
        )
        raise ConfigEntryError(str(err)) from err
    except asyncio.CancelledError:
        await _async_cleanup_failed_setup(
            hass, entry, hub_runtime, provider, provider_started
        )
        raise
    except Exception:
        await _async_cleanup_failed_setup(
            hass, entry, hub_runtime, provider, provider_started
        )
        raise

    _LOGGER.info(
        "Loaded provider hub with %d active system(s)",
        len(entry.runtime_data.systems),
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
) -> bool:
    """Unload platforms before closing the shared provider."""
    runtime = entry.runtime_data
    archive_manager = getattr(hass, "data", {}).get(DATA_ARCHIVE_MANAGER)
    if archive_manager is not None:
        archive_manager.detach_coordinators(runtime.coordinators.values())
    runtime.begin_quiescing()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
    if not unload_ok:
        runtime.restore_active()
        if archive_manager is not None:
            for coordinator in runtime.coordinators.values():
                archive_manager.attach_coordinator(coordinator)
        if runtime.reconcile_requested:
            runtime.schedule_reconcile(hass, entry)
        return False

    await runtime.async_wait_for_refreshes()
    try:
        try:
            await runtime.provider.async_disconnect()
        except ProviderError:
            _LOGGER.debug("Remote provider disconnect failed", exc_info=True)
    finally:
        await runtime.provider.async_close()

    runtime.finish_unload()
    return True


async def _async_entry_updated(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
) -> None:
    """Defer and coalesce persistence/runtime reconciliation."""
    runtime = getattr(entry, "runtime_data", None)
    if not isinstance(runtime, HubRuntime):
        return
    if runtime.lifecycle_state is LifecycleState.UNLOADED:
        return
    if runtime.lifecycle_state is LifecycleState.QUIESCING:
        runtime.reconcile_requested = True
        return
    runtime.schedule_reconcile(hass, entry)


def _build_provider(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> WebApiProvider:
    """Build the configured provider without performing network I/O."""
    if entry.data.get(CONF_KIND) != HUB_KIND_PROVIDER:
        raise ConfigEntryError("Unsupported hub kind")
    protocol = entry.data.get(CONF_PROTOCOL)
    if protocol != PROTOCOL_WEB_API:
        raise ConfigEntryError(f"Unsupported protocol: {protocol!r}")

    base_url = entry.data.get(CONF_BASE_URL)
    connection = entry.data.get(CONF_CONNECTION)
    configured_available_keys = entry.data.get(CONF_AVAILABLE_KEYS, [])
    if not isinstance(base_url, str) or not base_url:
        raise ConfigEntryError("base_url must be a non-empty string")
    if not isinstance(connection, Mapping):
        raise ConfigEntryError("connection must be a mapping")
    if not isinstance(configured_available_keys, list):
        raise ConfigEntryError("available_keys must be a list")

    provider = WebApiProvider(
        hass,
        base_url=base_url,
        connection=connection,
        preset=SOLESTA_WEB_API_DEFAULT,
        provider_id=_entry_provider_id(entry),
        duplicate_systems=_duplicate_systems(entry),
        configured_available_keys=configured_available_keys,
    )
    if _entry_provider_id(entry) != provider.provider_id:
        raise ConfigEntryError("Stored provider ID does not match the hub")
    return provider


def _entry_provider_id(entry: ConfigEntry) -> str:
    """Return the hub's required local provider ID."""
    value = entry.data.get(CONF_PROVIDER_ID)
    if not isinstance(value, str) or not value:
        raise ConfigEntryError("provider_id must be a non-empty string")
    return value

def _duplicate_systems(entry: ConfigEntry) -> dict[str, str]:
    """Build aliases solely from removable duplicate-system subentries."""
    result: dict[str, str] = {}
    for subentry in entry.get_subentries_of_type(
        SUBENTRY_TYPE_DUPLICATE_SYSTEM
    ):
        local_id = subentry.data.get(CONF_SOURCE_SYSTEM_ID)
        communication_id = subentry.data.get(
            CONF_COMMUNICATION_SOURCE_SYSTEM_ID
        )
        if not isinstance(local_id, str) or not local_id:
            raise ConfigEntryError(
                "Duplicate system has no valid local source-system ID"
            )
        if not isinstance(communication_id, str) or not communication_id:
            raise ConfigEntryError(
                "Duplicate system has no valid communication source-system ID"
            )
        if local_id in result:
            raise ConfigEntryError("Duplicate source-system ID in hub")
        result[local_id] = communication_id
    return result


async def _async_close_failed_provider(
    provider: Provider,
    started: bool,
) -> None:
    """Best-effort remote cleanup followed by mandatory local close."""
    try:
        await provider.async_cancel_initialization()
        if started:
            try:
                await provider.async_disconnect()
            except Exception:
                _LOGGER.debug(
                    "Remote cleanup after setup failure failed",
                    exc_info=True,
                )
    finally:
        try:
            await provider.async_close()
        except Exception:
            _LOGGER.debug(
                "Local cleanup after setup failure failed",
                exc_info=True,
            )


async def _async_cleanup_failed_setup(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
    runtime: HubRuntime | None,
    provider: Provider,
    started: bool,
) -> None:
    """Retire published runtime state and close a failed provider lifecycle."""
    if runtime is not None:
        archive_manager = getattr(hass, "data", {}).get(DATA_ARCHIVE_MANAGER)
        if archive_manager is not None:
            archive_manager.detach_coordinators(runtime.coordinators.values())
        runtime.begin_quiescing()
        await runtime.async_wait_for_refreshes()
    await _async_close_failed_provider(provider, started)
    if runtime is None:
        return
    runtime.finish_unload()
    if getattr(entry, "runtime_data", None) is runtime:
        del entry.runtime_data


def _invalid_identity_subentries(
    hass: HomeAssistant,
    current_entry: ConfigEntry,
) -> set[str]:
    """Find all sides of integration-wide identity collisions."""
    records: list[tuple[ConfigEntry, ConfigSubentry, str | None, str | None]] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
            if subentry.subentry_type not in SYSTEM_SUBENTRY_TYPES:
                continue
            records.append(
                (
                    entry,
                    subentry,
                    subentry.unique_id,
                    subentry.data.get(CONF_SYSTEM_ID),
                )
            )

    uid_counts = Counter(
        uid for _, _, uid, _ in records if isinstance(uid, str) and uid
    )
    id_counts = Counter(
        system_id
        for _, _, _, system_id in records
        if isinstance(system_id, str) and system_id
    )
    source_records: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry, subentry, _, _ in records:
        source_system_id = subentry.data.get(CONF_SOURCE_SYSTEM_ID)
        if isinstance(source_system_id, str) and source_system_id:
            source_records[(entry.entry_id, source_system_id)].append(
                subentry.subentry_id
            )

    invalid: set[str] = set()
    for entry, subentry, uid, system_id in records:
        collision = (
            not _is_canonical_uuid4(uid)
            or (isinstance(uid, str) and uid_counts[uid] > 1)
            or (
                isinstance(system_id, str)
                and system_id
                and id_counts[system_id] > 1
            )
            or len(
                source_records.get(
                    (
                        entry.entry_id,
                        str(subentry.data.get(CONF_SOURCE_SYSTEM_ID, "")),
                    ),
                    [],
                )
            )
            > 1
        )
        if collision and entry.entry_id == current_entry.entry_id:
            invalid.add(subentry.subentry_id)
            _LOGGER.error(
                "System subentry %s is inactive because its identity collides",
                subentry.subentry_id,
            )

    return invalid


def _canonical_uuid4(value: str | None, label: str) -> str:
    if value is None:
        raise ConfigEntryError(f"Missing {label}")
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError) as err:
        raise ConfigEntryError(f"Invalid {label}") from err
    if parsed.version != 4 or str(parsed) != value:
        raise ConfigEntryError(f"Invalid {label}")
    return value


def _is_canonical_uuid4(value: str | None) -> bool:
    try:
        return _canonical_uuid4(value, "system unique ID") == value
    except ConfigEntryError:
        return False


def _positive_revision(entry: ConfigEntry, key: str) -> int:
    value = entry.data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigEntryError(f"{key} must be a positive integer")
    return value
