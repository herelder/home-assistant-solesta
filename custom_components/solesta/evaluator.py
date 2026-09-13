"""Evaluate compiled source expressions against provider status data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import math
from numbers import Real
from types import MappingProxyType
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass

from .compile import CompiledSourceExpressions
from .description import EntityType
from .expression_functions import (
    EVALUATION_FUNCTIONS,
    INTERNAL_EVALUATION_FUNCTIONS,
    delay_zone,
    join_lines,
    to_number,
)
from .number_validation import NumberValidationError, validate_number_value
from .thetruth import DESCRIPTIONS

__all__ = (
    "delay_zone",
    "EvaluationError",
    "EvaluationErrorCategory",
    "EvaluationResult",
    "evaluate_source_expressions",
    "join_lines",
    "to_number",
)
_DESCRIPTIONS = {description.key: description for description in DESCRIPTIONS}


class EvaluationErrorCategory(StrEnum):
    """Stable, non-secret reason why one entity expression is invalid."""

    MISSING_SOURCE = "missing_source"
    DEPENDENCY_FAILED = "dependency_failed"
    DIVISION_BY_ZERO = "division_by_zero"
    TYPE_ERROR = "type_error"
    DOMAIN_ERROR = "domain_error"
    EVALUATION_ERROR = "evaluation_error"


@dataclass(frozen=True, slots=True)
class EvaluationError:
    """One classified expression failure without source-value disclosure."""

    category: EvaluationErrorCategory
    message: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Immutable values and per-entity failures from one evaluation pass."""

    values: Mapping[str, Any]
    errors: Mapping[str, EvaluationError]


class _InvalidEntityValue(ValueError):
    def __init__(
        self,
        category: EvaluationErrorCategory,
        message: str,
    ) -> None:
        super().__init__(message)
        self.category = category


def _normalized_timestamp(value: Any) -> datetime:
    if isinstance(value, bool):
        raise _InvalidEntityValue(
            EvaluationErrorCategory.TYPE_ERROR,
            "timestamp result must be a datetime, number, or ISO string",
        )
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, Real):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError("timestamp must be finite")
            parsed = datetime.fromtimestamp(numeric, tz=timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            raise TypeError("unsupported timestamp type")
    except TypeError as err:
        raise _InvalidEntityValue(
            EvaluationErrorCategory.TYPE_ERROR,
            "timestamp result has an invalid type",
        ) from err
    except (OSError, OverflowError, ValueError) as err:
        raise _InvalidEntityValue(
            EvaluationErrorCategory.DOMAIN_ERROR,
            "timestamp result is invalid",
        ) from err
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _finite_sensor_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise _InvalidEntityValue(
            EvaluationErrorCategory.TYPE_ERROR,
            "numeric sensor result must be a real number",
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise _InvalidEntityValue(
            EvaluationErrorCategory.DOMAIN_ERROR,
            "numeric sensor result must be finite",
        )
    return numeric


def _validated_entity_value(key: str, value: Any) -> Any:
    description = _DESCRIPTIONS.get(key)
    if description is None:
        return value

    # Home Assistant represents a temporarily absent sensor value as None.
    # Keep that distinct from an invalid type so one nullable provider field
    # cannot poison otherwise independent entities or block configuration.
    if value is None and description.entity_type is EntityType.SENSOR:
        return None

    if description.entity_type is EntityType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise _InvalidEntityValue(
                EvaluationErrorCategory.TYPE_ERROR,
                "Number result must be a real number",
            )
        try:
            numeric, _ = validate_number_value(value, description)
        except NumberValidationError as err:
            raise _InvalidEntityValue(
                EvaluationErrorCategory.DOMAIN_ERROR,
                "Number result violates its value contract",
            ) from err
        return numeric

    if description.entity_type is EntityType.BINARY_SENSOR:
        if not isinstance(value, bool):
            raise _InvalidEntityValue(
                EvaluationErrorCategory.TYPE_ERROR,
                "binary-sensor result must be boolean",
            )
        return value

    if description.entity_type is EntityType.SWITCH:
        if not isinstance(value, bool):
            raise _InvalidEntityValue(
                EvaluationErrorCategory.TYPE_ERROR,
                "switch result must be boolean",
            )
        return value

    if description.device_class is SensorDeviceClass.TIMESTAMP:
        return _normalized_timestamp(value)

    if (
        description.native_unit_of_measurement is not None
        or description.state_class is not None
        or description.suggested_display_precision is not None
    ):
        return _finite_sensor_number(value)

    if not isinstance(value, str):
        raise _InvalidEntityValue(
            EvaluationErrorCategory.TYPE_ERROR,
            "text sensor result must be a string",
        )
    return value


def evaluate_source_expressions(
    compiled: CompiledSourceExpressions,
    source_values: Mapping[str, Any],
) -> EvaluationResult:
    entity_values: dict[str, Any] = {}
    errors: dict[str, EvaluationError] = {}
    namespace = dict(EVALUATION_FUNCTIONS)
    namespace.update(INTERNAL_EVALUATION_FUNCTIONS)

    for source_key in compiled.source_keys:
        if source_key in source_values:
            namespace["__source__" + source_key] = source_values[source_key]

    for key in compiled.evaluation_order:
        item = compiled.expressions[key]

        failed_dependencies = [
            dependency
            for dependency in item.dependencies
            if dependency in errors
        ]
        if failed_dependencies:
            errors[key] = EvaluationError(
                EvaluationErrorCategory.DEPENDENCY_FAILED,
                "One or more entity dependencies are invalid",
            )
            entity_values[key] = None
            continue

        missing_sources = [
            source_key
            for source_key in item.source_keys
            if source_key not in source_values
        ]
        if missing_sources:
            errors[key] = EvaluationError(
                EvaluationErrorCategory.MISSING_SOURCE,
                "One or more source values are missing",
            )
            entity_values[key] = None
            continue

        try:
            value = eval(
                item.code,
                {"__builtins__": {}},
                namespace,
            )
            value = _validated_entity_value(key, value)
        except ZeroDivisionError:
            errors[key] = EvaluationError(
                EvaluationErrorCategory.DIVISION_BY_ZERO,
                "Expression attempted division by zero",
            )
            value = None
        except _InvalidEntityValue as err:
            errors[key] = EvaluationError(err.category, str(err))
            value = None
        except TypeError:
            errors[key] = EvaluationError(
                EvaluationErrorCategory.TYPE_ERROR,
                "Expression used incompatible value types",
            )
            value = None
        except (ArithmeticError, ValueError):
            errors[key] = EvaluationError(
                EvaluationErrorCategory.DOMAIN_ERROR,
                "Expression result is outside its supported domain",
            )
            value = None
        except Exception:
            errors[key] = EvaluationError(
                EvaluationErrorCategory.EVALUATION_ERROR,
                "Expression evaluation failed",
            )
            value = None

        entity_values[key] = value
        if key not in errors:
            namespace["__entity__" + key] = value

    return EvaluationResult(
        values=MappingProxyType(entity_values),
        errors=MappingProxyType(errors),
    )
