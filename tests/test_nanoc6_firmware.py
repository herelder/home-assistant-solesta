"""Execute the actual firmware lambdas with deterministic UART and clocks."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).parents[1]
FIRMWARE = ROOT / "esphome/public/solesta-nanoc6.yaml"


def firmware_lambda(marker):
    source = FIRMWARE.read_text().split(marker, 1)[1]
    match = re.search(r"^([ \t]*)(?:- )?lambda: \|-\n", source, re.MULTILINE)
    if match is None:
        raise AssertionError(f"Missing lambda after {marker}")
    indentation = len(match[1])
    lines = []
    for line in source[match.end():].splitlines():
        if line.strip() and len(line) - len(line.lstrip()) <= indentation:
            break
        lines.append(line)
    return textwrap.dedent("\n".join(lines))


class NanoC6FirmwareTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("c++"), "C++ compiler not installed")
    def test_actual_parser_and_report_timestamp_lambdas(self):
        source = (ROOT / "tests/fixtures/nanoc6_firmware_harness.cpp").read_text()
        for name, marker in {
            "REPORT": "    id: last_report\n",
            "PARSER": "  - interval: 20ms\n",
            "VALID": "    id: data_valid\n",
            "AGE": "    id: data_age_seconds\n",
        }.items():
            source = source.replace(f"/* {name}_LAMBDA */", firmware_lambda(marker))
        with tempfile.TemporaryDirectory(prefix="solesta-firmware-test-") as directory:
            path = Path(directory)
            (path / "test.cpp").write_text(source)
            build = subprocess.run(
                ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                 str(path / "test.cpp"), "-o", str(path / "test")],
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(path / "test")], capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("firmware report scenarios passed", run.stdout)
