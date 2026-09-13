# Weekly source archives

The integration can create a source archive of the previous calendar week
every Monday at **00:15 in the Home Assistant time zone**. A week starts on
Monday at 00:00 inclusive and ends on the following Monday at 00:00 exclusive.
This local-calendar definition also applies to weeks containing a
daylight-saving transition. No Home Assistant automation is required.

Weekly archives are optional and disabled by default for every system.

## Controls and status

Each solar water heater has three archive entities:

- **Weekly source archive** is the on/off switch. Its value is stored in the
  normal system configuration and survives a restart. Turning it off prevents
  both scheduled and manually requested exports for that system. Registry
  observation continues, existing files remain, and an export already being
  written is allowed to finish safely.
- **Last successful weekly export** is the time at which an archive was last
  created or successfully revalidated.
- **Archive status** is one of **Waiting for first export**, **Disabled**,
  **OK**, **Check archive coverage** or **Error**. Its attributes contain the
  week, file path, record count, coverage-warning count, Recorder warnings,
  last error and last successful export. Status survives a restart.

In **Reconfigure system**, **Enabled** and **Weekly source archive** appear
above the source expressions. The two diagnostic archive descriptions use
`drop()` by default because the archive manager supplies their values rather
than the provider expression evaluator.

Archive entities are part of the same central entity catalog as the other
Solesta entities. They are included in source archives from the moment Home
Assistant registers them. An archive covering time before their registration
will not yet list them.

## Request an export manually

Go to **Developer tools → Actions → Solesta: Archive week**.

- With no fields, the action catches up on missing completed weeks for all
  systems whose archive switch is on.
- Set `week` to an ISO week such as `2026-W36` to request one completed
  week.
- Set `device_id` to limit the action to one solar water heater.

The selected device's archive switch must be on. The current calendar week
cannot be exported because it is not complete.

## Storage on the Home Assistant system

Files are kept below the actual Home Assistant configuration directory,
normally:

```text
/config/archives/
  solesta/
    registry.sqlite3
    settings.json
    status.json
    <system_uid>/
        2026-W36.json.gz
        2026-W37.json.gz
        progress.json
```

`/config/archives` is a generic top-level location. This integration manages
only its `solesta` subdirectory. Each system's permanent UUID determines its
directory; display names and entity renames do not change archive identity.

The integration does not copy archives to another computer and never deletes
completed weekly archive files automatically. Include the whole
`/config/archives/solesta/` directory in any external retention plan. The
small registry journal, status and progress files are required together with
the weekly files for reliable continuation.

The journal database and its possible SQLite side files have owner-only read
and write permissions. After all affected weeks have been published, old
registry history is compacted to the last initial state still needed. An
unresolved failed week prevents compaction past that boundary. Incomplete
`.pending-*` files left by an interrupted write are cleaned up at the next
start. The archive switch itself lives in Home Assistant system configuration
and is not duplicated in `settings.json`.

## Backups and ordinary file copies

The integration exposes a Home Assistant backup platform. During a native Home
Assistant backup it:

1. waits for an active export;
2. prevents new archive writes;
3. flushes pending registry events;
4. persists current archive status;
5. creates a SQLite WAL checkpoint; and
6. keeps writes blocked until Home Assistant finishes the backup.

The resulting backup contains one internally consistent state across weekly
files, progress, status and the registry journal.

An ordinary file copy does not activate this coordination. Stop Home Assistant
before copying the archive directory directly.

## Gzip-compressed JSON format

Each `.json.gz` file decompresses to one ordinary JSON document with four
top-level sections:

| Section | Contents |
| --- | --- |
| `archive` | Format version 2, system identity, Home Assistant time zone, week boundaries, creation time, source version, counts, checksum and coverage |
| `entities` | Relevant registered entities keyed by permanent `unique_id`, including disabled or later removed entities, their types and observed registry history |
| `initial_states` | One starting condition per entity at the week boundary, explicitly marked as context rather than a new measurement |
| `changes` | Original Recorder rows and observed entity-registry events inside the week |

Measurements, binary states, settings and diagnostics are all eligible. The
export is not limited to `sensor.*` or to a name prefix. Identity follows the
Home Assistant entity registry and the permanent Solesta system layer.
Registry data in `entities` contains the observations available to the
exporter, including later rename information used to locate older Recorder
rows; it is not a claimed snapshot of the registry at the start of the week.

The integration reads original states and stored attributes from Recorder
without statistical aggregation, rounding or interpolation. Equal states with
different attributes remain separate. Repeated reports that Home Assistant did
not store cannot be reconstructed. Raw Recorder timestamps remain in the
records, including possible `null` values, with resolved UTC timestamps stored
separately.

Initial states retain their provenance:

- `last_recorded_state` contains the last original Recorder row found before
  the week and its original timestamps; and
- `registry_observation` contains the relevant registry observation.

If no defensible initial state exists, the archive records `unknown`, a
provenance value and a coverage note. It does not invent a measurement.

## Disabled, renamed and removed entities

From the time the integration loads, it maintains a durable journal of entity
registration, removal, renaming, enabling and disabling. Events are stored in
order; a quick disable and re-enable remains visible as two separate events.

The literal archive-only pseudostate **`uitgeschakeld`** means
**disabled**. The Dutch literal is part of archive format version 2 and is
documented here exactly so consumers can parse existing files. It never changes
the Home Assistant entity state. After re-enabling, the effective state is
`unknown` until a new stored state arrives. `off`, `unknown`,
`unavailable` and `uitgeschakeld` remain distinct.

For Recorder rows, `state` remains the original source value. During
reconstruction, use `effective_state` only when `applies_to_state` is true.
This preserves an original `unavailable` or removal row that occurred after
disabling without allowing it to overwrite the disabled pseudostate. Registry
removal also sets `present: false`, which is different from temporary
disabling.

Changes are sorted chronologically per permanent `unique_id`. Start with
`initial_states`, then apply applicable changes for that identity where
`at <= target time`. At identical timestamps, a registry event precedes a
Recorder row. A registry event that only changes a name is not a new
measurement.

Home Assistant may apply an entity rename to existing Recorder history. The
journal preserves the permanent identity mapping. If a historical name
collision cannot be assigned unambiguously, the export stops with an error
instead of attaching measurements to a guessed identity.

A disable time from before the first registry observation is never backdated.
If an entity is already disabled when observation begins, the journal records
that state at the observed start time; coverage before that remains unknown.
After a restart, differences are observed again without inventing an exact time
for changes made while Home Assistant was stopped.

## Recorder coverage

At least **21 days of detailed Recorder history** is recommended, with all
entities for the system included. The integration checks whether Recorder is
running, its configured retention period and active exclusions. A problem
creates a Home Assistant repair issue and an Archive status note. The
integration never changes global Recorder settings.

`archive.export_complete` means the available export was written and
validated completely. It does not prove uninterrupted measurements. Always
read `archive.coverage`, which can report:

- missing initial states or registry coverage before first observation;
- possible Recorder purging;
- known Recorder interruptions or unclean runs;
- registry-observation interruptions, including an unclean Home Assistant
  session;
- current Recorder exclusions or an insufficient retention period; and
- `first_or_partial_week` for incomplete or uncertain week coverage.

An unreachable Solesta provider does not prevent the archive job from reading
Recorder. Scheduling and Recorder export are independent of provider updates.
Original `unknown` and `unavailable` states and the related coverage notes
remain visible.

## First export, catch-up and recovery

For each system, `progress.json` determines whether archive administration
already exists. On a first run without progress, the integration records the
next calendar week as the starting boundary. It can create its first archive
only after a complete week has been observed under this installation. Existing
progress resumes at its stored week. This decision is based on the system's
archive administration, not on an old or current integration domain name.

After that, every system keeps independent progress. A restart catches up on
at most four weeks per system in one run. A failed week is retained as a
separate gap and retried while the main cursor continues. Capacity is reserved
for the newest released week so that one persistently broken old week cannot
block newer exports.

While a gap exists, Archive status and the Home Assistant repair issue remain
in error and another attempt is scheduled within an hour. History already
purged by Recorder cannot be recovered and is explicitly marked missing or
uncertain. Re-enabling weekly archives triggers another catch-up check.

An export is first written to a temporary file and validated for:

- gzip and JSON integrity;
- allowed record types and required fields;
- field types and entity identities;
- exact week boundaries and per-entity chronological order;
- declared record counts; and
- SHA-256 checksum consistency.

Only then is it published atomically, without replacing an existing archive.
A completed automatic attempt advances the main cursor even if that week
remains on the retry list; an interrupted attempt does not. A corrupt existing
file is never overwritten.

Manual and automatic exports share one lock. During shutdown, an active write
has up to five minutes to finish safely. A timeout creates a general
observation interruption in the registry journal so that a later archive does
not claim continuous coverage.

The registry journal uses durable SQLite transactions and unique event
identities. Retried writes do not create duplicate events. Journal write
failures remain visible and block an export that would be unreliable without
those events. A registry change during export causes a retry with a fresh
snapshot.

The Home Assistant time zone is stored in progress. If that time zone changes,
archiving stops with an error instead of silently moving existing week
boundaries.

The implementation targets Home Assistant 2026.9.0. Relevant references:
[Recorder](https://www.home-assistant.io/integrations/recorder/), the
[2026.9 entity registry](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/helpers/entity_registry.py)
and
[Recorder entity renaming](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/recorder/entity_registry.py).
