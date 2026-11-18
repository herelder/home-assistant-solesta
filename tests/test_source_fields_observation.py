"""Contracts for qualified source names and shared provider observation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections.abc import Collection, Mapping
import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "solesta_source_contract"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


observation = _load("observation")
source_fields = _load("source_fields")
_load("exceptions")
provider_module = _load("provider")
SourceObservation = observation.SourceObservation
SourceFieldError = source_fields.SourceFieldError
SourceFieldTable = source_fields.SourceFieldTable
canonical_source_name = source_fields.canonical_source_name
decode_canonical_source_name = source_fields.decode_canonical_source_name
flatten_source_mapping = source_fields.flatten_source_mapping


UTC = timezone.utc
T0 = datetime(2026, 10, 29, 12, tzinfo=UTC)


class SourceFieldTests(unittest.TestCase):
    def test_documented_paths_are_reversible(self):
        cases = {
            ("aaaa", "bbbb", "cccc"): "cccc__bbbb__aaaa",
            ("sensor", "boiler-1", "state"): "state__boiler_02D1__sensor",
            ("a", "", "c"): "c___0E__a",
            ("temp__raw",): "temp_05F_05Fraw",
            ("1", "_0", "é"): "_0C3_0A9___05F0___031",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(canonical_source_name(path), expected)
                self.assertEqual(decode_canonical_source_name(expected), path)

    def test_nested_mappings_qualify_but_lists_remain_opaque(self):
        values = flatten_source_mapping(
            {"metrics": {"temperature": 42}, "records": [{"x": 1}]}
        )
        self.assertEqual(
            values,
            {"temperature__metrics": 42, "records": [{"x": 1}]},
        )

    def test_shortest_unique_binding_and_absolute_anchor(self):
        table = SourceFieldTable(
            {"cccc__bbbb__aaaa", "other__bbbb__aaaa"}
        )
        self.assertEqual(table.resolve("cccc"), "cccc__bbbb__aaaa")
        self.assertEqual(
            table.resolve("cccc__bbbb"), "cccc__bbbb__aaaa"
        )
        self.assertEqual(
            table.resolve("_0R__cccc__bbbb__aaaa"),
            "cccc__bbbb__aaaa",
        )
        with self.assertRaises(SourceFieldError):
            SourceFieldTable({"cccc", "cccc__bbbb"}).resolve("cccc")
        self.assertEqual(table.resolve("unknown", optional=True), "unknown")
        with self.assertRaises(SourceFieldError):
            table.resolve("unknown")
        self.assertEqual(
            table.resolve("_0R__unknown", optional=True), "unknown"
        )


class ObservationTests(unittest.TestCase):
    def test_canonical_event_sequence(self):
        observed = SourceObservation()
        empty = observed.snapshot({"used", "optional_used"})
        self.assertIsNone(empty.last_report)
        self.assertIsNone(empty.last_update)

        observed.observe_event("used", "A", T0)
        first = observed.snapshot({"used", "optional_used"})
        self.assertEqual(first.last_report, T0)
        self.assertEqual(first.last_update, T0)

        observed.observe_event("used", "A", T0 + timedelta(seconds=1))
        same = observed.snapshot({"used", "optional_used"})
        self.assertEqual(same.last_report, T0 + timedelta(seconds=1))
        self.assertEqual(same.last_update, T0)

        observed.observe_event("unused", "X", T0 + timedelta(seconds=2))
        unused = observed.snapshot({"used", "optional_used"})
        self.assertEqual(unused.last_report, T0 + timedelta(seconds=2))
        self.assertEqual(unused.last_update, T0)

        observed.observe_event("unused", "Y", T0 + timedelta(seconds=3))
        still_unused = observed.snapshot({"used", "optional_used"})
        self.assertEqual(still_unused.last_report, T0 + timedelta(seconds=3))
        self.assertEqual(still_unused.last_update, T0)

        observed.observe_event("optional_used", 1, T0 + timedelta(seconds=4))
        optional = observed.snapshot({"used", "optional_used"})
        self.assertEqual(optional.last_report, T0 + timedelta(seconds=4))
        self.assertEqual(optional.last_update, T0 + timedelta(seconds=4))

        observed.observe_event("used", "B", T0 + timedelta(seconds=5))
        changed = observed.snapshot({"used", "optional_used"})
        self.assertEqual(changed.last_report, T0 + timedelta(seconds=5))
        self.assertEqual(changed.last_update, T0 + timedelta(seconds=5))

        # A failed attempt is represented by no accepted report at all.
        self.assertEqual(
            observed.snapshot({"used", "optional_used"}),
            changed,
        )

        observed.observe_event("used", "B", T0 + timedelta(seconds=7))
        replay = observed.snapshot({"used", "optional_used"})
        self.assertEqual(replay.last_report, T0 + timedelta(seconds=7))
        self.assertEqual(replay.last_update, T0 + timedelta(seconds=5))

        observed.observe_event("used", "C", T0 + timedelta(seconds=8))
        final = observed.snapshot({"used", "optional_used"})
        self.assertEqual(final.last_report, T0 + timedelta(seconds=8))
        self.assertEqual(final.last_update, T0 + timedelta(seconds=8))

        restarted = SourceObservation().snapshot({"used", "optional_used"})
        self.assertIsNone(restarted.last_report)
        self.assertIsNone(restarted.last_update)

    def test_each_referenced_keyset_has_its_own_last_update(self):
        observed = SourceObservation()
        observed.observe_event("first", "A", T0)
        observed.observe_event("second", "B", T0 + timedelta(seconds=1))

        first = observed.snapshot({"first"})
        second = observed.snapshot({"second"})
        both = observed.snapshot({"first", "second"})

        self.assertEqual(first.last_report, second.last_report)
        self.assertEqual(first.last_update, T0)
        self.assertEqual(second.last_update, T0 + timedelta(seconds=1))
        self.assertEqual(both.last_update, T0 + timedelta(seconds=1))

    def test_snapshot_presence_and_type_sensitive_comparison(self):
        observed = SourceObservation()
        observed.observe_snapshot(
            {"value": True, "nan": float("nan")}, T0
        )
        observed.observe_snapshot(
            {"value": 1, "nan": float("nan")},
            T0 + timedelta(seconds=1),
        )
        snapshot = observed.snapshot({"value", "nan"})
        self.assertEqual(snapshot.last_update, T0 + timedelta(seconds=1))
        self.assertTrue(math.isnan(snapshot.values["nan"]))

        observed.observe_snapshot(
            {"nan": float("nan")}, T0 + timedelta(seconds=2)
        )
        self.assertEqual(
            observed.snapshot({"value"}).last_update,
            T0 + timedelta(seconds=2),
        )

    def test_all_documented_opaque_equality_cases(self):
        equal_pairs = (
            (
                {"left": 1, "right": [2, {"deep": "value"}]},
                {"right": [2, {"deep": "value"}], "left": 1},
            ),
            (float("nan"), float("nan")),
        )
        changed_pairs = (
            (True, 1),
            ([1, 2], (1, 2)),
            (b"1", "1"),
        )
        for index, (left, right) in enumerate(equal_pairs):
            with self.subTest(kind="equal", index=index):
                observed = SourceObservation()
                observed.observe_event("value", left, T0)
                observed.observe_event(
                    "value", right, T0 + timedelta(seconds=1)
                )
                self.assertEqual(observed.snapshot({"value"}).last_update, T0)
        for index, (left, right) in enumerate(changed_pairs):
            with self.subTest(kind="changed", index=index):
                observed = SourceObservation()
                observed.observe_event("value", left, T0)
                observed.observe_event(
                    "value", right, T0 + timedelta(seconds=1)
                )
                self.assertEqual(
                    observed.snapshot({"value"}).last_update,
                    T0 + timedelta(seconds=1),
                )

    def test_defensive_deep_copy(self):
        raw = {"nested": [1]}
        observed = SourceObservation()
        observed.observe_event("key", raw, T0)
        raw["nested"].append(2)
        self.assertEqual(observed.snapshot({"key"}).values["key"], {"nested": [1]})


class _PullProvider(provider_module.Provider):
    def __init__(self, snapshots):
        super().__init__(provider_id="pull-provider")
        self.snapshots = iter(snapshots)

    async def async_open(self):
        return None

    async def async_connect(self):
        return None

    async def async_disconnect(self):
        return None

    async def async_close(self):
        return None

    async def _async_fetch_profile(self) -> Mapping[str, object]:
        return {"name": "pull"}

    async def _async_fetch_systems(self) -> Collection[str]:
        return ("system",)

    async def _async_fetch_system_status(self, source_system_id, source_keys):
        del source_system_id, source_keys
        return next(self.snapshots)


class PullProviderObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_snapshots_update_report_but_only_used_changes(self):
        provider = _PullProvider(
            (
                {"used": "A", "unused": "X"},
                {"used": "A", "unused": "Y"},
                {"used": "B", "unused": "Y"},
                {"unused": "Y"},
                {"used": "B", "unused": "Y"},
            )
        )
        moments = [T0 + timedelta(seconds=index) for index in range(5)]
        with patch.object(provider_module, "utcnow", side_effect=moments):
            await provider.async_initialize()
            first = await provider.get_system_snapshot(
                "system", {"used"}, {"used"}
            )
            second = await provider.get_system_snapshot(
                "system", {"used"}, {"used"}
            )
            third = await provider.get_system_snapshot(
                "system", {"used"}, {"used"}
            )
            missing = await provider.get_system_snapshot(
                "system", (), {"used"}
            )
            restored = await provider.get_system_snapshot(
                "system", {"used"}, {"used"}
            )

        self.assertEqual(first.last_report, moments[0])
        self.assertEqual(first.last_update, moments[0])
        self.assertGreaterEqual(second.last_report, first.last_report)
        self.assertEqual(second.last_update, first.last_update)
        self.assertEqual(third.last_update, moments[2])
        self.assertEqual(third.values["used"], "B")
        self.assertNotIn("used", missing.values)
        self.assertEqual(missing.last_update, moments[3])
        self.assertEqual(restored.values["used"], "B")
        self.assertEqual(restored.last_update, moments[4])


if __name__ == "__main__":
    unittest.main()
