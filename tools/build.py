#!/usr/bin/env python3
"""Regenerate or verify all workbook-derived Solesta source files."""

from __future__ import annotations

import argparse
import difflib
import os
from pathlib import Path
import tempfile
from typing import Final

import openpyxl

import generate_provider_defaults
import generate_thetruth


TOOLS_DIR: Final = Path(__file__).resolve().parent
REPOSITORY_DIR: Final = TOOLS_DIR.parent
COMPONENT_DIR: Final = REPOSITORY_DIR / "custom_components" / "solesta"
SOURCES_DIR: Final = TOOLS_DIR / "sources"
EXPECTED_OPENPYXL_VERSION: Final = "3.1.5"


def _translation_paths() -> list[Path]:
    result = [COMPONENT_DIR / "strings.json"]
    result.extend(sorted((COMPONENT_DIR / "translations").glob("*.json")))
    return result


def _render_outputs() -> dict[Path, str]:
    if openpyxl.__version__ != EXPECTED_OPENPYXL_VERSION:
        raise RuntimeError(
            "build requires openpyxl "
            f"{EXPECTED_OPENPYXL_VERSION}, found {openpyxl.__version__}"
        )
    return {
        COMPONENT_DIR / "thetruth.py": generate_thetruth.generate_text(
            SOURCES_DIR / "EntityDescriptions.xlsx",
            _translation_paths(),
            integration_dir=COMPONENT_DIR,
        ),
        COMPONENT_DIR
        / "provider_defaults.py": generate_provider_defaults.generate_text(
            SOURCES_DIR / "ProviderDefaults.xlsx"
        ),
    }


def _write_atomically(outputs: dict[Path, str]) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for output_path, content in outputs.items():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                temporary_path = Path(handle.name)
            mode = (
                output_path.stat().st_mode & 0o777
                if output_path.exists()
                else 0o644
            )
            os.chmod(temporary_path, mode)
            staged.append((temporary_path, output_path))
        for temporary_path, output_path in staged:
            temporary_path.replace(output_path)
    finally:
        for temporary_path, _ in staged:
            if temporary_path.exists():
                temporary_path.unlink()


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(COMPONENT_DIR)
    except ValueError:
        return path


def _check(outputs: dict[Path, str]) -> bool:
    matches = True
    for output_path, expected in outputs.items():
        try:
            actual = output_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"MISSING {_display_path(output_path)}")
            matches = False
            continue
        if actual == expected:
            print(f"OK {_display_path(output_path)}")
            continue
        matches = False
        print(f"DRIFT {_display_path(output_path)}")
        difference = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=str(output_path),
            tofile="regenerated",
            lineterm="",
        )
        for line_number, line in enumerate(difference):
            if line_number >= 80:
                print("... diff truncated ...")
                break
            print(line)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify that runtime files exactly match the canonical sources",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="regenerate both runtime files after all validation succeeds",
    )
    args = parser.parse_args()

    try:
        outputs = _render_outputs()
    except (
        OSError,
        RuntimeError,
        generate_provider_defaults.ProviderWorkbookError,
        generate_thetruth.WorkbookValidationError,
    ) as err:
        parser.error(str(err))

    if args.write:
        _write_atomically(outputs)
        for output_path in outputs:
            print(f"WROTE {_display_path(output_path)}")
        return 0
    return 0 if _check(outputs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
