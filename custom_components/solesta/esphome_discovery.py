"""Short-lived mDNS discovery for ESPHome config-flow choices."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import DEFAULT_ESPHOME_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ESPHOME_SERVICE_TYPE = "_esphomelib._tcp.local."
_BROWSE_SECONDS = 1.0
_RESOLVE_TIMEOUT_MS = 1000
_MAX_LABEL_LENGTH = 96
_UNSAFE_LABEL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class EsphomeDiscoveredNode:
    """One untrusted mDNS hint that still requires native-API validation."""

    service_name: str
    label: str
    host: str
    port: int


def _safe_label(value: Any, *, fallback: str) -> str:
    """Return bounded printable text for peer-controlled mDNS data."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = _UNSAFE_LABEL.sub("", str(value or "")).strip()
    return (text or fallback)[:_MAX_LABEL_LENGTH]


def _node_from_service_info(service_name: str, info: Any) -> EsphomeDiscoveredNode | None:
    """Convert resolved service data into a safe config-flow option."""
    host = str(getattr(info, "server", "") or "").strip().rstrip(".").lower()
    if not host:
        addresses = tuple(getattr(info, "parsed_addresses", lambda: ())())
        if not addresses:
            return None
        host = str(addresses[0]).strip()
    port = getattr(info, "port", None) or DEFAULT_ESPHOME_PORT
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return None

    fallback_name = service_name.partition(".")[0]
    properties = getattr(info, "properties", {}) or {}
    friendly_name = properties.get(b"friendly_name") or properties.get(
        "friendly_name"
    )
    display_name = _safe_label(friendly_name, fallback=fallback_name)
    safe_host = _safe_label(host, fallback=fallback_name)
    return EsphomeDiscoveredNode(
        service_name=service_name,
        label=f"{display_name} — {safe_host}:{port}",
        host=host,
        port=port,
    )


async def _async_browse_esphome_nodes(
    zeroconf_instance: Any,
    *,
    browser_factory: Callable[..., Any],
    info_factory: Callable[..., Any],
    removed_state: Any,
    browse_seconds: float,
) -> tuple[EsphomeDiscoveredNode, ...]:
    """Browse the shared zeroconf cache and briefly resolve new announcements."""
    nodes: dict[str, EsphomeDiscoveredNode] = {}
    resolve_tasks: dict[str, asyncio.Task[None]] = {}

    async def resolve(service_type: str, service_name: str) -> None:
        info = info_factory(service_type, service_name)
        try:
            resolved = await info.async_request(
                zeroconf_instance, timeout=_RESOLVE_TIMEOUT_MS
            )
        except Exception:
            _LOGGER.debug(
                "Could not resolve ESPHome mDNS service %r",
                service_name,
                exc_info=True,
            )
            return
        if not resolved:
            return
        if node := _node_from_service_info(service_name, info):
            nodes[service_name] = node

    def service_update(
        zeroconf: Any,
        service_type: str,
        name: str,
        state_change: Any,
    ) -> None:
        del zeroconf
        if state_change is removed_state:
            nodes.pop(name, None)
            if task := resolve_tasks.pop(name, None):
                task.cancel()
            return
        previous = resolve_tasks.get(name)
        if previous is not None and not previous.done():
            return
        resolve_tasks[name] = asyncio.create_task(
            resolve(service_type, name),
            name=f"{DOMAIN} ESPHome mDNS resolve",
        )

    browser = browser_factory(
        zeroconf_instance,
        ESPHOME_SERVICE_TYPE,
        handlers=[service_update],
    )
    try:
        await asyncio.sleep(browse_seconds)
    finally:
        await browser.async_cancel()

    if resolve_tasks:
        await asyncio.gather(*resolve_tasks.values(), return_exceptions=True)
    return tuple(sorted(nodes.values(), key=lambda item: item.label.casefold()))


async def async_discover_esphome_nodes(
    hass: HomeAssistant,
    *,
    browse_seconds: float = _BROWSE_SECONDS,
) -> tuple[EsphomeDiscoveredNode, ...]:
    """Return ESPHome nodes currently visible through Home Assistant mDNS."""
    from homeassistant.components import zeroconf as ha_zeroconf
    from zeroconf import ServiceStateChange
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

    zeroconf_instance = await ha_zeroconf.async_get_instance(hass)
    return await _async_browse_esphome_nodes(
        zeroconf_instance,
        browser_factory=AsyncServiceBrowser,
        info_factory=AsyncServiceInfo,
        removed_state=ServiceStateChange.Removed,
        browse_seconds=browse_seconds,
    )
