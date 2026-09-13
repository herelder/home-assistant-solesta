"""Public release contract for the ``solesta`` custom integration."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


REPOSITORY = Path(__file__).parents[1]
CANDIDATE = REPOSITORY / "custom_components" / "solesta"
TOOLS = REPOSITORY / "tools"


def _literal_assignments(path: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        else:
            continue
        if isinstance(target, ast.Name) and value is not None:
            try:
                result[target.id] = ast.literal_eval(value)
            except (ValueError, TypeError):
                pass
    return result


class Resources:
    def __init__(self, items=()):
        self.saved = deepcopy(list(items))
        self.items = []
        self.loaded = False
        self.changes = []

    async def async_get_info(self):
        if not self.loaded:
            self.items = deepcopy(self.saved)
            self.loaded = True
        return {"resources": len(self.items)}

    def async_items(self):
        if not self.loaded:
            raise AssertionError("resources must be loaded first")
        return self.items

    async def async_create_item(self, values):
        self.changes.append(("create", values))
        self.items.append(
            {"id": "new", "url": values["url"], "type": values["res_type"]}
        )

    async def async_update_item(self, item_id, values):
        self.changes.append(("update", item_id, values))
        item = next(item for item in self.items if item["id"] == item_id)
        item.update(url=values["url"], type=values["res_type"])

    async def async_delete_item(self, item_id):
        self.changes.append(("delete", item_id))
        self.items = [item for item in self.items if item["id"] != item_id]


@dataclass
class StaticPathConfig:
    url_path: str
    path: str
    cache_headers: bool


class CandidateIdentityTests(unittest.TestCase):
    def test_hacs_metadata_matches_the_public_release(self):
        hacs = json.loads(
            (REPOSITORY / "hacs.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            hacs,
            {
                "name": "Solesta",
                "country": "NL",
                "homeassistant": "2026.9.0",
            },
        )

    def test_product_identity_and_fresh_config_flow_history(self):
        manifest = json.loads(
            (CANDIDATE / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["domain"], "solesta")
        self.assertEqual(manifest["name"], "Solesta")
        self.assertEqual(manifest["version"], "0.2.3")
        self.assertNotIn("loggers", manifest)
        self.assertEqual(manifest["codeowners"], ["@herelder"])
        self.assertEqual(
            manifest["documentation"],
            "https://github.com/herelder/home-assistant-solesta",
        )
        self.assertEqual(
            manifest["issue_tracker"],
            "https://github.com/herelder/home-assistant-solesta/issues",
        )

        const = _literal_assignments(CANDIDATE / "const.py")
        flow = _literal_assignments(CANDIDATE / "config_flow.py")
        self.assertEqual(const["DOMAIN"], "solesta")
        self.assertEqual(flow["_CONFIG_ENTRY_VERSION"], 1)
        self.assertEqual(flow["_CONFIG_ENTRY_MINOR_VERSION"], 1)

        card = (CANDIDATE / "frontend" / "solesta-status-card.js").read_text(
            encoding="utf-8"
        )
        self.assertTrue(card.startswith('const SOLESTA_CARD_VERSION = "0.2.3";'))
        self.assertIn("integrationDomainFromModuleUrl(import.meta.url)", card)

    def test_internal_schema_and_format_versions_are_declared(self):
        contracts = {
            CANDIDATE / "const.py": ("EXPRESSION_SCHEMA_VERSION",),
            CANDIDATE / "archive_files.py": ("ARCHIVE_FORMAT",),
            CANDIDATE / "archive_journal.py": ("JOURNAL_FORMAT",),
            TOOLS / "generate_thetruth.py": ("CATALOG_REVISION",),
            TOOLS / "generate_provider_defaults.py": ("PRESET_REVISION",),
        }
        for path, names in contracts.items():
            with self.subTest(path=path):
                assignments = _literal_assignments(path)
                self.assertTrue(all(name in assignments for name in names))

    def test_candidate_has_no_state_or_migration_payload(self):
        forbidden_names = {
            ".storage",
            "archives",
            "solesta_archives",
            "migration.py",
        }
        self.assertFalse(
            [path for path in CANDIDATE.rglob("*") if path.name in forbidden_names]
        )
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in CANDIDATE.rglob("*.py")
        )
        self.assertNotIn("async_migrate_entry", source)
        self.assertNotIn("communication_provider_id", source)
        self.assertNotIn("provider_identity", source)

    def test_card_and_brand_assets_are_part_of_the_release(self):
        card = (
            CANDIDATE / "frontend" / "solesta-status-card.js"
        ).read_text(encoding="utf-8")
        self.assertIn("solesta-community-logo.png", card)
        self.assertIn("tank_bottom_temperature", card)
        self.assertTrue(
            (CANDIDATE / "frontend" / "solesta-community-logo.png").is_file()
        )
        brand = CANDIDATE / "brand"
        expected_sizes = {
            "icon.png": (256, 256),
            "icon@2x.png": (512, 512),
            "logo.png": (256, 256),
            "logo@2x.png": (512, 512),
        }
        contents = {}
        for name, expected_size in expected_sizes.items():
            with self.subTest(name=name):
                contents[name] = (brand / name).read_bytes()
                self.assertEqual(contents[name][:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(
                    struct.unpack(">II", contents[name][16:24]), expected_size
                )
                self.assertIn(contents[name][25], {4, 6}, "PNG must have alpha")
        self.assertEqual(contents["icon.png"], contents["logo.png"])
        self.assertEqual(contents["icon@2x.png"], contents["logo@2x.png"])


class FreshDashboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = {}
        for name in (
            "homeassistant",
            "homeassistant.components",
            "homeassistant.components.http",
            "homeassistant.components.lovelace",
            "homeassistant.components.lovelace.const",
            "homeassistant.components.lovelace.resources",
            "homeassistant.core",
            "homeassistant.loader",
            "solesta_transition_test",
            "solesta_transition_test.const",
        ):
            modules[name] = ModuleType(name)
        modules["homeassistant.components.http"].StaticPathConfig = StaticPathConfig
        modules["homeassistant.components.lovelace.const"].LOVELACE_DATA = "lovelace"
        modules[
            "homeassistant.components.lovelace.resources"
        ].ResourceStorageCollection = Resources
        modules["homeassistant.core"].HomeAssistant = object
        modules["homeassistant.loader"].async_get_integration = AsyncMock(
            return_value=SimpleNamespace(version="0.2.3")
        )
        modules["solesta_transition_test"].__path__ = [str(CANDIDATE)]
        modules["solesta_transition_test.const"].DOMAIN = "solesta"
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location(
                "solesta_transition_test.frontend", CANDIDATE / "frontend.py"
            )
            if spec is None or spec.loader is None:
                raise RuntimeError("cannot load candidate frontend")
            self.frontend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.frontend)

    @staticmethod
    def _hass(resources):
        return SimpleNamespace(
            data={"lovelace": SimpleNamespace(resources=resources)},
            http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        )

    async def test_empty_dashboard_gets_exactly_one_candidate_resource(self):
        resources = Resources()
        hass = self._hass(resources)
        await self.frontend.async_setup_frontend(hass)
        await self.frontend.async_setup_frontend(hass)

        self.assertEqual(
            resources.items,
            [
                {
                    "id": "new",
                    "url": "/solesta/solesta-status-card.js?v=0.2.3",
                    "type": "module",
                }
            ],
        )
        hass.http.async_register_static_paths.assert_awaited_once()
        routes = hass.http.async_register_static_paths.call_args.args[0]
        self.assertEqual(
            [route.url_path for route in routes],
            [
                "/solesta/solesta-status-card.js",
                "/solesta/solesta-community-logo.png",
            ],
        )
        self.assertTrue(all(Path(route.path).is_file() for route in routes))

    async def test_predecessor_resource_is_replaced_without_duplication(self):
        resources = Resources(
            [
                {
                    "id": "old",
                    "url": "/solestanext/solesta-status-card.js?v=1.12.0",
                    "type": "module",
                }
            ]
        )
        await self.frontend.async_setup_frontend(self._hass(resources))
        self.assertEqual(len(resources.items), 1)
        self.assertEqual(resources.items[0]["id"], "old")
        self.assertEqual(
            resources.items[0]["url"],
            "/solesta/solesta-status-card.js?v=0.2.3",
        )


if __name__ == "__main__":
    unittest.main()
