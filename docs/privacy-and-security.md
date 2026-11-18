# Privacy and security

This is an independent community integration, not a product developed,
certified or supported by Solesta or Home Assistant. Its three providers have
different network and credential requirements.

## Provider communication

| Provider | Destination and credentials | Data flow |
| --- | --- | --- |
| Web API | Fixed `https://dashboard.solesta.nl`; configured account user ID/password | Sign in, read account profile/systems, poll enabled systems, sign out |
| ESPHome Native | Configured node on the network; API encryption key and confirmed MAC | Encrypted direct subscription to reported native states |
| MQTT | User-chosen local or remote broker; optional username/password | MQTT 3.1.1 connection and subscriptions below configured system roots |

Web API requests require HTTPS, reject redirects, ignore inherited proxy
settings and have time/response-size/nesting limits. This route depends on the
Solesta service and internet connection. Its per-system Update interval
controls polling.

Native access does not require the Nano to reach the internet. The Noise key
authenticates/encrypts the native API connection; the confirmed MAC is checked
again on subsequent connections. Host changes must not silently replace a
physical device. Keys and numeric native routes are not permanent local
entity identities.

MQTT connects directly to the chosen broker; it does not use HA's MQTT
configuration or credentials. A source publisher sends its values to that
broker, and the provider reads them using `<root>/#`. There is no broker-wide
system discovery. Root topics, client activity and retained data may identify
devices and are visible to whoever administers the broker. Configure broker
accounts/ACLs for the intended subscriptions and manage retained messages at
the broker. Solesta does not change broker permissions or retained data.

Plain MQTT TCP does not provide transport encryption. Use TLS over an internet
or otherwise untrusted network. TLS checks server identity and certificate
trust against the system store. The form has no certificate-ignore option,
custom private-CA upload, client-certificate login or WebSocket transport.
Changing a broker's address is also a decision about where credentials and
subscription information are sent.

The manifest retains one HA IoT classification (`cloud_polling`) for this
multi-provider integration. That label does not imply internet dependence for
the local Native/MQTT routes. Neither local route needs the Solesta cloud.

## Local data and backups

HA config entries/subentries store provider IDs, connection settings, secrets,
source identities, available field metadata and source expressions. Depending
on the selected provider this includes account credentials, a native encryption
key or MQTT credentials. Protect HA's configuration and native backups as
sensitive data and restrict administrator access.

Entity attributes include local provider/system labels and provider protocol.
Recorder and optional archives can preserve those attributes, states, names,
entity IDs and configuration changes. Weekly archives live under
`/config/archives/solesta/`; the integration does not automatically remove or
send them elsewhere. Backup/restore can include this private history.

The card reads HA entities, registry information and Recorder history. Its code,
images and translations are bundled locally. It does not log in to a provider,
embed the Solesta website, or fetch external fonts, analytics or scripts.

The integration has no advertising or maintainer telemetry. Provider
connections go to the configured service/node/broker; there is no separate
upload to this repository or its maintainer. An administrator may separately
download/share diagnostics, archives or screenshots.

## Diagnostics and reports

Integration diagnostics omit credentials, permanent local IDs and raw provider
values. They contain numbered systems, configuration revisions, available
source names, error categories and report/change timestamps. The lab overlay
also identifies its build. Source names and timestamps can still reveal
operational information: review every download before sharing.

Public acceptance reports use consistent pseudonyms for installation/device,
system, registry and network identifiers. Original identifying evidence is
retained privately, outside the public release payload. A sanitized working
file does not sanitize earlier Git history: release preparation must also
verify the exact history that will be published.

Never publish passwords, Noise keys, cookies, tokens, raw authenticated
responses, databases, `.storage`, complete topic captures or unredacted
archives. Use fictional values such as `mqtt.example.com`, `solar/bridge_a`
and documentation-range IP addresses when illustrating a setup.

## Vulnerabilities and maintenance

Use the repository's **Security → Report a vulnerability** private reporting
form for suspected vulnerabilities. Ordinary bugs can use the sanitized public
issue template. See [SECURITY.md](../SECURITY.md) and
[Maintainer security](maintainer-security.md) for the policy and repository
settings to complete before publication.
