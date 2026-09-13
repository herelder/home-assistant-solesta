# Solesta source workbooks and generators

This directory contains the canonical development sources for the integration's
two generated runtime modules.

| Source | Revision | Generator | Runtime module |
| --- | ---: | --- | --- |
| `sources/EntityDescriptions.xlsx` | catalog 7 | `generate_thetruth.py` | `../custom_components/solesta/thetruth.py` |
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

`EntityDescriptions.xlsx` must have catalog revision 7 and the prescribed set
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
