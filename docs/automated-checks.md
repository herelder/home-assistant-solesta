# Automated checks

GitHub Actions validates every proposed change before it can become part of a
release. All external actions are pinned to full commit hashes and Dependabot
proposes updates to those pins.

## Test workflow

`.github/workflows/tests.yml` runs for every push, pull request and manual
dispatch. It contains four job groups:

| Status check | Purpose |
| --- | --- |
| `Ruff` | Finds Python syntax errors, undefined names, unused imports and selected style errors |
| `Python` | Reproduces generated modules, validates the side-by-side lab package and runs the complete unit-test suite |
| `Home Assistant (2026.9.0)` / `Home Assistant (2026.10.4)` | Runs configuration, migration and native-state contracts with real HA and ESPHome client libraries |
| `JavaScript` | Runs the dashboard-card behaviour and rendering tests in Node.js |

Ruff checks the integration, generators and most tests. Two compact legacy
archive-test modules and their generated golden fixture are excluded from lint
only; they remain part of the complete Python unit-test run.

The Home Assistant matrix uses Python 3.14 and pairs HA 2026.9.0 with
`aioesphomeapi==46.2.0`, and HA 2026.10.4 with `aioesphomeapi==46.6.0`.
Both jobs explicitly install the integration's `aiomqtt==2.5.1` client.
`tests/ha_release_contracts.py` checks concurrent provider-ID claims,
duplicate relinking and isolation, expression preservation through upgrades,
form validation, provider-source identities, MQTT setup/TLS and actual native
state models. All six provider-switch directions are included. It runs separately
from the fast suite, which does not require a Home Assistant installation.
These contracts use isolated fixtures; they do not start a live HA server.

## Repository validation

`.github/workflows/validate.yml` runs on every push and pull request, every day,
and on manual request:

| Status check | Purpose |
| --- | --- |
| `HACS` | Checks that the repository has the structure and metadata expected by HACS |
| `Hassfest` | Applies Home Assistant's integration validation rules |

The Python suite also verifies JSON files, local Markdown links, brand-image
sizes, generated-file consistency, absence of common private artifacts and
full-SHA pinning of every external GitHub Action.

## Security analysis

`.github/workflows/codeql.yml` analyzes both Python and JavaScript/TypeScript on
pull requests and changes to `main`. It also runs every Monday and can be
started manually. The extended CodeQL security queries publish findings to the
repository's **Security** area.

CodeQL is the only workflow with `security-events: write`; every workflow has
read-only access to repository contents. No workflow receives release,
administration, package-publishing or deployment permission.

## Dependency updates

Dependabot checks GitHub Actions and Python build/test dependencies every
Monday. Its pull requests must pass the same checks as an ordinary contribution
and should be reviewed before merging. Updates for the CodeQL `init` and
`analyze` steps are grouped so both steps always use the same pinned version.

## Repository rules

After the first workflow run, create an active ruleset for `main` and require:

- `Ruff`;
- `Python`;
- both `Home Assistant` matrix checks;
- `JavaScript`;
- `HACS`;
- `Hassfest`;
- `CodeQL (python)`; and
- `CodeQL (javascript-typescript)`.

Also require a pull request, block branch deletion and block force pushes. The
ruleset is a GitHub repository setting and therefore cannot be stored in this
source repository itself.
