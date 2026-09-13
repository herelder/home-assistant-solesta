"""Check resource installation without touching a real Home Assistant store."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

INTEGRATION = Path(__file__).parents[1] / 'custom_components' / 'solesta'

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
        return {'resources': len(self.items)}

    def async_items(self):
        assert self.loaded, 'must load saved resources before inspecting them'
        return self.items

    async def async_create_item(self, values):
        assert values['res_type'] == 'module'
        self.changes.append(('create', values))
        self.items.append({'id': 'new', 'url': values['url'], 'type': values['res_type']})

    async def async_update_item(self, item_id, values):
        self.changes.append(('update', item_id, values))
        item = next(i for i in self.items if i['id'] == item_id)
        item.update(url=values['url'], type=values['res_type'])

    async def async_delete_item(self, item_id):
        self.changes.append(('delete', item_id))
        self.items = [i for i in self.items if i['id'] != item_id]

@dataclass
class StaticPathConfig:
    url_path: str
    path: str
    cache_headers: bool

class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = {}
        for name in ['homeassistant', 'homeassistant.components',
                     'homeassistant.components.http', 'homeassistant.components.lovelace',
                     'homeassistant.components.lovelace.const',
                     'homeassistant.components.lovelace.resources',
                     'homeassistant.core', 'homeassistant.loader', 'frontend_test', 'frontend_test.const']:
            modules[name] = ModuleType(name)
        modules['homeassistant.components.http'].StaticPathConfig = StaticPathConfig
        modules['homeassistant.components.lovelace.const'].LOVELACE_DATA = 'lovelace'
        modules['homeassistant.components.lovelace.resources'].ResourceStorageCollection = Resources
        modules['homeassistant.core'].HomeAssistant = object
        modules['homeassistant.loader'].async_get_integration = AsyncMock(
            return_value=SimpleNamespace(version='0.2.3'))
        modules['frontend_test'].__path__ = [str(INTEGRATION)]
        modules['frontend_test.const'].DOMAIN = 'solesta'
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('frontend_test.frontend', INTEGRATION / 'frontend.py')
            self.frontend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.frontend)

    def hass(self, resources):
        return SimpleNamespace(
            data={'lovelace': SimpleNamespace(resources=resources)},
            http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        )

    async def test_fresh_install_and_repeat_do_not_duplicate_routes_or_resources(self):
        resources = Resources()
        hass = self.hass(resources)
        await self.frontend.async_setup_frontend(hass)
        await self.frontend.async_setup_frontend(hass)
        self.assertEqual(len(resources.items), 1)
        self.assertEqual(len(resources.changes), 1)
        self.assertEqual(resources.items[0]['url'], '/solesta/solesta-status-card.js?v=0.2.3')
        hass.http.async_register_static_paths.assert_awaited_once()
        static = hass.http.async_register_static_paths.call_args.args[0][0]
        self.assertTrue(Path(static.path).is_file())
        self.assertFalse(static.cache_headers)

    async def test_migrate_legacy_and_remove_duplicate_but_preserve_other_resources(self):
        other = {'id': 'other', 'url': '/local/other-card.js', 'type': 'module'}
        external = {'id': 'external', 'url': 'https://example.org/local/solesta-status-card.js', 'type': 'module'}
        resources = Resources([
            {'id': 'old', 'url': '/local/solesta-status-card.js?v=1.8.1', 'type': 'module'},
            {'id': 'duplicate', 'url': '/solesta/solesta-status-card.js?v=0.1.0', 'type': 'js'},
            other, external,
        ])
        await self.frontend.async_setup_frontend(self.hass(resources))
        self.assertEqual(len(resources.items), 3)
        self.assertEqual(resources.items[0]['id'], 'old')
        self.assertEqual(resources.items[0]['url'], '/solesta/solesta-status-card.js?v=0.2.3')
        self.assertIn(other, resources.items)
        self.assertIn(external, resources.items)

    async def test_current_resource_needs_no_write(self):
        resources = Resources([{'id': 'current', 'url': '/solesta/solesta-status-card.js?v=0.2.3', 'type': 'module'}])
        await self.frontend.async_setup_frontend(self.hass(resources))
        self.assertFalse(resources.changes)

    async def test_clean_domain_switch_replaces_predecessor_resource(self):
        resources = Resources([
            {'id': 'old-domain', 'url': '/solestanext/solesta-status-card.js?v=1.3.1', 'type': 'module'},
        ])
        with patch.object(self.frontend, 'CARD_PATH', '/solesta/solesta-status-card.js'):
            await self.frontend.async_setup_frontend(self.hass(resources))
        self.assertEqual(len(resources.items), 1)
        self.assertEqual(resources.items[0]['id'], 'old-domain')
        self.assertEqual(resources.items[0]['url'], '/solesta/solesta-status-card.js?v=0.2.3')

    async def test_yaml_resources_remain_user_managed(self):
        resources = SimpleNamespace(data=[{'url': '/local/other.js', 'type': 'module'}])
        original = deepcopy(resources.data)
        with self.assertLogs(self.frontend._LOGGER, level='WARNING') as log:
            await self.frontend.async_setup_frontend(self.hass(resources))
        self.assertEqual(resources.data, original)
        self.assertIn('/solesta/solesta-status-card.js?v=0.2.3', log.output[0])

if __name__ == '__main__':
    unittest.main()
