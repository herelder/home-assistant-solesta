# Solesta for Home Assistant

[![Test](https://github.com/herelder/home-assistant-solesta/actions/workflows/tests.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/tests.yml)
[![Validate](https://github.com/herelder/home-assistant-solesta/actions/workflows/validate.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/validate.yml)
[![CodeQL](https://github.com/herelder/home-assistant-solesta/actions/workflows/codeql.yml/badge.svg)](https://github.com/herelder/home-assistant-solesta/actions/workflows/codeql.yml)

<p align="center">
  <img src="custom_components/solesta/brand/logo.png" alt="Solesta community integration" width="180">
</p>

An independent community integration for monitoring Solesta solar water
heaters in Home Assistant. It connects to the Solesta web service, creates a
separate Home Assistant device for every enabled system, and includes a
purpose-built status card.

This project is not an official Solesta product and does not imply endorsement
by Solesta or Home Assistant.

Current release version: **0.2.3**

Minimum Home Assistant version: **2026.9.0**

## Features

- User-interface configuration; no YAML is needed for the integration itself.
- Multiple provider hubs and multiple solar water heaters.
- Temperature, stored-energy, pump, reporting and alert entities.
- Adjustable tank capacity, cold-water temperature, shower energy and update
  interval.
- A bundled bilingual Solesta system-status dashboard card.
- Day and seven-day tank-temperature history in the Home Assistant time zone.
- Optional weekly source archives built from Home Assistant Recorder history.
- Home Assistant backup integration for internally consistent archive backups.
- Downloadable diagnostics that omit credentials and raw provider values.

## Requirements

- A working Solesta Monitor account with at least one linked system.
- Home Assistant 2026.9.0 or newer.
- HACS for the custom-repository installation described below.
- Internet access from Home Assistant to `https://dashboard.solesta.nl`.

## Quick start

1. In HACS, open **Custom repositories** and add
   `https://github.com/herelder/home-assistant-solesta` as an
   **Integration** repository.
2. Download **Solesta** in HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Solesta**.
4. Create a provider hub with a unique local provider ID and your Solesta
   account credentials.
5. Open the new Solesta entry and choose **Add system**. Select a discovered
   solar water heater and review its settings.
6. New systems are deliberately created disabled. Open **Reconfigure system**,
   turn on **Enabled**, and submit the form.
7. Add **Solesta system status** from the dashboard card picker.

See [Installation and configuration](docs/installation.md) for the complete
procedure, updates, reauthentication and removal.

## Documentation

| Topic | Contents |
| --- | --- |
| [Installation and configuration](docs/installation.md) | HACS custom repository, first setup, adding and enabling systems, updates and removal |
| [Entities and settings](docs/entities.md) | All sensors, binary sensors, settings and default values |
| [Dashboard card](docs/dashboard.md) | Card setup, status meanings, history and YAML-managed resources |
| [Energy calculations](docs/energy-calculations.md) | MJ, kWh and standard-shower assumptions |
| [Weekly source archives](docs/archive.md) | Scheduling, file format, Recorder coverage, backup and recovery |
| [Multiple hubs and duplicate systems](docs/duplicates.md) | Identity model, safe reconfiguration and advanced duplicate links |
| [Troubleshooting](docs/troubleshooting.md) | Setup, authentication, entities, card, history and archive problems |
| [Privacy and security](docs/privacy-and-security.md) | Cloud communication, stored data, diagnostics and safe issue reports |
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
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_card.mjs
```

See [Contributing](CONTRIBUTING.md) and the
[generator documentation](tools/README.md) for the contribution and
verification process.

## License

Copyright © 2026 Herman Elderson. This project is licensed under the
[MIT License](LICENSE).
