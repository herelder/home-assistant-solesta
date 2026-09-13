"""Automatic weekly export and an on-demand action for Solesta machines."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from uuid import UUID

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.start import async_at_started
from homeassistant.loader import async_get_integration

from .archive_files import (
    ARCHIVE_FOLDER, ArchiveError, ArchiveWeek, _atomic_json, archive_path,
    cleanup_pending_files, latest_due_week, first_full_week_after, load_progress,
    machine_folder, next_weekly_run, save_progress,
)
from .archive_recorder import export_recorder_week
from .archive_journal import (
    RegistryJournal, compact_records, machine_history, registry_events, registry_snapshot,
)
from .const import (
    ARCHIVE_LAST_SUCCESS_ENTITY_KEY,
    ARCHIVE_STATUS_ENTITY_KEY,
    CONF_SOURCE_SYSTEM_ID,
    CONF_SYSTEM_ID,
    DOMAIN,
    DATA_ARCHIVE_MANAGER,
    SYSTEM_SUBENTRY_TYPES,
    WEEKLY_ARCHIVE_ENTITY_KEY,
)
from .external_value import ExternalEntityValue

_LOGGER = logging.getLogger(__name__)
SERVICE_ARCHIVE_WEEK = 'archive_week'
MAX_CATCHUP_WEEKS = 4
STOP_WAIT_TIMEOUT_SECONDS = 300
STOP_FLUSH_TIMEOUT_SECONDS = 30


def _journal_prune_cutoffs(
    root: Path,
    statuses: dict,
    time_zone: str,
    latest: ArchiveWeek,
    records: list[dict],
    current_system_uids: set[str],
) -> tuple[dict[str, float], float | None]:
    """Return cutoffs proven safe by durable progress and failed-week ledgers."""
    journal_system_uids = {
        system_uid
        for item in records
        if (system_uid := (
            item.get('machine', {}).get('system_uid')
            if isinstance(item.get('machine'), dict)
            else item.get('system_uid')
        )) is not None
    }
    all_system_uids = journal_system_uids | current_system_uids
    cutoffs = {}
    latest_safe = latest.following().start.timestamp()
    for system_uid in all_system_uids:
        folder = machine_folder(root, system_uid)
        if not (folder / 'progress.json').is_file():
            continue
        pending = load_progress(folder, latest)
        weeks = [pending]
        for key in statuses.get(system_uid, {}).get('failed_weeks', []):
            weeks.append(ArchiveWeek.from_key(key, time_zone))
        cutoffs[system_uid] = min(
            min(week.start.timestamp() for week in weeks),
            latest_safe,
        )
    global_cutoff = (
        min(cutoffs.values())
        if all_system_uids and all_system_uids.issubset(cutoffs)
        else None
    )
    return cutoffs, global_cutoff


def collect_machines(hass: HomeAssistant, device_id: str | None = None, *, include_disabled: bool = False) -> list[dict]:
    """Take registry/config snapshots on the event loop; never export credentials."""
    recorder = get_instance(hass)
    entries = {entry.entry_id: entry for entry in hass.config_entries.async_entries(DOMAIN)
               if include_disabled or entry.disabled_by is None}
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    machines = {}
    for entity in entities.entities.values():
        if entity.platform != DOMAIN or entity.config_entry_id not in entries:
            continue
        if device_id is not None and entity.device_id != device_id:
            continue
        device = devices.async_get(entity.device_id) if entity.device_id else None
        if device is None:
            continue
        identifiers = [uid for domain, uid in device.identifiers if domain == DOMAIN]
        if len(identifiers) != 1:
            continue
        try:
            uid = str(UUID(identifiers[0]))
        except (ValueError, TypeError):
            continue
        prefix = f'{uid}_'
        if not entity.unique_id.startswith(prefix):
            continue
        entry = entries[entity.config_entry_id]
        subentry = next((sub for sub in entry.subentries.values()
                         if sub.subentry_type in SYSTEM_SUBENTRY_TYPES
                         if sub.unique_id == uid), None)
        if uid not in machines:
            machines[uid] = {
                'system_uid': uid, 'device_id': device.id,
                'name': device.name_by_user or device.name,
                'hub_uid': entry.unique_id, 'config_entry_id': entry.entry_id,
                'config_subentry_id': (getattr(subentry, 'subentry_id', None) if subentry
                                       else getattr(entity, 'config_subentry_id', None)),
                'system_id': subentry.data.get(CONF_SYSTEM_ID) if subentry else None,
                'source_system_id': subentry.data.get(CONF_SOURCE_SYSTEM_ID) if subentry else None,
                'entities': [],
            }
        machines[uid]['entities'].append({
            'entity_key': entity.unique_id[len(prefix):],
            'registry_id': getattr(entity, 'id', None),
            'name': getattr(entity, 'name', None),
            'original_name': getattr(entity, 'original_name', None),
            'device_class': getattr(entity, 'device_class', None),
            'original_device_class': getattr(entity, 'original_device_class', None),
            'present': True,
            'entity_id': entity.entity_id,
            'unique_id': entity.unique_id,
            'translation_key': entity.translation_key,
            'platform': entity.domain,
            'disabled_by_now': entity.disabled_by,
            'unit_of_measurement_now': entity.unit_of_measurement,
            'recorded_now': (recorder.entity_filter is None or recorder.entity_filter(entity.entity_id))
                            and 'state_changed' not in recorder.exclude_event_types,
            'registry_created_at_utc': entity.created_at.isoformat(),
        })
    for machine in machines.values():
        machine['entities'].sort(key=lambda entity: entity['entity_key'])
    return sorted(machines.values(), key=lambda machine: machine['system_uid'])


class ArchiveManager:
    def __init__(self, hass: HomeAssistant, version: str) -> None:
        self.hass = hass
        self.version = version
        self.root = Path(hass.config.path(ARCHIVE_FOLDER)) / DOMAIN
        self.lock = asyncio.Lock()
        self.stopping = False
        self.task = None
        self.running_task = None
        self.cancel_timer = None
        self.cancel_start = None
        self.journal = RegistryJournal(self.root / 'registry.sqlite3')
        self.journal_records = []
        self.journal_pending = []
        self.registry_pending = []
        self.registry_cache = {}
        self.journal_lock = asyncio.Lock()
        self.settings_lock = asyncio.Lock()
        self.persistence_lock = asyncio.Lock()
        self.backup_active = False
        self.journal_task = None
        self.cancel_registry = None
        self.initialized = False
        self.registry_revision = 0
        self.statuses = {}
        self.coordinator_unsubscribers = {}
        self.coordinator_enabled_states = {}

    async def initialize(self) -> None:
        # Snapshot and subscribe without yielding; changes during disk loading
        # are buffered and replayed after the initial observation.
        baseline = registry_snapshot(collect_machines(self.hass, include_disabled=True))
        observed = datetime.now(timezone.utc).timestamp()
        self.registry_cache = baseline
        self.cancel_registry = self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self.registry_changed)
        try:
            removed = await self.hass.async_add_executor_job(cleanup_pending_files, self.root)
            if removed:
                _LOGGER.info('Removed %d unpublished archive temporary file(s)', len(removed))
            self.journal_records = await self.hass.async_add_executor_job(self.journal.read)
            self.statuses = await self.hass.async_add_executor_job(self._load_settings)
            prior = {}
            for item in self.journal_records:
                if 'entity' in item:
                    prior[item['entity']['unique_id']] = item
            self.journal_pending.append({'kind': 'start', 'at': observed})
            seen = set()
            for item in baseline.values():
                uid = item['entity']['unique_id']
                seen.add(uid)
                event = {**deepcopy(item), 'kind': 'observe', 'at': observed}
                if uid in prior:
                    event['before'] = prior[uid]['entity']
                self.journal_pending.append(event)
            for uid, item in prior.items():
                if uid not in seen and item['entity'].get('present', True):
                    # Disappearance while HA was off: only its observation
                    # time is known, never claim that was the removal time.
                    event = deepcopy(item)
                    # sequence and event_id identify the durable old record;
                    # this observation is a new event for the same entity.
                    event.pop('sequence', None)
                    event.pop('event_id', None)
                    event.update(
                        kind='observe',
                        at=observed,
                        before=item['entity'],
                        entity={**item['entity'], 'present': False},
                    )
                    self.journal_pending.append(event)
            self.initialized = True
            await self.flush_journal()
        except Exception:
            self.initialized = False
            if self.cancel_registry:
                self.cancel_registry()
                self.cancel_registry = None
            raise

    def _load_settings(self):
        path = self.root / 'settings.json'
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('format_version') not in (1, 2) or not isinstance(data.get('systems'), dict):
            raise ArchiveError('Invalid archive settings file')
        statuses = {}
        for uid, item in data['systems'].items():
            machine_folder(self.root, uid)
            if not isinstance(item, dict) or not isinstance(item.get('status', {}), dict):
                raise ArchiveError('Invalid per-system archive setting')
            statuses[uid] = item.get('status', {})
        return statuses

    async def _save_settings_locked(self) -> None:
        systems = {
            uid: {'status': deepcopy(status)}
            for uid, status in self.statuses.items()
        }
        await self._executor(self.hass.async_add_executor_job, _atomic_json,
                            self.root / 'settings.json', {'format_version': 2, 'systems': systems})

    async def save_settings(self) -> None:
        async with self.persistence_lock:
            async with self.settings_lock:
                await self._save_settings_locked()

    def enabled(self, uid: str) -> bool:
        coordinator = self._coordinator(uid)
        if coordinator is None or coordinator.data is None:
            return False
        return coordinator.data.get(WEEKLY_ARCHIVE_ENTITY_KEY) is True

    @callback
    def _coordinator(self, uid):
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            runtime = getattr(entry, 'runtime_data', None)
            coordinator = getattr(runtime, 'coordinators', {}).get(uid)
            if coordinator is not None:
                return coordinator
        return None

    @callback
    def attach_coordinator(self, coordinator):
        uid = coordinator.runtime.system_uid
        old_unsubscribe = self.coordinator_unsubscribers.pop(uid, None)
        if old_unsubscribe is not None:
            old_unsubscribe()
        previous = self.coordinator_enabled_states.get(uid)
        enabled = self.enabled(uid)
        self.coordinator_enabled_states[uid] = enabled

        @callback
        def coordinator_updated():
            enabled = self.enabled(uid)
            previous = self.coordinator_enabled_states.get(uid, False)
            self.coordinator_enabled_states[uid] = enabled
            self.notify(uid)
            if enabled and not previous:
                self._request_run()

        self.coordinator_unsubscribers[uid] = coordinator.async_add_listener(
            coordinator_updated
        )
        self.notify(uid)
        # System reconfiguration replaces its coordinator. Retain the last
        # observed switch value across that replacement so an off-to-on change
        # made in the config form still starts an immediate archive run.
        if enabled and previous is False:
            self._request_run()

    @callback
    def detach_coordinators(self, coordinators):
        for coordinator in coordinators:
            uid = coordinator.runtime.system_uid
            unsubscribe = self.coordinator_unsubscribers.pop(uid, None)
            if unsubscribe is not None:
                unsubscribe()

    @callback
    def notify(self, uid=None):
        targets = ([uid] if uid is not None else [
            coordinator.runtime.system_uid
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if (runtime := getattr(entry, 'runtime_data', None)) is not None
            for coordinator in getattr(runtime, 'coordinators', {}).values()
        ])
        for system_uid in targets:
            coordinator = self._coordinator(system_uid)
            if coordinator is None:
                continue
            status = self.statuses.get(system_uid, {})
            if not self.enabled(system_uid):
                state = 'disabled'
            elif status.get('last_error'):
                state = 'error'
            elif status.get('recorder_warnings') or status.get('coverage_warning_count'):
                state = 'warning'
            else:
                state = 'ok' if status.get('last_success_utc') else 'waiting'
            dropped = coordinator.runtime.configuration.dropped_keys
            values = {}
            if ARCHIVE_LAST_SUCCESS_ENTITY_KEY in dropped:
                values[ARCHIVE_LAST_SUCCESS_ENTITY_KEY] = ExternalEntityValue(
                    status.get('last_success_utc'), {}
                )
            if ARCHIVE_STATUS_ENTITY_KEY in dropped:
                values[ARCHIVE_STATUS_ENTITY_KEY] = ExternalEntityValue(
                    state,
                    {
                        key: status.get(key)
                        for key in (
                            'week', 'path', 'record_count',
                            'coverage_warning_count', 'recorder_warnings',
                            'last_error', 'last_success_utc', 'failed_weeks',
                            'archive_start_week',
                        )
                    },
                )
            coordinator.async_set_external_entity_values(values)

    def removed_snapshot(self, entity_id):
        registry = er.async_get(self.hass)
        candidates = [entity for entity in getattr(registry, 'deleted_entities', {}).values()
                      if entity.entity_id == entity_id and entity.platform == DOMAIN]
        # A create and remove can occur before the journal worker gets a turn.
        # Prefer that most recent observed identity over the older durable
        # cache, otherwise entity-id reuse can attach the removal to its former
        # owner.
        cached = next(
            (deepcopy(event['observed_snapshot']) for event in reversed(self.registry_pending)
             if event.get('entity_id') == entity_id and event.get('observed_snapshot') is not None),
            deepcopy(self.registry_cache.get(entity_id)),
        )
        if cached is not None:
            # HA can retain more than one deleted registry entry with the same
            # entity_id. The live cache is the observation immediately before
            # removal and therefore owns the stable identity for this event.
            expected = cached['entity']['unique_id']
            expected_entry = cached['machine'].get('config_entry_id')
            expected_subentry = cached['machine'].get('config_subentry_id')
            expected_device = cached['machine'].get('device_id')
            matching = [entity for entity in candidates
                        if entity.unique_id == expected
                        and (expected_entry is None
                             or getattr(entity, 'config_entry_id', None) == expected_entry)
                        and (expected_subentry is None
                             or getattr(entity, 'config_subentry_id', None) == expected_subentry)
                        and (expected_device is None
                             or getattr(entity, 'device_id', None) == expected_device)]
            if len(matching) > 1:
                return None
            deleted = matching[0] if matching else None
            result = cached
            if deleted is not None:
                result['entity'].update(entity_id=entity_id, disabled_by_now=deleted.disabled_by,
                    name=deleted.name, present=True, registry_id=deleted.id,
                    platform=entity_id.split('.')[0], registry_created_at_utc=deleted.created_at.isoformat())
            return result
        if len(candidates) != 1:
            # With no pre-removal observation, choosing one of several deleted
            # identities would fabricate ownership. registry_events records a
            # coverage gap when it can establish that this was our platform.
            return None
        deleted = candidates[0]
        template = next((item for item in self.registry_cache.values()
                         if item['entity']['unique_id'] == deleted.unique_id), None)
        if template is None:
            # A new entity can be registered and removed in the same event-loop
            # turn. HA's deleted entry still supplies its permanent identity.
            try:
                uid = str(UUID(deleted.unique_id[:36]))
                if not deleted.unique_id.startswith(uid + '_'):
                    return None
            except (ValueError, TypeError):
                return None
            entry = next((item for item in self.hass.config_entries.async_entries(DOMAIN)
                          if item.entry_id == deleted.config_entry_id), None)
            if entry is None:
                return None
            subentry = next((item for item in entry.subentries.values()
                             if item.subentry_type in SYSTEM_SUBENTRY_TYPES
                             if item.unique_id == uid), None)
            device = next((item for item in dr.async_get(self.hass).devices.values()
                           if (DOMAIN, uid) in item.identifiers), None)
            template = {'machine': {'system_uid': uid, 'device_id': device.id if device else None,
                         'name': (device.name_by_user or device.name) if device else (subentry.title if subentry else uid),
                         'hub_uid': entry.unique_id, 'config_entry_id': entry.entry_id,
                         'config_subentry_id': getattr(deleted, 'config_subentry_id', None),
                         'system_id': subentry.data.get(CONF_SYSTEM_ID) if subentry else None,
                         'source_system_id': subentry.data.get(CONF_SOURCE_SYSTEM_ID) if subentry else None},
                        'entity': {'entity_key': deleted.unique_id[37:], 'unique_id': deleted.unique_id,
                                   'translation_key': None, 'unit_of_measurement_now': None, 'recorded_now': None}}
        result = deepcopy(template)
        result['entity'].update(entity_id=entity_id, disabled_by_now=deleted.disabled_by,
            name=deleted.name, present=True, registry_id=deleted.id,
            platform=entity_id.split('.')[0], registry_created_at_utc=deleted.created_at.isoformat())
        return result

    @callback
    def registry_changed(self, event):
        data = event.data
        entity_id = data['entity_id']
        old_id = data.get('old_entity_id', entity_id)
        current = er.async_get(self.hass).async_get(entity_id)
        observed = None
        if current is not None and current.platform == DOMAIN:
            observed = registry_snapshot(collect_machines(self.hass, include_disabled=True)).get(entity_id)
        removed = self.removed_snapshot(entity_id) if current is None else None
        if old_id not in self.registry_cache and removed is None and (current is None or current.platform != DOMAIN):
            return
        # Only plain metadata is retained; no provider settings or credentials.
        self.registry_revision += 1
        context = observed or removed or self.registry_cache.get(old_id)
        system_uid = context.get('machine', {}).get('system_uid') if context else None
        self.registry_pending.append({'action': data['action'], 'entity_id': entity_id,
            'old_entity_id': old_id, 'changes': {key: value for key, value in data.get('changes', {}).items()
                                               if key in ('entity_id', 'disabled_by', 'name', 'original_name',
                                                          'unit_of_measurement', 'device_class', 'original_device_class')},
            'at': event.time_fired.timestamp(), 'observed_snapshot': observed,
            'removed_snapshot': removed or deepcopy(self.registry_cache.get(old_id)),
            'system_uid': system_uid})
        if self.initialized and (self.journal_task is None or self.journal_task.done()):
            self.journal_task = self.hass.async_create_background_task(self._journal_worker(), f'{DOMAIN} registry journal')

    async def _journal_worker(self):
        try:
            await self.flush_journal()
        except Exception as err:
            _LOGGER.exception('Registry journal could not be saved; retaining pending events for retry')
            for machine in collect_machines(self.hass):
                self.statuses.setdefault(machine['system_uid'], {})['last_error'] = str(err)
            self.notify()
            self.report_failure()
            self.schedule_next(retry=True)

    async def _flush_journal_locked(self):
        async with self.journal_lock:
            while self.registry_pending or self.journal_pending:
                if self.registry_pending:
                    events, self.registry_pending = self.registry_pending, []
                    current = registry_snapshot(collect_machines(self.hass, include_disabled=True))
                    self.journal_pending.extend(registry_events(self.registry_cache, current, events))
                    self.registry_cache = current
                batch = list(self.journal_pending)
                if not batch:
                    continue
                saved = await self._executor(self.hass.async_add_executor_job, self.journal.append, batch)
                existing = {item['sequence'] for item in self.journal_records}
                self.journal_records.extend(item for item in saved if item['sequence'] not in existing)
                del self.journal_pending[:len(batch)]

    async def flush_journal(self):
        async with self.persistence_lock:
            await self._flush_journal_locked()

    async def begin_backup(self) -> None:
        """Quiesce all archive persistence until Home Assistant ends its backup."""
        if self.backup_active:
            return
        await self.lock.acquire()
        try:
            await self.persistence_lock.acquire()
            try:
                if self.initialized:
                    await self._flush_journal_locked()
                async with self.settings_lock:
                    await self._save_settings_locked()
                await self._executor(
                    self.hass.async_add_executor_job,
                    self.journal.checkpoint,
                )
                self.backup_active = True
            except BaseException:
                self.persistence_lock.release()
                raise
        except BaseException:
            self.lock.release()
            raise

    def end_backup(self) -> None:
        """Release the persistence barrier held by begin_backup."""
        if not self.backup_active:
            return
        self.backup_active = False
        self.persistence_lock.release()
        self.lock.release()

    @callback
    def check_recorder(self, machines, recorder):
        global_problems = []
        if recorder.auto_purge and recorder.keep_days < 21:
            global_problems.append(f'Recorder bewaart {recorder.keep_days} dagen; aanbevolen: minstens 21.')
        if not recorder.enabled:
            global_problems.append('Recorder is uitgeschakeld.')
        problems_by_system = {}
        issue_details = list(global_problems)
        for machine in machines:
            excluded = [
                entity['entity_id'] for entity in machine['entities']
                if entity.get('recorded_now') is False
            ]
            specific = (
                ['Niet opgenomen in Recorder: ' + ', '.join(excluded)]
                if excluded else []
            )
            problems_by_system[machine['system_uid']] = global_problems + specific
            if specific:
                issue_details.append(f"{machine['name']}: {specific[0]}")
        if issue_details:
            ir.async_create_issue(self.hass, DOMAIN, 'archive_recorder', is_fixable=False,
                severity=ir.IssueSeverity.WARNING, translation_key='archive_recorder',
                translation_placeholders={'details': ' '.join(issue_details)})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, 'archive_recorder')
        return problems_by_system

    @callback
    def start(self, _hass: HomeAssistant) -> None:
        self._request_run()

    @callback
    def _request_run(self, _now: datetime | None = None) -> None:
        if self.stopping or (self.task is not None and not self.task.done()):
            return
        self.task = self.hass.async_create_background_task(self._automatic_run(), f'{DOMAIN} week archive')

    async def stop(self, _event=None) -> None:
        stopped_at = datetime.now(timezone.utc).timestamp()
        self.stopping = True
        for unsubscribe in tuple(self.coordinator_unsubscribers.values()):
            unsubscribe()
        self.coordinator_unsubscribers.clear()
        self.coordinator_enabled_states.clear()
        if self.cancel_start:
            self.cancel_start()
        if self.cancel_timer:
            self.cancel_timer()
        if self.cancel_registry:
            self.cancel_registry()
        current = asyncio.current_task()
        tasks = {task for task in (self.task, self.running_task, self.journal_task)
                 if task is not None and task is not current and not task.done()}
        incomplete = False
        cancelled = None
        try:
            if tasks:
                done, pending = await asyncio.wait(
                    tasks,
                    timeout=STOP_WAIT_TIMEOUT_SECONDS,
                )
                incomplete = bool(pending)
                for task in done:
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        _LOGGER.warning('Archive task was cancelled while Home Assistant stopped')
                    except Exception as err:
                        _LOGGER.error(
                            'Archive task ended with an error while Home Assistant stopped',
                            exc_info=(type(err), err, err.__traceback__),
                        )
                if pending:
                    _LOGGER.error(
                        'Timed out after %d seconds waiting for %d archive task(s) during shutdown',
                        STOP_WAIT_TIMEOUT_SECONDS,
                        len(pending),
                    )
        except asyncio.CancelledError as err:
            incomplete = True
            cancelled = err
        finally:
            if self.initialized:
                observation = {
                    'kind': 'observation_gap' if incomplete else 'stop',
                    'at': stopped_at,
                }
                if incomplete:
                    observation['reason'] = 'archive_shutdown_incomplete'
                self.journal_pending.append(observation)
                try:
                    async with asyncio.timeout(STOP_FLUSH_TIMEOUT_SECONDS):
                        await asyncio.shield(self.flush_journal())
                except TimeoutError:
                    _LOGGER.error('Timed out while saving the archive shutdown observation')
                except Exception:
                    _LOGGER.exception('Could not save the archive shutdown observation')
        if cancelled is not None:
            raise cancelled

    async def _compact_journal(self, latest: ArchiveWeek, current_system_uids: set[str]) -> None:
        """Compact only history older than every still-unpublished week."""
        if self.stopping:
            return
        try:
            cutoffs, global_cutoff = await self._executor(
                self.hass.async_add_executor_job,
                _journal_prune_cutoffs,
                self.root,
                deepcopy(self.statuses),
                self.hass.config.time_zone,
                latest,
                list(self.journal_records),
                set(current_system_uids),
            )
            if not cutoffs:
                return
            async with self.persistence_lock:
                async with self.journal_lock:
                    # A new registry observation arrived after the plan was
                    # made. Leave compaction to the next run after it is saved.
                    if self.stopping or self.registry_pending or self.journal_pending:
                        return
                    compacted = compact_records(
                        self.journal_records,
                        cutoffs,
                        global_cutoff,
                    )
                    if len(compacted) == len(self.journal_records):
                        return
                    keep = {item['event_id'] for item in compacted}
                    try:
                        removed = await self._executor(
                            self.hass.async_add_executor_job,
                            self.journal.prune,
                            keep,
                        )
                    except Exception:
                        self.journal_records = await self._executor(
                            self.hass.async_add_executor_job,
                            self.journal.read,
                        )
                        raise
                    if removed != len(self.journal_records) - len(compacted):
                        self.journal_records = await self._executor(
                            self.hass.async_add_executor_job,
                            self.journal.read,
                        )
                        raise ArchiveError('Registry journal changed unexpectedly during pruning')
                    self.journal_records = compacted
                    _LOGGER.info('Compacted %d published registry journal observation(s)', removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Archive publication and progress are already durable. A cleanup
            # failure must not turn a successful export into a failed week.
            _LOGGER.exception('Registry journal maintenance failed; a later run will retry')

    async def _automatic_run(self) -> None:
        retry = False
        try:
            result = await self.run()
            retry = bool(result['errors'] or result['more_pending'])
        except asyncio.CancelledError:
            raise
        except Exception:
            retry = True
            for machine in collect_machines(self.hass):
                self.statuses.setdefault(machine['system_uid'], {})['last_error'] = 'Archivering mislukt; zie het HA-log.'
            self.notify()
            self.report_failure()
            _LOGGER.exception('Automatic week archive failed; retrying in one hour')
        finally:
            self.schedule_next(retry)

    @callback
    def report_failure(self) -> None:
        ir.async_create_issue(self.hass, DOMAIN, 'archive_failed', is_fixable=False,
            severity=ir.IssueSeverity.ERROR, translation_key='archive_failed')

    @callback
    def schedule_next(self, retry: bool = False) -> None:
        if self.stopping:
            return
        now = datetime.now(timezone.utc)
        when = next_weekly_run(now, self.hass.config.time_zone)
        if retry:
            when = min(when, now + timedelta(hours=1))
        if self.cancel_timer:
            self.cancel_timer()
        self.cancel_timer = async_track_point_in_utc_time(self.hass, self._request_run, when)

    async def _executor(self, executor, function, *args):
        # Cancellation must not release the manager lock while a worker is
        # still writing. Stop waits for that one file; no new week is started.
        future = asyncio.ensure_future(executor(function, *args))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await asyncio.shield(future)
            raise

    async def run(self, week_key: str | None = None, device_id: str | None = None) -> dict:
        async with self.lock:
            if self.stopping:
                raise HomeAssistantError('Week archiving is stopping')
            self.running_task = asyncio.current_task()
            try:
                if not self.initialized:
                    await self.initialize()
                return await self._run_locked(week_key, device_id)
            finally:
                self.running_task = None

    @staticmethod
    def _automatic_weeks(pending: ArchiveWeek, latest: ArchiveWeek, failed_keys: set[str]) -> list[ArchiveWeek]:
        """Retry one gap, advance the cursor, and always reserve the newest due week."""
        failed = sorted(
            (ArchiveWeek.from_key(key, pending.time_zone) for key in failed_keys),
            key=lambda week: week.monday,
        )
        failed = [week for week in failed if week.monday <= latest.monday]
        queue = failed[:1]
        reserve_latest = pending.monday < latest.monday and all(week.key != latest.key for week in queue)
        sequential_slots = MAX_CATCHUP_WEEKS - len(queue) - (1 if reserve_latest else 0)
        week = pending
        while week.monday <= latest.monday and sequential_slots > 0:
            if all(candidate.key != week.key for candidate in queue):
                queue.append(week)
                sequential_slots -= 1
            week = week.following()
        if reserve_latest and all(candidate.key != latest.key for candidate in queue):
            queue.append(latest)
        return queue

    async def _run_locked(self, week_key: str | None, device_id: str | None) -> dict:
        now = datetime.now(timezone.utc)
        time_zone = self.hass.config.time_zone
        latest = latest_due_week(now, time_zone)
        requested = ArchiveWeek.from_key(week_key, time_zone) if week_key else None
        if requested and requested.monday > latest.monday:
            raise ValueError('Only completed calendar weeks can be archived, from Monday 00:15')
        await self.flush_journal()
        current_machines = collect_machines(self.hass, device_id)
        # A deleted entity (or last entity of a system) remains discoverable in
        # the journal while its owning HA integration entry is enabled.
        known = {machine['system_uid']: machine for machine in current_machines}
        entries = {entry.entry_id for entry in self.hass.config_entries.async_entries(DOMAIN)
                   if entry.disabled_by is None} if self.journal_records else set()
        for item in self.journal_records:
            machine = item.get('machine')
            if (machine and machine.get('config_entry_id') in entries
                and (device_id is None or machine['device_id'] == device_id)
                and machine['system_uid'] not in known):
                known[machine['system_uid']] = {**machine, 'entities': []}
        machines = [machine_history(machine, self.journal_records) for machine in known.values()]
        if device_id is not None and not machines:
            raise ValueError('No active Solesta integration entry owns this device')
        result = {'archives': [], 'errors': [], 'skipped': [], 'more_pending': False}
        if not machines:
            return result
        recorder = get_instance(self.hass)
        # Wait for startup/migrations and commit all queued changes before
        # opening a read transaction. A blocked recorder gets a retry.
        try:
            async with asyncio.timeout(60):
                ready = await asyncio.shield(recorder.async_db_ready)
                if ready is False:
                    raise ArchiveError('Recorder database is not ready')
                await recorder.async_block_till_done()
        except (TimeoutError, ArchiveError) as err:
            raise HomeAssistantError('Recorder is not ready for week archiving') from err
        recorder_problems = self.check_recorder(machines, recorder)
        recorder_config = {
            'keep_days': recorder.keep_days, 'auto_purge': recorder.auto_purge,
            'enabled': recorder.enabled, 'schema_version': recorder.schema_version,
        }
        for machine in machines:
            if self.stopping:
                break
            uid = machine['system_uid']
            if not self.enabled(uid):
                result['skipped'].append({'system_uid': uid, 'reason': 'weekly_archive_disabled'})
                continue
            status = self.statuses.setdefault(uid, {})
            status['recorder_warnings'] = recorder_problems.get(uid, [])
            try:
                folder = machine_folder(self.root, machine['system_uid'])
                start_key = status.get('archive_start_week')
                start_week = (
                    ArchiveWeek.from_key(start_key, time_zone)
                    if start_key
                    else None
                )
                # Progress is the durable, per-machine archive administration.
                # Its absence means this installation has never observed a
                # complete week for this machine, regardless of domain name.
                if start_week is None and not (folder / 'progress.json').is_file():
                    start_week = first_full_week_after(now, time_zone)
                    status['archive_start_week'] = start_week.key
                pending_week = await self._executor(
                    self.hass.async_add_executor_job, load_progress, folder, start_week or latest)
                if start_week and pending_week.monday < start_week.monday:
                    pending_week = start_week
                    await self._executor(self.hass.async_add_executor_job, save_progress, folder, pending_week)
                if requested and start_week and requested.monday < start_week.monday:
                    result['skipped'].append({'system_uid': uid, 'reason': 'before_archive_start',
                                              'first_week': start_week.key, 'week': requested.key})
                    continue
                failed_keys = set(status.get('failed_weeks', []))
                weeks = ([requested] if requested else
                         self._automatic_weeks(pending_week, latest, failed_keys))
                if not weeks and start_week and start_week.monday > latest.monday:
                    result['skipped'].append({'system_uid': uid, 'reason': 'awaiting_first_full_week',
                                              'first_week': start_week.key})
                machine_failed = False
                for week in weeks:
                    if self.stopping:
                        break
                    if not self.enabled(uid):
                        break
                    advances_cursor = not requested and week.key == pending_week.key
                    attempt_finished = False
                    try:
                        path = await self._executor(self.hass.async_add_executor_job, archive_path, folder, week)
                        await self.flush_journal()
                        fresh = {item['system_uid']: item for item in collect_machines(self.hass)}
                        machine = machine_history(fresh.get(uid, {**machine, 'entities': []}), self.journal_records)
                        revision = self.registry_revision
                        manifest = await self._executor(
                            recorder.async_add_executor_job, export_recorder_week,
                            self.hass, path, machine, week, now, recorder_config, DOMAIN, self.version,
                            lambda: revision == self.registry_revision,
                        )
                        summary = {
                            'system_uid': machine['system_uid'], 'name': machine['name'],
                            'week': week.key, 'path': str(path),
                            'record_count': manifest['record_count'],
                            'coverage_warning_count': len(manifest['coverage']['warnings']),
                        }
                        result['archives'].append(summary)
                        failed_keys.discard(week.key)
                        attempt_finished = True
                        status.update(last_success_utc=datetime.now(timezone.utc).isoformat(),
                                      last_error=None, **summary)
                        _LOGGER.info('Week archive saved/verified: %s (%d records, %d coverage notes)',
                                     path, summary['record_count'], summary['coverage_warning_count'])
                    except asyncio.CancelledError:
                        raise
                    except Exception as err:
                        machine_failed = True
                        failed_keys.add(week.key)
                        attempt_finished = True
                        _LOGGER.exception('Week archive failed for %s, week %s', uid, week.key)
                        result['errors'].append({'system_uid': uid, 'week': week.key, 'error': str(err)})
                    finally:
                        if advances_cursor and attempt_finished:
                            pending_week = week.following()
                            await self._executor(
                                self.hass.async_add_executor_job, save_progress, folder, pending_week)
                    status['failed_weeks'] = sorted(failed_keys)
                    await self.save_settings()
                    self.notify()
                status['failed_weeks'] = sorted(failed_keys)
                if failed_keys:
                    status['last_error'] = 'Weekexport nog mislukt: ' + ', '.join(sorted(failed_keys))
                elif not machine_failed:
                    status['last_error'] = None
                if (not requested and self.enabled(uid)
                    and (pending_week.monday <= latest.monday or failed_keys)):
                    result['more_pending'] = True
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.exception('Week archive failed for %s', machine['system_uid'])
                result['errors'].append({'system_uid': machine['system_uid'], 'error': str(err)})
                status['last_error'] = str(err)
                self.notify()
        await self.save_settings()
        self.notify()
        await self._executor(self.hass.async_add_executor_job, _atomic_json, self.root / 'status.json', {
            'finished_at_utc': datetime.now(timezone.utc).isoformat(), **result,
        })
        await self._compact_journal(
            latest,
            {machine['system_uid'] for machine in machines},
        )
        if result['errors']:
            self.report_failure()
        elif not device_id and not requested:
            ir.async_delete_issue(self.hass, DOMAIN, 'archive_failed')
        return result


async def async_setup_archiving(hass: HomeAssistant) -> None:
    """Install one scheduler and one admin action for all provider hubs."""
    if DATA_ARCHIVE_MANAGER in hass.data:
        return
    integration = await async_get_integration(hass, DOMAIN)
    manager = ArchiveManager(hass, integration.version)
    try:
        await manager.initialize()
    except Exception:
        _LOGGER.exception('Archive initialization failed; provider setup continues and archiving will retry')
        manager.report_failure()
    hass.data[DATA_ARCHIVE_MANAGER] = manager

    async def archive_action(call: ServiceCall) -> dict:
        try:
            result = await manager.run(call.data.get('week'), call.data.get('device_id'))
        except (ValueError, ArchiveError) as err:
            raise HomeAssistantError(str(err)) from err
        except Exception as err:
            manager.report_failure()
            manager.schedule_next(retry=True)
            raise HomeAssistantError('Week archiving failed. See the Home Assistant log.') from err
        if result['errors']:
            manager.schedule_next(retry=True)
            raise HomeAssistantError('One or more week archives failed. See the Solesta archive status and HA log.')
        return result

    async_register_admin_service(
        hass, DOMAIN, SERVICE_ARCHIVE_WEEK, archive_action,
        schema=vol.Schema({vol.Optional('week'): str, vol.Optional('device_id'): str}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    manager.cancel_start = async_at_started(hass, manager.start)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, manager.stop)
