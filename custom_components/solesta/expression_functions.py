"""Pure functions exposed to source expressions."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from numbers import Real
from typing import Any


_MAX_JOIN_ITEMS = 1024
_MAX_JOIN_CHARACTERS = 64 * 1024
_MAX_ABS_ARITHMETIC_RESULT = 1e100
_MAX_ROUND_DIGITS = 15


def to_number(value: Any) -> float | None:
    """Convert a provider value to a finite number, preserving null."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("cannot convert value to number")
    numeric = (
        float(value)
        if isinstance(value, Real)
        else float(str(value).strip().replace(",", "."))
    )
    if not math.isfinite(numeric):
        raise ValueError("number must be finite")
    return numeric


def join_lines(*values: Any) -> str:
    """Join scalar values and one flat list/tuple into readable lines.

    Provider alert payloads may be either a scalar value or one flat
    ``list``/``tuple``. Empty values are omitted. Nested sequences are rejected
    deliberately: accepting those recursively would make malformed provider
    payloads look valid and would leave the public alert contract ambiguous.
    Mapping elements remain supported and are converted individually, which
    preserves the useful representation of structured Solesta alerts.
    """
    lines: list[str] = []
    item_count = 0
    character_count = 0

    for value in values:
        items = value if isinstance(value, (list, tuple)) else (value,)
        for item in items:
            item_count += 1
            if item_count > _MAX_JOIN_ITEMS:
                raise ValueError("join_lines input contains too many items")
            if isinstance(item, (list, tuple)):
                raise TypeError("join_lines does not accept nested sequences")
            if item is None:
                continue
            text = str(item)
            if not text.strip():
                continue
            character_count += len(text) + bool(lines)
            if character_count > _MAX_JOIN_CHARACTERS:
                raise ValueError("join_lines result is too long")
            lines.append(text)

    return "\n".join(lines)


def validate_delay_zone_borders(*border_values: Any) -> tuple[int, ...]:
    """Return positive, strictly increasing whole-second zone maxima."""
    if not border_values:
        raise ValueError("delay_zone requires at least one border value")

    borders: list[int] = []
    previous = 0
    for value in border_values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("delay_zone borders must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0 or not numeric.is_integer():
            raise ValueError(
                "delay_zone borders must be positive whole seconds"
            )
        border = int(numeric)
        if border <= previous:
            raise ValueError(
                "delay_zone borders must be in strictly increasing order"
            )
        borders.append(border)
        previous = border
    return tuple(borders)


def _utc_now() -> datetime:
    """Return the current aware UTC time; isolated for deterministic tests."""
    return datetime.now(timezone.utc)


def _timestamp_seconds(value: Any) -> float:
    """Normalize the timestamp forms supported by the timestamp sensor."""
    if isinstance(value, bool):
        raise TypeError("last_report must be a timestamp")
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if not math.isfinite(timestamp):
            raise ValueError("last_report timestamp must be finite")
        return timestamp
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("last_report timestamp cannot be empty")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        raise TypeError("last_report must be a timestamp")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def delay_zone(last_report: Any, *border_values: Any) -> str | None:
    """Return the exact text value for the report-delay sensor.

    Every border is the inclusive maximum of its zone. The first zone starts
    at zero; subsequent zones start one whole second after the previous
    maximum. Small future clock skew is treated as zero delay. A report older
    than the final zone is returned as a normalized UTC ISO timestamp.
    """
    borders = validate_delay_zone_borders(*border_values)
    if last_report is None:
        return None

    report_timestamp = _timestamp_seconds(last_report)
    elapsed = max(0.0, _utc_now().timestamp() - report_timestamp)
    lower = 0
    for border in borders:
        if elapsed <= border:
            return f"[{lower},{border}]"
        lower = border + 1
    return datetime.fromtimestamp(report_timestamp, timezone.utc).isoformat()


def _finite_number(value: Any) -> float:
    """Return a bounded arithmetic operand without implicit string behavior."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("arithmetic operands must be real numbers")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("arithmetic operands must be finite")
    return numeric


def _bounded_result(value: float) -> float:
    if not math.isfinite(value) or abs(value) > _MAX_ABS_ARITHMETIC_RESULT:
        raise OverflowError("arithmetic result exceeds its safety limit")
    return value


def _safe_add(left: Any, right: Any) -> float:
    return _bounded_result(_finite_number(left) + _finite_number(right))


def _safe_sub(left: Any, right: Any) -> float:
    return _bounded_result(_finite_number(left) - _finite_number(right))


def _safe_mult(left: Any, right: Any) -> float:
    return _bounded_result(_finite_number(left) * _finite_number(right))


def _safe_div(left: Any, right: Any) -> float:
    divisor = _finite_number(right)
    if divisor == 0:
        raise ZeroDivisionError("division by zero")
    return _bounded_result(_finite_number(left) / divisor)


def _safe_mod(left: Any, right: Any) -> float:
    divisor = _finite_number(right)
    if divisor == 0:
        raise ZeroDivisionError("modulo by zero")
    return _bounded_result(_finite_number(left) % divisor)


def _safe_pos(value: Any) -> float:
    return _finite_number(value)


def _safe_neg(value: Any) -> float:
    return _bounded_result(-_finite_number(value))


def safe_round(value: Any, digits: int = 0) -> float:
    """Round a finite number with a small, explicit precision bound."""
    if isinstance(digits, bool) or not isinstance(digits, int):
        raise TypeError("round precision must be an integer")
    if not -_MAX_ROUND_DIGITS <= digits <= _MAX_ROUND_DIGITS:
        raise ValueError("round precision exceeds its safety limit")
    return _bounded_result(float(round(_finite_number(value), digits)))


EVALUATION_FUNCTIONS = {
    "delay_zone": delay_zone,
    "to_number": to_number,
    "round": safe_round,
    "join_lines": join_lines,
}

INTERNAL_EVALUATION_FUNCTIONS = {
    "__safe_add": _safe_add,
    "__safe_sub": _safe_sub,
    "__safe_mult": _safe_mult,
    "__safe_div": _safe_div,
    "__safe_mod": _safe_mod,
    "__safe_pos": _safe_pos,
    "__safe_neg": _safe_neg,
}
