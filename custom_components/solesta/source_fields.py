"""Qualified provider source-field paths and expression-name binding."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any


_ESCAPE_PREFIX = "_0"
_EMPTY_SEGMENT = "_0E"
_ABSOLUTE_MARKER = "_0R"
ABSOLUTE_SOURCE_PREFIX = _ABSOLUTE_MARKER + "__"


class SourceFieldError(ValueError):
    """A source path or expression name violates the qualified-key contract."""


class SourceFieldUnavailableError(SourceFieldError):
    """A required expression name does not select an available source field."""


class SourceFieldAmbiguousError(SourceFieldError):
    """An expression name selects more than one available source field."""


def encode_source_segment(value: str) -> str:
    """Return one reversible identifier segment for arbitrary UTF-8 text."""
    if not isinstance(value, str):
        raise SourceFieldError("Source-field path segments must be strings")
    raw = value.encode("utf-8")
    if not raw:
        return _EMPTY_SEGMENT

    encoded: list[str] = []
    size = len(raw)
    for index, byte in enumerate(raw):
        letter = 65 <= byte <= 90 or 97 <= byte <= 122
        digit = 48 <= byte <= 57
        next_byte = raw[index + 1] if index + 1 < size else None
        next_plain = next_byte is not None and (
            65 <= next_byte <= 90
            or 97 <= next_byte <= 122
            or 49 <= next_byte <= 57
        )
        readable_underscore = (
            byte == 95
            and index > 0
            and raw[index - 1] != 95
            and next_plain
        )
        if letter or (digit and index > 0) or readable_underscore:
            encoded.append(chr(byte))
        else:
            encoded.append(f"{_ESCAPE_PREFIX}{byte:02X}")
    result = "".join(encoded)
    if "__" in result or result == _ABSOLUTE_MARKER:
        raise AssertionError("Source-field encoder produced a reserved token")
    return result


def decode_source_segment(value: str) -> str:
    """Decode one canonical source-field identifier segment."""
    if not isinstance(value, str) or not value:
        raise SourceFieldError("Encoded source-field segment is empty")
    if value == _EMPTY_SEGMENT:
        return ""
    if value == _ABSOLUTE_MARKER:
        raise SourceFieldError("Absolute source marker is not a path segment")

    raw = bytearray()
    index = 0
    while index < len(value):
        if value.startswith(_ESCAPE_PREFIX, index):
            token = value[index + 2 : index + 4]
            if len(token) != 2 or any(
                character not in "0123456789ABCDEF" for character in token
            ):
                raise SourceFieldError("Source-field escape is not canonical")
            raw.append(int(token, 16))
            index += 4
            continue
        character = value[index]
        if not character.isascii() or not (
            character.isalnum() or character == "_"
        ):
            raise SourceFieldError("Encoded source-field segment is invalid")
        raw.extend(character.encode("ascii"))
        index += 1

    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as err:
        raise SourceFieldError("Source-field segment contains invalid UTF-8") from err
    if encode_source_segment(decoded) != value:
        raise SourceFieldError("Source-field segment is not canonical")
    return decoded


def canonical_source_name(path: Collection[str]) -> str:
    """Return the leaf-first canonical expression name for one source path."""
    segments = tuple(path)
    if not segments:
        raise SourceFieldError("Source-field path cannot be empty")
    return "__".join(
        encode_source_segment(segment) for segment in reversed(segments)
    )


def decode_canonical_source_name(value: str) -> tuple[str, ...]:
    """Return the outside-in path encoded by one full canonical name."""
    if not isinstance(value, str) or not value:
        raise SourceFieldError("Canonical source-field name is empty")
    if value.startswith(ABSOLUTE_SOURCE_PREFIX):
        value = value[len(ABSOLUTE_SOURCE_PREFIX) :]
    encoded = value.split("__")
    if any(not segment for segment in encoded):
        raise SourceFieldError("Canonical source-field name has an empty token")
    return tuple(reversed(tuple(decode_source_segment(item) for item in encoded)))


def flatten_source_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten nested mappings to collision-free qualified canonical names."""
    flattened: dict[str, Any] = {}

    def visit(mapping: Mapping[str, Any], prefix: tuple[str, ...]) -> None:
        for raw_key, item in mapping.items():
            if not isinstance(raw_key, str):
                raise SourceFieldError("Provider source keys must be strings")
            path = (*prefix, raw_key)
            if isinstance(item, Mapping) and item:
                visit(item, path)
                continue
            key = canonical_source_name(path)
            if key in flattened:
                raise SourceFieldError(
                    f"Provider source path collides at {key!r}"
                )
            flattened[key] = item

    visit(value, ())
    return flattened


class SourceFieldTable:
    """Resolve shortest unique expression names to exact canonical keys."""

    def __init__(self, canonical_names: Collection[str]) -> None:
        names: set[str] = set()
        for name in canonical_names:
            canonical = str(name)
            decoded = decode_canonical_source_name(canonical)
            if canonical_source_name(decoded) != canonical:
                raise SourceFieldError(
                    f"Source-field table name {canonical!r} is not canonical"
                )
            names.add(canonical)
        self._names = frozenset(names)

    @property
    def names(self) -> frozenset[str]:
        return self._names

    def resolve(self, value: str, *, optional: bool = False) -> str:
        """Resolve one short or absolute name without exact-match precedence."""
        if not isinstance(value, str) or not value:
            raise SourceFieldError("Source-field expression name is empty")
        if value.startswith(ABSOLUTE_SOURCE_PREFIX):
            canonical = value[len(ABSOLUTE_SOURCE_PREFIX) :]
            path = decode_canonical_source_name(canonical)
            canonical = canonical_source_name(path)
            if canonical not in self._names and not optional:
                raise SourceFieldUnavailableError(
                    f"Required source field {canonical!r} is unavailable"
                )
            return canonical

        # Validate that the spelling itself is a canonical segment sequence.
        path = decode_canonical_source_name(value)
        short = canonical_source_name(path)
        if short != value:
            raise SourceFieldError(f"Source field {value!r} is not canonical")
        candidates = sorted(
            name
            for name in self._names
            if name == short or name.startswith(short + "__")
        )
        if len(candidates) == 1:
            return candidates[0]
        if not candidates and optional:
            return short
        if not candidates:
            raise SourceFieldUnavailableError(f"Source field {value!r} is unavailable")
        raise SourceFieldAmbiguousError(
            f"Source field {value!r} is ambiguous: " + ", ".join(candidates)
        )
