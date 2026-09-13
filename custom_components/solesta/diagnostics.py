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
        systems.append(
            {
                "system_index": system_index,
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
