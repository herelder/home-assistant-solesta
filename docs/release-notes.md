# Release notes — 0.2.3 to 1.0.0

Version 1.0.0 adds ESPHome Native and MQTT alongside the existing Web API
provider. Existing 0.2.3 Web API configurations are preserved during the upgrade.

## What changes

- Choose between cloud Web API, encrypted local ESPHome Native and a directly
  connected MQTT 3.1.1 broker. MQTT supports TCP/TLS and subscription QoS 0/1/2;
  it does not depend on Mosquitto, HA OS or HA's MQTT integration.
- Source fields feed one shared evaluator and entity model. MQTT states remain
  raw text and Native states retain their reported types. Source expressions
  perform conversions and give fields their meaning.
- The common observation layer provides `last_report()` and `last_update()`.
  Identical reports, retained messages and unused fields have explicit
  semantics; see [Source expressions](source-expressions.md#report-time-change-time-and-retained-messages).
- Qualified field names support nested Web API data and MQTT topics, with
  shortest-unique binding checked when configuring a system.
- Universal pump/reporting/alert calculations, grouped `null(field, ...)`,
  localized alert records and unknown values work for every provider.
- A provider switch retains permanent system/entity identity and history,
  disables systems for review, and requires explicit source/expression
  validation before reactivation. Duplicate links can be relinked independently.
- The dashboard displays local provider/system identity and keeps using HA
  states and Recorder history. It needs no provider connection of its own.
- An optional [Solesta NanoC6 ESPHome firmware kit](../esphome/public/README.md)
  reads the Solesta debug header and exposes raw data through encrypted Native
  API; MQTT publishing can be enabled in a private local secrets file. The kit
  consists of a firmware YAML, a secrets example and its README. Users build
  and flash the NanoC6 separately; the HACS integration does not flash it.

The [configuration guide](installation.md) covers setup for all three
providers. The [energy-formula comparison with Solesta](energy-calculations.md)
is retained: kWh derives from MJ, while standard-shower energy follows the
configured cold-water temperature rather than Solesta's fixed comparison value.
The kit's ESPHome project version is `0.1.2`, independent of the Solesta
integration and dashboard version `1.0.0`.

## Upgrade from 0.2.3

Create a native HA backup with settings and history before upgrading. Keep a
known matching old version and backup available. The migration uses HA's
configuration APIs; do not edit `.storage` yourself.

Permanent hub/system UIDs, config/subentry identities, entity unique
IDs, local system labels, device associations and existing history are retained.
The Web API connection remains configured. The update does not switch providers
or reset a custom mapping to the current factory defaults.

The upgrade updates configuration metadata automatically.
**Every stored source expression is preserved exactly**, including custom
formulas and source-field names. A Last reported timestamp expression of
`last_update` continues to read that raw source field.

An existing Web API source-alert recipe such as `join_lines(alerts)` can
therefore remain different from a newly created system's local alert recipe.
Review any change deliberately; it is not a hidden part of the upgrade.

After the HA restart, check devices, current values, configured sources,
reporting/alerts and the existing dashboard/history. Refresh the browser or
reopen the app so the 1.0.0 card is loaded.

## Rollback

Restore the native backup containing both the previous code and its matching
stored HA configuration. Installing old Python files over an already migrated
entry is not a supported downgrade. Keep archives and recorded history private;
use the normal HA backup/restore route, not an SMB copy of a running database.

## MQTT limitations

The documented broker profile excludes WebSockets, private-CA configuration,
client certificates and broker discovery. TLS validates against the system
certificate store. Measurement validity is a source-expression decision, not
an interpretation of availability topics, frame counters or transport metadata.

## Known release boundaries

The completed 0.2.3-to-1.0.0 upgrade trial used an isolated Home Assistant Core
2026.11.2 environment under macOS. It exercised the real configuration-entry
migration, providers, entities, Recorder history, dashboard resource and
backup-based recovery, but it was not a full HA OS/Supervisor acceptance. See
the [upgrade acceptance report](results/solesta-0.2.3-to-1.0.0-upgrade-acceptance-2026-11-18.md)
for the tested scope and retained data.

The dashboard card remains functionally usable, but unusually narrow dashboard
columns can clip part of the top bar or the status-explanation popover. Normal
and wider layouts, history interaction and the underlying status calculations
passed their acceptance checks. These two narrow-layout findings are documented
in the [frontend acceptance report](results/frontend-acceptance-2026-11-18.md).
