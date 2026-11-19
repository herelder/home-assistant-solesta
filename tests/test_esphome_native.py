"""Contract tests for the encrypted local ESPHome provider."""

from __future__ import annotations

import ast
import base64
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


INTEGRATION = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "solesta_esphome_test"
NOISE_PSK = base64.b64encode(b"x" * 32).decode()


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


class APIConnectionError(Exception):
    """Test double for the library's transport error."""


class BadMACAddressAPIError(APIConnectionError):
    """Test double for a peer-identity mismatch."""


class InvalidAuthAPIError(APIConnectionError):
    """Test double for legacy authentication failure."""


class InvalidEncryptionKeyAPIError(APIConnectionError):
    """Test double for Noise authentication failure."""


class RequiresEncryptionAPIError(APIConnectionError):
    """Test double for a transport security mismatch."""


aioesphomeapi = ModuleType("aioesphomeapi")
aioesphomeapi.APIClient = object
aioesphomeapi.APIConnectionError = APIConnectionError
aioesphomeapi.BadMACAddressAPIError = BadMACAddressAPIError
aioesphomeapi.InvalidAuthAPIError = InvalidAuthAPIError
aioesphomeapi.InvalidEncryptionKeyAPIError = InvalidEncryptionKeyAPIError
aioesphomeapi.RequiresEncryptionAPIError = RequiresEncryptionAPIError
sys.modules.setdefault("aioesphomeapi", aioesphomeapi)

exceptions = _load("exceptions")
_load("provider")
esphome_native = _load("esphome_native")


class FakeClient:
    """Small native-API client with controllable entity state callbacks."""

    instances: list[FakeClient] = []
    connect_error: Exception | None = None

    def __init__(self, address, port, **kwargs):
        self.address = address
        self.port = port
        self.kwargs = kwargs
        self.is_connected = False
        self.on_stop = None
        self.on_state = None
        self.disconnect_forces = []
        type(self).instances.append(self)

    async def connect(self, *, on_stop, login, log_errors):
        if self.connect_error is not None:
            raise self.connect_error
        self.on_stop = on_stop
        self.login = login
        self.log_errors = log_errors
        self.is_connected = True

    async def device_info_and_list_entities(self):
        info = SimpleNamespace(
            name="solesta-nanoc6-demo",
            friendly_name="Solesta serial bridge",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="M5Stack NanoC6",
            manufacturer="M5Stack",
            esphome_version="2026.10.0",
            project_name="solesta.serial-bridge",
            project_version="1.0.0",
            devices=(),
        )
        object_ids = (
            "temperature_1_raw",
            "temperature_2_raw",
            "temperature_3_raw",
            "temperature_4_raw",
            "pump_raw",
            "flow_raw",
            "controller_state_text",
            "data_valid",
            "data_age_seconds",
            "frame_sequence",
        )
        entities = [
            SimpleNamespace(object_id=object_id, key=index, device_id=0)
            for index, object_id in enumerate(object_ids, start=1)
        ]
        return info, entities, []

    def subscribe_states(self, callback):
        self.on_state = callback

    def emit(self, key, value, *, device_id=0, missing_state=False):
        if self.on_state is None:
            raise AssertionError("provider did not subscribe to states")
        self.on_state(SimpleNamespace(
            key=key, device_id=device_id, state=value, missing_state=missing_state
        ))

    async def disconnect(self, *, force):
        self.disconnect_forces.append(force)
        self.is_connected = False


class WrongMacClient(FakeClient):
    """Client that reaches another ESPHome device at the configured host."""

    async def device_info_and_list_entities(self):
        info, entities, services = await super().device_info_and_list_entities()
        info.mac_address = "11:22:33:44:55:66"
        return info, entities, services


class NativeObjectIdClient(FakeClient):
    """Client exposing ESPHome's name-derived object ID for Data age."""

    async def device_info_and_list_entities(self):
        info, entities, services = await super().device_info_and_list_entities()
        for entity in entities:
            if entity.object_id == "data_age_seconds":
                entity.object_id = "data_age"
        return info, entities, services


class MeasurementsOnlyClient(FakeClient):
    """ESPHome node exposing only five measurement source fields."""

    async def device_info_and_list_entities(self):
        info, entities, services = await super().device_info_and_list_entities()
        measurements = {
            "temperature_1_raw",
            "temperature_2_raw",
            "temperature_3_raw",
            "temperature_4_raw",
            "pump_raw",
        }
        return (
            info,
            [entity for entity in entities if entity.object_id in measurements],
            services,
        )


class SubdeviceClient(FakeClient):
    """ESPHome node exposing main-device and explicit subdevice entities."""

    async def device_info_and_list_entities(self):
        info, _entities, services = await super().device_info_and_list_entities()
        info.devices = (
            SimpleNamespace(device_id=1),
            SimpleNamespace(device_id=2),
        )
        entities = [
            SimpleNamespace(object_id="shared_state", key=1, device_id=0),
            SimpleNamespace(object_id="shared_state", key=2, device_id=1),
            SimpleNamespace(object_id="shared_state", key=3, device_id=2),
        ]
        return info, entities, services


class EsphomeNativeProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeClient.instances.clear()
        FakeClient.connect_error = None

    @staticmethod
    def _provider(client_factory=FakeClient, expected_mac=None):
        connection = {
            "host": "Solesta-NanoC6-Demo.local.",
            "port": 6053,
            "noise_psk": NOISE_PSK,
        }
        if expected_mac is not None:
            connection["expected_mac"] = expected_mac
        return esphome_native.EsphomeNativeProvider(
            connection=connection,
            provider_id="nano_lab",
            client_factory=client_factory,
        )

    async def test_discovers_stable_identity_and_streams_all_native_states(self):
        provider = self._provider()
        await provider.async_initialize()

        client = FakeClient.instances[-1]
        self.assertEqual(client.address, "solesta-nanoc6-demo.local")
        self.assertEqual(client.port, 6053)
        self.assertEqual(client.kwargs["noise_psk"], NOISE_PSK)
        self.assertIsNone(client.kwargs["expected_mac"])
        self.assertIsNone(client.kwargs["zeroconf_instance"])
        self.assertFalse(client.kwargs["provide_time"])
        self.assertTrue(client.login)
        self.assertFalse(client.log_errors)
        self.assertEqual(provider.expected_mac, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(provider.systems, ("aa:bb:cc:dd:ee:ff",))
        self.assertEqual(provider.profile, {})

        self.assertEqual(
            set(provider.available_keys),
            {
                "temperature_1_raw",
                "temperature_2_raw",
                "temperature_3_raw",
                "temperature_4_raw",
                "pump_raw",
                "flow_raw",
                "controller_state_text",
                "data_valid",
                "data_age_seconds",
                "frame_sequence",
            },
        )
        self.assertNotIn("last_update", provider.available_keys)

        client.emit(1, 47.0)
        first = await provider.get_system_snapshot(
            provider.systems[0],
            {"temperature_1_raw"},
            {"temperature_1_raw"},
        )
        self.assertEqual(first.values["temperature_1_raw"], 47.0)
        self.assertIsNotNone(first.last_report)
        self.assertIsNotNone(first.last_update)

        client.emit(6, 11.0)
        client.emit(7, "STANDBY")
        client.emit(8, True)
        client.emit(9, 1.5)
        client.emit(10, 42.0)
        status = await provider.get_system_snapshot(provider.systems[0], {
                "temperature_1_raw",
                "flow_raw",
                "controller_state_text",
                "data_valid",
                "data_age_seconds",
                "frame_sequence",
            }, {
                "temperature_1_raw",
                "flow_raw",
                "controller_state_text",
                "data_valid",
                "data_age_seconds",
                "frame_sequence",
            })
        self.assertEqual(status["temperature_1_raw"], 47.0)
        self.assertEqual(status["flow_raw"], 11.0)
        self.assertEqual(status["controller_state_text"], "STANDBY")
        self.assertTrue(status["data_valid"])
        self.assertEqual(status["data_age_seconds"], 1.5)
        self.assertEqual(status["frame_sequence"], 42.0)
        self.assertNotIn("last_update", status)

        client.emit(1, 99.0)
        status = await provider.get_system_snapshot(provider.systems[0], {"temperature_1_raw"}, {"temperature_1_raw"})
        self.assertEqual(status["temperature_1_raw"], 99.0)

        await provider.async_close()
        self.assertEqual(client.disconnect_forces, [True])

    async def test_explicit_subdevices_get_hierarchical_isolated_sources(self):
        provider = self._provider(client_factory=SubdeviceClient)
        await provider.async_initialize()
        client = SubdeviceClient.instances[-1]

        self.assertEqual(
            provider.systems,
            (
                "aa:bb:cc:dd:ee:ff",
                "aa:bb:cc:dd:ee:ff/1",
                "aa:bb:cc:dd:ee:ff/2",
            ),
        )
        for source_system_id in provider.systems:
            self.assertEqual(
                provider.available_keys_for(source_system_id),
                ("shared_state",),
            )

        client.emit(1, "main")
        client.emit(2, "one", device_id=1)
        client.emit(3, "two", device_id=2)
        for source_system_id, expected in zip(
            provider.systems, ("main", "one", "two"), strict=True
        ):
            snapshot = await provider.get_system_snapshot(
                source_system_id,
                {"shared_state"},
                {"shared_state"},
            )
            self.assertEqual(snapshot.values["shared_state"], expected)
        await provider.async_close()

    async def test_entity_cannot_refer_to_an_unreported_subdevice(self):
        provider = self._provider()
        info = SimpleNamespace(
            mac_address="AA:BB:CC:DD:EE:FF",
            devices=(),
        )
        with self.assertRaises(exceptions.ProviderResponseError):
            provider._publish_discovery(
                info,
                [SimpleNamespace(object_id="state", key=1, device_id=7)],
                "aa:bb:cc:dd:ee:ff",
            )

    async def test_expected_mac_is_enforced_and_sent_without_separators(self):
        provider = self._provider(expected_mac="AA-BB-CC-DD-EE-FF")
        await provider.async_initialize()
        client = FakeClient.instances[-1]
        self.assertEqual(client.kwargs["expected_mac"], "aabbccddeeff")
        await provider.async_close()

        provider = self._provider(
            client_factory=WrongMacClient,
            expected_mac="AA:BB:CC:DD:EE:FF",
        )
        with self.assertRaises(exceptions.ProviderAuthenticationError):
            await provider.async_initialize()

    async def test_push_observation_is_independent_of_frame_barrier(self):
        provider = self._provider()
        await provider.async_initialize()
        client = FakeClient.instances[-1]
        for key, value in enumerate((47, 52, 48, 20, 0.42), start=1):
            client.emit(key, value)
        first = await provider.get_system_snapshot(
            provider.systems[0], (), {"temperature_1_raw"}
        )

        client.emit(1, 47)
        replay = await provider.get_system_snapshot(
            provider.systems[0], (), {"temperature_1_raw"}
        )
        self.assertGreaterEqual(replay.last_report, first.last_report)
        self.assertEqual(replay.last_update, first.last_update)

        client.emit(1, 99)
        changed = await provider.get_system_snapshot(
            provider.systems[0], (), {"temperature_1_raw"}
        )
        self.assertEqual(changed.values["temperature_1_raw"], 99)
        self.assertGreaterEqual(changed.last_update, replay.last_update)
        await provider.async_close()

    async def test_name_derived_data_age_object_id_is_an_ordinary_source(self):
        provider = self._provider(client_factory=NativeObjectIdClient)
        await provider.async_initialize()
        client = NativeObjectIdClient.instances[-1]

        self.assertIn("data_age", provider.available_keys)
        self.assertNotIn("data_age_seconds", provider.available_keys)
        self.assertNotIn("last_update", provider.available_keys)
        client.emit(9, 1.5)
        status = await provider.get_system_snapshot(provider.systems[0], {"data_age"}, {"data_age"})
        self.assertEqual(status["data_age"], 1.5)
        self.assertNotIn("last_update", status)
        await provider.async_close()

    async def test_missing_and_nonfinite_values_remain_opaque_states(self):
        for value, missing in (
            (0.0, True),
            (float("nan"), False),
            (float("inf"), False),
        ):
            with self.subTest(value=value, missing=missing):
                provider = self._provider(client_factory=MeasurementsOnlyClient)
                await provider.async_initialize()
                client = FakeClient.instances[-1]
                client.emit(1, value, missing_state=missing)
                snapshot = await provider.get_system_snapshot(
                    provider.systems[0],
                    {"temperature_1_raw"},
                    {"temperature_1_raw"},
                )
                actual = snapshot.values["temperature_1_raw"]
                if missing:
                    self.assertIsNone(actual)
                elif value != value:
                    self.assertNotEqual(actual, actual)
                else:
                    self.assertEqual(actual, value)
                self.assertIsNotNone(snapshot.last_report)
                self.assertIsNotNone(snapshot.last_update)
                await provider.async_close()

    async def test_measurements_only_publish_exactly_discovered_fields(self):
        provider = self._provider(client_factory=MeasurementsOnlyClient)
        await provider.async_initialize()
        client = MeasurementsOnlyClient.instances[-1]

        self.assertEqual(
            set(provider.available_keys),
            {
                "temperature_1_raw",
                "temperature_2_raw",
                "temperature_3_raw",
                "temperature_4_raw",
                "pump_raw",
            },
        )

        client.emit(1, 47.0)
        partial = await provider.get_system_snapshot(provider.systems[0], {"temperature_1_raw"}, {"temperature_1_raw"})
        self.assertEqual(partial["temperature_1_raw"], 47.0)

        client.emit(2, 52.0)
        client.emit(3, 48.0)
        client.emit(4, 309.0)
        client.emit(5, 0.42)
        status = await provider.get_system_snapshot(provider.systems[0], {
                "temperature_1_raw",
                "temperature_2_raw",
                "temperature_3_raw",
                "temperature_4_raw",
                "pump_raw",
            }, {
                "temperature_1_raw",
                "temperature_2_raw",
                "temperature_3_raw",
                "temperature_4_raw",
                "pump_raw",
            })

        self.assertEqual(status["temperature_1_raw"], 47.0)
        self.assertEqual(status["temperature_2_raw"], 52.0)
        self.assertEqual(status["temperature_3_raw"], 48.0)
        self.assertEqual(status["temperature_4_raw"], 309.0)
        self.assertEqual(status["pump_raw"], 0.42)
        self.assertNotIn("data_valid", status)
        self.assertNotIn("last_update", status)
        await provider.async_close()

    async def test_publisher_metadata_never_gates_other_source_fields(self):
        provider = self._provider()
        await provider.async_initialize()
        client = FakeClient.instances[-1]
        client.emit(8, False)
        client.emit(10, 0, missing_state=True)
        client.emit(1, 48.0)
        status = await provider.get_system_snapshot(provider.systems[0], {"data_valid", "frame_sequence", "temperature_1_raw"}, {"data_valid", "frame_sequence", "temperature_1_raw"})
        self.assertFalse(status["data_valid"])
        self.assertIsNone(status["frame_sequence"])
        self.assertEqual(status["temperature_1_raw"], 48.0)
        await provider.async_close()

    async def test_reconnect_preserves_the_shared_push_cache(self):
        provider = self._provider()
        await provider.async_initialize()
        client = FakeClient.instances[-1]
        client.emit(1, 48.0)
        before = await provider.get_system_snapshot(
            provider.systems[0],
            {"temperature_1_raw"},
            {"temperature_1_raw"},
        )

        client.is_connected = False
        await provider._async_on_connection_stopped(False)
        after = await provider.get_system_snapshot(
            provider.systems[0],
            {"temperature_1_raw"},
            {"temperature_1_raw"},
        )

        self.assertEqual(after.values["temperature_1_raw"], 48.0)
        self.assertEqual(after.last_report, before.last_report)
        self.assertEqual(after.last_update, before.last_update)
        await provider.async_close()

    async def test_invalid_noise_key_is_an_authentication_error(self):
        FakeClient.connect_error = InvalidEncryptionKeyAPIError("wrong key")
        provider = self._provider()
        with self.assertRaises(exceptions.ProviderAuthenticationError):
            await provider.async_initialize()

    def test_connection_fields_are_strictly_canonicalized(self):
        self.assertEqual(
            esphome_native.canonicalize_esphome_host(" Nano.local. "),
            "nano.local",
        )
        self.assertEqual(
            esphome_native.canonicalize_mac("AA-BB-CC-DD-EE-FF"),
            "aa:bb:cc:dd:ee:ff",
        )
        for invalid in ("", ".", "https://nano.local", "nano.local/path"):
            with self.subTest(host=invalid):
                with self.assertRaises(exceptions.ProviderConfigurationError):
                    esphome_native.canonicalize_esphome_host(invalid)
        with self.assertRaises(exceptions.ProviderConfigurationError):
            esphome_native.canonicalize_noise_psk("not-a-key")


class EsphomeSourceContractTests(unittest.TestCase):
    def test_provider_contains_no_firmware_specific_source_semantics(self):
        source = (INTEGRATION / "esphome_native.py").read_text()
        for forbidden in (
            "temperature_1_raw",
            "pump_raw",
            "flow_raw",
            "frame_sequence",
            "data_valid",
            "data_age",
            '"last_update"',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_config_flow_offers_mdns_selection_and_manual_fallback(self):
        source = (INTEGRATION / "config_flow.py").read_text()
        manifest = (INTEGRATION / "manifest.json").read_text()
        self.assertIn("async_step_esphome_native_node", source)
        self.assertIn("async_step_reconfigure_esphome_native_node", source)
        self.assertIn("_MANUAL_ESPHOME_NODE", source)
        self.assertIn('"zeroconf"', manifest)

    def test_factory_expressions_have_no_provider_specific_overrides(self):
        tree = ast.parse((INTEGRATION / "configuration.py").read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "default_source_expressions"
        )
        self.assertEqual(function.args.args, [])
        self.assertFalse(any(isinstance(node, ast.If) for node in function.body
                             if not isinstance(node, ast.For)))
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr == "update" for node in ast.walk(function)))
        self.assertIn("description.default_source_expression", ast.unparse(function))

    def test_all_six_protocol_switches_preserve_identity_and_disable_systems(self):
        tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_publish_provider_candidate"
        )
        isolated = ast.Module(
            body=[
                ast.ImportFrom(
                    module="__future__",
                    names=[ast.alias(name="annotations")],
                    level=0,
                ),
                function,
            ],
            type_ignores=[],
        )
        namespace = {
            "CONF_CONFIG_REVISION": "config_revision",
            "CONF_ENABLED": "enabled",
            "CONF_PROVIDER_REVISION": "provider_revision",
            "CONF_VALIDATED_HUB_UID": "validated_hub_uid",
            "CONF_VALIDATED_PROVIDER_REVISION": "validated_provider_revision",
            "_CONFIG_ENTRY_VERSION": 1,
            "_CONFIG_ENTRY_MINOR_VERSION": 4,
            "_json_copy": deepcopy,
            "_provider_title": lambda data: f"provider:{data['provider_id']}",
            "_system_subentries": lambda entry: tuple(entry.subentries.values()),
        }
        ast.fix_missing_locations(isolated)
        exec(compile(isolated, "config_flow.py", "exec"), namespace)
        publish = namespace["_publish_provider_candidate"]

        class ConfigEntries:
            def __init__(self):
                self.subentry_updates = []

            def async_update_subentry(self, current, item, *, data):
                self.subentry_updates.append((current, item))
                item.data = data

            def async_update_entry(self, current, **changes):
                self.updated_entry = current
                current.data = changes["data"]
                self.entry_changes = changes
                return True

        protocols = ("web_api", "esphome_native", "mqtt")
        switches = (
            (source, target)
            for source in protocols
            for target in protocols
            if source != target
        )
        for source, target in switches:
            with self.subTest(source=source, target=target):
                regular = SimpleNamespace(
                    subentry_id="regular",
                    unique_id="system-uid-1",
                    subentry_type="system",
                    data={
                        "system_id": "zonneboiler",
                        "source_system_id": "source-one",
                        "source_expressions": {
                            "temp_collector": "  to_number(temp1)  "
                        },
                        "enabled": True,
                        "validated_hub_uid": "hub-uid-1",
                        "validated_provider_revision": 4,
                        "config_revision": 7,
                    },
                )
                duplicate = SimpleNamespace(
                    subentry_id="duplicate",
                    unique_id="system-uid-2",
                    subentry_type="duplicate_system",
                    data={
                        "system_id": "zonneboiler_duplicate",
                        "source_system_id": "local-alias",
                        "communication_source_system_id": "source-one",
                        "source_expressions": {
                            "temp_collector": "to_number(temp1)\n"
                        },
                        "enabled": True,
                        "validated_hub_uid": "hub-uid-1",
                        "validated_provider_revision": 4,
                        "config_revision": 11,
                    },
                )
                entry = SimpleNamespace(
                    unique_id="hub-uid-1",
                    data={
                        "protocol": source,
                        "provider_id": "lab",
                        "provider_revision": 4,
                        "config_revision": 9,
                    },
                    subentries={
                        regular.subentry_id: regular,
                        duplicate.subentry_id: duplicate,
                    },
                )
                config_entries = ConfigEntries()
                hass = SimpleNamespace(config_entries=config_entries)
                candidate = {
                    "protocol": target,
                    "provider_id": "lab",
                    "provider_revision": 4,
                    "config_revision": 9,
                }

                self.assertTrue(
                    publish(hass, entry, candidate, protocol_changed=True)
                )
                self.assertEqual(entry.unique_id, "hub-uid-1")
                self.assertEqual(entry.data["protocol"], target)
                self.assertEqual(entry.data["provider_revision"], 5)
                self.assertEqual(entry.data["config_revision"], 10)
                self.assertEqual(len(config_entries.subentry_updates), 2)
                self.assertEqual(config_entries.entry_changes["version"], 1)
                self.assertEqual(
                    config_entries.entry_changes["minor_version"], 4
                )

                self.assertEqual(regular.unique_id, "system-uid-1")
                self.assertEqual(regular.data["system_id"], "zonneboiler")
                self.assertEqual(regular.data["source_system_id"], "source-one")
                self.assertEqual(
                    regular.data["source_expressions"]["temp_collector"],
                    "  to_number(temp1)  ",
                )
                self.assertEqual(regular.data["config_revision"], 8)

                self.assertEqual(duplicate.unique_id, "system-uid-2")
                self.assertEqual(
                    duplicate.data["communication_source_system_id"],
                    "source-one",
                )
                self.assertEqual(
                    duplicate.data["source_expressions"]["temp_collector"],
                    "to_number(temp1)\n",
                )
                self.assertEqual(duplicate.data["config_revision"], 12)

                for item in (regular, duplicate):
                    self.assertFalse(item.data["enabled"])
                    self.assertNotIn("validated_hub_uid", item.data)
                    self.assertNotIn(
                        "validated_provider_revision", item.data
                    )


if __name__ == "__main__":
    unittest.main()
