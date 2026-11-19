# Solesta for Home Assistant

[![Test](https://github.com/herelder/home-assistant-solesta/actions/workflows/tests.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/tests.yml)
[![Validate](https://github.com/herelder/home-assistant-solesta/actions/workflows/validate.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/validate.yml)
[![CodeQL](https://github.com/herelder/home-assistant-solesta/actions/workflows/codeql.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/codeql.yml)

<p align="center">
  <img src="custom_components/solesta/brand/logo.png" alt="Solesta community integration" width="180">
</p>

An independent community integration for monitoring Solesta solar water
heaters in Home Assistant. Choose the Solesta Web API, an encrypted ESPHome
Native connection or a standard MQTT broker. Each enabled system has its own
Home Assistant device and uses the same calculations and bundled status card.

This project is not an official Solesta product and does not imply endorsement
by Solesta or Home Assistant.

Current release version: **1.0.0**

Minimum Home Assistant version: **2026.9.0**

## Features

- User-interface configuration; no YAML is needed for the integration itself.
- Multiple provider hubs and multiple solar water heaters.
- Local ESPHome Native and broker-independent MQTT 3.1.1, including TLS.
- An optional Solesta NanoC6 ESPHome firmware kit for a receive-only connection
  to the Solesta debug header, with user-supplied connection settings.
- Validated source expressions for your source fields, units and calculations.
- Provider switching with permanent system/entity identity and history retained.
- Temperature, stored-energy, pump, reporting and alert entities.
- Adjustable tank capacity, cold-water temperature, shower energy and update
  interval.
- A bundled bilingual Solesta system-status dashboard card.
- Day and seven-day tank-temperature history in the Home Assistant time zone.
- Optional weekly source archives built from Home Assistant Recorder history.
- Home Assistant backup integration for internally consistent archive backups.
- Downloadable diagnostics that omit credentials and raw provider values.

## Requirements

- Home Assistant 2026.9.0 or newer.
- HACS for the custom-repository installation described below.
- Web API: a Solesta Monitor account and internet access to its HTTPS service.
- ESPHome Native: a reachable node with encrypted API and its encryption key.
- MQTT: a reachable broker, subscription rights and a publishing source. A
  local broker needs no internet or Home Assistant MQTT integration.
- To build the optional Solesta NanoC6 firmware: an M5Stack NanoC6, the Solesta
  debug-header wiring described in the [firmware kit](esphome/public/README.md),
  and ESPHome Device Builder. Other compatible sources can also be used.

## Quick start

1. In HACS, open **Custom repositories** and add
   `https://github.com/herelder/home-assistant-solesta` as an
   **Integration** repository.
2. Download **Solesta** in HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Solesta**.
4. Choose **Web API**, **ESPHome Native** or **MQTT** and create a hub with a
   unique local provider ID and that provider's connection settings.
5. Choose **Add system**. Select an offered Web API/Native source or enter a
   concrete MQTT root topic. Review the source expressions against actual field
   names and units; there is no automatic mapping between providers.
6. New systems are deliberately created disabled. Open **Reconfigure system**,
   turn on **Enabled**, and submit the form.
7. Add **Solesta system status** from the dashboard card picker.

See [Installation and configuration](docs/installation.md) for the complete GUI
procedure and [Source expressions](docs/source-expressions.md) for worked
mappings and formulas. Read [Release notes](docs/release-notes.md) before an
upgrade from 0.2.3. For normal installations, select a published release
version in HACS rather than the development branch.

## Documentation

| Topic | Contents |
| --- | --- |
| [Installation and configuration](docs/installation.md) | HACS custom repository, first setup, adding and enabling systems, updates and removal |
| [Solesta NanoC6 firmware kit](esphome/public/README.md) | ESPHome YAML, secrets template, wiring, flashing and optional MQTT publication |
| [Entities and settings](docs/entities.md) | All sensors, binary sensors, settings and default values |
| [Source expressions](docs/source-expressions.md) | Source fields, paths, conversions, dependencies, optional values, timestamps and alerts |
| [Release notes and upgrade](docs/release-notes.md) | Compatibility changes, preserved identities and backup-based rollback |
| [Dashboard card](docs/dashboard.md) | Card setup, status meanings, history and YAML-managed resources |
| [Energy calculations](docs/energy-calculations.md) | MJ, kWh and standard-shower assumptions |
| [Weekly source archives](docs/archive.md) | Scheduling, file format, Recorder coverage, backup and recovery |
| [Multiple hubs and duplicate systems](docs/duplicates.md) | Identity model, safe reconfiguration and advanced duplicate links |
| [Troubleshooting](docs/troubleshooting.md) | Setup, authentication, entities, card, history and archive problems |
| [Privacy and security](docs/privacy-and-security.md) | Provider communication, stored data, diagnostics and safe issue reports |
| [Logo and visual identity](docs/branding.md) | Community mark, brand assets, colours and usage rules |
| [Automated checks](docs/automated-checks.md) | GitHub Actions, CodeQL, Dependabot and required status checks |
| [Maintainer security](docs/maintainer-security.md) | GitHub account, repository, workflow and release safeguards |

All project documentation is written in English. The Home Assistant interface
and bundled dashboard card include English and Dutch translations.

## Support and issue reports

Use the repository's
[GitHub Issues](https://github.com/herelder/home-assistant-solesta/issues)
page for reproducible bugs and feature requests. Include the Home Assistant
version, integration version, a concise reproduction and carefully reviewed
diagnostics.

Never post passwords, cookies, access tokens, personal details, complete Home
Assistant databases, `.storage` files or unredacted archives. This community
project is maintained independently; official account, hardware and service
questions belong with Solesta support.

## Development

The generated runtime catalogs can be reproduced from the workbooks in
`tools/`:

```text
python3 -m pip install -r requirements-test.txt
python3 tools/build.py --check
python3 tools/build_lab.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_card.mjs
```

See [Contributing](CONTRIBUTING.md) and the
[generator documentation](tools/README.md) for the contribution and
verification process.

## License

Copyright © 2026 Herman Elderson. This project is licensed under the
[MIT License](LICENSE).
