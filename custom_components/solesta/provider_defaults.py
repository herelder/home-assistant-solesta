"""Generated provider defaults; do not edit manually.

Source: tools/sources/ProviderDefaults.xlsx
Source SHA-256: e848ec508f4215d7f06a21594f0016eeb1dc8086043fd17ff7f089a3f68dc358
Generator: tools/generate_provider_defaults.py
Generator SHA-256: fa1a353d23fdeecf54b0e66d5b088457229b251f93b91cea6e1c4ee052c7293e
Preset revision: 3
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final


def _freeze(value: Any) -> Any:
    """Return an immutable tree built only from validated generated data."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


SOLESTA_WEB_API_DEFAULT: Final[Mapping[str, Any]] = _freeze(
    {
        "schema_version": 1,
        "preset_id": "solesta",
        "preset_revision": 3,
        "protocol": "web_api",
        "base_url": "https://dashboard.solesta.nl",
        "total_timeout_seconds": 30,
        "available_keys": [],
        "flows": {
            "connect_flow": {
                "bindings": [
                    "password",
                    "userid",
                ],
                "steps": [
                    {
                        "op": "request",
                        "method": "POST",
                        "path_template": "/api/auth/login",
                        "json": {
                            "email": "{userid}",
                            "password": "{password}",
                        },
                        "response": {
                            "success_statuses": [
                                200,
                            ],
                            "extract": [],
                            "assert_equals": {
                                "success": True,
                            },
                        },
                    },
                ],
            },
            "disconnect_flow": {
                "bindings": [],
                "steps": [
                    {
                        "op": "request",
                        "method": "POST",
                        "path_template": "/api/auth/logout",
                        "response": {
                            "success_statuses": [
                                200,
                                204,
                            ],
                            "extract": [],
                        },
                    },
                ],
            },
            "profile_flow": {
                "bindings": [],
                "steps": [
                    {
                        "op": "request",
                        "method": "GET",
                        "path_template": "/api/users/me",
                        "response": {
                            "success_statuses": [
                                200,
                            ],
                            "extract": [
                                "*",
                            ],
                        },
                    },
                ],
            },
            "systems_flow": {
                "bindings": [],
                "steps": [
                    {
                        "op": "request",
                        "method": "GET",
                        "path_template": "/api/users/me",
                        "response": {
                            "success_statuses": [
                                200,
                            ],
                            "extract": [
                                "coupled_systems",
                            ],
                        },
                    },
                ],
            },
            "system_status_flow": {
                "bindings": [
                    "source_system_id",
                ],
                "steps": [
                    {
                        "op": "request",
                        "method": "GET",
                        "path_template": "/api/systems/{source_system_id}/live",
                        "response": {
                            "success_statuses": [
                                200,
                            ],
                            "extract": [
                                "*",
                            ],
                        },
                    },
                ],
            },
        },
    }
)


PROVIDER_DEFAULTS: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType({
    "solesta": SOLESTA_WEB_API_DEFAULT,
})
