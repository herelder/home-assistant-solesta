"""Compile declarative source expressions."""

from __future__ import annotations

import ast
from collections.abc import Collection, Mapping
from dataclasses import dataclass
import math
from types import CodeType, MappingProxyType
from typing import Any

from .expression_functions import (
    EVALUATION_FUNCTIONS,
    INTERNAL_EVALUATION_FUNCTIONS,
    validate_delay_zone_borders,
)
from .source_fields import SourceFieldError, SourceFieldTable

_MAX_EXPRESSIONS = 128
_MAX_EXPRESSION_CHARACTERS = 1024
_MAX_TOTAL_EXPRESSION_CHARACTERS = 16 * 1024
_MAX_AST_NODES = 256
_MAX_AST_DEPTH = 32
_MAX_STRING_LITERAL_BYTES = 4096
_MAX_ABS_NUMERIC_LITERAL = 1e12


class SourceExpressionError(ValueError):
    """Base error for an invalid source-expression mapping."""

    def __init__(
        self, message: str, *, expression_keys: Collection[str] = ()
    ) -> None:
        super().__init__(message)
        self.expression_keys = tuple(expression_keys)


class SourceExpressionValidationError(SourceExpressionError):
    """Keep independent failures attached to their original expression fields."""

    def __init__(self, errors: Mapping[str, SourceExpressionError]) -> None:
        super().__init__(
            "Invalid source expressions: " + ", ".join(errors),
            expression_keys=tuple(errors),
        )
        self.errors = MappingProxyType(dict(errors))


class SourceExpressionSyntaxError(SourceExpressionError):
    """A source expression uses invalid or unsupported syntax."""


class SourceExpressionFunctionError(SourceExpressionError):
    """A source expression uses a function outside its contract."""


class SourceExpressionDependencyError(SourceExpressionError):
    """The entity-expression dependency graph is invalid."""


_ALLOWED_NODES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.keyword,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


class _SyntaxValidator(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_NODES):
            raise SourceExpressionSyntaxError(
                f"Syntax element {type(node).__name__!r} is not allowed"
            )
        super().generic_visit(node)


def _rewrite_source_suffix(expression: str) -> tuple[str, dict[str, str]]:
    """Rewrite ``name'`` using aliases absent from the original expression."""
    result: list[str] = []
    aliases: dict[str, str] = {}
    index = 0
    alias_index = 0

    def next_alias() -> str:
        nonlocal alias_index
        while True:
            candidate = f"__source_suffix_alias_{alias_index}"
            alias_index += 1
            if candidate not in expression and candidate not in aliases:
                return candidate

    while index < len(expression):
        character = expression[index]

        if character in {"'", '"'}:
            # Copy a complete Python string literal without interpreting names
            # inside it as expression identifiers. Escapes and triple-quoted
            # literals are preserved for ast.parse to validate afterwards.
            quote = character
            delimiter = (
                quote * 3
                if expression.startswith(quote * 3, index)
                else quote
            )
            start = index
            index += len(delimiter)
            while index < len(expression):
                if expression[index] == "\\":
                    index = min(index + 2, len(expression))
                    continue
                if expression.startswith(delimiter, index):
                    index += len(delimiter)
                    break
                index += 1
            result.append(expression[start:index])
            continue

        if character.isalpha() or character == "_":
            start = index
            index += 1
            while index < len(expression) and (
                expression[index].isalnum() or expression[index] == "_"
            ):
                index += 1
            name = expression[start:index]
            if index < len(expression) and expression[index] == "'":
                alias = next_alias()
                aliases[alias] = name
                result.append(alias)
                index += 1
            else:
                result.append(name)
            continue

        result.append(character)
        index += 1

    return "".join(result), aliases


@dataclass(frozen=True, slots=True)
class CompiledSourceExpression:
    """One validated, resolved, and executable entity expression."""

    key: str
    expression: str
    code: CodeType
    dependencies: tuple[str, ...]
    source_keys: tuple[str, ...]
    required_dependencies: tuple[str, ...]
    required_source_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledSourceExpressions:
    """Immutable compiled graph and its complete provider-key contract."""

    expressions: Mapping[str, CompiledSourceExpression]
    evaluation_order: tuple[str, ...]
    source_keys: frozenset[str]
    required_source_keys: frozenset[str]

    def __getitem__(self, key: str) -> CompiledSourceExpression:
        return self.expressions[key]


class _NameResolver(ast.NodeTransformer):
    def __init__(
        self,
        current_key: str,
        entity_keys: set[str],
        source_aliases: Mapping[str, str],
        source_fields: SourceFieldTable | None,
    ) -> None:
        self.current_key = current_key
        self.entity_keys = entity_keys
        self.source_aliases = source_aliases
        self.source_fields = source_fields
        self.dependencies: set[str] = set()
        self.source_keys: set[str] = set()
        self.required_dependencies: set[str] = set()
        self.required_source_keys: set[str] = set()
        self._nullable_depth = 0

    def visit_Call(self, node: ast.Call) -> ast.Call:
        nullable = isinstance(node.func, ast.Name) and node.func.id == "null"
        self._nullable_depth += nullable
        try:
            node.args = [self.visit(argument) for argument in node.args]
            node.keywords = [self.visit(keyword) for keyword in node.keywords]
        finally:
            self._nullable_depth -= nullable
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        name = node.id
        if name in self.source_aliases:
            source = self._resolve_source(self.source_aliases[name])
            self.source_keys.add(source)
            node.id = "__source__" + source
        elif name in self.entity_keys:
            if name == self.current_key:
                source = self._resolve_source(name)
                self.source_keys.add(source)
                node.id = "__source__" + source
            else:
                self.dependencies.add(name)
                node.id = "__entity__" + name
        else:
            source = self._resolve_source(name)
            self.source_keys.add(source)
            node.id = "__source__" + source
        if not self._nullable_depth:
            if node.id.startswith("__source__"):
                self.required_source_keys.add(node.id[len("__source__"):])
            else:
                self.required_dependencies.add(name)
        return node

    def _resolve_source(self, name: str) -> str:
        if self.source_fields is None:
            return name
        try:
            return self.source_fields.resolve(
                name,
                optional=bool(self._nullable_depth),
            )
        except SourceFieldError as err:
            raise SourceExpressionDependencyError(str(err)) from err


class _FieldLiteralTransformer(ast.NodeTransformer):
    """Interpret Python's None token as an ordinary expression field name."""

    def visit_Constant(self, node: ast.Constant) -> ast.expr:
        if node.value is None:
            return ast.copy_location(ast.Name(id="None", ctx=ast.Load()), node)
        return node


class _ArgumentFields(ast.NodeVisitor):
    """Find field references while excluding function names."""

    def __init__(self) -> None:
        self.found = False

    def visit_Name(self, node: ast.Name) -> None:
        self.found = True

    def visit_Call(self, node: ast.Call) -> None:
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)


def _validate_null_call(node: ast.Call) -> None:
    if node.keywords:
        raise SourceExpressionFunctionError("null accepts positional arguments only")
    for argument in node.args:
        if isinstance(argument, ast.Name):
            continue
        fields = _ArgumentFields()
        fields.visit(argument)
        if fields.found:
            raise SourceExpressionFunctionError(
                "Each null argument must be a field or a field-free expression"
            )


_SAFE_BINARY_FUNCTIONS = {
    ast.Add: "__safe_add",
    ast.Sub: "__safe_sub",
    ast.Mult: "__safe_mult",
    ast.Div: "__safe_div",
    ast.Mod: "__safe_mod",
}


class _SafeOperatorTransformer(ast.NodeTransformer):
    """Replace allocating Python arithmetic with bounded numeric helpers."""

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        left = self.visit(node.left)
        right = self.visit(node.right)
        function = _SAFE_BINARY_FUNCTIONS[type(node.op)]
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id=function, ctx=ast.Load()),
                args=[left, right],
                keywords=[],
            ),
            node,
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            node.operand = operand
            return node
        function = (
            "__safe_pos" if isinstance(node.op, ast.UAdd) else "__safe_neg"
        )
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id=function, ctx=ast.Load()),
                args=[operand],
                keywords=[],
            ),
            node,
        )


def _validate_tree_complexity(tree: ast.AST) -> None:
    """Reject oversized, deeply nested, or allocating syntax before compile."""
    nodes = 0
    stack: list[tuple[ast.AST, int]] = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_AST_NODES:
            raise SourceExpressionSyntaxError(
                "Source expression contains too many syntax nodes"
            )
        if depth > _MAX_AST_DEPTH:
            raise SourceExpressionSyntaxError(
                "Source expression is nested too deeply"
            )
        if isinstance(node, ast.Constant):
            value = node.value
            if (
                isinstance(value, str)
                and len(value.encode("utf-8")) > _MAX_STRING_LITERAL_BYTES
            ):
                raise SourceExpressionSyntaxError(
                    "Source expression string literal is too long"
                )
            if isinstance(value, int) and not isinstance(value, bool):
                if abs(value) > _MAX_ABS_NUMERIC_LITERAL:
                    raise SourceExpressionSyntaxError(
                        "Source expression numeric literal is too large"
                    )
            elif isinstance(value, float):
                if (
                    not math.isfinite(value)
                    or abs(value) > _MAX_ABS_NUMERIC_LITERAL
                ):
                    raise SourceExpressionSyntaxError(
                        "Source expression numeric literal is too large"
                    )
            elif value is not None and not isinstance(value, (str, bool)):
                raise SourceExpressionSyntaxError(
                    "Source expression contains an unsupported literal"
                )
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


def _evaluate_constant_number(node: ast.expr) -> Any:
    """Evaluate a numeric border expression without native allocating ops."""
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("not a numeric constant")
        return value
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_constant_number(node.operand)
        function = (
            "__safe_pos" if isinstance(node.op, ast.UAdd) else "__safe_neg"
        )
        return INTERNAL_EVALUATION_FUNCTIONS[function](operand)
    if isinstance(node, ast.BinOp):
        left = _evaluate_constant_number(node.left)
        right = _evaluate_constant_number(node.right)
        function = _SAFE_BINARY_FUNCTIONS[type(node.op)]
        return INTERNAL_EVALUATION_FUNCTIONS[function](left, right)
    raise TypeError("not a numeric constant expression")


def _validate_delay_zone_call(node: ast.Call) -> None:
    """Validate the static border contract before runtime evaluation."""
    if node.keywords or len(node.args) < 2:
        raise SourceExpressionFunctionError(
            "delay_zone requires a timestamp and at least one border"
        )

    borders: list[Any] = []
    for argument in node.args[1:]:
        try:
            value = _evaluate_constant_number(argument)
        except Exception as err:
            raise SourceExpressionFunctionError(
                "delay_zone borders must be constant numeric expressions"
            ) from err
        borders.append(value)

    try:
        validate_delay_zone_borders(*borders)
    except (TypeError, ValueError) as err:
        raise SourceExpressionFunctionError(str(err)) from err


def _validate_solar_thermal_alerts_call(node: ast.Call) -> None:
    """Validate constant alert settings when an expression is configured."""
    if node.keywords:
        raise SourceExpressionFunctionError(
            "solar_thermal_alerts accepts positional arguments only"
        )
    if len(node.args) != 5:
        raise SourceExpressionFunctionError(
            "solar_thermal_alerts requires null values and four constants"
        )
    nullable_values = node.args[0]
    if (
        not isinstance(nullable_values, ast.Call)
        or not isinstance(nullable_values.func, ast.Name)
        or nullable_values.func.id != "null"
        or nullable_values.keywords
        or len(nullable_values.args) != 4
    ):
        raise SourceExpressionFunctionError(
            "solar_thermal_alerts requires four values in null(...)"
        )
    threshold_nodes = node.args[1:]

    thresholds: list[float] = []
    for argument in threshold_nodes:
        try:
            value = _evaluate_constant_number(argument)
        except Exception as err:
            raise SourceExpressionFunctionError(
                "solar_thermal_alerts thresholds must be constant numeric "
                "expressions"
            ) from err
        numeric = float(value)
        if not math.isfinite(numeric):
            raise SourceExpressionFunctionError(
                "solar_thermal_alerts thresholds must be finite"
            )
        thresholds.append(numeric)

    hot, danger, idle_delta, active_delta = thresholds
    if danger <= hot:
        raise SourceExpressionFunctionError(
            "collector danger threshold must exceed warning threshold"
        )
    if idle_delta < 0 or active_delta < 0:
        raise SourceExpressionFunctionError(
            "pump temperature deltas must not be negative"
        )


def _topological_order(graph: Mapping[str, set[str]]) -> tuple[str, ...]:
    remaining = {key: set(value) for key, value in graph.items()}
    result: list[str] = []
    while remaining:
        ready = sorted(key for key, value in remaining.items() if not value)
        if not ready:
            cyclic = []
            for key in sorted(remaining):
                pending = list(remaining[key])
                seen: set[str] = set()
                while pending:
                    dependency = pending.pop()
                    if dependency == key:
                        cyclic.append(key)
                        break
                    if dependency not in seen:
                        seen.add(dependency)
                        pending.extend(remaining[dependency])
            raise SourceExpressionDependencyError(
                "Circular dependency detected among: "
                + ", ".join(cyclic),
                expression_keys=cyclic,
            )
        result.extend(ready)
        for key in ready:
            remaining.pop(key)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(result)


def _compile_source_expression(
    key: str,
    expression: str,
    *,
    entity_keys: set[str],
    functions: Mapping[str, Any],
    source_fields: SourceFieldTable | None,
) -> CompiledSourceExpression:
    """Compile one field without replacing neighbouring expressions."""
    if not isinstance(expression, str) or not expression.strip():
        raise SourceExpressionError(
            f"Source expression for {key!r} must be a non-empty string"
        )
    if len(expression) > _MAX_EXPRESSION_CHARACTERS:
        raise SourceExpressionError(f"Source expression for {key!r} is too long")
    rewritten, source_aliases = _rewrite_source_suffix(expression)
    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError as err:
        raise SourceExpressionSyntaxError(
            f"Invalid source expression for {key!r}: {err.msg}"
        ) from err
    tree = _FieldLiteralTransformer().visit(tree)
    _validate_tree_complexity(tree)
    _SyntaxValidator().visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in functions
        ):
            raise SourceExpressionFunctionError(
                f"Function {getattr(node.func, 'id', None)!r} is not allowed"
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "null"
        ):
            _validate_null_call(node)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"last_report", "last_update"}
            and (node.keywords or node.args)
        ):
            raise SourceExpressionFunctionError(f"{node.func.id} requires no arguments")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "delay_zone"
        ):
            _validate_delay_zone_call(node)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "solar_thermal_alerts"
        ):
            _validate_solar_thermal_alerts_call(node)
    resolver = _NameResolver(key, entity_keys, source_aliases, source_fields)
    tree = resolver.visit(tree)
    tree = _SafeOperatorTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    return CompiledSourceExpression(
        key,
        expression,
        compile(tree, f"<source_expression:{key}>", "eval"),
        tuple(sorted(resolver.dependencies)),
        tuple(sorted(resolver.source_keys)),
        tuple(sorted(resolver.required_dependencies)),
        tuple(sorted(resolver.required_source_keys)),
    )


def compile_source_expressions(
    source_expressions: Mapping[str, str],
    *,
    allowed_functions: Mapping[str, Any] | None = None,
    available_source_keys: Collection[str] | None = None,
) -> CompiledSourceExpressions:
    """Validate and compile one complete source-expression graph."""
    if not isinstance(source_expressions, Mapping):
        raise SourceExpressionError("Source expressions must be a mapping")
    if len(source_expressions) > _MAX_EXPRESSIONS:
        raise SourceExpressionError("Too many source expressions")
    total_characters = sum(
        len(expression)
        for expression in source_expressions.values()
        if isinstance(expression, str)
    )
    if total_characters > _MAX_TOTAL_EXPRESSION_CHARACTERS:
        raise SourceExpressionError("Source expressions are too large")

    entity_keys = set(source_expressions)
    functions = dict(
        EVALUATION_FUNCTIONS if allowed_functions is None else allowed_functions
    )
    functions.update({"last_report": None, "last_update": None})
    source_fields = (
        None
        if available_source_keys is None
        else SourceFieldTable(available_source_keys)
    )
    compiled: dict[str, CompiledSourceExpression] = {}
    graph = {key: set() for key in source_expressions}
    source_keys: set[str] = set()
    required_source_keys: set[str] = set()
    errors: dict[str, SourceExpressionError] = {}
    for key, expression in source_expressions.items():
        if not isinstance(key, str) or not key:
            raise SourceExpressionError(
                "Source-expression keys must be non-empty strings"
            )
        try:
            item = _compile_source_expression(
                key,
                expression,
                entity_keys=entity_keys,
                functions=functions,
                source_fields=source_fields,
            )
        except SourceExpressionError as err:
            err.expression_keys = (key,)
            errors[key] = err
            continue
        graph[key] = set(item.dependencies)
        source_keys.update(item.source_keys)
        required_source_keys.update(item.required_source_keys)
        compiled[key] = item
    try:
        evaluation_order = _topological_order(graph)
    except SourceExpressionDependencyError as err:
        for key in err.expression_keys:
            errors[key] = err
    if errors:
        if len({id(error) for error in errors.values()}) == 1:
            raise next(iter(errors.values()))
        raise SourceExpressionValidationError(errors)
    return CompiledSourceExpressions(
        MappingProxyType(compiled),
        evaluation_order,
        frozenset(source_keys),
        frozenset(required_source_keys),
    )
