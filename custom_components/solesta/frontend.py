"""Serve and register the dashboard card shipped with this integration."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CARD_PATH = f"/{DOMAIN}/solesta-status-card.js"
LOGO_PATH = f"/{DOMAIN}/solesta-community-logo.png"
LEGACY_CARD_PATH = "/local/solesta-status-card.js"
# Recognizing the predecessor path makes the clean domain switch replace its
# resource instead of loading two bundles that compete for the same element.
LEGACY_CARD_PATHS = {
    LEGACY_CARD_PATH,
    "/solestanext/solesta-status-card.js",
}
_DATA_STATIC_REGISTERED = f"{DOMAIN}_card_static_registered"


def _is_card_resource(url: str) -> bool:
    """Recognize only our local resources, irrespective of cache version."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return not (parts.scheme or parts.netloc) and parts.path in {
        CARD_PATH,
        *LEGACY_CARD_PATHS,
    }


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register once during integration setup, independent of provider hubs."""
    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_PATH}?v={integration.version}"
    if not hass.data.get(_DATA_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_PATH,
                    str(Path(__file__).parent / "frontend" / "solesta-status-card.js"),
                    False,
                ),
                StaticPathConfig(
                    LOGO_PATH,
                    str(Path(__file__).parent / "frontend" / "solesta-community-logo.png"),
                    False,
                ),
            ]
        )
        hass.data[_DATA_STATIC_REGISTERED] = True

    resources = hass.data[LOVELACE_DATA].resources
    if not isinstance(resources, ResourceStorageCollection):
        _LOGGER.warning(
            "Dashboard resources use YAML: add %s as a module resource and "
            "replace any %s resource to load the bundled Solesta card",
            url,
            LEGACY_CARD_PATH,
        )
        return

    # Public collection API loads the saved resources before inspecting them.
    await resources.async_get_info()
    matches = [
        item for item in resources.async_items()
        if _is_card_resource(item.get("url", ""))
    ]
    if not matches:
        await resources.async_create_item({"url": url, "res_type": "module"})
    else:
        current = matches[0]
        if current.get("url") != url or current.get("type") != "module":
            await resources.async_update_item(
                current["id"], {"url": url, "res_type": "module"}
            )
        # Multiple versions race to define the same custom element. Keep one
        # resource using HA's collection API; never edit .storage files.
        for duplicate in matches[1:]:
            await resources.async_delete_item(duplicate["id"])
    _LOGGER.info("Registered bundled dashboard card: %s", url)
