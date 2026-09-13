"""Exact validation shared by runtime Number evaluation and HA writes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from numbers import Real
from typing import Any

from .description import Description


class NumberValidationError(ValueError):
    """A Number value or its generated metadata is invalid."""

    def __init__(
        self,
        message: str,
        *,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.translation_key = translation_key
        self.translation_placeholders = translation_placeholders or {}


def validate_number_value(
    value: Any,
    description: Description,
) -> tuple[float, str]:
    """Return a finite float and literal after exact range and step checks."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise NumberValidationError(
            "Number value must be a real number",
            translation_key="number_value_not_real",
        )

    numeric = float(value)
    if not math.isfinite(numeric):
        raise NumberValidationError(
            "Number value must be finite",
            translation_key="number_value_not_finite",
        )

    try:
        decimal_value = Decimal(str(value))
        minimum = (
            Decimal(str(description.native_min_value))
            if description.native_min_value is not None
            else None
        )
        maximum = (
            Decimal(str(description.native_max_value))
            if description.native_max_value is not None
            else None
        )
        step = (
            Decimal(str(description.native_step))
            if description.native_step is not None
            else None
        )
    except (InvalidOperation, ValueError) as err:
        raise NumberValidationError(
            "Number metadata is invalid",
            translation_key="number_metadata_invalid",
        ) from err

    if minimum is not None and decimal_value < minimum:
        raise NumberValidationError(
            "Number value is below its minimum",
            translation_key="number_value_below_minimum",
            translation_placeholders={
                "value": str(decimal_value),
                "minimum": str(minimum),
            },
        )
    if maximum is not None and decimal_value > maximum:
        raise NumberValidationError(
            "Number value is above its maximum",
            translation_key="number_value_above_maximum",
            translation_placeholders={
                "value": str(decimal_value),
                "maximum": str(maximum),
            },
        )
    if step is not None:
        if step <= 0:
            raise NumberValidationError(
                "Number step must be positive",
                translation_key="number_step_not_positive",
            )
        basis = minimum if minimum is not None else Decimal(0)
        if (decimal_value - basis) % step != 0:
            raise NumberValidationError(
                "Number value does not match its step",
                translation_key="number_value_step_mismatch",
                translation_placeholders={
                    "value": str(decimal_value),
                    "step": str(step),
                },
            )

    return numeric, repr(numeric)
