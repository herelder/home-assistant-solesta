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

First check the selected provider; its credentials and network route differ.

### Web API

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

### ESPHome Native

- Use a host/IP and the node's encrypted API port, usually 6053. An empty
  mDNS list can be bypassed with manual address entry; encryption is still
  required.
- Use `api.encryption.key`, not an MQTT or Wi-Fi password.
- Confirm that the node is reachable from HA. Internet access on the Nano is
  not required for this route.
- A confirmed MAC mismatch is an identity failure, not an address lookup hint.
  Check which physical node is at the address rather than bypassing the check.

### MQTT

- Verify host/IP, actual listener port, credentials and subscription rights.
  Do not put `mqtt://`, a topic path or a URL in the host field.
- Match **Use TLS** to the listener. Certificate/hostname failures require a
  valid trusted certificate and matching host; verification cannot be disabled
  in the form.
- Confirm the publisher sends under the exact configured root. Enter the root
  without wildcards or trailing slash; the integration adds `/#` itself.
- A connected broker without received source data cannot complete initial
  MQTT-system validation. Keep the publisher running while submitting.
- An availability or LWT topic is an ordinary source field. It does not
  automatically toggle Solesta reporting status. Review the timestamp/validity
  expression you actually configured.
- Reconnect and retained replay follow the shared observation rules; see
  [report and change time](source-expressions.md#report-time-change-time-and-retained-messages).

MQTT does not need the HA MQTT integration. Stopping one Solesta hub does not
stop the broker or other clients.

## The provider hub exists but there is no device

A provider hub and a solar water heater are separate configuration levels.
Open the Solesta entry and use **Add system**. After adding it, open
**Reconfigure system**, turn on **Enabled**, and submit the form. New systems
are initially disabled by design.

If **Add system** reports that no systems are available, confirm that the
system is linked to the Solesta account and has not already been added to that
hub.

For Native, check the devices actually offered by the selected node. MQTT has
no discovered-system list: add a root manually and validate its source data.

## Source-expression validation fails

Check the messages beside the individual source-expression fields. Validation
can identify several errors in one submission, including missing or ambiguous
source names, syntax, function arguments and invalid result values. For a
circular dependency, the expressions forming the cycle are marked; unrelated
expressions are not. Fix an original error before a dependent expression.
General connection or authentication errors apply to the provider rather than
one expression.

| Symptom | What to check |
| --- | --- |
| Unknown/missing source | Actual field name, selected system/root and received messages |
| Ambiguous field | Add outer path segments, such as `state__tank`, or use the exact absolute path |
| Invalid type/number | Convert numeric text with `to_number`; check units, decimal text and non-finite values |
| Failed dependency | Fix the original referenced entity before its dependent calculation |
| Dependency cycle | Remove the circular entity reference; apostrophe marks a raw field where needed |
| Division by zero | Check the divisor, especially energy per shower |
| Invalid alert thresholds | Use finite constant expressions, danger above warning and non-negative deltas |

The [source-expression guide](source-expressions.md) covers syntax, ordinary
`None`/`none` fields, `null()` and `null(field, ...)`, paths and examples. Enter
one space to restore the current factory expression on validation. Clearing
a field completely during reconfiguration restores its value from the start
of that reconfiguration.

## Entities are unavailable or updates stop

- Check **Reporting status** and **Report delay** on the device.
- Confirm that the system is still enabled under **Reconfigure system**.
- Confirm that the selected source actually supplies the required data; inspect
  the Web API account, Native node or MQTT publisher as appropriate.
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

For YAML-managed Lovelace resources, add
`/solesta/solesta-status-card.js?v=1.0.0` as a module in the existing
`lovelace.resources` list. Do not add a second `lovelace:` section.

## The card still shows an old design

The JavaScript bundle is cached by the browser. After every integration update,
restart Home Assistant and perform a full browser refresh. The installed
resource URL must end with the same version as the integration, for example:

```text
/solesta/solesta-status-card.js?v=1.0.0
```

When resources use Home Assistant storage mode, the integration updates the
canonical resource version and removes duplicate entries for that same path.
Historical `/local/solesta-status-card.js` and `/solestanext/solesta-status-card.js`
paths are unsupported and must be removed manually in the Resources interface.
Never edit Home Assistant's `.storage` files for this purpose.

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
