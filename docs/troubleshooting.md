# Troubleshooting

## The integration is not available after HACS installation

- Confirm that the custom repository type is **Integration**.
- Confirm that HACS downloaded a directory named
  `custom_components/solesta`.
- Restart Home Assistant; reloading the browser alone is not sufficient after
  installing Python integration files.
- Check **Settings → System → Logs** for an error mentioning `solesta`.

The integration requires Home Assistant 2026.9.0 or newer.

## Authentication or connection fails

- Verify the same user ID and password at
  `https://dashboard.solesta.nl`.
- Confirm that the Home Assistant host has working internet access and correct
  date and time.
- A temporary Solesta service problem can produce **Failed to connect** even
  when the credentials are correct.
- Use the Home Assistant reauthentication prompt or provider
  **Reconfigure** action after changing the account password.

The configured service address is fixed to HTTPS. Do not put credentials or an
authenticated web response in a public issue.

## The provider hub exists but there is no device

A provider hub and a solar water heater are separate configuration levels.
Open the Solesta entry and use **Add system**. After adding it, open
**Reconfigure system**, turn on **Enabled**, and submit the form. New systems
are initially disabled by design.

If **Add system** reports that no systems are available, confirm that the
system is linked to the Solesta account and has not already been added to that
hub.

## Entities are unavailable or updates stop

- Check **Reporting status** and **Report delay** on the device.
- Confirm that the system is still enabled under **Reconfigure system**.
- Confirm that the provider dashboard currently reports the selected system.
- If only calculated entities are unavailable, inspect their dependencies such
  as both tank temperatures, tank capacity and cold-water temperature.
- Download diagnostics from the Home Assistant integration page. Diagnostics
  list evaluation-error categories without including raw provider values or
  credentials.

A reporting problem in the Solesta system or cloud service cannot be repaired
by the community integration. Use Solesta support for account, hardware and
service-side faults.

## The dashboard card is missing

1. Restart Home Assistant.
2. Fully refresh the browser page, or close and reopen the mobile app.
3. Confirm that at least one Solesta system is enabled.
4. Search for **Solesta system status** in the card picker.

For YAML-managed Lovelace resources, add the resource shown in
[Dashboard card](dashboard.md#yaml-managed-dashboard-resources). Do not add a
second `lovelace:` section.

## The card still shows an old design

The JavaScript bundle is cached by the browser. After every integration update,
restart Home Assistant and perform a full browser refresh. The installed
resource URL must end with the same version as the integration, for example:

```text
/solesta/solesta-status-card.js?v=0.2.3
```

When resources use Home Assistant storage mode, the integration updates the
resource and removes duplicate legacy entries automatically. Never edit
Home Assistant's `.storage` files for this purpose.

## The card reports missing entities or a missing system

Open the card editor and select the intended solar water heater again. This is
especially important after removing and recreating the integration, because the
new Home Assistant device may have a different device ID.

The card obtains required entities from the selected device. Ensure that the
normal temperature, energy, pump, reporting and alert entities are enabled.
Cold-water temperature is also required for a complete preheated-water status.

## Temperature history is unavailable

The chart reads the tank-temperature entity's Home Assistant Recorder history.
Check that:

- Recorder is running;
- the tank-temperature entity is not excluded from Recorder;
- the entity has recorded numeric values; and
- the signed-in Home Assistant user may read history.

Unknown periods are intentionally shown as gaps. On a temporary history API
error, the card keeps the last usable chart and retries with a bounded delay.

## A weekly archive is not created

- Turn on **Weekly source archive** for that device.
- Only completed calendar weeks can be exported.
- Automatic export runs on Monday at 00:15 in the Home Assistant time zone.
- Inspect **Archive status** and its attributes for the week, last error,
  Recorder warnings and coverage warnings.
- Go to **Developer tools → Actions → Solesta: Archive week** to request a
  catch-up or a specific completed ISO week.

Recorder history that has already been purged cannot be recovered. At least 21
days of detailed Recorder history is recommended. See
[Weekly source archives](archive.md) for coverage and recovery semantics.

## Before opening an issue

Search existing issues and reproduce the problem on the newest release. Include:

- the Solesta integration version;
- the Home Assistant version;
- the affected area and exact steps;
- what you expected and what happened; and
- carefully reviewed Home Assistant diagnostics or a short sanitized log
  excerpt.

Never upload passwords, cookies, tokens, addresses, system identifiers,
authenticated responses, Home Assistant databases, `.storage` files or
weekly archive files.
