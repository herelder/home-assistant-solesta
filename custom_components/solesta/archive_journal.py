"""Durable registry observations, independent of the provider and Recorder DB."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from .archive_files import ArchiveError, _ensure_directory

JOURNAL_FORMAT = 1


class RegistryJournal:
    """One small local SQLite journal; each batch is a durable transaction."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _protect_files(self) -> None:
        """Keep the database and SQLite sidecars private, including upgrades."""
        for path in (self.path, Path(str(self.path) + '-wal'), Path(str(self.path) + '-shm')):
            try:
                os.chmod(path, 0o600)
            except FileNotFoundError:
                pass

    def _connect(self):
        _ensure_directory(self.path.parent)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            self._protect_files()
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA synchronous=FULL')
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, JOURNAL_FORMAT):
                connection.close()
                raise ArchiveError('Unsupported registry journal version')
            connection.execute('CREATE TABLE IF NOT EXISTS journal (sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)')
            connection.execute(f'PRAGMA user_version={JOURNAL_FORMAT}')
            self._protect_files()
        except Exception:
            connection.close()
            raise
        return connection

    def read(self) -> list[dict]:
        connection = self._connect()
        try:
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ArchiveError('Registry journal integrity check failed')
            result = []
            for sequence, payload in connection.execute('SELECT sequence, payload FROM journal ORDER BY sequence'):
                item = json.loads(payload)
                if not isinstance(item, dict) or not isinstance(item.get('at'), (int, float)):
                    raise ArchiveError('Invalid registry journal record')
                result.append(dict(item, sequence=sequence))
            return result
        finally:
            self._protect_files()
            connection.close()

    def append(self, items: list[dict]) -> list[dict]:
        connection = self._connect()
        try:
            result = []
            with connection:
                for item in items:
                    item.setdefault('event_id', str(uuid4()))
                    payload = json.dumps(item, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                    connection.execute('INSERT OR IGNORE INTO journal(event_id, payload) VALUES (?, ?)', (item['event_id'], payload))
                    sequence, saved = connection.execute('SELECT sequence, payload FROM journal WHERE event_id = ?', (item['event_id'],)).fetchone()
                    if saved != payload:
                        raise ArchiveError('Journal event identity collision')
                    result.append(dict(item, sequence=sequence))
            return result
        finally:
            self._protect_files()
            connection.close()

    def checkpoint(self) -> None:
        """Merge and remove the WAL so a filesystem backup is self-contained."""
        connection = self._connect()
        try:
            busy, _written, _checkpointed = connection.execute(
                'PRAGMA wal_checkpoint(TRUNCATE)'
            ).fetchone()
            if busy:
                raise ArchiveError('Registry journal WAL checkpoint is busy')
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ArchiveError('Registry journal integrity check failed after checkpoint')
        finally:
            self._protect_files()
            connection.close()

    def prune(self, keep_event_ids: set[str]) -> int:
        """Delete superseded journal rows in one transaction and compact SQLite."""
        connection = self._connect()
        try:
            before = connection.execute('SELECT COUNT(*) FROM journal').fetchone()[0]
            with connection:
                connection.execute('CREATE TEMP TABLE journal_keep (event_id TEXT PRIMARY KEY)')
                connection.executemany(
                    'INSERT INTO journal_keep(event_id) VALUES (?)',
                    ((event_id,) for event_id in keep_event_ids),
                )
                connection.execute(
                    'DELETE FROM journal WHERE NOT EXISTS '
                    '(SELECT 1 FROM journal_keep WHERE journal_keep.event_id = journal.event_id)'
                )
                connection.execute('DROP TABLE journal_keep')
            after = connection.execute('SELECT COUNT(*) FROM journal').fetchone()[0]
            if after != before:
                busy, _written, _checkpointed = connection.execute(
                    'PRAGMA wal_checkpoint(TRUNCATE)'
                ).fetchone()
                if busy:
                    raise ArchiveError('Registry journal WAL checkpoint is busy during pruning')
                connection.execute('VACUUM')
            return before - after
        finally:
            self._protect_files()
            connection.close()


def registry_snapshot(machines: list[dict]) -> dict[str, dict]:
    return {entity['entity_id']: {'machine': {key: value for key, value in machine.items() if key != 'entities'},
                                'entity': deepcopy(entity)}
            for machine in machines for entity in machine['entities']}


# Registry update events carry OLD field values. Rewind a burst backwards from
# its final snapshot to retain even disable/enable pairs in the same loop turn.
FIELD_NAMES = {'entity_id': 'entity_id', 'disabled_by': 'disabled_by_now',
               'name': 'name', 'original_name': 'original_name',
               'unit_of_measurement': 'unit_of_measurement_now',
               'device_class': 'device_class', 'original_device_class': 'original_device_class'}


def registry_events(previous: dict, current: dict, events: list[dict]) -> list[dict]:
    working = deepcopy(current)
    result = []
    for event in reversed(events):
        action, entity_id = event['action'], event['entity_id']
        old_id = event.get('old_entity_id', entity_id)
        after = working.get(entity_id)
        if action == 'remove':
            before = event.get('removed_snapshot') or previous.get(entity_id)
            if before is None:
                gap = {'kind': 'observation_gap', 'at': event['at'], 'entity_id': entity_id}
                if event.get('system_uid') is not None:
                    gap['system_uid'] = event['system_uid']
                result.append(gap)
                continue
            working[entity_id] = deepcopy(before)
            item = {**deepcopy(before), 'kind': 'remove', 'at': event['at']}
            item['entity']['present'] = False
        elif after is None:
            # An unrelated integration or a transient registration we could
            # not identify. Never attach its history to a guessed machine.
            continue
        elif action == 'create':
            item = {**deepcopy(after), 'kind': 'create', 'at': event['at']}
            working.pop(entity_id, None)
        else:
            before = deepcopy(after)
            for key, value in event.get('changes', {}).items():
                if key in FIELD_NAMES:
                    before['entity'][FIELD_NAMES[key]] = value
            before['entity']['entity_id'] = old_id
            working.pop(entity_id, None)
            working[old_id] = before
            if before == after:
                continue
            item = {**deepcopy(after), 'kind': 'update', 'at': event['at'], 'before': before['entity']}
        result.append(item)
    return list(reversed(result))


def machine_history(machine: dict, journal: list[dict]) -> dict:
    """Retain removed entities and all historical names under stable IDs."""
    result = deepcopy(machine)
    entities = {entity['unique_id']: entity for entity in result['entities']}
    for item in journal:
        if item.get('machine', {}).get('system_uid') != machine['system_uid']:
            continue
        entity = deepcopy(item['entity'])
        uid = entity['unique_id']
        if uid not in entities:
            entities[uid] = entity
        entities[uid].setdefault('registry_history', []).append(item)
    result['entities'] = sorted(entities.values(), key=lambda entity: entity['unique_id'])
    result['journal_sessions'] = [
        item for item in journal
        if item['kind'] in ('start', 'stop', 'observation_gap')
        and (
            item['kind'] != 'observation_gap'
            or item.get('system_uid') in (None, machine['system_uid'])
        )
    ]
    return result


def compact_records(
    records: list[dict],
    cutoffs: dict[str, float],
    global_cutoff: float | None,
) -> list[dict]:
    """Retain the minimum safe journal history before unpublished weeks.

    Per entity, the last snapshot before its system cutoff is the starting
    condition for later weeks. Later records remain untouched. Global session
    history retains its last start/stop boundary before the oldest common
    cutoff. Systems without a proven cutoff are never compacted.
    """
    if any(
        not isinstance(item.get('sequence'), int)
        or not isinstance(item.get('event_id'), str)
        for item in records
    ):
        return records
    keep_sequences: set[int] = set()
    latest_entities: dict[tuple[str, str], dict] = {}
    earlier_sessions = []

    for item in records:
        sequence = item.get('sequence')
        machine = item.get('machine')
        system_uid = machine.get('system_uid') if isinstance(machine, dict) else item.get('system_uid')
        at = item.get('at')
        if system_uid is not None:
            cutoff = cutoffs.get(system_uid)
            if cutoff is None or not isinstance(at, (int, float)) or at >= cutoff:
                keep_sequences.add(sequence)
                continue
            entity = item.get('entity')
            unique_id = entity.get('unique_id') if isinstance(entity, dict) else None
            if unique_id is not None:
                key = (system_uid, unique_id)
                previous = latest_entities.get(key)
                if previous is None or (item['at'], sequence) > (
                    previous['at'], previous['sequence']
                ):
                    latest_entities[key] = item
            # A scoped point-gap before the next unpublished week is already
            # recorded in its published archive and needs no baseline row.
            continue

        if item.get('kind') in ('start', 'stop'):
            if global_cutoff is None or not isinstance(at, (int, float)) or at >= global_cutoff:
                keep_sequences.add(sequence)
            else:
                earlier_sessions.append(item)
        elif item.get('kind') == 'observation_gap':
            if global_cutoff is None or not isinstance(at, (int, float)) or at >= global_cutoff:
                keep_sequences.add(sequence)
        else:
            keep_sequences.add(sequence)

    keep_sequences.update(item['sequence'] for item in latest_entities.values())
    if earlier_sessions:
        latest_session = max(
            earlier_sessions,
            key=lambda item: (item['at'], item['sequence']),
        )
        keep_sequences.add(latest_session['sequence'])
        if latest_session['kind'] == 'stop':
            preceding_starts = [
                item for item in earlier_sessions
                if item['kind'] == 'start'
                and (item['at'], item['sequence']) < (
                    latest_session['at'], latest_session['sequence']
                )
            ]
            if preceding_starts:
                keep_sequences.add(max(
                    preceding_starts,
                    key=lambda item: (item['at'], item['sequence']),
                )['sequence'])
    return [item for item in records if item.get('sequence') in keep_sequences]
