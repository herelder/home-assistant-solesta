"""Encrypted local ESPHome native-API status provider."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable, Collection, Mapping
import re
from typing import Any

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    BadMACAddressAPIError,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
)

from .const import DOMAIN
from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderSystemError,
)
from .provider import Provider
from .source_fields import canonical_source_name

_CONTROL_OR_SPACE_PATTERN = re.compile(r"[\x00-\x20\x7f]")
_MAC_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_MAX_HOST_LENGTH = 253
_STATE_WAIT_TIMEOUT = 20.0


def canonicalize_esphome_host(value: Any) -> str:
    """Return a bounded host name or address without accepting a URL."""
    if not isinstance(value, str):
        raise ProviderConfigurationError("ESPHome host must be text")
    host = value.strip()
    if (
        not host
        or len(host) > _MAX_HOST_LENGTH
        or _CONTROL_OR_SPACE_PATTERN.search(host)
        or "://" in host
        or "/" in host
        or "\\" in host
    ):
        raise ProviderConfigurationError("ESPHome host is invalid")
    host = host.rstrip(".").lower()
    if not host:
        raise ProviderConfigurationError("ESPHome host is invalid")
    return host


def canonicalize_esphome_port(value: Any) -> int:
    """Return a valid TCP port."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProviderConfigurationError("ESPHome port must be an integer")
    if not 1 <= value <= 65535:
        raise ProviderConfigurationError("ESPHome port is out of range")
    return value


def canonicalize_noise_psk(value: Any) -> str:
    """Validate and return one ESPHome Noise PSK without logging it."""
    if not isinstance(value, str) or not value:
        raise ProviderConfigurationError("ESPHome encryption key is required")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as err:
        raise ProviderConfigurationError(
            "ESPHome encryption key is not valid base64"
        ) from err
    if len(decoded) != 32:
        raise ProviderConfigurationError(
            "ESPHome encryption key must contain 32 bytes"
        )
    return value


def canonicalize_mac(value: Any, *, required: bool = True) -> str | None:
    """Return a lower-case colon-separated MAC address."""
    if value in (None, "") and not required:
        return None
    if not isinstance(value, str):
        raise ProviderConfigurationError("ESPHome MAC address must be text")
    compact = value.strip().lower().replace(":", "").replace("-", "")
    if not _MAC_PATTERN.fullmatch(compact):
        raise ProviderConfigurationError("ESPHome MAC address is invalid")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def _api_expected_mac(mac: str | None) -> str | None:
    """Return the format required by aioesphomeapi."""
    return None if mac is None else mac.replace(":", "")


class EsphomeNativeProvider(Provider):
    """Expose one encrypted ESPHome node through the generic provider API."""

    def __init__(
        self,
        *,
        connection: Mapping[str, Any],
        provider_id: Any,
        duplicate_systems: Mapping[Any, Any] | None = None,
        configured_available_keys: Collection[str] = (),
        client_factory: Callable[..., Any] = APIClient,
        zeroconf_instance: Any | None = None,
    ) -> None:
        super().__init__(
            provider_id=provider_id,
            duplicate_systems=duplicate_systems,
            configured_available_keys=configured_available_keys,
        )
        if not isinstance(connection, Mapping):
            raise ProviderConfigurationError("connection must be a mapping")
        allowed = {"host", "port", "noise_psk", "expected_mac"}
        if set(connection) - allowed or not {"host", "port", "noise_psk"} <= set(
            connection
        ):
            raise ProviderConfigurationError(
                "ESPHome connection fields are incomplete or unsupported"
            )

        self._host = canonicalize_esphome_host(connection["host"])
        self._port = canonicalize_esphome_port(connection["port"])
        self._noise_psk = canonicalize_noise_psk(connection["noise_psk"])
        self._expected_mac = canonicalize_mac(
            connection.get("expected_mac"), required=False
        )
        self._client_factory = client_factory
        self._zeroconf_instance = zeroconf_instance
        self._client: Any | None = None
        self._connect_lock = asyncio.Lock()
        self._closed = False
        self._actual_mac: str | None = None
        self._source_system_ids: tuple[str, ...] = ()
        self._key_to_source: dict[tuple[int, int], tuple[str, str]] = {}
        self._public_source_keys: dict[str, frozenset[str]] = {}
        self._state_events: dict[str, asyncio.Event] = {}

    @property
    def _status_is_complete_snapshot(self) -> bool:
        """Native callbacks, not coordinator polls, are reports."""
        return False

    @property
    def expected_mac(self) -> str | None:
        """Return the configured or verified device MAC address."""
        if self._expected_mac is not None:
            return self._expected_mac
        return self._actual_mac

    def available_keys_for(self, source_system_id: str) -> tuple[str, ...] | None:
        """Return the entity catalogue belonging to one reported device."""
        keys = self._public_source_keys.get(source_system_id)
        return None if keys is None else tuple(sorted(keys))

    async def async_open(self) -> None:
        """Create the API client inside the active event loop."""
        if self._closed:
            raise ProviderConfigurationError("Provider lifecycle is closed")
        if self._client is None:
            self._client = self._client_factory(
                self._host,
                self._port,
                noise_psk=self._noise_psk,
                expected_mac=_api_expected_mac(self._expected_mac),
                zeroconf_instance=self._zeroconf_instance,
                client_info=f"{DOMAIN} ESPHome provider",
                provide_time=False,
            )

    async def async_connect(self) -> None:
        """Connect, verify identity, list entities and subscribe to states."""
        if self._closed:
            raise ProviderConfigurationError("Provider lifecycle is closed")
        await self.async_open()
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                return
            for event in self._state_events.values():
                event.clear()
            try:
                await self._client.connect(
                    on_stop=self._async_on_connection_stopped,
                    login=True,
                    log_errors=False,
                )
                device_info, entities, _services = (
                    await self._client.device_info_and_list_entities()
                )
                actual_mac = canonicalize_mac(device_info.mac_address)
                if self._expected_mac is not None and actual_mac != self._expected_mac:
                    raise ProviderAuthenticationError(
                        "ESPHome device identity does not match the configured MAC"
                    )
                self._publish_discovery(device_info, entities, actual_mac)
                self._client.subscribe_states(self._async_on_state)
            except Exception as err:
                await self._async_force_disconnect()
                self._raise_api_error(err)

    def _publish_discovery(
        self, device_info: Any, entities: Collection[Any], actual_mac: str
    ) -> None:
        """Publish one internally consistent device/entity discovery result."""
        reported_device_ids: set[int] = set()
        for device in getattr(device_info, "devices", ()):
            device_id = getattr(device, "device_id", None)
            if (
                not isinstance(device_id, int)
                or isinstance(device_id, bool)
                or device_id <= 0
                or device_id in reported_device_ids
            ):
                raise ProviderResponseError(
                    "ESPHome returned invalid subdevice identity data"
                )
            reported_device_ids.add(device_id)

        key_to_source: dict[tuple[int, int], tuple[str, str]] = {}
        source_keys: dict[str, set[str]] = {actual_mac: set()}
        source_keys.update(
            (f"{actual_mac}/{device_id}", set())
            for device_id in reported_device_ids
        )
        for entity in entities:
            object_id = str(getattr(entity, "object_id", "")).strip()
            key = getattr(entity, "key", None)
            device_id = getattr(entity, "device_id", 0)
            if (
                not object_id
                or not isinstance(key, int)
                or isinstance(key, bool)
                or not isinstance(device_id, int)
                or isinstance(device_id, bool)
            ):
                raise ProviderResponseError(
                    "ESPHome returned invalid entity discovery data"
                )
            if device_id < 0 or (device_id and device_id not in reported_device_ids):
                raise ProviderResponseError(
                    "ESPHome entity refers to an unknown subdevice"
                )
            route = (device_id, key)
            source_system_id = (
                actual_mac if device_id == 0 else f"{actual_mac}/{device_id}"
            )
            source_key = canonical_source_name((object_id,))
            keys = source_keys.setdefault(source_system_id, set())
            if route in key_to_source or source_key in keys:
                raise ProviderResponseError(
                    "ESPHome returned duplicate entity identity data"
                )
            key_to_source[route] = (source_system_id, source_key)
            keys.add(source_key)

        ordered_source_ids = tuple(
            sorted(
                source_keys,
                key=lambda source: (
                    source != actual_mac,
                    int(source.rsplit("/", 1)[-1]) if "/" in source else 0,
                ),
            )
        )
        self._actual_mac = actual_mac
        self._key_to_source = key_to_source
        self._source_system_ids = ordered_source_ids
        self._public_source_keys = {
            source: frozenset(keys) for source, keys in source_keys.items()
        }
        self._effective_available_keys = frozenset(
            key for keys in source_keys.values() for key in keys
        )
        self._state_events = {
            source: self._state_events.get(source, asyncio.Event())
            for source in ordered_source_ids
        }

    async def _async_on_connection_stopped(self, expected_disconnect: bool) -> None:
        """Wake status waiters when the native connection closes."""
        del expected_disconnect
        for event in self._state_events.values():
            event.set()

    def _async_on_state(self, state: Any) -> None:
        """Update the object-id keyed snapshot from one native state callback."""
        route = (getattr(state, "device_id", 0), getattr(state, "key", None))
        source = self._key_to_source.get(route)
        if source is None:
            return
        source_system_id, source_key = source
        missing = bool(getattr(state, "missing_state", False))
        value = None if missing else getattr(state, "state", None)
        self._observe_event(source_system_id, source_key, value)
        self._state_events[source_system_id].set()

    async def async_disconnect(self) -> None:
        """Disconnect locally; no remote state is modified."""
        async with self._connect_lock:
            await self._async_force_disconnect()

    async def _async_force_disconnect(self) -> None:
        client = self._client
        try:
            if client is not None:
                try:
                    await client.disconnect(force=True)
                except (APIConnectionError, OSError):
                    pass
        finally:
            for event in self._state_events.values():
                event.set()

    async def async_close(self) -> None:
        """Close this provider lifecycle idempotently."""
        await self.async_cancel_initialization()
        if self._closed:
            return
        await self.async_disconnect()
        self._closed = True
        self._client = None

    async def _async_fetch_profile(self) -> Mapping[str, Any]:
        await self.async_connect()
        return {}

    async def _async_fetch_systems(self) -> Collection[Any]:
        await self.async_connect()
        if not self._source_system_ids:
            raise ProviderResponseError("ESPHome source-system identity is unavailable")
        return self._source_system_ids

    async def _async_discover_available_keys(self, source_system_id: str) -> None:
        """Use the entity catalogue instead of an incomplete first state wave."""
        if source_system_id not in self._public_source_keys:
            raise ProviderSystemError("ESPHome source system is unavailable")

    async def _async_fetch_system_status(
        self,
        source_system_id: str,
        source_keys: Collection[str],
    ) -> Mapping[str, Any]:
        if source_system_id not in self._public_source_keys:
            raise ProviderSystemError("ESPHome source system is unavailable")
        await self.async_connect()
        required = frozenset(source_keys)
        unavailable = required - self._public_source_keys[source_system_id]
        if unavailable:
            raise ProviderSystemError(
                "ESPHome source keys are unavailable: "
                + ", ".join(sorted(unavailable))
            )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + _STATE_WAIT_TIMEOUT
        while True:
            values = self._observation(source_system_id).snapshot(required).values
            missing = required - set(values)
            if not missing:
                return dict(values)
            event = self._state_events[source_system_id]
            event.clear()
            if self._client is None or not self._client.is_connected:
                raise ProviderCommunicationError("ESPHome connection was lost")
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ProviderSystemError(
                    "ESPHome source values are unavailable: "
                    + ", ".join(sorted(missing))
                )
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
            except asyncio.TimeoutError as err:
                raise ProviderSystemError(
                    "ESPHome source values did not arrive in time: "
                    + ", ".join(sorted(missing))
                ) from err

    @staticmethod
    def _raise_api_error(err: Exception) -> None:
        """Map aioesphomeapi failures to the stable provider error model."""
        if isinstance(err, ProviderAuthenticationError):
            raise err
        if isinstance(
            err,
            (
                InvalidAuthAPIError,
                InvalidEncryptionKeyAPIError,
                BadMACAddressAPIError,
            ),
        ):
            raise ProviderAuthenticationError(
                "ESPHome authentication or device identity validation failed"
            ) from err
        if isinstance(err, RequiresEncryptionAPIError):
            raise ProviderConfigurationError(
                "ESPHome encrypted native API is required"
            ) from err
        if isinstance(err, (ProviderResponseError, ProviderConfigurationError)):
            raise err
        if isinstance(err, (APIConnectionError, asyncio.TimeoutError, OSError)):
            raise ProviderCommunicationError(
                "ESPHome native API could not be reached"
            ) from err
        raise err
