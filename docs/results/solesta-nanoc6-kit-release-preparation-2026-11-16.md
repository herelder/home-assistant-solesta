# Solesta NanoC6 kit — 1.0.0 release preparation

Date: 16 November 2026. This report records a local release candidate. The
Solesta integration and dashboard are version `1.0.0`; the optional ESPHome
project identifies its firmware as `0.1.0`.

## Release contents and setup

The public kit at `esphome/public/` contains exactly `README.md`,
`solesta-nanoc6.yaml` and `secrets.example.yaml`. Users create their own
`secrets.yaml` alongside the firmware in ESPHome Device Builder; that file is
excluded from the candidate. The configuration reads GPIO1 only, exposes
encrypted Native API states, and enables MQTT publication only when
`mqtt_enabled` is true in the user's secrets. MQTT Discovery is off.

The repository README, installation guide, release notes and changelog link
the kit to the 1.0.0 providers and explain the separate firmware install. The
historical research snapshot is labeled as such and uses illustrative device
identifiers. Historical research reports and test fixtures now consistently
use an example device name and example MQTT root in place of locally used
connection identifiers.

## Evidence and checks

- The device owner reports a successful update of the NanoC6 from the public
  YAML, with the Solesta data stream returning immediately after the flash.
  This is a user observation, not a new firmware build in this release check.
- The owner removed the existing Home Assistant ESPHome device and observed
  rediscovery. This checks device discovery; it does not prove that ESPHome
  Device Builder can fetch the Dashboard import URL from GitHub.
- The clean candidate contains only the three public kit files, without
  `secrets.yaml`. Its eleven `!secret` references match the template keys.
  A private-value comparison against the locally supplied Wi-Fi, API and MQTT
  connection fields found no complete values in the candidate after
  pseudonymizing old reports and fixtures.
- Generator checks (`tools/build.py --check` and `tools/build_lab.py --check`),
  Ruff and the Python suite passed on the clean candidate (304 tests). The
  repository hygiene suite checks local Markdown links and private artifacts.

The verified public `main` head on this date is
`bccaee942ec20fe906f7ea3dd4a9978f1abba0b6`. The private development
branch's earlier commits are excluded. A local branch named
`release/1.0.0-nanoc6` was prepared from a fresh checkout of that public head,
with one candidate commit applying the inspected tree. It has five reachable
commits: four from public `main` and this release candidate. Recheck `main`
and the resulting branch tree and history before any push.

## Remaining release gates

1. After the reviewed candidate is on a public release branch, confirm that
   ESPHome Device Builder can fetch the Dashboard import URL at `main` when
   the kit actually reaches `main`. Recheck the MQTT-on and MQTT-off profiles
   if another firmware change is made; no firmware build was run here.
2. Run the GitHub HACS, Hassfest, Python/JavaScript and CodeQL checks on the
   final public branch/ref. The JavaScript test runtime was unavailable in
   this local session, so the dashboard suite was not rerun here.
3. Complete the already documented 1.0.0 HA target-environment smoke check,
   review the release branch, and decide separately on publication and the
   live production upgrade. No firmware flash or production upgrade was
   performed in this preparation.

Follow the [maintainer release procedure](../maintainer-security.md#publish-the-100-candidate-without-private-project-history)
for the clean-history publication route.
