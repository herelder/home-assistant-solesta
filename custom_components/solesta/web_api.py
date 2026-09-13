"""Generic HTTPS/JSON status provider driven by validated REST flows."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Sequence
import json
import math
import re
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import quote, urlsplit

import aiohttp
from yarl import URL

from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSystemError,
)
from .provider import Provider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_TOKEN_PATTERN = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_CONTROL_OR_SPACE_PATTERN = re.compile(r"[\x00-\x20\x7f]")
_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_JSON_DEPTH = 16
_MAX_JSON_NODES = 4096


class _HttpStatusError(Exception):
    """Internal response-status signal that contains no response body."""

    def __init__(self, flow_name: str, status: int) -> None:
        super().__init__(f"{flow_name} returned HTTP {status}")
        self.flow_name = flow_name
        self.status = status


class _ResponseAssertionError(ProviderResponseError):
    """A response body failed a configured equality assertion."""

    def __init__(self, flow_name: str, key: str) -> None:
        super().__init__(
            f"{flow_name} response failed its assertion for {key!r}"
        )
        self.flow_name = flow_name
        self.key = key


def canonicalize_base_url(value: str) -> str:
    """Return a stable HTTPS origin for requests and config comparison."""
    if not isinstance(value, str):
        raise ProviderConfigurationError("base_url must be a string")
    candidate = value.strip()
    if not candidate or _CONTROL_OR_SPACE_PATTERN.search(candidate):
        raise ProviderConfigurationError("base_url is empty or contains whitespace")
    if "\\" in candidate:
        raise ProviderConfigurationError("base_url cannot contain a backslash")

    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as err:
        raise ProviderConfigurationError("base_url is not a valid URL") from err

    if parsed.scheme.lower() != "https":
        raise ProviderConfigurationError("base_url must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ProviderConfigurationError("base_url cannot contain user information")
    if not parsed.hostname:
        raise ProviderConfigurationError("base_url must contain a hostname")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ProviderConfigurationError(
            "base_url must be an origin without path, query, or fragment"
        )
    if port is not None and not 1 <= port <= 65535:
        raise ProviderConfigurationError("base_url contains an invalid port")

    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as err:
        raise ProviderConfigurationError("base_url hostname is invalid") from err

    if ":" in host:
        host = f"[{host}]"
    port_suffix = "" if port in (None, 443) else f":{port}"
    return f"https://{host}{port_suffix}"


def _bind_path(path_template: str, bindings: Mapping[str, str]) -> str:
    segments: list[str] = []
    for segment in path_template.split("/"):
        match = _TOKEN_PATTERN.fullmatch(segment)
        if match:
            token = match.group(1)
            try:
                value = bindings[token]
            except KeyError as err:
                raise ProviderConfigurationError(
                    f"Missing binding for {token}"
                ) from err
            encoded = quote(str(value), safe="")
            if encoded in {".", ".."}:
                encoded = encoded.replace(".", "%2E")
            segments.append(encoded)
        else:
            segments.append(segment)
    return "/".join(segments)


def _bind_json(value: Any, bindings: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        match = _TOKEN_PATTERN.fullmatch(value)
        if not match:
            return value
        token = match.group(1)
        try:
            return bindings[token]
        except KeyError as err:
            raise ProviderConfigurationError(f"Missing binding for {token}") from err
    if isinstance(value, (list, tuple)):
        return [_bind_json(item, bindings) for item in value]
    if isinstance(value, Mapping):
        return {key: _bind_json(item, bindings) for key, item in value.items()}
    return value


def _strict_json_loads(raw: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"Non-finite JSON number: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if len(key.encode("utf-8")) > 64 * 1024:
                raise ValueError("JSON key is too long")
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as err:
        raise ProviderResponseError("Provider returned invalid JSON") from err
    if not isinstance(decoded, dict):
        raise ProviderResponseError("Provider JSON response must be an object")

    nodes = 0

    def inspect(value: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            raise ProviderResponseError("Provider JSON exceeds its complexity limit")
        if isinstance(value, float) and not math.isfinite(value):
            raise ProviderResponseError("Provider JSON contains a non-finite number")
        if isinstance(value, str) and len(value.encode("utf-8")) > 64 * 1024:
            raise ProviderResponseError("Provider JSON string is too long")
        if isinstance(value, list):
            for item in value:
                inspect(item, depth + 1)
        elif isinstance(value, Mapping):
            for item in value.values():
                inspect(item, depth + 1)

    inspect(decoded, 0)
    return decoded


async def _async_read_bounded_response(
    response: aiohttp.ClientResponse,
) -> bytes:
    """Read through EOF while enforcing the response-size ceiling."""
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await response.content.read(
            min(64 * 1024, _MAX_RESPONSE_BYTES + 1 - size)
        )
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > _MAX_RESPONSE_BYTES:
            raise ProviderResponseError(
                "Provider response exceeds the size limit"
            )


def _extract_response(
    body: Mapping[str, Any],
    selectors: Sequence[str],
) -> dict[str, Any]:
    select_all = len(selectors) == 1 and selectors[0] == "*"
    selected = list(body.items()) if select_all else []
    if not select_all:
        for selector in selectors:
            if selector not in body:
                raise ProviderResponseError(
                    f"Provider response is missing selector {selector!r}"
                )
            selected.append((selector, body[selector]))

    direct: dict[str, Any] = {
        key: value for key, value in selected if not isinstance(value, Mapping)
    }
    top_level_direct_keys = frozenset(direct)
    flattened_owner: dict[str, str] = {}
    for parent, value in selected:
        if not isinstance(value, Mapping):
            continue
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ProviderResponseError("Provider JSON keys must be strings")
            if key in top_level_direct_keys:
                continue
            previous = flattened_owner.get(key)
            if previous is not None and previous != parent:
                raise ProviderResponseError(
                    f"Flattened response key {key!r} is ambiguous"
                )
            flattened_owner[key] = parent
            direct[key] = nested
    return direct


def _assert_response(
    body: Mapping[str, Any],
    assertions: Mapping[str, Any],
    *,
    flow_name: str,
) -> None:
    """Require type-strict equality for configured top-level JSON values."""
    missing = object()
    for key, expected in assertions.items():
        actual = body.get(key, missing)
        if (
            actual is missing
            or type(actual) is not type(expected)
            or actual != expected
        ):
            raise _ResponseAssertionError(flow_name, key)


class RestFlowExecutor:
    """Execute one immutable, generator-validated REST preset."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        base_url: str,
        preset: Mapping[str, Any],
    ) -> None:
        self._hass = hass
        self._base_url = canonicalize_base_url(base_url)
        if preset["base_url"] != self._base_url:
            raise ProviderConfigurationError(
                "base_url does not match the generated REST preset"
            )
        self._flows = preset["flows"]
        self._timeout = preset["total_timeout_seconds"]
        self._session: aiohttp.ClientSession | None = None

    @property
    def is_open(self) -> bool:
        return self._session is not None and not self._session.closed

    async def async_open(self) -> None:
        if self.is_open:
            return
        from homeassistant.helpers.aiohttp_client import async_create_clientsession

        self._session = async_create_clientsession(
            self._hass,
            auto_cleanup=False,
            base_url=self._base_url,
            cookie_jar=aiohttp.CookieJar(unsafe=False),
            timeout=aiohttp.ClientTimeout(total=self._timeout),
            trust_env=False,
        )

    async def async_close(self) -> None:
        session, self._session = self._session, None
        if session is not None and not session.closed:
            # Home Assistant owns the connector supplied to this private
            # cookie-holding session. Detach without closing that connector.
            session.detach()

    async def execute(
        self,
        flow_name: str,
        bindings: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        flow = self._flows.get(flow_name)
        if flow is None:
            raise ProviderConfigurationError(f"Flow {flow_name!r} cannot be executed")
        if not self.is_open or self._session is None:
            raise ProviderConfigurationError("HTTPS session is not open")

        bound = dict(bindings or {})
        if set(bound) - set(flow["bindings"]):
            raise ProviderConfigurationError(f"Unexpected bindings for {flow_name}")

        output: dict[str, Any] = {}
        for step in flow["steps"]:
            path = _bind_path(step["path_template"], bound)
            payload = (
                _bind_json(step["json"], bound) if "json" in step else None
            )
            try:
                async with self._session.request(
                    method=step["method"],
                    url=URL(path, encoded=True),
                    json=payload,
                    allow_redirects=False,
                ) as response:
                    if response.status not in step["response"]["success_statuses"]:
                        raise _HttpStatusError(flow_name, response.status)
                    raw = await _async_read_bounded_response(response)

                    selectors = step["response"]["extract"]
                    assertions = step["response"].get("assert_equals", {})
                    if not selectors and not assertions:
                        continue
                    content_type = (
                        response.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .lower()
                    )
                    if (
                        content_type != "application/json"
                        and not content_type.endswith("+json")
                    ):
                        raise ProviderResponseError(
                            "Provider response has an invalid content type"
                        )
                    body = _strict_json_loads(raw)
                    _assert_response(
                        body,
                        assertions,
                        flow_name=flow_name,
                    )
                    extracted = _extract_response(body, selectors)
            except _HttpStatusError:
                raise
            except ProviderResponseError:
                raise
            except (aiohttp.ClientError, TimeoutError) as err:
                raise ProviderCommunicationError(
                    f"Provider request failed in {flow_name}"
                ) from err

            collision = set(output) & set(extracted)
            if collision:
                raise ProviderResponseError(
                    "Flow response contains duplicate output keys: "
                    + ", ".join(sorted(collision))
                )
            output.update(extracted)
        return output


class WebApiProvider(Provider):
    """Status provider implemented by a typed HTTPS/JSON flow snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        base_url: str,
        connection: Mapping[str, Any],
        preset: Mapping[str, Any],
        provider_id: Any,
        duplicate_systems: Mapping[Any, Any] | None = None,
        configured_available_keys: Collection[str] = (),
    ) -> None:
        super().__init__(
            provider_id=provider_id,
            duplicate_systems=duplicate_systems,
            configured_available_keys=configured_available_keys,
        )
        if not isinstance(connection, Mapping):
            raise ProviderConfigurationError("connection must be a mapping")
        if set(connection) != {"userid", "password"}:
            raise ProviderConfigurationError(
                "connection must contain exactly userid and password"
            )
        userid = connection["userid"]
        password = connection["password"]
        if not isinstance(userid, str) or not userid.strip():
            raise ProviderConfigurationError("userid cannot be empty")
        if not isinstance(password, str) or not password:
            raise ProviderConfigurationError("password cannot be empty")

        self._base_url = canonicalize_base_url(base_url)
        self._connection = {"userid": userid.strip(), "password": password}
        self._executor = RestFlowExecutor(
            hass,
            base_url=self._base_url,
            preset=preset,
        )
        self._connect_lock = asyncio.Lock()
        self._connected = False
        self._closed = False
        self._auth_generation = 0

    @property
    def base_url(self) -> str:
        """Return the canonical HTTPS origin."""
        return self._base_url

    async def async_open(self) -> None:
        if self._closed:
            raise ProviderConfigurationError("Provider lifecycle is closed")
        await self._executor.async_open()

    async def async_connect(self) -> None:
        if self._closed:
            raise ProviderConfigurationError("Provider lifecycle is closed")
        await self.async_open()
        async with self._connect_lock:
            if self._connected:
                return
            await self._execute_connect_locked()

    async def _execute_connect_locked(self) -> None:
        try:
            await self._executor.execute("connect_flow", self._connection)
        except _HttpStatusError as err:
            self._raise_for_status(err)
        except _ResponseAssertionError as err:
            raise ProviderAuthenticationError(
                "Provider authentication response was rejected"
            ) from err
        self._connected = True
        self._auth_generation += 1

    async def async_disconnect(self) -> None:
        async with self._connect_lock:
            if not self._connected or not self._executor.is_open:
                self._connected = False
                return
            try:
                await self._executor.execute("disconnect_flow")
            except (
                ProviderCommunicationError,
                ProviderConfigurationError,
                ProviderResponseError,
                _HttpStatusError,
            ):
                # Remote logout is best-effort; local lifecycle state wins.
                pass
            finally:
                self._connected = False

    async def async_close(self) -> None:
        await self.async_cancel_initialization()
        if self._closed:
            return
        self._closed = True
        self._connected = False
        await self._executor.async_close()

    async def _async_fetch_profile(self) -> Mapping[str, Any]:
        return await self._execute_discovery_once("profile_flow")

    async def _async_fetch_systems(self) -> Collection[Any]:
        result = await self._execute_discovery_once("systems_flow")
        if not result:
            return ()
        list_values = [value for value in result.values() if isinstance(value, list)]
        if len(result) != 1 or len(list_values) != 1:
            raise ProviderResponseError(
                "systems_flow must return exactly one list"
            )
        # Preserve JSON scalar types so the provider contract can reject nulls
        # and objects while still accepting opaque numeric identifiers.
        return tuple(list_values[0])

    async def _async_fetch_system_status(
        self,
        source_system_id: str,
        source_keys: Collection[str],
    ) -> Mapping[str, Any]:
        del source_keys
        if not isinstance(source_system_id, str) or not source_system_id:
            raise ProviderConfigurationError("source_system_id cannot be empty")
        return await self._execute_authenticated(
            "system_status_flow",
            {"source_system_id": source_system_id},
        )

    async def _execute_discovery_once(
        self,
        flow_name: str,
    ) -> dict[str, Any]:
        """Execute a lifecycle discovery flow without an implicit retry."""
        if not self._connected:
            await self.async_connect()
        try:
            return await self._executor.execute(flow_name)
        except _HttpStatusError as err:
            self._raise_for_status(err)

    async def _execute_authenticated(
        self,
        flow_name: str,
        bindings: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self._connected:
            await self.async_connect()
        generation = self._auth_generation
        try:
            return await self._executor.execute(flow_name, bindings)
        except _HttpStatusError as err:
            if err.status != 401:
                self._raise_for_status(err)

        # Coalesce concurrent expired-session responses. Only the first caller
        # reconnects; all waiters retry their own idempotent GET exactly once.
        async with self._connect_lock:
            if generation == self._auth_generation:
                self._connected = False
                try:
                    await self._execute_connect_locked()
                except Exception:
                    # Mark this reconnect generation as consumed even on
                    # failure, so concurrent 401 waiters do not each launch a
                    # second reconnect cycle.
                    self._auth_generation += 1
                    raise
        if not self._connected:
            raise ProviderAuthenticationError(
                "Concurrent provider reconnect failed"
            )

        try:
            return await self._executor.execute(flow_name, bindings)
        except _HttpStatusError as err:
            self._raise_for_status(err)

    @staticmethod
    def _raise_for_status(error: _HttpStatusError) -> NoReturn:
        status = error.status
        if status in (401, 403):
            raise ProviderAuthenticationError(
                "Provider authentication failed"
            ) from error
        if status == 429:
            raise ProviderRateLimitError("Provider rate limit reached") from error
        if status == 408 or status >= 500:
            raise ProviderCommunicationError(
                f"Provider returned temporary HTTP status {status}"
            ) from error
        if 400 <= status <= 499 and error.flow_name == "system_status_flow":
            raise ProviderSystemError(
                f"Source-system request failed with HTTP status {status}"
            ) from error
        if 400 <= status <= 499:
            raise ProviderConfigurationError(
                f"Provider rejected configuration with HTTP status {status}"
            ) from error
        raise ProviderResponseError(
            f"Provider returned unexpected HTTP status {status}"
        ) from error
