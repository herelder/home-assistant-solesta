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
| Last reported timestamp | Disabled | date/time | Locally observed last-report time from `last_report()` |
| Unused temperature | Disabled and hidden | °C | Reserved fourth temperature value, not used by the normal presentation |

The stored-energy formulas and their assumptions are documented in
[Energy calculations](energy-calculations.md).

## Diagnostic entities

| Entity | Type | Meaning |
| --- | --- | --- |
| Report delay | Sensor | `[0,150]` for a report no more than 150 seconds old, `[151,600]` up to 10 minutes, or the last-report UTC timestamp when older |
| Pump status | Running binary sensor | On when the pump percentage is greater than zero |
| Reporting status | Connectivity binary sensor | Derived locally from Report delay: on through 600 seconds, off afterwards, and unknown without a last report; the bundled card selects this entity when displaying `provider_id/system_id` |
| Alert lines | Sensor | Alert records from the configured expression; the factory expression derives local alerts. Records are separated by ASCII Record Separator; complete long records are also available in attributes |
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
| Update interval | 15 s | 15–3600 s, steps of 15 s | Provider refresh interval for this system |
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

Use `null()` to produce no value, `null(field)` to read a nullable field, or
`null(field, ...)` to collect an ordered list of field values with null at
missing positions. Each argument must be one source/entity field or an
expression/constant without fields. For a conversion, write
`to_number(null(field))`; calculations involving fields are not accepted as
arguments of `null(...)`. The function does not suppress calculation errors.

`None` and `none` in an expression are ordinary case-sensitive field names.
Use `null()` for the internal absent value, which Python calls `None`.
Zero, `False` and empty text remain their original values. A nullable consumer
can read a failed entity as absent while that entity's original diagnostic
error remains visible. A raw source becomes optional for provider validation
only when all references to it are inside `null(...)`.

Pump state uses `perc_pump_pwm > 0`. The factory alert expression collects its
four nullable fields as
`null(status_reporting, state_pump, temp_collector, temp_tank_top)` and follows
that list with `90, 200, 10, 10`. Change thresholds by editing and validating
`alerts_system`. Missing pump data therefore does not prevent independent
collector alerts. An internally absent result is a valid unknown state for
sensor, binary-sensor and number entities.

Every system entity exposes the same generic `provider_id`, `system_id` and
diagnostic `provider_protocol` attributes. Selecting the reporting entity as
the dashboard's identity source is a dashboard responsibility, not an entity
platform special case.

The default expression set is generated from
`tools/sources/EntityDescriptions.xlsx`. Contributors should update the
workbook and regenerate the catalog instead of editing
`custom_components/solesta/thetruth.py` directly.

Factory expressions are independent of provider type. Review and edit source
expressions manually when changing provider; a switch never rewrites source
field mappings. The upgrade from production 0.2.3 preserves all stored
expressions literally and updates metadata only; see
[Release notes](release-notes.md#upgrade-from-023). Current factory defaults
apply to new systems; existing mappings are not reset to those defaults.

See [Source expressions](source-expressions.md) for a full tutorial, provider
examples, qualified field names, missing values, timestamps and validation.
The current alert factory derives local alerts from four optional local inputs.
This four-input group followed by four constant thresholds is the only supported
`solar_thermal_alerts()` form. To display provider alert text, configure
**System alerts source expression** with an expression such as
`join_lines(alerts)`, using the actual source field name. Existing Web API
expressions of that form are preserved literally during upgrade.
