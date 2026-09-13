"""Merge original Recorder rows with explicitly observed registry transitions."""
from __future__ import annotations

from datetime import datetime
from heapq import merge
import math

from .archive_files import ArchiveError, utc_iso


def history(entity: dict) -> list[dict]:
    return sorted(entity.get('registry_history', []), key=lambda item: (item['at'], item.get('sequence', 0)))


def created_at(entity: dict) -> float | None:
    # Recreating the same stable entity must not erase its earlier registration.
    values = [entity.get('registry_created_at_utc')]
    values.extend(item['entity'].get('registry_created_at_utc') for item in entity.get('registry_history', []))
    stamps = [datetime.fromisoformat(value).timestamp() for value in values if value]
    return min(stamps) if stamps else None


def participates_in_week(entity: dict, week) -> bool:
    born = created_at(entity)
    if born is not None and born >= week.end.timestamp():
        return False
    previous = registry_at(entity, week.start.timestamp() - 0.000001)
    if previous is None or previous['entity'].get('present', True):
        return True
    return any(week.start.timestamp() <= item['at'] < week.end.timestamp()
               and item['entity'].get('present', True) for item in history(entity))


def registry_at(entity: dict, at: float) -> dict | None:
    previous = None
    for event in history(entity):
        if event['at'] > at:
            break
        previous = event
    return previous


def aliases(entity: dict) -> set[str]:
    result = {entity['entity_id']}
    for event in history(entity):
        result.add(event['entity']['entity_id'])
        if event.get('before'):
            result.add(event['before']['entity_id'])
    return result


class RowOwnership:
    """Precompute presence intervals once; exports may contain millions of rows."""

    def __init__(self, entities: list[dict]) -> None:
        self.by_name: dict[str, list[tuple[float, float, str, str | None]]] = {}
        for entity in entities:
            events = history(entity)
            born = created_at(entity)
            first = events[0] if events else None
            if first and first.get('before') is not None:
                current = dict(first['before'])
            elif first and first['kind'] == 'create':
                current = None
            elif first and first['kind'] == 'remove':
                current = {**first['entity'], 'present': True}
            elif first:
                current = dict(first['entity'])
            else:
                current = dict(entity)

            lifetime_start = born if born is not None else -math.inf
            interval_start = lifetime_start
            if current is not None and not current.get('present', True):
                current = None

            for event in events:
                at = float(event['at'])
                after = event['entity']
                after_present = after.get('present', True)
                before_name = current['entity_id'] if current is not None else None
                after_name = after['entity_id'] if after_present else None
                resets = event['kind'] == 'create'
                renamed = (
                    current is not None
                    and after_present
                    and before_name != after_name
                    and not resets
                )
                if current is not None and (
                    not after_present or before_name != after_name or resets
                ):
                    reason = event['kind'] if not after_present else 'rename'
                    self.by_name.setdefault(before_name, []).append(
                        (interval_start, at, entity['unique_id'], reason)
                    )
                    current = None
                if after_present and current is None:
                    current = dict(after)
                    if not renamed:
                        lifetime_start = at
                    # Recorder updates metadata on rename, including rows from
                    # before the rename. The new name therefore owns rows back
                    # to this uninterrupted registration's start.
                    interval_start = lifetime_start
                elif after_present:
                    current = dict(after)

            if current is not None:
                self.by_name.setdefault(current['entity_id'], []).append(
                    (interval_start, math.inf, entity['unique_id'], None)
                )

    def owner(self, database_name: str, at: float, removed: bool = False) -> str | None:
        intervals = self.by_name.get(database_name, [])
        # HA writes an empty Recorder state for an entity-registry removal.
        # At that exact boundary the interval that just ended owns the row;
        # an older identity that once used the same entity_id does not.
        if removed:
            ended = {
                uid for start, end, uid, reason in intervals
                if start <= at and end == at and reason == 'remove'
            }
            if len(ended) > 1:
                raise ArchiveError(
                    f'Ambiguous historical entity ownership for {database_name} at {utc_iso(at)}'
                )
            if ended:
                return next(iter(ended))

        candidates = {
            uid for start, end, uid, _reason in intervals
            if start <= at < end
        }
        if len(candidates) > 1:
            raise ArchiveError(f'Ambiguous historical entity ownership for {database_name} at {utc_iso(at)}')
        return next(iter(candidates)) if candidates else None


def owner_for_row(entities: list[dict], database_name: str, at: float, removed: bool = False) -> str | None:
    return RowOwnership(entities).owner(database_name, at, removed)


def reset_event(event: dict) -> bool:
    return event['kind'] == 'create' or (
        event.get('before', {}).get('disabled_by_now') is not None
        and event['entity'].get('disabled_by_now') is None
    ) or (event.get('before', {}).get('present') is False and event['entity'].get('present', True))


def merge_entity(entity: dict, week, initial: dict | None, rows, warnings: list[dict]):
    start, end = week.start.timestamp(), week.end.timestamp()
    events = history(entity)
    previous = registry_at(entity, start - 0.000001)
    status = previous['entity'] if previous else None
    born = created_at(entity)
    present = status.get('present', True) if status else (False if born is not None and born >= start else None)
    disabled = status is not None and status.get('disabled_by_now') is not None
    resets = [item for item in events if item['at'] < start and reset_event(item)]
    reset_after_value = bool(resets and (initial is None or resets[-1]['at'] > initial['last_updated_ts']))
    if disabled:
        effective, basis = 'uitgeschakeld', 'registry'
    elif present is False or reset_after_value:
        effective, basis = 'unknown', 'registry'
    elif initial is not None:
        effective, basis = initial['state'], 'recorder'
    else:
        effective, basis = 'unknown', 'missing_history'
    if initial is None and not disabled and present is not False:
        warnings.append({'code': 'no_start_state', 'unique_id': entity['unique_id']})
    if status is None and present is not False:
        warnings.append({'code': 'registry_state_at_week_start_unknown', 'unique_id': entity['unique_id']})
    yield {
        'record_kind': 'start_state', 'unique_id': entity['unique_id'], 'entity_key': entity['entity_key'],
        'entity_id': status['entity_id'] if status else entity['entity_id'],
        'at': start, 'at_utc': utc_iso(start), 'effective_state': effective,
        'state': effective, 'basis': basis, 'present': present,
        'attributes': initial['attributes'] if initial is not None and basis == 'recorder' else {},
        'last_recorded_state': initial, 'registry_observation': previous,
        'is_measurement': False,
    }
    changes = [item for item in events if start <= item['at'] < end]
    timeline = merge(((row['last_updated_ts'], 1, index, row) for index, row in enumerate(rows)),
                     ((item['at'], 0, index, item) for index, item in enumerate(changes)))
    for at, source, _, item in timeline:
        if source == 0:
            before = status
            status = item['entity']
            present = status.get('present', True)
            disabled = status.get('disabled_by_now') is not None
            applies = False
            if disabled:
                effective, applies = 'uitgeschakeld', True
            elif not present or reset_event(item) or (before and before.get('disabled_by_now') is not None):
                effective, applies = 'unknown', True
            yield {'record_kind': 'registry', 'unique_id': entity['unique_id'], 'entity_key': entity['entity_key'],
                   'entity_id': status['entity_id'], 'at': at, 'at_utc': utc_iso(at),
                   'event': item['kind'], 'registry': item, 'present': present,
                   'effective_state': effective, 'applies_to_state': applies, 'is_measurement': False}
        else:
            # A registration during this week may predate the journal. The
            # initial absence only applies before its known registry creation
            # time; a later Recorder row proves the entity was then present.
            # An explicitly observed removal must still take precedence.
            if status is None and present is False and born is not None and at >= born:
                present = True
            applies = not disabled and present is not False
            if applies:
                effective = item['state']
            # state and attributes remain the exact Recorder payload even when
            # a removal/unavailable row arrives after a disable event.
            yield {**item, 'entity_id': status['entity_id'] if status else entity['entity_id'], 'at': at, 'at_utc': utc_iso(at), 'present': present,
                   'effective_state': effective, 'applies_to_state': applies}
