# Contributing

Contributions and well-scoped bug reports are welcome.

## Before opening an issue

- Update to the latest published version.
- Confirm the problem still occurs after a Home Assistant restart and a full
  browser refresh when the dashboard card is involved.
- Search existing issues.
- Remove credentials, cookies, tokens, personal data, addresses, system IDs and
  private network information from all material.

## Code changes

1. Create a branch from `main`.
2. Keep runtime files required by Home Assistant inside
   `custom_components/solesta/`.
3. Do not edit `thetruth.py` or `provider_defaults.py` manually. Change their
   workbooks or generators under `tools/` and rebuild them.
4. Keep all public documentation in English and update `CHANGELOG.md` when
   behaviour changes.
5. Run the checks below before opening a pull request.

```text
python3 -m pip install -r requirements-lint.txt
python3 -m pip install -r requirements-test.txt
python3 -m ruff check .
python3 tools/build.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_card.mjs
```

GitHub repeats these checks for every push and pull request. See
[Automated checks](docs/automated-checks.md) for the complete CI policy and the
three intentionally excluded legacy test/fixture files.

Do not add production databases, `.storage` files, archives, screenshots with
personal data, passwords, access tokens or captured authenticated responses.
