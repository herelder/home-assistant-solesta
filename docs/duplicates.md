# Multiple provider hubs and duplicate systems

Solesta separates a provider hub's permanent local identity from its connection
and authentication settings. It also supports an advanced duplicate-system
link that exposes one real provider system under an additional local system
identity.

Most installations need one provider hub and one regular system link per solar
water heater. Duplicate systems are useful only when a deliberate second local
device, independent configuration or independent archive series is required
for the same underlying provider system.

## Provider identity

- `hub_uid` is the immutable, locally generated technical identity of one
  Home Assistant configuration entry.
- `provider_id` is the locally chosen provider identity. It must be unique
  across all Solesta provider hubs in the Home Assistant installation.
- Provider type, endpoint, user ID, password and other connection fields are
  configuration, not identity.

There is no credential-derived provider identity. Multiple independent hubs may
use the same account credentials as long as they have different provider IDs.
Choose Web API, ESPHome Native or MQTT. The Web API HTTPS address comes from
the generated preset; Native and MQTT connections use the entered address.
MQTT's exact root is its source-system ID. Native uses the confirmed device MAC
and any explicitly reported subdevice IDs; Web API uses the offered account ID.

## Safe provider reconfiguration

A proposed credential or connection change is tested outside the active
runtime:

1. connect and authenticate with the candidate configuration;
2. obtain the provider's offered sources, or validate configured MQTT roots;
3. confirm that every linked regular system and every duplicate communication
   target is still present;
4. evaluate each linked system's stored source expressions against a real
   status response; and
5. confirm that all expected entity values are valid.

Only after every check succeeds are the provider configuration and all system
validation stamps published together. Linked system subentries remain enabled.
If a system is absent or invalid, the old provider configuration remains active
in full.

This describes connection changes within the same provider type. A change of
provider type keeps permanent hub/system/entity identity but disables linked
systems until their sources and retained expressions are reviewed and validated.
See [Switch provider](installation.md#switch-provider-while-keeping-the-same-system).

A concurrent change to the hub or one of its systems causes a revision
conflict. The stale form is rejected instead of overwriting the newer
configuration.

## Link a duplicate system

Choose **Link a duplicate system** from the provider entry's system/subentry
menu. The integration obtains the provider's available communication sources;
for MQTT these are the already configured concrete roots. You then:

1. enter a unique local **Duplicate source-system ID**;
2. select the actual **Communication source-system ID**; and
3. complete the normal system settings form.

The duplicate is created disabled, just like a regular system. Use
**Reconfigure duplicate system**, turn on **Enabled**, and submit the form when
you are ready to start it. For MQTT too, you can finish adding the disabled
copy before its expressions pass live source/value validation. Expression
syntax and dependencies must still be valid; enabling requires a successful
live validation.

The local alias is translated to the external provider ID only at the provider
status boundary. The coordinator, expression engine, entity platforms and
archive implementation continue to treat it as an ordinary independent
system.

For MQTT, the communication target is the exact concrete root, including case
and meaningful spaces. It may exceed the local alias's 256-character limit;
the root's UTF-8 byte limit applies instead. Selecting or reconfiguring a
copy does not trim or rename that root.

A duplicate system has its own permanent `system_uid`, Home Assistant device,
entities, configuration and archive series. **Reconfigure duplicate system**
lets you select a different communication source from the current provider's
real discovered systems. The local alias, permanent identity and stored source
expressions are preserved. Review the expressions yourself before enabling
the new mapping; the integration does not rewrite them. Home Assistant's normal
**Delete** action unlinks the duplicate; it does not delete the real provider
system.

A stale or malformed duplicate link is isolated from healthy active systems.
It does not prevent the provider from starting. Reconfiguration lists only
current communication sources; it does not offer obsolete IDs or aliases
as possible targets. An unchanged stale mapping may be retained while disabled,
but enabling or changing it requires live validation.

## Enforced identity rules

- Provider IDs are unique across the integration.
- Different hubs may use the same account credentials.
- Local source-system IDs are unique within a hub.
- A duplicate's local source ID differs from its communication target.
- Duplicate mappings are direct and cannot form chains.
- A duplicate local ID cannot collide with a real discovered system.
- A duplicate target must be an actual offered source or configured MQTT root.
- Adding or removing a duplicate rebuilds the provider lifecycle even while
  that duplicate is disabled.
- A same-provider connection change validates linked systems before publishing.
- A provider-type change preserves local identities and disables systems for
  explicit remapping and validation; it does not rewrite source expressions.
