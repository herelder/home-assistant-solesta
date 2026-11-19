"""Pure contract tests for the version-1 provider/configuration model."""

from __future__ import annotations

import asyncio
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


INTEGRATION = Path(
    os.environ.get(
        "SOLESTA_INTEGRATION_ROOT",
        Path(__file__).parents[1] / "custom_components" / "solesta",
    )
)
EXPECTED_PRODUCT_VERSION = os.environ.get(
    "SOLESTA_EXPECTED_PRODUCT_VERSION", "1.0.0"
)
EXPECTED_CONFIG_ENTRY_MINOR_VERSION = int(
    os.environ.get("SOLESTA_EXPECTED_CONFIG_MINOR_VERSION", "9")
)
PACKAGE = "solesta_test"


def _load(short_name: str):
    full_name = f"{PACKAGE}.{short_name}"
    spec = importlib.util.spec_from_file_location(
        full_name,
        INTEGRATION / f"{short_name}.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {short_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _load_as(short_name: str, source_name: str):
    """Load one production module under a second test-only module name."""
    full_name = f"{PACKAGE}.{short_name}"
    spec = importlib.util.spec_from_file_location(
        full_name,
        INTEGRATION / f"{source_name}.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {source_name} as {short_name}")
    module = importlib.util.module_from_spec(spec)
    if source_name == "__init__":
        # Treat the integration package initializer as a module inside the
        # existing test package so its relative imports reuse our HA doubles.
        module.__package__ = PACKAGE
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


package = ModuleType(PACKAGE)
package.__path__ = [str(INTEGRATION)]
sys.modules[PACKAGE] = package

aiohttp = ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientSession = object
aiohttp.CookieJar = lambda **kwargs: SimpleNamespace(**kwargs)
aiohttp.ClientTimeout = lambda **kwargs: SimpleNamespace(**kwargs)
sys.modules.setdefault("aiohttp", aiohttp)
yarl = ModuleType("yarl")
yarl.URL = lambda value, **kwargs: value
sys.modules.setdefault("yarl", yarl)

const = _load("const")
exceptions = _load("exceptions")
provider_defaults = _load("provider_defaults")
provider_module = _load("provider")
web_api = _load("web_api")
compile_module = _load("compile")
expression_functions = _load("expression_functions")
form_helpers = _load("form_helpers")

description_stub = ModuleType(f"{PACKAGE}.description")
description_stub.Description = object


class _EntityType(StrEnum):
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    NUMBER = "number"
    SWITCH = "switch"


description_stub.EntityType = _EntityType
sys.modules[f"{PACKAGE}.description"] = description_stub
number_validation = _load("number_validation")
system_module = _load("system")


TEST_SYSTEM_IDS = (
    "test_boiler_1",
    "test_boiler_2",
    "test_boiler_3",
)
TEST_SYSTEM_STATUSES = {
    "test_boiler_1": {"temp1": 41.0, "status": "online"},
    "test_boiler_2": {"temp1": 52.0, "status": "standby"},
    "test_boiler_3": {"temp1": 63.0, "status": "heating"},
}


class _FakeProvider(provider_module.Provider):
    """Controllable multi-system provider used only by the test suite."""

    def __init__(
        self,
        configured=(),
        *,
        systems=TEST_SYSTEM_IDS,
        statuses=None,
        provider_id="fixture_provider",
        duplicate_systems=None,
    ):
        super().__init__(
            provider_id=provider_id,
            duplicate_systems=duplicate_systems,
            configured_available_keys=configured,
        )
        self._source_system_ids = tuple(systems)
        initial_statuses = (
            TEST_SYSTEM_STATUSES if statuses is None else statuses
        )
        self._statuses = {
            source_system_id: deepcopy(dict(initial_statuses[source_system_id]))
            for source_system_id in self._source_system_ids
        }
        self._failures = {}
        self.status_calls = []
        self.status_calls_by_system = {
            source_system_id: 0
            for source_system_id in self._source_system_ids
        }
        self._blocked_status_target = 0
        self._blocked_status_started = asyncio.Event()
        self._status_release = None
        self._active_status_calls = 0
        self.max_concurrent_status_calls = 0
        self.calls = {
            "open": 0,
            "connect": 0,
            "profile": 0,
            "systems": 0,
            "status": 0,
        }

    async def async_open(self):
        self.calls["open"] += 1

    async def async_connect(self):
        self.calls["connect"] += 1

    async def async_disconnect(self):
        return None

    async def async_close(self):
        return None

    def set_system_status(self, source_system_id, status):
        """Replace one system's next and subsequent status values."""
        if source_system_id not in self._statuses:
            raise KeyError(source_system_id)
        self._statuses[source_system_id] = deepcopy(dict(status))

    def set_system_failure(self, source_system_id, error=None):
        """Make one system fail without changing its siblings."""
        if source_system_id not in self._statuses:
            raise KeyError(source_system_id)
        self._failures[source_system_id] = error or (
            exceptions.ProviderSystemError(
                f"Fixture system {source_system_id} is unavailable"
            )
        )

    def clear_system_failure(self, source_system_id):
        """Restore normal status responses for one system."""
        self._failures.pop(source_system_id, None)

    def block_next_status_wave(self, expected_calls):
        """Hold a status wave until all expected concurrent calls arrived."""
        if expected_calls < 1:
            raise ValueError("expected_calls must be positive")
        self._blocked_status_target = expected_calls
        self._blocked_status_started = asyncio.Event()
        self._status_release = asyncio.Event()
        self.max_concurrent_status_calls = 0

    async def wait_for_blocked_status_wave(self):
        """Wait until the configured status-wave concurrency is observable."""
        await asyncio.wait_for(
            self._blocked_status_started.wait(),
            timeout=1,
        )

    def release_status_wave(self):
        """Release a status wave previously blocked by the fixture."""
        if self._status_release is None:
            raise RuntimeError("No status wave is blocked")
        self._status_release.set()
        self._status_release = None
        self._blocked_status_target = 0

    async def _async_fetch_profile(self):
        self.calls["profile"] += 1
        await asyncio.sleep(0)
        return {"name": "Multi-system test hub"}

    async def _async_fetch_systems(self):
        self.calls["systems"] += 1
        return self._source_system_ids

    async def _async_fetch_system_status(self, source_system_id, source_keys):
        if source_system_id not in self._statuses:
            raise exceptions.ProviderSystemError(
                f"Unknown fixture system: {source_system_id}"
            )

        self.calls["status"] += 1
        self.status_calls_by_system[source_system_id] += 1
        self.status_calls.append(
            (source_system_id, tuple(sorted(source_keys)))
        )
        self._active_status_calls += 1
        self.max_concurrent_status_calls = max(
            self.max_concurrent_status_calls,
            self._active_status_calls,
        )
        if self._active_status_calls >= self._blocked_status_target > 0:
            self._blocked_status_started.set()

        release = self._status_release
        try:
            if release is not None:
                await release.wait()
            if error := self._failures.get(source_system_id):
                raise error
            return deepcopy(self._statuses[source_system_id])
        finally:
            self._active_status_calls -= 1


# The local contract-test environment deliberately does not install all of
# Home Assistant. These small framework doubles let the real configuration,
# coordinator, and entity modules participate in the multi-system tests.
homeassistant = ModuleType("homeassistant")
homeassistant.__path__ = []
ha_components = ModuleType("homeassistant.components")
ha_components.__path__ = []
ha_binary_sensor = ModuleType("homeassistant.components.binary_sensor")
ha_binary_sensor.BinarySensorEntity = type("BinarySensorEntity", (), {})
ha_sensor = ModuleType("homeassistant.components.sensor")


class _SensorDeviceClass(StrEnum):
    TIMESTAMP = "timestamp"


ha_sensor.SensorDeviceClass = _SensorDeviceClass
ha_sensor.SensorEntity = type("SensorEntity", (), {})
ha_config_entries = ModuleType("homeassistant.config_entries")
ha_config_entries.ConfigEntry = type("ConfigEntry", (), {})
ha_config_entries.ConfigSubentry = type("ConfigSubentry", (), {})
ha_const = ModuleType("homeassistant.const")


class _Platform(StrEnum):
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    NUMBER = "number"
    SWITCH = "switch"


ha_const.Platform = _Platform
ha_const.MAX_LENGTH_STATE_STATE = 255
ha_core = ModuleType("homeassistant.core")
ha_core.HomeAssistant = type("HomeAssistant", (), {})
ha_exceptions = ModuleType("homeassistant.exceptions")
ha_exceptions.ConfigEntryAuthFailed = type(
    "ConfigEntryAuthFailed", (Exception,), {}
)
ha_exceptions.ConfigEntryError = type("ConfigEntryError", (Exception,), {})
ha_exceptions.ConfigEntryNotReady = type(
    "ConfigEntryNotReady", (Exception,), {}
)
ha_helpers = ModuleType("homeassistant.helpers")
ha_helpers.__path__ = []
ha_config_validation = ModuleType(
    "homeassistant.helpers.config_validation"
)
ha_config_validation.config_entry_only_config_schema = (
    lambda domain: ("config_entry_only", domain)
)
ha_helpers.config_validation = ha_config_validation
ha_update_coordinator = ModuleType(
    "homeassistant.helpers.update_coordinator"
)


class _DataUpdateCoordinator:
    def __init__(
        self,
        hass,
        *,
        logger,
        config_entry,
        name,
        update_interval,
    ):
        del logger, config_entry, name
        self.hass = hass
        self.update_interval = update_interval
        self.data = None
        self.last_exception = None

    @classmethod
    def __class_getitem__(cls, item):
        del item
        return cls

    async def async_refresh(self):
        try:
            self.data = await self._async_update_data()
        except Exception as err:
            self.last_exception = err
        else:
            self.last_exception = None

    async def async_request_refresh(self):
        await self.async_refresh()


ha_update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
ha_update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})
ha_device_registry = ModuleType("homeassistant.helpers.device_registry")


class _DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


ha_device_registry.DeviceInfo = _DeviceInfo
ha_entity_registry = ModuleType("homeassistant.helpers.entity_registry")


class _EmptyEntityRegistry:
    @staticmethod
    def async_get_entity_id(*args):
        del args
        return None

    @staticmethod
    def async_remove(entity_id):
        del entity_id


_EMPTY_ENTITY_REGISTRY = _EmptyEntityRegistry()
ha_entity_registry.async_get = lambda hass: getattr(
    hass,
    "entity_registry",
    _EMPTY_ENTITY_REGISTRY,
)
ha_helpers.entity_registry = ha_entity_registry
ha_entity_platform = ModuleType("homeassistant.helpers.entity_platform")
ha_entity_platform.AddConfigEntryEntitiesCallback = object
ha_util = ModuleType("homeassistant.util")
ha_util.__path__ = []
ha_util_dt = ModuleType("homeassistant.util.dt")
ha_util_dt.as_local = lambda value: value.astimezone(
    timezone(timedelta(hours=2))
)


class _CoordinatorEntity:
    @classmethod
    def __class_getitem__(cls, item):
        del item
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.hass = coordinator.hass


ha_update_coordinator.CoordinatorEntity = _CoordinatorEntity

for name, module in {
    "homeassistant": homeassistant,
    "homeassistant.components": ha_components,
    "homeassistant.components.binary_sensor": ha_binary_sensor,
    "homeassistant.components.sensor": ha_sensor,
    "homeassistant.config_entries": ha_config_entries,
    "homeassistant.const": ha_const,
    "homeassistant.core": ha_core,
    "homeassistant.exceptions": ha_exceptions,
    "homeassistant.helpers": ha_helpers,
    "homeassistant.helpers.config_validation": ha_config_validation,
    "homeassistant.helpers.update_coordinator": ha_update_coordinator,
    "homeassistant.helpers.device_registry": ha_device_registry,
    "homeassistant.helpers.entity_registry": ha_entity_registry,
    "homeassistant.helpers.entity_platform": ha_entity_platform,
    "homeassistant.util": ha_util,
    "homeassistant.util.dt": ha_util_dt,
}.items():
    sys.modules.setdefault(name, module)


class _RuntimeConfiguration:
    """Minimal compiler result used to exercise runtime construction."""

    def __init__(self, source_expressions):
        self.source_expressions = dict(source_expressions)
        self.required_source_keys = frozenset({"status", "temp1"})
        self.source_keys = self.required_source_keys
        self.dropped_keys = frozenset(
            key
            for key, expression in source_expressions.items()
            if expression.strip() == "drop()"
        )
        self.evaluated_keys = frozenset(source_expressions) - self.dropped_keys
        self.compiled_source_expressions = {
            key: expression
            for key, expression in source_expressions.items()
            if key not in self.dropped_keys
        }

    @classmethod
    def compile(cls, source_expressions, **kwargs):
        del kwargs
        return cls(source_expressions)

    def stored_source_expressions(self):
        return dict(self.source_expressions)


runtime_configuration_stub = ModuleType(
    f"{PACKAGE}.runtime_configuration"
)
runtime_configuration_stub.RuntimeConfiguration = _RuntimeConfiguration
sys.modules[f"{PACKAGE}.runtime_configuration"] = runtime_configuration_stub

thetruth_stub = ModuleType(f"{PACKAGE}.thetruth")


def _evaluation_description(
    key,
    *,
    entity_type=_EntityType.SENSOR,
    device_class=None,
    unit=None,
    state_class=None,
    precision=None,
    minimum=None,
    maximum=None,
    step=None,
    entity_category=None,
):
    return SimpleNamespace(
        key=key,
        entity_type=entity_type,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=state_class,
        suggested_display_precision=precision,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=step,
        entity_category=entity_category,
    )


thetruth_stub.DESCRIPTIONS = [
    _evaluation_description(
        "last_report", device_class=_SensorDeviceClass.TIMESTAMP
    ),
    _evaluation_description("report_delay"),
    _evaluation_description("numeric_value", unit="kWh", precision=2),
    _evaluation_description(
        "binary_value", entity_type=_EntityType.BINARY_SENSOR
    ),
    _evaluation_description(
        "weekly_archive", entity_type=_EntityType.SWITCH
    ),
    _evaluation_description(
        "number_value",
        entity_type=_EntityType.NUMBER,
        minimum=1,
        maximum=10,
        step=1,
        entity_category="config",
    ),
    _evaluation_description("quotient", unit="kWh", precision=2),
    _evaluation_description("dependent", unit="kWh", precision=2),
    _evaluation_description("text_value"),
    _evaluation_description("alerts_system"),
]
sys.modules[f"{PACKAGE}.thetruth"] = thetruth_stub

evaluator_actual = _load_as("evaluator_actual", "evaluator")

# Configuration itself does not need generated descriptions in these tests.
# The real evaluator above has already cached the focused contract fixture.
thetruth_stub.DESCRIPTIONS = []
configuration_module = _load("configuration")

evaluator_stub = ModuleType(f"{PACKAGE}.evaluator")


def _evaluate_source_expressions(compiled, source_values, context=None):
    del context
    result = dict(source_values)
    result[const.UPDATE_INTERVAL_ENTITY_KEY] = float(
        compiled[const.UPDATE_INTERVAL_ENTITY_KEY]
    )
    errors = {}
    if source_values.get("__evaluation_error__"):
        errors["temp_tank_average"] = SimpleNamespace(
            category=SimpleNamespace(value="missing_source")
        )
        result["temp_tank_average"] = None
    return SimpleNamespace(values=result, errors=errors)


evaluator_stub.evaluate_source_expressions = _evaluate_source_expressions
evaluator_stub.EvaluationError = type("EvaluationError", (), {})
evaluator_stub.EvaluationContext = evaluator_actual.EvaluationContext
sys.modules[f"{PACKAGE}.evaluator"] = evaluator_stub

coordinator_module = _load("coordinator")
diagnostics_module = _load("diagnostics")
entity_module = _load("entity")
sensor_module = _load("sensor")
binary_sensor_module = _load("binary_sensor")
integration_module = _load_as("integration_actual", "__init__")


class CompilerTests(unittest.TestCase):
    def test_null_accepts_fields_and_field_free_constants(self):
        for expression in ("null()", "null(1)", "null(field, 2+3)"):
            compile_module.compile_source_expressions({"value": expression})
        for expression in ("null(value=True)", "null(field > 0)"):
            with self.subTest(expression=expression):
                with self.assertRaises(compile_module.SourceExpressionFunctionError):
                    compile_module.compile_source_expressions({"value": expression})

    def test_generated_defaults_compile_as_one_production_graph(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        expressions = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "Description":
                continue
            values = {keyword.arg: keyword.value for keyword in node.keywords}
            key = ast.literal_eval(values["key"])
            expressions[key] = ast.literal_eval(
                values["default_source_expression"]
            )
        dropped = {
            key
            for key, expression in expressions.items()
            if expression.strip() == "drop()"
        }
        compiled = compile_module.compile_source_expressions(
            {
                key: expression
                for key, expression in expressions.items()
                if key not in dropped
            }
        )
        self.assertEqual(set(compiled.expressions), set(expressions) - dropped)
        self.assertEqual(
            dropped,
            {"archive_last_success", "archive_status"},
        )
        self.assertNotIn("update_interval", compiled.source_keys)

    def test_generated_defaults_omit_unused_solesta_sources(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        expressions = {
            ast.literal_eval(values["key"]): ast.literal_eval(
                values["default_source_expression"]
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Description"
            for values in (
                {keyword.arg: keyword.value for keyword in node.keywords},
            )
            if ast.literal_eval(values["key"])
            in {"alerts_system", "temp_reserved"}
        }
        self.assertEqual(expressions["temp_reserved"], "null()")
        expression = expressions["alerts_system"]
        self.assertEqual(
            expression,
            "solar_thermal_alerts(null(status_reporting, state_pump, "
            "temp_collector, temp_tank_top), 90, 200, 10, 10)",
        )
        compiled = compile_module.compile_source_expressions(
            {"alerts_system": expression}
        )
        self.assertNotIn("alerts", compiled.source_keys)
        source = {
            "status_reporting": True,
            "state_pump": False,
            "temp_collector": 40,
            "temp_tank_top": 40,
        }
        empty = evaluator_actual.evaluate_source_expressions(
            compiled,
            source,
        )
        self.assertEqual(empty.values["alerts_system"], "")
        alert = {
            "type": "sensor_fault",
            "message": "Line 1\nLine 2",
            "severity": "error",
        }
        populated = evaluator_actual.evaluate_source_expressions(
            compiled,
            {**source, "alerts": [alert]},
        )
        self.assertEqual(populated.values["alerts_system"], "")

    def test_strings_are_not_rewritten_as_source_suffixes(self):
        for expression in ("status=='online'", 'status=="online"'):
            compiled = compile_module.compile_source_expressions(
                {"value": expression}
            )
            self.assertEqual(compiled.source_keys, frozenset({"status"}))

    def test_source_suffix_and_compiled_mapping_are_stable(self):
        compiled = compile_module.compile_source_expressions(
            {"value": "temp1' + temp1"}
        )
        self.assertEqual(compiled.source_keys, frozenset({"temp1"}))
        with self.assertRaises(TypeError):
            compiled.expressions["other"] = None

    def test_source_suffix_alias_cannot_collide_with_real_source_name(self):
        collision_name = "__source_suffix_alias_0"
        compiled = compile_module.compile_source_expressions(
            {"value": f"temp1' + {collision_name}"}
        )
        self.assertEqual(
            compiled.source_keys,
            frozenset({"temp1", collision_name}),
        )
        result = evaluator_actual.evaluate_source_expressions(
            compiled,
            {"temp1": 2, collision_name: 3},
        )
        self.assertEqual(result.values["value"], 5.0)
        self.assertFalse(result.errors)

    def test_number_expression_may_use_provider_keys(self):
        compiled = compile_module.compile_source_expressions(
            {"number": "to_number(temp1)"}
        )
        self.assertEqual(compiled.source_keys, frozenset({"temp1"}))

    def test_delay_zone_dependency_and_static_borders_compile(self):
        compiled = compile_module.compile_source_expressions(
            {
                "last_report": "last_update",
                "report_delay": (
                    "delay_zone(last_report, 2*60+30, 10*60)"
                ),
            }
        )
        self.assertEqual(compiled.source_keys, frozenset({"last_update"}))
        self.assertLess(
            compiled.evaluation_order.index("last_report"),
            compiled.evaluation_order.index("report_delay"),
        )

    def test_delay_zone_invalid_border_contract_fails_compilation(self):
        invalid = (
            "delay_zone(last_report)",
            "delay_zone(last_report, 0)",
            "delay_zone(last_report, 150.5)",
            "delay_zone(last_report, 600, 150)",
            "delay_zone(last_report, 150, 150)",
            "delay_zone(last_report, border)",
            "delay_zone(last_report, 'x' * 1000000000)",
        )
        for expression in invalid:
            with self.subTest(expression=expression):
                with self.assertRaises(
                    compile_module.SourceExpressionFunctionError
                ):
                    compile_module.compile_source_expressions(
                        {"report_delay": expression}
                    )

    def test_solar_alert_constants_are_validated_at_compilation(self):
        optional_values = (
            "null(status_reporting, state_pump, temp_collector, "
            "temp_tank_top)"
        )
        valid = (
            f"solar_thermal_alerts({optional_values}, "
            "45*2, 100*2, 5+5, 20/2)"
        )
        compile_module.compile_source_expressions({"alerts_system": valid})
        invalid = (
            f"solar_thermal_alerts({optional_values}, hot, 200, 10, 10)",
            f"solar_thermal_alerts({optional_values}, 200, 200, 10, 10)",
            f"solar_thermal_alerts({optional_values}, 90, 200, -1, 10)",
            f"solar_thermal_alerts({optional_values}, 90, 200, 10, -1)",
            "solar_thermal_alerts(null(status_reporting), 90, 200, 10, 10)",
        )
        for expression in invalid:
            with self.subTest(expression=expression):
                with self.assertRaises(
                    compile_module.SourceExpressionFunctionError
                ):
                    compile_module.compile_source_expressions(
                        {"alerts_system": expression}
                    )

    def test_resource_limits_reject_oversized_or_expensive_expressions(self):
        rejected = (
            "1" * 1025,
            " + ".join("1" for _ in range(100)),
            "2 ** 32",
            "9" * 1000,
        )
        for expression in rejected:
            with self.subTest(expression=expression[:40]):
                with self.assertRaises(compile_module.SourceExpressionError):
                    compile_module.compile_source_expressions(
                        {"value": expression}
                    )

    def test_runtime_arithmetic_blocks_string_allocation_and_huge_results(self):
        expressions = (
            "'x' * 1000000000",
            " * ".join("1000000000000" for _ in range(9)),
        )
        for expression in expressions:
            with self.subTest(expression=expression[:40]):
                compiled = compile_module.compile_source_expressions(
                    {"value": expression}
                )
                result = evaluator_actual.evaluate_source_expressions(
                    compiled, {}
                )
                self.assertIsNone(result.values["value"])
                self.assertIn(
                    result.errors["value"].category,
                    {
                        evaluator_actual.EvaluationErrorCategory.TYPE_ERROR,
                        evaluator_actual.EvaluationErrorCategory.DOMAIN_ERROR,
                    },
                )


class ExpressionFunctionTests(unittest.TestCase):
    def test_null_returns_none(self):
        self.assertIsNone(expression_functions.null())

    def test_to_number_preserves_null_but_rejects_booleans(self):
        self.assertIsNone(expression_functions.to_number(None))
        with self.assertRaises(ValueError):
            expression_functions.to_number(True)

    def test_delay_zone_uses_inclusive_ascending_zones(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        cases = (
            (now, "[0,150]"),
            (
                now - timedelta(seconds=150),
                "[0,150]",
            ),
            (
                now - timedelta(seconds=150, microseconds=1),
                "[151,600]",
            ),
            (
                now - timedelta(seconds=600),
                "[151,600]",
            ),
            (
                now - timedelta(seconds=601),
                "[601,900]",
            ),
        )
        with patch.object(expression_functions, "_utc_now", return_value=now):
            for last_report, expected in cases:
                with self.subTest(last_report=last_report):
                    self.assertEqual(
                        expression_functions.delay_zone(
                            last_report,
                            2 * 60 + 30,
                            10 * 60,
                            15 * 60,
                        ),
                        expected,
                    )

    def test_delay_zone_supports_epoch_iso_and_preserves_old_value(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        old_iso = "2026-08-27T11:49:59Z"
        with patch.object(expression_functions, "_utc_now", return_value=now):
            self.assertEqual(
                expression_functions.delay_zone(now.timestamp() - 10, 150, 600),
                "[0,150]",
            )
            self.assertEqual(
                expression_functions.delay_zone(
                    "2026-08-27T13:57:30+02:00", 150, 600
                ),
                "[0,150]",
            )
            self.assertEqual(
                expression_functions.delay_zone(old_iso, 150, 600),
                "2026-08-27T11:49:59+00:00",
            )
            self.assertEqual(
                expression_functions.delay_zone(now + timedelta(seconds=5), 150),
                "[0,150]",
            )
            self.assertIsNone(expression_functions.delay_zone(None, 150))

    def test_delay_zone_rejects_invalid_borders(self):
        invalid = (
            (),
            (0,),
            (-1,),
            (150, 150),
            (600, 150),
            (True,),
            ("150",),
            (150.5,),
            (float("nan"),),
        )
        for borders in invalid:
            with self.subTest(borders=borders):
                with self.assertRaises((TypeError, ValueError)):
                    expression_functions.delay_zone(0, *borders)

    def test_is_timestamp_recognizes_supported_forms_only(self):
        self.assertTrue(
            expression_functions.is_timestamp("2026-10-25T20:18:53+00:00")
        )
        self.assertTrue(
            expression_functions.is_timestamp(
                datetime(2026, 10, 25, 20, 18, 53, tzinfo=timezone.utc)
            )
        )
        self.assertTrue(expression_functions.is_timestamp(1_798_229_933))
        for value in (None, True, "[0,150]", "current", ""):
            with self.subTest(value=value):
                self.assertFalse(expression_functions.is_timestamp(value))

    def test_join_lines_supports_scalar_flat_list_and_empty_values(self):
        self.assertEqual(expression_functions.join_lines("A"), "A")
        self.assertEqual(
            expression_functions.join_lines(["A", "", None, "B"]),
            "A\x1eB",
        )
        self.assertEqual(expression_functions.join_lines(None), "")

    def test_join_lines_does_not_split_newlines_inside_json_text(self):
        first = json.dumps(
            {"type": "note", "message": "first line\nsecond line"}
        )
        second = json.dumps({"type": "other", "message": "third line"})
        joined = expression_functions.join_lines(first, second)
        self.assertEqual(joined.split("\x1e"), [first, second])

    def test_join_lines_preserves_structured_alert_elements(self):
        alert = {"Type": "pump_idle", "severity": "warning"}
        self.assertEqual(expression_functions.join_lines([alert]), str(alert))

    def test_join_lines_rejects_nested_sequences(self):
        with self.assertRaises(TypeError):
            expression_functions.join_lines([["A"], "B"])

    def test_join_lines_has_item_and_output_limits(self):
        with self.assertRaises(ValueError):
            expression_functions.join_lines(["x"] * 1025)
        with self.assertRaises(ValueError):
            expression_functions.join_lines("x" * (64 * 1024 + 1))

    @staticmethod
    def _alerts(
        *,
        reporting=True,
        pump=False,
        collector=40,
        tank_top=40,
        hot=90,
        danger=200,
        idle_delta=10,
        active_delta=10,
    ):
        optional_values = [reporting, pump, collector, tank_top]
        value = expression_functions.solar_thermal_alerts(
            optional_values,
            hot,
            danger,
            idle_delta,
            active_delta,
        )
        return [
            json.loads(record)
            for record in value.split(const.TEXT_RECORD_SEPARATOR)
            if record
        ]

    def test_solar_alert_temperature_boundaries_are_strict(self):
        self.assertEqual(self._alerts(collector=90, pump=None), [])
        self.assertEqual(
            self._alerts(collector=200, pump=None),
            [
                {
                    "type": "collector_hot",
                    "translation_key": "alert_collector_hot",
                    "translation_placeholders": {
                        "temperature": "200",
                    },
                    "severity": "warning",
                }
            ],
        )
        self.assertEqual(
            self._alerts(collector=201, pump=None)[0]["severity"],
            "danger",
        )

    def test_solar_alert_pump_rules_and_boundaries(self):
        self.assertEqual(
            self._alerts(pump=False, collector=50, tank_top=40),
            [],
        )
        self.assertEqual(
            self._alerts(pump=False, collector=51, tank_top=40)[0]["type"],
            "pump_idle",
        )
        self.assertEqual(
            self._alerts(pump=True, collector=39, tank_top=40)[0]["severity"],
            "info",
        )
        self.assertEqual(
            self._alerts(pump=True, collector=30, tank_top=40)[0]["severity"],
            "info",
        )
        self.assertEqual(
            self._alerts(pump=True, collector=29, tank_top=40)[0]["severity"],
            "warning",
        )
        self.assertEqual(
            self._alerts(pump=True, collector=39, tank_top=40, active_delta=0)[0]["severity"],
            "warning",
        )
        self.assertEqual(
            self._alerts(pump=True, collector=40, tank_top=40),
            [],
        )

    def test_local_solar_alerts_are_language_neutral_translation_records(self):
        scenarios = (
            (
                self._alerts(reporting=False),
                "alert_offline",
                {},
            ),
            (
                self._alerts(collector=201, pump=None),
                "alert_collector_danger",
                {"temperature": "201"},
            ),
            (
                self._alerts(pump=False, collector=51, tank_top=40),
                "alert_pump_idle",
                {},
            ),
            (
                self._alerts(pump=True, collector=39, tank_top=40),
                "alert_pump_active_cool",
                {},
            ),
            (
                self._alerts(pump=True, collector=29, tank_top=40),
                "alert_pump_active_cold",
                {},
            ),
        )
        for alerts, translation_key, placeholders in scenarios:
            with self.subTest(translation_key=translation_key):
                self.assertEqual(len(alerts), 1)
                self.assertNotIn("message", alerts[0])
                self.assertEqual(alerts[0]["translation_key"], translation_key)
                self.assertEqual(
                    alerts[0].get("translation_placeholders", {}),
                    placeholders,
                )

    def test_solar_alert_offline_is_exclusive_and_unknown_is_partial(self):
        self.assertEqual(
            self._alerts(reporting=False, collector=300),
            [{
                "type": "offline",
                "translation_key": "alert_offline",
                "severity": "danger",
            }],
        )
        self.assertEqual(
            self._alerts(reporting=None, collector=300),
            [],
        )

    def test_solar_alert_missing_measurements_only_suppress_dependent_rules(self):
        self.assertEqual(
            self._alerts(collector=95, tank_top=None, pump=None),
            [{
                "type": "collector_hot",
                "translation_key": "alert_collector_hot",
                "translation_placeholders": {"temperature": "95"},
                "severity": "warning",
            }],
        )

    def test_solar_alert_runtime_data_types_are_validated(self):
        with self.assertRaises(TypeError):
            self._alerts(reporting="online")
        with self.assertRaises(TypeError):
            self._alerts(pump="on")


class EvaluatorTests(unittest.TestCase):
    def test_null_expression_has_no_source_dependency(self):
        compiled = compile_module.compile_source_expressions(
            {
                "temp_reserved": "null()",
                "source_named_null": "null",
                "source_named_none": "none",
            }
        )
        self.assertEqual(compiled.source_keys, {"null", "none"})
        result = evaluator_actual.evaluate_source_expressions(
            compiled,
            {"null": "source null", "none": "source none"},
        )
        self.assertIsNone(result.values["temp_reserved"])
        self.assertEqual(result.values["source_named_null"], "source null")
        self.assertEqual(result.values["source_named_none"], "source none")
        self.assertFalse(result.errors)

    def test_universal_reporting_and_pump_boundaries(self):
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        compiled = compile_module.compile_source_expressions(
            {
                "last_report": "last_update",
                "report_delay": "delay_zone(last_report, 150, 600)",
                "status_reporting": (
                    "report_delay and not is_timestamp(report_delay)"
                ),
                "state_pump": "perc_pump_pwm > 0",
            }
        )
        for age, pump, expected_reporting, expected_pump in (
            (600, 0, True, False),
            (601, 0.1, False, True),
        ):
            with self.subTest(age=age, pump=pump), patch.object(
                expression_functions,
                "_utc_now",
                return_value=now,
            ):
                result = evaluator_actual.evaluate_source_expressions(
                    compiled,
                    {
                        "last_update": now - timedelta(seconds=age),
                        "perc_pump_pwm": pump,
                    },
                )
            self.assertIs(
                result.values["status_reporting"],
                expected_reporting,
            )
            self.assertIs(result.values["state_pump"], expected_pump)

        missing = evaluator_actual.evaluate_source_expressions(compiled, {})
        self.assertIsNone(missing.values["status_reporting"])
        self.assertIsNone(missing.values["state_pump"])

        provider_independent = compile_module.compile_source_expressions(
            {
                "status_reporting": (
                    "report_delay and not is_timestamp(report_delay)"
                )
            }
        )
        for delay, expected in (
            (None, None),
            ("within-provider-specific-zone", True),
            ("2026-10-25T20:18:53+00:00", False),
        ):
            with self.subTest(delay=delay):
                result = evaluator_actual.evaluate_source_expressions(
                    provider_independent,
                    {"report_delay": delay},
                )
                self.assertFalse(result.errors)
                self.assertIs(result.values["status_reporting"], expected)

    def test_web_and_esphome_defaults_produce_identical_local_alerts(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        web = {}
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Name)
                or node.func.id != "Description"
            ):
                continue
            values = {item.arg: item.value for item in node.keywords}
            expression = ast.literal_eval(values["default_source_expression"])
            if expression != "drop()":
                web[ast.literal_eval(values["key"])] = expression
        esphome = dict(web)
        esphome.update(
            {
                "last_report": "last_update",
                "temp_collector": "to_number(temperature_1_raw)",
                "temp_tank_top": "to_number(temperature_2_raw)",
                "temp_tank_bottom": "to_number(temperature_3_raw)",
                "temp_reserved": "to_number(temperature_4_raw)",
                "perc_pump_pwm": "to_number(pump_raw) * 100",
                "alerts_system": (
                    "solar_thermal_alerts(null(status_reporting, "
                    "state_pump, temp_collector, temp_tank_top), "
                    "90, 200, 10, 10)"
                ),
            }
        )
        moment = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        common = {
            "last_update": moment.isoformat(),
        }
        with patch.object(
            expression_functions,
            "_utc_now",
            return_value=moment,
        ):
            web_result = evaluator_actual.evaluate_source_expressions(
                compile_module.compile_source_expressions(web),
                {
                    **common,
                    "temp1": 95,
                    "temp2": 50,
                    "temp3": 40,
                    "temp4": 20,
                    "pump": 0,
                    "alerts": [],
                },
                evaluator_actual.EvaluationContext(
                    last_report=moment,
                    last_update=moment,
                ),
            )
            esphome_result = evaluator_actual.evaluate_source_expressions(
                compile_module.compile_source_expressions(esphome),
                {
                    **common,
                    "temperature_1_raw": 95,
                    "temperature_2_raw": 50,
                    "temperature_3_raw": 40,
                    "temperature_4_raw": 20,
                    "pump_raw": 0,
                },
            )
        self.assertFalse(web_result.errors)
        self.assertFalse(esphome_result.errors)
        self.assertEqual(
            web_result.values["alerts_system"],
            esphome_result.values["alerts_system"],
        )
        self.assertIn(
            const.TEXT_RECORD_SEPARATOR,
            web_result.values["alerts_system"],
        )

    def test_switch_requires_and_preserves_boolean_values(self):
        valid = compile_module.compile_source_expressions(
            {"weekly_archive": "False"}
        )
        valid_result = evaluator_actual.evaluate_source_expressions(valid, {})
        self.assertFalse(valid_result.errors)
        self.assertIs(valid_result.values["weekly_archive"], False)

        invalid = compile_module.compile_source_expressions(
            {"weekly_archive": "0"}
        )
        invalid_result = evaluator_actual.evaluate_source_expressions(invalid, {})
        self.assertIsNone(invalid_result.values["weekly_archive"])
        self.assertEqual(
            invalid_result.errors["weekly_archive"].category,
            evaluator_actual.EvaluationErrorCategory.TYPE_ERROR,
        )

    def test_nullable_numeric_sensor_does_not_poison_other_entities(self):
        compiled = compile_module.compile_source_expressions(
            {
                "numeric_value": "to_number(optional)",
                "binary_value": 'status == "online"',
            }
        )
        result = evaluator_actual.evaluate_source_expressions(
            compiled,
            {"optional": None, "status": "online"},
        )

        self.assertFalse(result.errors)
        self.assertIsNone(result.values["numeric_value"])
        self.assertIs(result.values["binary_value"], True)

    def test_typed_results_include_delay_text_and_normalized_timestamp(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        compiled = compile_module.compile_source_expressions(
            {
                "last_report": "last_update",
                "report_delay": "delay_zone(last_report, 150, 600)",
                "numeric_value": "to_number(temp)",
                "binary_value": 'status == "online"',
                "number_value": "5",
                "text_value": "join_lines(alerts)",
            }
        )
        with patch.object(expression_functions, "_utc_now", return_value=now):
            result = evaluator_actual.evaluate_source_expressions(
                compiled,
                {
                    "last_update": now - timedelta(seconds=151),
                    "temp": "12,50",
                    "status": "online",
                    "alerts": ["A", "B"],
                },
            )

        self.assertFalse(result.errors)
        self.assertEqual(
            result.values["report_delay"],
            "[151,600]",
        )
        self.assertIsInstance(result.values["last_report"], datetime)
        self.assertEqual(result.values["numeric_value"], 12.5)
        self.assertIs(result.values["binary_value"], True)
        self.assertEqual(result.values["number_value"], 5.0)
        self.assertEqual(result.values["text_value"], "A\x1eB")
        with self.assertRaises(TypeError):
            result.values["numeric_value"] = 99

    def test_report_delay_falls_back_to_typed_timestamp_after_last_zone(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        compiled = compile_module.compile_source_expressions(
            {
                "last_report": "last_update",
                "report_delay": "delay_zone(last_report, 150, 600)",
            }
        )
        with patch.object(expression_functions, "_utc_now", return_value=now):
            result = evaluator_actual.evaluate_source_expressions(
                compiled,
                {"last_update": "2026-08-27T11:49:59Z"},
            )
        self.assertFalse(result.errors)
        self.assertEqual(
            result.values["report_delay"],
            "2026-08-27T11:49:59+00:00",
        )

    def test_failures_are_classified_and_do_not_poison_siblings(self):
        compiled = compile_module.compile_source_expressions(
            {
                "numeric_value": "bad_numeric",
                "dependent": "numeric_value + 1",
                "number_value": "0",
                "quotient": "10 / zero",
                "text_value": "missing_text",
                "binary_value": 'status == "online"',
            }
        )
        result = evaluator_actual.evaluate_source_expressions(
            compiled,
            {
                "bad_numeric": "not-a-number",
                "zero": 0,
                "status": "online",
            },
        )
        categories = {
            key: error.category for key, error in result.errors.items()
        }
        self.assertEqual(
            categories,
            {
                "numeric_value": evaluator_actual.EvaluationErrorCategory.TYPE_ERROR,
                "dependent": evaluator_actual.EvaluationErrorCategory.DEPENDENCY_FAILED,
                "number_value": evaluator_actual.EvaluationErrorCategory.DOMAIN_ERROR,
                "quotient": evaluator_actual.EvaluationErrorCategory.DIVISION_BY_ZERO,
                "text_value": evaluator_actual.EvaluationErrorCategory.MISSING_SOURCE,
            },
        )
        self.assertIs(result.values["binary_value"], True)
        for key in categories:
            self.assertIsNone(result.values[key])
        with self.assertRaises(TypeError):
            result.errors["extra"] = None


class TextSensorStateLengthTests(unittest.TestCase):
    @staticmethod
    def _sensor(value, key="text_value"):
        sensor = object.__new__(sensor_module.SystemSensor)
        sensor._description = SimpleNamespace(key=key, device_class=None)
        sensor.coordinator = SimpleNamespace(data={key: value})
        return sensor

    def test_short_and_missing_text_values_are_unchanged(self):
        empty = self._sensor("", key="alerts_system")
        self.assertEqual(empty.native_value, "")
        self.assertIsNone(empty.extra_state_attributes)
        missing = self._sensor(None)
        self.assertIsNone(missing.native_value)
        self.assertIsNone(missing.extra_state_attributes)

    def test_255_characters_remain_unchanged_without_attributes(self):
        value = "x" * 255
        sensor = self._sensor(value)
        self.assertEqual(sensor.native_value, value)
        self.assertIsNone(sensor.extra_state_attributes)

    def test_256_characters_are_truncated_and_preserved_in_attributes(self):
        value = "x" * 256
        sensor = self._sensor(value)
        self.assertEqual(sensor.native_value, "x" * 254 + "…")
        self.assertEqual(len(sensor.native_value), 255)
        self.assertEqual(
            sensor.extra_state_attributes,
            {"lines": [value], "truncated": True},
        )

    def test_all_lines_are_preserved_for_any_oversized_text_sensor(self):
        lines = ["first", "x" * 250, "third"]
        sensor = self._sensor("\n".join(lines), key="arbitrary_text_sensor")
        attributes = sensor.extra_state_attributes
        self.assertTrue(attributes["truncated"])
        self.assertEqual(attributes["lines"], lines)
        self.assertNotIn("alerts", attributes)

    def test_record_separator_preserves_newlines_inside_overflow_records(self):
        records = ["first line\nsecond line", "x" * 250]
        sensor = self._sensor("\x1e".join(records), key="alerts_system")
        self.assertEqual(sensor.extra_state_attributes["lines"], records)


class SystemEntityProviderMetadataTests(unittest.TestCase):
    @staticmethod
    def _sensor(key, protocol):
        sensor = object.__new__(binary_sensor_module.SystemBinarySensor)
        sensor._description = SimpleNamespace(key=key)
        sensor.coordinator = SimpleNamespace(
            data={key: True},
            config_entry=SimpleNamespace(
                data={
                    const.CONF_PROTOCOL: protocol,
                    const.CONF_PROVIDER_ID: "provider_a",
                }
            ),
            runtime=SimpleNamespace(system_id="system_a"),
        )
        return sensor

    def test_generic_entity_exposes_provider_and_system_identity(self):
        sensor = self._sensor("status_reporting", const.PROTOCOL_ESPHOME_NATIVE)
        self.assertEqual(
            sensor.extra_state_attributes,
            {
                "provider_protocol": const.PROTOCOL_ESPHOME_NATIVE,
                "provider_id": "provider_a",
                "system_id": "system_a",
            },
        )

    def test_other_entity_uses_the_same_generic_metadata_contract(self):
        sensor = self._sensor("state_pump", const.PROTOCOL_WEB_API)
        self.assertEqual(
            sensor.extra_state_attributes,
            {
                "provider_protocol": const.PROTOCOL_WEB_API,
                "provider_id": "provider_a",
                "system_id": "system_a",
            },
        )


class ExternalCoordinatorContractTests(unittest.TestCase):
    def _coordinator(self):
        coordinator = object.__new__(coordinator_module.SystemCoordinator)
        runtime = SimpleNamespace(
            configuration=SimpleNamespace(
                dropped_keys=frozenset({"archive_status"})
            )
        )
        coordinator._system_uid = TEST_SYSTEM_UIDS[0]
        coordinator._hub_runtime = SimpleNamespace(
            systems={TEST_SYSTEM_UIDS[0]: runtime}
        )
        coordinator._evaluated_values = {"normal": 1}
        coordinator._external_entity_values = {}
        coordinator.data = {"normal": 1}
        coordinator.listener_calls = 0
        coordinator.async_update_listeners = lambda: setattr(
            coordinator,
            "listener_calls",
            coordinator.listener_calls + 1,
        )
        return coordinator

    def test_external_values_require_drop_and_keep_attributes_separate(self):
        coordinator = self._coordinator()
        coordinator.async_set_external_entity_values(
            {
                "archive_status": coordinator_module.ExternalEntityValue(
                    "warning",
                    {"coverage_warning_count": 1},
                )
            }
        )
        self.assertEqual(coordinator.data["archive_status"], "warning")
        self.assertEqual(
            dict(coordinator.external_entity_attributes("archive_status")),
            {"coverage_warning_count": 1},
        )
        self.assertNotIn("coverage_warning_count", coordinator.data)
        self.assertEqual(coordinator.listener_calls, 1)
        with self.assertRaises(ValueError):
            coordinator.async_set_external_entity_values(
                {
                    "normal": coordinator_module.ExternalEntityValue(
                        2,
                        {},
                    )
                }
            )


class UnloadLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_unload_waits_for_refresh_and_survives_disconnect_failure(self):
        """A failed remote logout must not obstruct local HA cleanup."""

        class FailingProvider:
            def __init__(self):
                self.disconnect_calls = 0
                self.close_calls = 0

            async def async_disconnect(self):
                self.disconnect_calls += 1
                raise exceptions.ProviderCommunicationError(
                    "simulated logout network failure"
                )

            async def async_close(self):
                self.close_calls += 1

        class ConfigEntries:
            def __init__(self):
                self.unload_calls = []

            async def async_unload_platforms(self, entry, platforms):
                self.unload_calls.append((entry, tuple(platforms)))
                return True

        provider = FailingProvider()
        runtime = configuration_module.HubRuntime(
            hub_uid="00000000-0000-4000-8000-000000000001",
            provider=provider,
            config_revision=1,
            provider_revision=1,
            systems={"system": object()},
            coordinators={"system": object()},
        )
        entry = SimpleNamespace(runtime_data=runtime)
        config_entries = ConfigEntries()
        hass = SimpleNamespace(config_entries=config_entries)

        refresh_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def refresh_in_progress():
            refresh_started.set()
            await release_refresh.wait()

        refresh_task = asyncio.create_task(refresh_in_progress())
        runtime.track_refresh_task(refresh_task)
        await refresh_started.wait()

        unload_task = asyncio.create_task(
            integration_module.async_unload_entry(hass, entry)
        )
        await asyncio.sleep(0)
        self.assertFalse(unload_task.done())
        self.assertEqual(provider.disconnect_calls, 0)
        self.assertEqual(
            runtime.lifecycle_state,
            configuration_module.LifecycleState.QUIESCING,
        )

        release_refresh.set()
        self.assertTrue(await unload_task)
        await asyncio.sleep(0)

        self.assertEqual(provider.disconnect_calls, 1)
        self.assertEqual(provider.close_calls, 1)
        self.assertEqual(len(config_entries.unload_calls), 1)
        self.assertEqual(
            config_entries.unload_calls[0][1],
            tuple(integration_module.PLATFORMS),
        )
        self.assertEqual(
            runtime.lifecycle_state,
            configuration_module.LifecycleState.UNLOADED,
        )
        self.assertFalse(runtime.systems)
        self.assertFalse(runtime.coordinators)
        self.assertFalse(runtime.refresh_tasks)
        self.assertFalse(runtime.reconcile_requested)

    async def test_web_api_logout_is_best_effort_for_http_and_network_errors(self):
        """Both HTTP and transport logout failures leave a closable provider."""

        class FailingExecutor:
            def __init__(self, failure):
                self.failure = failure
                self.is_open = True
                self.execute_calls = []
                self.close_calls = 0

            async def execute(self, flow_name):
                self.execute_calls.append(flow_name)
                raise self.failure

            async def async_close(self):
                self.close_calls += 1
                self.is_open = False

        failures = (
            web_api._HttpStatusError("disconnect_flow", 500),
            exceptions.ProviderCommunicationError(
                "simulated logout timeout"
            ),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                executor = FailingExecutor(failure)
                provider = object.__new__(web_api.WebApiProvider)
                provider._connect_lock = asyncio.Lock()
                provider._connected = True
                provider._closed = False
                provider._initialize_task = None
                provider._executor = executor

                await provider.async_disconnect()

                self.assertFalse(provider._connected)
                self.assertEqual(
                    executor.execute_calls,
                    ["disconnect_flow"],
                )

                await provider.async_close()
                self.assertTrue(provider._closed)
                self.assertEqual(executor.close_calls, 1)


class FormHelperTests(unittest.TestCase):
    def test_empty_fields_restore_factory_default_not_initial_value(self):
        defaults = {"first": "factory_first", "second": "factory_second"}
        self.assertEqual(
            form_helpers.normalize_source_expressions(
                defaults,
                {"first": "   ", "second": " custom "},
                defaults,
            ),
            {"first": "factory_first", "second": "custom"},
        )

    def test_omitted_optional_field_restores_factory_default(self):
        defaults = {"value": "factory"}
        self.assertEqual(
            form_helpers.normalize_source_expressions(defaults, {}, defaults),
            defaults,
        )


class VersionTests(unittest.TestCase):
    def test_release_and_schema_versions(self):
        manifest = json.loads((INTEGRATION / "manifest.json").read_text())
        self.assertEqual(manifest["version"], EXPECTED_PRODUCT_VERSION)
        self.assertEqual(const.EXPRESSION_SCHEMA_VERSION, 11)
        self.assertEqual(
            integration_module.CONFIG_SCHEMA,
            ("config_entry_only", const.DOMAIN),
        )

        tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
        module_assignments = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id
            in {"_CONFIG_ENTRY_VERSION", "_CONFIG_ENTRY_MINOR_VERSION"}
        }
        self.assertEqual(module_assignments["_CONFIG_ENTRY_VERSION"], 1)
        self.assertEqual(
            module_assignments["_CONFIG_ENTRY_MINOR_VERSION"],
            EXPECTED_CONFIG_ENTRY_MINOR_VERSION,
        )
        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ConfigFlowHandler"
        )
        assignments = {
            node.targets[0].id: node.value
            for node in handler.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
        }
        self.assertEqual(
            assignments["VERSION"].id, "_CONFIG_ENTRY_VERSION"
        )
        self.assertEqual(
            assignments["MINOR_VERSION"].id,
            "_CONFIG_ENTRY_MINOR_VERSION",
        )


class ExpressionSchemaMigrationTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _descriptions():
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        return [
            SimpleNamespace(
                key=ast.literal_eval(values["key"]),
                default_source_expression=ast.literal_eval(values["default_source_expression"]),
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Description"
            and (values := {item.arg: item.value for item in node.keywords})
        ]

    def _fixture(self):
        stored = json.loads((Path(__file__).parent / "fixtures" /
                             "solesta_023_source_expressions.json").read_text())
        subentry = SimpleNamespace(
            subentry_id="system-1",
            subentry_type=const.SUBENTRY_TYPE_SYSTEM,
            unique_id=TEST_SYSTEM_UIDS[0],
            data={
                const.CONF_SOURCE_EXPRESSIONS: stored,
                const.CONF_EXPRESSION_SCHEMA_VERSION: 4,
                const.CONF_CONFIG_REVISION: 3,
                const.CONF_SOURCE_SYSTEM_ID: "source_unchanged",
                const.CONF_SYSTEM_ID: "system_unchanged",
                const.CONF_ENABLED: True,
            },
        )
        entry = SimpleNamespace(
            version=1, minor_version=1,
            data={const.CONF_PROTOCOL: const.PROTOCOL_WEB_API,
                  const.CONF_CONFIG_REVISION: 5},
            subentries={subentry.subentry_id: subentry},
        )

        class ConfigEntries:
            writes = 0

            def async_update_subentry(self, current, item, *, data):
                self.writes += 1
                item.data = data

            def async_update_entry(self, current, **changes):
                self.writes += 1
                for key, value in changes.items():
                    setattr(current, key, value)

        return SimpleNamespace(config_entries=ConfigEntries()), entry, subentry

    async def test_production_upgrade_preserves_every_expression_and_identity(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                hass, entry, system = self._fixture()
                if custom:
                    system.data[const.CONF_SOURCE_EXPRESSIONS]["last_report"] = "  last_update  "
                    system.data[const.CONF_SOURCE_EXPRESSIONS]["temp_reserved"] = "null()"
                before = deepcopy(system.data)
                with patch.object(configuration_module, "DESCRIPTIONS", self._descriptions()):
                    self.assertTrue(await integration_module.async_migrate_entry(hass, entry))
                self.assertEqual(system.data[const.CONF_SOURCE_EXPRESSIONS], before[const.CONF_SOURCE_EXPRESSIONS])
                self.assertEqual(system.unique_id, TEST_SYSTEM_UIDS[0])
                for key in (const.CONF_SOURCE_SYSTEM_ID, const.CONF_SYSTEM_ID, const.CONF_ENABLED):
                    self.assertEqual(system.data[key], before[key])
                self.assertEqual(system.data[const.CONF_EXPRESSION_SCHEMA_VERSION], 11)
                self.assertEqual(system.data[const.CONF_CONFIG_REVISION], 4)
                self.assertEqual(entry.data[const.CONF_CONFIG_REVISION], 6)
                self.assertEqual(entry.minor_version, 9)
                saved = deepcopy(system.data)
                self.assertTrue(await integration_module.async_migrate_entry(hass, entry))
                self.assertEqual(system.data, saved)
                self.assertEqual(hass.config_entries.writes, 2)

    async def test_invalid_metadata_prevents_all_writes(self):
        for key, invalid in ((const.CONF_CONFIG_REVISION, False),
                             (const.CONF_EXPRESSION_SCHEMA_VERSION, 5),
                             (const.CONF_SOURCE_EXPRESSIONS, {"temp_collector": None})):
            with self.subTest(key=key):
                hass, entry, system = self._fixture()
                bad = deepcopy(system)
                bad.subentry_id = "bad"
                bad.data[key] = invalid
                entry.subentries["bad"] = bad
                before = deepcopy(system.data)
                with self.assertLogs(integration_module._LOGGER, level="ERROR"):
                    self.assertFalse(await integration_module.async_migrate_entry(hass, entry))
                self.assertEqual(system.data, before)
                self.assertEqual(hass.config_entries.writes, 0)
                self.assertEqual(entry.minor_version, 1)

    async def test_lab_schemas_are_not_migrated(self):
        for minor in range(2, 9):
            with self.subTest(minor=minor):
                hass, entry, system = self._fixture()
                entry.minor_version = minor
                before = deepcopy(system.data)
                with self.assertLogs(integration_module._LOGGER, level="ERROR"):
                    self.assertFalse(await integration_module.async_migrate_entry(hass, entry))
                self.assertEqual(system.data, before)
                self.assertEqual(hass.config_entries.writes, 0)


class TranslationTests(unittest.TestCase):
    def test_dashboard_translation_contract_and_approved_dutch_copy(self):
        paths = (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "nl.json",
        )
        documents = [json.loads(path.read_text()) for path in paths]
        key_sets = [set(document["common"]) for document in documents]
        self.assertEqual(key_sets[0], key_sets[1])
        self.assertEqual(key_sets[0], key_sets[2])
        dutch = documents[2]["common"]
        self.assertEqual(
            dutch["dashboard_contact_support"],
            "Controleer uw systeem en verbinding",
        )
        self.assertEqual(
            dutch["dashboard_loading"],
            "Systeemgegevens worden geladen…",
        )
        self.assertNotIn("Solesta", dutch["dashboard_missing_entities"])
        self.assertNotIn("Solesta", dutch["dashboard_no_systems"])
        self.assertEqual(
            dutch["dashboard_tank_temperature_is"],
            "De temperatuur in je zonneboiler is:",
        )
        self.assertEqual(
            dutch["dashboard_preheated_water"],
            "Het systeem levert {warmteindicatie} voorverwarmd water",
        )
        self.assertEqual(dutch["dashboard_warmth_slight"], "enigszins")
        self.assertEqual(dutch["dashboard_warmth_strong"], "sterk")
        self.assertEqual(dutch["dashboard_circulation"], "Circulatie")
        self.assertNotIn("dashboard_active", dutch)
        for document in documents:
            self.assertTrue(document["common"]["dashboard_warmth_slight"][0].islower())
            self.assertTrue(document["common"]["dashboard_warmth_strong"][0].islower())
        self.assertEqual(
            dutch["dashboard_last_status_change_help"],
            "Een statuswijziging is een verandering van de waarde van een "
            "component van de zonneboiler, een afgeleide waarde of de "
            "communicatieverbinding. Statuswijzigingen zijn heel normaal in "
            "uw zonneboiler.",
        )
        self.assertEqual(
            dutch["dashboard_status_change_info"],
            "Meer informatie over statuswijzigingen",
        )

    def test_live_expression_error_categories_have_field_translations(self):
        expected_keys = {
            "source_value_missing_source",
            "source_value_dependency_failed",
            "source_value_division_by_zero",
            "source_value_type_error",
            "source_value_domain_error",
            "source_value_evaluation_error",
        }
        compile_error_keys = {
            "source_expression_syntax_error",
            "source_expression_function_error",
            "source_expression_dependency_cycle",
            "source_expression_ambiguous_source",
            "source_expression_invalid_source",
        }
        for path in (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "nl.json",
        ):
            with self.subTest(path=path.name):
                translated = json.loads(path.read_text(encoding="utf-8"))
                for kind in ("system", "duplicate_system"):
                    errors = translated["config_subentries"][kind]["error"]
                    for key in expected_keys | compile_error_keys:
                        self.assertTrue(errors[key].strip())

        tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_EVALUATION_FORM_ERRORS"
        )
        self.assertEqual(
            {ast.literal_eval(value) for value in assignment.value.values},
            expected_keys,
        )

    def test_revision_conflict_instructs_user_to_reopen_the_form(self):
        for path in (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
        ):
            translated = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(
                "Close this form and open it again",
                translated["config"]["error"]["configuration_changed"],
            )
            self.assertIn(
                "Close this form and open it again",
                translated["config_subentries"]["system"]["error"]
                ["configuration_changed"],
            )

        dutch = json.loads(
            (INTEGRATION / "translations" / "nl.json").read_text(
                encoding="utf-8"
            )
        )
        for message in (
            dutch["config"]["error"]["configuration_changed"],
            dutch["config_subentries"]["system"]["error"]
            ["configuration_changed"],
        ):
            self.assertIn("Sluit dit formulier en open het opnieuw", message)

    def test_number_validation_exceptions_have_complete_translations(self):
        expected_keys = {
            "number_value_not_real",
            "number_value_not_finite",
            "number_metadata_invalid",
            "number_value_below_minimum",
            "number_value_above_maximum",
            "number_step_not_positive",
            "number_value_step_mismatch",
        }
        for path in (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "nl.json",
        ):
            with self.subTest(path=path.name):
                translated = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(set(translated["exceptions"]), expected_keys)
                for value in translated["exceptions"].values():
                    self.assertTrue(value["message"].strip())

        source = (INTEGRATION / "number.py").read_text(encoding="utf-8")
        self.assertIn("raise ServiceValidationError(", source)
        self.assertIn("translation_domain=DOMAIN", source)
        self.assertIn("translation_key=err.translation_key", source)

    def test_reconfigure_checks_conflicts_before_live_validation(self):
        tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
        handler = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "SystemSubentryFlowHandler"
        )
        method = next(
            node
            for node in handler.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "async_step_reconfigure"
        )
        calls = {
            node.func.id: node.lineno
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            in {"_merge_system_data", "_async_live_validate_system"}
        }
        self.assertLess(
            calls["_merge_system_data"],
            calls["_async_live_validate_system"],
        )

    def test_reconfigure_keeps_an_unavailable_stored_source_and_validates_changed_expressions(self):
        source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        handler = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "SystemSubentryFlowHandler"
        )
        method = next(
            node for node in handler.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "async_step_reconfigure"
        )
        body = ast.get_source_segment(source, method)
        self.assertIn("stored_source_system_id", body)
        self.assertIn("source_options = available_sources", body)
        self.assertIn("_async_discover_communication_systems", body)
        self.assertIn("expressions_changed", body)
        self.assertIn("or expressions_changed", body)
        self.assertIn("if requires_live_validation:", body)
        self.assertIn("allow_offline_contract=False", body)
        self.assertIn("validation.required_source_keys", body)
        self.assertNotIn("source_options[0]", body)
        self.assertNotIn("async_abort(reason=_provider_error_key(err))", body)

    def test_temporary_mqtt_validation_uses_a_distinct_client_id(self):
        source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("client_id_nonce=uuid4().hex", source)

    def test_rest_flow_configuration_is_not_exposed(self):
        self.assertNotIn(
            "ObjectSelector",
            (INTEGRATION / "config_flow.py").read_text(encoding="utf-8"),
        )
        for path in (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "nl.json",
        ):
            translated = json.loads(path.read_text(encoding="utf-8"))
            steps = translated["config"]["step"]
            self.assertNotIn("rest_config", steps["web_api"]["data"])
            self.assertNotIn("rest_config", steps["reconfigure"]["data"])

    def test_subentry_menu_labels_are_present_in_all_translation_files(self):
        expected = {
            "strings.json": ("Add system", "Reconfigure system"),
            "en.json": ("Add system", "Reconfigure system"),
            "nl.json": ("Voeg systeem toe", "Systeem herconfigureren"),
        }
        expected_entry_types = {
            "strings.json": (
                "Solar water heater",
                "Duplicate solar water heater",
            ),
            "en.json": (
                "Solar water heater",
                "Duplicate solar water heater",
            ),
            "nl.json": ("Zonneboiler", "Dubbele zonneboiler"),
        }
        paths = {
            "strings.json": INTEGRATION / "strings.json",
            "en.json": INTEGRATION / "translations" / "en.json",
            "nl.json": INTEGRATION / "translations" / "nl.json",
        }
        for name, path in paths.items():
            with self.subTest(name=name):
                document = json.loads(path.read_text())
                subentries = document["config_subentries"]
                initiate_flow = subentries["system"][
                    "initiate_flow"
                ]
                self.assertEqual(
                    (initiate_flow["user"], initiate_flow["reconfigure"]),
                    expected[name],
                )
                self.assertEqual(
                    (
                        subentries["system"]["entry_type"],
                        subentries["duplicate_system"]["entry_type"],
                    ),
                    expected_entry_types[name],
                )
                self.assertNotIn("title", subentries["system"])
                self.assertNotIn("title", subentries["duplicate_system"])

    def test_provider_and_duplicate_system_flows_are_fully_translated(self):
        for path in (
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "nl.json",
        ):
            with self.subTest(path=path.name):
                document = json.loads(path.read_text())
                self.assertNotIn(
                    "duplicate_provider", document["config"]["step"]
                )
                self.assertIn(
                    "provider_id",
                    document["config"]["step"]["web_api"]["data"],
                )
                self.assertIn(
                    "linked_systems_missing", document["config"]["error"]
                )
                self.assertIn(
                    "linked_systems_invalid", document["config"]["error"]
                )
                duplicate = document["config_subentries"]["duplicate_system"]
                self.assertTrue(duplicate["initiate_flow"]["user"].strip())
                self.assertEqual(
                    set(duplicate["step"]["user"]["data"]),
                    {"source_system_id", "communication_source_system_id"},
                )

        dutch = json.loads(
            (INTEGRATION / "translations" / "nl.json").read_text()
        )
        self.assertEqual(
            dutch["config_subentries"]["duplicate_system"]
            ["initiate_flow"]["user"],
            "Koppel een duplicaatsysteem",
        )

        tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
        methods = {
            node.name: {
                child.name
                for child in node.body
                if isinstance(child, ast.AsyncFunctionDef)
            }
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        self.assertIn(
            "async_step_system", methods["SystemSubentryFlowHandler"]
        )
        self.assertIn(
            "async_step_duplicate_system",
            methods["DuplicateSystemSubentryFlowHandler"],
        )

    def test_hub_reconfigure_distinguishes_same_and_new_protocol(self):
        source = (INTEGRATION / "config_flow.py").read_text()
        self.assertIn("linked_entry=entry", source)
        self.assertIn("_publish_provider_candidate", source)
        self.assertIn("CONF_VALIDATED_PROVIDER_REVISION", source)
        self.assertNotIn("reconfigure_successful_systems_disabled", source)
        self.assertIn("if protocol_changed:", source)
        self.assertIn("subentry_data[CONF_ENABLED] = False", source)
        self.assertIn("linked_entry=None if protocol_changed else entry", source)
        self.assertIn("minor_version=_CONFIG_ENTRY_MINOR_VERSION", source)

    def test_report_delay_has_entity_and_form_translations(self):
        expected_names = {
            "strings.json": "Report delay",
            "en.json": "Report delay",
            "nl.json": "Rapportagevertraging",
        }
        paths = {
            "strings.json": INTEGRATION / "strings.json",
            "en.json": INTEGRATION / "translations" / "en.json",
            "nl.json": INTEGRATION / "translations" / "nl.json",
        }
        for name, path in paths.items():
            with self.subTest(name=name):
                document = json.loads(path.read_text())
                self.assertEqual(
                    document["entity"]["sensor"]["report_delay"]["name"],
                    expected_names[name],
                )
                for step in ("details", "reconfigure"):
                    label = document["config_subentries"]["system"]["step"][
                        step
                    ]["data"]["report_delay"]
                    self.assertIsInstance(label, str)
                    self.assertTrue(label.strip())


class GeneratedEntityTests(unittest.TestCase):
    @staticmethod
    def _generated_descriptions():
        """Return generated Description keyword values keyed by entity key."""
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        descriptions = {}
        for call in (
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ):
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            key = values.get("key")
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                descriptions[key.value] = values
        return descriptions

    def test_v8_adds_universal_alert_configuration(self):
        descriptions = self._generated_descriptions()

        self.assertEqual(len(descriptions), 21)
        self.assertIn("temp_tank_average", descriptions)
        self.assertEqual(
            ast.literal_eval(
                descriptions["report_delay"]["default_source_expression"]
            ),
            "delay_zone(last_report, 2*60+30, 10*60)",
        )
        self.assertEqual(
            ast.literal_eval(descriptions["report_delay"]["icon"]),
            "mdi:timer-sand",
        )
        self.assertIsNone(
            ast.literal_eval(
                descriptions["report_delay"][
                    "suggested_display_precision"
                ]
            )
        )
        self.assertTrue(
            ast.literal_eval(
                descriptions["report_delay"][
                    "entity_registry_enabled_default"
                ]
            )
        )
        for key in (
            "alert_collector_hot_threshold",
            "alert_collector_danger_threshold",
            "alert_pump_idle_delta",
            "alert_pump_active_delta",
        ):
            self.assertNotIn(key, descriptions)
        self.assertFalse(
            ast.literal_eval(
                descriptions["last_report"][
                    "entity_registry_enabled_default"
                ]
            )
        )
        self.assertEqual(
            ast.literal_eval(
                descriptions["weekly_archive"]["default_source_expression"]
            ),
            "False",
        )
        self.assertEqual(
            ast.literal_eval(
                descriptions["archive_last_success"][
                    "default_source_expression"
                ]
            ),
            "drop()",
        )
        self.assertEqual(
            ast.literal_eval(descriptions["archive_status"]["options"]),
            ("waiting", "disabled", "ok", "warning", "error"),
        )

    def test_dashboard_metadata_matches_the_generated_entity_catalog(self):
        descriptions = self._generated_descriptions()
        source = (
            INTEGRATION / "frontend" / "solesta-status-card.js"
        ).read_text()
        metadata_source = source.split(
            "const CARD_ENTITY_METADATA = Object.freeze({", 1
        )[1].split("});", 1)[0]
        mappings = re.findall(
            r'^\s*([a-z_]+): \["([a-z_]+)", "([a-z_]+)"\],$',
            metadata_source,
            flags=re.MULTILINE,
        )
        self.assertEqual(len(mappings), 13)
        for card_key, domain, translation_key in mappings:
            with self.subTest(card_key=card_key):
                self.assertIn(translation_key, descriptions)
                generated = descriptions[translation_key]
                self.assertEqual(
                    ast.literal_eval(generated["translation_key"]),
                    translation_key,
                )
                entity_type = generated["entity_type"]
                self.assertIsInstance(entity_type, ast.Attribute)
                self.assertEqual(entity_type.attr.lower(), domain)

    def test_confirmed_solesta_golden_energy_results(self):
        """Keep the approved Solesta temperature and energy chain stable."""
        descriptions = self._generated_descriptions()
        keys = (
            "temp_tank_top",
            "temp_tank_bottom",
            "temp_tank_average",
            "volume_tank",
            "temp_coldwater",
            "energy_shower_kwh",
            "energy_tank_mj",
            "energy_tank_kwh",
            "energy_tank_showers",
        )
        generated_expressions = {
            key: ast.literal_eval(
                descriptions[key]["default_source_expression"]
            )
            for key in keys
        }
        golden_cases = (
            {
                "name": "representative_default_tank",
                "source": {"temp2": 39, "temp3": 36},
                "numbers": {
                    "volume_tank": "100",
                    "temp_coldwater": "12",
                },
                "expected": {
                    "temp_tank_average": 37.5,
                    "energy_shower_kwh": 1.20929,
                    "energy_tank_mj": 10.6743,
                    "energy_tank_kwh": 2.965,
                    "energy_tank_showers": 2.45,
                },
            },
            {
                "name": "no_energy_above_cold_water",
                "source": {"temp2": 12, "temp3": 12},
                "numbers": {
                    "volume_tank": "100",
                    "temp_coldwater": "12",
                },
                "expected": {
                    "temp_tank_average": 12.0,
                    "energy_shower_kwh": 1.20929,
                    "energy_tank_mj": 0.0,
                    "energy_tank_kwh": 0.0,
                    "energy_tank_showers": 0.0,
                },
            },
            {
                "name": "custom_number_settings",
                "source": {"temp2": 65, "temp3": 55},
                "numbers": {
                    "volume_tank": "120",
                    "temp_coldwater": "10",
                    "energy_shower_kwh": "1.5",
                },
                "expected": {
                    "temp_tank_average": 60.0,
                    "energy_tank_mj": 25.116,
                    "energy_tank_kwh": 6.977,
                    "energy_tank_showers": 4.65,
                },
            },
        )

        for case in golden_cases:
            with self.subTest(case=case["name"]):
                expressions = dict(generated_expressions)
                expressions.update(case["numbers"])
                compiled = compile_module.compile_source_expressions(
                    expressions
                )
                result = evaluator_actual.evaluate_source_expressions(
                    compiled, case["source"]
                )
                self.assertFalse(result.errors)
                self.assertEqual(
                    {
                        key: result.values[key]
                        for key in case["expected"]
                    },
                    case["expected"],
                )

        self.assertEqual(
            {
                key: ast.literal_eval(
                    descriptions[key]["suggested_display_precision"]
                )
                for key in (
                    "temp_tank_average",
                    "energy_tank_mj",
                    "energy_tank_kwh",
                    "energy_tank_showers",
                )
            },
            {
                "temp_tank_average": 1,
                "energy_tank_mj": 4,
                "energy_tank_kwh": 3,
                "energy_tank_showers": 2,
            },
        )

    def test_energy_metadata_and_factory_formulas_match_the_approved_model(self):
        descriptions = self._generated_descriptions()
        self.assertEqual(
            descriptions["energy_tank_mj"]["state_class"].attr,
            "MEASUREMENT",
        )
        self.assertEqual(
            descriptions["energy_tank_kwh"]["state_class"].attr,
            "MEASUREMENT",
        )
        self.assertEqual(
            ast.literal_eval(
                descriptions["energy_tank_kwh"]["default_source_expression"]
            ),
            "round(energy_tank_mj / 3.6, 3)",
        )
        self.assertEqual(
            ast.literal_eval(
                descriptions["energy_shower_kwh"]["default_source_expression"]
            ),
            "round( (5 * 8 * (38 - temp_coldwater) * 4.186) / 3600, 5)",
        )

    def test_generated_round_precision_matches_display_precision(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        for call in (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Description"
        ):
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            key = ast.literal_eval(values["key"])
            precision = ast.literal_eval(
                values["suggested_display_precision"]
            )
            expression = ast.parse(
                ast.literal_eval(values["default_source_expression"]),
                mode="eval",
            )
            for round_call in (
                node
                for node in ast.walk(expression)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "round"
            ):
                digits = (
                    0
                    if len(round_call.args) == 1
                    else ast.literal_eval(round_call.args[1])
                )
                with self.subTest(key=key):
                    self.assertEqual(digits, precision)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_runs_once_and_primes_first_status(self):
        provider = _FakeProvider()
        await asyncio.gather(
            provider.async_initialize(),
            provider.async_initialize(),
        )
        self.assertEqual(provider.calls["profile"], 1)
        self.assertEqual(provider.calls["systems"], 1)
        self.assertEqual(provider.calls["status"], 1)
        self.assertEqual(provider.systems, TEST_SYSTEM_IDS)
        self.assertEqual(provider.available_keys, ("status", "temp1"))

        first = await provider.get_system_snapshot("test_boiler_1", {"temp1"}, {"temp1"})
        self.assertEqual(first["temp1"], 41.0)
        self.assertEqual(provider.calls["status"], 1)

    async def test_configured_keys_are_authoritative(self):
        provider = _FakeProvider(("manual_key",))
        await provider.async_initialize()
        self.assertEqual(provider.calls["status"], 0)
        self.assertEqual(provider.available_keys, ("manual_key",))
        self.assertEqual(
            provider.unavailable_keys(["other", "manual_key", "other"]),
            ["other"],
        )

    async def test_unknown_keyset_is_conservative(self):
        provider = _FakeProvider()
        self.assertEqual(
            provider.unavailable_keys(["temp2", "temp1"]),
            ["temp1", "temp2"],
        )

    def test_source_system_ids_are_opaque_text_or_numbers(self):
        cases = (
            (" SOL_01 ", " SOL_01 "),
            (123456, "123456"),
            (-7, "-7"),
            (12.5, "12.5"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    provider_module.normalise_source_system_id(value),
                    expected,
                )

    def test_invalid_or_extreme_source_system_ids_are_rejected(self):
        invalid = (
            None,
            True,
            "",
            "   ",
            {},
            [],
            object(),
            float("nan"),
            float("inf"),
            "x" * 65534,
        )
        for value in invalid:
            with self.subTest(value=repr(value)):
                with self.assertRaises(exceptions.ProviderResponseError):
                    provider_module.normalise_source_system_id(value)

    async def test_discovery_normalises_numeric_source_system_id(self):
        provider = _FakeProvider(
            ("manual_key",),
            systems=(123456,),
            statuses={123456: {"manual_key": 1}},
        )
        await provider.async_initialize()
        self.assertEqual(provider.systems, ("123456",))

    async def test_discovery_rejects_invalid_source_system_id(self):
        for value in (None, object(), "x" * 65534):
            with self.subTest(value=repr(value)):
                provider = _FakeProvider(
                    ("manual_key",),
                    systems=(value,),
                    statuses={value: {"manual_key": 1}},
                )
                with self.assertRaises(exceptions.ProviderResponseError):
                    await provider.async_initialize()

    async def test_duplicate_system_is_discovered_and_routes_status_only(self):
        provider = _FakeProvider(
            ("status", "temp1"),
            provider_id="duplicate_webapi",
            duplicate_systems={"duplicate_boiler": "test_boiler_1"},
        )
        await provider.async_initialize()

        self.assertEqual(provider.provider_id, "duplicate_webapi")
        self.assertEqual(provider.communication_systems, TEST_SYSTEM_IDS)
        self.assertEqual(
            provider.systems,
            (*TEST_SYSTEM_IDS, "duplicate_boiler"),
        )

        status = await provider.get_system_snapshot("duplicate_boiler", {"temp1"}, {"temp1"})
        self.assertEqual(status["temp1"], 41.0)
        self.assertEqual(
            provider.status_calls[-1][0],
            "test_boiler_1",
        )

    def test_duplicate_system_mapping_fields_must_be_valid_and_distinct(self):
        for mapping in (
            {"same": "same"},
            {"": "source"},
            {"alias": ""},
        ):
            with self.subTest(mapping=mapping):
                with self.assertRaises(exceptions.ProviderConfigurationError):
                    _FakeProvider(duplicate_systems=mapping)

    async def test_duplicate_alias_chains_are_never_followed(self):
        provider = _FakeProvider(
            ("temp1",),
            duplicate_systems={"alias_a": "alias_b", "alias_b": "test_boiler_1"},
        )
        await provider.async_initialize()
        self.assertNotIn("alias_a", provider.systems)
        self.assertIn("alias_b", provider.systems)
        with self.assertRaises(exceptions.ProviderSystemError):
            await provider.get_system_snapshot("alias_a", ("temp1",), ("temp1",))
        status = await provider.get_system_snapshot("alias_b", ("temp1",), ("temp1",))
        self.assertEqual(status["temp1"], 41.0)

    async def test_duplicate_system_may_not_collide_with_real_discovery(self):
        provider = _FakeProvider(
            ("temp1",),
            duplicate_systems={"test_boiler_1": "test_boiler_2"},
        )
        await provider.async_initialize()
        self.assertEqual(provider.systems, TEST_SYSTEM_IDS)
        status = await provider.get_system_snapshot("test_boiler_1", ("temp1",), ("temp1",))
        self.assertEqual(status["temp1"], 41.0)

    async def test_duplicate_target_must_come_from_real_discovery(self):
        provider = _FakeProvider(
            ("temp1",),
            duplicate_systems={"duplicate_boiler": "missing_boiler"},
        )
        await provider.async_initialize()
        self.assertEqual(provider.systems, TEST_SYSTEM_IDS)
        with self.assertRaises(exceptions.ProviderSystemError):
            await provider.get_system_snapshot("duplicate_boiler", ("temp1",), ("temp1",))
        status = await provider.get_system_snapshot("test_boiler_2", ("temp1",), ("temp1",))
        self.assertEqual(status["temp1"], 52.0)


TEST_HUB_UID = "00000000-0000-4000-8000-000000000000"
TEST_SYSTEM_UIDS = (
    "00000000-0000-4000-8000-000000000001",
    "00000000-0000-4000-8000-000000000002",
    "00000000-0000-4000-8000-000000000003",
)


def _system_subentry(index, *, enabled=True, interval=None):
    source_system_id = TEST_SYSTEM_IDS[index]
    return SimpleNamespace(
        subentry_id=f"subentry-{index + 1}",
        subentry_type=const.SUBENTRY_TYPE_SYSTEM,
        unique_id=TEST_SYSTEM_UIDS[index],
        data={
            const.CONF_ENABLED: enabled,
            const.CONF_SYSTEM_ID: source_system_id,
            const.CONF_SOURCE_SYSTEM_ID: source_system_id,
            const.CONF_SOURCE_EXPRESSIONS: {
                const.UPDATE_INTERVAL_ENTITY_KEY: str(
                    interval if interval is not None else (index + 1) * 11
                )
            },
            const.CONF_CONFIG_REVISION: 1,
            const.CONF_EXPRESSION_SCHEMA_VERSION:
                const.EXPRESSION_SCHEMA_VERSION,
            const.CONF_VALIDATED_HUB_UID: TEST_HUB_UID,
            const.CONF_VALIDATED_PROVIDER_REVISION: 7,
        },
    )


def _hub_entry(*subentries):
    return SimpleNamespace(
        unique_id=TEST_HUB_UID,
        data={
            const.CONF_CONFIG_REVISION: 1,
            const.CONF_PROVIDER_REVISION: 7,
        },
        subentries={
            subentry.subentry_id: subentry
            for subentry in subentries
        },
    )


class CachedProviderFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_measurements_age_offline_and_recover(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        expression_by_key = {}
        coordinator_descriptions = []
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Name)
                or node.func.id != "Description"
            ):
                continue
            values = {item.arg: item.value for item in node.keywords}
            key = ast.literal_eval(values["key"])
            expression_by_key[key] = ast.literal_eval(
                values["default_source_expression"]
            )
            category_node = values["entity_category"]
            category = (
                category_node.attr.lower()
                if isinstance(category_node, ast.Attribute)
                else None
            )
            coordinator_descriptions.append(
                SimpleNamespace(key=key, entity_category=category)
            )

        expressions = {
            key: value
            for key, value in expression_by_key.items()
            if value != "drop()"
        }
        compiled = compile_module.compile_source_expressions(expressions)
        runtime_configuration = SimpleNamespace(
            compiled_source_expressions=compiled,
            required_source_keys=compiled.source_keys,
            source_keys=compiled.source_keys,
            dropped_keys=frozenset(
                key
                for key, value in expression_by_key.items()
                if value == "drop()"
            ),
        )

        previous_evaluator = sys.modules[f"{PACKAGE}.evaluator"]
        previous_descriptions = thetruth_stub.DESCRIPTIONS
        sys.modules[f"{PACKAGE}.evaluator"] = evaluator_actual
        thetruth_stub.DESCRIPTIONS = coordinator_descriptions
        try:
            actual_coordinator = _load_as(
                "coordinator_offline_actual",
                "coordinator",
            )
        finally:
            sys.modules[f"{PACKAGE}.evaluator"] = previous_evaluator
            thetruth_stub.DESCRIPTIONS = previous_descriptions

        base = datetime(2026, 10, 25, 8, 0, tzinfo=timezone.utc)

        class System:
            fail = False

            def __init__(self):
                self.last_update = base

            async def status(self, required_keys, referenced_keys=None):
                self.required_keys = required_keys
                self.referenced_keys = referenced_keys
                if self.fail:
                    raise exceptions.ProviderCommunicationError("offline")
                return SimpleNamespace(
                    values={
                        "last_update": self.last_update.isoformat(),
                        "temp1": 75,
                        "temp2": 45,
                        "temp3": 35,
                        "temp4": 20,
                        "pump": 0,
                        "alerts": [],
                    },
                    last_report=self.last_update,
                    last_update=self.last_update,
                )

        system = System()
        system_runtime = SimpleNamespace(
            system_id="boiler",
            system_uid="system-uid",
            subentry_id="subentry",
            runtime_generation=1,
            system=system,
            configuration=runtime_configuration,
        )
        hub_runtime = SimpleNamespace(
            lifecycle_state=configuration_module.LifecycleState.ACTIVE,
            systems={"system-uid": system_runtime},
            track_refresh_task=lambda task: None,
        )
        coordinator = actual_coordinator.SystemCoordinator(
            SimpleNamespace(),
            SimpleNamespace(),
            hub_runtime,
            "system-uid",
        )

        with patch.object(
            expression_functions,
            "_utc_now",
            return_value=base + timedelta(seconds=100),
        ):
            fresh = await coordinator._async_update_data()
        self.assertTrue(fresh["status_reporting"])
        self.assertEqual(fresh["temp_collector"], 75)

        system.fail = True
        with patch.object(
            expression_functions,
            "_utc_now",
            return_value=base + timedelta(seconds=601),
        ):
            stale = await coordinator._async_update_data()
        self.assertFalse(stale["status_reporting"])
        self.assertIsNone(stale["temp_collector"])
        self.assertEqual(stale["last_report"], base)
        self.assertEqual(stale["report_delay"], base.isoformat())
        self.assertEqual(
            json.loads(stale["alerts_system"]),
            {
                "type": "offline",
                "translation_key": "alert_offline",
                "severity": "danger",
            },
        )
        self.assertEqual(
            coordinator.provider_error,
            "ProviderCommunicationError",
        )

        system.fail = False
        system.last_update = base + timedelta(seconds=602)
        with patch.object(
            expression_functions,
            "_utc_now",
            return_value=base + timedelta(seconds=602),
        ):
            restored = await coordinator._async_update_data()
        self.assertTrue(restored["status_reporting"])
        self.assertEqual(restored["temp_collector"], 75)
        self.assertIsNone(coordinator.provider_error)


class DuplicateTargetIdentityTests(unittest.TestCase):
    def test_provider_targets_preserve_spaces_and_use_the_byte_limit(self):
        for target in (" root ", "x" * 257, "x" * 65533, "é" * 32766 + "x"):
            with self.subTest(bytes=len(target.encode())):
                item = SimpleNamespace(subentry_type=const.SUBENTRY_TYPE_DUPLICATE_SYSTEM,
                    data={const.CONF_SOURCE_SYSTEM_ID: "copy",
                          const.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: target})
                entry = SimpleNamespace(subentries={"copy": item})
                self.assertEqual(configuration_module.duplicate_systems_from_entry(entry), {"copy": target})

    def test_malformed_targets_and_local_aliases_stay_isolated(self):
        for local, target in (("copy", "x" * 65534), ("copy", "é" * 32767),
                              ("copy", None), ("copy", ""), ("copy", "   "),
                              (" copy ", "root"), ("x" * 257, "root"), ("same", "same")):
            with self.subTest(local_length=len(local), target_type=type(target).__name__):
                item = SimpleNamespace(subentry_type=const.SUBENTRY_TYPE_DUPLICATE_SYSTEM,
                    data={const.CONF_SOURCE_SYSTEM_ID: local,
                          const.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: target})
                self.assertEqual(configuration_module.duplicate_systems_from_entry(
                    SimpleNamespace(subentries={"copy": item})), {})


class MultiSystemFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_duplicate_mapping_add_or_remove_rebuilds_provider(self):
        provider = _FakeProvider(
            ("status", "temp1"),
            duplicate_systems={"duplicate_boiler": "test_boiler_1"},
        )
        await provider.async_initialize()
        duplicate_subentry = SimpleNamespace(
            subentry_id="duplicate-subentry",
            subentry_type=const.SUBENTRY_TYPE_DUPLICATE_SYSTEM,
            unique_id=TEST_SYSTEM_UIDS[0],
            data={
                const.CONF_SOURCE_SYSTEM_ID: "duplicate_boiler",
                const.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: "test_boiler_1",
                const.CONF_ENABLED: False,
            },
        )
        entry = SimpleNamespace(
            unique_id=TEST_HUB_UID,
            data={
                const.CONF_CONFIG_REVISION: 1,
                const.CONF_PROVIDER_REVISION: 1,
            },
            subentries={duplicate_subentry.subentry_id: duplicate_subentry},
        )
        runtime = configuration_module.HubRuntime(
            hub_uid=TEST_HUB_UID,
            provider=provider,
            config_revision=1,
            provider_revision=1,
        )

        self.assertTrue(runtime.matches_persistence(entry))
        entry.subentries = {}
        self.assertFalse(runtime.matches_persistence(entry))

    async def test_evaluation_error_logging_and_diagnostics_are_redacted_and_change_driven(self):
        provider = _FakeProvider(
            configured=("status", "temp1", "__evaluation_error__")
        )
        await provider.async_initialize()
        subentry = _system_subentry(0)
        entry = _hub_entry(subentry)
        entry.entry_id = "entry-1"
        hub_runtime = configuration_module.HubRuntime(
            hub_uid=TEST_HUB_UID,
            provider=provider,
            config_revision=1,
            provider_revision=7,
        )
        hub_runtime.systems = configuration_module.build_system_runtimes(
            entry, provider, hub_runtime.runtime_generation
        )
        coordinator = coordinator_module.SystemCoordinator(
            SimpleNamespace(), entry, hub_runtime, TEST_SYSTEM_UIDS[0]
        )
        hub_runtime.coordinators = {TEST_SYSTEM_UIDS[0]: coordinator}
        entry.runtime_data = hub_runtime
        provider.set_system_status(
            TEST_SYSTEM_IDS[0],
            {
                "status": "online",
                "temp1": 41.0,
                "__evaluation_error__": "VALUE_MUST_NOT_BE_LOGGED",
            },
        )

        with self.assertLogs(coordinator_module._LOGGER, level="WARNING") as first:
            await coordinator.async_refresh()
        log_text = "\n".join(first.output)
        self.assertIn("temp_tank_average:missing_source", log_text)
        self.assertIn("__evaluation_error__", log_text)
        self.assertNotIn("VALUE_MUST_NOT_BE_LOGGED", log_text)
        diagnostics = await diagnostics_module.async_get_config_entry_diagnostics(
            SimpleNamespace(), entry
        )
        serialized = json.dumps(diagnostics)
        self.assertIn('"entity_key": "temp_tank_average"', serialized)
        self.assertIn('"category": "missing_source"', serialized)
        self.assertIn('"available_source_keys"', serialized)
        self.assertIn('"system_index": 1', serialized)
        self.assertNotIn("VALUE_MUST_NOT_BE_LOGGED", serialized)
        self.assertNotIn(entry.entry_id, serialized)
        self.assertNotIn(TEST_SYSTEM_UIDS[0], serialized)

        with self.assertNoLogs(coordinator_module._LOGGER, level="INFO"):
            await coordinator.async_refresh()

        provider.set_system_status(
            TEST_SYSTEM_IDS[0], {"status": "online", "temp1": 41.0}
        )
        with self.assertLogs(coordinator_module._LOGGER, level="INFO") as restored:
            await coordinator.async_refresh()
        self.assertIn("errors cleared", "\n".join(restored.output))

    async def test_one_provider_serves_three_independent_system_models(self):
        provider = _FakeProvider(configured=("status", "temp1"))
        await provider.async_initialize()

        systems = [
            system_module.System(
                system_uid=system_uid,
                system_id=f"boiler_{index}",
                source_system_id=source_system_id,
                provider=provider,
            )
            for index, (system_uid, source_system_id) in enumerate(
                zip(TEST_SYSTEM_UIDS, TEST_SYSTEM_IDS, strict=True),
                start=1,
            )
        ]
        statuses = await asyncio.gather(
            *(system.status({"status", "temp1"}, {"status", "temp1"}) for system in systems)
        )

        self.assertEqual(
            [status["temp1"] for status in statuses],
            [41.0, 52.0, 63.0],
        )
        self.assertTrue(all(system.provider is provider for system in systems))
        self.assertEqual(
            {system.source_system_id for system in systems},
            set(TEST_SYSTEM_IDS),
        )
        self.assertEqual(
            {system.info["system_uid"] for system in systems},
            set(TEST_SYSTEM_UIDS),
        )
        self.assertEqual(provider.status_calls_by_system, {
            source_system_id: 1
            for source_system_id in TEST_SYSTEM_IDS
        })

        with self.assertRaises(TypeError):
            statuses[0].values["temp1"] = -999
        unchanged = await systems[0].status({"temp1"}, {"temp1"})
        self.assertEqual(unchanged["temp1"], 41.0)

    async def test_coordinators_refresh_concurrently_and_isolate_failure(self):
        provider = _FakeProvider(configured=("status", "temp1"))
        await provider.async_initialize()
        entry = _hub_entry(
            _system_subentry(0, interval=11),
            _system_subentry(1, interval=22),
            _system_subentry(2, interval=33),
        )
        hub_runtime = configuration_module.HubRuntime(
            hub_uid=TEST_HUB_UID,
            provider=provider,
            config_revision=1,
            provider_revision=7,
        )
        hub_runtime.systems = configuration_module.build_system_runtimes(
            entry,
            provider,
            hub_runtime.runtime_generation,
        )
        hass = SimpleNamespace()
        hub_runtime.coordinators = {
            system_uid: coordinator_module.SystemCoordinator(
                hass,
                entry,
                hub_runtime,
                system_uid,
            )
            for system_uid in hub_runtime.systems
        }

        provider.block_next_status_wave(3)
        first_refreshes = [
            asyncio.create_task(coordinator.async_refresh())
            for coordinator in hub_runtime.coordinators.values()
        ]
        try:
            await provider.wait_for_blocked_status_wave()
            self.assertEqual(provider.max_concurrent_status_calls, 3)
        finally:
            provider.release_status_wave()
        await asyncio.gather(*first_refreshes)

        for index, system_uid in enumerate(TEST_SYSTEM_UIDS):
            coordinator = hub_runtime.coordinators[system_uid]
            self.assertIsNone(coordinator.last_exception)
            self.assertEqual(
                coordinator.data["temp1"],
                TEST_SYSTEM_STATUSES[TEST_SYSTEM_IDS[index]]["temp1"],
            )
            self.assertEqual(
                coordinator.update_interval,
                timedelta(seconds=(index + 1) * 11),
            )

        provider.set_system_failure("test_boiler_2")
        provider.set_system_status(
            "test_boiler_1", {"temp1": 41.5, "status": "online"}
        )
        provider.set_system_status(
            "test_boiler_3", {"temp1": 63.5, "status": "heating"}
        )
        provider.block_next_status_wave(3)
        second_refreshes = [
            asyncio.create_task(coordinator.async_refresh())
            for coordinator in hub_runtime.coordinators.values()
        ]
        try:
            await provider.wait_for_blocked_status_wave()
            self.assertEqual(provider.max_concurrent_status_calls, 3)
        finally:
            provider.release_status_wave()
        await asyncio.gather(*second_refreshes)

        first = hub_runtime.coordinators[TEST_SYSTEM_UIDS[0]]
        defective = hub_runtime.coordinators[TEST_SYSTEM_UIDS[1]]
        third = hub_runtime.coordinators[TEST_SYSTEM_UIDS[2]]
        self.assertEqual(first.data["temp1"], 41.5)
        self.assertEqual(third.data["temp1"], 63.5)
        self.assertIsNone(first.last_exception)
        self.assertIsNone(third.last_exception)
        self.assertIsNone(defective.last_exception)
        self.assertEqual(defective.data["temp1"], 52.0)
        self.assertEqual(
            provider.status_calls_by_system,
            {source_system_id: 2 for source_system_id in TEST_SYSTEM_IDS},
        )

        provider.clear_system_failure("test_boiler_2")
        provider.set_system_status(
            "test_boiler_2", {"temp1": 52.5, "status": "online"}
        )
        await defective.async_refresh()
        self.assertIsNone(defective.last_exception)
        self.assertEqual(defective.data["temp1"], 52.5)
        self.assertEqual(provider.status_calls_by_system, {
            "test_boiler_1": 2,
            "test_boiler_2": 3,
            "test_boiler_3": 2,
        })

    async def test_runtime_rebuild_adds_disables_reconfigures_and_removes(self):
        provider = _FakeProvider(configured=("status", "temp1"))
        first = _system_subentry(0)
        second = _system_subentry(1)
        entry = _hub_entry(first, second)

        initial = configuration_module.build_system_runtimes(
            entry, provider, 1
        )
        self.assertEqual(set(initial), set(TEST_SYSTEM_UIDS[:2]))

        third = _system_subentry(2)
        entry.subentries[third.subentry_id] = third
        added = configuration_module.build_system_runtimes(
            entry, provider, 2
        )
        self.assertEqual(set(added), set(TEST_SYSTEM_UIDS))
        self.assertEqual(
            {runtime.source_system_id for runtime in added.values()},
            set(TEST_SYSTEM_IDS),
        )
        self.assertEqual(
            len({runtime.system_id for runtime in added.values()}),
            3,
        )

        description = SimpleNamespace(
            key="temp_collector",
            translation_key="temp_collector",
            name="Collector temperature",
            device_class=None,
            native_unit_of_measurement="°C",
            state_class=None,
            entity_category=None,
            icon="mdi:solar-panel",
            entity_registry_enabled_default=True,
            entity_registry_visible_default=True,
            suggested_display_precision=0,
            has_entity_name=True,
        )
        entities = [
            entity_module.SystemEntity(
                SimpleNamespace(
                    runtime=runtime,
                    data={},
                    hass=SimpleNamespace(),
                ),
                description,
            )
            for runtime in added.values()
        ]
        self.assertEqual(
            len({entity._attr_unique_id for entity in entities}),
            3,
        )
        self.assertEqual(
            {
                next(iter(entity._attr_device_info["identifiers"]))[1]
                for entity in entities
            },
            set(TEST_SYSTEM_UIDS),
        )

        second.data[const.CONF_ENABLED] = False
        disabled = configuration_module.build_system_runtimes(
            entry, provider, 3
        )
        self.assertEqual(
            set(disabled),
            {TEST_SYSTEM_UIDS[0], TEST_SYSTEM_UIDS[2]},
        )

        second.data[const.CONF_ENABLED] = True
        second.data[const.CONF_SYSTEM_ID] = "test_boiler_2_renamed"
        second.data[const.CONF_CONFIG_REVISION] = 2
        reconfigured = configuration_module.build_system_runtimes(
            entry, provider, 4
        )
        self.assertEqual(
            reconfigured[TEST_SYSTEM_UIDS[1]].system_id,
            "test_boiler_2_renamed",
        )
        self.assertEqual(
            reconfigured[TEST_SYSTEM_UIDS[1]].source_system_id,
            "test_boiler_2",
        )

        del entry.subentries[first.subentry_id]
        removed = configuration_module.build_system_runtimes(
            entry, provider, 5
        )
        self.assertEqual(
            set(removed),
            {TEST_SYSTEM_UIDS[1], TEST_SYSTEM_UIDS[2]},
        )

        second.data[const.CONF_SOURCE_SYSTEM_ID] = "test_boiler_1"
        second.data[const.CONF_CONFIG_REVISION] = 3
        remapped = configuration_module.build_system_runtimes(
            entry, provider, 6
        )
        self.assertEqual(
            remapped[TEST_SYSTEM_UIDS[1]].source_system_id,
            "test_boiler_1",
        )
        self.assertEqual(
            remapped[TEST_SYSTEM_UIDS[1]].system_uid,
            TEST_SYSTEM_UIDS[1],
        )


class RestConfigurationTests(unittest.TestCase):
    def test_generated_default_is_normalized_and_deeply_immutable(self):
        preset = provider_defaults.SOLESTA_WEB_API_DEFAULT
        self.assertEqual(preset["preset_id"], "solesta")
        self.assertEqual(preset["preset_revision"], 3)
        self.assertEqual(len(preset["flows"]["connect_flow"]["steps"]), 1)
        self.assertEqual(
            preset["flows"]["connect_flow"]["steps"][0]["path_template"],
            "/api/auth/login",
        )
        login_assertion = preset["flows"]["connect_flow"]["steps"][0][
            "response"
        ]["assert_equals"]["success"]
        self.assertIs(login_assertion, True)
        with self.assertRaises(TypeError):
            preset["base_url"] = "https://example.invalid"
        with self.assertRaises(TypeError):
            preset["flows"]["connect_flow"]["steps"][0]["method"] = "GET"
        with self.assertRaises(AttributeError):
            preset["flows"]["connect_flow"]["steps"].append({})

    def test_runtime_does_not_revalidate_the_generated_preset(self):
        self.assertFalse(hasattr(web_api, "validate_rest_config"))

    def test_immutable_wildcard_selector_extracts_the_complete_response(self):
        body = {"success": True, "nested": {"temperature": 42}}
        self.assertEqual(
            web_api._extract_response(body, ("*",)),
            {"success": True, "temperature__nested": 42},
        )

    def test_response_assertion_is_type_strict(self):
        web_api._assert_response(
            {"success": True},
            {"success": True},
            flow_name="connect_flow",
        )
        with self.assertRaises(web_api._ResponseAssertionError):
            web_api._assert_response(
                {"success": 1},
                {"success": True},
                flow_name="connect_flow",
            )

    def test_provider_identity_is_independent_from_connection_data(self):
        sources = "\n".join(
            path.read_text()
            for path in INTEGRATION.glob("*.py")
        )
        self.assertNotIn("provider_identity", sources)
        self.assertNotIn("communication_provider_id", sources)
        self.assertNotIn("build_web_api_provider_identity", sources)

    def test_duplicate_response_keys_are_rejected(self):
        with self.assertRaises(exceptions.ProviderResponseError):
            web_api._strict_json_loads(b'{"temp1":1,"temp1":2}')


class RestExecutionTests(unittest.IsolatedAsyncioTestCase):
    def test_http_status_matrix_is_classified_by_exact_error_type(self):
        cases = (
            (401, exceptions.ProviderAuthenticationError),
            (403, exceptions.ProviderAuthenticationError),
            (429, exceptions.ProviderRateLimitError),
            *(
                (status, exceptions.ProviderCommunicationError)
                for status in range(500, 600)
            ),
        )
        for status, expected_error in cases:
            with self.subTest(status=status):
                error = web_api._HttpStatusError("profile_flow", status)
                with self.assertRaises(expected_error) as raised:
                    web_api.WebApiProvider._raise_for_status(error)
                self.assertIs(type(raised.exception), expected_error)

    async def test_html_and_corrupt_json_are_response_errors(self):
        class FakeContent:
            def __init__(self, body):
                self._body = body

            async def read(self, size):
                del size
                body, self._body = self._body, b""
                return body

        class FakeResponse:
            status = 200

            def __init__(self, content_type, body):
                self.headers = {"Content-Type": content_type}
                self.content = FakeContent(body)

        class FakeRequestContext:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self.response

            async def __aexit__(self, exc_type, exc, traceback):
                del exc_type, exc, traceback

        class FakeSession:
            closed = False

            def __init__(self, response):
                self.response = response

            def request(self, **kwargs):
                del kwargs
                return FakeRequestContext(self.response)

        cases = (
            (
                "html",
                FakeResponse("text/html; charset=utf-8", b"<html>error</html>"),
                "invalid content type",
            ),
            (
                "corrupt_json",
                FakeResponse("application/json", b'{"temp1":'),
                "invalid JSON",
            ),
        )
        for name, response, expected_message in cases:
            with self.subTest(case=name):
                executor = web_api.RestFlowExecutor(
                    SimpleNamespace(),
                    base_url=provider_defaults.SOLESTA_WEB_API_DEFAULT[
                        "base_url"
                    ],
                    preset=provider_defaults.SOLESTA_WEB_API_DEFAULT,
                )
                executor._session = FakeSession(response)

                with self.assertRaises(
                    exceptions.ProviderResponseError
                ) as raised:
                    await executor.execute("profile_flow")

                self.assertIn(expected_message, str(raised.exception))

    async def test_assertion_is_evaluated_when_extract_is_empty(self):
        class FakeContent:
            def __init__(self):
                self._body = b'{"success":false}'

            async def read(self, size):
                del size
                body, self._body = self._body, b""
                return body

        class FakeResponse:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __init__(self):
                self.content = FakeContent()

        class FakeRequestContext:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc, traceback):
                del exc_type, exc, traceback

        class FakeSession:
            closed = False

            def request(self, **kwargs):
                del kwargs
                return FakeRequestContext()

        executor = web_api.RestFlowExecutor(
            SimpleNamespace(),
            base_url=provider_defaults.SOLESTA_WEB_API_DEFAULT["base_url"],
            preset=provider_defaults.SOLESTA_WEB_API_DEFAULT,
        )
        executor._session = FakeSession()
        with self.assertRaises(web_api._ResponseAssertionError):
            await executor.execute(
                "connect_flow",
                {"userid": "user", "password": "password"},
            )

    async def test_connect_assertion_maps_to_authentication_error(self):
        class RejectingExecutor:
            async def execute(self, flow_name, bindings):
                del bindings
                raise web_api._ResponseAssertionError(flow_name, "success")

        provider = web_api.WebApiProvider(
            SimpleNamespace(),
            base_url=provider_defaults.SOLESTA_WEB_API_DEFAULT["base_url"],
            connection={"userid": "user", "password": "password"},
            preset=provider_defaults.SOLESTA_WEB_API_DEFAULT,
            provider_id="fixture_provider",
        )
        provider._executor = RejectingExecutor()
        with self.assertRaises(exceptions.ProviderAuthenticationError):
            await provider._execute_connect_locked()


class NumberValidationTests(unittest.TestCase):
    def setUp(self):
        self.description = SimpleNamespace(
            native_min_value=0.00001,
            native_max_value=10,
            native_step=0.00001,
        )

    def test_energy_per_shower_rejects_zero(self):
        with self.assertRaises(number_validation.NumberValidationError):
            number_validation.validate_number_value(0, self.description)

    def test_energy_per_shower_accepts_exact_minimum(self):
        value, literal = number_validation.validate_number_value(
            0.00001,
            self.description,
        )
        self.assertEqual(value, 0.00001)
        self.assertEqual(literal, "1e-05")

    def test_generated_description_contains_exact_minimum(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        for call in (
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ):
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            key = values.get("key")
            if isinstance(key, ast.Constant) and key.value == "energy_shower_kwh":
                minimum = values["native_min_value"]
                self.assertIsInstance(minimum, ast.Constant)
                self.assertEqual(minimum.value, 0.00001)
                break
        else:
            self.fail("energy_shower_kwh description was not generated")

    def test_generated_update_interval_matches_v6(self):
        tree = ast.parse((INTEGRATION / "thetruth.py").read_text())
        for call in (
            node for node in ast.walk(tree) if isinstance(node, ast.Call)
        ):
            values = {keyword.arg: keyword.value for keyword in call.keywords}
            key = values.get("key")
            if isinstance(key, ast.Constant) and key.value == "update_interval":
                self.assertEqual(
                    ast.literal_eval(values["native_min_value"]), 15
                )
                self.assertEqual(
                    ast.literal_eval(values["native_max_value"]), 3600
                )
                self.assertEqual(ast.literal_eval(values["native_step"]), 15)
                self.assertEqual(
                    ast.unparse(values["mode"]), "NumberMode.SLIDER"
                )
                self.assertEqual(
                    ast.literal_eval(values["icon"]),
                    "mdi:timer-sync-outline",
                )
                self.assertEqual(
                    ast.literal_eval(values["default_source_expression"]),
                    "15",
                )
                break
        else:
            self.fail("update_interval description was not generated")

    def test_bool_and_non_finite_values_are_rejected(self):
        for value in (True, float("nan"), float("inf")):
            with self.assertRaises(number_validation.NumberValidationError):
                number_validation.validate_number_value(
                    value,
                    self.description,
                )

    def test_validation_errors_expose_translation_contract(self):
        cases = (
            (0, "number_value_below_minimum", {"value", "minimum"}),
            (11, "number_value_above_maximum", {"value", "maximum"}),
            (0.000015, "number_value_step_mismatch", {"value", "step"}),
        )
        for value, key, placeholders in cases:
            with self.subTest(value=value):
                with self.assertRaises(
                    number_validation.NumberValidationError
                ) as raised:
                    number_validation.validate_number_value(
                        value,
                        self.description,
                    )
                self.assertEqual(raised.exception.translation_key, key)
                self.assertEqual(
                    set(raised.exception.translation_placeholders),
                    placeholders,
                )


if __name__ == "__main__":
    unittest.main()
