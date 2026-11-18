"""Value-agnostic provider observation and freshness timestamps."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from types import MappingProxyType
from typing import Any


def utcnow() -> datetime:
    """Return one aware UTC timestamp; isolated for deterministic tests."""
    return datetime.now(timezone.utc)


def _raw_equal(left: Any, right: Any) -> bool:
    """Compare opaque provider values without Python's cross-type coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and math.isnan(left):
        return math.isnan(right)
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _raw_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _raw_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


@dataclass(frozen=True, slots=True)
class _ObservedValue:
    present: bool
    value: Any
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderStatusSnapshot:
    """One immutable raw provider snapshot plus local observation times."""

    values: Mapping[str, Any]
    last_report: datetime | None
    last_update: datetime | None

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


class SourceObservation:
    """Cache raw states and their local report/change timestamps."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._observed: dict[str, _ObservedValue] = {}
        self._last_report: datetime | None = None

    @staticmethod
    def _validated_time(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("Observation time must be an aware datetime")
        return value.astimezone(timezone.utc)

    def observe_event(self, key: str, value: Any, at: datetime) -> None:
        """Apply one pushed key/value report."""
        moment = self._validated_time(at)
        copied = deepcopy(value)
        previous = self._observed.get(key)
        changed = (
            previous is None
            or not previous.present
            or not _raw_equal(previous.value, copied)
        )
        if changed:
            self._observed[key] = _ObservedValue(True, copied, moment)
        self._values[key] = copied
        self._last_report = moment

    def observe_report(self, at: datetime) -> None:
        """Record a received report that yielded no accepted state value."""
        self._last_report = self._validated_time(at)

    def observe_snapshot(self, values: Mapping[str, Any], at: datetime) -> None:
        """Apply one complete authoritative polling snapshot."""
        moment = self._validated_time(at)
        copied = deepcopy(dict(values))
        previous_keys = set(self._values)
        current_keys = set(copied)
        for key in previous_keys | current_keys:
            previous = self._observed.get(key)
            if key not in copied:
                if previous is None or previous.present:
                    self._observed[key] = _ObservedValue(False, None, moment)
                continue
            value = copied[key]
            changed = (
                previous is None
                or not previous.present
                or not _raw_equal(previous.value, value)
            )
            if changed:
                self._observed[key] = _ObservedValue(True, value, moment)
        self._values = copied
        self._last_report = moment

    def snapshot(self, referenced_keys: Collection[str]) -> ProviderStatusSnapshot:
        """Return defensive values and timestamps for one expression contract."""
        updates = [
            observed.changed_at
            for key in referenced_keys
            if (observed := self._observed.get(key)) is not None
        ]
        return ProviderStatusSnapshot(
            MappingProxyType(deepcopy(self._values)),
            self._last_report,
            max(updates) if updates else None,
        )
