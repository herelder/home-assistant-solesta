"""HA-backed release contracts; run separately from the lightweight suite."""

from __future__ import annotations

import asyncio
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from aioesphomeapi import APIClient, BinarySensorState, SensorState

from custom_components import solesta as integration
from custom_components.solesta import config_flow as cf
from custom_components.solesta import configuration as config
from custom_components.solesta import const as c
from custom_components.solesta import mqtt as mqtt_module
from custom_components.solesta.coordinator import SystemCoordinator
from custom_components.solesta.esphome_native import EsphomeNativeProvider
from custom_components.solesta.evaluator import EvaluationContext, evaluate_source_expressions
from custom_components.solesta.exceptions import (
    ProviderAuthenticationError,
    ProviderSystemError,
)
from custom_components.solesta.provider import Provider
from custom_components.solesta.observation import SourceObservation
from custom_components.solesta.runtime_configuration import RuntimeConfiguration
from custom_components.solesta.source_fields import canonical_source_name


SYSTEM_UID = "00000000-0000-4000-8000-000000000001"
HUB_UID = "00000000-0000-4000-8000-000000000002"


class FixtureProvider(Provider):
    """Use the real provider lifecycle with a deterministic remote fixture."""

    def __init__(self, aliases=None):
        super().__init__(provider_id="fixture", duplicate_systems=aliases)

    async def async_open(self):
        pass

    async def async_connect(self):
        pass

    async def async_disconnect(self):
        pass

    async def async_close(self):
        await self.async_cancel_initialization()

    async def _async_fetch_profile(self):
        return {}

    async def _async_fetch_systems(self):
        return ("current_source",)

    async def _async_fetch_system_status(self, source_system_id, source_keys):
        if source_system_id != "current_source":
            raise ProviderSystemError("absent source")
        return {
            "last_update": datetime.now(timezone.utc).isoformat(),
            "temp1": 40,
            "temp2": 40,
            "temp3": 30,
            "temp4": 20,
            "pump": 0,
        }


class SnapshotProvider(FixtureProvider):
    """Keep advertised fields separate from the values in one live response."""

    def __init__(self, available_keys, values):
        super().__init__()
        self.fields = tuple(available_keys)
        self.values = dict(values)

    def available_keys_for(self, source_system_id):
        return self.fields

    async def get_system_snapshot(self, source_system_id, required_keys, referenced_keys):
        now = datetime.now(timezone.utc)
        return SimpleNamespace(values=dict(self.values), last_report=now, last_update=now)


class Entries:
    def __init__(self, entry):
        self.entry = entry
        self.writes = 0
        self.reloads = []

    def async_entries(self, domain):
        return [self.entry]

    def async_get_known_entry(self, entry_id):
        return self.entry

    def async_update_subentry(self, entry, subentry, *, data, title=None):
        subentry.data = data
        self.writes += 1

    def async_update_entry(self, entry, **changes):
        for key, value in changes.items():
            setattr(entry, key, value)
        return True

    def async_schedule_reload(self, entry_id):
        self.reloads.append(entry_id)


def fixture_entry(*, duplicate=False, expressions=None):
    subentry = SimpleNamespace(
        subentry_id="system",
        unique_id=SYSTEM_UID,
        subentry_type=c.SUBENTRY_TYPE_DUPLICATE_SYSTEM
        if duplicate
        else c.SUBENTRY_TYPE_SYSTEM,
        data={
            c.CONF_SYSTEM_ID: "boiler",
            c.CONF_SOURCE_SYSTEM_ID: "local_alias" if duplicate else "current_source",
            c.CONF_ENABLED: False,
            c.CONF_CONFIG_REVISION: 1,
            c.CONF_SOURCE_EXPRESSIONS: expressions
            or config.default_source_expressions(),
            c.CONF_EXPRESSION_SCHEMA_VERSION: c.EXPRESSION_SCHEMA_VERSION,
            c.CONF_VALIDATED_HUB_UID: HUB_UID,
            c.CONF_VALIDATED_PROVIDER_REVISION: 1,
            **(
                {c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: "old_source"}
                if duplicate
                else {}
            ),
        },
    )
    entry = SimpleNamespace(
        entry_id="entry",
        unique_id=HUB_UID,
        version=1,
        minor_version=4,
        data={
            c.CONF_PROTOCOL: c.PROTOCOL_WEB_API,
            c.CONF_PROVIDER_ID: "fixture",
            c.CONF_PROVIDER_REVISION: 1,
            c.CONF_CONFIG_REVISION: 1,
        },
        subentries={"system": subentry},
        update_listeners=[object()],
    )
    entry.get_subentries_of_type = lambda kind: [
        s for s in entry.subentries.values() if s.subentry_type == kind
    ]
    return entry, subentry


class FormContracts(unittest.IsolatedAsyncioTestCase):
    def flow(self, entry, subentry):
        class Flow(cf.SystemSubentryFlowHandler):
            def _get_entry(self):
                return entry

            def _get_reconfigure_subentry(self):
                return subentry

            async def _async_discover_communication_systems(self, entry):
                return ("current_source",)

            def async_show_form(self, **kwargs):
                return kwargs

            def async_abort(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "form"
        flow.hass = SimpleNamespace(data={}, config_entries=Entries(entry))
        return flow

    async def initialize(self, *args, **kwargs):
        provider = FixtureProvider(kwargs.get("duplicate_systems"))
        await provider.async_initialize()
        return provider

    async def test_compile_failures_are_attached_to_the_correct_form_fields(self):
        cases = (
            (
                {"temp_collector": "to_number(", "temp_tank_top": "unknown(1)"},
                {
                    "temp_collector": "source_expression_syntax_error",
                    "temp_tank_top": "source_expression_function_error",
                },
            ),
            (
                {"temp_tank_top": "temp_tank_average"},
                {
                    "temp_tank_top": "source_expression_dependency_cycle",
                    "temp_tank_average": "source_expression_dependency_cycle",
                },
            ),
        )
        for edited, expected in cases:
            with self.subTest(edited=edited):
                entry, subentry = fixture_entry()
                before = deepcopy(subentry.data)
                flow = self.flow(entry, subentry)
                result = await flow.async_step_reconfigure(edited)
                self.assertEqual(result["errors"], expected)
                self.assertEqual(subentry.data, before)
                self.assertEqual(flow.hass.config_entries.writes, 0)

    async def test_live_validation_keeps_source_and_value_errors_at_their_fields(self):
        values = {"temp1": 40, "temp2": 17, "temp3": 15, "pump": 0}
        cases = (
            (
                {
                    "temp_collector": "to_number(absent_collector)",
                    "temp_tank_top": "to_number(absent_tank)",
                },
                values, values,
                {
                    "temp_collector": "source_value_missing_source",
                    "temp_tank_top": "source_value_missing_source",
                },
            ),
            (
                {}, {**values, "temp1__other": 40}, values,
                {"temp_collector": "source_expression_ambiguous_source"},
            ),
            (
                {"temp_collector": "_0ZZ"}, values, values,
                {"temp_collector": "source_expression_invalid_source"},
            ),
            (
                {}, values, {key: value for key, value in values.items() if key != "temp1"},
                {"temp_collector": "source_value_missing_source"},
            ),
            (
                {"energy_shower_kwh": "1 / 0"}, values, values,
                {
                    "energy_shower_kwh": "source_value_division_by_zero",
                    "energy_tank_showers": "source_value_dependency_failed",
                },
            ),
            (
                {"state_pump": "1"}, values, values,
                {"state_pump": "source_value_type_error"},
            ),
            (
                {"update_interval": "0"}, values, values,
                {"update_interval": "source_value_domain_error"},
            ),
        )
        for protocol in (c.PROTOCOL_WEB_API, c.PROTOCOL_ESPHOME_NATIVE, c.PROTOCOL_MQTT):
            for edits, fields, snapshot, expected in cases:
                with self.subTest(protocol=protocol, edits=edits, expected=expected):
                    entry, _subentry = fixture_entry()
                    entry.data[c.CONF_PROTOCOL] = protocol
                    expressions = {**config.default_source_expressions(), **edits}
                    before = dict(expressions)
                    runtime = RuntimeConfiguration.compile(expressions)
                    provider = SnapshotProvider(fields, snapshot)
                    with patch.object(
                        cf, "_async_initialize_provider", AsyncMock(return_value=provider)
                    ):
                        result = await cf._async_live_validate_system(
                            SimpleNamespace(), entry, "current_source", runtime,
                            allow_offline_contract=False,
                        )
                    self.assertFalse(result.valid)
                    self.assertIsNone(result.base_error)
                    for key, error in expected.items():
                        self.assertEqual(result.expression_errors.get(key), error, result)
                    self.assertEqual(expressions, before)

    async def test_authentication_failure_remains_a_general_error(self):
        entry, _subentry = fixture_entry()
        with patch.object(
            cf, "_async_initialize_provider",
            AsyncMock(side_effect=ProviderAuthenticationError("test-secret")),
        ):
            result = await cf._async_live_validate_system(
                SimpleNamespace(), entry, "current_source",
                RuntimeConfiguration.compile(config.default_source_expressions()),
                allow_offline_contract=False,
            )
        self.assertFalse(result.valid)
        self.assertEqual(result.base_error, "invalid_auth")
        self.assertFalse(result.expression_errors)
        self.assertNotIn("test-secret", repr(result))

    async def test_invalid_provider_field_table_is_not_blame_on_an_expression(self):
        entry, _subentry = fixture_entry()
        provider = SnapshotProvider({"_0ZZ"}, {})
        with patch.object(
            cf, "_async_initialize_provider", AsyncMock(return_value=provider)
        ):
            result = await cf._async_live_validate_system(
                SimpleNamespace(), entry, "current_source",
                RuntimeConfiguration.compile(config.default_source_expressions()),
                allow_offline_contract=False,
            )
        self.assertFalse(result.valid)
        self.assertEqual(result.base_error, "invalid_provider_config")
        self.assertFalse(result.expression_errors)

    async def test_duplicate_relink_keeps_identity_alias_and_all_expressions(self):
        entry, subentry = fixture_entry(duplicate=True)
        before = deepcopy(subentry.data[c.CONF_SOURCE_EXPRESSIONS])
        flow = self.flow(entry, subentry)
        form = await flow.async_step_reconfigure()
        fields = {
            marker.schema: value for marker, value in form["data_schema"].schema.items()
        }
        field = c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID
        self.assertNotIn(c.CONF_SOURCE_SYSTEM_ID, fields)
        self.assertEqual(
            [option["value"] for option in fields[field].config["options"]],
            ["current_source"],
        )
        with patch.object(cf, "_async_initialize_provider", self.initialize):
            result = await flow.async_step_reconfigure(
                {field: "current_source", c.CONF_ENABLED: True}
            )
        self.assertEqual(result, {"reason": "reconfigure_successful"})
        self.assertEqual(subentry.unique_id, SYSTEM_UID)
        self.assertEqual(subentry.data[c.CONF_SOURCE_SYSTEM_ID], "local_alias")
        self.assertEqual(subentry.data[field], "current_source")
        self.assertEqual(subentry.data[c.CONF_SOURCE_EXPRESSIONS], before)
        self.assertTrue(subentry.data[c.CONF_ENABLED])

    async def test_regular_choices_never_offer_the_unavailable_old_source(self):
        entry, subentry = fixture_entry()
        subentry.data[c.CONF_SOURCE_SYSTEM_ID] = "old_source"
        flow = self.flow(entry, subentry)
        form = await flow.async_step_reconfigure()
        fields = {
            marker.schema: value for marker, value in form["data_schema"].schema.items()
        }
        self.assertEqual(
            [
                option["value"]
                for option in fields[c.CONF_SOURCE_SYSTEM_ID].config["options"]
            ],
            ["current_source"],
        )
        result = await flow.async_step_reconfigure({c.CONF_ENABLED: True})
        self.assertEqual(
            result["errors"][c.CONF_SOURCE_SYSTEM_ID], "invalid_source_system"
        )
        self.assertEqual(flow.hass.config_entries.writes, 0)

    async def test_submitting_an_unchanged_expression_preserves_its_whitespace(self):
        expressions = config.default_source_expressions()
        expressions["temp_collector"] = "to_number(temp1)  "
        before = deepcopy(expressions)
        entry, subentry = fixture_entry(expressions=expressions)
        flow = self.flow(entry, subentry)
        await flow.async_step_reconfigure()
        with patch.object(cf, "_async_initialize_provider", self.initialize):
            result = await flow.async_step_reconfigure(
                {c.CONF_ENABLED: True, "temp_collector": expressions["temp_collector"]}
            )
        self.assertEqual(result, {"reason": "reconfigure_successful"})
        self.assertEqual(subentry.data[c.CONF_SOURCE_EXPRESSIONS], before)

    async def test_expression_only_change_is_bound_to_provider_source_fields(self):
        entry, subentry = fixture_entry()
        subentry.data[c.CONF_ENABLED] = True
        before = deepcopy(subentry.data)
        flow = self.flow(entry, subentry)
        await flow.async_step_reconfigure()

        with patch.object(cf, "_async_initialize_provider", self.initialize):
            result = await flow.async_step_reconfigure(
                {"temp_collector": "to_number(not_a_provider_field)"}
            )

        self.assertEqual(
            result["errors"]["temp_collector"], "source_value_missing_source"
        )
        self.assertNotIn("base", result["errors"])
        self.assertEqual(subentry.data, before)
        self.assertEqual(flow.hass.config_entries.writes, 0)

    async def test_expression_only_change_stores_bound_required_source_fields(self):
        entry, subentry = fixture_entry()
        subentry.data[c.CONF_ENABLED] = True
        flow = self.flow(entry, subentry)
        await flow.async_step_reconfigure()

        with patch.object(cf, "_async_initialize_provider", self.initialize):
            result = await flow.async_step_reconfigure(
                {"temp_reserved": "to_number(temp4)"}
            )

        self.assertEqual(result, {"reason": "reconfigure_successful"})
        self.assertIn("temp4", subentry.data[c.CONF_REQUIRED_SOURCE_KEYS])
        self.assertEqual(flow.hass.config_entries.writes, 1)

    async def test_first_system_reconfigure_after_switch_to_mqtt_uses_root_as_source(self):
        entry, subentry = fixture_entry()
        entry.data.update(
            {
                c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
                c.CONF_CONNECTION: {
                    c.CONF_HOST: "broker.example",
                    c.CONF_PORT: 1883,
                    c.CONF_TLS: False,
                    c.CONF_KEEPALIVE: 60,
                    c.CONF_QOS: 0,
                },
            }
        )
        flow = self.flow(entry, subentry)
        form = await flow.async_step_reconfigure()
        source_marker = next(
            marker
            for marker in form["data_schema"].schema
            if marker.schema == c.CONF_SOURCE_SYSTEM_ID
        )
        self.assertEqual(source_marker.default(), "current_source")

        async def validate(
            _hass,
            _entry,
            selected_source_system_id,
            _runtime,
            **kwargs,
        ):
            self.assertEqual(selected_source_system_id, "house/boiler")
            self.assertNotIn("mqtt_root", kwargs)
            return cf._LiveValidationResult(
                True,
                available_source_keys=("state",),
                required_source_keys=("state",),
            )

        with patch.object(cf, "_async_live_validate_system", validate):
            result = await flow.async_step_reconfigure(
                {
                    c.CONF_SOURCE_SYSTEM_ID: "house/boiler",
                    c.CONF_ENABLED: True,
                }
            )

        self.assertEqual(result, {"reason": "reconfigure_successful"})
        self.assertEqual(
            subentry.data[c.CONF_SOURCE_SYSTEM_ID], "house/boiler"
        )
        self.assertEqual(subentry.data[c.CONF_AVAILABLE_KEYS], ["state"])
        self.assertTrue(subentry.data[c.CONF_ENABLED])

    async def test_user_drop_is_visible_rejected_and_can_be_corrected(self):
        expressions = config.default_source_expressions()
        expressions["temp_reserved"] = "drop()"
        RuntimeConfiguration.compile(expressions)
        entry, subentry = fixture_entry(expressions=expressions)
        flow = self.flow(entry, subentry)
        form = await flow.async_step_reconfigure()
        visible = {marker.schema for marker in form["data_schema"].schema}
        self.assertIn("temp_reserved", visible)
        self.assertNotIn("archive_status", visible)
        failed = await flow.async_step_reconfigure({c.CONF_ENABLED: True})
        self.assertEqual(
            failed["errors"]["temp_reserved"], "source_expression_drop_not_allowed"
        )
        self.assertEqual(
            subentry.data[c.CONF_SOURCE_EXPRESSIONS]["temp_reserved"], "drop()"
        )
        self.assertEqual(flow.hass.config_entries.writes, 0)
        with patch.object(cf, "_async_initialize_provider", self.initialize):
            result = await flow.async_step_reconfigure(
                {c.CONF_ENABLED: True, "temp_reserved": ""}
            )
        self.assertEqual(result, {"reason": "reconfigure_successful"})
        self.assertEqual(
            subentry.data[c.CONF_SOURCE_EXPRESSIONS]["temp_reserved"],
            "null()",
        )
        self.assertEqual(
            subentry.data[c.CONF_SOURCE_EXPRESSIONS]["archive_status"], "drop()"
        )

    async def test_overlapping_creation_claims_the_id_atomically(self):
        for mixed, defer_save in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            with self.subTest(mixed=mixed, defer_save=defer_save):
                entries = []
                hass = SimpleNamespace(
                    data={},
                    config_entries=SimpleNamespace(
                        async_entries=lambda domain: entries
                    ),
                )
                ready = asyncio.Event()
                arrived = 0

                async def validate(hass, candidate):
                    nonlocal arrived
                    arrived += 1
                    if arrived == 2:
                        ready.set()
                    await ready.wait()
                    return candidate

                class Flow(cf.ConfigFlowHandler):
                    def async_create_entry(self, *, title, data):
                        new_entry = cf.ConfigEntry(
                            version=1,
                            minor_version=4,
                            domain=c.DOMAIN,
                            title=title,
                            data=data,
                            source="user",
                            options={},
                            unique_id=self._hub_uid,
                            discovery_keys={},
                            subentries_data=[],
                        )
                        if not defer_save:
                            entries.append(new_entry)
                        return {"created": True}

                    def async_show_form(self, **kwargs):
                        return kwargs

                flows = [Flow(), Flow()]
                for index, flow in enumerate(flows):
                    flow.hass = hass
                    flow.flow_id = f"flow-{index}"
                    flow._hub_uid = f"fixture-{index}"
                with patch.object(cf, "_async_validate_hub_candidate", validate):
                    result = await asyncio.wait_for(
                        asyncio.gather(
                            flows[0].async_step_web_api(
                                {
                                    c.CONF_PROVIDER_ID: "same",
                                    c.CONF_USER_ID: "fixture",
                                    c.CONF_PASSWORD: "fixture",
                                }
                            ),
                            (
                                flows[1].async_step_esphome_native(
                                    {
                                        c.CONF_PROVIDER_ID: "same",
                                        c.CONF_HOST: "fixture.local",
                                        c.CONF_PORT: 6053,
                                        c.CONF_NOISE_PSK: base64.b64encode(
                                            b"x" * 32
                                        ).decode(),
                                    }
                                )
                                if mixed
                                else flows[1].async_step_web_api(
                                    {
                                        c.CONF_PROVIDER_ID: "same",
                                        c.CONF_USER_ID: "fixture",
                                        c.CONF_PASSWORD: "fixture",
                                    }
                                )
                            ),
                        ),
                        timeout=5,
                    )
                self.assertEqual(len(entries), 0 if defer_save else 1)
                self.assertEqual(sum(item.get("created", False) for item in result), 1)
                failed = next(item for item in result if "errors" in item)
                self.assertEqual(
                    failed["errors"][c.CONF_PROVIDER_ID], "provider_id_exists"
                )
                for flow in flows:
                    flow.async_remove()
                self.assertFalse(cf._claims(hass).provider_ids)

    async def test_switch_with_stale_duplicate_does_not_block_valid_systems(self):
        entry, duplicate = fixture_entry(duplicate=True)
        entries = Entries(entry)
        hass = SimpleNamespace(config_entries=entries)
        cf._publish_provider_candidate(
            hass,
            entry,
            {**entry.data, c.CONF_PROTOCOL: c.PROTOCOL_ESPHOME_NATIVE},
            protocol_changed=True,
        )
        self.assertFalse(duplicate.data[c.CONF_ENABLED])
        provider = FixtureProvider({"local_alias": "old_source"})
        await provider.async_initialize()
        self.assertEqual(provider.systems, ("current_source",))
        self.assertEqual(
            (await provider.get_system_snapshot("current_source", (), ()))["temp1"], 40
        )
        with self.assertRaises(ProviderSystemError):
            await provider.get_system_snapshot("local_alias", (), ())

    async def test_malformed_or_stale_sibling_cannot_prevent_a_valid_system_runtime(
        self,
    ):
        for target in (None, "local_alias", "old_source"):
            with self.subTest(target=target):
                entry, regular = fixture_entry()
                regular.data[c.CONF_ENABLED] = True
                _, duplicate = fixture_entry(duplicate=True)
                duplicate.subentry_id = "duplicate"
                duplicate.unique_id = "00000000-0000-4000-8000-000000000003"
                duplicate.data[c.CONF_ENABLED] = True
                duplicate.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = target
                entry.subentries["duplicate"] = duplicate
                aliases = config.duplicate_systems_from_entry(entry)
                provider = FixtureProvider(aliases)
                await provider.async_initialize()
                with self.assertLogs(config._LOGGER, level="ERROR"):
                    systems = config.build_system_runtimes(entry, provider, 1)
                self.assertEqual(set(systems), {SYSTEM_UID})
                self.assertEqual(
                    (await systems[SYSTEM_UID].system.status((), ()))["temp1"], 40
                )

    async def test_schema_upgrade_preserves_every_old_expression_and_is_idempotent(self):
        entry, subentry = fixture_entry()
        entry.minor_version = 1
        entry.data[c.CONF_PROTOCOL] = c.PROTOCOL_WEB_API
        subentry.data[c.CONF_EXPRESSION_SCHEMA_VERSION] = 4
        stored = json.loads((Path(__file__).parent / "fixtures" /
                             "solesta_023_source_expressions.json").read_text())
        subentry.data[c.CONF_SOURCE_EXPRESSIONS] = stored
        before = deepcopy(subentry.data)
        entries = Entries(entry)
        hass = SimpleNamespace(config_entries=entries)
        self.assertTrue(await integration.async_migrate_entry(hass, entry))
        self.assertEqual(entry.minor_version, 9)
        self.assertEqual(subentry.data[c.CONF_EXPRESSION_SCHEMA_VERSION], 11)
        self.assertEqual(subentry.unique_id, SYSTEM_UID)
        self.assertEqual(subentry.data[c.CONF_SOURCE_EXPRESSIONS], stored)
        self.assertEqual(subentry.data[c.CONF_SOURCE_EXPRESSIONS]["last_report"], "last_update")
        for key in (c.CONF_SYSTEM_ID, c.CONF_SOURCE_SYSTEM_ID):
            self.assertEqual(subentry.data[key], before[key])
        saved = deepcopy(subentry.data)
        self.assertTrue(await integration.async_migrate_entry(hass, entry))
        self.assertEqual(subentry.data, saved)
        self.assertEqual(entries.writes, 1)

    async def test_unreleased_mqtt_and_native_source_ids_are_not_rewritten(self):
        for protocol, source_id in ((c.PROTOCOL_MQTT, "legacy-local-uuid"),
                                    (c.PROTOCOL_ESPHOME_NATIVE, "aa:bb:cc:dd:ee:ff/uart1")):
            with self.subTest(protocol=protocol):
                entry, regular = fixture_entry()
                entry.minor_version = 8
                entry.data[c.CONF_PROTOCOL] = protocol
                regular.data[c.CONF_SOURCE_SYSTEM_ID] = source_id
                regular.data["mqtt_root_topic"] = "house/boiler"
                before = deepcopy(regular.data)
                entries = Entries(entry)
                with self.assertLogs(integration._LOGGER, level="ERROR"):
                    self.assertFalse(await integration.async_migrate_entry(
                        SimpleNamespace(config_entries=entries), entry))
                self.assertEqual(regular.data, before)
                self.assertEqual(entry.minor_version, 8)
                self.assertEqual(entries.writes, 0)

    async def test_colliding_bad_alias_cannot_disable_a_valid_duplicate(self):
        entry, regular = fixture_entry()
        regular.data[c.CONF_ENABLED] = True
        _, duplicate = fixture_entry(duplicate=True)
        duplicate.subentry_id = "valid_duplicate"
        duplicate.unique_id = "00000000-0000-4000-8000-000000000003"
        duplicate.data[c.CONF_ENABLED] = True
        duplicate.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = "current_source"
        bad = deepcopy(duplicate)
        bad.subentry_id = "bad_duplicate"
        bad.unique_id = "00000000-0000-4000-8000-000000000004"
        bad.data[c.CONF_SOURCE_SYSTEM_ID] = "current_source"
        bad.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = "obsolete"
        entry.subentries.update(valid_duplicate=duplicate, bad_duplicate=bad)
        provider = FixtureProvider(config.duplicate_systems_from_entry(entry))
        await provider.async_initialize()
        with self.assertLogs(config._LOGGER, level="ERROR"):
            systems = config.build_system_runtimes(entry, provider, 1)
        self.assertEqual(set(systems), {SYSTEM_UID, duplicate.unique_id})
        self.assertEqual(
            (await systems[duplicate.unique_id].system.status((), ()))["temp1"], 40
        )

    async def test_bad_expression_does_not_block_a_sibling_during_schema_upgrade(self):
        entry, regular = fixture_entry()
        entry.minor_version = 1
        entry.data[c.CONF_PROTOCOL] = c.PROTOCOL_WEB_API
        regular.data[c.CONF_EXPRESSION_SCHEMA_VERSION] = 4
        bad = deepcopy(regular)
        bad.subentry_id = "bad"
        bad.unique_id = "00000000-0000-4000-8000-000000000003"
        bad.data[c.CONF_SOURCE_EXPRESSIONS]["temp_collector"] = "to_number("
        entry.subentries["bad"] = bad
        before = deepcopy(bad.data[c.CONF_SOURCE_EXPRESSIONS])
        with self.assertLogs(integration._LOGGER, level="ERROR"):
            self.assertTrue(await integration.async_migrate_entry(
                SimpleNamespace(config_entries=Entries(entry)), entry))
        self.assertEqual(bad.data[c.CONF_SOURCE_EXPRESSIONS], before)
        self.assertEqual(entry.minor_version, 9)

    async def test_a_failed_creation_releases_the_provider_id_claim(self):
        hass = SimpleNamespace(
            data={}, config_entries=SimpleNamespace(async_entries=lambda domain: [])
        )

        class Flow(cf.ConfigFlowHandler):
            def async_create_entry(self, **kwargs):
                raise RuntimeError("storage fixture failure")

        flow = Flow()
        flow.hass = hass
        flow.flow_id = "failed-flow"
        flow._hub_uid = HUB_UID

        async def validate(hass, candidate):
            return candidate

        with patch.object(cf, "_async_validate_hub_candidate", validate):
            with self.assertRaisesRegex(RuntimeError, "storage fixture failure"):
                await flow.async_step_web_api(
                    {
                        c.CONF_PROVIDER_ID: "fixture",
                        c.CONF_USER_ID: "fixture",
                        c.CONF_PASSWORD: "fixture",
                    }
                )
        self.assertFalse(cf._claims(hass).provider_ids)


class MqttFlowContracts(unittest.IsolatedAsyncioTestCase):
    async def system_creation_flow(self, protocol, *, duplicate):
        entry, _existing = fixture_entry()
        entry.data[c.CONF_PROTOCOL] = protocol
        if not duplicate:
            entry.subentries.clear()
        handler = (
            cf.DuplicateSystemSubentryFlowHandler
            if duplicate else cf.SystemSubentryFlowHandler
        )

        class Flow(handler):
            def _get_entry(self):
                return entry

            def _get_reconfigure_subentry(self):
                return self.saved_subentry

            async def _async_discover_systems(self, entry):
                return ("current_source",)

            async def _async_discover_communication_systems(self, entry):
                return ("current_source",)

            def async_show_form(self, **kwargs):
                return kwargs

            def async_create_entry(self, **kwargs):
                return kwargs

            def async_abort(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "system-creation"
        flow.hass = SimpleNamespace(data={}, config_entries=Entries(entry))
        self.addCleanup(flow.async_remove)
        selection = {c.CONF_SOURCE_SYSTEM_ID: "current_source"}
        if duplicate:
            selection = {
                c.CONF_SOURCE_SYSTEM_ID: "local_copy",
                c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: "current_source",
            }
        form = await flow.async_step_user(selection)
        self.assertEqual(form["step_id"], "details")
        return entry, flow

    async def test_unvalidated_push_system_and_copy_can_be_created_disabled(self):
        failures = (
            cf._LiveValidationResult(False, "cannot_validate_offline"),
            cf._LiveValidationResult(False, "invalid_source_values"),
            cf._LiveValidationResult(
                False,
                expression_errors={
                    "temp_collector": "source_value_missing_source",
                },
            ),
        )
        for protocol in (c.PROTOCOL_MQTT, c.PROTOCOL_ESPHOME_NATIVE):
            for duplicate in (False, True):
                for failure in failures:
                    with self.subTest(
                        protocol=protocol, duplicate=duplicate, failure=failure
                    ):
                        entry, flow = await self.system_creation_flow(
                            protocol, duplicate=duplicate
                        )
                        expression = "to_number(not_published_yet)"
                        validate = AsyncMock(return_value=failure)
                        with patch.object(cf, "_async_live_validate_system", validate):
                            result = await flow.async_step_details({
                                c.CONF_SYSTEM_ID: "new_boiler",
                                "temp_collector": expression,
                            })
                        self.assertIn("data", result, result)
                        data = result["data"]
                        self.assertFalse(data[c.CONF_ENABLED])
                        self.assertIsNone(data[c.CONF_VALIDATED_HUB_UID])
                        self.assertIsNone(data[c.CONF_VALIDATED_PROVIDER_REVISION])
                        self.assertEqual(
                            data[c.CONF_SOURCE_EXPRESSIONS]["temp_collector"],
                            expression,
                        )
                        self.assertEqual(
                            data[c.CONF_SOURCE_SYSTEM_ID],
                            "local_copy" if duplicate else "current_source",
                        )
                        if duplicate:
                            self.assertEqual(
                                data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID],
                                "current_source",
                            )
                        validate.assert_awaited_once()
                        self.assertEqual(validate.await_args.args[2], "current_source")
                        if protocol == c.PROTOCOL_MQTT:
                            self.assertEqual(data[c.CONF_AVAILABLE_KEYS], [])
                        self.assertEqual(flow.hass.config_entries.writes, 0)

    async def test_unvalidated_mqtt_system_and_copy_still_require_valid_activation(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                entry, flow = await self.system_creation_flow(
                    c.PROTOCOL_MQTT, duplicate=duplicate
                )
                failure = cf._LiveValidationResult(
                    False,
                    expression_errors={"temp_collector": "source_value_missing_source"},
                )
                validate = AsyncMock(return_value=failure)
                with patch.object(cf, "_async_live_validate_system", validate):
                    created = await flow.async_step_details({
                        c.CONF_SYSTEM_ID: "new_boiler",
                        "temp_collector": "to_number(not_published_yet)",
                    })
                    self.assertIn("data", created, created)
                    # Simulate HA committing the newly created disabled subentry.
                    flow.async_remove()
                    saved = SimpleNamespace(
                        subentry_id="created",
                        unique_id=created["unique_id"],
                        subentry_type=(
                            c.SUBENTRY_TYPE_DUPLICATE_SYSTEM
                            if duplicate else c.SUBENTRY_TYPE_SYSTEM
                        ),
                        data=created["data"],
                    )
                    entry.subentries[saved.subentry_id] = saved
                    flow.saved_subentry = saved
                    before = deepcopy(saved.data)
                    result = await flow.async_step_reconfigure({c.CONF_ENABLED: True})
                self.assertEqual(result["step_id"], "reconfigure")
                self.assertEqual(
                    result["errors"]["temp_collector"], "source_value_missing_source"
                )
                self.assertEqual(saved.data, before)
                self.assertEqual(flow.hass.config_entries.writes, 0)

                validate.return_value = cf._LiveValidationResult(True)
                with patch.object(cf, "_async_live_validate_system", validate):
                    result = await flow.async_step_reconfigure({c.CONF_ENABLED: True})
                self.assertEqual(result, {"reason": "reconfigure_successful"})
                self.assertTrue(saved.data[c.CONF_ENABLED])
                self.assertEqual(saved.data[c.CONF_VALIDATED_HUB_UID], HUB_UID)
                self.assertEqual(saved.data[c.CONF_VALIDATED_PROVIDER_REVISION], 1)

    async def test_disabled_mqtt_system_and_copy_still_reject_invalid_syntax(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                _entry, flow = await self.system_creation_flow(
                    c.PROTOCOL_MQTT, duplicate=duplicate
                )
                validate = AsyncMock()
                with patch.object(cf, "_async_live_validate_system", validate):
                    result = await flow.async_step_details({
                        c.CONF_SYSTEM_ID: "new_boiler",
                        "temp_collector": "to_number(",
                    })
                self.assertEqual(result["step_id"], "details")
                self.assertEqual(
                    result["errors"]["temp_collector"], "source_expression_syntax_error"
                )
                validate.assert_not_awaited()

    @staticmethod
    def hub_flow(hass):
        class Flow(cf.ConfigFlowHandler):
            def async_show_form(self, **kwargs):
                return kwargs

            def async_create_entry(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "mqtt-hub-flow"
        flow.hass = hass
        flow._hub_uid = HUB_UID
        return flow

    async def test_runtime_client_creation_uses_preloaded_dependency(self):
        self.assertIs(integration.MqttProvider, mqtt_module.MqttProvider)
        self.assertIs(cf.MqttProvider, mqtt_module.MqttProvider)
        provider = mqtt_module.MqttProvider(
            connection={c.CONF_HOST: "broker.example", c.CONF_PORT: 1883},
            provider_id="preloaded-dependency",
            source_system_ids=("root",),
        )
        self.addAsyncCleanup(provider.async_close)

        def factory(**kwargs):
            return SimpleNamespace(kwargs=kwargs)

        with (
            patch.object(mqtt_module, "_AIOMQTT_CLIENT", factory),
            patch.object(
                mqtt_module,
                "_AIOMQTT_PROTOCOL_VERSION",
                SimpleNamespace(V311=4),
            ),
            patch("builtins.__import__", wraps=__import__) as import_mock,
        ):
            client = provider._new_client()

        self.assertEqual(client.kwargs["protocol"], 4)
        self.assertNotIn(
            "aiomqtt",
            [call.args[0] for call in import_mock.call_args_list],
        )

    async def test_broker_candidate_is_validated_before_save_and_keeps_options(self):
        hass = SimpleNamespace(
            data={},
            config_entries=SimpleNamespace(async_entries=lambda domain: []),
        )
        flow = self.hub_flow(hass)
        seen = []

        async def validate(_hass, candidate):
            seen.append(deepcopy(candidate))
            return candidate

        user_input = {
            c.CONF_PROVIDER_ID: "mqtt-lab",
            c.CONF_HOST: "Broker.Example.",
            c.CONF_PORT: 28883,
            c.CONF_TLS: True,
            c.CONF_USERNAME: "test-user",
            c.CONF_PASSWORD: "test-secret",
            c.CONF_KEEPALIVE: 37,
            c.CONF_QOS: 2,
        }
        with patch.object(cf, "_async_validate_hub_candidate", validate):
            result = await flow.async_step_mqtt(user_input)

        self.assertEqual(len(seen), 1)
        self.assertEqual(result["data"], seen[0])
        connection = result["data"][c.CONF_CONNECTION]
        self.assertEqual(connection[c.CONF_HOST], "broker.example")
        self.assertEqual(connection[c.CONF_PORT], 28883)
        self.assertTrue(connection[c.CONF_TLS])
        self.assertEqual(connection[c.CONF_KEEPALIVE], 37)
        self.assertEqual(connection[c.CONF_QOS], 2)
        self.assertEqual(connection[c.CONF_USERNAME], "test-user")
        self.assertEqual(connection[c.CONF_PASSWORD], "test-secret")
        flow.async_remove()

    async def test_auth_rejection_saves_nothing_and_does_not_echo_secret(self):
        hass = SimpleNamespace(
            data={},
            config_entries=SimpleNamespace(async_entries=lambda domain: []),
        )
        flow = self.hub_flow(hass)

        async def reject(_hass, candidate):
            del candidate
            raise ProviderAuthenticationError(
                "not authorized: must-not-leak"
            )

        with patch.object(cf, "_async_validate_hub_candidate", reject):
            result = await flow.async_step_mqtt(
                {
                    c.CONF_PROVIDER_ID: "mqtt-lab",
                    c.CONF_HOST: "broker.example",
                    c.CONF_PORT: 1883,
                    c.CONF_TLS: False,
                    c.CONF_USERNAME: "test-user",
                    c.CONF_PASSWORD: "must-not-leak",
                    c.CONF_KEEPALIVE: 60,
                    c.CONF_QOS: 1,
                }
            )

        self.assertEqual(result["errors"]["base"], "invalid_auth")
        self.assertNotIn("data", result)
        self.assertNotIn("must-not-leak", repr(result))
        self.assertFalse(cf._claims(hass).provider_ids)

    async def test_user_password_reauth_preserves_hub_system_and_expressions(self):
        entry, subentry = fixture_entry()
        before_expressions = deepcopy(
            subentry.data[c.CONF_SOURCE_EXPRESSIONS]
        )
        entry.data.update(
            {
                c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
                c.CONF_CONNECTION: {
                    c.CONF_HOST: "broker.example",
                    c.CONF_PORT: 1883,
                    c.CONF_TLS: False,
                    c.CONF_USERNAME: "test-user",
                    c.CONF_PASSWORD: "old-secret",
                    c.CONF_KEEPALIVE: 60,
                    c.CONF_QOS: 1,
                },
            }
        )
        entries = Entries(entry)
        hass = SimpleNamespace(data={}, config_entries=entries)

        class Flow(cf.ConfigFlowHandler):
            def _get_reauth_entry(self):
                return entry

            def async_show_form(self, **kwargs):
                return kwargs

            def async_abort(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "mqtt-reauth-flow"
        flow.hass = hass
        flow._base_config_revision = entry.data[c.CONF_CONFIG_REVISION]
        flow._base_system_contract = cf._system_contract_snapshot(entry)

        async def validate(_hass, candidate, *, linked_entry):
            self.assertIs(linked_entry, entry)
            return candidate

        with (
            patch.object(cf, "_async_validate_hub_candidate", validate),
            patch.object(
                cf,
                "_entry_provider_id",
                return_value=entry.data[c.CONF_PROVIDER_ID],
            ),
        ):
            result = await flow.async_step_reauth_confirm(
                {c.CONF_PASSWORD: "new-secret"}
            )

        self.assertEqual(result, {"reason": "reauth_successful"})
        self.assertEqual(entry.unique_id, HUB_UID)
        self.assertEqual(subentry.unique_id, SYSTEM_UID)
        self.assertEqual(
            subentry.data[c.CONF_SOURCE_EXPRESSIONS], before_expressions
        )
        self.assertEqual(
            entry.data[c.CONF_CONNECTION][c.CONF_PASSWORD], "new-secret"
        )
        self.assertNotIn("old-secret", repr(result))
        self.assertNotIn("new-secret", repr(result))

    async def test_manual_root_is_the_source_identity_after_live_validation(self):
        entry, _existing = fixture_entry()
        entry.data.update(
            {
                c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
                c.CONF_CONNECTION: {
                    c.CONF_HOST: "broker.example",
                    c.CONF_PORT: 1883,
                    c.CONF_TLS: False,
                    c.CONF_KEEPALIVE: 60,
                    c.CONF_QOS: 1,
                },
            }
        )
        entries = Entries(entry)
        hass = SimpleNamespace(data={}, config_entries=entries)

        class Flow(cf.SystemSubentryFlowHandler):
            def _get_entry(self):
                return entry

            def async_show_form(self, **kwargs):
                return kwargs

            def async_create_entry(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "mqtt-system-flow"
        flow.hass = hass

        details_form = await flow.async_step_mqtt_source(
            {c.CONF_SOURCE_SYSTEM_ID: " house/boiler "}
        )
        self.assertEqual(details_form["step_id"], "details")
        local_source_id = flow._selected_source_system_id
        self.assertIsNotNone(local_source_id)
        self.assertEqual(local_source_id, " house/boiler ")

        validations = []

        async def live_validate(
            _hass,
            _entry,
            source_system_id,
            runtime,
            **kwargs,
        ):
            validations.append(
                (source_system_id, dict(runtime.source_expressions), kwargs)
            )
            return cf._LiveValidationResult(
                True,
                available_source_keys=("required", "optional"),
                required_source_keys=("required",),
            )

        with patch.object(cf, "_async_live_validate_system", live_validate):
            result = await flow.async_step_details(
                {c.CONF_SYSTEM_ID: "mqtt_boiler"}
            )

        self.assertEqual(len(validations), 1)
        self.assertEqual(validations[0][0], local_source_id)
        self.assertNotIn("mqtt_root", validations[0][2])
        self.assertEqual(result["data"][c.CONF_SOURCE_SYSTEM_ID], local_source_id)
        self.assertNotIn("mqtt_root_topic", result["data"])
        self.assertEqual(
            result["data"][c.CONF_AVAILABLE_KEYS],
            ["required", "optional"],
        )
        self.assertFalse(result["data"][c.CONF_ENABLED])
        flow.async_remove()

    async def test_nullable_short_missing_key_does_not_block_mqtt_live_validation(self):
        entry, _subentry = fixture_entry()
        entry.data.update(
            {
                c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
                c.CONF_CONNECTION: {
                    c.CONF_HOST: "broker.example",
                    c.CONF_PORT: 1883,
                    c.CONF_TLS: False,
                    c.CONF_KEEPALIVE: 60,
                    c.CONF_QOS: 1,
                },
            }
        )
        expressions = config.default_source_expressions()
        for key, expression in tuple(expressions.items()):
            if expression not in {"True", "False", "drop()"}:
                expressions[key] = "null()"
        expressions["temp_collector"] = "to_number(required)"
        expressions["temp_reserved"] = "null(missing)"
        runtime = RuntimeConfiguration.compile(expressions)

        class LiveProvider:
            closed = False

            @staticmethod
            async def async_get_available_keys(source_system_id, required_source_names):
                del source_system_id, required_source_names
                return ("required",)

            @staticmethod
            def available_keys_for(source_system_id):
                del source_system_id
                return ("required",)

            @staticmethod
            async def get_system_snapshot(
                source_system_id, required_keys, referenced_keys
            ):
                del source_system_id, required_keys, referenced_keys
                now = datetime.now(timezone.utc)
                return SimpleNamespace(
                    values={"required": "42"},
                    last_report=now,
                    last_update=now,
                )

            @staticmethod
            async def async_cancel_initialization():
                return None

            @staticmethod
            async def async_disconnect():
                return None

            async def async_close(self):
                self.closed = True

        provider = LiveProvider()
        calls = []

        async def initialize(_hass, data, **kwargs):
            calls.append((data, kwargs))
            return provider

        with patch.object(cf, "_async_initialize_provider", initialize):
            result = await cf._async_live_validate_system(
                SimpleNamespace(),
                entry,
                "house/boiler",
                runtime,
                allow_offline_contract=False,
            )

        self.assertTrue(result.valid, result)
        self.assertEqual(result.required_source_keys, ("required",))
        self.assertIn(
            "house/boiler", calls[0][1]["mqtt_source_system_ids"]
        )
        self.assertTrue(provider.closed)


class NativeModelContracts(unittest.IsolatedAsyncioTestCase):
    async def test_minimum_client_supports_used_constructor_contract(self):
        client = APIClient(
            "fixture.local",
            6053,
            noise_psk=base64.b64encode(b"x" * 32).decode(),
            expected_mac="aabbccddeeff",
            zeroconf_instance=None,
            client_info="Solesta test",
            provide_time=False,
        )
        self.assertIsNotNone(client)

    async def test_native_states_are_opaque_independent_events(self):
        provider = EsphomeNativeProvider(
            connection={
                "host": "fixture.local",
                "port": 6053,
                "noise_psk": base64.b64encode(b"x" * 32).decode(),
            },
            provider_id="fixture",
        )
        keys = (
            "temperature_1_raw",
            "temperature_2_raw",
            "temperature_3_raw",
            "temperature_4_raw",
            "pump_raw",
            "data_valid",
            "data_age",
            "frame_sequence",
        )
        info = SimpleNamespace(mac_address="aa:bb:cc:dd:ee:ff")
        provider._publish_discovery(
            info,
            [
                SimpleNamespace(object_id=key, key=index, device_id=0)
                for index, key in enumerate(keys, 1)
            ],
            info.mac_address,
        )
        source_id = "aa:bb:cc:dd:ee:ff"
        provider._async_on_state(
            SensorState(key=1, state=0, missing_state=True)
        )
        provider._async_on_state(
            SensorState(key=2, state=float("nan"))
        )
        provider._async_on_state(BinarySensorState(key=6, state=False))
        provider._async_on_state(SensorState(key=7, state=600))
        provider._async_on_state(
            SensorState(key=8, state=0, missing_state=True)
        )

        snapshot = provider._observation(source_id).snapshot(keys)
        self.assertIsNone(snapshot.values["temperature_1_raw"])
        self.assertTrue(math.isnan(snapshot.values["temperature_2_raw"]))
        self.assertFalse(snapshot.values["data_valid"])
        self.assertEqual(snapshot.values["data_age"], 600)
        self.assertIsNone(snapshot.values["frame_sequence"])
        self.assertNotIn("last_update", snapshot.values)
        self.assertIsNotNone(snapshot.last_report)
        self.assertIsNotNone(snapshot.last_update)


class MqttReviewContracts(unittest.IsolatedAsyncioTestCase):
    def mqtt(self, roots=("root",)):
        class Local(mqtt_module.MqttProvider):
            async def async_open(self):
                pass

            async def async_connect(self):
                pass

        provider = Local(connection={"host": "broker.example", "port": 1883},
                         provider_id="fixture", source_system_ids=roots)
        self.addAsyncCleanup(provider.async_close)
        return provider

    @staticmethod
    def emit(provider, topic, value):
        provider._handle_message(SimpleNamespace(topic=topic, payload=str(value).encode()))

    async def validate_stream(self, events, *, roots=("root",), timeout=0.7, hub=False):
        provider = self.mqtt(roots)
        if roots[0] != "root":
            self.emit(provider, roots[0] + "/uptime", 1)
        expressions = config.default_source_expressions()
        expressions.update(temp_collector="to_number(state__collector)",
                           temp_tank_top="to_number(state__tank_top)",
                           temp_tank_bottom="to_number(state__tank_bottom)",
                           perc_pump_pwm="to_number(state__pump)")
        entry, subentry = fixture_entry(expressions=expressions)
        entry.data[c.CONF_PROTOCOL] = c.PROTOCOL_MQTT
        subentry.data[c.CONF_SOURCE_SYSTEM_ID] = "root"

        async def publish():
            previous = 0
            for moment, topic, value in events:
                await asyncio.sleep(moment - previous)
                self.emit(provider, topic, value)
                previous = moment

        started = asyncio.get_running_loop().time()
        task = asyncio.create_task(publish())
        try:
            with (
                patch.object(mqtt_module, "_STATE_WAIT_TIMEOUT", timeout),
                patch.object(mqtt_module, "_DISCOVERY_QUIET_PERIOD", 0.02),
                patch.object(cf, "_provider_from_data", return_value=provider),
                patch.object(cf, "_async_close_temporary_provider", new=AsyncMock()),
            ):
                if hub:
                    result = await cf._async_validate_hub_candidate(SimpleNamespace(),
                        entry.data, linked_entry=entry)
                else:
                    result = await cf._async_live_validate_system(
                        SimpleNamespace(), entry, "root", RuntimeConfiguration.compile(expressions),
                        allow_offline_contract=False,
                    )
            elapsed = asyncio.get_running_loop().time() - started
        finally:
            await task
        return result, provider, expressions, elapsed

    async def test_staggered_nonretained_fields_validate_and_binding_stays_frozen(self):
        events = [(0.01 + index * 0.11, f"root/sensor/{name}/state", value)
                  for index, (name, value) in enumerate(
                      (("collector", 40), ("tank_top", 35), ("tank_bottom", 25), ("pump", 0)))]
        for roots in (("root",), ("other", "root")):
            with self.subTest(roots=roots):
                result, provider, expressions, _ = await self.validate_stream(events, roots=roots)
                self.assertTrue(result.valid, result)
                runtime = RuntimeConfiguration.compile(expressions,
                    available_source_keys=result.available_source_keys)
                self.emit(provider, "root/backup/collector/state", 99)
                snapshot = await provider.get_system_snapshot(
                    "root", runtime.required_source_keys, runtime.source_keys)
                evaluated = evaluate_source_expressions(runtime.compiled_source_expressions,
                    snapshot.values, EvaluationContext(snapshot.last_report, snapshot.last_update))
                self.assertEqual(evaluated.values["temp_collector"], 40)
                self.assertFalse(evaluated.errors)

    async def test_late_ambiguity_is_a_field_error_while_collecting_missing_keys(self):
        result, _provider, _expressions, _ = await self.validate_stream([
            (0.01, "root/sensor/collector/state", 40),
            (0.12, "root/backup/collector/state", 99),
            (0.23, "root/sensor/tank_top/state", 35),
        ])
        self.assertFalse(result.valid)
        self.assertEqual(result.expression_errors.get("temp_collector"), "source_expression_ambiguous_source")
        self.assertIsNone(result.base_error)

    async def test_connection_validation_waits_for_linked_source_fields_too(self):
        events = [(0.01 + index * 0.11, f"root/sensor/{name}/state", value)
                  for index, (name, value) in enumerate(
                      (("collector", 40), ("tank_top", 35), ("tank_bottom", 25), ("pump", 0)))]
        result, _provider, _expressions, _ = await self.validate_stream(events, hub=True)
        self.assertEqual(result[c.CONF_PROTOCOL], c.PROTOCOL_MQTT)

    async def test_missing_fields_stop_at_deadline_despite_unrelated_reports(self):
        result, _provider, _expressions, elapsed = await self.validate_stream(
            [(0.01, "root/sensor/collector/state", 40)] +
            [(0.02 + index * 0.025, "root/uptime", index) for index in range(20)],
            timeout=0.4,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.expression_errors.get("temp_tank_top"), "source_value_missing_source")
        self.assertIsNone(result.base_error)
        self.assertGreaterEqual(elapsed, 0.35)
        self.assertLess(elapsed, 1.5)

    async def test_credentials_can_be_removed_replaced_or_retained_atomically(self):
        cases = (
            ("old", "old-secret", "", "", None),
            ("", "", "new", "new-secret", ("new", "new-secret")),
            ("old", "old-secret", "old", "", ("old", "old-secret")),
            ("old", "old-secret", "new", "", "error"),
            ("old", "old-secret", "new", "new-secret", ("new", "new-secret")),
            ("old", "old-secret", "old", "new-secret", ("old", "new-secret")),
            ("old", "old-secret", " old ", "", ("old", "old-secret")),
            ("old", "old-secret", "", "new-secret", "error"),
        )
        for index, (old_user, old_pass, username, password, expected) in enumerate(cases):
            with self.subTest(case=index):
                entry, subentry = fixture_entry()
                entry.data.update({c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
                                   c.CONF_KIND: c.HUB_KIND_PROVIDER,
                                   c.CONF_CONNECTION: {c.CONF_HOST: "broker.example", c.CONF_PORT: 1883,
                                                       c.CONF_TLS: False, c.CONF_KEEPALIVE: 60, c.CONF_QOS: 0}})
                if old_user:
                    entry.data[c.CONF_CONNECTION].update({c.CONF_USERNAME: old_user, c.CONF_PASSWORD: old_pass})
                entries = Entries(entry)
                before = deepcopy(entry.data)
                before_system = deepcopy(subentry.data)

                class Flow(cf.ConfigFlowHandler):
                    def _get_reconfigure_entry(self):
                        return entry

                    def async_show_form(self, **kwargs):
                        return kwargs

                    def async_abort(self, **kwargs):
                        return kwargs

                flow = Flow()
                flow.flow_id = f"credential-test-{index}"
                flow.hass = SimpleNamespace(data={}, config_entries=entries)
                flow._base_config_revision = entry.data[c.CONF_CONFIG_REVISION]
                flow._base_system_contract = cf._system_contract_snapshot(entry)
                seen = []

                async def validate(_hass, candidate, **kwargs):
                    self.assertEqual(entry.data, before)
                    self.assertEqual(subentry.data, before_system)
                    seen.append(deepcopy(candidate))
                    return candidate

                with (
                    patch.object(cf, "_async_validate_hub_candidate", validate),
                    patch.object(cf, "_entry_provider_id", return_value="fixture"),
                ):
                    result = await flow.async_step_reconfigure_mqtt({
                        **before[c.CONF_CONNECTION], c.CONF_USERNAME: username, c.CONF_PASSWORD: password})
                flow.async_remove()
                if expected == "error":
                    self.assertEqual(result.get("errors", {}).get("base"), "invalid_provider_config")
                    self.assertFalse(seen)
                    self.assertEqual(entry.data, before)
                    self.assertEqual(subentry.data, before_system)
                else:
                    self.assertEqual(result, {"reason": "reconfigure_successful"})
                    self.assertEqual(len(seen), 1)
                    connection = entry.data[c.CONF_CONNECTION]
                    if expected is None:
                        self.assertNotIn(c.CONF_USERNAME, connection)
                        self.assertNotIn(c.CONF_PASSWORD, connection)
                    else:
                        self.assertEqual((connection[c.CONF_USERNAME], connection[c.CONF_PASSWORD]), expected)
                    self.assertEqual(subentry.data[c.CONF_SOURCE_EXPRESSIONS], before_system[c.CONF_SOURCE_EXPRESSIONS])
                    self.assertEqual(entry.unique_id, HUB_UID)
                    self.assertEqual(subentry.unique_id, SYSTEM_UID)

    async def test_rejected_credential_change_keeps_every_saved_value(self):
        entry, subentry = fixture_entry()
        entry.data.update({c.CONF_PROTOCOL: c.PROTOCOL_MQTT,
            c.CONF_KIND: c.HUB_KIND_PROVIDER,
            c.CONF_CONNECTION: {c.CONF_HOST: "broker.example", c.CONF_PORT: 1883,
                               c.CONF_USERNAME: "old", c.CONF_PASSWORD: "old-secret"}})
        before = deepcopy(entry.data)
        before_system = deepcopy(subentry.data)

        class Flow(cf.ConfigFlowHandler):
            def _get_reconfigure_entry(self):
                return entry

            def async_show_form(self, **kwargs):
                return kwargs

        flow = Flow()
        flow.flow_id = "rejected-credentials"
        flow.hass = SimpleNamespace(data={}, config_entries=Entries(entry))
        flow._base_config_revision = entry.data[c.CONF_CONFIG_REVISION]
        flow._base_system_contract = cf._system_contract_snapshot(entry)
        reject = AsyncMock(side_effect=ProviderAuthenticationError("rejected-secret"))
        with (
            patch.object(cf, "_async_validate_hub_candidate", reject),
            patch.object(cf, "_entry_provider_id", return_value="fixture"),
        ):
            result = await flow.async_step_reconfigure_mqtt({c.CONF_HOST: "broker.example",
                c.CONF_PORT: 1883, c.CONF_USERNAME: "new", c.CONF_PASSWORD: "new-secret"})
        flow.async_remove()
        self.assertEqual(result["errors"]["base"], "invalid_auth")
        self.assertEqual(entry.data, before)
        self.assertEqual(subentry.data, before_system)
        self.assertNotIn("rejected-secret", repr(result))
        self.assertNotIn("new-secret", repr(result))


class MqttExactRootContracts(unittest.IsolatedAsyncioTestCase):
    async def test_copy_create_reconfigure_and_runtime_keep_the_exact_root(self):
        for root in (" root ", "x" * 257, "solar/é" * 40):
            with self.subTest(root_length=len(root)):
                entry, regular = fixture_entry()
                entry.data[c.CONF_PROTOCOL] = c.PROTOCOL_MQTT
                regular.data[c.CONF_SOURCE_SYSTEM_ID] = root
                entries = Entries(entry)

                class Flow(cf.DuplicateSystemSubentryFlowHandler):
                    def _get_entry(self):
                        return entry

                    def _get_reconfigure_subentry(self):
                        return self.saved

                    async def _async_discover_systems(self, entry):
                        return (root,)

                    async def _async_discover_communication_systems(self, entry):
                        return (root,)

                    def async_show_form(self, **kwargs):
                        return kwargs

                    def async_create_entry(self, **kwargs):
                        return kwargs

                    def async_abort(self, **kwargs):
                        return kwargs

                flow = Flow()
                flow.flow_id = "exact-root-create"
                flow.hass = SimpleNamespace(data={}, config_entries=entries)
                self.addCleanup(flow.async_remove)
                form = await flow.async_step_user({c.CONF_SOURCE_SYSTEM_ID: "local_copy",
                    c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: root})
                self.assertEqual(form.get("step_id"), "details", form.get("errors"))

                async def validate(_hass, _entry, source_id, runtime, **kwargs):
                    self.assertEqual(source_id, root)
                    return cf._LiveValidationResult(True, available_source_keys=("temp1", "temp2", "temp3", "pump"))

                with patch.object(cf, "_async_live_validate_system", validate):
                    created = await flow.async_step_details({c.CONF_SYSTEM_ID: "copy_boiler"})
                self.assertEqual(created["data"][c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID], root)
                flow.async_remove()
                copy = SimpleNamespace(subentry_type=c.SUBENTRY_TYPE_DUPLICATE_SYSTEM,
                    subentry_id="copy", unique_id="00000000-0000-4000-8000-000000000003",
                    data=created["data"])
                entry.subentries[copy.subentry_id] = copy
                self.assertEqual(config.duplicate_systems_from_entry(entry), {"local_copy": root})
                flow = Flow()
                flow.saved = copy
                flow.flow_id = "exact-root-reconfigure"
                flow.hass = SimpleNamespace(data={}, config_entries=entries)
                self.addCleanup(flow.async_remove)
                with patch.object(cf, "_async_live_validate_system", validate):
                    result = await flow.async_step_reconfigure({c.CONF_SYSTEM_ID: "copy_boiler",
                        c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID: root, c.CONF_ENABLED: True})
                self.assertEqual(result, {"reason": "reconfigure_successful"})
                self.assertEqual(copy.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID], root)

                class Local(mqtt_module.MqttProvider):
                    async def async_open(self):
                        pass

                    async def async_connect(self):
                        pass

                for generation in (1, 2):
                    provider = Local(connection={"host": "broker.example", "port": 1883},
                        provider_id="fixture", source_system_ids=(root,),
                        duplicate_systems=config.duplicate_systems_from_entry(entry))
                    self.addAsyncCleanup(provider.async_close)
                    for name, value in {"temp1": 42, "temp2": 35, "temp3": 25, "pump": 0}.items():
                        provider._handle_message(SimpleNamespace(topic=f"{root}/{name}", payload=str(value).encode()))
                    await provider.async_initialize()
                    runtime = config.build_system_runtimes(entry, provider, generation)[copy.unique_id]
                    snapshot = await runtime.system.status(runtime.configuration.required_source_keys,
                        runtime.configuration.source_keys)
                    self.assertEqual(snapshot.values["temp1"], "42")
                    self.assertEqual(runtime.source_system_id, "local_copy")
                self.assertEqual(copy.unique_id, "00000000-0000-4000-8000-000000000003")
                expressions = deepcopy(copy.data[c.CONF_SOURCE_EXPRESSIONS])
                for protocol in (c.PROTOCOL_ESPHOME_NATIVE, c.PROTOCOL_MQTT):
                    cf._publish_provider_candidate(flow.hass, entry,
                        {**entry.data, c.CONF_PROTOCOL: protocol}, protocol_changed=True)
                    self.assertFalse(copy.data[c.CONF_ENABLED])
                    self.assertEqual(copy.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID], root)
                    self.assertEqual(copy.data[c.CONF_SOURCE_SYSTEM_ID], "local_copy")
                    self.assertEqual(copy.data[c.CONF_SOURCE_EXPRESSIONS], expressions)
                self.assertEqual(config.duplicate_systems_from_entry(entry), {"local_copy": root})


class DuplicateBindingContracts(unittest.IsolatedAsyncioTestCase):
    """Validate and run real per-source adapters with simulated transports."""

    async def provider(self, protocol, target):
        aliases = {"local_alias": target}
        if protocol == c.PROTOCOL_ESPHOME_NATIVE:
            class Native(EsphomeNativeProvider):
                async def async_open(self):
                    pass

                async def async_connect(self):
                    pass

            provider = Native(
                connection={"host": "native.example", "port": 6053,
                            "noise_psk": base64.b64encode(b"x" * 32).decode()},
                provider_id="fixture", duplicate_systems=aliases,
            )
            names = ("temperature_1_raw", "temperature_2_raw", "temperature_3_raw", "pump_raw")
            info = SimpleNamespace(devices=(SimpleNamespace(device_id=1),))
            provider._publish_discovery(info, [
                SimpleNamespace(object_id=name, key=index, device_id=device)
                for device in (0, 1)
                for index, name in enumerate((*names, f"only_device_{device}"), 1)
            ], "aa:bb:cc:dd:ee:ff")
            for device in (0, 1):
                for key, value in enumerate((40 + device * 20, 45, 35, 0, 1), 1):
                    provider._async_on_state(SimpleNamespace(
                        key=key, device_id=device, state=value, missing_state=False,
                    ))
        else:
            class Mqtt(mqtt_module.MqttProvider):
                async def async_open(self):
                    pass

                async def async_connect(self):
                    pass

            provider = Mqtt(
                connection={"host": "broker.example", "port": 1883},
                provider_id="fixture", source_system_ids=("root/first", "root/second"),
                duplicate_systems=aliases,
            )
            for index, root in enumerate(("root/first", "root/second")):
                for name, value in {
                    "collector": 40 + index * 20, "tank_top": 45,
                    "tank_bottom": 35, "pump": 0, f"only_root_{index}": 1,
                }.items():
                    provider._handle_message(SimpleNamespace(
                        topic=f"{root}/sensor/{name}/state", payload=str(value).encode(),
                    ))
        await provider.async_initialize()
        self.addAsyncCleanup(provider.async_close)
        return provider

    async def test_copy_validation_matches_runtime_after_reload_and_relink(self):
        variants = (
            (c.PROTOCOL_ESPHOME_NATIVE, "plain"),
            (c.PROTOCOL_ESPHOME_NATIVE, "absolute"),
            (c.PROTOCOL_MQTT, "short"),
            (c.PROTOCOL_MQTT, "full"),
            (c.PROTOCOL_MQTT, "absolute"),
        )
        for protocol, spelling in variants:
            entry, duplicate = fixture_entry(duplicate=True)
            entry.data[c.CONF_PROTOCOL] = protocol
            expressions = config.default_source_expressions()
            names = ("temperature_1_raw", "temperature_2_raw", "temperature_3_raw", "pump_raw")
            if protocol == c.PROTOCOL_MQTT:
                names = tuple(f"state__{name}" for name in ("collector", "tank_top", "tank_bottom", "pump"))
                if spelling != "short":
                    names = tuple(name + "__sensor" for name in names)
            if spelling == "absolute":
                names = tuple("_0R__" + name for name in names)
            for key, name in zip(
                ("temp_collector", "temp_tank_top", "temp_tank_bottom", "perc_pump_pwm"),
                names, strict=True,
            ):
                expressions[key] = f"to_number({name})"
            duplicate.data[c.CONF_SOURCE_EXPRESSIONS] = expressions
            duplicate.data[c.CONF_ENABLED] = True
            targets = (
                ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff/1")
                if protocol == c.PROTOCOL_ESPHOME_NATIVE else ("root/first", "root/second")
            )
            for generation, stage in enumerate(("initial", "reload", "relink"), 1):
                with self.subTest(protocol=protocol, spelling=spelling, stage=stage):
                    target = targets[stage == "relink"]
                    duplicate.data[c.CONF_COMMUNICATION_SOURCE_SYSTEM_ID] = target
                    if stage == "relink":
                        duplicate.data[c.CONF_CONFIG_REVISION] += 1
                    validation_provider = await self.provider(protocol, target)
                    with patch.object(cf, "_async_initialize_provider", return_value=validation_provider):
                        validation = await cf._async_live_validate_system(
                            SimpleNamespace(), entry, target,
                            RuntimeConfiguration.compile(expressions),
                            allow_offline_contract=False,
                        )
                    self.assertTrue(validation.valid, validation)
                    duplicate.data[c.CONF_AVAILABLE_KEYS] = list(validation.available_source_keys)
                    duplicate.data[c.CONF_REQUIRED_SOURCE_KEYS] = list(validation.required_source_keys)
                    before = deepcopy(duplicate.data)
                    provider = await self.provider(protocol, target)
                    runtime = config.build_system_runtimes(entry, provider, generation)[SYSTEM_UID]
                    self.assertEqual(runtime.configuration.required_source_keys,
                                     set(validation.required_source_keys))
                    self.assertEqual(runtime.configuration.available_source_keys,
                                     set(provider.available_keys_for(target)))
                    snapshot = await asyncio.wait_for(runtime.system.status(
                        runtime.configuration.required_source_keys,
                        runtime.configuration.source_keys,
                    ), timeout=0.5)
                    result = evaluate_source_expressions(
                        runtime.configuration.compiled_source_expressions, snapshot.values,
                        EvaluationContext(snapshot.last_report, snapshot.last_update),
                    )
                    self.assertFalse(result.errors)
                    self.assertEqual(result.values["temp_collector"], 60 if stage == "relink" else 40)
                    self.assertEqual(runtime.system_uid, SYSTEM_UID)
                    self.assertEqual(runtime.subentry_id, duplicate.subentry_id)
                    self.assertEqual(runtime.source_system_id, "local_alias")
                    self.assertEqual(runtime.configuration.source_expressions, expressions)
                    self.assertEqual(duplicate.data, before)


class NanoC6KitContracts(unittest.TestCase):
    """Run the shipped mappings through observation, evaluation and publication."""

    def kit(self, protocol, *, device_report=True, diagnostics=True):
        readme = (
            Path(__file__).parents[1] / "esphome/public/README.md"
        ).read_text(encoding="utf-8")
        rows = re.findall(
            r'^\| `([a-z_0-9]+)` \| `([^`]+)` \| `([^`]+)` \|$',
            readme, re.MULTILINE,
        )
        self.assertEqual(
            {key for key, _, _ in rows},
            {"temp_collector", "temp_tank_top", "temp_tank_bottom",
             "perc_pump_pwm", "last_report", "status_reporting"},
        )
        expressions = config.default_source_expressions()
        expressions.update({key: native if protocol == "native" else mqtt
                            for key, native, mqtt in rows})
        if not device_report:
            expressions["last_report"] = "last_report()"
        observed = SourceObservation()

        def emit(name, value, at):
            if protocol == "mqtt":
                kind = ("text_sensor" if name == "last_report" else
                        "binary_sensor" if name == "data_valid" else "sensor")
                name = canonical_source_name((kind, name, "state"))
                value = (
                    "ON" if value is True else "OFF" if value is False
                    else str(value)
                )
            observed.observe_event(name, value, at)

        initial = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        initial_values = {
            "temperature_1_raw": 31.0, "temperature_2_raw": 52.0,
            "temperature_3_raw": 40.0, "pump_raw": 0.0,
        }
        if device_report:
            initial_values["last_report"] = initial.isoformat()
        if diagnostics:
            initial_values.update(data_age=0.0, data_valid=True)
        for name, value in initial_values.items():
            emit(name, value, initial)
        available = observed.snapshot(()).values.keys()
        runtime = SimpleNamespace(configuration=RuntimeConfiguration.compile(
            expressions, available_source_keys=available,
        ))
        coordinator = object.__new__(SystemCoordinator)
        coordinator._hub_runtime = SimpleNamespace(systems={SYSTEM_UID: runtime})
        coordinator._system_uid = SYSTEM_UID
        coordinator._evaluation_errors = {}
        coordinator._evaluated_values = {}
        coordinator._external_entity_values = {}

        def publish(now):
            snapshot = observed.snapshot(runtime.configuration.source_keys)
            with patch(
                "custom_components.solesta.expression_functions._utc_now",
                return_value=now,
            ):
                values = coordinator._evaluate_source_values(
                    runtime, snapshot.values, last_report=snapshot.last_report,
                    last_update=snapshot.last_update,
                )
            self.assertFalse(coordinator.evaluation_errors)
            return values, snapshot

        return initial, emit, publish, coordinator

    def test_device_report_ages_despite_diagnostics_and_recovers_with_a_new_frame(self):
        for protocol in ("native", "mqtt"):
            with self.subTest(protocol=protocol):
                initial, emit, publish, coordinator = self.kit(protocol)
                fresh, _ = publish(initial)
                self.assertTrue(fresh["status_reporting"])
                self.assertEqual(fresh["temp_collector"], 31.0)
                self.assertEqual(fresh["alerts_system"], "")
                emit("data_valid", False, initial + timedelta(seconds=16))
                for age in range(20, 3601, 5):
                    emit("data_age", float(age), initial + timedelta(seconds=age))
                stale, snapshot = publish(initial + timedelta(hours=1))
                self.assertEqual(snapshot.last_report, initial + timedelta(hours=1))
                self.assertEqual(stale["last_report"], initial)
                self.assertEqual(stale["report_delay"], initial.isoformat())
                self.assertFalse(stale["status_reporting"])
                self.assertEqual(json.loads(stale["alerts_system"])["type"], "offline")
                for key in ("temp_collector", "temp_tank_top", "temp_tank_bottom",
                            "temp_tank_average", "perc_pump_pwm", "energy_tank_kwh"):
                    self.assertIsNone(stale[key], key)
                restored_at = initial + timedelta(seconds=3601)
                for name, value in {
                    "temperature_1_raw": 32.0, "temperature_2_raw": 53.0,
                    "temperature_3_raw": 41.0, "pump_raw": 0.0,
                }.items():
                    emit(name, value, restored_at)
                emit("data_valid", True, restored_at)
                emit("last_report", restored_at.isoformat(), restored_at)
                recovered, _ = publish(restored_at)
                self.assertTrue(recovered["status_reporting"])
                self.assertEqual(recovered["temp_collector"], 32.0)
                self.assertEqual(recovered["temp_tank_top"], 53.0)
                self.assertEqual(recovered["alerts_system"], "")
                self.assertEqual(coordinator._system_uid, SYSTEM_UID)

    def test_device_report_uses_existing_age_boundaries_without_validity_input(self):
        for protocol in ("native", "mqtt"):
            with self.subTest(protocol=protocol):
                initial, emit, publish, _coordinator = self.kit(protocol, diagnostics=False)
                emit("data_age", 600, initial + timedelta(seconds=600))
                before_limit, _ = publish(initial + timedelta(seconds=600))
                self.assertTrue(before_limit["status_reporting"])
                after_limit, _ = publish(initial + timedelta(seconds=601))
                self.assertFalse(after_limit["status_reporting"])
                self.assertIsNone(after_limit["temp_collector"])
                self.assertEqual(json.loads(after_limit["alerts_system"])["type"], "offline")

    def test_generic_route_needs_only_temperatures_and_pump_without_heuristics(self):
        for protocol in ("native", "mqtt"):
            with self.subTest(protocol=protocol):
                initial, emit, publish, _coordinator = self.kit(
                    protocol, device_report=False, diagnostics=False,
                )
                later = initial + timedelta(hours=12)
                # Identical measurements can remain valid; no cooling guess.
                emit("temperature_1_raw", 31.0, later)
                values, snapshot = publish(later)
                self.assertEqual(len(snapshot.values), 4)
                self.assertTrue(values["status_reporting"])
                self.assertEqual(values["temp_collector"], 31.0)
                self.assertEqual(values["alerts_system"], "")

    def test_existing_mqtt_transport_expression_is_not_reinterpreted_by_new_field(self):
        initial, emit, publish, _coordinator = self.kit("mqtt", device_report=False)
        emit("last_report", initial.isoformat(), initial)
        later = initial + timedelta(hours=1)
        emit("data_age", 3600, later)
        values, _snapshot = publish(later)
        self.assertTrue(values["status_reporting"])
        self.assertEqual(values["last_report"], later)

    def test_missing_device_time_remains_unknown(self):
        initial, emit, publish, _coordinator = self.kit("native")
        emit("last_report", None, initial)
        values, _snapshot = publish(initial)
        self.assertIsNone(values["last_report"])
        self.assertIsNone(values["report_delay"])
        self.assertIsNone(values["status_reporting"])
        self.assertEqual(values["alerts_system"], "")


if __name__ == "__main__":
    unittest.main()
