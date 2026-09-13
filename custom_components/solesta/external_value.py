"""Generic value contract for state supplied outside expression evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExternalEntityValue:
    """Value and attributes supplied outside provider expression evaluation."""

    value: Any
    attributes: Mapping[str, Any]
