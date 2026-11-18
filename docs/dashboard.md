# Dashboard card

Solesta 1.0.0 includes the matching
`frontend/solesta-status-card.js` card bundle. The card presents current
system status and Home Assistant history without embedding or reusing the
Solesta web dashboard.

## Add the card

1. Restart Home Assistant after installing or updating the integration.
2. Fully refresh the Home Assistant page, or close and reopen the mobile app.
3. Edit a dashboard, choose **Add card**, and select
   **Solesta system status**.
4. Choose the solar water heater and save the card. When exactly one eligible
   device is available, the editor selects it automatically.

The card resolves entities from the selected device and the integration's
stable entity keys. You do not maintain a list of entity IDs. Renamed entities
are resolved again after Home Assistant supplies the updated entity registry.

The selected device must provide the normal tank, collector, energy, pump,
reporting and alert entities. Cold-water temperature is also needed for a
complete preheated-water statement. If that setting is temporarily unknown,
the card reports incomplete system data and does not make a preheated-water
claim.

The visual editor supports these optional settings:

| Setting | Purpose |
| --- | --- |
| Display name | Overrides the device name shown at the top of the card |
| Return path | Navigates to this path when the card's close button is used |
| Fit to available screen height | Scales the card down when necessary; enabled by default |

English and Dutch card text is supplied by the integration translations.

By default, the card shows the stable local identity as
`provider_id/system_id`, both in the header and in the last-report footer. An
explicit display name always remains a fixed custom name, even when its text
is `Web API` or `ESPHome Native`. Leave the display name empty to follow the
provider/system identity after a provider switch.

## Current presentation

The layout contains:

- an independent community mark and the selected system name;
- a prominent average tank temperature and preheated-water indication;
- reporting, stored-energy, shower, pump and alert status;
- a live schematic of the collector, pump and storage tank; and
- switchable **Today** and **seven days** tank-temperature history.

The lower circulation line in the schematic runs from right to left while the
pump is active, representing the return flow from the tank to the collector.
Informational and warning collector/pump observations use the normal status
presentation. Alerts with severity `danger`, `error` or `critical` use the red
attention presentation, including a dangerously hot collector. A
`pump_active` alert keeps the locally evaluated `info` or `warning` severity.

The overall normal status requires valid tank-average, tank-top, tank-bottom,
collector, cold-water, energy and shower values, together with known pump,
reporting and alert states. A missing measurement produces the incomplete-data
status. An offline connection or independent severe alert retains its higher
priority.

The main temperature is the average of the measured top and bottom tank
temperatures. The preheated-water wording compares it with the configured
cold-water temperature:

- below cold-water temperature + 5 °C: **slightly preheated water**;
- at least cold-water temperature + 5 °C, but below cold-water temperature
  + 15 °C: **preheated water**; and
- at least cold-water temperature + 15 °C: **strongly preheated water**.

When reporting is offline, the card asks you to check the system and connection. The
**Last status change** timestamp covers changes in component values, derived
values and the communication link. Select the adjacent information icon for
this explanation in the card.

The displayed MJ, kWh and standard-shower values come from Home Assistant
entities. See [Energy calculations](energy-calculations.md) for the assumptions
and the intentional difference from the Solesta web dashboard formulas.

## Temperature history

The chart uses the tank-water-temperature entity's Home Assistant Recorder
history. It follows the configured Home Assistant time zone, including
daylight-saving transitions. Each local day begins at its first valid instant;
when a transition skips midnight, the chart starts at the actual local start
time. An unresolvable day boundary replaces only the chart with an unavailable
message.

The card does not invent measurements between recorded state changes:

- the last known numeric value remains in effect until a new state change;
- an unknown or unavailable period breaks the line;
- averages are weighted by the amount of time each value was in effect;
- the seven-day view shows the minimum, weighted average and maximum per day;
  and
- the today view shows the day's full range and the timeline up to the current
  local time.

Daily statistics and the interactive cursor use the complete recorded series.
Only the drawn line is reduced for display, retaining extrema with their next
state and every transition into or out of an unknown period. Gap boundaries
take precedence over the usual drawing budget of 720 points.

History requests are bounded and refreshed periodically. If the history API
temporarily fails, the last usable chart remains visible with a warning while
the card retries with an increasing delay capped at 15 minutes.
