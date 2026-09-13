"""Pure helpers shared by configuration forms."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_source_expressions(
    keys: Iterable[str],
    user_input: Mapping[str, Any],
    defaults: Mapping[str, str],
) -> dict[str, str]:
    """Use the factory default for every omitted, empty or whitespace value."""
    result: dict[str, str] = {}
    for key in keys:
        raw = user_input.get(key)
        value = "" if raw is None else str(raw).strip()
        result[key] = value or defaults[key]
    return result
