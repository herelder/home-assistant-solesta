"""Strict reference parser for the observed Solesta serial stream.

This host-side parser exists to make the protocol assumptions executable before
the ESP32 hardware is available.  The eventual ESPHome implementation must keep
the same all-or-nothing parsing, raw-token preservation and line resynchronising
behaviour.  Only status records and controller-state records belong to the
contract; MQTT logging and all other source logging are deliberately ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re


RAW_FIELD_NAMES = (
    "temperature_1_raw",
    "temperature_2_raw",
    "temperature_3_raw",
    "temperature_4_raw",
    "flow_raw",
    "pump_raw",
)

_FINITE_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_UNSIGNED_INTEGER = re.compile(r"\d+")


class StatusParseError(ValueError):
    """Raised when a candidate status line violates the observed grammar."""


class ControllerStateParseError(ValueError):
    """Raised when a candidate controller-state line is malformed."""


@dataclass(frozen=True, slots=True)
class StatusFrame:
    """One fully validated status frame in raw and numeric form."""

    raw_values: tuple[str, str, str, str, str, str]
    numeric_values: tuple[float, float, float, float, float, float]
    raw_line: str

    def raw_by_name(self) -> dict[str, str]:
        """Return stable technical field names mapped to original tokens."""

        return dict(zip(RAW_FIELD_NAMES, self.raw_values, strict=True))

    def numeric_by_name(self) -> dict[str, float]:
        """Return stable technical field names mapped to parsed numbers."""

        return dict(zip(RAW_FIELD_NAMES, self.numeric_values, strict=True))


@dataclass(frozen=True, slots=True)
class ControllerState:
    """The code and unpadded text from one ``Z|code|text`` record."""

    code: int
    text: str

    def entity_states(self) -> dict[str, int | str]:
        """Return the two ESPHome/HA entity states defined by the contract."""

        return {
            "controller_state_code": self.code,
            "controller_state_text": self.text,
        }


def _remove_line_ending(line: str) -> str:
    """Remove one LF or CRLF ending, without trimming content characters."""

    if line.endswith("\n"):
        line = line[:-1]
        if line.endswith("\r"):
            line = line[:-1]
    elif line.endswith("\r"):
        line = line[:-1]
    return line


def _parse_number(token: str) -> float:
    if _FINITE_NUMBER.fullmatch(token) is None:
        raise StatusParseError(f"invalid numeric token: {token!r}")
    value = float(token)
    if not math.isfinite(value):
        raise StatusParseError(f"non-finite numeric token: {token!r}")
    return value


def parse_status_line(line: str) -> StatusFrame:
    """Parse exactly ``T|t1|t2|t3|t4_F|flow_PWM|pump``.

    Only a line ending may be removed.  Tokens are retained byte-for-byte after
    ASCII decoding, so ``0.000000`` and the exceptional ``309`` remain intact.
    """

    line = _remove_line_ending(line)
    groups = line.split("_")
    if len(groups) != 3:
        raise StatusParseError("expected exactly three underscore groups")

    temperature = groups[0].split("|")
    flow = groups[1].split("|")
    pump = groups[2].split("|")
    if temperature[0:1] != ["T"] or len(temperature) != 5:
        raise StatusParseError("expected T followed by four values")
    if flow[0:1] != ["F"] or len(flow) != 2:
        raise StatusParseError("expected F followed by one value")
    if pump[0:1] != ["PWM"] or len(pump) != 2:
        raise StatusParseError("expected PWM followed by one value")

    raw_values = tuple(temperature[1:] + flow[1:] + pump[1:])
    if len(raw_values) != 6:
        raise StatusParseError("expected exactly six values")
    numeric_values = tuple(_parse_number(token) for token in raw_values)
    return StatusFrame(raw_values, numeric_values, line)  # type: ignore[arg-type]


def parse_controller_state_line(line: str) -> ControllerState:
    """Parse ``Z|code|text`` and remove only text-field space padding."""

    line = _remove_line_ending(line)
    parts = line.split("|", 2)
    if len(parts) != 3 or parts[0] != "Z":
        raise ControllerStateParseError("expected Z followed by code and text")
    code_token, wire_text = parts[1], parts[2]
    if _UNSIGNED_INTEGER.fullmatch(code_token) is None:
        raise ControllerStateParseError("controller-state code was not an integer")
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in wire_text):
        raise ControllerStateParseError(
            "controller-state text contained a non-printable character"
        )
    text = wire_text.strip(" ")
    if not text:
        raise ControllerStateParseError("controller-state text was empty")
    return ControllerState(code=int(code_token), text=text)


@dataclass(slots=True)
class StreamStats:
    """Observable counters for replay and later on-device diagnostics."""

    valid_frames: int = 0
    invalid_frames: int = 0
    controller_states: int = 0
    invalid_controller_states: int = 0
    ignored_lines: int = 0
    non_ascii_lines: int = 0
    overlong_lines: int = 0
    truncated_lines: int = 0


@dataclass(slots=True)
class SolestaStreamParser:
    """Incrementally frame UART bytes and retain only status and Z records."""

    max_line_length: int = 256
    stats: StreamStats = field(default_factory=StreamStats)
    last_valid_frame: StatusFrame | None = None
    last_controller_state: ControllerState | None = None
    controller_state_updates: list[ControllerState] = field(default_factory=list)
    last_error: str | None = None
    _buffer: bytearray = field(default_factory=bytearray)
    _discard_until_lf: bool = False

    def feed(self, data: bytes) -> list[StatusFrame]:
        """Consume an arbitrary UART byte chunk and return new valid frames."""

        frames: list[StatusFrame] = []
        for byte in data:
            if self._discard_until_lf:
                if byte == 0x0A:
                    self._discard_until_lf = False
                continue

            if byte == 0x0A:
                line = bytes(self._buffer)
                self._buffer.clear()
                if line.endswith(b"\r"):
                    line = line[:-1]
                frame = self._process_line(line)
                if frame is not None:
                    frames.append(frame)
                continue

            self._buffer.append(byte)
            if len(self._buffer) > self.max_line_length:
                self._buffer.clear()
                self._discard_until_lf = True
                self.stats.overlong_lines += 1
                self.last_error = "line exceeded maximum length"
        return frames

    def finish(self) -> None:
        """Mark a non-newline-terminated tail as truncated and discard it."""

        if self._discard_until_lf:
            self._discard_until_lf = False
            return
        if not self._buffer:
            return
        self._buffer.clear()
        self.stats.truncated_lines += 1
        self.last_error = "truncated line without LF terminator"

    def _process_line(self, encoded_line: bytes) -> StatusFrame | None:
        try:
            line = encoded_line.decode("ascii")
        except UnicodeDecodeError:
            self.stats.non_ascii_lines += 1
            self.stats.ignored_lines += 1
            self.last_error = "line was not ASCII"
            return None

        if line.startswith("Z|"):
            try:
                state = parse_controller_state_line(line)
            except ControllerStateParseError as err:
                self.stats.invalid_controller_states += 1
                self.last_error = str(err)
                return None
            self.last_controller_state = state
            self.controller_state_updates.append(state)
            self.stats.controller_states += 1
            self.last_error = None
            return None

        is_status_candidate = line.startswith("T|") or "_F|" in line or "_PWM|" in line
        if not is_status_candidate:
            self.stats.ignored_lines += 1
            return None

        try:
            frame = parse_status_line(line)
        except StatusParseError as err:
            self.stats.invalid_frames += 1
            self.last_error = str(err)
            return None

        self.last_valid_frame = frame
        self.stats.valid_frames += 1
        self.last_error = None
        return frame
