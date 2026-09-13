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
The current release supports the Solesta Web API provider only; its HTTPS
service address is supplied by the generated provider preset rather than by the
setup form.

## Safe provider reconfiguration

A proposed credential or connection change is tested outside the active
runtime:

1. connect and authenticate with the candidate configuration;
2. run real provider system discovery;
3. confirm that every linked regular system and every duplicate communication
   target is still present;
4. evaluate each linked system's stored source expressions against a real
   status response; and
5. confirm that all expected entity values are valid.

Only after every check succeeds are the provider configuration and all system
validation stamps published together. Linked system subentries remain enabled.
If a system is absent or invalid, the old provider configuration remains active
in full.

A concurrent change to the hub or one of its systems causes a revision
conflict. The stale form is rejected instead of overwriting the newer
configuration.

## Link a duplicate system

Choose **Link a duplicate system** from the provider entry's system/subentry
menu. The integration first performs normal provider discovery. You then:

1. enter a unique local **Duplicate source-system ID**;
2. select the real **Communication source-system ID** from discovery; and
3. complete the normal system settings form.

The duplicate is created disabled, just like a regular system. Use
**Reconfigure duplicate system**, turn on **Enabled**, and submit the form when
you are ready to start it.

The local alias is translated to the external provider ID only at the provider
status boundary. The coordinator, expression engine, entity platforms and
archive implementation continue to treat it as an ordinary independent
system.

A duplicate system has its own permanent `system_uid`, Home Assistant device,
entities, configuration and archive series. Its communication mapping is
intentionally fixed during reconfiguration. Remove the duplicate system
subentry and create a new one to change the target. Home Assistant's normal
**Delete** action unlinks the duplicate; it does not delete the real provider
system.

## Enforced identity rules

- Provider IDs are unique across the integration.
- Different hubs may use the same account credentials.
- Local source-system IDs are unique within a hub.
- A duplicate's local source ID differs from its communication target.
- Duplicate mappings are direct and cannot form chains.
- A duplicate local ID cannot collide with a real discovered system.
- A duplicate target must be a real system returned by provider discovery.
- Adding or removing a duplicate rebuilds the provider lifecycle even while
  that duplicate is disabled.
- A provider change preserves every linked system or is rejected completely.
