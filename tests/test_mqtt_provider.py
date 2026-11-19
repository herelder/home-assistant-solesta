"""Focused transport tests for the standard MQTT provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "solesta_mqtt_contract"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


exceptions = _load("exceptions")
_load("observation")
_load("source_fields")
_load("provider")
mqtt = _load("mqtt")
MqttProvider = mqtt.MqttProvider
canonicalize_mqtt_root = mqtt.canonicalize_mqtt_root
canonicalize_mqtt_host = mqtt.canonicalize_mqtt_host
canonicalize_mqtt_port = mqtt.canonicalize_mqtt_port
ProviderAuthenticationError = exceptions.ProviderAuthenticationError
ProviderCommunicationError = exceptions.ProviderCommunicationError
ProviderConfigurationError = exceptions.ProviderConfigurationError


@dataclass
class _Message:
    topic: str
    payload: bytes
    qos: int = 0
    retain: bool = False


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.subscriptions = []
        self.queue = asyncio.Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))

    @property
    def messages(self):
        async def iterate():
            while True:
                item = await self.queue.get()
                if item is None:
                    return
                yield item

        return iterate()


class _Factory:
    def __init__(self):
        self.clients = []

    def __call__(self, **kwargs):
        client = _FakeClient(**kwargs)
        self.clients.append(client)
        return client


async def _until(predicate):
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not reached")


class MqttValidationTests(unittest.TestCase):
    def test_host_port_and_connection_fields_are_strict(self):
        self.assertEqual(canonicalize_mqtt_host(" Broker.Example. "), "broker.example")
        self.assertEqual(canonicalize_mqtt_port(28883), 28883)
        for value in ("", ".", "mqtt://broker", "broker/path", "a b"):
            with self.subTest(host=value):
                with self.assertRaises(ProviderConfigurationError):
                    canonicalize_mqtt_host(value)
        for value in (True, 0, 65536, "1883"):
            with self.subTest(port=value):
                with self.assertRaises(ProviderConfigurationError):
                    canonicalize_mqtt_port(value)

    def test_root_is_exact_and_allows_empty_relative_levels(self):
        self.assertEqual(canonicalize_mqtt_root("/home//boiler"), "/home//boiler")
        self.assertEqual(canonicalize_mqtt_root(" root "), " root ")
        for value in ("", "root/", "root/+", "root/#", "a\x00b"):
            with self.subTest(value=value):
                with self.assertRaises(ProviderConfigurationError):
                    canonicalize_mqtt_root(value)

    def test_auth_qos_keepalive_and_duplicate_roots_are_validated(self):
        base = {"host": "broker.example", "port": 1883}
        invalid_connections = (
            {**base, "password": "secret"},
            {**base, "username": "user"},
            {**base, "keepalive": 0},
            {**base, "qos": 3},
            {**base, "tls": "yes"},
            {**base, "unsupported": True},
        )
        for connection in invalid_connections:
            with self.subTest(connection=tuple(connection)):
                with self.assertRaises(ProviderConfigurationError):
                    MqttProvider(
                        connection=connection,
                        provider_id="validation",
                        source_system_ids=("root",),
                    )
        with self.assertRaises(ProviderConfigurationError):
            MqttProvider(
                connection=base,
                provider_id="validation",
                source_system_ids=("same", "same"),
            )


class MqttProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.factory = _Factory()
        self.provider = MqttProvider(
            connection={
                "host": "broker.example",
                "port": 1883,
                "tls": False,
                "keepalive": 30,
                "qos": 1,
            },
            provider_id="provider-one",
            source_system_ids=("house/boiler",),
            client_factory=self.factory,
        )

    async def asyncTearDown(self):
        await self.provider.async_close()

    async def _initialize_with(self, message):
        task = asyncio.create_task(self.provider.async_initialize())
        await _until(
            lambda: self.factory.clients
            and self.factory.clients[0].subscriptions
        )
        await self.factory.clients[0].queue.put(message)
        await task

    async def test_subscribe_cache_payload_and_transport_metadata(self):
        await self._initialize_with(
            _Message(
                "house/boiler/sensor/boiler-1/state",
                b" 01 ",
                qos=1,
                retain=True,
            )
        )
        client = self.factory.clients[0]
        self.assertEqual(self.provider.profile, {})
        self.assertEqual(self.provider.systems, ("house/boiler",))
        self.assertEqual(client.subscriptions, [("house/boiler/#", 1)])
        self.assertEqual(client.kwargs["protocol"], 4)
        self.assertTrue(client.kwargs["clean_session"])
        self.assertEqual(len(client.kwargs["identifier"]), 20)
        key = "state__boiler_02D1__sensor"
        snapshot = await self.provider.get_system_snapshot(
            "house/boiler", {key}, {key}
        )
        self.assertEqual(snapshot.values[key], " 01 ")
        metadata = self.provider.message_metadata[("house/boiler", key)]
        self.assertEqual((metadata.qos, metadata.retain), (1, True))

    async def test_connection_options_anonymous_auth_and_tls_verification(self):
        tls_factory = _Factory()
        tls_provider = MqttProvider(
            connection={
                "host": "Broker.Example.",
                "port": 28883,
                "tls": True,
                "username": "user",
                "password": "secret",
                "keepalive": 37,
                "qos": 2,
            },
            provider_id="tls-provider",
            source_system_ids=("root",),
            client_factory=tls_factory,
        )
        self.addAsyncCleanup(tls_provider.async_close)
        client = tls_provider._new_client()
        context = client.kwargs["tls_context"]
        self.assertEqual(client.kwargs["hostname"], "broker.example")
        self.assertEqual(client.kwargs["port"], 28883)
        self.assertEqual(client.kwargs["username"], "user")
        self.assertEqual(client.kwargs["password"], "secret")
        self.assertEqual(client.kwargs["keepalive"], 37)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, mqtt.ssl.CERT_REQUIRED)

        anonymous = self.provider._new_client()
        self.assertIsNone(anonymous.kwargs["username"])
        self.assertIsNone(anonymous.kwargs["password"])
        self.assertIsNone(anonymous.kwargs["tls_context"])

    async def test_runtime_client_creation_does_not_import_aiomqtt(self):
        factory = _Factory()
        protocol_version = type("ProtocolVersion", (), {"V311": 4})
        provider = MqttProvider(
            connection={"host": "broker.example", "port": 1883},
            provider_id="preloaded-dependency",
            source_system_ids=("root",),
        )
        self.addAsyncCleanup(provider.async_close)

        with (
            patch.object(mqtt, "_AIOMQTT_CLIENT", factory),
            patch.object(
                mqtt,
                "_AIOMQTT_PROTOCOL_VERSION",
                protocol_version,
            ),
            patch("builtins.__import__", wraps=__import__) as import_mock,
        ):
            client = provider._new_client()

        self.assertEqual(client.kwargs["protocol"], 4)
        self.assertNotIn(
            "aiomqtt",
            [call.args[0] for call in import_mock.call_args_list],
        )

    async def test_qos_zero_and_two_empty_payload_and_exact_topic_path(self):
        for qos in (0, 2):
            with self.subTest(qos=qos):
                factory = _Factory()
                provider = MqttProvider(
                    connection={
                        "host": "broker.example",
                        "port": 1883,
                        "qos": qos,
                    },
                    provider_id=f"provider-{qos}",
                    source_system_ids=("root",),
                    client_factory=factory,
                )
                try:
                    task = asyncio.create_task(provider.async_initialize())
                    await _until(
                        lambda: factory.clients
                        and factory.clients[0].subscriptions
                    )
                    await factory.clients[0].queue.put(
                        _Message("root/alpha//omega", b"", qos=qos)
                    )
                    await task
                    key = "omega___0E__alpha"
                    snapshot = await provider.get_system_snapshot(
                        "root", {key}, {key}
                    )
                    self.assertEqual(snapshot.values[key], "")
                    self.assertEqual(
                        factory.clients[0].subscriptions,
                        [("root/#", qos)],
                    )
                    self.assertEqual(
                        provider.message_metadata[("root", key)].qos,
                        qos,
                    )
                finally:
                    await provider.async_close()

    async def test_temporary_client_nonce_prevents_session_takeover(self):
        production = self.provider._new_client()
        temporary = MqttProvider(
            connection={
                "host": "broker.example",
                "port": 1883,
            },
            provider_id="provider-one",
            source_system_ids=(),
            client_factory=self.factory,
            client_id_nonce="one-validation-lifecycle",
        )
        self.addAsyncCleanup(temporary.async_close)
        candidate = temporary._new_client()

        self.assertEqual(len(production.kwargs["identifier"]), 20)
        self.assertEqual(len(candidate.kwargs["identifier"]), 20)
        self.assertNotEqual(
            production.kwargs["identifier"],
            candidate.kwargs["identifier"],
        )

    async def test_identical_replay_and_invalid_utf8_timestamp_contract(self):
        await self._initialize_with(_Message("house/boiler/state", b"A"))
        first = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        await self.factory.clients[0].queue.put(
            _Message("house/boiler/state", b"A", retain=True)
        )
        await _until(
            lambda: self.provider._observation("house/boiler").snapshot(
                {"state"}
            ).last_report != first.last_report
        )
        replay = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        self.assertGreater(replay.last_report, first.last_report)
        self.assertEqual(replay.last_update, first.last_update)

        await self.factory.clients[0].queue.put(
            _Message("house/boiler/state", b"\xff")
        )
        await _until(
            lambda: self.provider._observation("house/boiler").snapshot(
                {"state"}
            ).last_report != replay.last_report
        )
        invalid = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        self.assertEqual(invalid.values["state"], "A")
        self.assertEqual(invalid.last_update, first.last_update)

    async def test_reconnect_resubscribes_and_preserves_cache(self):
        self.provider._random = type(
            "NoJitter", (), {"uniform": staticmethod(lambda _a, _b: 0.0)}
        )()
        await self._initialize_with(_Message("house/boiler/state", b"A"))
        first = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        await self.factory.clients[0].queue.put(None)
        await _until(lambda: len(self.factory.clients) >= 2)
        await _until(lambda: bool(self.factory.clients[1].subscriptions))
        self.assertEqual(
            self.factory.clients[1].subscriptions,
            [("house/boiler/#", 1)],
        )
        cached = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        self.assertEqual(cached.values["state"], "A")
        self.assertEqual(cached.last_update, first.last_update)

        await self.factory.clients[1].queue.put(
            _Message("house/boiler/state", b"B", retain=True)
        )
        await _until(
            lambda: self.provider._observation("house/boiler").snapshot(
                {"state"}
            ).values.get("state") == "B"
        )
        changed = await self.provider.get_system_snapshot(
            "house/boiler", {"state"}, {"state"}
        )
        self.assertGreater(changed.last_report, cached.last_report)
        self.assertGreater(changed.last_update, cached.last_update)

    async def test_closing_one_hub_is_idempotent_and_does_not_touch_another(self):
        other_factory = _Factory()
        other = MqttProvider(
            connection={"host": "broker.example", "port": 1883},
            provider_id="provider-two",
            source_system_ids=("other/root",),
            client_factory=other_factory,
        )
        self.addAsyncCleanup(other.async_close)
        first_task = asyncio.create_task(self.provider.async_initialize())
        second_task = asyncio.create_task(other.async_initialize())
        await _until(
            lambda: self.factory.clients
            and self.factory.clients[0].subscriptions
            and other_factory.clients
            and other_factory.clients[0].subscriptions
        )
        await self.factory.clients[0].queue.put(
            _Message("house/boiler/state", b"A")
        )
        await other_factory.clients[0].queue.put(
            _Message("other/root/state", b"B")
        )
        await asyncio.gather(first_task, second_task)

        await self.provider.async_close()
        await self.provider.async_close()
        other_snapshot = await other.get_system_snapshot(
            "other/root", {"state"}, {"state"}
        )
        self.assertEqual(other_snapshot.values["state"], "B")
        self.assertIsNotNone(other._runner)
        self.assertFalse(other._runner.done())

    async def test_client_errors_are_redacted_and_stably_classified(self):
        for error in (
            RuntimeError("not authorized: super-secret"),
            RuntimeError("bad username or password: super-secret"),
        ):
            with self.subTest(error=str(error)):
                with self.assertRaises(ProviderAuthenticationError) as raised:
                    self.provider._raise_client_error(error)
                self.assertNotIn("super-secret", str(raised.exception))
        with self.assertRaises(ProviderCommunicationError) as raised:
            self.provider._raise_client_error(
                OSError("broker.example refused super-secret")
            )
        self.assertNotIn("super-secret", str(raised.exception))

    async def test_tls_context_comes_only_from_the_system_trust_store(self):
        marker = object()
        tls_provider = MqttProvider(
            connection={
                "host": "broker.example",
                "port": 8883,
                "tls": True,
            },
            provider_id="tls-system-trust",
            source_system_ids=(),
            client_factory=self.factory,
        )
        self.addAsyncCleanup(tls_provider.async_close)
        with patch.object(
            mqtt.ssl, "create_default_context", return_value=marker
        ) as create_context:
            client = tls_provider._new_client()
        create_context.assert_called_once_with()
        self.assertIs(client.kwargs["tls_context"], marker)
        self.assertFalse(hasattr(tls_provider, "ca_file"))


if __name__ == "__main__":
    unittest.main()
