"""Constants for the integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "solesta"
DATA_ARCHIVE_MANAGER = f"{DOMAIN}_archive_manager"

# Hub configuration.
CONF_HUB_UID = "hub_uid"
CONF_KIND = "kind"
CONF_PROTOCOL = "protocol"
CONF_CONNECTION = "connection"
CONF_BASE_URL = "base_url"
CONF_USER_ID = "userid"
CONF_PASSWORD = "password"
CONF_PROVIDER_ID = "provider_id"
CONF_PROVIDER_REVISION = "provider_revision"
CONF_CONFIG_REVISION = "config_revision"
CONF_AVAILABLE_KEYS = "available_keys"
CONF_PRESET_ID = "preset_id"
CONF_PRESET_REVISION = "preset_revision"

HUB_KIND_PROVIDER = "provider"
PROTOCOL_WEB_API = "web_api"

# System ConfigSubentry configuration.
SUBENTRY_TYPE_SYSTEM = "system"
SUBENTRY_TYPE_DUPLICATE_SYSTEM = "duplicate_system"
SYSTEM_SUBENTRY_TYPES = frozenset(
    {SUBENTRY_TYPE_SYSTEM, SUBENTRY_TYPE_DUPLICATE_SYSTEM}
)
CONF_SYSTEM_UID = "system_uid"
CONF_SYSTEM_ID = "system_id"
CONF_SOURCE_SYSTEM_ID = "source_system_id"
CONF_COMMUNICATION_SOURCE_SYSTEM_ID = "communication_source_system_id"
CONF_SOURCE_EXPRESSIONS = "source_expressions"
CONF_REQUIRED_SOURCE_KEYS = "required_source_keys"
CONF_EXPRESSION_SCHEMA_VERSION = "expression_schema_version"
CONF_VALIDATED_HUB_UID = "validated_hub_uid"
CONF_VALIDATED_PROVIDER_REVISION = "validated_provider_revision"
CONF_ENABLED = "enabled"

EXPRESSION_SCHEMA_VERSION = 4

# Runtime data keys.
DATA_PROVIDER = "provider"
DATA_SYSTEMS = "systems"
DATA_COORDINATORS = "coordinators"
DATA_RUNTIME_CONFIGURATIONS = "runtime_configurations"
DATA_ENTRY_LOCK = "entry_lock"
DATA_HUB_RUNTIME = "hub_runtime"

UPDATE_INTERVAL_ENTITY_KEY = "update_interval"
WEEKLY_ARCHIVE_ENTITY_KEY = "weekly_archive"
ARCHIVE_LAST_SUCCESS_ENTITY_KEY = "archive_last_success"
ARCHIVE_STATUS_ENTITY_KEY = "archive_status"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
HTTP_REQUEST_TIMEOUT = 30

# Solesta-specific preset metadata. Provider/runtime abstractions do not depend
# on these product defaults.
DEFAULT_MANUFACTURER = "Solesta"
