"""Portable, lossless weekly archives; no Home Assistant or database imports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

ARCHIVE_FORMAT = 2
ARCHIVE_FOLDER = 'archives'
GRACE = timedelta(minutes=15)


class ArchiveError(Exception):
    """An archive cannot safely be created or reused."""


def utc_iso(value: datetime | float | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromtimestamp(value, timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ArchiveWeek:
    monday: date
    time_zone: str

    def __post_init__(self) -> None:
        if self.monday.weekday() != 0:
            raise ValueError('Archive week must start on Monday')
        ZoneInfo(self.time_zone)

    @property
    def key(self) -> str:
        year, week, _ = self.monday.isocalendar()
        return f'{year:04d}-W{week:02d}'

    @property
    def start(self) -> datetime:
        return datetime.combine(self.monday, time(), ZoneInfo(self.time_zone)).astimezone(timezone.utc)

    @property
    def end(self) -> datetime:
        return datetime.combine(self.monday + timedelta(days=7), time(), ZoneInfo(self.time_zone)).astimezone(timezone.utc)

    def following(self) -> ArchiveWeek:
        return ArchiveWeek(self.monday + timedelta(days=7), self.time_zone)

    @classmethod
    def from_key(cls, key: str, time_zone: str) -> ArchiveWeek:
        try:
            year, week = key.split('-W')
            result = cls(date.fromisocalendar(int(year), int(week), 1), time_zone)
            if result.key != key:
                raise ValueError
            return result
        except (TypeError, ValueError) as err:
            raise ValueError('Use an ISO week such as 2026-W35') from err


def latest_due_week(now: datetime, time_zone: str) -> ArchiveWeek:
    local = now.astimezone(ZoneInfo(time_zone)) - GRACE
    monday = local.date() - timedelta(days=local.weekday() + 7)
    return ArchiveWeek(monday, time_zone)


def next_weekly_run(now: datetime, time_zone: str) -> datetime:
    due = latest_due_week(now, time_zone)
    return due.following().end + GRACE


def first_full_week_after(now: datetime, time_zone: str) -> ArchiveWeek:
    """Return the first calendar week that starts strictly after setup."""
    local = now.astimezone(ZoneInfo(time_zone))
    current_monday = local.date() - timedelta(days=local.weekday())
    return ArchiveWeek(current_monday + timedelta(days=7), time_zone)


def machine_folder(root: Path, system_uid: str) -> Path:
    # Registry data must never be allowed to choose an arbitrary file path.
    if str(UUID(system_uid)) != system_uid:
        raise ArchiveError('System UID must be a canonical UUID')
    return root / system_uid


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directory(path: Path) -> None:
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        _sync_directory(directory.parent)


def cleanup_pending_files(root: Path) -> list[Path]:
    """Remove unpublished files left by an interrupted archive write.

    The manager calls this once during startup, before it can start an export.
    Only the archive root and canonical per-system folders are inspected, so a
    crafted directory or symlink cannot expand the cleanup scope.
    """
    if not root.is_dir():
        return []
    folders = [root]
    for child in root.iterdir():
        if not child.is_dir() or child.is_symlink():
            continue
        try:
            if str(UUID(child.name)) == child.name:
                folders.append(child)
        except (TypeError, ValueError):
            continue
    removed = []
    for folder in folders:
        changed = False
        for path in folder.glob('.pending-*'):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed.append(path)
                changed = True
        if changed:
            _sync_directory(folder)
    return removed


def _atomic_json(path: Path, document: dict) -> None:
    _ensure_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(document, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_progress(folder: Path, first: ArchiveWeek) -> ArchiveWeek:
    path = folder / 'progress.json'
    if not path.exists():
        # This is saved BEFORE reading history so a failed first attempt is
        # retried for the same week even if HA is restarted much later.
        existing = sorted(folder.glob('????-W??.json.gz')) if folder.exists() else []
        initial = ArchiveWeek.from_key(existing[0].name[:8], first.time_zone) if existing else first
        save_progress(folder, initial)
        return initial
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['format_version'] not in (1, ARCHIVE_FORMAT) or data['time_zone'] != first.time_zone:
            raise ValueError('Archive format or time zone changed')
        return ArchiveWeek.from_key(data['next_week'], data['time_zone'])
    except (KeyError, ValueError, TypeError) as err:
        raise ArchiveError(f'Cannot read archive progress: {path.name}') from err


def save_progress(folder: Path, next_week: ArchiveWeek) -> None:
    _atomic_json(folder / 'progress.json', {
        'format_version': ARCHIVE_FORMAT,
        'time_zone': next_week.time_zone,
        'next_week': next_week.key,
    })


def archive_path(folder: Path, week: ArchiveWeek) -> Path:
    """Return the one supported archive path for a calendar week."""
    return folder / f'{week.key}.json.gz'


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


_RECORD_KINDS = frozenset({'start_state', 'state', 'registry'})
_REGISTRY_EVENTS = frozenset({'observe', 'create', 'update', 'remove'})


def _number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ArchiveError(f'Archive field {field} must be a finite number')
    return float(value)


def _string(value, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ArchiveError(f'Archive field {field} must be a string')
    return value


def _state(value, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ArchiveError(f'Archive field {field} must be a string or null')
    return value


def _require_fields(record: dict, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise ArchiveError('Archive record is missing required field(s): ' + ', '.join(missing))


def _identity_map(entities: object, *, stored_counts: bool) -> dict[str, dict]:
    if not isinstance(entities, list):
        raise ArchiveError('Archive entities must be a list')
    result: dict[str, dict] = {}
    entity_keys: set[str] = set()
    for entity in entities:
        if not isinstance(entity, dict):
            raise ArchiveError('Archive entity metadata must be an object')
        uid = _string(entity.get('unique_id'), 'unique_id')
        key = _string(entity.get('entity_key'), 'entity_key')
        _string(entity.get('entity_id'), 'entity_id')
        if uid in result or key in entity_keys:
            raise ArchiveError('Duplicate archive entity identity or key')
        if stored_counts:
            for count_key in ('states', 'registry_changes'):
                count = entity.get(count_key)
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise ArchiveError(f'Archive entity {count_key} must be a non-negative integer')
        result[uid] = entity
        entity_keys.add(key)
    return result


def _validate_record(record: object, identities: dict[str, dict], week: ArchiveWeek) -> tuple[str, str, float]:
    if not isinstance(record, dict):
        raise ArchiveError('Archive record must be an object')
    kind = record.get('record_kind')
    if kind not in _RECORD_KINDS:
        raise ArchiveError('Unsupported archive record kind')
    _require_fields(
        record,
        ('record_kind', 'unique_id', 'entity_key', 'entity_id', 'at', 'at_utc', 'present'),
    )
    uid = _string(record.get('unique_id'), 'unique_id')
    if uid not in identities:
        raise ArchiveError('Unexpected entity identity')
    if _string(record.get('entity_key'), 'entity_key') != identities[uid]['entity_key']:
        raise ArchiveError('Archive record entity key does not match its identity')
    _string(record.get('entity_id'), 'entity_id')
    at = _number(record.get('at'), 'at')
    if record.get('at_utc') != utc_iso(at):
        raise ArchiveError('Archive record UTC timestamp does not match at')
    present = record.get('present')
    if present is not None and type(present) is not bool:
        raise ArchiveError('Archive record present must be boolean or null')

    if kind == 'start_state':
        _require_fields(
            record,
            ('state', 'effective_state', 'basis', 'attributes', 'is_measurement',
             'last_recorded_state', 'registry_observation'),
        )
        if at != week.start.timestamp():
            raise ArchiveError('Initial state must be timestamped at the exact week start')
        if record.get('basis') not in {'recorder', 'registry', 'missing_history'}:
            raise ArchiveError('Initial state has an invalid basis')
        _state(record.get('state'), 'state')
        _state(record.get('effective_state'), 'effective_state')
        if not isinstance(record.get('attributes'), dict):
            raise ArchiveError('Initial state attributes must be an object')
        if type(record.get('is_measurement')) is not bool:
            raise ArchiveError('Initial state is_measurement must be boolean')
    elif kind == 'state':
        _require_fields(
            record,
            ('state_id', 'metadata_id', 'state', 'effective_state', 'removed',
             'applies_to_state', 'attributes', 'last_updated_ts', 'last_changed_ts',
             'last_reported_ts', 'last_updated_utc', 'last_changed_utc',
             'last_reported_utc'),
        )
        if not week.start.timestamp() <= at < week.end.timestamp():
            raise ArchiveError('Change falls outside requested week')
        if _number(record.get('last_updated_ts'), 'last_updated_ts') != at:
            raise ArchiveError('State timestamp does not match last_updated_ts')
        for field in ('state_id', 'metadata_id'):
            value = record.get(field)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ArchiveError(f'State field {field} must be an integer')
        _state(record.get('state'), 'state')
        _state(record.get('effective_state'), 'effective_state')
        if type(record.get('removed')) is not bool or type(record.get('applies_to_state')) is not bool:
            raise ArchiveError('State flags must be boolean')
        if not isinstance(record.get('attributes'), dict):
            raise ArchiveError('State attributes must be an object')
        for numeric, utc_field in (
            ('last_updated_ts', 'last_updated_utc'),
            ('last_changed_ts', 'last_changed_utc'),
            ('last_reported_ts', 'last_reported_utc'),
        ):
            value = record.get(numeric)
            effective = at if value is None else _number(value, numeric)
            if record.get(utc_field) != utc_iso(effective):
                raise ArchiveError(f'State field {utc_field} does not match {numeric}')
    else:
        _require_fields(
            record,
            ('event', 'registry', 'effective_state', 'applies_to_state', 'is_measurement'),
        )
        if not week.start.timestamp() <= at < week.end.timestamp():
            raise ArchiveError('Change falls outside requested week')
        event = record.get('event')
        if event not in _REGISTRY_EVENTS:
            raise ArchiveError('Registry record has an invalid event')
        if type(record.get('applies_to_state')) is not bool or type(record.get('is_measurement')) is not bool:
            raise ArchiveError('Registry record flags must be boolean')
        _state(record.get('effective_state'), 'effective_state')
        registry = record.get('registry')
        if not isinstance(registry, dict) or registry.get('kind') != event:
            raise ArchiveError('Registry payload does not match its event')
    return kind, uid, at


def verify_archive(path: Path, system_uid: str, week: ArchiveWeek) -> dict:
    """Validate gzip CRC, JSON records, identities, boundaries and payload SHA."""
    try:
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
            digest = hashlib.sha256()
            line = stream.readline()
            if not line.startswith('{"entities":') or not line.endswith(',\n'):
                raise ArchiveError('Invalid archive entity section')
            entities = json.loads(line[len('{"entities":'):-2])
            identities = _identity_map(entities, stored_counts=True)
            digest.update(line.encode())
            line = stream.readline()
            if not line.startswith('"initial_states":') or not line.endswith(',\n'):
                raise ArchiveError('Invalid initial state section')
            initial = json.loads(line[len('"initial_states":'):-2])
            if not isinstance(initial, list):
                raise ArchiveError('Initial states must be a list')
            initial_ids = []
            for item in initial:
                kind, uid, _ = _validate_record(item, identities, week)
                if kind != 'start_state':
                    raise ArchiveError('Initial state section contains a change record')
                initial_ids.append(uid)
            if set(initial_ids) != set(identities) or len(initial_ids) != len(identities):
                raise ArchiveError('Every entity must have exactly one initial state')
            digest.update(line.encode())
            if stream.readline() != '"changes":[\n':
                raise ArchiveError('Invalid change section')
            count = 0
            counts = {uid: {'states': 0, 'registry_changes': 0} for uid in identities}
            last_at: dict[str, float] = {}
            for line in stream:
                if line == '],\n':
                    break
                prefix = ',' if count else ''
                if not line.startswith(prefix + '{') or not line.endswith('\n'):
                    raise ArchiveError('Invalid change record')
                data = line[len(prefix):]
                record = json.loads(data)
                kind, uid, at = _validate_record(record, identities, week)
                if kind == 'start_state':
                    raise ArchiveError('Change section contains an initial state')
                if uid in last_at and at < last_at[uid]:
                    raise ArchiveError('Entity changes are not chronological')
                last_at[uid] = at
                counts[uid]['states' if kind == 'state' else 'registry_changes'] += 1
                digest.update(data.encode())
                count += 1
            else:
                raise ArchiveError('Truncated change section')
            line = stream.readline()
            if not line.startswith('"archive":') or not line.endswith('\n'):
                raise ArchiveError('Missing archive metadata')
            metadata = json.loads(line[len('"archive":'):])
            if stream.read() != '}\n':  # Read to EOF to force gzip CRC validation.
                raise ArchiveError('Unexpected archive trailer')
            if any(
                counts[uid][name] != identities[uid][name]
                for uid in identities
                for name in ('states', 'registry_changes')
            ):
                raise ArchiveError('Per-entity archive counts do not match the payload')
            if (metadata['format_version'] != ARCHIVE_FORMAT
                or metadata['machine']['system_uid'] != system_uid
                or metadata['week']['id'] != week.key
                or metadata['week']['time_zone'] != week.time_zone
                or metadata['week']['start_utc'] != utc_iso(week.start)
                or metadata['week']['end_utc_exclusive'] != utc_iso(week.end)
                or metadata['payload_sha256'] != digest.hexdigest()
                or metadata['change_count'] != count
                or metadata['record_count'] != count + len(initial)
                or metadata['export_complete'] is not True):
                raise ArchiveError('Archive identity, boundary, count or checksum mismatch')
            return metadata
    except (OSError, KeyError, ValueError, TypeError, UnicodeError, EOFError) as err:
        raise ArchiveError(f'Archive is unreadable: {path.name}') from err


def write_archive(path: Path, machine: dict, week: ArchiveWeek, records: Iterable[dict], coverage: dict,
                  *, created_at: datetime, integration_domain: str, integration_version: str,
                  recorder_schema_version: int, snapshot_valid=None) -> dict:
    """Stream one portable JSON document, verify it, then publish without overwrite."""
    if path.exists():
        return verify_archive(path, machine['system_uid'], week)
    _ensure_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', suffix='.json.gz', dir=path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary)
    identity_map = _identity_map(machine['entities'], stored_counts=False)
    identities = set(identity_map)
    counts = {uid: {'states': 0, 'registry_changes': 0} for uid in identities}
    initial = {}
    total = 0
    try:
        # Disk spool bounds memory even with a high-frequency week. This is
        # temporary and never a second delivered archive.
        with tempfile.TemporaryFile(mode='w+t', encoding='utf-8', dir=path.parent) as spool:
            last_at: dict[str, float] = {}
            for record in records:
                kind, uid, at = _validate_record(record, identity_map, week)
                if kind == 'start_state':
                    if uid in initial:
                        raise ArchiveError('Duplicate initial state')
                    initial[uid] = record
                    continue
                if uid not in initial:
                    raise ArchiveError('Entity change precedes its initial state')
                if uid in last_at and at < last_at[uid]:
                    raise ArchiveError('Entity changes are not chronological')
                last_at[uid] = at
                spool.write(_json(record) + '\n')
                counts[uid]['states' if kind == 'state' else 'registry_changes'] += 1
                total += 1
            if set(initial) != identities:
                raise ArchiveError('Missing initial entity state')
            entities = [dict(entity, **counts[entity['unique_id']]) for entity in machine['entities']]
            digest = hashlib.sha256()
            with gzip.open(temporary_path, 'wt', encoding='utf-8', newline='\n', compresslevel=6) as output:
                for line in ('{"entities":' + _json(entities) + ',\n',
                             '"initial_states":' + _json(list(initial.values())) + ',\n'):
                    output.write(line)
                    digest.update(line.encode())
                output.write('"changes":[\n')
                spool.seek(0)
                for index, line in enumerate(spool):
                    output.write((',' if index else '') + line)
                    digest.update(line.encode())
                output.write('],\n')
                metadata = {
                    'format_version': ARCHIVE_FORMAT, 'created_at_utc': utc_iso(created_at),
                    'integration': {'domain': integration_domain, 'version': integration_version},
                    'source': {'type': 'home_assistant_recorder_and_registry_journal', 'schema_version': recorder_schema_version},
                    'machine': {key: value for key, value in machine.items() if key not in ('entities', 'journal_sessions')},
                    'week': {'id': week.key, 'time_zone': week.time_zone, 'start_utc': utc_iso(week.start),
                             'end_utc_exclusive': utc_iso(week.end), 'duration_seconds': int((week.end-week.start).total_seconds())},
                    'export_complete': True, 'coverage': coverage,
                    'record_count': total + len(initial), 'change_count': total,
                    'payload_sha256': digest.hexdigest(),
                    'semantics': 'initial_states are starting conditions, not new measurements. Changes are ordered per unique_id by at; Recorder fields are unchanged. Apply effective_state only when applies_to_state is true. Registry-only uitgeschakeld is distinct from off, unknown and unavailable. Read coverage before reconstructing observed history.',
                }
                output.write('"archive":' + _json(metadata) + '\n}\n')
        verified = verify_archive(temporary_path, machine['system_uid'], week)
        with temporary_path.open('rb') as stored:
            os.fsync(stored.fileno())
        if snapshot_valid is not None and not snapshot_valid():
            raise ArchiveError('Entity registry changed during export; retry with a fresh snapshot')
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            return verify_archive(path, machine['system_uid'], week)
        _sync_directory(path.parent)
        return verified
    finally:
        temporary_path.unlink(missing_ok=True)
