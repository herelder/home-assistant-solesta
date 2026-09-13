"""Validation tests for the generated immutable REST preset contract."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPOSITORY = Path(__file__).parents[1]
TOOLS = REPOSITORY / "tools"
WORKBOOK = TOOLS / "sources" / "ProviderDefaults.xlsx"

spec = importlib.util.spec_from_file_location(
    "generate_provider_defaults_test",
    TOOLS / "generate_provider_defaults.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load generate_provider_defaults.py")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class ProviderGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flow_rows, cls.key_rows = generator._load_source_rows(WORKBOOK)

    def _rows(self):
        return [list(row) for row in deepcopy(self.flow_rows)]

    @staticmethod
    def _row(rows, flow_name):
        return next(row for row in rows if row[2] == flow_name)

    def _assert_rejected(self, rows):
        with (
            patch.object(
                generator,
                "_load_source_rows",
                return_value=(rows, deepcopy(self.key_rows)),
            ),
            self.assertRaises(generator.ProviderWorkbookError),
        ):
            generator.load_provider_default(WORKBOOK)

    def test_canonical_workbook_builds_normalized_execution_contract(self):
        contract = generator.load_provider_default(WORKBOOK)
        self.assertEqual(contract["base_url"], "https://dashboard.solesta.nl")
        self.assertEqual(contract["total_timeout_seconds"], 30)
        self.assertNotIn("setup_httpsession_flow", contract["flows"])
        self.assertEqual(
            contract["flows"]["connect_flow"]["bindings"],
            ["password", "userid"],
        )
        self.assertEqual(
            contract["flows"]["system_status_flow"]["bindings"],
            ["source_system_id"],
        )

    def test_unsafe_or_incomplete_contracts_fail_before_generation(self):
        mutations = {
            "origin": lambda rows: self._row(rows, "setup_httpsession_flow").__setitem__(
                5, "https://example.invalid"
            ),
            "login_assertion": lambda rows: self._row(rows, "connect_flow").__setitem__(
                12, None
            ),
            "query_in_path": lambda rows: self._row(rows, "system_status_flow").__setitem__(
                8, "/api/systems/{source_system_id}/live?unsafe=1"
            ),
            "non_idempotent_read": lambda rows: self._row(rows, "profile_flow").__setitem__(
                7, "POST"
            ),
            "duplicate_status": lambda rows: self._row(rows, "disconnect_flow").__setitem__(
                10, "[200,200]"
            ),
            "duplicate_extract": lambda rows: self._row(rows, "systems_flow").__setitem__(
                11, '["coupled_systems","coupled_systems"]'
            ),
            "partial_json_placeholder": lambda rows: self._row(rows, "connect_flow").__setitem__(
                9, '{"email":"prefix-{userid}","password":"{password}"}'
            ),
            "request_session_field": lambda rows: self._row(rows, "profile_flow").__setitem__(
                5, "https://dashboard.solesta.nl"
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                rows = self._rows()
                mutate(rows)
                self._assert_rejected(rows)

    def test_extra_flow_step_is_rejected_before_generation(self):
        rows = self._rows()
        extra = deepcopy(self._row(rows, "connect_flow"))
        extra[3] = 1
        rows.append(extra)
        self._assert_rejected(rows)


if __name__ == "__main__":
    unittest.main()
