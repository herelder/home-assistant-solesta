from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

ROOT = Path(
    os.environ.get(
        'SOLESTA_INTEGRATION_ROOT',
        Path(__file__).parents[1] / 'custom_components' / 'solesta',
    )
)
TEST_DOMAIN = os.environ.get('SOLESTA_TEST_DOMAIN', 'solesta')
PKG = 'archive_test_package'
package = ModuleType(PKG); package.__path__ = [str(ROOT)]; sys.modules[PKG] = package

def load(name):
    spec = importlib.util.spec_from_file_location(f'{PKG}.{name}', ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

files = load('archive_files')
UID = 'a638b5a7-b54a-40a1-93e1-c3229483c984'
WEEK = files.ArchiveWeek.from_key('2026-W35', 'Europe/Amsterdam')
NOW = WEEK.end + timedelta(minutes=20)

class Base(DeclarativeBase): pass
class States(Base):
    __tablename__ = 'states'
    state_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metadata_id: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    attributes_id: Mapped[int | None] = mapped_column(Integer)
    last_updated_ts: Mapped[float] = mapped_column(Float)
    last_changed_ts: Mapped[float | None] = mapped_column(Float)
    last_reported_ts: Mapped[float | None] = mapped_column(Float)
class StateAttributes(Base):
    __tablename__ = 'state_attributes'
    attributes_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shared_attrs: Mapped[str | None] = mapped_column(Text)
class StatesMeta(Base):
    __tablename__ = 'states_meta'
    metadata_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String)
class RecorderRuns(Base):
    __tablename__ = 'recorder_runs'
    run_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)
    closed_incorrect: Mapped[bool] = mapped_column(Boolean, default=False)

@contextmanager
def session_scope(*, hass, read_only):
    assert read_only is True
    with Session(hass.engine) as session:
        yield session

stubs = {}
for name in ['homeassistant', 'homeassistant.components', 'homeassistant.components.recorder',
             'homeassistant.components.recorder.db_schema', 'homeassistant.helpers',
             'homeassistant.helpers.recorder', 'homeassistant.helpers.device_registry',
             'homeassistant.helpers.entity_registry', 'homeassistant.helpers.issue_registry',
             'homeassistant.helpers.event', 'homeassistant.helpers.service',
             'homeassistant.helpers.start', 'homeassistant.core', 'homeassistant.const',
             'homeassistant.exceptions', 'homeassistant.loader']:
    stubs[name] = ModuleType(name)
stubs['homeassistant.components.recorder.db_schema'].__dict__.update(
    States=States, StatesMeta=StatesMeta, StateAttributes=StateAttributes, RecorderRuns=RecorderRuns)
stubs['homeassistant.helpers.recorder'].session_scope = session_scope
stubs['homeassistant.helpers.recorder'].get_instance = lambda hass: hass.recorder
stubs['homeassistant.core'].__dict__.update(HomeAssistant=object, ServiceCall=object,
    SupportsResponse=SimpleNamespace(OPTIONAL='optional'), callback=lambda function:function)
stubs['homeassistant.const'].EVENT_HOMEASSISTANT_STOP = 'stop'
stubs['homeassistant.exceptions'].HomeAssistantError = type('HomeAssistantError', (Exception,), {})
stubs['homeassistant.helpers.device_registry'].async_get = lambda hass: hass.devices
stubs['homeassistant.helpers.entity_registry'].async_get = lambda hass: hass.entities
stubs['homeassistant.helpers.entity_registry'].EVENT_ENTITY_REGISTRY_UPDATED = 'entity_registry_updated'
issues = stubs['homeassistant.helpers.issue_registry']
issues.async_create_issue = Mock(); issues.async_delete_issue = Mock(); issues.IssueSeverity = SimpleNamespace(ERROR='error', WARNING='warning')
stubs['homeassistant.helpers.event'].async_track_point_in_utc_time = Mock(return_value=lambda:None)
stubs['homeassistant.helpers.service'].async_register_admin_service = Mock()
stubs['homeassistant.helpers.start'].async_at_started = Mock(return_value=lambda:None)
stubs['homeassistant.loader'].async_get_integration = AsyncMock(return_value=SimpleNamespace(version='1.2.0'))
with patch.dict(sys.modules, stubs):
    recorder = load('archive_recorder')
    manager_module = load('archive')


def machine(uid=UID, number=1):
    entries = [{'entity_id':f'sensor.custom_name_{number}', 'entity_key':'temp',
                'unique_id':f'{uid}_temp', 'recorded_now':True},
               {'entity_id':f'number.custom_name_{number}', 'entity_key':'setting',
                'unique_id':f'{uid}_setting', 'recorded_now':True},
               {'entity_id':f'sensor.disabled_{number}', 'entity_key':'disabled',
                'unique_id':f'{uid}_disabled', 'recorded_now':True, 'disabled_by_now':'user'}]
    return {'system_uid':uid, 'name':f'System {number}', 'source_system_id':f'SOL_{number}', 'entities':entries}


class ArchiveCoordinator:
    """Focused coordinator contract used by archive-manager tests."""

    def __init__(self, uid, enabled=True):
        self.runtime = SimpleNamespace(
            system_uid=uid,
            configuration=SimpleNamespace(
                dropped_keys=frozenset(
                    {'archive_last_success', 'archive_status'}
                )
            ),
        )
        self.data = {'weekly_archive': enabled}
        self.external_values = {}
        self.listeners = []

    def async_set_external_entity_values(self, values):
        self.external_values = dict(values)

    def async_add_listener(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def set_enabled(self, enabled):
        self.data['weekly_archive'] = enabled
        for listener in tuple(self.listeners):
            listener()


class ArchiveCoordinators(dict):
    def get(self, uid, default=None):
        if uid not in self:
            self[uid] = ArchiveCoordinator(uid)
        return super().get(uid, default)


def raw_records(path):
    with gzip.open(path, 'rt') as source:
        document = json.load(source)
    rows = [item['last_recorded_state'] for item in document['initial_states'] if item.get('last_recorded_state')]
    rows += [item for item in document['changes'] if item['record_kind'] == 'state']
    return sorted(rows, key=lambda row: row['state_id'])


class WeekTests(unittest.TestCase):
    def test_spring_and_autumn_dst_and_iso_year_boundary(self):
        spring = files.ArchiveWeek.from_key('2026-W13','Europe/Amsterdam')
        autumn = files.ArchiveWeek.from_key('2026-W43','Europe/Amsterdam')
        self.assertEqual((spring.end - spring.start).total_seconds(),167*3600)
        self.assertEqual((autumn.end - autumn.start).total_seconds(),169*3600)
        self.assertEqual(files.ArchiveWeek(date(2025,12,29),'Europe/Amsterdam').key,'2026-W01')

    def test_grace_period_and_next_run_in_ha_time_zone(self):
        before = WEEK.end + timedelta(minutes=14)
        self.assertEqual(files.latest_due_week(before,WEEK.time_zone).key,'2026-W34')
        self.assertEqual(files.next_weekly_run(before,WEEK.time_zone), WEEK.end + timedelta(minutes=15))
        self.assertEqual(files.latest_due_week(NOW,WEEK.time_zone), WEEK)
        self.assertEqual(files.next_weekly_run(NOW,WEEK.time_zone), WEEK.following().end + timedelta(minutes=15))

    def test_invalid_week_and_path_inputs_are_rejected(self):
        for key in ['2026-W00','2026-W54','2026-W1','../../x']:
            with self.assertRaises(ValueError): files.ArchiveWeek.from_key(key,WEEK.time_zone)
        with self.assertRaises(ValueError): files.machine_folder(Path('/tmp'), '../../etc')

    def test_progress_is_saved_before_first_export_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            self.assertEqual(files.load_progress(path,WEEK),WEEK)
            self.assertEqual(files.load_progress(path,WEEK.following()),WEEK)
            files.save_progress(path,WEEK.following())
            self.assertEqual(files.load_progress(path,WEEK.following()),WEEK.following())
            with self.assertRaises(files.ArchiveError):
                files.load_progress(path,files.ArchiveWeek(WEEK.monday,'UTC'))


class DatabaseArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.root=Path(self.temporary.name)
        self.engine=create_engine(f'sqlite:///{self.root / "recorder.db"}')
        with self.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        Base.metadata.create_all(self.engine)
        self.hass=SimpleNamespace(engine=self.engine)
        self.machine=machine(); self.path=self.root/'week.json.gz'
        self.config={'keep_days':10,'auto_purge':True,'enabled':True,'schema_version':99}
        start,end=WEEK.start.timestamp(),WEEK.end.timestamp()
        with Session(self.engine) as session:
            session.add_all([
                StatesMeta(metadata_id=1,entity_id='sensor.custom_name_1'),
                StatesMeta(metadata_id=2,entity_id='number.custom_name_1'),
                StatesMeta(metadata_id=3,entity_id='sensor.unrelated'),
                StateAttributes(attributes_id=1,shared_attrs='{"unit_of_measurement":"°C","nested":{"text":"é\\nnew line"}}'),
                StateAttributes(attributes_id=2,shared_attrs='{"unit_of_measurement":"°C","changed":true}'),
                RecorderRuns(start=WEEK.start-timedelta(days=1),end=None),
                States(state_id=1,metadata_id=1,state='20',attributes_id=1,last_updated_ts=start-60),
                States(state_id=2,metadata_id=1,state='21',attributes_id=1,last_updated_ts=start),
                States(state_id=3,metadata_id=1,state='21',attributes_id=2,last_updated_ts=start+60,last_changed_ts=start,last_reported_ts=start+61),
                States(state_id=4,metadata_id=1,state='unknown',attributes_id=1,last_updated_ts=start+120),
                States(state_id=5,metadata_id=1,state='unavailable',attributes_id=1,last_updated_ts=start+180),
                States(state_id=6,metadata_id=1,state='',attributes_id=None,last_updated_ts=start+240),
                States(state_id=7,metadata_id=1,state='next week',attributes_id=1,last_updated_ts=end),
                States(state_id=8,metadata_id=2,state='12',attributes_id=1,last_updated_ts=start-86400),
                States(state_id=9,metadata_id=3,state='not Solesta',attributes_id=1,last_updated_ts=start+1),
            ]); session.commit()

    def tearDown(self):
        self.engine.dispose(); self.temporary.cleanup()

    def export(self, now=NOW):
        return recorder.export_recorder_week(self.hass,self.path,self.machine,WEEK,now,self.config,TEST_DOMAIN,'1.2.0')

    def test_all_original_states_attributes_and_start_values_are_preserved(self):
        result=self.export()
        rows = raw_records(self.path)
        self.assertEqual([row['state_id'] for row in rows],[1,2,3,4,5,6,8])
        self.assertEqual(rows[0]['record_kind'],'start_state')
        self.assertEqual(rows[0]['last_updated_ts'],WEEK.start.timestamp()-60)
        self.assertEqual(rows[2]['last_changed_ts'],WEEK.start.timestamp())
        self.assertTrue(rows[2]['attributes']['changed'])
        self.assertEqual(rows[0]['attributes']['nested']['text'],'é\nnew line')
        self.assertEqual(rows[0]['last_changed_ts'],None)
        self.assertEqual(rows[0]['last_changed_utc'],rows[0]['last_updated_utc'])
        self.assertTrue(rows[5]['removed'])
        self.assertEqual(result['record_count'],8)
        with gzip.open(self.path, 'rt') as source: document=json.load(source)
        self.assertEqual(document['entities'][2]['states'],0)
        self.assertEqual(set(document), {'archive','entities','initial_states','changes'})
        self.assertEqual(result['week']['duration_seconds'],604800)
        self.assertIn('no_start_state',[warning['code'] for warning in result['coverage']['warnings']])
        self.assertNotIn('recorder_gap',[warning['code'] for warning in result['coverage']['warnings']])

    def test_export_is_read_only_and_repeat_preserves_existing_zip(self):
        with Session(self.engine) as session: before=session.scalar(select(func.count()).select_from(States))
        self.export(); data=self.path.read_bytes(); stamp=self.path.stat().st_mtime_ns
        self.export()
        self.assertEqual(self.path.read_bytes(),data); self.assertEqual(self.path.stat().st_mtime_ns,stamp)
        with Session(self.engine) as session: after=session.scalar(select(func.count()).select_from(States))
        self.assertEqual(before,after)

    def test_corrupt_existing_archive_is_rejected_and_not_overwritten(self):
        self.path.write_bytes(b'corrupted')
        with self.assertRaises(files.ArchiveError): self.export()
        self.assertEqual(self.path.read_bytes(),b'corrupted')

    def test_failed_export_leaves_no_final_or_temporary_zip(self):
        with patch.object(recorder,'_record',side_effect=RuntimeError('read failed')):
            with self.assertRaises(RuntimeError): self.export()
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.root.glob('.pending-*')),[])

    def test_possible_purge_loss_and_recorder_gaps_are_declared(self):
        with Session(self.engine) as session:
            run=session.get(RecorderRuns,1); run.end=WEEK.start+timedelta(days=2)
            session.add(RecorderRuns(start=WEEK.start+timedelta(days=3),end=None,closed_incorrect=True));session.commit()
        result=self.export(now=NOW+timedelta(days=5))
        codes=[warning['code'] for warning in result['coverage']['warnings']]
        self.assertIn('week_exceeds_configured_retention',codes)
        self.assertIn('recorder_gap',codes)
        self.assertIn('recorder_run_closed_incorrectly',codes)

    def test_concurrent_recorder_write_cannot_change_the_export_snapshot(self):
        original=recorder._record; changed=False
        def intercept(row, entity, kind):
            nonlocal changed
            if not changed:
                changed=True
                with Session(self.engine) as session:
                    session.add(States(state_id=10,metadata_id=2,state='concurrent',last_updated_ts=WEEK.start.timestamp()+1))
                    session.commit()
            return original(row,entity,kind)
        with patch.object(recorder,'_record',side_effect=intercept): self.export()
        rows = raw_records(self.path)
        self.assertNotIn(10,[row['state_id'] for row in rows])
        with Session(self.engine) as session: self.assertIsNotNone(session.get(States,10))

    def test_wrong_machine_or_week_cannot_reuse_an_archive(self):
        self.export()
        with self.assertRaises(files.ArchiveError): files.verify_archive(self.path,'b'*36,WEEK)
        with self.assertRaises(files.ArchiveError): files.verify_archive(self.path,UID,WEEK.following())


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        ready=asyncio.get_running_loop().create_future(); ready.set_result(True)
        async def executor(function,*args): return function(*args)
        self.recorder=SimpleNamespace(async_db_ready=ready,async_block_till_done=AsyncMock(),
            async_add_executor_job=executor,keep_days=10,auto_purge=True,enabled=True,schema_version=99)
        self.hass=SimpleNamespace(config=SimpleNamespace(time_zone=WEEK.time_zone,path=lambda name:str(self.root/name)),
            recorder=self.recorder,async_add_executor_job=executor)
        self.coordinators=ArchiveCoordinators({UID:ArchiveCoordinator(UID)})
        runtime=SimpleNamespace(coordinators=self.coordinators)
        entry=SimpleNamespace(entry_id='hub',disabled_by=None,runtime_data=runtime)
        self.hass.config_entries=SimpleNamespace(async_entries=lambda domain:[entry])
        self.manager=manager_module.ArchiveManager(self.hass,'1.3.0')
        self.manager.initialized=True
        files.save_progress(self.manager.root/UID,WEEK)
        self.calls=[]
        def export(hass,path,machine,week,*args):
            self.calls.append((machine['system_uid'],week.key))
            return {'record_count':2,'coverage':{'warnings':[]}}
        self.exporter=patch.object(manager_module,'export_recorder_week',side_effect=export);self.exporter.start()
        self.collector=patch.object(manager_module,'collect_machines',return_value=[machine()]);self.collector.start()
        self.clock=patch.object(manager_module,'datetime'); self.mocktime=self.clock.start();self.mocktime.now.return_value=NOW
        issues.async_create_issue.reset_mock();issues.async_delete_issue.reset_mock()

    async def asyncTearDown(self):
        self.exporter.stop();self.collector.stop();self.clock.stop();self.temporary.cleanup()

    async def test_archive_root_is_scoped_by_integration_domain(self):
        self.assertEqual(
            self.manager.root,
            self.root/'archives'/TEST_DOMAIN,
        )
        self.assertEqual(
            self.manager.journal.path,
            self.manager.root/'registry.sqlite3',
        )

    async def test_existing_administration_and_restart_catch_up_without_duplicate_weeks(self):
        result=await self.manager.run(); self.assertEqual(len(result['archives']),1)
        self.assertEqual(self.calls,[(UID,'2026-W35')])
        await self.manager.run(); self.assertEqual(len(self.calls),1)
        self.mocktime.now.return_value=NOW+timedelta(weeks=3)
        another=manager_module.ArchiveManager(self.hass,'1.3.0')
        another.initialized=True
        result=await another.run()
        self.assertEqual([week for _,week in self.calls],['2026-W35','2026-W36','2026-W37','2026-W38'])
        self.assertFalse(result['more_pending'])

    async def test_failure_is_queued_and_other_machines_continue(self):
        uid2='b638b5a7-b54a-40a1-93e1-c3229483c984'
        files.save_progress(self.manager.root/uid2,WEEK)
        manager_module.collect_machines.return_value=[machine(),machine(uid2,2)]
        def export(hass,path,machine,week,*args):
            if machine['system_uid']==UID: raise OSError('disk error')
            return {'record_count':0,'coverage':{'warnings':[]}}
        manager_module.export_recorder_week.side_effect=export
        with self.assertLogs(manager_module._LOGGER,level='ERROR'):
            result=await self.manager.run()
        self.assertEqual(len(result['errors']),1);self.assertEqual(len(result['archives']),1)
        self.assertEqual(files.load_progress(self.manager.root/UID,WEEK),WEEK.following())
        self.assertEqual(self.manager.statuses[UID]['failed_weeks'],[WEEK.key])
        self.assertEqual(files.load_progress(self.manager.root/uid2,WEEK),WEEK.following())
        self.assertTrue(any(call.args[2]=='archive_failed' for call in issues.async_create_issue.call_args_list))

    async def test_scheduled_and_manual_runs_share_one_lock(self):
        await asyncio.gather(self.manager.run(),self.manager.run())
        self.assertEqual(len(self.calls),1)

    async def test_current_and_future_weeks_are_rejected(self):
        with self.assertRaises(ValueError): await self.manager.run('2026-W36')
        self.assertFalse(self.calls)

    async def test_catchup_is_bounded_and_reports_remaining_work(self):
        files.save_progress(self.manager.root/UID,files.ArchiveWeek.from_key('2026-W01',WEEK.time_zone))
        result=await self.manager.run()
        self.assertEqual(len(result['archives']),manager_module.MAX_CATCHUP_WEEKS)
        self.assertTrue(result['more_pending'])

    async def test_stop_waits_for_a_manual_export_to_finish(self):
        started=asyncio.Event(); release=asyncio.Event()
        async def blocking_export(function,*args):
            started.set();await release.wait();return {'record_count':2,'coverage':{'warnings':[]}}
        self.recorder.async_add_executor_job=blocking_export
        task=asyncio.create_task(self.manager.run());await started.wait()
        stopping=asyncio.create_task(self.manager.stop());await asyncio.sleep(0)
        self.assertFalse(stopping.done())
        self.assertTrue(self.manager.stopping)
        release.set();await task;await stopping
        self.assertIsNone(self.manager.running_task)

    async def test_manual_old_week_does_not_rebase_automatic_progress(self):
        await self.manager.run('2026-W01')
        self.assertEqual(files.load_progress(self.manager.root/UID,WEEK),WEEK)
        await self.manager.run()
        self.assertEqual([week for _,week in self.calls],['2026-W01','2026-W35'])

    async def test_cancellation_waits_for_worker_before_releasing_lock(self):
        started=asyncio.Event(); release=asyncio.Event()
        async def blocking_export(function,*args):
            started.set();await release.wait();return {'record_count':2,'coverage':{'warnings':[]}}
        self.recorder.async_add_executor_job=blocking_export
        task=asyncio.create_task(self.manager.run());await started.wait()
        task.cancel();await asyncio.sleep(0)
        self.assertTrue(self.manager.lock.locked())
        release.set()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertFalse(self.manager.lock.locked())

class EndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_domain_starts_with_empty_archive_administration(self):
        """A new domain must not import or mutate its predecessor's journal."""
        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory)
            predecessor_domain = (
                'solestanext' if TEST_DOMAIN == 'solesta' else 'solesta'
            )
            predecessor_root = config_root / 'archives' / predecessor_domain
            predecessor_root.mkdir(parents=True)
            marker = predecessor_root / 'untouched.txt'
            marker.write_text('predecessor data', encoding='utf-8')

            async def executor(function, *args):
                return function(*args)

            cancel_registry = Mock()
            hass = SimpleNamespace(
                config=SimpleNamespace(
                    path=lambda name: str(config_root / name),
                ),
                recorder=SimpleNamespace(
                    entity_filter=None,
                    exclude_event_types=set(),
                ),
                config_entries=SimpleNamespace(async_entries=Mock(return_value=[])),
                devices=SimpleNamespace(async_get=lambda device_id: None),
                entities=SimpleNamespace(entities={}),
                bus=SimpleNamespace(
                    async_listen=Mock(return_value=cancel_registry),
                ),
                async_add_executor_job=executor,
            )
            manager = manager_module.ArchiveManager(hass, '0.1.0')
            await manager.initialize()

            self.assertEqual(
                manager.root, config_root / 'archives' / TEST_DOMAIN
            )
            hass.config_entries.async_entries.assert_called_once_with(TEST_DOMAIN)
            self.assertEqual(manager.statuses, {})
            self.assertEqual(
                [record['kind'] for record in manager.journal_records],
                ['start'],
            )
            self.assertFalse((manager.root / 'settings.json').exists())
            self.assertEqual(marker.read_text(encoding='utf-8'), 'predecessor data')
            self.assertTrue((manager.root / 'registry.sqlite3').is_file())
            if manager.cancel_registry:
                manager.cancel_registry()

    async def test_manager_writes_and_verifies_real_database_archive(self):
        fixture=DatabaseArchiveTests();fixture.setUp()
        try:
            ready=asyncio.get_running_loop().create_future();ready.set_result(True)
            async def executor(function,*args): return function(*args)
            hass=fixture.hass
            hass.config=SimpleNamespace(time_zone=WEEK.time_zone,path=lambda name:str(fixture.root/name))
            hass.async_add_executor_job=executor
            hass.recorder=SimpleNamespace(async_db_ready=ready,async_block_till_done=AsyncMock(),
                async_add_executor_job=executor,keep_days=10,auto_purge=True,enabled=True,schema_version=99)
            coordinators=ArchiveCoordinators({UID:ArchiveCoordinator(UID)})
            entry=SimpleNamespace(
                entry_id='hub',disabled_by=None,
                runtime_data=SimpleNamespace(coordinators=coordinators),
            )
            hass.config_entries=SimpleNamespace(async_entries=lambda domain:[entry])
            manager=manager_module.ArchiveManager(hass,'1.3.0')
            manager.initialized=True
            files.save_progress(manager.root/UID,WEEK)
            with patch.object(manager_module,'datetime') as clock, patch.object(manager_module,'collect_machines',return_value=[fixture.machine]):
                clock.now.return_value=NOW
                result=await manager.run()
                self.assertFalse(result['errors'])
                self.assertEqual(result['archives'][0]['record_count'],8)
                path=manager.root/UID/'2026-W35.json.gz'
                files.verify_archive(path,UID,WEEK)
                self.assertEqual(files.load_progress(manager.root/UID,WEEK),WEEK.following())
                original=path.read_bytes()
                self.assertEqual((await manager.run())['archives'],[])
                self.assertEqual(path.read_bytes(),original)
        finally:
            fixture.tearDown()

    async def test_setup_registers_one_admin_action_and_start_and_stop_callbacks(self):
        service=stubs['homeassistant.helpers.service'].async_register_admin_service
        start=stubs['homeassistant.helpers.start'].async_at_started
        service.reset_mock();start.reset_mock()
        with tempfile.TemporaryDirectory() as directory:
            hass=SimpleNamespace(data={},config=SimpleNamespace(path=lambda name:str(Path(directory)/name)),
                bus=SimpleNamespace(async_listen_once=Mock()))
            with patch.object(manager_module.ArchiveManager, "initialize", new=AsyncMock()):
                await manager_module.async_setup_archiving(hass)
                await manager_module.async_setup_archiving(hass)
            service.assert_called_once(); start.assert_called_once(); hass.bus.async_listen_once.assert_called_once()
            self.assertEqual(service.call_args.args[1:3],(TEST_DOMAIN,'archive_week'))
            self.assertEqual(service.call_args.kwargs['supports_response'],'optional')


class RegistryTests(unittest.TestCase):
    def test_groups_all_entities_and_excludes_disabled_hubs_and_other_integrations(self):
        uid2='b638b5a7-b54a-40a1-93e1-c3229483c984'
        sub=SimpleNamespace(
            subentry_id='system_a', subentry_type='system', unique_id=UID,
            data={'system_id':'Visible name','source_system_id':'SOL_PHYSICAL'})
        entry=SimpleNamespace(entry_id='hub_a',unique_id='hub_uid',disabled_by=None,
            subentries={'system_a':sub})
        disabled=SimpleNamespace(entry_id='hub_b',unique_id='other_hub',disabled_by='user',
            subentries={})
        device=SimpleNamespace(id='device_a',identifiers={(TEST_DOMAIN,UID)},name='Machine',name_by_user=None)
        device2=SimpleNamespace(id='device_b',identifiers={(TEST_DOMAIN,uid2)},name='Other',name_by_user=None)
        def entity(key, **updates):
            data=dict(entity_id='sensor.renamed_'+key,domain='sensor',unique_id=UID+'_'+key,
                device_id='device_a',platform=TEST_DOMAIN,config_entry_id='hub_a',
                translation_key=key,unit_of_measurement='°C',disabled_by=None,created_at=NOW)
            data.update(updates);return SimpleNamespace(**data)
        other_domain = 'solesta' if TEST_DOMAIN == 'solestanext' else 'solestanext'
        entities=[entity('temperature'),entity('disabled',disabled_by='user'),
            entity('foreign',platform=other_domain),entity('other',config_entry_id='hub_b',device_id='device_b',unique_id=uid2+'_other')]
        hass=SimpleNamespace(recorder=SimpleNamespace(entity_filter=None,exclude_event_types=set()),
            config_entries=SimpleNamespace(async_entries=lambda domain:[entry,disabled]),
            devices=SimpleNamespace(async_get=lambda device_id:{'device_a':device,'device_b':device2}.get(device_id)),
            entities=SimpleNamespace(entities={item.entity_id:item for item in entities}))
        result=manager_module.collect_machines(hass)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['source_system_id'],'SOL_PHYSICAL')
        self.assertEqual([e['entity_key'] for e in result[0]['entities']],['disabled','temperature'])
        self.assertEqual(result[0]['entities'][0]['disabled_by_now'],'user')
        self.assertEqual(manager_module.collect_machines(hass,'device_b'),[])


if __name__=='__main__': unittest.main()
