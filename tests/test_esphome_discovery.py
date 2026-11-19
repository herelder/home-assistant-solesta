"""Tests for the ESPHome mDNS choice helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


INTEGRATION = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "solesta_discovery_test"


def _load(short_name: str):
    full_name = f"{PACKAGE}.{short_name}"
    spec = importlib.util.spec_from_file_location(
        full_name,
        INTEGRATION / f"{short_name}.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {short_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


package = ModuleType(PACKAGE)
package.__path__ = [str(INTEGRATION)]
sys.modules[PACKAGE] = package

_load("const")
discovery = _load("esphome_discovery")


class EsphomeDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_service_info_prefers_hostname_and_sanitizes_peer_label(self):
        info = SimpleNamespace(
            server="Nano-C6.local.",
            port=6053,
            properties={b"friendly_name": b"Solesta\nBridge"},
            parsed_addresses=lambda: ("192.0.2.1",),
        )

        node = discovery._node_from_service_info(
            "solesta-nanoc6-demo._esphomelib._tcp.local.", info
        )

        self.assertEqual(node.host, "nano-c6.local")
        self.assertEqual(node.port, 6053)
        self.assertEqual(node.label, "SolestaBridge — nano-c6.local:6053")

    def test_service_info_uses_address_and_default_port_as_fallback(self):
        info = SimpleNamespace(
            server=None,
            port=0,
            properties={},
            parsed_addresses=lambda: ("192.0.2.5",),
        )

        node = discovery._node_from_service_info(
            "nano._esphomelib._tcp.local.", info
        )

        self.assertEqual(node.host, "192.0.2.5")
        self.assertEqual(node.port, 6053)
        self.assertEqual(node.label, "nano — 192.0.2.5:6053")

    async def test_browser_resolves_sorts_and_cancels(self):
        removed = object()

        class FakeInfo:
            def __init__(self, service_type, service_name):
                self.service_type = service_type
                self.service_name = service_name
                self.server = None
                self.port = 6053
                self.properties = {}

            async def async_request(self, zeroconf_instance, *, timeout):
                self.zeroconf_instance = zeroconf_instance
                self.timeout = timeout
                short_name = self.service_name.partition(".")[0]
                self.server = f"{short_name}.local."
                return True

            def parsed_addresses(self):
                return ()

        class FakeBrowser:
            instance = None

            def __init__(self, zeroconf_instance, service_type, *, handlers):
                self.zeroconf_instance = zeroconf_instance
                self.service_type = service_type
                self.cancelled = False
                type(self).instance = self
                handler = handlers[0]
                handler(
                    zeroconf=zeroconf_instance,
                    service_type=service_type,
                    name="zeta.local.",
                    state_change=object(),
                )
                handler(
                    zeroconf=zeroconf_instance,
                    service_type=service_type,
                    name="alpha.local.",
                    state_change=object(),
                )

            async def async_cancel(self):
                self.cancelled = True

        zeroconf_instance = object()
        nodes = await discovery._async_browse_esphome_nodes(
            zeroconf_instance,
            browser_factory=FakeBrowser,
            info_factory=FakeInfo,
            removed_state=removed,
            browse_seconds=0,
        )

        self.assertEqual([node.host for node in nodes], [
            "alpha.local",
            "zeta.local",
        ])
        self.assertTrue(FakeBrowser.instance.cancelled)


if __name__ == "__main__":
    unittest.main()
