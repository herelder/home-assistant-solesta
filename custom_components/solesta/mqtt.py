"""Standard MQTT 3.1.1 push provider with a value-agnostic state cache."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
import hashlib
import random
import re
import ssl
from typing import Any

try:
    from aiomqtt import Client as _AIOMQTT_CLIENT
    from aiomqtt import ProtocolVersion as _AIOMQTT_PROTOCOL_VERSION
except ImportError:
    _AIOMQTT_CLIENT = None
    _AIOMQTT_PROTOCOL_VERSION = None

from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderSystemError,
)
from .observation import utcnow
from .provider import Provider
from .source_fields import (
    SourceFieldError,
    SourceFieldTable,
    SourceFieldUnavailableError,
    canonical_source_name,
)

_CONTROL_OR_SPACE_PATTERN = re.compile(r"[\x00-\x20\x7f]")
_STATE_WAIT_TIMEOUT = 20.0
_CONNECT_TIMEOUT = 20.0
_DISCOVERY_QUIET_PERIOD = 0.1


def canonicalize_mqtt_host(value: Any) -> str:
    """Return a bounded hostname/address, never a URL."""
    if not isinstance(value, str):
        raise ProviderConfigurationError("MQTT broker host must be text")
    host = value.strip().rstrip(".").lower()
    if (
        not host
        or len(host) > 253
        or _CONTROL_OR_SPACE_PATTERN.search(host)
        or "://" in host
        or "/" in host
        or "\\" in host
    ):
        raise ProviderConfigurationError("MQTT broker host is invalid")
    return host


def canonicalize_mqtt_port(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        raise ProviderConfigurationError("MQTT broker port is invalid")
    return value


def canonicalize_mqtt_root(value: Any) -> str:
    """Require one concrete, slash-separated root without wildcards."""
    if not isinstance(value, str):
        raise ProviderConfigurationError("MQTT root topic must be text")
    root = value
    if (
        not root
        or "#" in root
        or "+" in root
        or "\x00" in root
        or root.endswith("/")
        or len(root.encode("utf-8")) > 65533
    ):
        raise ProviderConfigurationError("MQTT root topic is invalid")
    return root


@dataclass(frozen=True, slots=True)
class MqttMessageMetadata:
    """Last transport metadata retained for diagnostics and tests."""

    qos: int
    retain: bool


class MqttProvider(Provider):
    """Subscribe to configured topic roots and expose opaque text states."""

    def __init__(
        self,
        *,
        connection: Mapping[str, Any],
        provider_id: Any,
        source_system_ids: Collection[str],
        source_available_keys: Mapping[str, Collection[str]] | None = None,
        duplicate_systems: Mapping[Any, Any] | None = None,
        client_factory: Callable[..., Any] | None = None,
        client_id_nonce: str | None = None,
        random_source: random.Random | None = None,
    ) -> None:
        super().__init__(
            provider_id=provider_id,
            duplicate_systems=duplicate_systems,
        )
        if not isinstance(connection, Mapping):
            raise ProviderConfigurationError("connection must be a mapping")
        allowed = {
            "host", "port", "tls", "username", "password", "keepalive", "qos"
        }
        if set(connection) - allowed or not {"host", "port"} <= set(connection):
            raise ProviderConfigurationError(
                "MQTT connection fields are incomplete or unsupported"
            )
        self._host = canonicalize_mqtt_host(connection["host"])
        self._port = canonicalize_mqtt_port(connection["port"])
        self._tls = connection.get("tls", False)
        if not isinstance(self._tls, bool):
            raise ProviderConfigurationError("MQTT TLS setting must be boolean")
        self._keepalive = connection.get("keepalive", 60)
        if (
            not isinstance(self._keepalive, int)
            or isinstance(self._keepalive, bool)
            or not 1 <= self._keepalive <= 65535
        ):
            raise ProviderConfigurationError("MQTT keepalive is invalid")
        self._qos = connection.get("qos", 0)
        if self._qos not in {0, 1, 2} or isinstance(self._qos, bool):
            raise ProviderConfigurationError("MQTT QoS must be 0, 1, or 2")
        self._username = connection.get("username")
        self._password = connection.get("password")
        if self._username in (None, ""):
            if self._password not in (None, ""):
                raise ProviderConfigurationError(
                    "MQTT password requires a username"
                )
            self._username = None
            self._password = None
        elif not isinstance(self._username, str) or not isinstance(
            self._password, (str, type(None))
        ):
            raise ProviderConfigurationError("MQTT credentials are invalid")
        elif not self._password:
            raise ProviderConfigurationError(
                "MQTT username requires a password"
            )

        if isinstance(source_system_ids, (str, bytes, Mapping)) or not isinstance(
            source_system_ids, Collection
        ):
            raise ProviderConfigurationError("MQTT source-system IDs are invalid")
        roots = tuple(canonicalize_mqtt_root(root) for root in source_system_ids)
        if len(set(roots)) != len(roots):
            raise ProviderConfigurationError("MQTT source-system IDs must be unique")
        self._source_system_ids = roots
        self._root_sources = {root: root for root in roots}
        configured = source_available_keys or {}
        self._available_by_source: dict[str, set[str]] = {
            source_id: set(configured.get(source_id, ()))
            for source_id in self._source_system_ids
        }
        self._state_events = {
            source_id: asyncio.Event() for source_id in self._source_system_ids
        }
        self._metadata: dict[tuple[str, str], MqttMessageMetadata] = {}
        self._client_factory = client_factory
        if client_id_nonce is not None and (
            not isinstance(client_id_nonce, str) or not client_id_nonce
        ):
            raise ProviderConfigurationError(
                "MQTT client-ID nonce must be non-empty text"
            )
        self._client_id_nonce = client_id_nonce
        self._random = random_source or random.Random()
        self._runner: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._first_attempt = asyncio.Event()
        self._first_error: Exception | None = None
        self._stop = asyncio.Event()
        self._closed = False
        self._client: Any | None = None
        self._field_discovery_deadline: float | None = None

    @property
    def _status_is_complete_snapshot(self) -> bool:
        return False

    @property
    def message_metadata(self) -> Mapping[tuple[str, str], MqttMessageMetadata]:
        return dict(self._metadata)

    def available_keys_for(self, source_system_id: str) -> tuple[str, ...] | None:
        keys = self._available_by_source.get(source_system_id)
        return None if not keys else tuple(sorted(keys))

    async def async_get_available_keys(
        self, source_system_id: str, required_source_names: Collection[str]
    ) -> tuple[str, ...]:
        """Wait for requested field bindings within this discovery window."""
        if source_system_id not in self._source_system_ids:
            raise ProviderSystemError("MQTT source system is unavailable")
        loop = asyncio.get_running_loop()
        deadline = self._field_discovery_deadline
        if deadline is None:
            deadline = loop.time() + _STATE_WAIT_TIMEOUT
        event = self._state_events[source_system_id]
        while True:
            available = tuple(sorted(self._available_by_source[source_system_id]))
            try:
                table = SourceFieldTable(available)
            except SourceFieldError:
                return available
            missing = False
            for name in required_source_names:
                try:
                    table.resolve(name)
                except SourceFieldUnavailableError:
                    missing = True
                except SourceFieldError:
                    # Compile against this table to attach ambiguity/spelling
                    # errors to the corresponding expression fields.
                    return available
            if not missing:
                return available
            remaining = deadline - loop.time()
            if remaining <= 0:
                return available
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return tuple(sorted(self._available_by_source[source_system_id]))

    async def async_open(self) -> None:
        if self._closed:
            raise ProviderConfigurationError("Provider lifecycle is closed")

    async def async_connect(self) -> None:
        await self.async_open()
        if self._runner is None:
            self._runner = asyncio.create_task(
                self._run(), name=f"MQTT provider {self.provider_id}"
            )
        try:
            await asyncio.wait_for(self._first_attempt.wait(), _CONNECT_TIMEOUT)
        except asyncio.TimeoutError as err:
            raise ProviderCommunicationError("MQTT broker did not respond") from err
        if self._first_error is not None and not self._connected.is_set():
            self._raise_client_error(self._first_error)

    def _new_client(self) -> Any:
        factory = self._client_factory
        protocol: Any = 4
        if factory is None:
            if (
                _AIOMQTT_CLIENT is None
                or _AIOMQTT_PROTOCOL_VERSION is None
            ):
                raise ProviderConfigurationError(
                    "The MQTT client dependency is unavailable"
                )
            factory = _AIOMQTT_CLIENT
            protocol = _AIOMQTT_PROTOCOL_VERSION.V311
        tls_context = ssl.create_default_context() if self._tls else None
        identifier_source = self.provider_id
        if self._client_id_nonce is not None:
            identifier_source += "\x00" + self._client_id_nonce
        client_suffix = hashlib.sha256(
            identifier_source.encode("utf-8")
        ).hexdigest()[:15]
        return factory(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            keepalive=self._keepalive,
            tls_context=tls_context,
            identifier=f"mqtt-{client_suffix}",
            clean_session=True,
            protocol=protocol,
        )

    async def _run(self) -> None:
        delay = 1.0
        first = True
        while not self._stop.is_set():
            try:
                async with self._new_client() as client:
                    self._client = client
                    for root in self._root_sources:
                        await client.subscribe(f"{root}/#", qos=self._qos)
                    self._connected.set()
                    self._first_error = None
                    self._first_attempt.set()
                    first = False
                    delay = 1.0
                    async for message in client.messages:
                        self._handle_message(message)
                        if self._stop.is_set():
                            break
            except asyncio.CancelledError:
                raise
            except Exception as err:
                if first:
                    self._first_error = err
                    self._first_attempt.set()
                    first = False
                self._connected.clear()
            finally:
                self._client = None
                self._connected.clear()
            if self._stop.is_set():
                break
            jitter = self._random.uniform(0.8, 1.2)
            try:
                await asyncio.wait_for(self._stop.wait(), delay * jitter)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, 60.0)

    def _handle_message(self, message: Any) -> None:
        topic = str(message.topic)
        matched: tuple[str, str] | None = None
        for root, source_id in sorted(
            self._root_sources.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if topic == root:
                matched = source_id, ""
                break
            prefix = root + "/"
            if topic.startswith(prefix):
                matched = source_id, topic[len(prefix) :]
                break
        if matched is None:
            return
        source_id, relative = matched
        path = relative.split("/") if relative else [""]
        key = canonical_source_name(path)
        self._metadata[(source_id, key)] = MqttMessageMetadata(
            qos=int(getattr(message, "qos", 0)),
            retain=bool(getattr(message, "retain", False)),
        )
        try:
            value = bytes(message.payload).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            self._observation(source_id).observe_report(utcnow())
            self._state_events[source_id].set()
            return
        self._available_by_source[source_id].add(key)
        self._observe_event(source_id, key, value)
        self._state_events[source_id].set()

    async def async_disconnect(self) -> None:
        self._stop.set()
        runner, self._runner = self._runner, None
        if runner is not None and not runner.done():
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass

    async def async_close(self) -> None:
        await self.async_cancel_initialization()
        if self._closed:
            return
        await self.async_disconnect()
        self._closed = True

    async def _async_fetch_profile(self) -> Mapping[str, Any]:
        await self.async_connect()
        return {}

    async def _async_fetch_systems(self) -> Collection[Any]:
        await self.async_connect()
        return self._source_system_ids

    async def _async_discover_available_keys(self, source_system_id: str) -> None:
        if source_system_id not in self._source_system_ids:
            raise ProviderSystemError("MQTT source system is unavailable")
        loop = asyncio.get_running_loop()
        if self._field_discovery_deadline is None:
            self._field_discovery_deadline = loop.time() + _STATE_WAIT_TIMEOUT
        deadline = self._field_discovery_deadline
        event = self._state_events[source_system_id]
        while True:
            event.clear()
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            timeout = (
                min(_DISCOVERY_QUIET_PERIOD, remaining)
                if self._available_by_source[source_system_id]
                else remaining
            )
            try:
                await asyncio.wait_for(event.wait(), timeout)
            except asyncio.TimeoutError:
                return

    async def _async_fetch_system_status(
        self,
        source_system_id: str,
        source_keys: Collection[str],
    ) -> Mapping[str, Any]:
        if source_system_id not in self._source_system_ids:
            raise ProviderSystemError("MQTT source system is unavailable")
        await self.async_connect()
        required = frozenset(source_keys)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _STATE_WAIT_TIMEOUT
        while True:
            values = self._observation(source_system_id).snapshot(required).values
            missing = required - set(values)
            if not missing:
                return dict(values)
            self._state_events[source_system_id].clear()
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ProviderSystemError(
                    "MQTT source values are unavailable: "
                    + ", ".join(sorted(missing))
                )
            try:
                await asyncio.wait_for(
                    self._state_events[source_system_id].wait(),
                    remaining,
                )
            except asyncio.TimeoutError as err:
                raise ProviderSystemError(
                    "MQTT source values did not arrive in time: "
                    + ", ".join(sorted(missing))
                ) from err

    @staticmethod
    def _raise_client_error(err: Exception) -> None:
        text = str(err).lower()
        if any(token in text for token in ("not authorized", "bad user", "auth")):
            raise ProviderAuthenticationError(
                "MQTT authentication was rejected"
            ) from err
        raise ProviderCommunicationError("MQTT broker could not be reached") from err
