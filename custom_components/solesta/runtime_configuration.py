"""Immutable compiled configuration for one system."""

from __future__ import annotations

from dataclasses import dataclass
import ast
from types import MappingProxyType
from typing import Mapping

from .compile import CompiledSourceExpressions, compile_source_expressions
from .description import EntityType
from .thetruth import DESCRIPTIONS


DROP_SOURCE_EXPRESSION = "drop()"


def is_drop_expression(value: object) -> bool:
    """Return whether a stored expression suppresses runtime evaluation."""
    return (
        isinstance(value, str)
        and value.strip() == DROP_SOURCE_EXPRESSION
    )


@dataclass(frozen=True, slots=True)
class RuntimeConfiguration:
    """Keep source expressions and every compiler result in one atomic value."""

    source_expressions: Mapping[str, str]
    compiled_source_expressions: CompiledSourceExpressions
    required_source_keys: frozenset[str]
    dropped_keys: frozenset[str]
    evaluated_keys: frozenset[str]

    @classmethod
    def compile(
        cls,
        source_expressions: Mapping[str, str],
    ) -> RuntimeConfiguration:
        """Validate and compile one complete expression mapping."""
        expressions = dict(source_expressions)
        expected_keys = {description.key for description in DESCRIPTIONS}
        actual_keys = set(expressions)

        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            details: list[str] = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("unexpected: " + ", ".join(extra))
            raise ValueError(
                "Source-expression keys do not match the entity schema ("
                + "; ".join(details)
                + ")"
            )

        description_by_key = {
            description.key: description for description in DESCRIPTIONS
        }
        for key, expression in expressions.items():
            if description_by_key[key].entity_type is not EntityType.SWITCH:
                continue
            try:
                literal = ast.literal_eval(expression)
            except (SyntaxError, ValueError) as err:
                raise ValueError(
                    f"Switch source expression {key!r} must be True or False"
                ) from err
            if type(literal) is not bool:
                raise ValueError(
                    f"Switch source expression {key!r} must be True or False"
                )

        dropped_keys = frozenset(
            key for key, value in expressions.items() if is_drop_expression(value)
        )
        evaluated = {
            key: value
            for key, value in expressions.items()
            if key not in dropped_keys
        }
        compiled = compile_source_expressions(evaluated)

        return cls(
            source_expressions=MappingProxyType(expressions),
            compiled_source_expressions=compiled,
            required_source_keys=compiled.source_keys,
            dropped_keys=dropped_keys,
            evaluated_keys=frozenset(evaluated),
        )

    def with_source_expression(
        self,
        key: str,
        source_expression: str,
    ) -> RuntimeConfiguration:
        """Return a fully compiled replacement with one changed expression."""
        if key not in self.source_expressions:
            raise KeyError(f"Unknown entity key: {key}")

        expressions = dict(self.source_expressions)
        expressions[key] = source_expression
        return type(self).compile(expressions)

    def stored_source_expressions(self) -> dict[str, str]:
        """Return the serializable source expressions."""
        return dict(self.source_expressions)
