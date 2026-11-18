# Solesta source workbooks and generators

This directory contains the canonical development sources for the integration's
two generated runtime modules.

| Source | Revision | Generator | Runtime module |
| --- | ---: | --- | --- |
| `sources/EntityDescriptions.xlsx` | catalog 16 | `generate_thetruth.py` | `../custom_components/solesta/thetruth.py` |
| `sources/ProviderDefaults.xlsx` | preset 3 | `generate_provider_defaults.py` | `../custom_components/solesta/provider_defaults.py` |

The build coordinator derives the component location from the repository
layout: `custom_components/solesta`. Do not edit `thetruth.py` or
`provider_defaults.py` manually.

## Build environment

The release candidate is generated and verified with Python 3.12.14 and
`openpyxl==3.1.5`. Install the pinned build dependency in an isolated Python
environment:

```text
python3 -m pip install -r tools/requirements-build.txt
```

## Generate and verify

Run these commands from the repository root:

```text
python3 tools/build.py --write
python3 tools/build.py --check
```

`--write` validates both workbooks and all translations before replacing
generated files. Each result is first built in a temporary file beside its
destination. `--check` writes nothing and fails when a runtime module cannot
be reproduced byte-for-byte from its canonical source.

`EntityDescriptions.xlsx` must have catalog revision 16 and the prescribed set
of 21 entity keys. `ProviderDefaults.xlsx` must have preset revision 3 and
exactly one login request. Generated headers include SHA-256 hashes of the
source workbook and generator.

Before publishing, the REST generator validates the entire preset contract:
the fixed HTTPS origin, flow structure, methods, paths, placeholders, request
content, expected status codes, selectors and response assertions. It
normalizes the result into executable flows with their allowed bindings and
recursively freezes the generated data. The runtime executes this generated
contract directly and does not store an editable copy in a new Home Assistant
configuration.

The energy formulas and their intentional differences from the Solesta web
dashboard are documented in
[Energy calculations](../docs/energy-calculations.md).

## Side-by-side lab package

`build_lab.py` derives a separate `solesta_lab` integration from the canonical
`custom_components/solesta` tree. It does not maintain a second source tree.
The generated integration has its own Home Assistant domain and visible name,
registers its dashboard card under the independent
`custom:solesta-lab-status-card` type, and does not start the archive manager
or archive service. The separate card type and `/solesta_lab/` resource path
allow the production and lab dashboards to be loaded side by side.

Validate the overlay and deterministic output without writing an artifact:

```text
python3 tools/build_lab.py --check
```

Generate the installable component tree:

```text
python3 tools/build_lab.py --write
```

In VS Code, use **Terminal → Run Task** and select either **Solesta Lab:
controleren** or **Solesta Lab: bouwen** for the same actions.

The default output is:

```text
work/solesta_lab/custom_components/solesta_lab
```

`work/` is ignored by Git. Every generated package contains `lab_build.py`
with the canonical manifest version, a SHA-256 of the complete source
component and a short build ID. The same metadata is included in downloaded
lab diagnostics. Never copy generated lab files back into the canonical
component, and do not deploy the lab package to live Home Assistant without a
separate backup, recovery and verification plan.
