"""Backup platform for Solesta archive data."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .archive import DATA_ARCHIVE_MANAGER

_LOGGER = logging.getLogger(__name__)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Flush and lock archive persistence before Home Assistant snapshots it."""
    manager = hass.data.get(DATA_ARCHIVE_MANAGER)
    if manager is None:
        return
    _LOGGER.info("Preparing Solesta archives for Home Assistant backup")
    await manager.begin_backup()


async def async_post_backup(hass: HomeAssistant) -> None:
    """Release archive persistence after Home Assistant completes its backup."""
    manager = hass.data.get(DATA_ARCHIVE_MANAGER)
    if manager is None:
        return
    manager.end_backup()
    _LOGGER.info("Solesta archive persistence resumed after backup")
