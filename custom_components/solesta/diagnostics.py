"""Redacted diagnostics for Solesta."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .configuration import HubRuntime


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[HubRuntime],
) -> dict:
    """Return expression diagnostics without provider data or credentials."""
    del hass
    runtime = entry.runtime_data
    systems = []
    for system_index, (_system_uid, coordinator) in enumerate(
        sorted(runtime.coordinators.items()), start=1
    ):
        snapshot = coordinator.raw_status_snapshot
        changed_at = coordinator.evaluation_errors_changed_at
        provider_changed_at = coordinator.provider_error_changed_at
        systems.append(
            {
                "system_index": system_index,
                "provider_error": coordinator.provider_error,
                "provider_error_changed_at_utc": (
                    provider_changed_at.isoformat()
                    if provider_changed_at is not None
                    else None
                ),
                "evaluation_errors_changed_at_utc": (
                    changed_at.isoformat() if changed_at is not None else None
                ),
                "evaluation_errors": [
                    {
                        "entity_key": key,
                        "category": error.category.value,
                    }
                    for key, error in sorted(coordinator.evaluation_errors.items())
                ],
                "available_source_keys": (
                    sorted(snapshot.values) if snapshot is not None else []
                ),
                "last_report_utc": (
                    snapshot.last_report.isoformat()
                    if snapshot is not None
                    and snapshot.last_report is not None
                    else None
                ),
                "last_update_utc": (
                    snapshot.last_update.isoformat()
                    if snapshot is not None
                    and snapshot.last_update is not None
                    else None
                ),
            }
        )
    return {
        "config_entry": {
            "config_revision": runtime.config_revision,
            "provider_revision": runtime.provider_revision,
            "system_count": len(systems),
        },
        "systems": systems,
    }
