# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-11-18

- Added the optional, source-available Solesta NanoC6 ESPHome firmware kit:
  receive-only debug-header parser, encrypted Native API, switchable MQTT
  publishing and a secrets template. The kit has its own firmware version.
- Updated NanoC6 firmware to 0.1.1: disabled the Native API reboot timer for
  MQTT-only use and documented complete Native/MQTT source-validity mappings
  and UART loss/recovery checks. Existing mappings require explicit review.
- Replaced the NanoC6-specific validity mapping with firmware 0.1.2's UTC
  `last_report` field, advanced only by complete valid UART status frames.
  Generic providers retain their existing transport semantics and require
  no additional diagnostic field. Existing MQTT mappings remain unchanged.
- Added encrypted ESPHome Native and broker-independent MQTT 3.1.1 alongside
  the existing Web API provider, with TCP/TLS and MQTT QoS 0/1/2 support.
- Added provider selection, native node discovery/manual entry, manual MQTT
  root topics, connection validation, reauthentication and all provider-switch
  routes while retaining local system/entity identities and history.
- Shared raw-state observation and push caching across providers; exposed
  `last_report()` and `last_update()` with explicit identical/retained-message
  semantics and per-system referenced-field tracking.
- Added qualified source-field names, shortest-unique binding and grouped
  `null(field, ...)`; fixed independent alert evaluation and unknown entity values.
- Added universal local diagnostics and localized alert records. Alert limits
  are constants in the expression; lab-only argument forms and migrations have
  been removed. Existing source alert text remains supported.
- Isolated stale/invalid duplicates, enabled safe duplicate relinking,
  strengthened expression validation and made concurrent provider-ID claims atomic.
- Bound duplicate-system expressions to the communication source's field table
  during runtime setup, matching live validation after reload and relinking.
  Own-name source references now follow the same path and ambiguity checks
  as other sources, including nullable fields.
- Allowed required MQTT fields to arrive separately within a bounded discovery
  window, preserving fixed expression bindings after validation. Kept exact
  MQTT communication roots for copies and made credential removal, replacement
  and password retention explicit during reconfiguration.
- Allowed MQTT systems and copies to be created disabled before their mappings
  pass live validation, matching Native; enabling still requires valid source data.
- Attached expression-validation errors to the affected form fields, including
  missing/ambiguous source names, syntax, function arguments and actual cycle
  members; retained per-field evaluation errors across all three providers.
- Preserved source expressions across provider switches. Restricted upgrade
  work to production 0.2.3 metadata migration, preserving all stored expressions
  literally; source identities use provider-native MAC/subdevice IDs or exact
  MQTT roots.
- Removed obsolete internal status/observation fallbacks and historical card
  resource routes. Explicit card display names are always preserved.
- Kept complete Recorder history for daily statistics and the chart cursor,
  reducing only drawing geometry while preserving gap boundaries. Supported
  skipped/repeated local midnights and isolated unresolvable chart boundaries.
  Missing required measurements now make the overall card status incomplete,
  with offline and severe-alert priorities preserved.
- Clarified local factory alerts and preserved source-alert expressions in the
  entity guide; removed internal catalog-function descriptions from user guides.
- Restricted `null(...)` inputs to individual fields or field-free expressions;
  missing fields preserve null values without suppressing calculation errors.
  `None` and `none` are ordinary field names. No stored expressions are migrated.
- Kept the energy calculations and their documented differences from Solesta:
  kWh derives from MJ and shower energy follows cold-water temperature.
- Expanded GUI setup, expression, privacy, upgrade and recovery documentation
  for all three providers, with a synchronized 1.0.0 integration/card release.
- See [Release notes](docs/release-notes.md) for compatibility and backup advice.

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
- Updated Ruff and both CodeQL workflow steps together, and configured
  Dependabot to keep future CodeQL action updates in one proposal.

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
