# Dashboard card

Integration version 0.2.3 includes the matching
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

## Current presentation

The 0.2.3 layout contains:

- an independent community mark and the selected system name;
- a prominent average tank temperature and preheated-water indication;
- reporting, stored-energy, shower, pump and alert status;
- a live schematic of the collector, pump and storage tank; and
- switchable **Today** and **seven days** tank-temperature history.

The lower circulation line in the schematic runs from right to left while the
pump is active, representing the return flow from the tank to the collector.
Normal collector and pump observations are shown as healthy status information.
Only provider alerts that require attention use the alert presentation.

The main temperature is the average of the measured top and bottom tank
temperatures. The preheated-water wording compares it with the configured
cold-water temperature:

- below cold-water temperature + 5 °C: **slightly preheated water**;
- at least cold-water temperature + 5 °C, but below cold-water temperature
  + 15 °C: **preheated water**; and
- at least cold-water temperature + 15 °C: **strongly preheated water**.

When reporting is offline, the card advises contacting Solesta support. The
**Last status change** timestamp covers changes in component values, derived
values and the communication link. Select the adjacent information icon for
this explanation in the card.

The displayed MJ, kWh and standard-shower values come from Home Assistant
entities. See [Energy calculations](energy-calculations.md) for the assumptions
and the intentional difference from the Solesta web dashboard formulas.

## Temperature history

The chart uses the tank-water-temperature entity's Home Assistant Recorder
history. It follows the configured Home Assistant time zone, including
daylight-saving transitions.

The card does not invent measurements between recorded state changes:

- the last known numeric value remains in effect until a new state change;
- an unknown or unavailable period breaks the line;
- averages are weighted by the amount of time each value was in effect;
- the seven-day view shows the minimum, weighted average and maximum per day;
  and
- the today view shows the day's full range and the timeline up to the current
  local time.

History requests are bounded and refreshed periodically. If the history API
temporarily fails, the last usable chart remains visible with a warning while
the card retries with an increasing delay capped at 15 minutes.

## Existing dashboards and resource migration

The current card configuration uses a `device_id`. Old configurations that
contain a manually maintained `entities:` section are not supported. Open
such a card in the visual editor and select the solar water heater again.

At startup, Solesta registers its bundled card as a dashboard resource. Old
local resource paths and duplicate resources for this card are migrated to one
current resource, preventing different bundle versions from competing for the
same custom element.

The bundled resource for this release is:

```text
/solesta/solesta-status-card.js?v=0.2.3
```

The version parameter changes with each integration release. A browser page
that was already open must still be fully refreshed after an update.

## YAML-managed dashboard resources

When Lovelace resources are managed in YAML, the integration can register the
static file path but cannot edit the YAML resource list. It writes the required
resource to the Home Assistant log.

Add the following module to the existing `lovelace.resources` list in
`configuration.yaml`, replacing any old resource for the Solesta status card:

```yaml
lovelace:
  resource_mode: yaml
  resources:
    - url: /solesta/solesta-status-card.js?v=0.2.3
      type: module
```

Do not create a second `lovelace:` section when one already exists. Reload
dashboard resources or restart Home Assistant, then fully refresh the browser.

A minimal YAML card configuration uses the device ID from Home Assistant:

```yaml
type: custom:solesta-status-card
device_id: REPLACE_WITH_DEVICE_ID
```

The visual editor fills in this ID automatically. Removing and recreating the
integration can produce a new device ID; select the device again if that
happens.

## Installation check

- The card appears in the card picker and can be added without a manual entity
  list.
- The editor offers only eligible Solesta solar water heaters and displays
  their correct device names.
- Missing required entities produce a clear message and do not make the card
  silently select a different system.
- Current status and history stay isolated between devices when multiple
  systems are configured.
- The card resource and saved options survive an integration reload or Home
  Assistant restart.

The implementation targets Home Assistant 2026.9.0. Static files are
registered with Home Assistant's asynchronous static-path API; storage-mode
resources use the Lovelace resource collection and the integration never edits
`.storage` directly.

Relevant Home Assistant references:
[custom cards](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/),
[asynchronous static paths](https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/)
and the
[2026.9 resource collection](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/lovelace/resources.py).
