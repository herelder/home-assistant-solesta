"""Golden and negative-fixture tests for generate_thetruth.py."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPOSITORY = Path(__file__).parents[1]
COMPONENT = REPOSITORY / "custom_components" / "solesta"
TOOLS = REPOSITORY / "tools"
FIXTURES = Path(__file__).with_name("fixtures")

spec = importlib.util.spec_from_file_location(
    "generate_thetruth_test",
    TOOLS / "generate_thetruth.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load generate_thetruth.py")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _rows(raw_rows):
    return generator.normalize_rows(
        (row.pop("row_number"), row) for row in deepcopy(raw_rows)
    )


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid = _fixture("entity_descriptions_v5_valid.json")
        cls.invalid = _fixture("entity_descriptions_v5_invalid.json")
        cls.compiler = generator.load_production_compiler(
            COMPONENT
        )

    def _validate(self, raw_rows, translations=None):
        rows = _rows(raw_rows)
        generator.validate_rows(
            rows,
            compile_expressions=type(self).compiler,
            translations=[
                (
                    Path("fixture.json"),
                    translations or self.valid["translations"],
                )
            ],
        )
        return rows

    def test_golden_output(self):
        rows = self._validate(self.valid["rows"])
        actual = generator.render_descriptions(
            rows,
            "EntityDescriptions_fixture.xlsx",
            source_sha256="source-hash",
            generator_sha256="generator-hash",
            catalog_revision=generator.CATALOG_REVISION,
        )
        expected = (
            FIXTURES / "entity_descriptions_v5_golden.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_negative_fixtures_fail_before_output(self):
        for name, mutation in self.invalid.items():
            with self.subTest(name=name):
                rows = deepcopy(self.valid["rows"])
                if name.startswith("duplicate_"):
                    duplicate = deepcopy(rows[0])
                    duplicate["row_number"] = 5
                    duplicate["key"] = "second_entity"
                    duplicate["translation_key"] = "second_entity"
                    duplicate["unique_id"] = "second_uid"
                    duplicate["entity_id"] = "number.second_entity"
                    duplicate[mutation["field"]] = mutation["value"]
                    rows.append(duplicate)
                    translations = deepcopy(self.valid["translations"])
                    translations["entity"]["number"]["second_entity"] = {
                        "name": "Second entity"
                    }
                else:
                    rows[0][mutation["field"]] = mutation["value"]
                    translations = self.valid["translations"]
                with self.assertRaises(generator.WorkbookValidationError):
                    self._validate(rows, translations)

    def test_missing_translation_is_rejected(self):
        with self.assertRaises(generator.WorkbookValidationError):
            self._validate(self.valid["rows"], {"entity": {}})

    def test_round_precision_must_fit_runtime_safety_limit(self):
        rows = deepcopy(self.valid["rows"])
        rows[0]["default_source_expression"] = "round(15, 16)"
        rows[0]["suggested_display_precision"] = 16
        with self.assertRaises(generator.WorkbookValidationError):
            self._validate(rows)

    def test_expression_commas_get_readability_spaces(self):
        self.assertEqual(
            generator._expression(
                "delay_zone(last_report,2*60+30,10*60)", row=2
            ),
            "delay_zone(last_report, 2*60+30, 10*60)",
        )
        self.assertEqual(
            generator._expression('join_lines("a,b",alerts)', row=2),
            'join_lines("a,b", alerts)',
        )

    def test_generate_does_not_replace_output_after_validation_failure(self):
        raw_rows = deepcopy(self.valid["rows"])
        raw_rows[0]["default_source_expression"] = "round("
        rows = _rows(raw_rows)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "thetruth.py"
            output.write_text("original\n", encoding="utf-8")
            with (
                patch.object(
                    generator, "load_workbook_rows", return_value=rows
                ),
                patch.object(
                    generator,
                    "load_translation_files",
                    return_value=[
                        (Path("fixture.json"), self.valid["translations"])
                    ],
                ),
                self.assertRaises(generator.WorkbookValidationError),
            ):
                generator.generate(
                    Path("invalid.xlsx"),
                    output,
                    [Path("fixture.json")],
                    integration_dir=COMPONENT,
                )

            self.assertEqual(output.read_text(encoding="utf-8"), "original\n")

    def test_canonical_workbook_has_revision_and_required_key_order(self):
        rows = generator.load_workbook_rows(
            TOOLS
            / "sources"
            / "EntityDescriptions.xlsx"
        )
        self.assertEqual(
            tuple(row["key"] for row in rows), generator.EXPECTED_KEYS
        )

    def test_old_catalog_revision_is_rejected(self):
        rows = generator.load_workbook_rows(
            TOOLS
            / "sources"
            / "EntityDescriptions.xlsx"
        )
        with self.assertRaises(generator.WorkbookValidationError):
            generator._validate_catalog(generator.CATALOG_REVISION - 1, rows)

    def test_incomplete_catalog_is_rejected(self):
        rows = generator.load_workbook_rows(
            TOOLS
            / "sources"
            / "EntityDescriptions.xlsx"
        )
        with self.assertRaises(generator.WorkbookValidationError):
            generator._validate_catalog(generator.CATALOG_REVISION, rows[:-1])


if __name__ == "__main__":
    unittest.main()
