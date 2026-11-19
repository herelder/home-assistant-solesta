"""Dry-run the Solesta parser against the preserved CoolTerm excerpt."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPOSITORY = Path(__file__).parents[1]
FIXTURE = REPOSITORY / "tests" / "fixtures" / "solesta_coolterm_excerpt.txt"
PARSER_PATH = REPOSITORY / "tools" / "solesta_stream_parser.py"
spec = importlib.util.spec_from_file_location("solesta_stream_parser", PARSER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load tools/solesta_stream_parser.py")
parser_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser_module
spec.loader.exec_module(parser_module)

SolestaStreamParser = parser_module.SolestaStreamParser
ControllerStateParseError = parser_module.ControllerStateParseError
StatusParseError = parser_module.StatusParseError
parse_controller_state_line = parser_module.parse_controller_state_line
parse_status_line = parser_module.parse_status_line


class SolestaStatusLineTests(unittest.TestCase):
    def test_exact_coolterm_status_line_preserves_all_six_tokens(self):
        frame = parse_status_line("T|47|34|34|309_F|0.000000_PWM|0.000000")
        self.assertEqual(
            frame.raw_values,
            ("47", "34", "34", "309", "0.000000", "0.000000"),
        )
        self.assertEqual(
            frame.numeric_values,
            (47.0, 34.0, 34.0, 309.0, 0.0, 0.0),
        )
        self.assertEqual(
            frame.raw_line,
            "T|47|34|34|309_F|0.000000_PWM|0.000000",
        )
        self.assertEqual(frame.raw_by_name()["temperature_4_raw"], "309")

    def test_fractional_pwm_is_preserved_and_not_reduced_to_binary(self):
        frame = parse_status_line("T|37|34|34|309_F|0.000000_PWM|0.757539")
        self.assertEqual(frame.raw_by_name()["pump_raw"], "0.757539")
        self.assertEqual(frame.numeric_by_name()["pump_raw"], 0.757539)

    def test_lf_and_crlf_are_accepted_without_trimming_tokens(self):
        source = "T|47|34|34|309_F|0.000000_PWM|0.000000"
        self.assertEqual(parse_status_line(source + "\n").raw_values[3], "309")
        self.assertEqual(parse_status_line(source + "\r\n").raw_values[4], "0.000000")
        with self.assertRaises(StatusParseError):
            parse_status_line(" " + source)

    def test_invalid_frames_are_rejected_as_a_whole(self):
        invalid = (
            "T|47|34|309_F|0.000000_PWM|0.000000",
            "T|47|34|34|309_F|0.000000_PWM|0.000000_EXTRA|1",
            "T|47|34|34|309_PWM|0.000000_F|0.000000",
            "T|47|34|bad|309_F|0.000000_PWM|0.000000",
            "T|47|34|34|309_F|NaN_PWM|0.000000",
            "T|47|34|34|309_F|inf_PWM|0.000000",
        )
        for line in invalid:
            with self.subTest(line=line), self.assertRaises(StatusParseError):
                parse_status_line(line)


class SolestaControllerStateTests(unittest.TestCase):
    def test_code_and_source_text_are_both_preserved(self):
        state = parse_controller_state_line("Z|3|Run State\r\n")
        self.assertEqual(state.code, 3)
        self.assertEqual(state.text, "Run State")
        self.assertEqual(
            state.entity_states(),
            {
                "controller_state_code": 3,
                "controller_state_text": "Run State",
            },
        )

        future = parse_controller_state_line("Z|17|Future State")
        self.assertEqual(future.code, 17)
        self.assertEqual(future.text, "Future State")

    def test_malformed_controller_states_are_rejected(self):
        for line in ("Z|run|Run State", "Z|3|", "Z|3", "Z|3|Run\tState"):
            with self.subTest(line=line), self.assertRaises(ControllerStateParseError):
                parse_controller_state_line(line)


class SolestaStreamReplayTests(unittest.TestCase):
    def test_preserved_coolterm_excerpt_survives_arbitrary_uart_chunks(self):
        stream = FIXTURE.read_bytes()
        parser = SolestaStreamParser()
        frames = []
        chunk_sizes = (1, 2, 7, 3, 11, 5)
        offset = 0
        chunk_index = 0
        while offset < len(stream):
            size = chunk_sizes[chunk_index % len(chunk_sizes)]
            frames.extend(parser.feed(stream[offset : offset + size]))
            offset += size
            chunk_index += 1
        parser.finish()

        self.assertEqual(len(frames), 4)
        self.assertEqual(parser.stats.valid_frames, 4)
        self.assertEqual(parser.stats.invalid_frames, 0)
        self.assertEqual(parser.stats.controller_states, 3)
        self.assertEqual(parser.stats.invalid_controller_states, 0)
        self.assertEqual(parser.stats.ignored_lines, 8)
        self.assertEqual(
            parser.controller_state_updates,
            [
                parser_module.ControllerState(2, "Startup State"),
                parser_module.ControllerState(3, "Run State"),
                parser_module.ControllerState(4, "Pause State"),
            ],
        )
        self.assertEqual(
            [frame.raw_by_name()["pump_raw"] for frame in frames],
            ["0.000000", "1.000000", "0.757539", "0.000000"],
        )

    def test_invalid_frame_does_not_replace_last_valid_values(self):
        parser = SolestaStreamParser()
        valid = b"T|47|34|34|309_F|0.000000_PWM|0.000000\r\n"
        parser.feed(valid)
        previous = parser.last_valid_frame
        parser.feed(b"T|47|34|broken|309_F|0.000000_PWM|0.000000\n")

        self.assertIs(parser.last_valid_frame, previous)
        self.assertEqual(parser.stats.valid_frames, 1)
        self.assertEqual(parser.stats.invalid_frames, 1)

    def test_nonterminated_tail_is_counted_as_truncated(self):
        parser = SolestaStreamParser()
        parser.feed(b"T|47|34")
        parser.finish()
        self.assertEqual(parser.stats.invalid_frames, 0)
        self.assertEqual(parser.stats.truncated_lines, 1)
        self.assertIsNone(parser.last_valid_frame)

    def test_overlong_startup_garbage_is_discarded_until_next_lf(self):
        parser = SolestaStreamParser(max_line_length=64)
        valid = b"T|47|34|34|309_F|0.000000_PWM|0.000000\r\n"
        frames = parser.feed((b"\xff" * 305) + b"\r\n" + valid)

        self.assertEqual(len(frames), 1)
        self.assertEqual(parser.stats.overlong_lines, 1)
        self.assertEqual(parser.stats.non_ascii_lines, 0)
        self.assertEqual(parser.stats.ignored_lines, 0)

    def test_short_non_ascii_and_mqtt_logging_are_ignored(self):
        parser = SolestaStreamParser()
        frames = parser.feed(
            b"\xff\r\n"
            b"Temp01 updated!\r\n"
            b"Temp01 Failed!\r\n"
            b"MQTT failed!\r\n"
            b"HTTP return code: 502\r\n"
        )

        self.assertEqual(frames, [])
        self.assertEqual(parser.stats.non_ascii_lines, 1)
        self.assertEqual(parser.stats.ignored_lines, 5)
        self.assertEqual(parser.stats.invalid_frames, 0)
        self.assertEqual(parser.stats.controller_states, 0)

    def test_syntactically_valid_temperature_jump_is_not_filtered(self):
        parser = SolestaStreamParser()
        stream = (
            b"T|56|30|30|309_F|0.000000_PWM|0.000000\r\n"
            b"T|37|30|30|309_F|0.000000_PWM|0.000000\r\n"
            b"T|38|30|30|309_F|0.000000_PWM|0.000000\r\n"
            b"T|59|31|31|309_F|0.000000_PWM|0.000000\r\n"
        )
        frames = parser.feed(stream)
        self.assertEqual(
            [frame.numeric_by_name()["temperature_1_raw"] for frame in frames],
            [56.0, 37.0, 38.0, 59.0],
        )


if __name__ == "__main__":
    unittest.main()
