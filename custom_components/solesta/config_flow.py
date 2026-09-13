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

from .configuration import default_source_expressions
from .const import (
    CONF_AVAILABLE_KEYS,
    CONF_BASE_URL,
    CONF_COMMUNICATION_SOURCE_SYSTEM_ID,
    CONF_CONFIG_REVISION,
    CONF_CONNECTION,
    CONF_ENABLED,
    CONF_EXPRESSION_SCHEMA_VERSION,
    CONF_KIND,
    CONF_PASSWORD,
    CONF_PROVIDER_ID,
    CONF_PROTOCOL,
    CONF_PROVIDER_REVISION,
    CONF_REQUIRED_SOURCE_KEYS,
    CONF_SOURCE_EXPRESSIONS,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
    CONF_USER_ID,
    CONF_VALIDATED_HUB_UID,
    CONF_VALIDATED_PROVIDER_REVISION,
    DOMAIN,
    EXPRESSION_SCHEMA_VERSION,
    HUB_KIND_PROVIDER,
    PROTOCOL_WEB_API,
    SYSTEM_SUBENTRY_TYPES,
    SUBENTRY_TYPE_DUPLICATE_SYSTEM,
    SUBENTRY_TYPE_SYSTEM,
)
from .description import EntityType
from .exceptions import (
    ProviderAuthenticationError,
    ProviderCommunicationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSystemError,
)
from .evaluator import EvaluationErrorCategory, evaluate_source_expressions
from .provider_defaults import SOLESTA_WEB_API_DEFAULT
from .runtime_configuration import RuntimeConfiguration, is_drop_expression
from .thetruth import DESCRIPTIONS
from .web_api import (
    WebApiProvider,
    canonicalize_base_url,
)

_LOGGER = logging.getLogger(__name__)
_FLOW_CLAIMS_DATA = f"{DOMAIN}_flow_claims"
_MAX_SYSTEM_ID_LENGTH = 64
_PROTOCOL_OPTIONS = (PROTOCOL_WEB_API,)
_CONFIG_ENTRY_VERSION = 1
_CONFIG_ENTRY_MINOR_VERSION = 1
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
    result: dict[str, str] = {}
    for subentry in entry.get_subentries_of_type(
        SUBENTRY_TYPE_DUPLICATE_SYSTEM
    ):
        local_id = subentry.data.get(CONF_SOURCE_SYSTEM_ID)
        communication_id = subentry.data.get(
            CONF_COMMUNICATION_SOURCE_SYSTEM_ID
        )
        if (
            isinstance(local_id, str)
            and local_id
            and isinstance(communication_id, str)
            and communication_id
        ):
            result[local_id] = communication_id
    return result


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


def _source_expressions(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Return a complete mapping, restoring factory defaults when blank."""
    defaults = default_source_expressions()
    result: dict[str, str] = {}
    for description in DESCRIPTIONS:
        raw = user_input.get(description.key)
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
    unavailable_systems: Collection[str] = (),
    enabled: bool | None = None,
) -> vol.Schema:
    """Build a create or reconfigure form for one system."""
    source_validator: Any = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=item,
                        label=(f"⚠ {item}" if item in unavailable_systems else item),
                    )
                    for item in discovered_systems
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        if discovered_systems
        else str
    )
    schema: dict[Any, Any] = {}
    if system_id is not None:
        schema[vol.Required(CONF_SYSTEM_ID, default=system_id)] = str
    schema[
        vol.Required(CONF_SOURCE_SYSTEM_ID, default=source_system_id)
    ] = source_validator
    if enabled is not None:
        schema[vol.Required(CONF_ENABLED, default=enabled)] = bool
    for description in DESCRIPTIONS:
        if (
            description.entity_type is EntityType.SWITCH
            and not is_drop_expression(source_expressions[description.key])
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
            or is_drop_expression(source_expressions[description.key])
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
            and not is_drop_expression(source_expressions[description.key])
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
            or is_drop_expression(source_expressions[description.key])
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


def _compile_expressions(
    expressions: Mapping[str, str],
) -> tuple[RuntimeConfiguration | None, dict[str, str]]:
    """Compile a complete mapping and locate expression-specific errors."""
    try:
        return RuntimeConfiguration.compile(expressions), {}
    except Exception:
        pass

    defaults = default_source_expressions()
    invalid: dict[str, str] = {}
    for description in DESCRIPTIONS:
        key = description.key
        candidate = dict(defaults)
        candidate[key] = expressions[key]
        try:
            RuntimeConfiguration.compile(candidate)
        except Exception:
            invalid[key] = "invalid_source_expression"
    return None, invalid or {"base": "invalid_source_expressions"}


def _required_source_keys(runtime: RuntimeConfiguration) -> frozenset[str]:
    """Return compiler-derived provider keys across runtime API revisions."""
    value = getattr(runtime, "required_source_keys", None)
    if value is None:
        value = getattr(runtime, "source_keys")
    return frozenset(str(key) for key in value)


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
) -> WebApiProvider:
    """Create the provider selected by validated hub data."""
    if data.get(CONF_PROTOCOL) != PROTOCOL_WEB_API:
        raise ProviderConfigurationError("Unsupported provider protocol")
    return WebApiProvider(
        hass,
        base_url=str(data[CONF_BASE_URL]),
        connection=data[CONF_CONNECTION],
        preset=SOLESTA_WEB_API_DEFAULT,
        provider_id=_entry_provider_id(data),
        duplicate_systems=duplicate_systems,
        configured_available_keys=data.get(CONF_AVAILABLE_KEYS, ()),
    )


async def _async_close_temporary_provider(provider: WebApiProvider) -> None:
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
) -> WebApiProvider:
    """Open, connect and initialize one temporary provider lifecycle."""
    provider = _provider_from_data(
        hass, data, duplicate_systems=duplicate_systems
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


async def _async_validate_hub_candidate(
    hass: HomeAssistant,
    candidate: Mapping[str, Any],
    *,
    linked_entry: ConfigEntry | None = None,
) -> dict[str, Any]:
    """Validate a provider and every existing linked-system contract."""
    provider = await _async_initialize_provider(hass, candidate)
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
                runtime, expression_errors = _compile_expressions(
                    source_expressions
                )
                if runtime is None or expression_errors:
                    invalid.append(system_id)
                    continue
                try:
                    status = await provider.get_system_status(
                        _communication_source_system_id(subentry),
                        _required_source_keys(runtime),
                    )
                    if _required_source_keys(runtime) - {
                        str(key) for key in status
                    }:
                        invalid.append(system_id)
                        continue
                    result = evaluate_source_expressions(
                        runtime.compiled_source_expressions,
                        status,
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
        return _json_copy(candidate)
    finally:
        await _async_close_temporary_provider(provider)


def _publish_provider_candidate(
    hass: HomeAssistant,
    current: ConfigEntry,
    candidate: Mapping[str, Any],
) -> bool:
    """Publish one validated provider change and preserve active systems."""
    next_provider_revision = int(current.data[CONF_PROVIDER_REVISION]) + 1
    next_config_revision = int(current.data[CONF_CONFIG_REVISION]) + 1

    for subentry in _system_subentries(current):
        subentry_data = _json_copy(subentry.data)
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
        title=f"Web API – {stored[CONF_PROVIDER_ID]}",
        version=_CONFIG_ENTRY_VERSION,
        minor_version=_CONFIG_ENTRY_MINOR_VERSION,
    )


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
    provider: WebApiProvider | None = None
    try:
        provider = await _async_initialize_provider(
            hass,
            entry.data,
            duplicate_systems=_duplicate_systems_from_entry(entry),
        )
        status = await provider.get_system_status(source_system_id, required)
        if required - {str(key) for key in status}:
            return _LiveValidationResult(False, "source_keys_unavailable")
        result = evaluate_source_expressions(
            runtime.compiled_source_expressions,
            status,
        )
        evaluated = result.values
        if set(evaluated) != set(runtime.evaluated_keys):
            return _LiveValidationResult(False, "invalid_source_values")
        if result.errors:
            expression_errors = {
                key: _EVALUATION_FORM_ERRORS[error.category]
                for key, error in result.errors.items()
                if error.category in _EVALUATION_FORM_ERRORS
            }
            if len(expression_errors) != len(result.errors):
                return _LiveValidationResult(False, "invalid_source_values")
            return _LiveValidationResult(
                False,
                expression_errors=expression_errors,
            )
        return _LiveValidationResult(True)
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
        """Start configuration for the currently supported provider type."""
        del user_input
        hub_uid = self._ensure_new_hub_uid()
        await self._async_bind_unique_id(hub_uid, mismatch=False)
        self._protocol = _PROTOCOL_OPTIONS[0]
        return await self.async_step_web_api()

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
                    _claims(self.hass).provider_ids[provider_id] = self.flow_id
                    return self.async_create_entry(
                        title=f"Web API – {provider_id}",
                        data=candidate,
                    )

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Atomically replace connection data while preserving all systems."""
        entry = self._get_reconfigure_entry()
        if entry.unique_id is None:
            return self.async_abort(reason="invalid_hub_identity")
        await self._async_bind_unique_id(entry.unique_id, mismatch=True)
        if self._base_config_revision is None:
            self._base_config_revision = int(
                entry.data.get(CONF_CONFIG_REVISION, 0)
            )
            self._base_system_contract = _system_contract_snapshot(entry)
        connection = entry.data[CONF_CONNECTION]
        default_base_url, preset, _ = _preset_parts()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        suggested = user_input or {}

        if user_input is not None:
            password = str(user_input.get(CONF_PASSWORD, ""))
            if not password:
                password = str(connection[CONF_PASSWORD])
            try:
                protocol = (
                    _PROTOCOL_OPTIONS[0]
                    if len(_PROTOCOL_OPTIONS) == 1
                    else str(user_input[CONF_PROTOCOL])
                )
                candidate = _hub_candidate(
                    protocol=protocol,
                    base_url=default_base_url,
                    user_id=user_input[CONF_USER_ID],
                    password=password,
                    preset=preset,
                    # A non-empty saved override remains authoritative. An
                    # empty list retains the AUTO-discovery meaning.
                    configured_available_keys=entry.data.get(
                        CONF_AVAILABLE_KEYS, ()
                    ),
                    provider_revision=int(entry.data[CONF_PROVIDER_REVISION]),
                    config_revision=int(entry.data[CONF_CONFIG_REVISION]),
                    provider_id=_entry_provider_id(entry),
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
                    _LOGGER.exception("Unexpected hub reconfiguration error")
                errors["base"] = _provider_error_key(err)
            else:
                current = self.hass.config_entries.async_get_known_entry(
                    entry.entry_id
                )
                if (
                    current.unique_id != entry.unique_id
                    or current.data.get(CONF_KIND) != HUB_KIND_PROVIDER
                    or int(current.data.get(CONF_CONFIG_REVISION, 0))
                    != self._base_config_revision
                    or _system_contract_snapshot(current)
                    != self._base_system_contract
                ):
                    errors["base"] = "configuration_changed"
                elif _provider_id_exists(
                    self.hass,
                    _entry_provider_id(current),
                    self.flow_id,
                    exclude_entry_id=current.entry_id,
                ):
                    errors["base"] = "provider_id_exists"
                else:
                    if (
                        candidate == _json_copy(current.data)
                        and current.version == _CONFIG_ENTRY_VERSION
                        and current.minor_version
                        == _CONFIG_ENTRY_MINOR_VERSION
                    ):
                        if not current.update_listeners:
                            self.hass.config_entries.async_schedule_reload(
                                current.entry_id
                            )
                        return self.async_abort(
                            reason="reconfigure_successful"
                        )
                    changed = _publish_provider_candidate(
                        self.hass, current, candidate
                    )
                    if not changed or not current.update_listeners:
                        self.hass.config_entries.async_schedule_reload(
                            current.entry_id
                        )
                    return self.async_abort(reason="reconfigure_successful")

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_USER_ID,
                default=str(
                    suggested.get(CONF_USER_ID, connection[CONF_USER_ID])
                ),
            ): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
        }
        if len(_PROTOCOL_OPTIONS) > 1:
            schema[
                vol.Required(
                    CONF_PROTOCOL,
                    default=str(
                        suggested.get(CONF_PROTOCOL, entry.data[CONF_PROTOCOL])
                    ),
                )
            ] = vol.In(_PROTOCOL_OPTIONS)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema),
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
        """Validate a replacement password against every linked system."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                candidate = _hub_candidate(
                    protocol=str(entry.data[CONF_PROTOCOL]),
                    base_url=entry.data[CONF_BASE_URL],
                    user_id=entry.data[CONF_CONNECTION][CONF_USER_ID],
                    password=str(user_input[CONF_PASSWORD]),
                    preset=SOLESTA_WEB_API_DEFAULT,
                    configured_available_keys=entry.data.get(
                        CONF_AVAILABLE_KEYS, ()
                    ),
                    provider_revision=int(
                        entry.data[CONF_PROVIDER_REVISION]
                    ),
                    config_revision=int(entry.data[CONF_CONFIG_REVISION]),
                    provider_id=_entry_provider_id(entry),
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
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
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
        provider: WebApiProvider | None = None
        try:
            provider = await _async_initialize_provider(
                self.hass,
                entry.data,
                duplicate_systems=_duplicate_systems_from_entry(entry),
            )
            self._discovered_systems = tuple(
                sorted(
                    {
                        str(item).strip()
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
        proposed_system_id = cv.slugify(source_system_id)
        display_system_id = str(
            (user_input or {}).get(CONF_SYSTEM_ID, proposed_system_id)
        ).strip()
        expressions = (
            _source_expressions(user_input) if user_input is not None else defaults
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
                # Creation is deliberately disabled. Live validation is useful
                # for stamps but a temporary failure never blocks persistence.
                validation = await _async_live_validate_system(
                    self.hass,
                    entry,
                    (
                        self._selected_communication_source_system_id
                        or source_system_id
                    ),
                    runtime,
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
                else:
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
                                _required_source_keys(runtime)
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
        discovery_error: str | None = None
        try:
            discovered = await self._async_discover_systems(entry)
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
            if not _source_system_id_exists(
                entry,
                source_system_id,
                exclude_subentry_id=subentry.subentry_id,
            )
        )
        errors: dict[str, str] = {}
        stored_source_system_id = str(base[CONF_SOURCE_SYSTEM_ID])
        source_options = (
            (stored_source_system_id,)
            if subentry.subentry_type == SUBENTRY_TYPE_DUPLICATE_SYSTEM
            else (
                stored_source_system_id,
                *(
                    item
                    for item in available_sources
                    if item != stored_source_system_id
                ),
            )
        )
        unavailable_sources = (
            {stored_source_system_id}
            if stored_source_system_id not in discovered
            else set()
        )
        display_system_id = str(
            (user_input or {}).get(CONF_SYSTEM_ID, base[CONF_SYSTEM_ID])
        ).strip()
        source_system_id = str(
            (user_input or {}).get(
                CONF_SOURCE_SYSTEM_ID, stored_source_system_id
            )
        ).strip()
        expressions = (
            _source_expressions(user_input)
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
            source_changed = source_system_id != stored_source_system_id
            if source_system_id not in source_options or (
                source_changed
                and (discovery_error is not None or source_system_id not in discovered)
            ):
                errors[CONF_SOURCE_SYSTEM_ID] = "invalid_source_system"
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
                            merged[CONF_REQUIRED_SOURCE_KEYS] = sorted(
                                _required_source_keys(merged_runtime)
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
                                edited[CONF_SOURCE_SYSTEM_ID]
                                != base[CONF_SOURCE_SYSTEM_ID]
                            )
                            requires_live_validation = enabling or source_changed
                            if requires_live_validation:
                                validation = await _async_live_validate_system(
                                    self.hass,
                                    current_entry,
                                    str(merged[CONF_SOURCE_SYSTEM_ID]),
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
                source_system_id=source_system_id,
                source_expressions=expressions,
                discovered_systems=source_options,
                unavailable_systems=unavailable_sources,
                enabled=enabled,
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
        ).strip()
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
    for key in (CONF_SYSTEM_ID, CONF_SOURCE_SYSTEM_ID, CONF_ENABLED):
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
