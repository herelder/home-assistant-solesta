# Privacy and security

## Community status

This repository is an independent community project. It is not developed,
certified or supported by Solesta or by the Home Assistant project. The
integration uses the web service available to a Solesta Monitor account; that
service can change independently of this repository.

## Cloud communication

Home Assistant connects directly to `https://dashboard.solesta.nl` over
HTTPS. The current provider flow:

- signs in with the configured user ID and password;
- reads the account profile and linked-system list;
- requests live status for each enabled system; and
- signs out when the provider session is closed.

The dashboard host is fixed in the integration and must use HTTPS. Requests do
not follow redirects, do not use proxy settings inherited from the Home
Assistant process, and have time and response-size limits. Returned JSON is
also checked for excessive size and nesting before it is used.

The integration is classified as **cloud polling**. Its availability therefore
depends on the Home Assistant internet connection and the Solesta web service.
The per-system **Update interval** controls how often live status is requested.

## Data stored in Home Assistant

The provider ID, user ID, password and system configuration are stored as a
Home Assistant configuration entry. Protect Home Assistant's configuration
directory and backups as sensitive data, restrict administrator access, and
keep Home Assistant itself up to date.

The dashboard card runs inside Home Assistant. It reads the selected device's
entity states and requests the tank-temperature history from Home Assistant; it
does not need separate Solesta credentials. Its JavaScript and images are
bundled with the integration and do not load code, fonts or analytics from an
external service.

The integration has no analytics, advertising, crash-reporting or maintainer
telemetry. It does not send Home Assistant data to this repository or its
maintainer. Data leaves Home Assistant only for the provider requests described
above, or when an administrator deliberately downloads and shares a diagnostic
or archive file.

Optional weekly archives are stored under
`/config/archives/solesta/`. They can contain entity IDs, names, states,
attributes, system identity and historical configuration changes. Treat them
as private operational data. They are never deleted or copied to another
computer automatically.

## Diagnostics

Downloadable integration diagnostics intentionally omit credentials, local
configuration-entry IDs, permanent system IDs and raw provider values. Systems
are numbered only within the diagnostic download. The download does contain
configuration revisions, available provider key names and expression-error
categories. These values can still reveal technical information about an
installation, so review the download before sharing it.

Do not share a complete Home Assistant database, files from `.storage`,
authenticated Solesta responses or weekly archive files in a public issue.

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting form on the repository's
**Security** tab. Do not disclose a suspected vulnerability, credentials or
authenticated response in a public issue.

Ordinary bugs can use the public issue template after all personal and secret
values have been removed. See [SECURITY.md](../SECURITY.md) for the reporting
policy.

Repository owners should complete the protective GitHub settings described in
[Maintainer security](maintainer-security.md) before announcing a release.
