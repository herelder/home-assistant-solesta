"""Read original Recorder rows on Recorder's worker pool, never over SMB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from sqlalchemy import func, select

from homeassistant.components.recorder.db_schema import RecorderRuns, StateAttributes, States, StatesMeta
from homeassistant.helpers.recorder import session_scope

from .archive_files import ArchiveWeek, utc_iso, verify_archive, write_archive
from .archive_timeline import RowOwnership, aliases, merge_entity, participates_in_week


def _base_statement():
    return select(
        States.state_id,
        States.metadata_id,
        States.state,
        States.last_updated_ts,
        States.last_changed_ts,
        States.last_reported_ts,
        StateAttributes.shared_attrs,
    ).outerjoin(StateAttributes, States.attributes_id == StateAttributes.attributes_id)


def _record(row, entity: dict, kind: str) -> dict:
    updated = row.last_updated_ts
    attributes = json.loads(row.shared_attrs) if row.shared_attrs is not None else {}
    if not isinstance(attributes, dict):
        raise ValueError('Recorder state attributes must be a JSON object')
    return {
        'entity_key': entity['entity_key'],
        'entity_id': entity['entity_id'],
        'unique_id': entity['unique_id'],
        'record_kind': kind,
        'state_id': row.state_id,
        'metadata_id': row.metadata_id,
        'state': row.state,
        'removed': row.state == '',
        'last_updated_ts': updated,
        'last_changed_ts': row.last_changed_ts,
        'last_reported_ts': row.last_reported_ts,
        'last_updated_utc': utc_iso(updated),
        'last_changed_utc': utc_iso(row.last_changed_ts if row.last_changed_ts is not None else updated),
        'last_reported_utc': utc_iso(row.last_reported_ts if row.last_reported_ts is not None else updated),
        'attributes': attributes,
    }


def export_recorder_week(
    hass,
    path: Path,
    machine: dict,
    week: ArchiveWeek,
    now: datetime,
    recorder_config: dict,
    domain: str,
    version: str,
    snapshot_valid=None,
) -> dict:
    """Stream all stored rows in a consistent read transaction into one compressed JSON file."""
    if path.exists():
        return verify_archive(path, machine['system_uid'], week)
    with session_scope(hass=hass, read_only=True) as session:
        # sqlite3's legacy transaction mode does not BEGIN for SELECTs. Begin
        # explicitly so all entities and the manifest see the same snapshot.
        if session.bind.dialect.name == 'sqlite':
            connection = session.connection()
            if not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql('BEGIN')
        else:
            session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})

        machine = {**machine, 'entities': [entity for entity in machine['entities']
                   if participates_in_week(entity, week)]}
        ids = sorted({name for entry in machine['entities'] for name in aliases(entry)})
        metadata = dict(session.execute(
            select(StatesMeta.entity_id, StatesMeta.metadata_id).where(StatesMeta.entity_id.in_(ids))
        ).all())
        start, end = week.start.timestamp(), week.end.timestamp()
        earliest = session.scalar(select(func.min(States.last_updated_ts)))
        runs = session.execute(select(RecorderRuns.start, RecorderRuns.end, RecorderRuns.closed_incorrect).where(
            RecorderRuns.start < week.end,
            (RecorderRuns.end.is_(None)) | (RecorderRuns.end > week.start),
        ).order_by(RecorderRuns.start)).all()
        warnings = []
        if recorder_config['auto_purge'] and recorder_config['keep_days'] < 21:
            warnings.append({'code': 'retention_below_recommended_21_days', 'keep_days': recorder_config['keep_days']})
        sessions = machine.get('journal_sessions', [])
        starts = [item for item in sessions if item['kind'] == 'start']
        if not starts or starts[0]['at'] > start:
            warnings.append({'code': 'journal_does_not_reach_week_start',
                             'first_observation_utc': utc_iso(starts[0]['at']) if starts else None})
        last_stop = None
        for item in sessions:
            if item['kind'] == 'stop':
                last_stop = item['at']
            elif item['kind'] == 'start' and item is not starts[0]:
                if item['at'] > start and (last_stop is None or last_stop < end):
                    warnings.append({'code': 'journal_observation_gap', 'start_utc': utc_iso(last_stop),
                                     'end_utc': utc_iso(item['at']), 'unclean_stop': last_stop is None})
                last_stop = None
            elif item['kind'] == 'observation_gap' and start <= item['at'] < end:
                warnings.append({'code': 'registry_event_snapshot_missing', **item})
        if earliest is None or earliest > start:
            warnings.append({'code': 'database_does_not_reach_week_start', 'oldest_state_utc': utc_iso(earliest)})
        if recorder_config['auto_purge'] and week.start < now - timedelta(days=recorder_config['keep_days']):
            warnings.append({'code': 'week_exceeds_configured_retention'})
        if not recorder_config['enabled']:
            warnings.append({'code': 'recorder_currently_disabled'})
        cursor = week.start
        run_metadata = []
        for run in runs:
            run_start = run.start.replace(tzinfo=timezone.utc) if run.start.tzinfo is None else run.start
            run_end = (run.end.replace(tzinfo=timezone.utc) if run.end.tzinfo is None else run.end) if run.end else now
            run_metadata.append({'start_utc': utc_iso(run_start), 'end_utc': utc_iso(run.end), 'closed_incorrectly': run.closed_incorrect})
            if run_start > cursor:
                warnings.append({'code': 'recorder_gap', 'start_utc': utc_iso(cursor), 'end_utc': utc_iso(min(run_start, week.end))})
            cursor = max(cursor, min(run_end, week.end))
            if run.closed_incorrect:
                warnings.append({'code': 'recorder_run_closed_incorrectly', 'start_utc': utc_iso(run_start)})
        if cursor < week.end:
            warnings.append({'code': 'recorder_gap', 'start_utc': utc_iso(cursor), 'end_utc': utc_iso(week.end)})
        for entity in machine['entities']:
            if entity.get('recorded_now') is False:
                warnings.append({'code': 'entity_currently_excluded', 'entity_id': entity['entity_id']})
        coverage = {
            'scope': 'Original stored rows linked to stable entities through observed registry history, with preceding states and registry events. No guarantee of uninterrupted recording.',
            'first_or_partial_week': any(item['code'] != 'retention_below_recommended_21_days' for item in warnings),
            'recorder_at_export': recorder_config,
            'oldest_database_state_utc': utc_iso(earliest),
            'recorder_runs': run_metadata,
            'warnings': warnings,
        }

        ownership = RowOwnership(machine['entities'])

        def records():
            for entity in machine['entities']:
                selected = {metadata[name]: name for name in aliases(entity) if name in metadata}
                entity_statement = _base_statement().where(States.metadata_id.in_(selected))

                def belongs(row):
                    return ownership.owner(selected[row.metadata_id],
                                         row.last_updated_ts, row.state == '') == entity['unique_id']

                initial = None
                result = session.execute(entity_statement.where(States.last_updated_ts < start).order_by(
                    States.last_updated_ts.desc(), States.state_id.desc()).execution_options(yield_per=2048))
                try:
                    for row in result:
                        if belongs(row):
                            initial = _record(row, entity, 'start_state')
                            break
                finally:
                    result.close()

                def states():
                    result = session.execute(entity_statement.where(
                        States.last_updated_ts >= start, States.last_updated_ts < end
                    ).order_by(States.last_updated_ts, States.state_id).execution_options(yield_per=2048))
                    try:
                        for row in result:
                            if belongs(row):
                                record = _record(row, entity, 'state')
                                record['recorder_entity_id_at_export'] = selected[row.metadata_id]
                                yield record
                    finally:
                        result.close()

                yield from merge_entity(entity, week, initial, states(), warnings)
            coverage['first_or_partial_week'] = any(item['code'] != 'retention_below_recommended_21_days' for item in warnings)

        return write_archive(
            path, machine, week, records(), coverage,
            created_at=now, integration_domain=domain, integration_version=version,
            recorder_schema_version=recorder_config['schema_version'], snapshot_valid=snapshot_valid,
        )
