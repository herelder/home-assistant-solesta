"""Configuration flows for provider hubs and their systems."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
import logging
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .compile import (
    SourceExpressionDependencyError,
    SourceExpressionError,
    SourceExpressionFunctionError,
    SourceExpressionSyntaxError,
    SourceExpressionValidationError,
)
from .configuration import default_source_expressions, duplicate_systems_from_entry
from .const import (
    CONF_AVAILABLE_KEYS,
    CONF_BASE_URL,
    CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
    CONF_CONFIG_REVISION,
    CONF_CONNECTION,
    CONF_ENABLED,
    CONF_EXPECTED_MAC,
    CONF_ESPHOME_NODE,
    CONF_EXPRESSION_SCHEMA_VERSION,
    CONF_HOST,
    CONF_KIND,
    CONF_NOISE_PSK,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROVIDER_ID,
    CONF_PROTOCOL,
    CONF_PROVIDER_REVISION,
    CONF_REQUIRED_SOURCE_KEYS,
    CONF_SOURCE_EXPRESSIONS,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
    CONF_USER_ID,
    CONF_USERNAME,
    CONF_TLS,
    CONF_KEEPALIVE,
    CONF_QOS,
    CONF_VALIDATED_HUB_UID,
    CONF_VALIDATED_PROVIDER_REVISION,
    DOMAIN,
    EXPRESSION_SCHEMA_VERSION,
    HUB_KIND_PROVIDER,
    DEFAULT_ESPHOME_PORT,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TLS_PORT,
    PROTOCOL_ESPHOME_NATIVE,
    PROTOCOL_MQTT,
    PROTOCOL_WEB_API,
    SYSTEM_SUBENTRY_TYPES,
    SUBENTRY_TYPE_DUPLICATE_SYSTEM,
    SUBENTRY_TYPE_SYSTEM,
)
from .description import EntityType
from .esphome_discovery import (
    EsphomeDiscoveredNode,
    async_discover_esphome_nodes,
)
from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSystemError,
)
from .evaluator import (
    EvaluationContext,
    EvaluationErrorCategory,
    evaluate_source_expressions,
)
from .mqtt import (
    MqttProvider,
    canonicalize_mqtt_host,
    canonicalize_mqtt_port,
    canonicalize_mqtt_root,
)
from .provider_defaults import SOLESTA_WEB_API_DEFAULT
from .provider import Provider
from .runtime_configuration import RuntimeConfiguration, is_drop_expression
from .source_fields import (
    SourceFieldAmbiguousError,
    SourceFieldError,
    SourceFieldUnavailableError,
)
from .thetruth import DESCRIPTIONS
from .web_api import (
    WebApiProvider,
    canonicalize_base_url,
)

_LOGGER = logging.getLogger(__name__)
_FLOW_CLAIMS_DATA = f"{DOMAIN}_flow_claims"
_MAX_SYSTEM_ID_LENGTH = 64
_PROTOCOL_OPTIONS = (PROTOCOL_WEB_API, PROTOCOL_ESPHOME_NATIVE, PROTOCOL_MQTT)
_CONFIG_ENTRY_VERSION = 1
_CONFIG_ENTRY_MINOR_VERSION = 9
_MANUAL_ESPHOME_NODE = "manual"
_EVALUATION_FORM_ERRORS = {
    EvaluationErrorCategory.MISSING_SOURCE: "source_value_missing_source",
    EvaluationErrorCategory.DEPENDENCY_FAILED: "source_value_dependency_failed",
    EvaluationErrorCategory.DIVISION_BY_ZERO: "source_value_division_by_zero",
    EvaluationErrorCategory.TYPE_ERROR: "source_value_type_error",
    EvaluationErrorCategory.DOMAIN_ERROR: "source_value_domain_error",
    EvaluationErrorCategory.EVALUATION_ERROR: "source_value_evaluation_error",
}


def _json_copy(value: Any) -> Any:
    """Return a mutable copy of a JSON-compatible value."""
    if isinstance(value, Mapping):
        return {str(key): _json_copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_copy(item) for item in value]
    return value


def _preset_parts() -> tuple[str, Mapping[str, Any], list[str]]:
    """Return the immutable generated preset and its public setup values."""
    preset = SOLESTA_WEB_API_DEFAULT
    return (
        str(preset[CONF_BASE_URL]),
        preset,
        sorted({str(key) for key in preset.get(CONF_AVAILABLE_KEYS, ())}),
    )


@dataclass(slots=True)
class _FlowClaims:
    """Process-local claims covering in-progress flow commits."""

    hub_uids: dict[str, str] = field(default_factory=dict)
    provider_ids: dict[str, str] = field(default_factory=dict)
    system_uids: dict[str, str] = field(default_factory=dict)
    system_ids: dict[str, str] = field(default_factory=dict)
    source_system_ids: dict[tuple[str, str], str] = field(default_factory=dict)

    @staticmethod
    def is_claimed(claims: Mapping[Any, str], value: Any, owner: str) -> bool:
        """Return whether ``value`` is claimed by another flow."""
        claimed_by = claims.get(value)
        return claimed_by is not None and claimed_by != owner

    def release(self, owner: str) -> None:
        """Release every claim owned by a finished or cancelled flow."""
        for claims in (
            self.hub_uids,
            self.provider_ids,
            self.system_uids,
            self.system_ids,
            self.source_system_ids,
        ):
            for key, claimed_by in tuple(claims.items()):
                if claimed_by == owner:
                    claims.pop(key, None)


@dataclass(frozen=True, slots=True)
class _LiveValidationResult:
    """One live-validation outcome suitable for a config form."""

    valid: bool
    base_error: str | None = None
    expression_errors: Mapping[str, str] = field(default_factory=dict)
    available_source_keys: tuple[str, ...] = ()
    required_source_keys: tuple[str, ...] = ()


class _LinkedSystemsValidationError(ProviderConfigurationError):
    """A provider candidate cannot preserve every linked system contract."""

    def __init__(self, translation_key: str, system_ids: Collection[str]) -> None:
        self.translation_key = translation_key
        self.system_ids = tuple(sorted({str(value) for value in system_ids}))
        super().__init__(f"{translation_key}: {', '.join(self.system_ids)}")


def _claims(hass: HomeAssistant) -> _FlowClaims:
    """Return the domain's process-local flow claims."""
    return hass.data.setdefault(_FLOW_CLAIMS_DATA, _FlowClaims())


def _entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return all visible entries of this integration."""
    return list(hass.config_entries.async_entries(DOMAIN))


def _hub_uid_exists(hass: HomeAssistant, hub_uid: str, owner: str) -> bool:
    """Return whether a hub UUID is visible or pending."""
    claims = _claims(hass)
    return any(entry.unique_id == hub_uid for entry in _entries(hass)) or (
        claims.is_claimed(claims.hub_uids, hub_uid, owner)
    )


def _entry_provider_id(entry_or_data: ConfigEntry | Mapping[str, Any]) -> str:
    """Return the hub's required local provider ID."""
    data = (
        entry_or_data.data
        if isinstance(entry_or_data, ConfigEntry)
        else entry_or_data
    )
    value = data.get(CONF_PROVIDER_ID, "")
    return str(value).strip()


def _mqtt_sources_from_entry(
    entry: ConfigEntry,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Return manual MQTT source IDs and their frozen field tables."""
    sources: list[str] = []
    available: dict[str, tuple[str, ...]] = {}
    for subentry in _system_subentries(entry):
        if subentry.subentry_type != SUBENTRY_TYPE_SYSTEM:
            continue
        source_id = subentry.data.get(CONF_SOURCE_SYSTEM_ID)
        keys = subentry.data.get(CONF_AVAILABLE_KEYS, ())
        if isinstance(source_id, str):
            sources.append(source_id)
            if isinstance(keys, (list, tuple)):
                available[source_id] = tuple(str(key) for key in keys)
    return tuple(sources), available


def _configured_opaque_id(value: Any) -> str | None:
    """Normalize a user-entered local ID without imposing a format."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        return None
    return normalized


def _provider_id_exists(
    hass: HomeAssistant,
    provider_id: str,
    owner: str,
    *,
    exclude_entry_id: str | None = None,
) -> bool:
    """Return whether a local provider ID is visible or pending."""
    if any(
        entry.entry_id != exclude_entry_id
        and _entry_provider_id(entry) == provider_id
        for entry in _entries(hass)
    ):
        return True
    return _claims(hass).is_claimed(
        _claims(hass).provider_ids, provider_id, owner
    )


def _duplicate_systems_from_entry(entry: ConfigEntry) -> dict[str, str]:
    """Return direct system aliases owned by removable system subentries."""
    return duplicate_systems_from_entry(entry)


def _system_subentries(entry: ConfigEntry) -> tuple[Any, ...]:
    """Return regular and duplicate system subentries."""
    return tuple(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type in SYSTEM_SUBENTRY_TYPES
    )


def _system_contract_snapshot(entry: ConfigEntry) -> tuple[Any, ...]:
    """Return all linked-system data needed for race-safe hub validation."""
    return tuple(
        (
            subentry.subentry_id,
            subentry.subentry_type,
            subentry.unique_id,
            _json_copy(subentry.data),
        )
        for subentry in sorted(
            _system_subentries(entry), key=lambda item: item.subentry_id
        )
    )


def _communication_source_system_id(subentry: Any) -> str:
    """Return the provider-discovered source behind one local system."""
    key = (
        CONF_COMMUNICATION_SOURCE_SYSTEM_ID
        if subentry.subentry_type == SUBENTRY_TYPE_DUPLICATE_SYSTEM
        else CONF_SOURCE_SYSTEM_ID
    )
    value = subentry.data.get(key)
    if not isinstance(value, str) or not value:
        raise _LinkedSystemsValidationError(
            "linked_systems_invalid", (str(subentry.data.get(CONF_SYSTEM_ID)),)
        )
    return value


def _system_uid_exists(hass: HomeAssistant, system_uid: str, owner: str) -> bool:
    """Return whether a system UUID is visible or pending integration-wide."""
    if any(
        subentry.unique_id == system_uid
        for entry in _entries(hass)
        for subentry in _system_subentries(entry)
    ):
        return True
    claims = _claims(hass)
    return claims.is_claimed(claims.system_uids, system_uid, owner)


def _system_id_exists(
    hass: HomeAssistant,
    system_id: str,
    owner: str,
    *,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Return whether a readable system ID is visible or pending."""
    if any(
        subentry.subentry_id != exclude_subentry_id
        and subentry.data.get(CONF_SYSTEM_ID) == system_id
        for entry in _entries(hass)
        for subentry in _system_subentries(entry)
    ):
        return True
    claims = _claims(hass)
    return claims.is_claimed(claims.system_ids, system_id, owner)


def _source_system_id_exists(
    entry: ConfigEntry,
    source_system_id: str,
    *,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Return whether a provider source ID is visible in a hub."""
    return any(
        subentry.subentry_id != exclude_subentry_id
        and subentry.data.get(CONF_SOURCE_SYSTEM_ID) == source_system_id
        for subentry in _system_subentries(entry)
    )


def _source_system_id_is_claimed(
    hass: HomeAssistant, entry_id: str, source_system_id: str, owner: str
) -> bool:
    """Return whether a source ID has a pending claim in its parent hub."""
    claims = _claims(hass)
    return claims.is_claimed(
        claims.source_system_ids,
        (entry_id, source_system_id),
        owner,
    )


def _canonical_system_id(value: Any) -> str | None:
    """Return a valid user-facing system ID without silently renaming it."""
    raw = str(value).strip()
    if (
        not raw
        or len(raw) > _MAX_SYSTEM_ID_LENGTH
        or cv.slugify(raw) != raw
    ):
        return None
    return raw


def _source_expressions(
    user_input: Mapping[str, Any],
    *,
    stored: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a complete mapping, restoring factory defaults when blank."""
    defaults = default_source_expressions()
    result: dict[str, str] = {}
    for description in DESCRIPTIONS:
        if is_drop_expression(defaults[description.key]):
            result[description.key] = (
                stored[description.key] if stored is not None
                else defaults[description.key]
            )
            continue
        if stored is not None and description.key not in user_input:
            result[description.key] = stored[description.key]
            continue
        raw = user_input.get(description.key)
        if stored is not None and raw == stored[description.key]:
            result[description.key] = stored[description.key]
            continue
        if description.entity_type is EntityType.SWITCH and type(raw) is bool:
            result[description.key] = "True" if raw else "False"
            continue
        value = "" if raw is None else str(raw).strip()
        result[description.key] = value or defaults[description.key]
    return result


def _switch_form_value(expression: str) -> bool:
    """Convert a validated Switch literal to its form value."""
    return expression.strip() == "True"


def _system_schema(
    *,
    system_id: str | None,
    source_system_id: str,
    source_expressions: Mapping[str, str],
    discovered_systems: Collection[str] = (),
    enabled: bool | None = None,
    source_field: str = CONF_SOURCE_SYSTEM_ID,
    manual_source: bool = False,
) -> vol.Schema:
    """Build a create or reconfigure form for one system."""
    source_validator: Any = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=item,
                        label=item,
                    )
                    for item in discovered_systems
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    )
    schema: dict[Any, Any] = {}
    if system_id is not None:
        schema[vol.Required(CONF_SYSTEM_ID, default=system_id)] = str
    if manual_source:
        schema[vol.Required(source_field, default=source_system_id)] = str
    else:
        source_marker = (
            vol.Required(source_field, default=source_system_id)
            if source_system_id in discovered_systems
            else vol.Optional(source_field)
        )
        schema[source_marker] = source_validator
    if enabled is not None:
        schema[vol.Required(CONF_ENABLED, default=enabled)] = bool
    for description in DESCRIPTIONS:
        if (
            description.entity_type is EntityType.SWITCH
            and not is_drop_expression(description.default_source_expression)
        ):
            schema[
                vol.Required(
                    description.key,
                    default=_switch_form_value(
                        source_expressions[description.key]
                    ),
                )
            ] = bool
    for description in DESCRIPTIONS:
        if (
            description.entity_type is EntityType.SWITCH
            or is_drop_expression(description.default_source_expression)
        ):
            continue
        schema[
            vol.Optional(
                description.key,
                description={
                    "suggested_value": source_expressions[description.key]
                },
            )
        ] = str
    return vol.Schema(schema)


def _system_create_details_schema(
    *,
    system_id: str,
    source_expressions: Mapping[str, str],
) -> vol.Schema:
    """Build the second create form after the provider system is selected."""
    schema: dict[Any, Any] = {
        vol.Required(CONF_SYSTEM_ID, default=system_id): str,
    }
    for description in DESCRIPTIONS:
        if (
            description.entity_type is EntityType.SWITCH
            and not is_drop_expression(description.default_source_expression)
        ):
            schema[
                vol.Required(
                    description.key,
                    default=_switch_form_value(
                        source_expressions[description.key]
                    ),
                )
            ] = bool
    for description in DESCRIPTIONS:
        if (
            description.entity_type is EntityType.SWITCH
            or is_drop_expression(description.default_source_expression)
        ):
            continue
        schema[
            vol.Optional(
                description.key,
                description={
                    "suggested_value": source_expressions[description.key]
                },
            )
        ] = str
    return vol.Schema(schema)


def _esphome_node_schema(
    nodes: Collection[EsphomeDiscoveredNode],
) -> vol.Schema:
    """Build the mDNS choice form with an explicit manual fallback."""
    options = [
        selector.SelectOptionDict(
            value=node.service_name,
            label=node.label,
        )
        for node in nodes
    ]
    options.append(
        selector.SelectOptionDict(
            value=_MANUAL_ESPHOME_NODE,
            label=_MANUAL_ESPHOME_NODE,
        )
    )
    return vol.Schema(
        {
            vol.Required(CONF_ESPHOME_NODE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    translation_key=CONF_ESPHOME_NODE,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _source_expression_error_key(error: SourceExpressionError) -> str:
    """Translate classified compiler failures without exposing raw values."""
    if isinstance(error.__cause__, SourceFieldUnavailableError):
        return "source_value_missing_source"
    if isinstance(error.__cause__, SourceFieldAmbiguousError):
        return "source_expression_ambiguous_source"
    if isinstance(error.__cause__, SourceFieldError):
        return "source_expression_invalid_source"
    if isinstance(error, SourceExpressionSyntaxError):
        return "source_expression_syntax_error"
    if isinstance(error, SourceExpressionFunctionError):
        return "source_expression_function_error"
    if isinstance(error, SourceExpressionDependencyError):
        return "source_expression_dependency_cycle"
    return "invalid_source_expression"


def _compile_expressions(
    expressions: Mapping[str, str],
    *,
    available_source_keys: Collection[str] | None = None,
) -> tuple[RuntimeConfiguration | None, dict[str, str]]:
    """Compile a complete mapping and locate expression-specific errors."""
    forbidden_drop = {
        description.key: "source_expression_drop_not_allowed"
        for description in DESCRIPTIONS
        if is_drop_expression(expressions.get(description.key))
        and not is_drop_expression(description.default_source_expression)
    }
    if forbidden_drop:
        return None, forbidden_drop
    try:
        return RuntimeConfiguration.compile(
            expressions, available_source_keys=available_source_keys
        ), {}
    except SourceExpressionValidationError as err:
        return None, {
            key: _source_expression_error_key(error)
            for key, error in err.errors.items()
        }
    except SourceExpressionError as err:
        return None, {
            key: _source_expression_error_key(err)
            for key in err.expression_keys
        } or {"base": "invalid_source_expressions"}
    except SourceFieldError:
        return None, {"base": "invalid_provider_config"}
    except ValueError:
        return None, {"base": "invalid_source_expressions"}


def _required_source_keys(runtime: RuntimeConfiguration) -> frozenset[str]:
    """Return the compiled provider requirement set."""
    return runtime.required_source_keys


def _stored_expressions(runtime: RuntimeConfiguration) -> dict[str, str]:
    """Return the canonical persistent expression mapping."""
    return dict(runtime.stored_source_expressions())


def _missing_offline_keys(
    entry: ConfigEntry, required_source_keys: Collection[str]
) -> list[str]:
    """Return missing keys using the saved provider contract."""
    runtime = getattr(entry, "runtime_data", None)
    runtime_provider = getattr(runtime, "provider", None)
    if runtime_provider is not None:
        return runtime_provider.unavailable_keys(required_source_keys)

    available = {
        str(key) for key in entry.data.get(CONF_AVAILABLE_KEYS, ()) if str(key)
    }
    required = {str(key) for key in required_source_keys}
    if not required:
        return []
    # Empty means automatic discovery/unknown, not authoritative emptiness.
    if not available:
        return sorted(required)
    return sorted(required - available)


def _provider_from_data(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    *,
    duplicate_systems: Mapping[str, str] | None = None,
    mqtt_source_system_ids: Collection[str] | None = None,
    mqtt_source_available_keys: Mapping[str, Collection[str]] | None = None,
) -> Provider:
    """Create the provider selected by validated hub data."""
    protocol = data.get(CONF_PROTOCOL)
    common = {
        "provider_id": _entry_provider_id(data),
        "duplicate_systems": duplicate_systems,
        "configured_available_keys": data.get(CONF_AVAILABLE_KEYS, ()),
    }
    if protocol == PROTOCOL_WEB_API:
        return WebApiProvider(
            hass,
            base_url=str(data[CONF_BASE_URL]),
            connection=data[CONF_CONNECTION],
            preset=SOLESTA_WEB_API_DEFAULT,
            **common,
        )
    if protocol == PROTOCOL_ESPHOME_NATIVE:
        from .esphome_native import EsphomeNativeProvider
        from homeassistant.components import zeroconf as ha_zeroconf

        return EsphomeNativeProvider(
            connection=data[CONF_CONNECTION],
            zeroconf_instance=ha_zeroconf.async_get_async_zeroconf(
                hass
            ).zeroconf,
            **common,
        )
    if protocol == PROTOCOL_MQTT:
        return MqttProvider(
            connection=data[CONF_CONNECTION],
            provider_id=common["provider_id"],
            duplicate_systems=duplicate_systems,
            source_system_ids=mqtt_source_system_ids or (),
            source_available_keys=mqtt_source_available_keys,
            # Config flows may run beside the loaded hub. A distinct nonce
            # prevents Mosquitto from evicting the production client while a
            # candidate connection is being validated.
            client_id_nonce=uuid4().hex,
        )
    raise ProviderConfigurationError("Unsupported provider protocol")


async def _async_close_temporary_provider(provider: Provider) -> None:
    """Disconnect remotely where possible and always close local resources."""
    await provider.async_cancel_initialization()
    with suppress(Exception):
        await provider.async_disconnect()
    await provider.async_close()


async def _async_initialize_provider(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    *,
    duplicate_systems: Mapping[str, str] | None = None,
    mqtt_source_system_ids: Collection[str] | None = None,
    mqtt_source_available_keys: Mapping[str, Collection[str]] | None = None,
) -> Provider:
    """Open, connect and initialize one temporary provider lifecycle."""
    provider = _provider_from_data(
        hass,
        data,
        duplicate_systems=duplicate_systems,
        mqtt_source_system_ids=mqtt_source_system_ids,
        mqtt_source_available_keys=mqtt_source_available_keys,
    )
    try:
        await provider.async_open()
        await provider.async_connect()
        # profile_flow and systems_flow are coalesced to one execution each.
        await provider.async_initialize()
    except asyncio.CancelledError:
        await _async_close_temporary_provider(provider)
        raise
    except Exception:
        await _async_close_temporary_provider(provider)
        raise
    return provider


def _provider_error_key(err: Exception) -> str:
    """Translate provider failures to stable config-flow error keys."""
    if isinstance(err, ProviderAuthenticationError):
        return "invalid_auth"
    if isinstance(err, (ProviderConfigurationError, ProviderResponseError)):
        return "invalid_provider_config"
    if isinstance(err, (ProviderCommunicationError, ProviderRateLimitError)):
        return "cannot_connect"
    if isinstance(err, ProviderSystemError):
        return "invalid_source_system"
    return "unknown"


def _hub_candidate(
    *,
    protocol: str,
    base_url: Any,
    user_id: Any,
    password: Any,
    preset: Mapping[str, Any],
    configured_available_keys: Collection[str],
    provider_revision: int,
    config_revision: int,
    provider_id: Any,
) -> dict[str, Any]:
    """Normalize all locally decidable hub fields."""
    if protocol != PROTOCOL_WEB_API:
        raise ProviderConfigurationError("Unsupported provider protocol")
    canonical_base_url = canonicalize_base_url(str(base_url))
    if canonical_base_url != preset[CONF_BASE_URL]:
        raise ProviderConfigurationError(
            "Provider origin does not match the generated preset"
        )
    normalized_user_id = str(user_id).strip()
    if not normalized_user_id or not isinstance(password, str) or not password:
        raise ProviderConfigurationError("Credentials must not be empty")
    local_provider_id = _configured_opaque_id(provider_id)
    if local_provider_id is None:
        raise ProviderConfigurationError("Provider ID is invalid")
    return {
        CONF_KIND: HUB_KIND_PROVIDER,
        CONF_PROTOCOL: PROTOCOL_WEB_API,
        CONF_BASE_URL: canonical_base_url,
        CONF_CONNECTION: {
            CONF_USER_ID: normalized_user_id,
            CONF_PASSWORD: password,
        },
        CONF_PROVIDER_ID: local_provider_id,
        CONF_PROVIDER_REVISION: provider_revision,
        CONF_CONFIG_REVISION: config_revision,
        CONF_AVAILABLE_KEYS: sorted(
            {str(key) for key in configured_available_keys if str(key)}
        ),
    }


def _esphome_hub_candidate(
    *,
    host: Any,
    port: Any,
    noise_psk: Any,
    expected_mac: Any,
    configured_available_keys: Collection[str],
    provider_revision: int,
    config_revision: int,
    provider_id: Any,
) -> dict[str, Any]:
    """Normalize one encrypted ESPHome native-API hub candidate."""
    from .esphome_native import (
        canonicalize_esphome_host,
        canonicalize_esphome_port,
        canonicalize_mac,
        canonicalize_noise_psk,
    )

    local_provider_id = _configured_opaque_id(provider_id)
    if local_provider_id is None:
        raise ProviderConfigurationError("Provider ID is invalid")
    connection = {
        CONF_HOST: canonicalize_esphome_host(host),
        CONF_PORT: canonicalize_esphome_port(port),
        CONF_NOISE_PSK: canonicalize_noise_psk(noise_psk),
    }
    normalized_mac = canonicalize_mac(expected_mac, required=False)
    if normalized_mac is not None:
        connection[CONF_EXPECTED_MAC] = normalized_mac
    return {
        CONF_KIND: HUB_KIND_PROVIDER,
        CONF_PROTOCOL: PROTOCOL_ESPHOME_NATIVE,
        CONF_CONNECTION: connection,
        CONF_PROVIDER_ID: local_provider_id,
        CONF_PROVIDER_REVISION: provider_revision,
        CONF_CONFIG_REVISION: config_revision,
        CONF_AVAILABLE_KEYS: sorted(
            {str(key) for key in configured_available_keys if str(key)}
        ),
    }


def _mqtt_hub_candidate(
    *,
    host: Any,
    port: Any,
    tls: Any,
    username: Any,
    password: Any,
    keepalive: Any,
    qos: Any,
    provider_revision: int,
    config_revision: int,
    provider_id: Any,
) -> dict[str, Any]:
    """Normalize one standard MQTT 3.1.1 broker candidate."""
    local_provider_id = _configured_opaque_id(provider_id)
    if local_provider_id is None:
        raise ProviderConfigurationError("Provider ID is invalid")
    if not isinstance(tls, bool):
        raise ProviderConfigurationError("MQTT TLS setting must be boolean")
    connection = {
        CONF_HOST: canonicalize_mqtt_host(host),
        CONF_PORT: canonicalize_mqtt_port(port),
        CONF_TLS: tls,
        CONF_KEEPALIVE: keepalive,
        CONF_QOS: qos,
    }
    normalized_username = str(username).strip() if username is not None else ""
    if normalized_username:
        if not isinstance(password, str) or not password:
            raise ProviderConfigurationError(
                "MQTT username requires a password"
            )
        connection[CONF_USERNAME] = normalized_username
        connection[CONF_PASSWORD] = password
    elif password not in (None, ""):
        raise ProviderConfigurationError("MQTT password requires a username")
    # Let the provider perform the complete connection-contract validation.
    return {
        CONF_KIND: HUB_KIND_PROVIDER,
        CONF_PROTOCOL: PROTOCOL_MQTT,
        CONF_CONNECTION: connection,
        CONF_PROVIDER_ID: local_provider_id,
        CONF_PROVIDER_REVISION: provider_revision,
        CONF_CONFIG_REVISION: config_revision,
        CONF_AVAILABLE_KEYS: [],
    }


async def _async_validate_hub_candidate(
    hass: HomeAssistant,
    candidate: Mapping[str, Any],
    *,
    linked_entry: ConfigEntry | None = None,
) -> dict[str, Any]:
    """Validate a provider and every existing linked-system contract."""
    mqtt_sources: Collection[str] | None = None
    mqtt_keys: Mapping[str, Collection[str]] | None = None
    if linked_entry is not None and candidate.get(CONF_PROTOCOL) == PROTOCOL_MQTT:
        mqtt_sources, mqtt_keys = _mqtt_sources_from_entry(linked_entry)
    provider = await _async_initialize_provider(
        hass,
        candidate,
        mqtt_source_system_ids=mqtt_sources,
        mqtt_source_available_keys=mqtt_keys,
    )
    try:
        if linked_entry is not None:
            linked = _system_subentries(linked_entry)
            communication_ids = {
                _communication_source_system_id(subentry)
                for subentry in linked
            }
            missing = communication_ids - set(provider.communication_systems)
            if missing:
                raise _LinkedSystemsValidationError(
                    "linked_systems_missing", missing
                )

            invalid: list[str] = []
            for subentry in linked:
                system_id = str(
                    subentry.data.get(
                        CONF_SYSTEM_ID,
                        subentry.data.get(CONF_SOURCE_SYSTEM_ID, "?"),
                    )
                )
                source_expressions = subentry.data.get(
                    CONF_SOURCE_EXPRESSIONS
                )
                if not isinstance(source_expressions, Mapping):
                    invalid.append(system_id)
                    continue
                communication_id = _communication_source_system_id(subentry)
                try:
                    unbound = RuntimeConfiguration.compile(source_expressions)
                    available = await provider.async_get_available_keys(
                        communication_id, unbound.required_source_keys
                    )
                    runtime = RuntimeConfiguration.compile(
                        source_expressions,
                        available_source_keys=available,
                    )
                except ValueError:
                    invalid.append(system_id)
                    continue
                try:
                    snapshot = await provider.get_system_snapshot(
                        communication_id,
                        _required_source_keys(runtime),
                        runtime.source_keys,
                    )
                    status = snapshot.values
                    if _required_source_keys(runtime) - {
                        str(key) for key in status
                    }:
                        invalid.append(system_id)
                        continue
                    result = evaluate_source_expressions(
                        runtime.compiled_source_expressions,
                        status,
                        EvaluationContext(
                            snapshot.last_report,
                            snapshot.last_update,
                        ),
                    )
                    if (
                        result.errors
                        or set(result.values) != set(runtime.evaluated_keys)
                    ):
                        invalid.append(system_id)
                except (ProviderResponseError, ProviderSystemError):
                    invalid.append(system_id)
            if invalid:
                raise _LinkedSystemsValidationError(
                    "linked_systems_invalid", invalid
                )

        # Discovery is a runtime effective keyset. The configured empty list
        # must remain empty so that the next lifecycle still means AUTO.
        stored = _json_copy(candidate)
        if candidate.get(CONF_PROTOCOL) == PROTOCOL_ESPHOME_NATIVE:
            expected_mac = getattr(provider, "expected_mac", None)
            if not isinstance(expected_mac, str) or not expected_mac:
                raise ProviderResponseError(
                    "ESPHome did not report a valid MAC address"
                )
            stored[CONF_CONNECTION][CONF_EXPECTED_MAC] = expected_mac
        return stored
    finally:
        await _async_close_temporary_provider(provider)


def _publish_provider_candidate(
    hass: HomeAssistant,
    current: ConfigEntry,
    candidate: Mapping[str, Any],
    *,
    protocol_changed: bool = False,
) -> bool:
    """Publish one validated provider change and preserve system identity."""
    next_provider_revision = int(current.data[CONF_PROVIDER_REVISION]) + 1
    next_config_revision = int(current.data[CONF_CONFIG_REVISION]) + 1

    for subentry in _system_subentries(current):
        subentry_data = _json_copy(subentry.data)
        if protocol_changed:
            subentry_data[CONF_ENABLED] = False
            subentry_data.pop(CONF_VALIDATED_HUB_UID, None)
            subentry_data.pop(CONF_VALIDATED_PROVIDER_REVISION, None)
        else:
            subentry_data[CONF_VALIDATED_HUB_UID] = current.unique_id
            subentry_data[CONF_VALIDATED_PROVIDER_REVISION] = (
                next_provider_revision
            )
        subentry_data[CONF_CONFIG_REVISION] = (
            int(subentry.data.get(CONF_CONFIG_REVISION, 0)) + 1
        )
        hass.config_entries.async_update_subentry(
            current, subentry, data=subentry_data
        )

    stored = _json_copy(candidate)
    stored[CONF_PROVIDER_REVISION] = next_provider_revision
    stored[CONF_CONFIG_REVISION] = next_config_revision
    return hass.config_entries.async_update_entry(
        current,
        data=stored,
        title=_provider_title(stored),
        version=_CONFIG_ENTRY_VERSION,
        minor_version=_CONFIG_ENTRY_MINOR_VERSION,
    )


def _provider_title(data: Mapping[str, Any]) -> str:
    """Return a readable title without using connection data as identity."""
    label = {
        PROTOCOL_ESPHOME_NATIVE: "ESPHome Native",
        PROTOCOL_MQTT: "MQTT",
        PROTOCOL_WEB_API: "Web API",
    }.get(data.get(CONF_PROTOCOL), "Provider")
    return f"{label} – {data[CONF_PROVIDER_ID]}"


async def _async_live_validate_system(
    hass: HomeAssistant,
    entry: ConfigEntry,
    source_system_id: str,
    runtime: RuntimeConfiguration,
    *,
    allow_offline_contract: bool = True,
) -> _LiveValidationResult:
    """Validate one compiled mapping against one provider status response."""
    required = _required_source_keys(runtime)
    provider: Provider | None = None
    try:
        mqtt_sources: list[str] | None = None
        mqtt_keys: dict[str, tuple[str, ...]] | None = None
        if entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT:
            stored_sources, mqtt_keys = _mqtt_sources_from_entry(entry)
            mqtt_sources = list(stored_sources)
            if source_system_id not in mqtt_sources:
                mqtt_sources.append(source_system_id)
            mqtt_keys.pop(source_system_id, None)
        provider = await _async_initialize_provider(
            hass,
            entry.data,
            duplicate_systems=_duplicate_systems_from_entry(entry),
            mqtt_source_system_ids=mqtt_sources,
            mqtt_source_available_keys=mqtt_keys,
        )
        available = await provider.async_get_available_keys(source_system_id, required)
        bound_runtime, binding_errors = _compile_expressions(
            runtime.source_expressions,
            available_source_keys=available,
        )
        if bound_runtime is None:
            return _LiveValidationResult(
                False,
                base_error=binding_errors.get("base"),
                expression_errors={
                    key: value for key, value in binding_errors.items() if key != "base"
                },
            )
        required = _required_source_keys(bound_runtime)
        snapshot = await provider.get_system_snapshot(
            source_system_id,
            required,
            bound_runtime.source_keys,
        )
        if (
            entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT
            and snapshot.last_report is None
        ):
            return _LiveValidationResult(False, "cannot_validate_offline")
        status = snapshot.values
        result = evaluate_source_expressions(
            bound_runtime.compiled_source_expressions,
            status,
            EvaluationContext(snapshot.last_report, snapshot.last_update),
        )
        evaluated = result.values
        if result.errors:
            expression_errors = {
                key: _EVALUATION_FORM_ERRORS.get(
                    error.category, "source_value_evaluation_error"
                )
                for key, error in result.errors.items()
            }
            return _LiveValidationResult(
                False,
                expression_errors=expression_errors,
            )
        missing_results = set(bound_runtime.evaluated_keys) - set(evaluated)
        if missing_results:
            return _LiveValidationResult(
                False,
                expression_errors={
                    key: "source_value_evaluation_error" for key in missing_results
                },
            )
        if set(evaluated) != set(bound_runtime.evaluated_keys):
            return _LiveValidationResult(False, "invalid_source_values")
        return _LiveValidationResult(
            True,
            available_source_keys=tuple(
                sorted(
                    set(available or status)
                    | set(bound_runtime.source_keys)
                )
            ),
            required_source_keys=tuple(
                sorted(bound_runtime.required_source_keys)
            ),
        )
    except ValueError:
        return _LiveValidationResult(False, "invalid_source_values")
    except (
        ProviderAuthenticationError,
        ProviderConfigurationError,
        ProviderResponseError,
        ProviderSystemError,
    ) as err:
        return _LiveValidationResult(False, _provider_error_key(err))
    except (ProviderCommunicationError, ProviderRateLimitError):
        if allow_offline_contract and not _missing_offline_keys(entry, required):
            return _LiveValidationResult(True)
        return _LiveValidationResult(False, "cannot_validate_offline")
    except Exception as err:
        if not isinstance(err, ProviderError):
            _LOGGER.exception("Unexpected system live-validation error")
        return _LiveValidationResult(False, _provider_error_key(err))
    finally:
        if provider is not None:
            await _async_close_temporary_provider(provider)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle provider hub creation, reconfiguration and reauthentication."""

    VERSION = _CONFIG_ENTRY_VERSION
    MINOR_VERSION = _CONFIG_ENTRY_MINOR_VERSION

    def __init__(self) -> None:
        self._hub_uid: str | None = None
        self._unique_id_bound = False
        self._protocol = PROTOCOL_WEB_API
        self._base_config_revision: int | None = None
        self._base_system_contract: tuple[Any, ...] | None = None
        self._esphome_discovered_nodes: (
            dict[str, EsphomeDiscoveredNode] | None
        ) = None
        self._esphome_selected_host: str | None = None
        self._esphome_selected_port: int | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the system subentry flow supported by provider hubs."""
        del config_entry
        return {
            SUBENTRY_TYPE_SYSTEM: SystemSubentryFlowHandler,
            SUBENTRY_TYPE_DUPLICATE_SYSTEM:
                DuplicateSystemSubentryFlowHandler,
        }

    async def _async_bind_unique_id(self, unique_id: str, *, mismatch: bool) -> None:
        """Bind the permanent hub UUID to this flow exactly once."""
        if self._unique_id_bound:
            return
        await self.async_set_unique_id(unique_id)
        if mismatch:
            self._abort_if_unique_id_mismatch()
        else:
            self._abort_if_unique_id_configured()
        self._unique_id_bound = True

    def _ensure_new_hub_uid(self) -> str:
        """Generate and claim a collision-free UUID for a new hub."""
        if self._hub_uid is not None:
            return self._hub_uid
        claims = _claims(self.hass)
        while True:
            candidate = str(uuid4())
            if not _hub_uid_exists(self.hass, candidate, self.flow_id):
                claims.hub_uids[candidate] = self.flow_id
                self._hub_uid = candidate
                return candidate

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the provider protocol before collecting connection data."""
        hub_uid = self._ensure_new_hub_uid()
        await self._async_bind_unique_id(hub_uid, mismatch=False)
        if user_input is not None:
            protocol = str(user_input.get(CONF_PROTOCOL, ""))
            if protocol in _PROTOCOL_OPTIONS:
                self._protocol = protocol
                if protocol == PROTOCOL_ESPHOME_NATIVE:
                    return await self.async_step_esphome_native_node()
                if protocol == PROTOCOL_MQTT:
                    return await self.async_step_mqtt()
                return await self.async_step_web_api()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL, default=PROTOCOL_WEB_API
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=PROTOCOL_WEB_API,
                                    label="Web API",
                                ),
                                selector.SelectOptionDict(
                                    value=PROTOCOL_ESPHOME_NATIVE,
                                    label="ESPHome Native",
                                ),
                                selector.SelectOptionDict(
                                    value=PROTOCOL_MQTT,
                                    label="MQTT 3.1.1",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def _async_esphome_node_selection(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        reconfigure: bool,
    ) -> ConfigFlowResult:
        """Select a current mDNS hint or continue with manual host entry."""
        if self._esphome_discovered_nodes is None:
            try:
                discovered = await async_discover_esphome_nodes(self.hass)
            except Exception:
                _LOGGER.debug(
                    "ESPHome mDNS discovery is unavailable; manual entry remains",
                    exc_info=True,
                )
                discovered = ()
            self._esphome_discovered_nodes = {
                node.service_name: node for node in discovered
            }

        errors: dict[str, str] = {}
        if user_input is not None:
            selected = str(user_input.get(CONF_ESPHOME_NODE, ""))
            if selected == _MANUAL_ESPHOME_NODE:
                self._esphome_selected_host = None
                self._esphome_selected_port = None
            elif node := self._esphome_discovered_nodes.get(selected):
                self._esphome_selected_host = node.host
                self._esphome_selected_port = node.port
            else:
                errors[CONF_ESPHOME_NODE] = "invalid_discovery"

            if not errors:
                if reconfigure:
                    return await self.async_step_reconfigure_esphome_native()
                return await self.async_step_esphome_native()

        return self.async_show_form(
            step_id=step_id,
            data_schema=_esphome_node_schema(
                self._esphome_discovered_nodes.values()
            ),
            errors=errors,
        )

    async def async_step_esphome_native_node(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a discovered ESPHome node or choose manual entry."""
        return await self._async_esphome_node_selection(
            user_input,
            step_id="esphome_native_node",
            reconfigure=False,
        )

    async def async_step_web_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and create a Web API provider hub."""
        if self._hub_uid is None:
            hub_uid = self._ensure_new_hub_uid()
            await self._async_bind_unique_id(hub_uid, mismatch=False)
        default_base_url, preset, configured_keys = _preset_parts()
        errors: dict[str, str] = {}
        suggested = user_input or {}

        if user_input is not None:
            provider_id = _configured_opaque_id(
                user_input.get(CONF_PROVIDER_ID)
            )
            if provider_id is None:
                errors[CONF_PROVIDER_ID] = "invalid_provider_id"
            elif _provider_id_exists(
                self.hass, provider_id, self.flow_id
            ):
                errors[CONF_PROVIDER_ID] = "provider_id_exists"
            else:
                try:
                    candidate = _hub_candidate(
                        protocol=self._protocol,
                        base_url=default_base_url,
                        user_id=user_input[CONF_USER_ID],
                        password=user_input[CONF_PASSWORD],
                        preset=preset,
                        configured_available_keys=configured_keys,
                        provider_revision=1,
                        config_revision=1,
                        provider_id=provider_id,
                    )
                    candidate = await _async_validate_hub_candidate(
                        self.hass, candidate
                    )
                except Exception as err:
                    if not isinstance(err, ProviderError):
                        _LOGGER.exception(
                            "Unexpected Web API hub validation error"
                        )
                    errors["base"] = _provider_error_key(err)
                else:
                    if _provider_id_exists(self.hass, provider_id, self.flow_id):
                        errors[CONF_PROVIDER_ID] = "provider_id_exists"
                    else:
                        _claims(self.hass).provider_ids[provider_id] = self.flow_id
                        try:
                            return self.async_create_entry(
                                title=_provider_title(candidate), data=candidate
                            )
                        except BaseException:
                            _claims(self.hass).release(self.flow_id)
                            raise

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_PROVIDER_ID,
                default=str(suggested.get(CONF_PROVIDER_ID, "")),
            ): str,
            vol.Required(
                CONF_USER_ID,
                default=str(suggested.get(CONF_USER_ID, "")),
            ): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return self.async_show_form(
            step_id="web_api",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_esphome_native(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and create an encrypted ESPHome Native provider hub."""
        if self._hub_uid is None:
            hub_uid = self._ensure_new_hub_uid()
            await self._async_bind_unique_id(hub_uid, mismatch=False)
        self._protocol = PROTOCOL_ESPHOME_NATIVE
        errors: dict[str, str] = {}
        suggested = user_input or {}

        if user_input is not None:
            provider_id = _configured_opaque_id(
                user_input.get(CONF_PROVIDER_ID)
            )
            if provider_id is None:
                errors[CONF_PROVIDER_ID] = "invalid_provider_id"
            elif _provider_id_exists(
                self.hass, provider_id, self.flow_id
            ):
                errors[CONF_PROVIDER_ID] = "provider_id_exists"
            else:
                try:
                    candidate = _esphome_hub_candidate(
                        host=user_input.get(CONF_HOST),
                        port=user_input.get(CONF_PORT),
                        noise_psk=user_input.get(CONF_NOISE_PSK),
                        expected_mac=None,
                        configured_available_keys=(),
                        provider_revision=1,
                        config_revision=1,
                        provider_id=provider_id,
                    )
                    candidate = await _async_validate_hub_candidate(
                        self.hass, candidate
                    )
                except Exception as err:
                    if not isinstance(err, ProviderError):
                        _LOGGER.exception(
                            "Unexpected ESPHome Native hub validation error"
                        )
                    errors["base"] = _provider_error_key(err)
                else:
                    if _provider_id_exists(self.hass, provider_id, self.flow_id):
                        errors[CONF_PROVIDER_ID] = "provider_id_exists"
                    else:
                        _claims(self.hass).provider_ids[provider_id] = self.flow_id
                        try:
                            return self.async_create_entry(
                                title=_provider_title(candidate), data=candidate
                            )
                        except BaseException:
                            _claims(self.hass).release(self.flow_id)
                            raise

        return self.async_show_form(
            step_id="esphome_native",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROVIDER_ID,
                        default=str(suggested.get(CONF_PROVIDER_ID, "")),
                    ): str,
                    vol.Required(
                        CONF_HOST,
                        default=str(
                            suggested.get(
                                CONF_HOST,
                                self._esphome_selected_host or "",
                            )
                        ),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=suggested.get(
                            CONF_PORT,
                            self._esphome_selected_port
                            or DEFAULT_ESPHOME_PORT,
                        ),
                    ): int,
                    vol.Required(CONF_NOISE_PSK): str,
                }
            ),
            errors=errors,
        )

    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and create a standard MQTT broker hub."""
        if self._hub_uid is None:
            hub_uid = self._ensure_new_hub_uid()
            await self._async_bind_unique_id(hub_uid, mismatch=False)
        self._protocol = PROTOCOL_MQTT
        errors: dict[str, str] = {}
        suggested = user_input or {}
        if user_input is not None:
            provider_id = _configured_opaque_id(user_input.get(CONF_PROVIDER_ID))
            if provider_id is None:
                errors[CONF_PROVIDER_ID] = "invalid_provider_id"
            elif _provider_id_exists(self.hass, provider_id, self.flow_id):
                errors[CONF_PROVIDER_ID] = "provider_id_exists"
            else:
                try:
                    candidate = _mqtt_hub_candidate(
                        host=user_input.get(CONF_HOST),
                        port=user_input.get(CONF_PORT),
                        tls=user_input.get(CONF_TLS, False),
                        username=user_input.get(CONF_USERNAME, ""),
                        password=user_input.get(CONF_PASSWORD, ""),
                        keepalive=user_input.get(CONF_KEEPALIVE, 60),
                        qos=user_input.get(CONF_QOS, 0),
                        provider_revision=1,
                        config_revision=1,
                        provider_id=provider_id,
                    )
                    candidate = await _async_validate_hub_candidate(
                        self.hass, candidate
                    )
                except Exception as err:
                    if not isinstance(err, ProviderError):
                        _LOGGER.exception("Unexpected MQTT hub validation error")
                    errors["base"] = _provider_error_key(err)
                else:
                    _claims(self.hass).provider_ids[provider_id] = self.flow_id
                    try:
                        return self.async_create_entry(
                            title=_provider_title(candidate), data=candidate
                        )
                    except BaseException:
                        _claims(self.hass).release(self.flow_id)
                        raise
        tls_default = bool(suggested.get(CONF_TLS, False))
        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROVIDER_ID,
                        default=str(suggested.get(CONF_PROVIDER_ID, "")),
                    ): str,
                    vol.Required(
                        CONF_HOST,
                        default=str(suggested.get(CONF_HOST, "")),
                    ): str,
                    vol.Required(
                        CONF_TLS,
                        default=tls_default,
                    ): bool,
                    vol.Required(
                        CONF_PORT,
                        default=suggested.get(
                            CONF_PORT,
                            DEFAULT_MQTT_TLS_PORT if tls_default else DEFAULT_MQTT_PORT,
                        ),
                    ): int,
                    vol.Optional(
                        CONF_USERNAME,
                        default=str(suggested.get(CONF_USERNAME, "")),
                    ): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Required(
                        CONF_KEEPALIVE,
                        default=suggested.get(CONF_KEEPALIVE, 60),
                    ): int,
                    vol.Required(
                        CONF_QOS,
                        default=suggested.get(CONF_QOS, 0),
                    ): vol.In((0, 1, 2)),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the replacement protocol before entering its connection data."""
        entry = self._get_reconfigure_entry()
        if entry.unique_id is None:
            return self.async_abort(reason="invalid_hub_identity")
        await self._async_bind_unique_id(entry.unique_id, mismatch=True)
        if self._base_config_revision is None:
            self._base_config_revision = int(
                entry.data.get(CONF_CONFIG_REVISION, 0)
            )
            self._base_system_contract = _system_contract_snapshot(entry)
        if user_input is not None:
            protocol = str(user_input.get(CONF_PROTOCOL, ""))
            if protocol in _PROTOCOL_OPTIONS:
                if protocol == PROTOCOL_ESPHOME_NATIVE:
                    return await self.async_step_reconfigure_esphome_native_node()
                if protocol == PROTOCOL_MQTT:
                    return await self.async_step_reconfigure_mqtt()
                return await self.async_step_reconfigure_web_api()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL,
                        default=str(entry.data[CONF_PROTOCOL]),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=PROTOCOL_WEB_API,
                                    label="Web API",
                                ),
                                selector.SelectOptionDict(
                                    value=PROTOCOL_ESPHOME_NATIVE,
                                    label="ESPHome Native",
                                ),
                                selector.SelectOptionDict(
                                    value=PROTOCOL_MQTT,
                                    label="MQTT 3.1.1",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def _async_finish_hub_reconfiguration(
        self,
        entry: ConfigEntry,
        candidate: Mapping[str, Any],
        *,
        protocol_changed: bool,
        errors: dict[str, str],
        placeholders: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate and atomically publish one provider candidate."""
        try:
            validated = await _async_validate_hub_candidate(
                self.hass,
                candidate,
                linked_entry=None if protocol_changed else entry,
            )
        except _LinkedSystemsValidationError as err:
            errors["base"] = err.translation_key
            placeholders["system_ids"] = ", ".join(err.system_ids)
            return None
        except Exception as err:
            if not isinstance(err, ProviderError):
                _LOGGER.exception("Unexpected hub reconfiguration error")
            errors["base"] = _provider_error_key(err)
            return None

        current = self.hass.config_entries.async_get_known_entry(entry.entry_id)
        if (
            current.unique_id != entry.unique_id
            or current.data.get(CONF_KIND) != HUB_KIND_PROVIDER
            or int(current.data.get(CONF_CONFIG_REVISION, 0))
            != self._base_config_revision
            or _system_contract_snapshot(current) != self._base_system_contract
        ):
            errors["base"] = "configuration_changed"
            return None
        if _provider_id_exists(
            self.hass,
            _entry_provider_id(current),
            self.flow_id,
            exclude_entry_id=current.entry_id,
        ):
            errors["base"] = "provider_id_exists"
            return None
        if (
            validated == _json_copy(current.data)
            and current.version == _CONFIG_ENTRY_VERSION
            and current.minor_version == _CONFIG_ENTRY_MINOR_VERSION
        ):
            if not current.update_listeners:
                self.hass.config_entries.async_schedule_reload(current.entry_id)
            return self.async_abort(reason="reconfigure_successful")
        changed = _publish_provider_candidate(
            self.hass,
            current,
            validated,
            protocol_changed=protocol_changed,
        )
        if not changed or not current.update_listeners:
            self.hass.config_entries.async_schedule_reload(current.entry_id)
        return self.async_abort(reason="reconfigure_successful")

    async def async_step_reconfigure_web_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure or switch to the Web API provider."""
        entry = self._get_reconfigure_entry()
        protocol_changed = entry.data[CONF_PROTOCOL] != PROTOCOL_WEB_API
        old_connection = (
            entry.data[CONF_CONNECTION] if not protocol_changed else {}
        )
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        suggested = user_input or {}
        if user_input is not None:
            password = str(user_input.get(CONF_PASSWORD, ""))
            if not password:
                password = str(old_connection.get(CONF_PASSWORD, ""))
            default_base_url, preset, _ = _preset_parts()
            try:
                candidate = _hub_candidate(
                    protocol=PROTOCOL_WEB_API,
                    base_url=default_base_url,
                    user_id=user_input.get(CONF_USER_ID),
                    password=password,
                    preset=preset,
                    configured_available_keys=(
                        ()
                        if protocol_changed
                        else entry.data.get(CONF_AVAILABLE_KEYS, ())
                    ),
                    provider_revision=int(entry.data[CONF_PROVIDER_REVISION]),
                    config_revision=int(entry.data[CONF_CONFIG_REVISION]),
                    provider_id=_entry_provider_id(entry),
                )
            except Exception as err:
                errors["base"] = _provider_error_key(err)
            else:
                result = await self._async_finish_hub_reconfiguration(
                    entry,
                    candidate,
                    protocol_changed=protocol_changed,
                    errors=errors,
                    placeholders=placeholders,
                )
                if result is not None:
                    return result

        password_field = (
            vol.Required(CONF_PASSWORD)
            if protocol_changed
            else vol.Optional(CONF_PASSWORD, default="")
        )
        return self.async_show_form(
            step_id="reconfigure_web_api",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_ID,
                        default=str(
                            suggested.get(
                                CONF_USER_ID,
                                old_connection.get(CONF_USER_ID, ""),
                            )
                        ),
                    ): str,
                    password_field: str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure_esphome_native_node(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an ESPHome mDNS hint before native reconfiguration."""
        return await self._async_esphome_node_selection(
            user_input,
            step_id="reconfigure_esphome_native_node",
            reconfigure=True,
        )

    async def async_step_reconfigure_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure or switch to a standard MQTT broker."""
        entry = self._get_reconfigure_entry()
        protocol_changed = entry.data[CONF_PROTOCOL] != PROTOCOL_MQTT
        old_connection = entry.data[CONF_CONNECTION] if not protocol_changed else {}
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        suggested = user_input or {}
        if user_input is not None:
            username_value = user_input.get(CONF_USERNAME, "")
            username = str(username_value).strip() if username_value is not None else ""
            password = str(user_input.get(CONF_PASSWORD, ""))
            if not password and username and username == old_connection.get(CONF_USERNAME):
                password = str(old_connection.get(CONF_PASSWORD, ""))
            try:
                candidate = _mqtt_hub_candidate(
                    host=user_input.get(CONF_HOST),
                    port=user_input.get(CONF_PORT),
                    tls=user_input.get(CONF_TLS, False),
                    username=username,
                    password=password,
                    keepalive=user_input.get(CONF_KEEPALIVE, 60),
                    qos=user_input.get(CONF_QOS, 0),
                    provider_revision=int(entry.data[CONF_PROVIDER_REVISION]),
                    config_revision=int(entry.data[CONF_CONFIG_REVISION]),
                    provider_id=_entry_provider_id(entry),
                )
            except Exception as err:
                errors["base"] = _provider_error_key(err)
            else:
                result = await self._async_finish_hub_reconfiguration(
                    entry,
                    candidate,
                    protocol_changed=protocol_changed,
                    errors=errors,
                    placeholders=placeholders,
                )
                if result is not None:
                    return result
        tls_default = bool(
            suggested.get(CONF_TLS, old_connection.get(CONF_TLS, False))
        )
        password_field = (
            vol.Optional(CONF_PASSWORD, default="")
            if old_connection.get(CONF_USERNAME)
            else vol.Optional(CONF_PASSWORD, default="")
        )
        return self.async_show_form(
            step_id="reconfigure_mqtt",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=str(suggested.get(
                            CONF_HOST, old_connection.get(CONF_HOST, "")
                        )),
                    ): str,
                    vol.Required(CONF_TLS, default=tls_default): bool,
                    vol.Required(
                        CONF_PORT,
                        default=suggested.get(
                            CONF_PORT,
                            old_connection.get(
                                CONF_PORT,
                                DEFAULT_MQTT_TLS_PORT if tls_default else DEFAULT_MQTT_PORT,
                            ),
                        ),
                    ): int,
                    vol.Optional(
                        CONF_USERNAME,
                        default=str(suggested.get(
                            CONF_USERNAME, old_connection.get(CONF_USERNAME, "")
                        )),
                    ): str,
                    password_field: str,
                    vol.Required(
                        CONF_KEEPALIVE,
                        default=suggested.get(
                            CONF_KEEPALIVE, old_connection.get(CONF_KEEPALIVE, 60)
                        ),
                    ): int,
                    vol.Required(
                        CONF_QOS,
                        default=suggested.get(
                            CONF_QOS, old_connection.get(CONF_QOS, 0)
                        ),
                    ): vol.In((0, 1, 2)),
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure_esphome_native(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure or switch to an encrypted ESPHome Native provider."""
        entry = self._get_reconfigure_entry()
        protocol_changed = entry.data[CONF_PROTOCOL] != PROTOCOL_ESPHOME_NATIVE
        old_connection = (
            entry.data[CONF_CONNECTION] if not protocol_changed else {}
        )
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        suggested = user_input or {}
        if user_input is not None:
            noise_psk = str(user_input.get(CONF_NOISE_PSK, ""))
            if not noise_psk:
                noise_psk = str(old_connection.get(CONF_NOISE_PSK, ""))
            try:
                candidate = _esphome_hub_candidate(
                    host=user_input.get(CONF_HOST),
                    port=user_input.get(CONF_PORT),
                    noise_psk=noise_psk,
                    expected_mac=old_connection.get(CONF_EXPECTED_MAC),
                    configured_available_keys=(
                        ()
                        if protocol_changed
                        else entry.data.get(CONF_AVAILABLE_KEYS, ())
                    ),
                    provider_revision=int(entry.data[CONF_PROVIDER_REVISION]),
                    config_revision=int(entry.data[CONF_CONFIG_REVISION]),
                    provider_id=_entry_provider_id(entry),
                )
            except Exception as err:
                errors["base"] = _provider_error_key(err)
            else:
                result = await self._async_finish_hub_reconfiguration(
                    entry,
                    candidate,
                    protocol_changed=protocol_changed,
                    errors=errors,
                    placeholders=placeholders,
                )
                if result is not None:
                    return result

        key_field = (
            vol.Required(CONF_NOISE_PSK)
            if protocol_changed
            else vol.Optional(CONF_NOISE_PSK, default="")
        )
        return self.async_show_form(
            step_id="reconfigure_esphome_native",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=str(
                            suggested.get(
                                CONF_HOST,
                                self._esphome_selected_host
                                or old_connection.get(CONF_HOST, ""),
                            )
                        ),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=suggested.get(
                            CONF_PORT,
                            self._esphome_selected_port
                            or old_connection.get(
                                CONF_PORT, DEFAULT_ESPHOME_PORT
                            ),
                        ),
                    ): int,
                    key_field: str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start credential-only reauthentication."""
        del entry_data
        entry = self._get_reauth_entry()
        if entry.unique_id is None:
            return self.async_abort(reason="invalid_hub_identity")
        await self._async_bind_unique_id(entry.unique_id, mismatch=True)
        self._base_config_revision = int(
            entry.data.get(CONF_CONFIG_REVISION, 0)
        )
        self._base_system_contract = _system_contract_snapshot(entry)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement provider credentials against linked systems."""
        entry = self._get_reauth_entry()
        protocol = str(entry.data[CONF_PROTOCOL])
        connection = entry.data[CONF_CONNECTION]
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                common = {
                    "configured_available_keys": entry.data.get(
                        CONF_AVAILABLE_KEYS, ()
                    ),
                    "provider_revision": int(
                        entry.data[CONF_PROVIDER_REVISION]
                    ),
                    "config_revision": int(entry.data[CONF_CONFIG_REVISION]),
                    "provider_id": _entry_provider_id(entry),
                }
                if protocol == PROTOCOL_ESPHOME_NATIVE:
                    candidate = _esphome_hub_candidate(
                        host=connection[CONF_HOST],
                        port=connection[CONF_PORT],
                        noise_psk=str(user_input[CONF_NOISE_PSK]),
                        expected_mac=connection[CONF_EXPECTED_MAC],
                        **common,
                    )
                elif protocol == PROTOCOL_MQTT:
                    candidate = _mqtt_hub_candidate(
                        host=connection[CONF_HOST],
                        port=connection[CONF_PORT],
                        tls=connection.get(CONF_TLS, False),
                        username=connection.get(CONF_USERNAME, ""),
                        password=str(user_input[CONF_PASSWORD]),
                        keepalive=connection.get(CONF_KEEPALIVE, 60),
                        qos=connection.get(CONF_QOS, 0),
                        provider_revision=common["provider_revision"],
                        config_revision=common["config_revision"],
                        provider_id=common["provider_id"],
                    )
                else:
                    candidate = _hub_candidate(
                        protocol=protocol,
                        base_url=entry.data[CONF_BASE_URL],
                        user_id=connection[CONF_USER_ID],
                        password=str(user_input[CONF_PASSWORD]),
                        preset=SOLESTA_WEB_API_DEFAULT,
                        **common,
                    )
                candidate = await _async_validate_hub_candidate(
                    self.hass,
                    candidate,
                    linked_entry=entry,
                )
            except _LinkedSystemsValidationError as err:
                errors["base"] = err.translation_key
                placeholders["system_ids"] = ", ".join(err.system_ids)
            except Exception as err:
                if not isinstance(err, ProviderError):
                    _LOGGER.exception("Unexpected reauthentication error")
                errors["base"] = _provider_error_key(err)

            if not errors:
                current = self.hass.config_entries.async_get_known_entry(
                    entry.entry_id
                )
                if (
                    current.unique_id != entry.unique_id
                    or int(current.data.get(CONF_CONFIG_REVISION, 0))
                    != self._base_config_revision
                    or _system_contract_snapshot(current)
                    != self._base_system_contract
                ):
                    errors["base"] = "configuration_changed"
                else:
                    if candidate == _json_copy(current.data):
                        self.hass.config_entries.async_schedule_reload(
                            current.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")
                    changed = _publish_provider_candidate(
                        self.hass, current, candidate
                    )
                    # Failed setup has no listener; a loaded entry's listener
                    # owns reload scheduling.
                    if not changed or not current.update_listeners:
                        self.hass.config_entries.async_schedule_reload(
                            current.entry_id
                        )
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NOISE_PSK
                        if protocol == PROTOCOL_ESPHOME_NATIVE
                        else CONF_PASSWORD
                    ): str
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    @callback
    def async_remove(self) -> None:
        """Release pending claims after commit, abort or cancellation."""
        _claims(self.hass).release(self.flow_id)


class SystemSubentryFlowHandler(ConfigSubentryFlow):
    """Create and reconfigure one system ConfigSubentry."""

    def __init__(self) -> None:
        self._base_subentry_data: dict[str, Any] | None = None
        self._base_provider_revision: int | None = None
        self._discovered_systems: tuple[str, ...] | None = None
        self._communication_systems: tuple[str, ...] | None = None
        self._selected_source_system_id: str | None = None
        self._selected_communication_source_system_id: str | None = None

    async def _async_discover_systems(self, entry: ConfigEntry) -> tuple[str, ...]:
        """Discover the provider's complete system list once for this flow."""
        if self._discovered_systems is not None:
            return self._discovered_systems
        provider: Provider | None = None
        try:
            mqtt_sources: Collection[str] | None = None
            mqtt_keys: Mapping[str, Collection[str]] | None = None
            if entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT:
                mqtt_sources, mqtt_keys = _mqtt_sources_from_entry(entry)
            provider = await _async_initialize_provider(
                self.hass,
                entry.data,
                duplicate_systems=_duplicate_systems_from_entry(entry),
                mqtt_source_system_ids=mqtt_sources,
                mqtt_source_available_keys=mqtt_keys,
            )
            self._discovered_systems = tuple(
                sorted(
                    {
                        str(item)
                        for item in provider.systems
                        if str(item).strip()
                    }
                )
            )
            self._communication_systems = tuple(
                sorted(set(provider.communication_systems))
            )
        finally:
            if provider is not None:
                await _async_close_temporary_provider(provider)
        return self._discovered_systems

    async def _async_discover_communication_systems(
        self, entry: ConfigEntry
    ) -> tuple[str, ...]:
        """Return only systems truly reported at the communication boundary."""
        await self._async_discover_systems(entry)
        assert self._communication_systems is not None
        return self._communication_systems

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select one system actually reported by the v1 provider."""
        entry = self._get_entry()
        if entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT:
            return await self.async_step_mqtt_source(user_input)
        discovery_revision = (
            self._base_provider_revision
            if self._base_provider_revision is not None
            else int(entry.data[CONF_PROVIDER_REVISION])
        )
        try:
            discovered = await self._async_discover_systems(entry)
        except ProviderError as err:
            return self.async_abort(reason=_provider_error_key(err))
        except Exception:
            _LOGGER.exception(
                "Unexpected provider discovery error while adding a system"
            )
            return self.async_abort(reason="unknown")
        current = self.hass.config_entries.async_get_known_entry(entry.entry_id)
        if int(current.data[CONF_PROVIDER_REVISION]) != discovery_revision:
            return self.async_abort(reason="configuration_changed")
        self._base_provider_revision = discovery_revision
        linked = {
            str(subentry.data.get(CONF_SOURCE_SYSTEM_ID))
            for subentry in _system_subentries(entry)
        }
        available = tuple(item for item in discovered if item not in linked)
        if not available:
            return self.async_abort(reason="no_available_systems")

        errors: dict[str, str] = {}
        source_system_id = str(
            (user_input or {}).get(
                CONF_SOURCE_SYSTEM_ID, available[0]
            )
        ).strip()

        if user_input is not None:
            if source_system_id not in available:
                errors[CONF_SOURCE_SYSTEM_ID] = "invalid_source_system"
            elif _source_system_id_exists(
                entry, source_system_id
            ) or _source_system_id_is_claimed(
                self.hass,
                entry.entry_id,
                source_system_id,
                self.flow_id,
            ):
                errors[CONF_SOURCE_SYSTEM_ID] = "source_system_id_exists"
            else:
                self._selected_source_system_id = source_system_id
                return await self.async_step_details()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SOURCE_SYSTEM_ID,
                        default=source_system_id,
                    ): vol.In(available),
                }
            ),
            errors=errors,
        )

    async def async_step_mqtt_source(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect one manual MQTT source ID; never scan broker topics."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        source_system_id = str(
            (user_input or {}).get(CONF_SOURCE_SYSTEM_ID, "")
        )
        if user_input is not None:
            try:
                source_system_id = canonicalize_mqtt_root(source_system_id)
            except ProviderConfigurationError:
                errors[CONF_SOURCE_SYSTEM_ID] = "invalid_mqtt_root_topic"
            existing_sources = {
                str(subentry.data.get(CONF_SOURCE_SYSTEM_ID))
                for subentry in _system_subentries(entry)
            }
            if source_system_id in existing_sources:
                errors[CONF_SOURCE_SYSTEM_ID] = "source_system_id_exists"
            if not errors:
                self._selected_source_system_id = source_system_id
                self._base_provider_revision = int(
                    entry.data[CONF_PROVIDER_REVISION]
                )
                return await self.async_step_details()
        return self.async_show_form(
            step_id="mqtt_source",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SOURCE_SYSTEM_ID,
                        default=source_system_id,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start a regular-system flow when HA uses the subtype as step ID."""
        return await self.async_step_user(user_input)

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create the selected system disabled with its permanent UUID."""
        if self._selected_source_system_id is None:
            return await self.async_step_user()

        entry = self._get_entry()
        source_system_id = self._selected_source_system_id
        defaults = default_source_expressions()
        errors: dict[str, str] = {}
        proposed_system_id = cv.slugify(source_system_id.rsplit("/", 1)[-1])
        display_system_id = str(
            (user_input or {}).get(CONF_SYSTEM_ID, proposed_system_id)
        ).strip()
        expressions = (
            _source_expressions(user_input)
            if user_input is not None
            else defaults
        )

        if user_input is not None:
            system_id = _canonical_system_id(display_system_id)
            if system_id is None:
                errors[CONF_SYSTEM_ID] = "invalid_system_id"

            runtime, expression_errors = _compile_expressions(expressions)
            errors.update(expression_errors)
            if system_id is not None and _system_id_exists(
                self.hass, system_id, self.flow_id
            ):
                errors[CONF_SYSTEM_ID] = "system_id_exists"
            if source_system_id and (
                _source_system_id_exists(entry, source_system_id)
                or _source_system_id_is_claimed(
                    self.hass,
                    entry.entry_id,
                    source_system_id,
                    self.flow_id,
                )
            ):
                errors["base"] = "source_system_id_exists"

            if not errors and system_id is not None and runtime is not None:
                # Creation is disabled for every provider. A failed live check
                # leaves the mapping unvalidated; enabling still requires it.
                validation = await _async_live_validate_system(
                    self.hass,
                    entry,
                    (
                        self._selected_communication_source_system_id
                        or source_system_id
                    ),
                    runtime,
                    allow_offline_contract=(
                        entry.data.get(CONF_PROTOCOL) != PROTOCOL_MQTT
                    ),
                )
                validated = validation.valid
                current = self.hass.config_entries.async_get_known_entry(
                    entry.entry_id
                )
                if (
                    self._base_provider_revision is None
                    or int(current.data[CONF_PROVIDER_REVISION])
                    != self._base_provider_revision
                ):
                    errors["base"] = "configuration_changed"
                elif _system_id_exists(
                    self.hass, system_id, self.flow_id
                ):
                    errors[CONF_SYSTEM_ID] = "system_id_exists"
                elif _source_system_id_exists(
                    current, source_system_id
                ) or _source_system_id_is_claimed(
                    self.hass,
                    current.entry_id,
                    source_system_id,
                    self.flow_id,
                ):
                    errors["base"] = "source_system_id_exists"
                elif not errors:
                    claims = _claims(self.hass)
                    while True:
                        system_uid = str(uuid4())
                        if not _system_uid_exists(
                            self.hass, system_uid, self.flow_id
                        ):
                            break
                    claims.system_uids[system_uid] = self.flow_id
                    claims.system_ids[system_id] = self.flow_id
                    claims.source_system_ids[
                        (current.entry_id, source_system_id)
                    ] = self.flow_id
                    return self.async_create_entry(
                        title=system_id,
                        unique_id=system_uid,
                        data={
                            CONF_SYSTEM_ID: system_id,
                            CONF_SOURCE_SYSTEM_ID: source_system_id,
                            CONF_SOURCE_EXPRESSIONS:
                                _stored_expressions(runtime),
                            CONF_REQUIRED_SOURCE_KEYS: sorted(
                                validation.required_source_keys
                                or _required_source_keys(runtime)
                            ),
                            CONF_ENABLED: False,
                            CONF_VALIDATED_HUB_UID: (
                                current.unique_id if validated else None
                            ),
                            CONF_VALIDATED_PROVIDER_REVISION: (
                                int(current.data[CONF_PROVIDER_REVISION])
                                if validated
                                else None
                            ),
                            CONF_CONFIG_REVISION: 1,
                            CONF_EXPRESSION_SCHEMA_VERSION:
                                EXPRESSION_SCHEMA_VERSION,
                            **(
                                {
                                    CONF_AVAILABLE_KEYS: list(
                                        validation.available_source_keys
                                    )
                                }
                                if entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT
                                else {}
                            ),
                            **(
                                {
                                    CONF_COMMUNICATION_SOURCE_SYSTEM_ID:
                                        self._selected_communication_source_system_id
                                }
                                if self._selected_communication_source_system_id
                                is not None
                                else {}
                            ),
                        },
                    )

        return self.async_show_form(
            step_id="details",
            data_schema=_system_create_details_schema(
                system_id=display_system_id,
                source_expressions=expressions,
            ),
            errors=errors,
            description_placeholders={
                "source_system_id": source_system_id,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure provider mapping and desired enabled state."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if subentry.unique_id is None:
            return self.async_abort(reason="invalid_system_identity")

        if self._base_subentry_data is None:
            self._base_subentry_data = _json_copy(subentry.data)
            self._base_provider_revision = int(
                entry.data[CONF_PROVIDER_REVISION]
            )
        base = self._base_subentry_data
        duplicate = subentry.subentry_type == SUBENTRY_TYPE_DUPLICATE_SYSTEM
        mqtt = (
            entry.data.get(CONF_PROTOCOL) == PROTOCOL_MQTT
            and not duplicate
        )
        source_field = (
            CONF_COMMUNICATION_SOURCE_SYSTEM_ID if duplicate else CONF_SOURCE_SYSTEM_ID
        )
        discovery_error: str | None = None
        try:
            discovered = await self._async_discover_communication_systems(entry)
        except ProviderError as err:
            discovered = ()
            discovery_error = _provider_error_key(err)
        except Exception:
            discovered = ()
            discovery_error = "unknown"
            _LOGGER.exception(
                "Unexpected provider discovery error while reconfiguring a system"
            )
        available_sources = tuple(
            source_system_id
            for source_system_id in discovered
            if duplicate or not _source_system_id_exists(
                entry,
                source_system_id,
                exclude_subentry_id=subentry.subentry_id,
            )
        )
        errors: dict[str, str] = {}
        stored_source_system_id = str(base[CONF_SOURCE_SYSTEM_ID])
        stored_mapping = str(base.get(source_field, ""))
        source_options = available_sources
        if mqtt:
            discovery_error = None
        display_system_id = str(
            (user_input or {}).get(CONF_SYSTEM_ID, base[CONF_SYSTEM_ID])
        ).strip()
        selected_source = str(
            (user_input or {}).get(
                source_field,
                stored_source_system_id if mqtt else stored_mapping,
            )
        )
        source_system_id = stored_source_system_id if duplicate else selected_source
        expressions = (
            _source_expressions(
                user_input,
                stored=base[CONF_SOURCE_EXPRESSIONS],
            )
            if user_input is not None
            else dict(base[CONF_SOURCE_EXPRESSIONS])
        )
        enabled = bool(
            (user_input or {}).get(CONF_ENABLED, base[CONF_ENABLED])
        )
        if user_input is not None:
            system_id = _canonical_system_id(display_system_id)
            if system_id is None:
                errors[CONF_SYSTEM_ID] = "invalid_system_id"
            elif _system_id_exists(
                self.hass,
                system_id,
                self.flow_id,
                exclude_subentry_id=subentry.subentry_id,
            ):
                errors[CONF_SYSTEM_ID] = "system_id_exists"
            source_changed = selected_source != stored_mapping
            if mqtt:
                try:
                    selected_source = canonicalize_mqtt_root(selected_source)
                    source_system_id = selected_source
                except ProviderConfigurationError:
                    errors[CONF_SOURCE_SYSTEM_ID] = "invalid_mqtt_root_topic"
                other_sources = {
                    str(item.data.get(CONF_SOURCE_SYSTEM_ID))
                    for item in _system_subentries(entry)
                    if item.subentry_id != subentry.subentry_id
                }
                if selected_source in other_sources:
                    errors[CONF_SOURCE_SYSTEM_ID] = "source_system_id_exists"
                source_changed = selected_source != stored_mapping
            if not mqtt and (enabled or source_changed) and (
                selected_source not in source_options or discovery_error is not None
            ):
                errors[source_field] = "invalid_source_system"
            runtime, expression_errors = _compile_expressions(expressions)
            errors.update(expression_errors)
            if _source_system_id_exists(
                entry,
                source_system_id,
                exclude_subentry_id=subentry.subentry_id,
            ) or _source_system_id_is_claimed(
                self.hass,
                entry.entry_id,
                source_system_id,
                self.flow_id,
            ):
                errors[CONF_SOURCE_SYSTEM_ID] = "source_system_id_exists"

            if not errors and system_id is not None:
                claims = _claims(self.hass)
                for claimed_id, owner in tuple(claims.system_ids.items()):
                    if owner == self.flow_id and claimed_id != system_id:
                        claims.system_ids.pop(claimed_id, None)
                claims.system_ids[system_id] = self.flow_id
                for claimed_source, owner in tuple(
                    claims.source_system_ids.items()
                ):
                    if owner == self.flow_id and claimed_source != (
                        entry.entry_id,
                        source_system_id,
                    ):
                        claims.source_system_ids.pop(claimed_source, None)
                claims.source_system_ids[
                    (entry.entry_id, source_system_id)
                ] = self.flow_id

            validated = False
            if not errors and runtime is not None:
                current_entry = self.hass.config_entries.async_get_known_entry(
                    entry.entry_id
                )
                current_subentry = current_entry.subentries.get(
                    subentry.subentry_id
                )
                if (
                    current_subentry is None
                    or current_subentry.unique_id != subentry.unique_id
                    or current_entry.unique_id != entry.unique_id
                    or int(current_entry.data[CONF_PROVIDER_REVISION])
                    != self._base_provider_revision
                ):
                    errors["base"] = "configuration_changed"
                else:
                    current_data = _json_copy(current_subentry.data)
                    current_revision = int(
                        current_data.get(CONF_CONFIG_REVISION, 0)
                    )
                    edited = {
                        CONF_SYSTEM_ID: system_id,
                        CONF_SOURCE_SYSTEM_ID: source_system_id,
                        CONF_SOURCE_EXPRESSIONS: _stored_expressions(runtime),
                        CONF_ENABLED: enabled,
                    }
                    if duplicate:
                        edited[CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = selected_source
                    merged, conflicts = _merge_system_data(
                        base=base, edited=edited, current=current_data
                    )
                    if conflicts:
                        errors["base"] = "configuration_changed"
                    else:
                        merged_runtime, merged_errors = _compile_expressions(
                            merged[CONF_SOURCE_EXPRESSIONS]
                        )
                        if merged_runtime is None:
                            errors.update(merged_errors)
                        else:
                            merged.setdefault(
                                CONF_REQUIRED_SOURCE_KEYS,
                                sorted(_required_source_keys(merged_runtime)),
                            )
                            base_was_validated = (
                                base.get(CONF_VALIDATED_HUB_UID)
                                == current_entry.unique_id
                                and base.get(CONF_VALIDATED_PROVIDER_REVISION)
                                == int(current_entry.data[CONF_PROVIDER_REVISION])
                            )
                            enabling = bool(edited[CONF_ENABLED]) and (
                                not bool(base[CONF_ENABLED])
                                or not base_was_validated
                            )
                            source_changed = (
                                edited[source_field] != base[source_field]
                            )
                            expressions_changed = (
                                merged[CONF_SOURCE_EXPRESSIONS]
                                != current_data[CONF_SOURCE_EXPRESSIONS]
                            )
                            requires_live_validation = (
                                enabling
                                or source_changed
                                or expressions_changed
                            )
                            if requires_live_validation:
                                validation = await _async_live_validate_system(
                                    self.hass,
                                    current_entry,
                                    str(merged[source_field]),
                                    merged_runtime,
                                    allow_offline_contract=False,
                                )
                                validated = validation.valid
                                if not validated:
                                    if validation.expression_errors:
                                        errors.update(
                                            validation.expression_errors
                                        )
                                    else:
                                        errors["base"] = (
                                            validation.base_error
                                            or "cannot_validate"
                                        )
                                else:
                                    merged[CONF_REQUIRED_SOURCE_KEYS] = list(
                                        validation.required_source_keys
                                    )
                                    if mqtt:
                                        merged[CONF_AVAILABLE_KEYS] = list(
                                            validation.available_source_keys
                                        )
                            else:
                                validated = True

                        if not errors:
                            latest = self.hass.config_entries.async_get_known_entry(
                                current_entry.entry_id
                            )
                            latest_subentry = latest.subentries.get(
                                current_subentry.subentry_id
                            )
                            if (
                                latest_subentry is None
                                or latest_subentry.unique_id
                                != current_subentry.unique_id
                                or int(
                                    latest_subentry.data.get(
                                        CONF_CONFIG_REVISION, 0
                                    )
                                )
                                != current_revision
                                or int(latest.data[CONF_PROVIDER_REVISION])
                                != self._base_provider_revision
                            ):
                                errors["base"] = "configuration_changed"
                            elif _source_system_id_exists(
                                latest,
                                str(merged[CONF_SOURCE_SYSTEM_ID]),
                                exclude_subentry_id=latest_subentry.subentry_id,
                            ) or _source_system_id_is_claimed(
                                self.hass,
                                latest.entry_id,
                                str(merged[CONF_SOURCE_SYSTEM_ID]),
                                self.flow_id,
                            ):
                                errors[
                                    CONF_SOURCE_SYSTEM_ID
                                ] = "source_system_id_exists"
                            elif _system_id_exists(
                                self.hass,
                                str(merged[CONF_SYSTEM_ID]),
                                self.flow_id,
                                exclude_subentry_id=latest_subentry.subentry_id,
                            ):
                                errors[CONF_SYSTEM_ID] = "system_id_exists"
                            else:
                                if validated:
                                    merged[CONF_VALIDATED_HUB_UID] = latest.unique_id
                                    merged[
                                        CONF_VALIDATED_PROVIDER_REVISION
                                    ] = int(
                                        latest.data[CONF_PROVIDER_REVISION]
                                    )
                                if merged == current_data:
                                    if not latest.update_listeners:
                                        self.hass.config_entries.async_schedule_reload(
                                            latest.entry_id
                                        )
                                    return self.async_abort(
                                        reason="reconfigure_successful"
                                    )
                                merged[CONF_CONFIG_REVISION] = current_revision + 1
                                self.hass.config_entries.async_update_subentry(
                                    latest,
                                    latest_subentry,
                                    data=merged,
                                    title=str(merged[CONF_SYSTEM_ID]),
                                )
                                if not latest.update_listeners:
                                    self.hass.config_entries.async_schedule_reload(
                                        latest.entry_id
                                    )
                                return self.async_abort(
                                    reason="reconfigure_successful"
                                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_system_schema(
                system_id=display_system_id,
                source_system_id=selected_source,
                source_expressions=expressions,
                discovered_systems=source_options,
                enabled=enabled,
                source_field=source_field,
                manual_source=mqtt,
            ),
            errors=errors,
            description_placeholders={
                "system_uid": str(subentry.unique_id),
            },
        )

    @callback
    def async_remove(self) -> None:
        """Release pending claims after subentry commit or cancellation."""
        _claims(self.hass).release(self.flow_id)


class DuplicateSystemSubentryFlowHandler(SystemSubentryFlowHandler):
    """Link one removable local alias to a discovered provider system."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the local duplicate ID and its communication target."""
        entry = self._get_entry()
        discovery_revision = int(entry.data[CONF_PROVIDER_REVISION])
        try:
            communication_systems = (
                await self._async_discover_communication_systems(entry)
            )
            all_discovered = await self._async_discover_systems(entry)
        except ProviderError as err:
            return self.async_abort(reason=_provider_error_key(err))
        except Exception:
            _LOGGER.exception(
                "Unexpected provider discovery error while adding a duplicate system"
            )
            return self.async_abort(reason="unknown")

        current = self.hass.config_entries.async_get_known_entry(entry.entry_id)
        if int(current.data[CONF_PROVIDER_REVISION]) != discovery_revision:
            return self.async_abort(reason="configuration_changed")
        self._base_provider_revision = discovery_revision
        if not communication_systems:
            return self.async_abort(reason="no_communication_systems")

        suggested = user_input or {}
        duplicate_source_system_id = str(
            suggested.get(CONF_SOURCE_SYSTEM_ID, "")
        ).strip()
        communication_source_system_id = str(
            suggested.get(
                CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
                communication_systems[0],
            )
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            local_id = _configured_opaque_id(duplicate_source_system_id)
            if local_id is None:
                errors[CONF_SOURCE_SYSTEM_ID] = "invalid_duplicate_source_system"
            elif (
                local_id in all_discovered
                or _source_system_id_exists(entry, local_id)
                or _source_system_id_is_claimed(
                    self.hass,
                    entry.entry_id,
                    local_id,
                    self.flow_id,
                )
            ):
                errors[CONF_SOURCE_SYSTEM_ID] = "source_system_id_exists"

            if communication_source_system_id not in communication_systems:
                errors[CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = (
                    "invalid_source_system"
                )
            if (
                local_id is not None
                and local_id == communication_source_system_id
            ):
                errors[CONF_SOURCE_SYSTEM_ID] = "duplicate_source_matches_original"

            if not errors and local_id is not None:
                self._selected_source_system_id = local_id
                self._selected_communication_source_system_id = (
                    communication_source_system_id
                )
                _claims(self.hass).source_system_ids[
                    (entry.entry_id, local_id)
                ] = self.flow_id
                return await self.async_step_details()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SOURCE_SYSTEM_ID,
                        default=duplicate_source_system_id,
                    ): str,
                    vol.Required(
                        CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
                        default=communication_source_system_id,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(communication_systems),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_duplicate_system(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start a duplicate-system flow when HA uses the subtype as step ID."""
        return await self.async_step_user(user_input)


def _merge_value(base: Any, edited: Any, current: Any) -> tuple[Any, bool]:
    """Three-way merge one value and flag a same-field conflict."""
    if current == base or current == edited:
        return edited, False
    if edited == base:
        return current, False
    return current, True


def _merge_system_data(
    *,
    base: Mapping[str, Any],
    edited: Mapping[str, Any],
    current: Mapping[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    """Three-way merge system fields, expressions independently per key."""
    result = _json_copy(current)
    conflicts: set[str] = set()
    merge_keys = [CONF_SYSTEM_ID, CONF_SOURCE_SYSTEM_ID, CONF_ENABLED]
    if CONF_COMMUNICATION_SOURCE_SYSTEM_ID in base:
        merge_keys.append(CONF_COMMUNICATION_SOURCE_SYSTEM_ID)
    for key in merge_keys:
        result[key], conflict = _merge_value(
            base[key], edited[key], current[key]
        )
        if conflict:
            conflicts.add(key)

    merged_expressions = dict(current[CONF_SOURCE_EXPRESSIONS])
    for key in base[CONF_SOURCE_EXPRESSIONS]:
        merged_expressions[key], conflict = _merge_value(
            base[CONF_SOURCE_EXPRESSIONS][key],
            edited[CONF_SOURCE_EXPRESSIONS][key],
            current[CONF_SOURCE_EXPRESSIONS][key],
        )
        if conflict:
            conflicts.add(f"{CONF_SOURCE_EXPRESSIONS}.{key}")
    result[CONF_SOURCE_EXPRESSIONS] = merged_expressions
    return result, conflicts
