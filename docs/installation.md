# Installation and configuration

## Before you start

You need:

- Home Assistant 2026.9.0 or newer;
- HACS installed in Home Assistant;
- a Solesta Monitor account with at least one linked solar water heater; and
- network access from Home Assistant to `https://dashboard.solesta.nl`.

This is a community integration. It is installed as a HACS custom repository
and is not distributed as a built-in Home Assistant integration.

## Install through a HACS custom repository

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Enter
   `https://github.com/herelder/home-assistant-solesta`.
4. Select **Integration** as the repository type and choose **Add**.
5. Open the newly available **Solesta** repository and choose **Download**.
6. Select the newest version, complete the download, and restart Home
   Assistant.
7. Go to **Settings → Devices & services → Add integration** and search for
   **Solesta**.

If Solesta does not appear, confirm that HACS installed
`custom_components/solesta` and restart Home Assistant again. See
[Troubleshooting](troubleshooting.md) for browser and dashboard cache issues.

## Create a provider hub

The first form creates a local provider hub. Enter:

- **Provider ID**: a stable local label that is unique across all Solesta
  provider hubs in this Home Assistant installation. For example,
  `family_account` or `holiday_home`. It is local identity, not a value
  supplied by Solesta.
- **User ID**: the email address or user name used for the Solesta Monitor
  account.
- **Password**: the password for that account.

The connection and credentials are tested before the hub is saved. The entry is
named `Web API – <provider ID>`. Credentials may be reused by another hub,
but every hub must have a different provider ID.

## Add and enable a solar water heater

Creating the provider hub does not yet create a device:

1. Open the Solesta integration entry.
2. Choose **Add system**.
3. Select one of the provider systems discovered for the account.
4. Review the proposed **System ID** and the source expressions.
5. Submit the form.

The System ID becomes the stable local name used when initial entity IDs are
created. It must be a unique lowercase Home Assistant slug of no more than 64
characters. Changing it later does not rename existing entity IDs.

Every new system is deliberately created disabled. This lets you review the
mapping without starting updates immediately:

1. Open the newly added system under the provider hub.
2. Choose **Reconfigure system**.
3. Turn on **Enabled**.
4. Submit the form.

Home Assistant then creates the device and its enabled-by-default entities.
Repeat **Add system** for each additional solar water heater. A provider system
can be linked only once as a regular system under the same hub.

The default expressions are appropriate for the supported Solesta web service.
Only change them when you understand the provider payload and the dependency
between calculated entities. Invalid expressions or values are rejected during
reconfiguration.

## Reconfigure or reauthenticate

Use **Reconfigure** on the provider hub to change the Solesta user ID or
password. Leave the password field empty to keep the saved password. The
candidate connection is tested against every linked system; the existing
configuration stays active if authentication, discovery or entity evaluation
fails.

When Home Assistant starts a reauthentication flow after an authentication
error, enter the current password. It is saved only after all linked systems
have been validated successfully.

Use **Reconfigure system** to:

- enable or disable that system;
- change the regular provider source-system mapping;
- adjust its local System ID or source expressions; and
- enable weekly source archives.

A source marked with a warning symbol is temporarily absent from provider
discovery. Its stored mapping remains selected so that a temporary outage does
not silently remap the system.

## Add the dashboard card

After the integration is running:

1. Fully refresh the Home Assistant browser page, or close and reopen the
   mobile app.
2. Edit a dashboard and choose **Add card**.
3. Select **Solesta system status**.
4. Choose the solar water heater and save the card.

See [Dashboard card](dashboard.md) for the available options and for
YAML-managed dashboard resources.

## Update

1. Create a Home Assistant backup.
2. Read [CHANGELOG.md](../CHANGELOG.md), especially when updating across
   multiple versions.
3. Install the update from HACS.
4. Restart Home Assistant.
5. Fully refresh every browser or reopen the mobile app so that the updated
   card bundle is loaded.

The integration updates its storage-mode dashboard resource to the installed
version and removes duplicate legacy resources for this card.

## Remove or reinstall

Before removal, save anything you need from
`/config/archives/solesta/`. Weekly archives are user data and are not
deleted automatically.

To remove the integration completely:

1. Remove the Solesta configuration entry in **Settings → Devices & services**.
2. Remove Solesta through HACS.
3. Restart Home Assistant.
4. Remove dashboard cards that still use
   `custom:solesta-status-card`.

Removing and later recreating a system can give its Home Assistant device a new
device ID. If an existing card then reports that its system is missing, open
the card editor and select the solar water heater again.
