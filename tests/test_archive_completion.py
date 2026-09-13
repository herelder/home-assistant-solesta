"""Behavioural tests for the agreed weekly source-archive specification."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.orm import Session

import test_archives as base

journal = base.load('archive_journal')
timeline = base.load('archive_timeline')
with patch.dict(__import__('sys').modules, base.stubs):
    backup = base.load('backup')
files = base.files
UID, WEEK, NOW = base.UID, base.WEEK, base.NOW
START = WEEK.start.timestamp()


def event(entity, at, kind='observe', before=None, **changes):
    data = deepcopy(entity)
    data.update(changes)
    item = {'kind': kind, 'at': at, 'entity': data,
            'machine': {key: val for key,val in base.machine().items() if key != 'entities'}}
    if before is not None:
        item['before'] = before
    return item


def raw(entity, at, state, **extra):
    return {'record_kind': 'state', 'unique_id': entity['unique_id'], 'entity_key': entity['entity_key'],
            'entity_id': entity['entity_id'], 'state': state, 'last_updated_ts': at,
            'attributes': {'value': 'unchanged'}, **extra}


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.entity = base.machine()['entities'][0]
        self.entity.update(present=True, disabled_by_now=None)

    def test_disable_reenable_and_new_value_preserve_raw_rows(self):
        entity=self.entity
        enabled=deepcopy(entity);disabled={**entity,'disabled_by_now':'user'}
        entity['registry_history']=[event(enabled,START-100),event(disabled,START+10,'update',enabled),
                                    event(enabled,START+20,'update',disabled)]
        rows=[raw(entity,START+1,'52.4'),raw(entity,START+11,'unavailable'),
              raw(entity,START+12,''),raw(entity,START+21,'51.8')]
        result=list(timeline.merge_entity(entity,WEEK,raw(entity,START-10,'50'),iter(rows),[]))
        self.assertEqual([item['effective_state'] for item in result],
                         ['50','52.4','uitgeschakeld','uitgeschakeld','uitgeschakeld','unknown','51.8'])
        self.assertEqual(result[3]['state'],'unavailable')
        self.assertEqual(result[4]['state'],'')
        self.assertFalse(result[3]['applies_to_state'])
        self.assertTrue(result[-1]['applies_to_state'])

    def test_off_unknown_unavailable_and_disabled_remain_distinct(self):
        entity=self.entity
        entity['registry_history']=[event(entity,START-10),event(entity,START+4,'update',entity,disabled_by_now='user')]
        rows=[raw(entity,START+1,'off'),raw(entity,START+2,'unknown'),raw(entity,START+3,'unavailable')]
        result=list(timeline.merge_entity(entity,WEEK,None,rows,[]))
        self.assertEqual([item['effective_state'] for item in result[1:]],['off','unknown','unavailable','uitgeschakeld'])

    def test_already_disabled_at_week_start_and_observation_later_not_backdated(self):
        entity=self.entity
        disabled={**entity,'disabled_by_now':'user'}
        entity['registry_history']=[event(disabled,START-1)]
        result=list(timeline.merge_entity(entity,WEEK,raw(entity,START-100,'52'),[],[]))
        self.assertEqual(result[0]['effective_state'],'uitgeschakeld')
        self.assertEqual(result[0]['last_recorded_state']['state'],'52')
        entity['registry_history']=[event(disabled,START+100)]
        warnings=[];result=list(timeline.merge_entity(entity,WEEK,None,[],warnings))
        self.assertEqual(result[0]['effective_state'],'unknown')
        self.assertEqual(result[1]['at'],START+100)
        self.assertEqual(result[1]['effective_state'],'uitgeschakeld')
        self.assertIn('registry_state_at_week_start_unknown',[item['code'] for item in warnings])

    def test_entity_created_in_week_before_journal_started_uses_recorded_values(self):
        entity=self.entity
        entity['registry_created_at_utc']=files.utc_iso(START+10)
        entity['registry_history']=[event(entity,WEEK.end.timestamp()+100)]
        rows=[raw(entity,START+11,'15.0'),raw(entity,START+12,'30.0')]
        result=list(timeline.merge_entity(entity,WEEK,None,rows,[]))
        self.assertFalse(result[0]['present'])
        self.assertEqual(result[0]['effective_state'],'unknown')
        self.assertEqual([item['effective_state'] for item in result[1:]],['15.0','30.0'])
        self.assertTrue(all(item['applies_to_state'] and item['present'] for item in result[1:]))

    def test_known_registry_removal_is_not_undone_by_a_late_recorder_row(self):
        entity=self.entity
        entity['registry_created_at_utc']=files.utc_iso(START+10)
        entity['registry_history']=[event(entity,START+10,'create'),event(entity,START+12,'remove',present=False)]
        result=list(timeline.merge_entity(entity,WEEK,None,[raw(entity,START+13,'unavailable')],[]))
        self.assertFalse(result[-1]['applies_to_state'])
        self.assertFalse(result[-1]['present'])

    def test_reenabled_before_week_does_not_restore_obsolete_value(self):
        entity=self.entity;disabled={**entity,'disabled_by_now':'user'}
        entity['registry_history']=[event(disabled,START-100),event(entity,START-5,'update',disabled)]
        result=list(timeline.merge_entity(entity,WEEK,raw(entity,START-10,'52'),[],[]))
        self.assertEqual(result[0]['effective_state'],'unknown')

    def test_added_removed_and_renamed_are_explicit_and_end_is_excluded(self):
        entity=self.entity;renamed={**entity,'entity_id':'sensor.new_name'}
        entity['registry_created_at_utc']=files.utc_iso(START+10)
        entity['registry_history']=[event(entity,START+10,'create'),event(renamed,START+20,'update',entity),
                                    event(renamed,START+30,'remove',present=False),event(entity,WEEK.end.timestamp(),'create')]
        result=list(timeline.merge_entity(entity,WEEK,None,[],[]))
        self.assertFalse(result[0]['present'])
        self.assertEqual([item['event'] for item in result[1:]],['create','update','remove'])
        self.assertFalse(result[2]['applies_to_state'])
        self.assertFalse(result[-1]['present'])

    def test_rename_chain_and_reuse_of_old_name_dont_mix_identity(self):
        entity=self.entity;renamed={**entity,'entity_id':'sensor.renamed'}
        entity['registry_history']=[event(entity,START-10),event(renamed,START+10,'update',entity)]
        other={**deepcopy(entity),'unique_id':UID+'_other','entity_key':'other',
               'registry_created_at_utc':files.utc_iso(START+20),'registry_history':[]}
        other['registry_history']=[event(other,START+20,'create')]
        self.assertEqual(timeline.owner_for_row([entity,other],'sensor.renamed',START),entity['unique_id'])
        self.assertEqual(timeline.owner_for_row([entity,other],entity['entity_id'],START+30),other['unique_id'])

    def test_recreated_stable_identity_keeps_earlier_registered_history(self):
        entity=self.entity
        original={**entity,'registry_created_at_utc':files.utc_iso(START-1000)}
        entity['registry_created_at_utc']=files.utc_iso(START+30)
        entity['registry_history']=[event(original,START-1000,'create'),event(original,START+10,'remove',present=False),
                                    event(entity,START+30,'create')]
        self.assertEqual(timeline.owner_for_row([entity],entity['entity_id'],START),entity['unique_id'])
        self.assertIsNone(timeline.owner_for_row([entity],entity['entity_id'],START+20))
        self.assertEqual(timeline.owner_for_row([entity],entity['entity_id'],START+40),entity['unique_id'])

    def test_entities_removed_before_week_stay_out_until_registered_again(self):
        entity=self.entity
        entity['registry_history']=[event(entity,START-100,'remove',present=False)]
        self.assertFalse(timeline.participates_in_week(entity,WEEK))
        entity['registry_history'].append(event(entity,START+10,'create'))
        self.assertTrue(timeline.participates_in_week(entity,WEEK))

    def test_ambiguous_name_collision_stops_instead_of_guessing(self):
        entity=self.entity
        other={**entity,'unique_id':UID+'_other'}
        with self.assertRaises(files.ArchiveError):
            timeline.owner_for_row([entity,other],entity['entity_id'],START)

    def test_empty_removal_row_belongs_to_interval_ending_at_that_removal(self):
        first=deepcopy(self.entity)
        first['registry_history']=[event(first,START-100),event(first,START+10,'remove',present=False)]
        second={**deepcopy(self.entity),'unique_id':UID+'_second','entity_key':'second',
                'registry_created_at_utc':files.utc_iso(START+20)}
        second['registry_history']=[event(second,START+20,'create'),event(second,START+30,'remove',present=False)]
        ownership=timeline.RowOwnership([first,second])
        self.assertEqual(ownership.owner(first['entity_id'],START+10,removed=True),first['unique_id'])
        self.assertEqual(ownership.owner(second['entity_id'],START+30,removed=True),second['unique_id'])


class JournalTests(unittest.TestCase):
    def test_commit_restart_idempotency_and_transaction_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            store=journal.RegistryJournal(Path(directory)/'registry.sqlite3')
            item=event(base.machine()['entities'][0],START)
            stored=store.append([item]);self.assertEqual(store.read(),stored)
            self.assertEqual(store.append([item]),stored)
            self.assertEqual(len(store.read()),1)
            with self.assertRaises(ValueError): store.append([{'kind':'start','at':START+1},{'kind':'start','at':float('nan')}])
            self.assertEqual(len(store.read()),1)
            self.assertEqual(journal.RegistryJournal(store.path).read(),stored)

    def test_corrupt_journal_is_rejected_without_resetting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'journal.sqlite3';path.write_bytes(b'not a database')
            with self.assertRaises(Exception): journal.RegistryJournal(path).read()
            self.assertEqual(path.read_bytes(),b'not a database')

    def test_disable_and_enable_in_same_event_loop_burst(self):
        previous=journal.registry_snapshot([base.machine()]);current=deepcopy(previous)
        name=base.machine()['entities'][0]['entity_id']
        previous[name]['entity']['disabled_by_now']=None;current[name]['entity']['disabled_by_now']=None
        changes=[{'action':'update','entity_id':name,'at':START+1,'changes':{'disabled_by':None}},
                 {'action':'update','entity_id':name,'at':START+2,'changes':{'disabled_by':'user'}}]
        events=journal.registry_events(previous,current,changes)
        self.assertEqual([item['entity']['disabled_by_now'] for item in events],['user',None])
        self.assertEqual(events[0]['before']['disabled_by_now'],None)
        self.assertEqual(events[1]['before']['disabled_by_now'],'user')

    def test_rename_then_delete_in_one_burst_retains_both(self):
        previous=journal.registry_snapshot([base.machine()]);name=base.machine()['entities'][0]['entity_id']
        current={key:value for key,value in previous.items() if key!=name}
        renamed=deepcopy(previous[name]);renamed['entity']['entity_id']='sensor.renamed'
        changes=[{'action':'update','entity_id':'sensor.renamed','old_entity_id':name,'at':START+1,'changes':{}},
                 {'action':'remove','entity_id':'sensor.renamed','at':START+2,'removed_snapshot':renamed}]
        result=journal.registry_events(previous,current,changes)
        self.assertEqual([item['kind'] for item in result],['update','remove'])
        self.assertEqual(result[0]['before']['entity_id'],name)

    def test_removed_entity_is_kept_under_its_stable_identity(self):
        machine=base.machine();entity=machine['entities'].pop(0)
        events=[event(entity,START-100),event(entity,START+100,'remove',present=False)]
        result=journal.machine_history(machine,events)
        restored=next(item for item in result['entities'] if item['unique_id']==entity['unique_id'])
        self.assertEqual(len(restored['registry_history']),2)

    def test_observation_gaps_are_scoped_to_their_machine(self):
        second_uid='b638b5a7-b54a-40a1-93e1-c3229483c984'
        scoped=journal.registry_events({}, {}, [{
            'action':'remove','entity_id':'sensor.missing','at':START,
            'system_uid':UID,
        }])[0]
        self.assertEqual(scoped['system_uid'],UID)
        sessions=[{'kind':'start','at':START-10},scoped,
                  {'kind':'observation_gap','at':START+1,'system_uid':second_uid},
                  {'kind':'observation_gap','at':START+2}]
        first=journal.machine_history(base.machine(),sessions)['journal_sessions']
        second=journal.machine_history(base.machine(second_uid,2),sessions)['journal_sessions']
        self.assertEqual([item['at'] for item in first],[START-10,START,START+2])
        self.assertEqual([item['at'] for item in second],[START-10,START+1,START+2])

    def test_journal_files_are_private_and_pruning_is_transactional(self):
        with tempfile.TemporaryDirectory() as directory:
            store=journal.RegistryJournal(Path(directory)/'registry.sqlite3')
            entity=base.machine()['entities'][0]
            records=store.append([
                event(entity,START-20),event(entity,START-10),event(entity,START+10),
                {'kind':'start','at':START-30},{'kind':'stop','at':START-15},
                {'kind':'start','at':START-5},
            ])
            os.chmod(store.path,0o644)
            store.read()
            self.assertEqual(store.path.stat().st_mode & 0o777,0o600)
            for suffix in ('-wal','-shm'):
                sidecar=Path(str(store.path)+suffix)
                sidecar.write_bytes(b'')
                os.chmod(sidecar,0o644)
            store._protect_files()
            self.assertTrue(all(
                Path(str(store.path)+suffix).stat().st_mode & 0o777 == 0o600
                for suffix in ('-wal','-shm')
            ))
            # Remove the fake sidecars before SQLite opens the database again.
            for suffix in ('-wal','-shm'):
                Path(str(store.path)+suffix).unlink()

            compacted=journal.compact_records(records,{UID:START},START)
            kept={item['at'] for item in compacted}
            self.assertEqual(kept,{START-10,START+10,START-5})
            removed=store.prune({item['event_id'] for item in compacted})
            self.assertEqual(removed,3)
            self.assertEqual(
                [item['event_id'] for item in store.read()],
                [item['event_id'] for item in compacted],
            )

    def test_compaction_never_prunes_a_system_without_a_cutoff(self):
        second_uid='b638b5a7-b54a-40a1-93e1-c3229483c984'
        first=event(base.machine()['entities'][0],START-10)
        second_entity=base.machine(second_uid,2)['entities'][0]
        second=event(second_entity,START-20)
        second['machine']={key:value for key,value in base.machine(second_uid,2).items() if key!='entities'}
        for sequence,item in enumerate((first,second,{'kind':'start','at':START-30}),1):
            item.update(sequence=sequence,event_id=f'event-{sequence}')
        compacted=journal.compact_records([first,second,{'kind':'start','at':START-30,
            'sequence':3,'event_id':'event-3'}],{UID:START},None)
        self.assertEqual(len(compacted),3)

    def test_compaction_retains_the_start_of_an_open_shutdown_gap(self):
        records=[
            {'kind':'start','at':START-30,'sequence':1,'event_id':'one'},
            {'kind':'stop','at':START-20,'sequence':2,'event_id':'two'},
            {'kind':'start','at':START+10,'sequence':3,'event_id':'three'},
        ]
        compacted=journal.compact_records(records,{},START)
        self.assertEqual([item['event_id'] for item in compacted],['one','two','three'])


class BackupPlatformTests(unittest.IsolatedAsyncioTestCase):
    async def test_backup_hooks_quiesce_flush_checkpoint_and_restore_all_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base_path=Path(directory)
            async def executor(function,*args): return function(*args)
            hass=SimpleNamespace(
                data={},
                config=SimpleNamespace(time_zone=WEEK.time_zone,path=lambda name:str(base_path/'live'/name)),
                async_add_executor_job=executor,
            )
            manager=base.manager_module.ArchiveManager(hass,'test')
            manager.initialized=True
            manager.statuses={UID:{'last_week':'2026-W35'}}
            manager.journal_pending=[{'kind':'start','at':START}]
            hass.data[base.manager_module.DATA_ARCHIVE_MANAGER]=manager

            await backup.async_pre_backup(hass)
            self.assertTrue(manager.backup_active)
            self.assertTrue(manager.lock.locked())
            self.assertTrue(manager.persistence_lock.locked())
            self.assertFalse(manager.journal_pending)
            self.assertEqual(len(manager.journal.read()),1)
            self.assertFalse(manager.journal.path.with_name(manager.journal.path.name+'-wal').exists())

            blocked=asyncio.create_task(manager.save_settings())
            await asyncio.sleep(0)
            self.assertFalse(blocked.done())
            snapshot=base_path/'snapshot'
            shutil.copytree(manager.root,snapshot)
            await backup.async_post_backup(hass)
            await blocked
            self.assertFalse(manager.backup_active)

            manager.journal.append([{'kind':'start','at':START+1}])
            restored=base_path/'restored'
            shutil.copytree(snapshot,restored)
            restored_settings=json.loads((restored/'settings.json').read_text())
            restored_journal=journal.RegistryJournal(restored/'registry.sqlite3').read()
            self.assertNotIn('enabled',restored_settings['systems'][UID])
            self.assertEqual(
                restored_settings['systems'][UID]['status']['last_week'],
                '2026-W35',
            )
            self.assertEqual(len(restored_journal),1)


class FileAndDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=base.DatabaseArchiveTests();self.fixture.setUp()
    def tearDown(self): self.fixture.tearDown()

    def test_gzip_is_one_standard_json_document_and_detects_payload_tampering(self):
        f=self.fixture; f.export()
        with gzip.open(f.path,'rt') as source: document=json.load(source)
        self.assertEqual(set(document),{'archive','entities','initial_states','changes'})
        self.assertEqual(len(document['initial_states']),3)
        text=gzip.decompress(f.path.read_bytes()).decode().replace('"state":"21"','"state":"99"',1)
        f.path.write_bytes(gzip.compress(text.encode()))
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)

    def test_startup_cleanup_only_removes_unpublished_archive_files(self):
        root=self.fixture.root/'archives';root.mkdir()
        machine_folder=files.machine_folder(root,UID);machine_folder.mkdir()
        root_pending=root/'.pending-settings';root_pending.write_text('partial')
        machine_pending=machine_folder/'.pending-week.json.gz';machine_pending.write_text('partial')
        published=machine_folder/f'{WEEK.key}.json.gz';published.write_text('keep')
        unrelated=root/'not-a-system';unrelated.mkdir()
        hidden=unrelated/'.pending-unrelated';hidden.write_text('keep')
        removed=files.cleanup_pending_files(root)
        self.assertEqual(set(removed),{root_pending,machine_pending})
        self.assertTrue(published.exists())
        self.assertTrue(hidden.exists())

    @staticmethod
    def _rewrite_with_valid_digest(path, document):
        digest=__import__('hashlib').sha256()
        entities='{"entities":'+json.dumps(document['entities'],ensure_ascii=False,separators=(',',':'))+',\n'
        initial='"initial_states":'+json.dumps(document['initial_states'],ensure_ascii=False,separators=(',',':'))+',\n'
        digest.update(entities.encode());digest.update(initial.encode())
        change_lines=[]
        for item in document['changes']:
            line=json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n'
            change_lines.append(line);digest.update(line.encode())
        metadata=document['archive']
        metadata['payload_sha256']=digest.hexdigest()
        metadata['change_count']=len(document['changes'])
        metadata['record_count']=len(document['changes'])+len(document['initial_states'])
        with gzip.open(path,'wt',encoding='utf-8',newline='\n') as output:
            output.write(entities);output.write(initial);output.write('"changes":[\n')
            for index,line in enumerate(change_lines): output.write((',' if index else '')+line)
            output.write('],\n"archive":'+json.dumps(metadata,ensure_ascii=False,separators=(',',':'))+'\n}\n')

    def _document(self):
        self.fixture.export()
        with gzip.open(self.fixture.path,'rt',encoding='utf-8') as source:
            return json.load(source)

    def test_writer_rejects_an_unsupported_record_kind_before_publication(self):
        f=self.fixture;document=self._document();target=f.root/'invalid.json.gz'
        records=[*document['initial_states'],*document['changes']]
        records[len(document['initial_states'])]['record_kind']='unsupported'
        with self.assertRaises(files.ArchiveError):
            files.write_archive(target,f.machine,WEEK,records,document['archive']['coverage'],created_at=NOW,
                integration_domain=base.TEST_DOMAIN,integration_version='test',recorder_schema_version=99)
        self.assertFalse(target.exists())

    def test_verifier_rejects_unsupported_kind_missing_field_and_wrong_type(self):
        f=self.fixture;baseline=self._document();document=deepcopy(baseline);document['changes'][0]['record_kind']='unsupported'
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)
        document=deepcopy(baseline);document['changes'][0]['attributes']=[]
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)
        document=deepcopy(baseline);del document['changes'][0]['entity_id']
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)

    def test_verifier_rejects_wrong_initial_time_and_non_chronological_changes(self):
        f=self.fixture;baseline=self._document();document=deepcopy(baseline);document['initial_states'][0]['at']+=1
        document['initial_states'][0]['at_utc']=files.utc_iso(document['initial_states'][0]['at'])
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)
        document=deepcopy(baseline)
        indexes=[index for index,item in enumerate(document['changes']) if item['unique_id']==document['changes'][0]['unique_id']]
        self.assertGreaterEqual(len(indexes),2)
        left,right=indexes[:2]
        document['changes'][left],document['changes'][right]=document['changes'][right],document['changes'][left]
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)

    def test_verifier_rejects_per_entity_count_mismatch(self):
        f=self.fixture;document=self._document();document['entities'][0]['states']+=1
        self._rewrite_with_valid_digest(f.path,document)
        with self.assertRaises(files.ArchiveError): files.verify_archive(f.path,UID,WEEK)

    def test_truncated_gzip_fails_crc_and_is_not_overwritten(self):
        f=self.fixture;f.export();truncated=f.path.read_bytes()[:-8];f.path.write_bytes(truncated)
        with self.assertRaises(files.ArchiveError): f.export()
        self.assertEqual(f.path.read_bytes(),truncated)

    def test_registry_change_during_export_prevents_publication(self):
        f=self.fixture
        with self.assertRaises(files.ArchiveError):
            base.recorder.export_recorder_week(f.hass,f.path,f.machine,WEEK,NOW,f.config,base.TEST_DOMAIN,'1.3.0',lambda:False)
        self.assertFalse(f.path.exists())
        self.assertFalse(list(f.root.glob('.pending-*')))

    def test_renamed_recorder_metadata_includes_original_week_rows(self):
        f=self.fixture;entity=f.machine['entities'][0]
        old=deepcopy(entity);entity['entity_id']='sensor.new_name'
        entity['registry_history']=[event(old,START-1000),event(entity,START+1000,'update',old)]
        with Session(f.engine) as session:
            session.get(base.StatesMeta,1).entity_id=entity['entity_id'];session.commit()
        f.export();rows=base.raw_records(f.path)
        self.assertEqual([item['state_id'] for item in rows],[1,2,3,4,5,6,8])
        self.assertEqual(rows[1]['entity_id'],old['entity_id'])

    def test_removed_entity_history_exported_from_journal(self):
        f=self.fixture;entity=f.machine['entities'].pop(0)
        f.machine=journal.machine_history(f.machine,[event(entity,START-1000),event(entity,START+300,'remove',present=False)])
        f.export();rows=base.raw_records(f.path)
        self.assertIn(2,[item['state_id'] for item in rows])
        with gzip.open(f.path,'rt') as source: document=json.load(source)
        self.assertTrue(any(item.get('event')=='remove' for item in document['changes']))

    def test_new_entities_after_requested_week_are_excluded(self):
        f=self.fixture;f.machine['entities'][0]['registry_created_at_utc']=files.utc_iso(WEEK.end+timedelta(hours=1))
        f.export()
        with gzip.open(f.path,'rt') as source: document=json.load(source)
        self.assertEqual(len(document['entities']),2)
        self.assertNotIn(2,[item['state_id'] for item in base.raw_records(f.path)])

    def test_low_retention_and_journal_gap_are_declared(self):
        f=self.fixture
        f.machine['journal_sessions']=[{'kind':'start','at':START-10},{'kind':'stop','at':START+10},
                                       {'kind':'start','at':START+20}]
        result=f.export();codes=[item['code'] for item in result['coverage']['warnings']]
        self.assertIn('retention_below_recommended_21_days',codes)
        self.assertIn('journal_observation_gap',codes)
        self.assertTrue(result['coverage']['first_or_partial_week'])

class ManagerCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=base.ManagerTests();await self.fixture.asyncSetUp()
        self.manager=self.fixture.manager;self.hass=self.fixture.hass
        self.hass.bus=SimpleNamespace(async_listen=Mock(return_value=lambda:None))
        self.hass.async_create_background_task=lambda coro,name:asyncio.create_task(coro)
    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def test_switch_source_controls_automatic_and_manual_exports(self):
        manager=self.manager;manager._request_run=Mock()
        coordinator=self.fixture.coordinators[UID]
        manager.attach_coordinator(coordinator)
        coordinator.set_enabled(False)
        result=await manager.run();self.assertFalse(result['archives']);self.assertTrue(result['skipped'])
        self.assertFalse((await manager.run(WEEK.key))['archives'])
        another=base.manager_module.ArchiveManager(self.hass,'1.3.0')
        another.statuses=another._load_settings()
        self.assertFalse(another.enabled(UID))
        coordinator.set_enabled(True);manager._request_run.assert_called_once()
        await manager.run();self.assertEqual(len(self.fixture.calls),1)

    async def test_config_form_enable_survives_coordinator_replacement(self):
        manager=self.manager;manager._request_run=Mock()
        coordinator=self.fixture.coordinators[UID]
        coordinator.set_enabled(False)
        manager.attach_coordinator(coordinator)
        manager.detach_coordinators([coordinator])

        replacement=base.ArchiveCoordinator(UID,enabled=True)
        self.fixture.coordinators[UID]=replacement
        manager.attach_coordinator(replacement)

        manager._request_run.assert_called_once()
        self.assertTrue(manager.coordinator_enabled_states[UID])
        self.assertFalse(coordinator.listeners)
        self.assertEqual(len(replacement.listeners),1)

    async def test_last_success_and_file_survive_no_work_run_and_restart(self):
        await self.manager.run()
        saved=deepcopy(self.manager.statuses[UID])
        await self.manager.run()
        self.assertEqual(self.manager.statuses[UID]['path'],saved['path'])
        statuses=self.manager._load_settings()
        self.assertEqual(statuses[UID],saved)
        self.assertIn('.json.gz',saved['path'])

    async def test_recorder_warning_does_not_change_global_settings(self):
        recorder=self.fixture.recorder;before=(recorder.keep_days,recorder.enabled)
        await self.manager.run()
        self.assertEqual((recorder.keep_days,recorder.enabled),before)
        self.assertTrue(self.manager.statuses[UID]['recorder_warnings'])
        self.assertTrue(any(call.args[2]=='archive_recorder' for call in base.issues.async_create_issue.call_args_list))

    async def test_recorder_exclusions_are_reported_per_machine(self):
        second_uid='b638b5a7-b54a-40a1-93e1-c3229483c984'
        first=base.machine();second=base.machine(second_uid,2)
        first['entities'][0]['recorded_now']=False
        second['entities'][1]['recorded_now']=False
        problems=self.manager.check_recorder([first,second],self.fixture.recorder)
        self.assertIn(first['entities'][0]['entity_id'],' '.join(problems[UID]))
        self.assertNotIn(second['entities'][1]['entity_id'],' '.join(problems[UID]))
        self.assertIn(second['entities'][1]['entity_id'],' '.join(problems[second_uid]))
        self.assertNotIn(first['entities'][0]['entity_id'],' '.join(problems[second_uid]))
        self.assertTrue(all('21' in ' '.join(items) for items in problems.values()))

    async def test_initial_observation_is_durable_and_shutdown_records_stop(self):
        self.manager.initialized=False
        await self.manager.initialize()
        records=self.manager.journal.read()
        self.assertEqual(records[0]['kind'],'start')
        self.assertEqual(sum(item['kind']=='observe' for item in records),3)
        await self.manager.stop()
        self.assertEqual(self.manager.journal.read()[-1]['kind'],'stop')

    async def test_restart_absence_gets_a_fresh_journal_event_identity(self):
        entity=base.machine()['entities'][0]
        previous=self.manager.journal.append([event(entity,START)])[0]
        current=base.machine()
        current['entities']=current['entities'][1:]
        base.manager_module.collect_machines.return_value=[current]
        self.manager.initialized=False

        await self.manager.initialize()

        observations=[item for item in self.manager.journal.read()
            if item.get('entity',{}).get('unique_id')==entity['unique_id']]
        self.assertEqual(len(observations),2)
        self.assertNotEqual(observations[-1]['event_id'],previous['event_id'])
        self.assertFalse(observations[-1]['entity']['present'])
        self.assertEqual(observations[-1]['before'],previous['entity'])

    async def test_shutdown_task_failure_cannot_skip_stop_observation(self):
        release=asyncio.Event()
        async def fail():
            await release.wait()
            raise RuntimeError('worker failed')
        self.manager.task=asyncio.create_task(fail())
        stopping=asyncio.create_task(self.manager.stop())
        await asyncio.sleep(0)
        release.set()
        with self.assertLogs(base.manager_module._LOGGER,level='ERROR'):
            await stopping
        self.assertEqual(self.manager.journal.read()[-1]['kind'],'stop')

    async def test_shutdown_timeout_is_bounded_and_records_global_gap(self):
        release=asyncio.Event()
        self.manager.task=asyncio.create_task(release.wait())
        with patch.object(base.manager_module,'STOP_WAIT_TIMEOUT_SECONDS',0.01):
            with self.assertLogs(base.manager_module._LOGGER,level='ERROR'):
                await self.manager.stop()
        saved=self.manager.journal.read()[-1]
        self.assertEqual(saved['kind'],'observation_gap')
        self.assertNotIn('system_uid',saved)
        self.manager.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.manager.task

    async def test_prune_cutoff_waits_for_progress_and_oldest_failed_week(self):
        second_uid='b638b5a7-b54a-40a1-93e1-c3229483c984'
        files.save_progress(self.manager.root/UID,WEEK.following().following())
        records=[
            {'kind':'observe','at':START,'machine':{'system_uid':UID}},
            {'kind':'observe','at':START,'machine':{'system_uid':second_uid}},
        ]
        cutoffs,global_cutoff=base.manager_module._journal_prune_cutoffs(
            self.manager.root,{UID:{'failed_weeks':[WEEK.key]}},WEEK.time_zone,
            WEEK.following(),records,{UID,second_uid})
        self.assertEqual(cutoffs[UID],WEEK.start.timestamp())
        self.assertNotIn(second_uid,cutoffs)
        self.assertIsNone(global_cutoff)

        files.save_progress(self.manager.root/second_uid,WEEK.following())
        cutoffs,global_cutoff=base.manager_module._journal_prune_cutoffs(
            self.manager.root,{UID:{'failed_weeks':[WEEK.key]}},WEEK.time_zone,
            WEEK.following(),records,{UID,second_uid})
        self.assertEqual(global_cutoff,WEEK.start.timestamp())

    async def test_manager_compacts_only_after_durable_progress(self):
        entity=base.machine()['entities'][0]
        self.manager.journal_records=self.manager.journal.append([
            event(entity,START),event(entity,START+1),event(entity,START+2),
            {'kind':'start','at':START-1},
        ])
        files.save_progress(self.manager.root/UID,WEEK.following())
        await self.manager._compact_journal(WEEK,{UID})
        self.assertEqual(len(self.manager.journal_records),2)
        self.assertEqual(self.manager.journal.read(),self.manager.journal_records)
        self.assertEqual(
            [item['at'] for item in self.manager.journal_records],
            [START+2,START-1],
        )

    async def test_disk_failure_keeps_journal_events_for_retry(self):
        self.manager.journal_pending=[{'kind':'start','at':START}]
        with patch.object(self.manager.journal,'append',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): await self.manager.flush_journal()
        self.assertEqual(len(self.manager.journal_pending),1)
        await self.manager.flush_journal()
        self.assertFalse(self.manager.journal_pending)
        self.assertEqual(len(self.manager.journal.read()),1)

    async def test_real_registry_callbacks_keep_disable_then_remove_in_one_burst(self):
        machines=[base.machine()]
        base.manager_module.collect_machines.side_effect=lambda *args,**kwargs:deepcopy(machines)
        await self.manager.initialize()
        entity=machines[0]['entities'].pop(0);name=entity['entity_id']
        deleted=SimpleNamespace(entity_id=name,platform=base.TEST_DOMAIN,unique_id=entity['unique_id'],
                                disabled_by='user',name='Removed',id='registry_id',created_at=WEEK.start-timedelta(days=1))
        self.hass.entities=SimpleNamespace(async_get=lambda name:None,deleted_entities={name:deleted})
        for action,at,changes in [('update',START+10,{'disabled_by':None}),('remove',START+20,{})]:
            self.manager.registry_changed(SimpleNamespace(data={'action':action,'entity_id':name,'changes':changes},
                                                          time_fired=WEEK.start+timedelta(seconds=at-START)))
        await self.manager.journal_task
        changes=[item for item in self.manager.journal.read() if item['kind'] in ('update','remove')]
        self.assertEqual([item['kind'] for item in changes],['update','remove'])
        self.assertEqual(changes[0]['entity']['disabled_by_now'],'user')
        self.assertFalse(changes[1]['entity']['present'])

    async def test_remove_a_reuse_id_by_b_remove_b_prefers_latest_observation(self):
        first_uid=UID;second_uid='b638b5a7-b54a-40a1-93e1-c3229483c984'
        entity_id='sensor.reused'
        def deleted(uid,identifier):
            return SimpleNamespace(entity_id=entity_id,platform=base.TEST_DOMAIN,unique_id=uid+'_temperature',
                config_entry_id='hub',config_subentry_id='sub-'+identifier,device_id=identifier,
                disabled_by=None,name=identifier,id=identifier,
                created_at=WEEK.start-timedelta(days=1))
        first=deleted(first_uid,'first');second=deleted(second_uid,'second')
        first_snapshot={
            'machine':{'system_uid':first_uid,'device_id':'first','name':'First','hub_uid':'hub-uid',
                       'config_entry_id':'hub','config_subentry_id':'sub-first',
                       'system_id':'first','source_system_id':'source-first'},
            'entity':{'entity_key':'temperature','unique_id':first.unique_id,'entity_id':entity_id,
                      'translation_key':'temperature','unit_of_measurement_now':'°C','recorded_now':True},
        }
        second_machine={'system_uid':second_uid,'device_id':'second','name':'Second','hub_uid':'hub-uid',
            'config_entry_id':'hub','config_subentry_id':'sub-second','system_id':'second',
            'source_system_id':'source-second','entities':[{
                'entity_key':'temperature','unique_id':second.unique_id,'entity_id':entity_id,
                'translation_key':'temperature','unit_of_measurement_now':'°C','recorded_now':True,
            }]}
        self.manager.registry_cache={entity_id:first_snapshot}
        current=[second]
        self.hass.entities=SimpleNamespace(async_get=lambda name:current[0],
            deleted_entities={first.unique_id:first,second.unique_id:second})
        base.manager_module.collect_machines.side_effect=lambda *args,**kwargs:deepcopy(
            [second_machine] if current[0] else [])

        # B is created with A's former entity_id and removed again before the
        # background journal worker has had an event-loop turn.
        for action,at in [('create',START+10),('remove',START+20)]:
            self.manager.registry_changed(SimpleNamespace(
                data={'action':action,'entity_id':entity_id,'changes':{}},
                time_fired=WEEK.start+timedelta(seconds=at-START)))
            if action == 'create':
                current[0]=None
        await self.manager.journal_task
        changes=[item for item in self.manager.journal.read() if item['kind'] in ('create','remove')]
        self.assertEqual([item['kind'] for item in changes],['create','remove'])
        self.assertTrue(all(item['entity']['unique_id']==second.unique_id for item in changes))
        self.assertEqual(changes[-1]['entity']['registry_id'],'second')

    async def test_absent_machine_administration_waits_for_first_fully_observed_week(self):
        (self.manager.root/UID/'progress.json').unlink()
        manager=base.manager_module.ArchiveManager(self.hass,'1.3.2')
        manager.initialized=True
        result=await manager.run()
        self.assertFalse(self.fixture.calls)
        self.assertEqual(manager.statuses[UID]['archive_start_week'],'2026-W37')
        self.assertEqual(result['skipped'][0]['reason'],'awaiting_first_full_week')
        manual=await manager.run(WEEK.key)
        self.assertEqual(manual['skipped'][0]['reason'],'before_archive_start')

    async def test_poison_week_is_recorded_while_newer_weeks_continue(self):
        self.fixture.mocktime.now.return_value=NOW+timedelta(weeks=3)
        files.save_progress(self.manager.root/UID,WEEK)
        def export(hass,path,machine,week,*args):
            self.fixture.calls.append((machine['system_uid'],week.key))
            if week.key==WEEK.key:
                raise OSError('permanent row/identity error')
            return {'record_count':2,'coverage':{'warnings':[]}}
        base.manager_module.export_recorder_week.side_effect=export
        with self.assertLogs(base.manager_module._LOGGER,level='ERROR'):
            result=await self.manager.run()
        self.assertEqual([week for _,week in self.fixture.calls],
                         ['2026-W35','2026-W36','2026-W37','2026-W38'])
        self.assertEqual(files.load_progress(self.manager.root/UID,WEEK).key,'2026-W39')
        self.assertEqual(self.manager.statuses[UID]['failed_weeks'],['2026-W35'])
        self.assertEqual(len(result['archives']),3)
        self.assertTrue(result['more_pending'])

    async def test_registry_added_while_initial_journal_is_loading_is_not_lost(self):
        machines=[base.machine()]
        base.manager_module.collect_machines.side_effect=lambda *args,**kwargs:deepcopy(machines)
        self.hass.entities=SimpleNamespace(async_get=lambda name:SimpleNamespace(platform=base.TEST_DOMAIN))
        original=self.manager.journal.read
        def load_and_add():
            result=original()
            entity={**machines[0]['entities'][0],'unique_id':UID+'_extra','entity_id':'sensor.extra','entity_key':'extra'}
            machines[0]['entities'].append(entity)
            self.manager.registry_changed(SimpleNamespace(data={'action':'create','entity_id':'sensor.extra'},time_fired=NOW))
            return result
        self.manager.initialized=False
        with patch.object(self.manager.journal,'read',side_effect=load_and_add):
            await self.manager.initialize()
        records=self.manager.journal.read()
        created=[item for item in records if item['kind']=='create']
        self.assertEqual(len(created),1)
        self.assertEqual(created[0]['entity']['unique_id'],UID+'_extra')

    async def test_archive_settings_do_not_duplicate_the_switch_value(self):
        await self.manager.run()
        document=json.loads(
            (self.manager.root/'settings.json').read_text()
        )
        self.assertEqual(document['format_version'],2)
        self.assertNotIn('enabled',document['systems'][UID])

    async def test_archive_values_use_the_generic_coordinator_contract(self):
        coordinator=self.fixture.coordinators[UID]
        self.manager.attach_coordinator(coordinator)
        self.assertEqual(
            coordinator.external_values['archive_status'].value,
            'waiting',
        )
        self.assertIsNone(
            coordinator.external_values['archive_last_success'].value
        )
        await self.manager.run()
        status=coordinator.external_values['archive_status']
        self.assertEqual(status.value,'warning')
        self.assertIn('.json.gz',status.attributes['path'])
        self.assertIsNotNone(
            coordinator.external_values['archive_last_success'].value
        )
        coordinator.set_enabled(False)
        self.assertEqual(
            coordinator.external_values['archive_status'].value,
            'disabled',
        )
        self.manager.detach_coordinators([coordinator])
        self.assertFalse(coordinator.listeners)
