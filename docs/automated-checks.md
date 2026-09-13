# Automated checks

GitHub Actions validates every proposed change before it can become part of a
release. All external actions are pinned to full commit hashes and Dependabot
proposes updates to those pins.

## Test workflow

`.github/workflows/tests.yml` runs for every push, pull request and manual
dispatch. It contains three independent jobs:

| Status check | Purpose |
| --- | --- |
| `Ruff` | Finds Python syntax errors, undefined names, unused imports and selected style errors |
| `Python` | Reproduces generated modules and runs the complete unit-test suite |
| `JavaScript` | Runs the dashboard-card behaviour and rendering tests in Node.js |

Ruff checks the integration, generators and most tests. Two compact legacy
archive-test modules and their generated golden fixture are excluded from lint
only; they remain part of the complete Python unit-test run.

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
and should be reviewed before merging.

## Repository rules

After the first workflow run, create an active ruleset for `main` and require:

- `Ruff`;
- `Python`;
- `JavaScript`;
- `HACS`;
- `Hassfest`;
- `CodeQL (python)`; and
- `CodeQL (javascript-typescript)`.

Also require a pull request, block branch deletion and block force pushes. The
ruleset is a GitHub repository setting and therefore cannot be stored in this
source repository itself.
