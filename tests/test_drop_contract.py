"""Tests for the generic drop() runtime contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


ROOT = Path(__file__).parents[1] / "custom_components" / "solesta"
PACKAGE = "drop_contract_test"
package = ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package

description = ModuleType(f"{PACKAGE}.description")


class EntityType:
    SENSOR = "sensor"
    SWITCH = "switch"


description.EntityType = EntityType
sys.modules[description.__name__] = description

compiled_inputs: list[dict[str, str]] = []
compiler = ModuleType(f"{PACKAGE}.compile")
compiler.CompiledSourceExpressions = object


def compile_source_expressions(expressions):
    compiled_inputs.append(dict(expressions))
    return SimpleNamespace(source_keys=frozenset({"provider_value"}))


compiler.compile_source_expressions = compile_source_expressions
sys.modules[compiler.__name__] = compiler

thetruth = ModuleType(f"{PACKAGE}.thetruth")
thetruth.DESCRIPTIONS = [
    SimpleNamespace(key="normal", entity_type=EntityType.SENSOR),
    SimpleNamespace(key="control", entity_type=EntityType.SWITCH),
    SimpleNamespace(key="external", entity_type=EntityType.SENSOR),
]
sys.modules[thetruth.__name__] = thetruth

spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.runtime_configuration",
    ROOT / "runtime_configuration.py",
)
runtime_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime_module
spec.loader.exec_module(runtime_module)


class DropContractTests(unittest.TestCase):
    def setUp(self):
        compiled_inputs.clear()

    def test_drop_is_stored_but_not_compiled(self):
        runtime = runtime_module.RuntimeConfiguration.compile(
            {
                "normal": "provider_value",
                "control": "False",
                "external": "  drop()  ",
            }
        )
        self.assertEqual(runtime.dropped_keys, {"external"})
        self.assertEqual(runtime.evaluated_keys, {"normal", "control"})
        self.assertEqual(
            compiled_inputs[-1],
            {"normal": "provider_value", "control": "False"},
        )
        self.assertEqual(
            runtime.stored_source_expressions()["external"],
            "  drop()  ",
        )

    def test_replacing_drop_with_expression_restores_compilation(self):
        runtime = runtime_module.RuntimeConfiguration.compile(
            {
                "normal": "provider_value",
                "control": "True",
                "external": "drop()",
            }
        ).with_source_expression("external", "provider_value")
        self.assertFalse(runtime.dropped_keys)
        self.assertEqual(
            set(compiled_inputs[-1]),
            {"normal", "control", "external"},
        )

    def test_switch_source_is_a_boolean_literal(self):
        with self.assertRaisesRegex(ValueError, "must be True or False"):
            runtime_module.RuntimeConfiguration.compile(
                {
                    "normal": "provider_value",
                    "control": "provider_value > 0",
                    "external": "drop()",
                }
            )


if __name__ == "__main__":
    unittest.main()
