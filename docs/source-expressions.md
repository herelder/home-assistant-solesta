# Source expressions

A source expression is the recipe for one Solesta entity. It reads a provider
field, calculates from other entities, returns a fixed setting or calls an
allowed helper. The same evaluator serves Web API, ESPHome Native and MQTT.
The transport does not decide a value's meaning or unit.

Follow [Installation and configuration](installation.md) to reach **Configure
system** or **Reconfigure system**. Enter only the expression in its field,
without an assignment, entity name or YAML wrapper.

## Start with a value

| Expression | Meaning |
| --- | --- |
| `to_number(temp1)` | Convert an offered provider field to a number |
| `round((temp_tank_top + temp_tank_bottom) / 2, 1)` | Calculate from two Solesta entities |
| `100` | Use a fixed number, for example tank capacity in litres |
| `last_report()` | Ask for the locally observed report time |

`temp_tank_top` is an internal entity key, not an HA entity ID such as
`sensor.solar_tank_temperature`. Renaming an HA entity does not alter these
references. Names are case-sensitive.

A reference to another configured entity creates a dependency on its value.
To explicitly read an equally named provider field, append one apostrophe:

```text
to_number(temp_collector')
```

The apostrophe marks a source reference; it is not an opening quote. A field's
own name in its own expression also resolves as a source. Use the explicit
mark when a provider field and another entity share a name.
An own-name source uses the same path and uniqueness rules as other source
references; qualify it if more than one offered path matches.

## Find the actual source fields

Consult the publisher/node configuration or inspect the provider's offered
data. For an active system, **Devices & services → Solesta → Download
diagnostics** lists `available_source_keys` and error categories without raw
values or credentials. The first mapping may need the source's documentation
because that system is not running yet.

For MQTT, a broker topic viewer or the separate HA MQTT integration's
**Listen to a topic** can show messages under the chosen root. This is an
inspection aid, not a Solesta dependency. Check sample values and units as well
as names. A successful broker connection does not establish that a pump value
is a fraction, a percentage or even a number. Review inspection output before
sharing; topics can identify an installation.

### Paths and short unique names

Nested Web API objects and relative MQTT topics retain their structure.
MQTT payloads remain UTF-8 text; the provider does not parse JSON payloads
into additional fields. Native keys are the reported `object_id` values
within the selected device.

An expression name reads segments from the leaf outward, joined by `__`:

| Offered source path | Canonical expression name |
| --- | --- |
| JSON field `metrics/temp1` | `temp1__metrics` |
| Relative MQTT topic `sensor/tank/state` | `state__tank__sensor` |
| Native object ID `temperature_1_raw` | `temperature_1_raw` |

With root `solar/bridge_a`, topic `solar/bridge_a/sensor/tank/state` uses
`state__tank__sensor`. The root identifies the system and is not part of the
relative field path.

You may use the shortest name that uniquely selects an offered full path. If
both `sensor/tank/state` and `sensor/collector/state` exist, `state` is ambiguous;
use `state__tank` and `state__collector`. Even an exact short name has no
priority over a matching longer candidate. Binding is frozen for a
configuration revision: a new topic cannot silently redirect an existing
expression. Reconfiguration rebuilds and validates the field table.

Special characters are encoded without losing segment boundaries. For example,
`sensor/boiler-1/state` becomes `state__boiler_02D1__sensor`. Copy a reported
canonical name if unsure. The exact [encoding contract](decisions/0008-provider-observation-and-timestamps.md#canonieke-expressienaam)
covers escapes, empty levels and consecutive underscores.

Prefix `_0R__` to select one exact complete path. This also explicitly declares
an optional field that has not appeared yet:

```text
to_number(null(_0R__state__extra__sensor))
```

An unknown required field still fails validation. An absolute name is not a
wildcard or a way to make up missing data.

## Worked mappings

These are examples of possible source layouts, not automatic mappings for
every device. Check your actual keys, units and ranges.

| Entity | Web API example | Native example | MQTT example |
| --- | --- | --- | --- |
| Collector temperature | `to_number(temp1)` | `to_number(temperature_1_raw)` | `to_number(state__collector)` |
| Tank top temperature | `to_number(temp2)` | `to_number(temperature_2_raw)` | `to_number(state__tank_top)` |
| Tank bottom temperature | `to_number(temp3)` | `to_number(temperature_3_raw)` | `to_number(state__tank_bottom)` |
| Pump percentage | `to_number(pump)` | `to_number(pump_raw) * 100` | `to_number(state__pump) * 100` |
| Last reported timestamp | `last_report()` | `last_report()` | `last_report()` |

The MQTT column assumes relative topics `sensor/collector/state`,
`sensor/tank_top/state`, `sensor/tank_bottom/state` and `sensor/pump/state`.
Native/MQTT pump examples assume a fraction from 0 to 1. If already expressed
as 0–100 percent, omit `* 100`. The provider does not infer this from its name.

For the bundled **Solesta NanoC6 firmware**, use the complete
[kit mappings](../esphome/public/README.md#source-expressions). Its MQTT topics
use `temperature_1_raw` through
`temperature_3_raw` and `pump_raw`, rather than the illustrative topic names
above. Firmware 0.1.2 supplies a source field `last_report` containing the UTC
time of the last complete valid UART frame. Map the Native entity's expression
to `last_report` to use that device time with the normal report-age logic.
The field is distinct from the transport-observation function `last_report()`.
Other sources need no such field; their explicitly chosen transport mapping
remains valid. Updating firmware does not rewrite existing MQTT expressions.

After normalizing those inputs, use shared calculations. Average tank
temperature can remain:

```text
round((temp_tank_bottom + temp_tank_top) / 2, 1)
```

Pump state can remain:

```text
perc_pump_pwm > 0
```

Energy formulas then use the normalized entities. The
[energy calculations and intentional differences from Solesta](energy-calculations.md)
apply equally to all three providers.

## Values, operators and helpers

Numbers use a decimal point, such as `12.5`; booleans are `True` and `False`.
Text uses single or double quotes. Call `null()` for the absence of a value.
That internal value is called Python `None`; it differs from `0`, `False` and
an empty string. In a source expression, **`None` and `none` are ordinary,
case-sensitive field names**, never null literals. For example, `None` reads
the field named `None`, while `"None"` is text and `null()` produces no value.

Supported operators are arithmetic `+ - * / %`, comparisons `== != < <= > >=`,
and `and`, `or`, `not`, with parentheses. Arithmetic requires finite numbers;
it does not concatenate strings or treat booleans as numbers. The language
does not allow assignments, imports, attributes, indexing, list/dictionary
literals, comprehensions, lambdas, Jinja templates or `**`. Calls use
positional arguments. Size, depth and numeric limits also apply.

| Helper | Meaning |
| --- | --- |
| `to_number(value)` | Finite numeric conversion; numeric text including decimal comma is accepted, `None` stays unknown, booleans are rejected |
| `round(value, digits)` | Round a finite number; integer digits from -15 to 15 |
| `null(field, ...)` | No arguments: no value; one argument: its value; multiple arguments: an ordered list. Missing fields give the internal null value |
| `last_report()` | Most recent accepted report time in UTC, or `None` |
| `last_update()` | Most recent change time among this system's referenced source fields, or `None` |
| `delay_zone(timestamp, border, ...)` | Inclusive report-age zones, or an older UTC timestamp; borders are increasing positive constant whole seconds |
| `is_timestamp(value)` | Check for a supported timestamp representation |
| `join_lines(value, ...)` | Join non-empty scalar values or a flat list/tuple into record-separated text |
| `solar_thermal_alerts(null(...), hot, danger, idle_delta, active_delta)` | Shared solar-thermal diagnostics; see below |

### Dependencies and unknown values

An entity is evaluated after the entities it depends on. A failed required
dependency blocks its dependent; unrelated entities can still work. Circular
references are rejected. Correct missing or invalid measurements rather than
substituting zero for a temperature you do not know.

Logical `and` and `or` short-circuit and return an operand, not necessarily a
boolean. Compile-time dependency validation still applies. The factory
reporting expression is:

```text
report_delay and not is_timestamp(report_delay)
```

When `report_delay` is `None`, its result is `None`; a non-empty zone such as
`"[0,150]"` gives `True`; an older timestamp gives `False`. Numeric zero on
the left returns zero, so do not use an arbitrary number when a binary sensor
expects a boolean. Binary sensors can be unknown (`None`).

### Null values and missing fields

`null()` has three forms:

| Expression | Result |
| --- | --- |
| `null()` | The internal null value (Python `None`) |
| `null(temperature)` | The field's value, or null if the field is absent or has no value |
| `null(temperature, pump, 10 * 2)` | An ordered list, keeping each available value and substituting null for each missing field |

A single argument keeps its value and type, including `0`, `False`, empty
text and a list-valued source. Multiple arguments always return a list; source
lists are not flattened.

**Each argument must be either one source/entity field, or an expression or
constant containing no fields.** These examples are valid:

```text
null(status_reporting, state_pump, temp_collector, temp_tank_top)
null(10 * 2, round(12.25, 1), "not reported")
to_number(null(maybe_missing))
```

Perform calculations or conversions involving fields outside `null(...)`.
For example, `null(to_number(temp1))` and `null(temp1 > 0)` are rejected during
configuration. Use `to_number(null(temp1))` for the conversion.

Missing short field names are accepted within `null(...)`; they give null
when no matching field exists. Existing short names must still select one
unambiguous full path. An ambiguous name remains a configuration error.
Use an absolute name when the intended complete path must be explicit:

```text
to_number(null(_0R__maybe_missing))
```

A field is exempt from required-source validation only when every reference
to it is inside `null(...)`. Referencing it elsewhere still makes it required.
All referenced fields, including nullable ones, count towards `last_update()`.

`null(entity_field)` reads that entity's current result. If the entity failed,
its result is null and its original error remains in diagnostics. The nullable
consumer can still run; it does not make the raw inputs of that entity's own
expression optional.

`null()` does not catch calculation or conversion errors. For example,
`null(1 / 0)` still reports division by zero, and an existing nonnumeric field
still fails `to_number(null(field))`. Syntax, allowed functions, cycles and
resource limits remain validated. Keyword arguments are not supported.

## Report time, change time and retained messages

`last_report()` advances for every successful Web API status poll and every
received Native callback or MQTT PUBLISH, including identical values and
unused fields. Connection events alone do not count. It records local
observation, not the publisher's measurement time or proof of a new complete
physical measurement frame.

`last_update()` uses all raw fields referenced by this system, including
optional fields. First observation establishes a baseline and counts as a
change; a subsequent value/type change advances change time again. Identical
values and changes to unused fields do not. Duplicate systems can have different
change times if they reference different fields.

Reconnect within the same provider instance preserves its cached baseline.
MQTT retained replay counts as a report, but only a differing referenced value
counts as a change. A new process/provider instance starts with an empty cache;
its first observed referenced values count as changes again.
A retained value can describe an old physical measurement: a recent report
time does not prove measurement freshness. Explicitly use a source measurement
timestamp or validity field when your publisher provides one with that
documented meaning. Availability/LWT topics, frame counters and status texts
receive no special interpretation from the provider.

A bare `last_update` field is distinct from `last_update()`. The factory Last
reported timestamp uses `last_report()`. The factory Report delay uses
`delay_zone(last_report, 2*60+30, 10*60)`, where `last_report` refers to the
entity. Its zones cover ages through 150 and 600 seconds inclusive; older
reports produce the normalized UTC timestamp.

## Universal alerts

The current factory **System alerts source expression** is:

```text
solar_thermal_alerts(null(status_reporting, state_pump, temp_collector, temp_tank_top), 90, 200, 10, 10)
```

Constants specify collector warning temperature (°C), collector danger
temperature (°C), idle-pump delta (K) and active-pump delta (K). Change them by
editing and validating this expression. These diagnostic thresholds are configurable; they are not universal
safe operating limits for every heater.

| Condition | Result |
| --- | --- |
| Reporting is `False` | Exclusive offline/danger record |
| Reporting is `True`, collector > danger | Collector-hot/danger |
| Reporting is `True`, warning < collector ≤ danger | Collector-hot/warning |
| Pump off, collector > tank top + idle delta | Pump-idle/warning |
| Pump on, collector < tank top - active delta | Pump-active/warning |
| Pump on, tank top - active delta ≤ collector < tank top | Pump-active/info |

Temperature/pump rules require reporting `True` and their relevant usable
inputs. Missing pump data does not suppress an independent collector rule.
Unknown reporting is not offline. Saving validates constant finite
collector limits with danger above warning and finite non-negative deltas.

The helper accepts exactly four grouped optional inputs followed by four
constant thresholds. It derives local alerts only; it does not accept or merge
an extra source-alert argument. To use provider-supplied alert text instead,
configure a separate expression such as `join_lines(alerts)`, using the actual
qualified field name where necessary. Existing Web API expressions of that
form are preserved during upgrade.

Records use ASCII Record Separator (`U+001E`); CR/LF remains supported for
legacy input. Newlines inside a valid JSON text field do not split records.
Long HA sensor states are shortened; complete records remain in attributes
for the card.

## Defaults, settings and editing safely

Factory expressions are the same for all providers. They are starting values,
not automatic source mapping. In the source-expression configuration form:

- Enter a **single space** to reset an expression to its current **factory
  value** when the form is validated.
- **Clear the field completely** during reconfiguration to restore the value
  it had **at the start of that reconfiguration**, rather than the factory value.

Unchanged or omitted existing fields keep their stored expressions.

Validation errors appear beside the affected expression fields, with separate
reasons for syntax, function arguments, missing or ambiguous source fields,
invalid values and failed dependencies. Multiple fields can be marked in one
submission. A circular reference marks the expressions forming the cycle.
Connection and authentication failures remain general form errors.

Setting an adjustable number entity in HA replaces its expression with a
fixed literal. Setting **Energy per shower** manually therefore stops that
setting following the cold-water formula until you restore the formula.
Weekly archive is configured as a boolean switch, not a free-text expression.

Keep a backup and privately record the old mapping. Edit the smallest necessary
set, submit, resolve errors, and check normalized measurements, reporting and
energy before relying on the dashboard. Useful internal keys are:

| Group | Keys |
| --- | --- |
| Measurements | `temp_collector`, `temp_tank_top`, `temp_tank_bottom`, `perc_pump_pwm` |
| Derived status | `temp_tank_average`, `state_pump`, `status_reporting`, `alerts_system` |
| Settings | `volume_tank`, `temp_coldwater`, `energy_shower_kwh`, `update_interval` |
| Energy | `energy_tank_mj`, `energy_tank_kwh`, `energy_tank_showers` |
| Reporting entities | `last_report`, `report_delay` |

The reserved temperature defaults to `null()` and is normally hidden. A
publisher offering a fourth measurement does not itself require you to map it.

Provider switches retain mappings and disable systems until you review and
validate them. The upgrade from production 0.2.3 updates metadata and preserves
all stored expressions literally, including a raw field named `last_update`.
See [Release notes](release-notes.md#upgrade-from-023). A transport does not
rewrite expressions to match its own source names.

For validation failures, check spelling/qualification and raw type first, then
the original dependency and allowed ranges. See
[Troubleshooting](troubleshooting.md) for source, cycle and value errors.
