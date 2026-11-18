# Installation and configuration

Solesta supports three providers. They feed the same entities, calculations,
dashboard and history. Choose the transport that your system actually offers.

## Before you start

You need Home Assistant 2026.9.0 or newer and HACS for the installation below.
The integration is a community custom integration. Provider requirements are:

| Provider | Required connection | Source selection |
| --- | --- | --- |
| Web API | Solesta Monitor account and HA access to `https://dashboard.solesta.nl` | Select an account system |
| ESPHome Native | Reachable ESPHome node, encrypted native API and its encryption key | Select a device reported by that node |
| MQTT | Reachable MQTT 3.1.1 broker, subscription rights and a publisher | Enter a concrete root topic manually |

ESPHome Native works locally without internet access. MQTT can use a local or
remote broker; its network requirements follow that choice. Mosquitto and EMQX
have been tested. Neither a particular broker nor the HA MQTT integration is
required. MQTT Discovery is not used to create Solesta systems.

Have the source's field names, values and units available. The
[source-expression guide](source-expressions.md) explains their mapping to
entities. Read [Energy calculations](energy-calculations.md) for assumptions
and intentional differences from Solesta's own dashboard.

For a Solesta controller with the described debug header, the optional
[Solesta NanoC6 firmware kit](../esphome/public/README.md) provides a
receive-only ESPHome source. Follow its hardware checks and first-flash order
before configuring a Solesta Native hub. The NanoC6 can also publish to MQTT
when enabled in its local `secrets.yaml`. Install the firmware separately from
the Solesta HACS integration. You can connect Solesta directly to the node's
encrypted Native API without adding Home Assistant's ESPHome integration.

Steps use English HA labels; **Settings → Devices & services** is
**Instellingen → Apparaten en diensten** in Dutch. Menu placement can vary
slightly by HA version.

## Install through HACS

1. Open **HACS**, then its menu and **Custom repositories**.
2. Add `https://github.com/herelder/home-assistant-solesta` with type
   **Integration**.
3. Open **Solesta**, choose **Download**, and select the released version.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → Solesta**.
6. On **Choose provider**, select **Web API**, **ESPHome Native** or **MQTT**.

For a normal installation, select a version published as a full GitHub Release.
A tag or development branch alone is not a stable HACS release. If the
integration is missing after downloading a released version, check its
installation directory and restart HA; see [Troubleshooting](troubleshooting.md).

## Create the provider hub

Every hub needs a unique **Provider ID**, such as `boiler_local`. This is your
local connection label, independent of host, credentials and provider type.
Several hubs may use the same credentials but need different provider IDs.

### Web API

On **Connect Web API provider**, enter **Provider ID**, **User ID** and
**Password** for the Solesta Monitor account, then submit. The integration
tests HTTPS connectivity and obtains the account's system list.

### ESPHome Native

1. On **Choose ESPHome node**, select an mDNS-discovered node or manual entry.
   Discovery fills in an address; it does not authenticate it.
2. On **Connect ESPHome Native provider**, enter **Provider ID**, **Host or IP
   address**, **Port** and **API encryption key**. The usual API port is 6053.
3. Submit. The encrypted API must connect and confirm the device identity
   before the hub is saved.

The key is `api.encryption.key` in the node's ESPHome configuration. If that
YAML references a secret, consult the referenced secret. It is not the Wi-Fi
password or MQTT password. Keep it private.

The node's confirmed MAC is its main source-system identity. Explicit ESPHome
subdevices, when reported by the node, have separate selectable source IDs.
The integration does not manufacture a serial-channel suffix.

For the NanoC6 kit, the node offers raw `temperature_1_raw` through
`temperature_4_raw`, `flow_raw` and `pump_raw` fields plus controller state and
diagnostics. Review the
[complete NanoC6 mappings](../esphome/public/README.md#source-expressions) before
enabling the system. Firmware 0.1.2 offers `last_report` as the device's own
UTC report timestamp; its Native source expression can be `last_report`.
The normal reporting and report-age expressions remain applicable. For the
observed controller, `pump_raw` is a fraction that needs `* 100` to become a
percentage.
The official ESPHome integration is optional
and, if added, creates its own separate set of raw HA entities.

### MQTT

On **Connect MQTT provider**, enter:

| Field | What to enter |
| --- | --- |
| Provider ID | A unique local hub label |
| Broker host or IP address | A hostname or IP without a URL scheme or topic path |
| Use TLS | Enable for a TLS listener; use TLS for an internet connection |
| Port | The actual broker listener; commonly 1883 for TCP or 8883 for TLS |
| Username / Password | Both for authenticated access, or both empty for broker-supported anonymous access |
| Keepalive (seconds) | Normally 60; range 1–65535 |
| Subscription QoS | 0, 1 or 2; normally start with 0 |

Check the port when changing TLS; enabling TLS does not turn a plain TCP
listener into a secure listener. TLS verifies the certificate and host against
the system trust store. Use the hostname on the certificate. There is no
ignore-certificate-error option, private-CA upload, client-certificate form or
WebSocket transport.

The integration uses its own MQTT client and subscribes to configured source
roots. Hub connectivity is validated before saving; values are validated when
adding a system. Keep the publisher running during that next step. See
[Privacy and security](privacy-and-security.md).

MQTT field discovery has a bounded 20-second window. Required fields may arrive
in separate non-retained messages; they need not form one immediate burst.
Missing fields at the deadline and ambiguous names are reported at their
source-expression fields. Once validated, the compiled bindings stay fixed
until a new configuration is validated.

## Add a system and map its source

Creating a provider hub does not yet create a running system:

1. Open its Solesta entry under **Devices & services**.
2. Choose **Add system** from the hub's system/subentry actions.
3. For Web API or Native, select the **Provider source-system ID** reported by
   that provider. Only currently offered sources are listed.
4. For MQTT, **Add manual MQTT source** asks for **Root topic**. Enter the
   exact concrete root, for example `solar/bridge_a`, without `/#` or a trailing
   slash. Wildcards are not allowed. Case and meaningful spaces are preserved.
   The subscription is `solar/bridge_a/#`; no broker-wide discovery is performed.
5. On **Configure system**, choose a unique **System ID** and review the
   source-expression fields. See [worked mappings](source-expressions.md#worked-mappings).
6. Submit. Expression syntax and dependencies are checked. Every new system
   is saved disabled, even if its source is unavailable, required source fields
   are missing or its values fail live validation. This also applies to MQTT
   and duplicate systems. Enabling requires successful live source/expression
   validation; creation alone is not proof that a system is ready to enable.

The local System ID is a lowercase HA slug of at most 64 characters, such as
`solar_tank`. It supplies initial entity names. Changing it later does not
rename existing entity IDs. Permanent internal identity is separate from this
label and the external source.

There is one shared set of factory expressions. The integration does not
select formulas by provider or guess field relationships. The default
`to_number(temp1)` requires a source offering `temp1`; a node or publisher with
different names needs a mapping you have reviewed. Multiply a pump input by
100 only if it is a fraction, not an already expressed percentage.

In the source-expression configuration form:

- Enter a **single space** to reset an expression to its current **factory
  value** when the form is validated.
- **Clear the field completely** during reconfiguration to restore the value
  it had **at the start of that reconfiguration**, rather than the factory value.

## Enable the system

Every new system is deliberately created disabled:

1. Open it under its provider hub and choose **Reconfigure system**.
2. Review its source and expressions and turn on **Enabled**.
3. Submit and resolve any source or value-validation errors.

Once validated and enabled, HA sets up the device and entities. Repeat for
additional systems. A regular source can be linked once per hub; a deliberate
second local representation uses a [duplicate system](duplicates.md).

## Change a connection or credentials

Open the hub's menu and **Reconfigure**. Keep its provider type to change the
connection, or select another type for a provider switch. Candidate connections
are validated before replacing active configuration.

- Web API: change user ID/password. An empty password retains the saved
  password when reconfiguring this provider.
- Native: select/enter the address again. An empty encryption key retains the
  saved key. The saved MAC must still match; another physical node is not a
  silent device replacement.
- MQTT: change broker, TLS, port, credentials or transport settings. An empty
  password retains the saved one only if the username is unchanged. The new
  broker must provide the configured sources and usable expressions.

For MQTT anonymous access, clear both Username and Password. Changing Username
requires a new Password; a previous user's password is not reused. The broker
must accept the proposed access before the saved configuration changes.

When HA displays **Reauthenticate provider hub**, supply the requested
password or encryption key. It is saved after the candidate connection and
linked systems validate. Resolve any reported connection, source or expression
error; leaving the active connection intact is the failure behaviour.

## Switch provider while keeping the same system

Use **Reconfigure** on the existing hub rather than deleting it:

1. Select the new provider and enter its connection settings.
2. Save the validated connection. Linked systems become disabled.
3. Open **Reconfigure system** for each system and select the new offered
   source, or enter the MQTT root manually.
4. Review every expression against the new source's actual fields and units.
   Expressions are retained, not translated or replaced for you.
5. Enable and submit after the mapping passes validation.

Permanent hub/system identities, existing entity identities and history remain
attached to the same local system. A stale source is not offered as a fake
discovery choice. An unchanged mapping can be retained while disabled;
enabling it requires a current valid source. A duplicate's communication source
can be relinked while retaining its local alias.

## Add the dashboard

Refresh HA or reopen its mobile app after installation. Edit a dashboard,
choose **Add card → Solesta system status**, select the device and save. See
[Dashboard card](dashboard.md) for labels, history and YAML resources.

## Upgrade and recover

1. Create a native HA backup, including settings and history.
2. Read [Release notes](release-notes.md) and [CHANGELOG.md](../CHANGELOG.md),
   including the metadata-only upgrade and literal preservation of stored expressions.
3. Install the published HACS update and restart HA.
4. Refresh browsers/reopen apps and check every provider and system.

The upgrade keeps permanent local identities and existing dashboards/history.
It does not automatically convert custom mappings to another provider. After a
storage-schema upgrade, rollback requires the matching native backup with old
code and configuration. Replacing Python files alone is not a schema rollback.
See [Release notes](release-notes.md#upgrade-from-023).

## Remove or reinstall

Save needed weekly archives before removal; `/config/archives/solesta/` is user
data and is not automatically deleted. Remove the config entry in **Devices &
services**, remove Solesta in HACS, restart HA and remove its dashboard cards.
Recreating a deleted system can give it a new device identity; existing cards
may need their device reselected.
