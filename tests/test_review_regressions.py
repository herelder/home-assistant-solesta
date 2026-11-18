"""Review regressions using the complete generated catalogue and real engine.

Only HA enum containers are replaced; no descriptions, compiler or evaluator
behaviour is stubbed. This keeps the fast suite independent of an HA install.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "solesta_review_contract"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


def load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _enum_modules():
    tree = ast.parse((ROOT / "thetruth.py").read_text())
    fields = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            fields.setdefault(node.value.id, set()).add(node.attr)
    modules = {}
    for location, names in {
        "homeassistant.components.sensor": ("SensorDeviceClass", "SensorStateClass"),
        "homeassistant.components.binary_sensor": ("BinarySensorDeviceClass",),
        "homeassistant.components.number": ("NumberDeviceClass", "NumberMode"),
        "homeassistant.const": ("EntityCategory",),
    }.items():
        module = ModuleType(location)
        for name in names:
            setattr(
                module, name, StrEnum(name, {key: key.lower() for key in fields[name]})
            )
        modules[location] = module
    return modules


with patch.dict(sys.modules, _enum_modules()):
    const = load("const")
    description = load("description")
    catalogue = load("thetruth")
    functions = load("expression_functions")
    compiler = load("compile")
    source_fields = sys.modules[f"{PACKAGE}.source_fields"]
    load("number_validation")
    evaluator = load("evaluator")
    runtime = load("runtime_configuration")

DEFAULTS = {item.key: item.default_source_expression for item in catalogue.DESCRIPTIONS}
NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


class ExpressionErrorLocationTests(unittest.TestCase):
    def test_independent_compile_errors_keep_their_original_fields(self):
        expressions = {
            "syntax": "to_number(",
            "function": "unknown_function(1)",
            "good": "2",
        }
        before = dict(expressions)
        with self.assertRaises(compiler.SourceExpressionValidationError) as caught:
            compiler.compile_source_expressions(expressions)
        errors = caught.exception.errors
        self.assertEqual(set(errors), {"syntax", "function"})
        self.assertIsInstance(errors["syntax"], compiler.SourceExpressionSyntaxError)
        self.assertIsInstance(errors["function"], compiler.SourceExpressionFunctionError)
        self.assertEqual(errors["syntax"].expression_keys, ("syntax",))
        self.assertEqual(expressions, before)

    def test_source_binding_errors_keep_field_and_structured_cause(self):
        with self.assertRaises(compiler.SourceExpressionValidationError) as caught:
            compiler.compile_source_expressions(
                {"missing": "absent", "ambiguous": "state", "invalid": "_0ZZ"},
                available_source_keys={"state__a", "state__b"},
            )
        errors = caught.exception.errors
        self.assertIsInstance(errors["missing"].__cause__, source_fields.SourceFieldUnavailableError)
        self.assertIsInstance(errors["ambiguous"].__cause__, source_fields.SourceFieldAmbiguousError)
        self.assertIsInstance(errors["invalid"].__cause__, source_fields.SourceFieldError)
        self.assertEqual(errors["ambiguous"].expression_keys, ("ambiguous",))

    def test_cycles_identify_only_members_not_downstream_expressions(self):
        with self.assertRaises(compiler.SourceExpressionDependencyError) as caught:
            compiler.compile_source_expressions({
                "a": "b", "b": "a", "downstream": "a + 1", "independent": "2",
            })
        self.assertEqual(caught.exception.expression_keys, ("a", "b"))

    def test_compile_error_does_not_hide_an_independent_cycle(self):
        with self.assertRaises(compiler.SourceExpressionValidationError) as caught:
            compiler.compile_source_expressions({
                "syntax": "to_number(", "a": "b", "b": "a", "downstream": "a",
            })
        self.assertEqual(set(caught.exception.errors), {"syntax", "a", "b"})

    def test_switch_literal_failure_identifies_its_field(self):
        expressions = {**DEFAULTS, "weekly_archive": "not_a_boolean"}
        with self.assertRaises(compiler.SourceExpressionSyntaxError) as caught:
            runtime.RuntimeConfiguration.compile(expressions)
        self.assertEqual(caught.exception.expression_keys, ("weekly_archive",))


class OwnSourceBindingTests(unittest.TestCase):
    def test_own_field_uses_the_same_unique_path_as_explicit_source(self):
        for expression in ("to_number(temp_collector)", "to_number(temp_collector')"):
            with self.subTest(expression=expression):
                compiled = compiler.compile_source_expressions(
                    {"temp_collector": expression},
                    available_source_keys={"temp_collector__metrics"},
                )
                result = evaluator.evaluate_source_expressions(
                    compiled, {"temp_collector__metrics": 42},
                )
                self.assertEqual(result.values["temp_collector"], 42.0)
                self.assertFalse(result.errors)
                self.assertEqual(compiled.source_keys, {"temp_collector__metrics"})
                self.assertEqual(compiled.required_source_keys, compiled.source_keys)
                self.assertEqual(compiled["temp_collector"].expression, expression)
                self.assertFalse(compiled["temp_collector"].dependencies)

    def test_ambiguous_own_source_is_rejected_even_when_nullable(self):
        for expression in ("to_number(temp_collector)", "null(temp_collector)"):
            with self.subTest(expression=expression):
                with self.assertRaises(compiler.SourceExpressionDependencyError) as caught:
                    compiler.compile_source_expressions(
                        {"temp_collector": expression},
                        available_source_keys={"temp_collector", "temp_collector__metrics"},
                    )
                self.assertEqual(caught.exception.expression_keys, ("temp_collector",))
                self.assertIsInstance(
                    caught.exception.__cause__, source_fields.SourceFieldAmbiguousError,
                )

    def test_missing_own_source_is_optional_only_inside_null(self):
        with self.assertRaises(compiler.SourceExpressionDependencyError) as caught:
            compiler.compile_source_expressions(
                {"temp_collector": "to_number(temp_collector)"},
                available_source_keys={"other"},
            )
        self.assertIsInstance(
            caught.exception.__cause__, source_fields.SourceFieldUnavailableError,
        )
        compiled = compiler.compile_source_expressions(
            {"temp_collector": "to_number(null(temp_collector))"},
            available_source_keys={"other"},
        )
        result = evaluator.evaluate_source_expressions(compiled, {})
        self.assertIsNone(result.values["temp_collector"])
        self.assertFalse(result.errors)
        self.assertFalse(compiled.required_source_keys)

    def test_none_own_sources_bind_case_sensitively_and_consumers_stay_entities(self):
        compiled = compiler.compile_source_expressions(
            {"None": "null(None)", "none": "null(none)",
             "consumer": "null(None, none)"},
            available_source_keys={"None__metrics", "none__metrics"},
        )
        result = evaluator.evaluate_source_expressions(
            compiled, {"None__metrics": 7, "none__metrics": 9},
        )
        self.assertEqual(result.values["consumer"], [7, 9])
        self.assertFalse(result.errors)
        self.assertEqual(compiled.source_keys, {"None__metrics", "none__metrics"})
        self.assertEqual(set(compiled["consumer"].dependencies), {"None", "none"})
        with self.assertRaises(compiler.SourceExpressionDependencyError):
            compiler.compile_source_expressions(
                {"a": "null(b)", "b": "null(a)"},
                available_source_keys={"a__metrics", "b__metrics"},
            )


class NullExpressionTests(unittest.TestCase):
    def evaluate(self, expressions, sources=None, fields=None):
        compiled = compiler.compile_source_expressions(
            expressions, available_source_keys=fields
        )
        return compiled, evaluator.evaluate_source_expressions(compiled, sources or {})

    def test_zero_one_and_multiple_arguments_preserve_values_and_types(self):
        for expression, expected in (
            ("null()", None), ("null(3)", 3), ("null(True)", True),
            ('null("text")', "text"), ("null(5 * 2 + 1)", 11.0),
            ('null(to_number("42"))', 42.0), ("null(null())", None),
            ("null(null(3), 4)", [3, 4]),
        ):
            with self.subTest(expression=expression):
                _, result = self.evaluate({"result": expression})
                self.assertEqual(result.values["result"], expected)
                self.assertIs(type(result.values["result"]), type(expected))
                self.assertFalse(result.errors)
        for value in (0, False, "", None, "value", 12.5, [1, 2]):
            with self.subTest(value=value):
                compiled, result = self.evaluate({"result": "null(source)"}, {"source": value})
                self.assertEqual(result.values["result"], value)
                self.assertIs(type(result.values["result"]), type(value))
                self.assertEqual(compiled.required_source_keys, set())
                self.assertEqual(compiled.source_keys, {"source"})
                self.assertFalse(result.errors)
        _, result = self.evaluate(
            {"result": 'null(zero, missing, empty, disabled, 3 + 4)'},
            {"zero": 0, "empty": "", "disabled": False},
        )
        self.assertEqual(result.values["result"], [0, None, "", False, 7.0])
        self.assertFalse(result.errors)

    def test_missing_short_and_absolute_fields_are_allowed_but_ambiguity_is_not(self):
        for expression in ("null(missing)", "null(_0R__missing)"):
            with self.subTest(expression=expression):
                compiled, result = self.evaluate({"result": expression}, fields={"other"})
                self.assertIsNone(result.values["result"])
                self.assertEqual(compiled.source_keys, {"missing"})
                self.assertFalse(compiled.required_source_keys)
                self.assertFalse(result.errors)
        _, result = self.evaluate(
            {"result": "null(temperature)"}, {"temperature__metrics": 42},
            fields={"temperature__metrics"},
        )
        self.assertEqual(result.values["result"], 42)
        with self.assertRaises(compiler.SourceExpressionDependencyError):
            self.evaluate({"result": "null(temperature)"},
                          fields={"temperature", "temperature__metrics"})

    def test_failed_entity_field_does_not_block_nullable_consumer(self):
        compiled, result = self.evaluate(
            {"bad": "1 / 0", "good": "null(bad) or 42", "strict": "bad + 1"}
        )
        self.assertEqual(result.values["good"], 42)
        self.assertNotIn("good", result.errors)
        self.assertIn("bad", result.errors)
        self.assertEqual(result.errors["strict"].category,
                         evaluator.EvaluationErrorCategory.DEPENDENCY_FAILED)
        self.assertIn("bad", compiled.expressions["good"].dependencies)
        self.assertFalse(compiled.expressions["good"].required_dependencies)

    def test_field_is_nullable_only_when_every_reference_is_within_null(self):
        for expressions in (
            {"result": "null(source) + source"},
            {"result": "null(source)", "other": "source"},
        ):
            with self.subTest(expressions=expressions):
                compiled, result = self.evaluate(expressions)
                self.assertEqual(compiled.required_source_keys, {"source"})
                self.assertIn("result" if "other" not in expressions else "other", result.errors)

    def test_field_expressions_keywords_cycles_and_old_helper_are_rejected(self):
        for expression in (
            "null(source > 0)", "null(source + 1)", "null(to_number(source))",
            "null(not source)", "null(source and 1)", "null(null(source))",
            "null(1 + None)", "null(to_number(source'))", "null(value=1)",
            "null(lambda: 1)", "null(unknown_function(1))", "null(source.__class__)",
            "null('x' * 1000000000000000)", "optional(1)",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(compiler.SourceExpressionError):
                    self.evaluate({"result": expression})
        with self.assertRaises(compiler.SourceExpressionDependencyError):
            self.evaluate({"a": "null(b)", "b": "null(a)"})

    def test_field_free_expression_errors_are_not_silenced(self):
        for expression in ("null(1 / 0)", 'null(to_number("bad"))'):
            with self.subTest(expression=expression):
                _, result = self.evaluate({"result": expression})
                self.assertIn("result", result.errors)
        _, result = self.evaluate({"result": "to_number(null(missing))"}, fields={"other"})
        self.assertIsNone(result.values["result"])
        self.assertFalse(result.errors)

    def test_none_spellings_are_case_sensitive_fields_not_null_literals(self):
        compiled, result = self.evaluate(
            {"upper": "None", "lower": "none", "text": '\"None\"'},
            {"None": 17, "none": "lower field"}, fields={"None", "none"},
        )
        self.assertEqual(compiled.source_keys, {"None", "none"})
        self.assertEqual(compiled.required_source_keys, {"None", "none"})
        self.assertEqual(result.values, {"upper": 17, "lower": "lower field", "text": "None"})
        self.assertFalse(result.errors)
        _, missing = self.evaluate({"upper": "None", "lower": "none"})
        self.assertEqual(set(missing.errors), {"upper", "lower"})
        compiled, guarded = self.evaluate({"result": "null(None, none)"}, fields={"other"})
        self.assertEqual(guarded.values["result"], [None, None])
        self.assertEqual(compiled.source_keys, {"None", "none"})
        self.assertFalse(guarded.errors)
        for name in ("None", "none"):
            with self.subTest(name=name):
                with self.assertRaises(compiler.SourceExpressionDependencyError):
                    self.evaluate({"result": name}, fields={"other"})
        _, entities = self.evaluate({"None": "7", "none": "8", "result": "null(None, none)"})
        self.assertEqual(entities.values["result"], [7, 8])
        _, explicit = self.evaluate({"None": "null()", "result": "null(None')"}, {"None": "raw"})
        self.assertEqual(explicit.values["result"], "raw")


class ProviderTimestampExpressionTests(unittest.TestCase):
    def evaluate(self, expressions, sources=None):
        compiled = compiler.compile_source_expressions(expressions)
        return compiled, evaluator.evaluate_source_expressions(
            compiled, sources or {}
        )

    def test_context_functions_are_not_source_keys(self):
        compiled = compiler.compile_source_expressions(
            {"last_report": "last_report()"}
        )
        self.assertEqual(compiled.source_keys, frozenset())
        result = evaluator.evaluate_source_expressions(
            compiled,
            {},
            evaluator.EvaluationContext(
                last_report=NOW,
                last_update=NOW - timedelta(seconds=1),
            ),
        )
        self.assertEqual(result.values["last_report"], NOW)

    def test_context_functions_require_zero_arguments(self):
        for expression in ("last_report(1)", "last_update(value=1)"):
            with self.subTest(expression=expression):
                with self.assertRaises(compiler.SourceExpressionFunctionError):
                    compiler.compile_source_expressions({"result": expression})

    def test_qualified_names_bind_at_compile_time(self):
        compiled = compiler.compile_source_expressions(
            {"result": "temperature"},
            available_source_keys={"temperature__metrics"},
        )
        self.assertEqual(
            compiled.source_keys, frozenset({"temperature__metrics"})
        )
        with self.assertRaises(compiler.SourceExpressionDependencyError):
            compiler.compile_source_expressions(
                {"result": "temperature"},
                available_source_keys={
                    "temperature",
                    "temperature__metrics",
                },
            )

    def test_binary_null_is_unknown_without_a_type_error(self):
        _, result = self.evaluate({"status_reporting": "null()"})
        self.assertIsNone(result.values["status_reporting"])
        self.assertFalse(result.errors)

    def test_nullable_numeric_entity_can_temporarily_be_unknown(self):
        _, result = self.evaluate({"volume_tank": "to_number(null(missing))"})
        self.assertIsNone(result.values["volume_tank"])
        self.assertFalse(result.errors)


class CompleteCatalogueAlertTests(unittest.TestCase):
    def evaluate(self, **changes):
        values = {
            "last_update": NOW.isoformat(),
            "temp1": 40,
            "temp2": 40,
            "temp3": 30,
            "temp4": 20,
            "pump": 0,
            **changes,
        }
        config = runtime.RuntimeConfiguration.compile(DEFAULTS)
        raw_report = values.get("last_update")
        report_time = (
            datetime.fromisoformat(raw_report)
            if isinstance(raw_report, str)
            else raw_report
        )
        with patch.object(functions, "_utc_now", return_value=NOW):
            result = evaluator.evaluate_source_expressions(
                config.compiled_source_expressions,
                values,
                evaluator.EvaluationContext(
                    last_report=report_time,
                    last_update=report_time,
                ),
            )
        return config, result

    def test_full_catalogue_reports_danger_with_an_unknown_or_malformed_pump(self):
        for pump in (None, "broken"):
            with self.subTest(pump=pump):
                config, result = self.evaluate(temp1=250, pump=pump)
                alerts = [
                    json.loads(item)
                    for item in functions.split_records(result.values["alerts_system"])
                ]
                self.assertEqual(
                    alerts,
                    [
                        {
                            "type": "collector_hot",
                            "translation_key": "alert_collector_danger",
                            "translation_placeholders": {
                                "temperature": "250",
                            },
                            "severity": "danger",
                        }
                    ],
                )
                self.assertIsNone(result.values["state_pump"])
                self.assertNotIn("alerts_system", result.errors)
                self.assertNotIn("alerts", config.required_source_keys)

    def test_offline_alert_does_not_require_valid_temperature_or_pump(self):
        _, result = self.evaluate(
            last_update=(NOW - timedelta(seconds=601)).isoformat(),
            temp1="broken",
            pump=None,
        )
        self.assertFalse(result.values["status_reporting"])
        self.assertEqual(json.loads(result.values["alerts_system"])["type"], "offline")
        self.assertIn("temp_collector", result.errors)
        self.assertNotIn("alerts_system", result.errors)

    def test_missing_report_is_unknown_and_does_not_poison_alerts(self):
        _, result = self.evaluate(last_update=None)
        self.assertIsNone(result.values["report_delay"])
        self.assertIsNone(result.values["status_reporting"])
        self.assertEqual(result.values["alerts_system"], "")
        self.assertFalse(result.errors)

    def test_unused_provider_alerts_are_ignored_by_catalogue_default(self):
        alert = {"type": "sensor_fault", "message": "broken", "severity": "error"}
        config, result = self.evaluate(alerts=[alert])
        self.assertNotIn("alerts", config.required_source_keys)
        self.assertEqual(result.values["alerts_system"], "")


class ProductionExpressionTests(unittest.TestCase):
    def test_unmodified_023_catalogue_still_uses_raw_time_and_source_alerts(self):
        stored = json.loads((Path(__file__).parent / "fixtures" /
                             "solesta_023_source_expressions.json").read_text())
        config = runtime.RuntimeConfiguration.compile(stored)
        alerts = [
            {"Type": "pump_wrong", "Message": "Line 1\nLine 2", "Severity": "warning"},
            {"Type": "note", "Message": "Retained source text", "Severity": "info"},
        ]
        with patch.object(functions, "_utc_now", return_value=NOW):
            result = evaluator.evaluate_source_expressions(
                config.compiled_source_expressions,
                {"last_update": NOW.isoformat(), "temp1": 40, "temp2": 40,
                 "temp3": 30, "temp4": 20, "pump": 50,
                 "status": "online", "alerts": alerts},
                evaluator.EvaluationContext(last_report=NOW - timedelta(days=1)),
            )
        self.assertFalse(result.errors)
        self.assertEqual(result.values["last_report"], NOW)
        self.assertTrue(result.values["status_reporting"])
        self.assertTrue(result.values["state_pump"])
        self.assertEqual(result.values["temp_reserved"], 20)
        self.assertEqual(result.values["energy_tank_mj"], 9.6278)
        self.assertEqual(result.values["energy_tank_kwh"], 2.674)
        self.assertEqual(functions.split_records(result.values["alerts_system"]),
                         [str(item) for item in alerts])
        self.assertEqual(config.stored_source_expressions(), stored)


class RecordSplitterTests(unittest.TestCase):
    def test_single_long_json_with_unicode_line_separators_stays_one_record(self):
        for separator in ("\u2028", "\u2029", "\u0085"):
            with self.subTest(separator=repr(separator)):
                alert = {
                    "type": "sensor_fault",
                    "message": "x" * 260 + separator + "tail",
                    "severity": "error",
                }
                raw = json.dumps(alert, ensure_ascii=False)
                self.assertEqual(functions.split_records(raw), [raw])
                self.assertEqual(functions.join_lines(raw), raw)

    def test_only_four_grouped_solar_alert_inputs_are_supported(self):
        with self.assertRaises(TypeError):
            functions.solar_thermal_alerts([True, False, 40, 40, ""], 90, 200, 10, 10)
        with self.assertRaises(TypeError):
            functions.solar_thermal_alerts(True, False, 40, 40, 90, 200, 10, 10, "")
        for expression in (
            "solar_thermal_alerts(null(True, False, 40, 40, alerts), 90, 200, 10, 10)",
            "solar_thermal_alerts(True, False, 40, 40, 90, 200, 10, 10, alerts)",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(compiler.SourceExpressionFunctionError):
                    compiler.compile_source_expressions({"alerts_system": expression})

    def test_record_separator_and_legacy_cr_lf_are_distinct(self):
        self.assertEqual(functions.split_records("a\x1eb\nc"), ["a", "b\nc"])
        self.assertEqual(functions.split_records("a\r\nb\rc\nd"), ["a", "b", "c", "d"])
