"""Tests for the generated side-by-side Solesta Lab package."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


REPOSITORY = Path(__file__).parents[1]
COMPONENT = REPOSITORY / "custom_components" / "solesta"
TOOLS = REPOSITORY / "tools"
spec = importlib.util.spec_from_file_location(
    "lab_build_test",
    TOOLS / "build_lab.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load tools/build_lab.py")
lab_build = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lab_build
spec.loader.exec_module(lab_build)


def _tree_snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def _literal_assignments(content: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    for node in ast.parse(content).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            try:
                result[target.id] = ast.literal_eval(node.value)
            except (TypeError, ValueError):
                pass
    return result


class LabBuildTests(unittest.TestCase):
    def test_render_is_deterministic_and_does_not_change_source(self):
        before = _tree_snapshot(COMPONENT)
        first = lab_build.render_lab_package()
        second = lab_build.render_lab_package()
        self.assertEqual(first, second)
        self.assertEqual(_tree_snapshot(COMPONENT), before)
        self.assertEqual(set(first), set(before) | {Path("lab_build.py")})

    def test_manifest_and_build_metadata_identify_the_lab(self):
        package = lab_build.render_lab_package()
        source_manifest = json.loads((COMPONENT / "manifest.json").read_bytes())
        manifest = json.loads(package[Path("manifest.json")])
        self.assertEqual(manifest["domain"], "solesta_lab")
        self.assertEqual(manifest["name"], "Solesta Lab")
        self.assertEqual(manifest["version"], source_manifest["version"])

        const = _literal_assignments(package[Path("const.py")])
        metadata = _literal_assignments(package[Path("lab_build.py")])
        self.assertEqual(const["DOMAIN"], "solesta_lab")
        self.assertEqual(metadata["CANONICAL_DOMAIN"], "solesta")
        self.assertEqual(metadata["LAB_DOMAIN"], "solesta_lab")
        self.assertEqual(metadata["SOURCE_VERSION"], source_manifest["version"])
        self.assertRegex(metadata["SOURCE_TREE_SHA256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            metadata["LAB_BUILD_ID"],
            metadata["SOURCE_TREE_SHA256"][:12],
        )

    def test_isolated_frontend_is_started_but_archiving_is_not(self):
        package = lab_build.render_lab_package()
        setup = package[Path("__init__.py")].decode("utf-8")
        self.assertIn("await async_setup_frontend", setup)
        self.assertNotIn("await async_setup_archiving", setup)

        metadata = _literal_assignments(package[Path("lab_build.py")])
        self.assertTrue(metadata["FRONTEND_ENABLED"])
        self.assertFalse(metadata["ARCHIVING_ENABLED"])
        self.assertIn(
            '"lab_build": {',
            package[Path("diagnostics.py")].decode("utf-8"),
        )

    def test_lab_frontend_uses_an_isolated_card_identity(self):
        package = lab_build.render_lab_package()
        frontend = package[Path("frontend.py")].decode("utf-8")
        card = package[Path("frontend/solesta-status-card.js")].decode("utf-8")

        self.assertIn('CARD_PATH = f"/{DOMAIN}/solesta-status-card.js"', frontend)
        self.assertIn("from .lab_build import LAB_BUILD_ID", frontend)
        self.assertIn(
            'f"{CARD_PATH}?v={integration.version}&build={LAB_BUILD_ID}"',
            frontend,
        )
        self.assertIn('domain === "solesta"', card)
        self.assertIn('`${domain.replaceAll("_", "-")}-status-card`', card)

    def test_every_generated_python_file_parses(self):
        package = lab_build.render_lab_package()
        for relative, content in package.items():
            if relative.suffix == ".py":
                with self.subTest(path=relative):
                    ast.parse(content, filename=relative.as_posix())

    def test_writer_replaces_a_stale_lab_package(self):
        package = lab_build.render_lab_package()
        with TemporaryDirectory() as directory:
            output = Path(directory) / "custom_components" / "solesta_lab"
            output.mkdir(parents=True)
            (output / "stale.txt").write_text("stale", encoding="utf-8")

            lab_build._write_package(package, output)

            self.assertFalse((output / "stale.txt").exists())
            self.assertEqual(_tree_snapshot(output), package)

    def test_writer_rejects_non_lab_target_name(self):
        package = lab_build.render_lab_package()
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                lab_build.LabBuildError,
                "must be named solesta_lab",
            ):
                lab_build._write_package(package, Path(directory) / "solesta")

    def test_writer_rejects_live_home_assistant_target(self):
        with self.assertRaisesRegex(
            lab_build.LabBuildError,
            "never writes directly to live HA config",
        ):
            lab_build._validate_output_path(
                Path("/Volumes/config/custom_components/solesta_lab")
            )

    def test_writer_rejects_generated_tree_beside_canonical_source(self):
        with self.assertRaisesRegex(
            lab_build.LabBuildError,
            "must stay below work",
        ):
            lab_build._validate_output_path(
                REPOSITORY / "custom_components" / "solesta_lab"
            )


if __name__ == "__main__":
    unittest.main()
