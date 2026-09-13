# Changelog

All notable changes to this project will be documented in this file.

## [0.2.3] - 2026-09-13

- Corrected the preheated-water wording to use only relative thresholds from
  the configured cold-water temperature.
- Changed the lowest range from **no** to **slightly** preheated water below
  cold-water temperature + 5 °C.
- Defined the unqualified range from +5 °C up to, but excluding, +15 °C, and
  the **strongly** range from +15 °C upward; the former absolute 40 °C
  threshold no longer applies.
- Added exact boundary tests and kept the integration manifest, dashboard card
  and registered resource version in sync at 0.2.3.
- Prevented the Python CI job from leaving bytecode files in the checkout so
  the repository-hygiene check runs deterministically.
- Added current Home Assistant config-subentry type labels and declared the
  integration as configurable through config entries only for Hassfest.

## [0.2.2] - 2026-09-12

- Updated the bundled dashboard card to version 0.2.2.
- Refreshed the card presentation to match the concepts and useful details in
  the renewed Solesta web dashboard while continuing to use Home Assistant
  entities and Recorder history.
- Added the independent Solesta community mark to the card.
- Kept the status card, integration manifest and registered resource version in
  sync at 0.2.2.
- Reworked all public documentation in English, corrected the provider-hub and
  system-enablement setup procedure, and added entity, troubleshooting,
  privacy, update and removal guidance.
- Hardened downloadable diagnostics by removing local entry and permanent
  system identifiers.
- Pinned GitHub Actions to immutable revisions, disabled persisted checkout
  credentials, added workflow time limits and enabled Dependabot update
  proposals for Actions and test dependencies.
- Added the missing `voluptuous` test dependency so archive tests also run in a
  clean CI environment.
- Expanded the privacy, vulnerability-reporting and maintainer-security
  guidance for public release.
- Standardized the original community artwork as the integration icon and logo,
  added 256 px and 512 px brand assets, and documented the visual identity and
  usage rules.
- Added automatic Ruff, repository-hygiene and CodeQL checks, CI concurrency
  controls, status badges and documentation for the required GitHub branch
  checks.

## [0.1.0] - 2026-09-10

- Prepared the first complete Solesta integration candidate under the
  `solesta` domain.
- Included configuration flows, entities, the dashboard card, diagnostics and
  weekly source archives.
