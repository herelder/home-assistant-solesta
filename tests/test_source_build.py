"""Release-contract tests for the canonical workbook build."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import subprocess
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


REPOSITORY = Path(__file__).parents[1]
COMPONENT = REPOSITORY / "custom_components" / "solesta"
TOOLS = REPOSITORY / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("source_build_test", TOOLS / "build.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load tools/build.py")
source_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_build)


class SourceBuildTests(unittest.TestCase):
    def test_canonical_sources_are_byte_equal_to_runtime(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "build.py"), "--check"],
            cwd=REPOSITORY,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK thetruth.py", result.stdout)
        self.assertIn("OK provider_defaults.py", result.stdout)

    def test_generated_headers_contain_source_and_generator_hashes(self):
        for path in (
            COMPONENT / "thetruth.py",
            COMPONENT / "provider_defaults.py",
        ):
            header = path.read_text(encoding="utf-8").split('"""', 2)[1]
            self.assertIn("Source SHA-256: ", header)
            self.assertIn("Generator SHA-256: ", header)

    def test_check_reports_drift_without_changing_the_target(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "generated.py"
            target.write_text("current\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                matches = source_build._check({target: "expected\n"})
            self.assertFalse(matches)
            self.assertIn("DRIFT", output.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "current\n")

    def test_atomic_writer_replaces_all_staged_outputs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.py"
            second = root / "second.py"
            first.write_text("old first\n", encoding="utf-8")
            second.write_text("old second\n", encoding="utf-8")
            source_build._write_atomically(
                {first: "new first\n", second: "new second\n"}
            )
            self.assertEqual(first.read_text(encoding="utf-8"), "new first\n")
            self.assertEqual(second.read_text(encoding="utf-8"), "new second\n")


if __name__ == "__main__":
    unittest.main()
