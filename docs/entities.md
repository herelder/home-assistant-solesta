# Entities and settings

Each enabled solar water heater is represented by its own Home Assistant device.
Entity IDs are initially derived from the System ID, but the integration tracks
entities by permanent internal identity. Renaming an entity in Home Assistant
does not change its source mapping.

## Measurement and calculated sensors

| Entity | Default | Unit | Meaning |
| --- | --- | --- | --- |
| Collector temperature | Enabled | °C | Temperature reported by the solar collector sensor |
| Tank top temperature | Enabled | °C | Temperature reported at the top of the storage tank |
| Tank bottom temperature | Enabled | °C | Temperature reported at the bottom of the storage tank |
| Tank water temperature | Enabled | °C | Average of the top and bottom tank temperatures |
| Pump PWM percentage | Enabled | % | Reported pump drive percentage |
| Tank energy in MJ | Enabled | MJ | Calculated energy above the configured cold-water temperature |
| Tank energy in kWh | Enabled | kWh | The same stored energy converted from MJ |
| Tank energy in showers | Enabled | — | Stored energy divided by the configured energy per standard shower |
| Last reported timestamp | Disabled | date/time | Provider timestamp of the last system report |
| Unused temperature | Disabled and hidden | °C | Reserved fourth temperature value, not used by the normal presentation |

The stored-energy formulas and their assumptions are documented in
[Energy calculations](energy-calculations.md).

## Diagnostic entities

| Entity | Type | Meaning |
| --- | --- | --- |
| Report delay | Sensor | `[0,150]` for a report no more than 150 seconds old, `[151,600]` up to 10 minutes, or the last-report UTC timestamp when older |
| Pump status | Running binary sensor | On when the pump percentage is greater than zero |
| Reporting status | Connectivity binary sensor | On when the provider reports the system as online |
| Alert lines | Sensor | Provider alert messages joined as lines; long content is also available in attributes |
| Last successful weekly export | Timestamp sensor | Time of the most recent successful archive creation or validation |
| Archive status | Enum sensor | `waiting`, `disabled`, `ok`, `warning` or `error`, with details in its attributes |

## Adjustable settings

These are Home Assistant number or switch entities. A change is validated and
written back to that system's stored configuration.

| Entity | Default | Allowed values | Effect |
| --- | ---: | --- | --- |
| Tank capacity | 100 L | 1–250 L, steps of 1 L | Used by the stored-energy calculation |
| Cold-water temperature | 12 °C | 0–20 °C, steps of 1 °C | Baseline for energy and preheated-water calculations |
| Energy per shower | Calculated | 0.00001–10 kWh | Divisor used for the number of standard showers |
| Update interval | 15 s | 15–3600 s, steps of 15 s | Cloud polling interval for this system |
| Weekly source archive | Off | On or off | Enables automatic and manual weekly exports for this system |

The configuration entities may be hidden from the default device controls even
though they are enabled. Open the device's full entity list to find them.

Changing the cold-water temperature recalculates the default shower energy only
while the shower-energy source expression still refers to it. Setting **Energy
per shower** directly replaces that expression with a fixed numeric value. The
same rule applies to all writable number entities: a manual value becomes that
entity's stored literal.

## Source expressions

The system configuration maps provider values to entities through a small,
validated expression language. Some entities depend on other Solesta entities;
for example, tank energy depends on tank temperature, tank capacity and
cold-water temperature. A missing required provider value or a failed
dependency makes the affected entity unavailable and is recorded as an
evaluation error.

The default expression set is generated from
`tools/sources/EntityDescriptions.xlsx`. Contributors should update the
workbook and regenerate the catalog instead of editing
`custom_components/solesta/thetruth.py` directly.
