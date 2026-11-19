#!/usr/bin/env python3
"""Build or verify the generated side-by-side Solesta Lab integration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Final


TOOLS_DIR: Final = Path(__file__).resolve().parent
REPOSITORY_DIR: Final = TOOLS_DIR.parent
SOURCE_COMPONENT_DIR: Final = REPOSITORY_DIR / "custom_components" / "solesta"
DEFAULT_OUTPUT_DIR: Final = (
    REPOSITORY_DIR
    / "work"
    / "solesta_lab"
    / "custom_components"
    / "solesta_lab"
)
SOURCE_DOMAIN: Final = "solesta"
LAB_DOMAIN: Final = "solesta_lab"
LAB_NAME: Final = "Solesta Lab"
LIVE_CONFIG_ROOT: Final = Path("/Volumes/config")

_SOURCE_SETUP = '''async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the dashboard card and archiving once for all provider hubs."""
    from .archive import async_setup_archiving
    from .frontend import async_setup_frontend

    await async_setup_frontend(hass)
    await async_setup_archiving(hass)
    return True
'''
_LAB_SETUP = '''async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the isolated lab dashboard without archive side effects."""
    from .frontend import async_setup_frontend

    await async_setup_frontend(hass)
    return True
'''


class LabBuildError(ValueError):
    """Raised when the canonical component cannot produce a safe lab build."""


def _source_files(source_dir: Path) -> dict[Path, bytes]:
    """Read the canonical component tree without following links."""
    if not source_dir.is_dir():
        raise LabBuildError(f"Canonical component is missing: {source_dir}")
    files: dict[Path, bytes] = {}
    for path in sorted(source_dir.rglob("*")):
        relative = path.relative_to(source_dir)
        if path.is_symlink():
            raise LabBuildError(f"Symlinks are not allowed: {relative}")
        if path.is_dir():
            continue
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        files[relative] = path.read_bytes()
    if not files:
        raise LabBuildError("Canonical component contains no files")
    return files


def _tree_hash(files: dict[Path, bytes]) -> str:
    """Hash paths and contents with explicit boundaries."""
    digest = hashlib.sha256()
    for relative, content in sorted(files.items(), key=lambda item: item[0].as_posix()):
        encoded_path = relative.as_posix().encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise LabBuildError(f"Expected one {label} marker, found {count}")
    return text.replace(old, new, 1)


def _transform_manifest(content: bytes) -> tuple[bytes, str]:
    try:
        manifest = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise LabBuildError("Canonical manifest is not valid JSON") from err
    if manifest.get("domain") != SOURCE_DOMAIN:
        raise LabBuildError("Canonical manifest domain is not solesta")
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise LabBuildError("Canonical manifest has no version")
    manifest["domain"] = LAB_DOMAIN
    manifest["name"] = LAB_NAME
    return (
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        version,
    )


def _lab_build_module(source_hash: str, source_version: str) -> bytes:
    return f'''"""Generated identity and safety policy for this lab package."""

CANONICAL_DOMAIN = "{SOURCE_DOMAIN}"
LAB_DOMAIN = "{LAB_DOMAIN}"
SOURCE_VERSION = "{source_version}"
SOURCE_TREE_SHA256 = "{source_hash}"
LAB_BUILD_ID = "{source_hash[:12]}"
FRONTEND_ENABLED = True
ARCHIVING_ENABLED = False
'''.encode("utf-8")


def render_lab_package(
    source_dir: Path = SOURCE_COMPONENT_DIR,
) -> dict[Path, bytes]:
    """Return a deterministic lab package without writing it."""
    source = _source_files(source_dir)
    source_hash = _tree_hash(source)
    output = dict(source)

    manifest, source_version = _transform_manifest(output[Path("manifest.json")])
    output[Path("manifest.json")] = manifest

    const_path = Path("const.py")
    const_text = output[const_path].decode("utf-8")
    const_text = _replace_once(
        const_text,
        'DOMAIN = "solesta"',
        'DOMAIN = "solesta_lab"',
        label="domain",
    )
    output[const_path] = const_text.encode("utf-8")

    setup_path = Path("__init__.py")
    setup_text = output[setup_path].decode("utf-8")
    setup_text = _replace_once(
        setup_text,
        _SOURCE_SETUP,
        _LAB_SETUP,
        label="global setup",
    )
    output[setup_path] = setup_text.encode("utf-8")

    frontend_path = Path("frontend.py")
    frontend_text = output[frontend_path].decode("utf-8")
    frontend_text = _replace_once(
        frontend_text,
        "from .const import DOMAIN\n",
        "from .const import DOMAIN\nfrom .lab_build import LAB_BUILD_ID\n",
        label="lab frontend build identity import",
    )
    frontend_text = _replace_once(
        frontend_text,
        '    url = f"{CARD_PATH}?v={integration.version}"',
        '    url = (\n'
        '        f"{CARD_PATH}?v={integration.version}&build={LAB_BUILD_ID}"\n'
        '    )',
        label="lab frontend cache identity",
    )
    output[frontend_path] = frontend_text.encode("utf-8")

    diagnostics_path = Path("diagnostics.py")
    diagnostics_text = output[diagnostics_path].decode("utf-8")
    diagnostics_text = _replace_once(
        diagnostics_text,
        "from .configuration import HubRuntime\n",
        "from .configuration import HubRuntime\n"
        "from .lab_build import (\n"
        "    ARCHIVING_ENABLED,\n"
        "    CANONICAL_DOMAIN,\n"
        "    FRONTEND_ENABLED,\n"
        "    LAB_BUILD_ID,\n"
        "    LAB_DOMAIN,\n"
        "    SOURCE_TREE_SHA256,\n"
        "    SOURCE_VERSION,\n"
        ")\n",
        label="diagnostics import",
    )
    diagnostics_text = _replace_once(
        diagnostics_text,
        '    return {\n        "config_entry": {',
        '    return {\n'
        '        "lab_build": {\n'
        '            "build_id": LAB_BUILD_ID,\n'
        '            "canonical_domain": CANONICAL_DOMAIN,\n'
        '            "domain": LAB_DOMAIN,\n'
        '            "source_version": SOURCE_VERSION,\n'
        '            "source_tree_sha256": SOURCE_TREE_SHA256,\n'
        '            "frontend_enabled": FRONTEND_ENABLED,\n'
        '            "archiving_enabled": ARCHIVING_ENABLED,\n'
        '        },\n'
        '        "config_entry": {',
        label="diagnostics result",
    )
    output[diagnostics_path] = diagnostics_text.encode("utf-8")
    output[Path("lab_build.py")] = _lab_build_module(
        source_hash,
        source_version,
    )

    validate_lab_package(output, source_files=source)
    return output


def validate_lab_package(
    package: dict[Path, bytes],
    *,
    source_files: dict[Path, bytes] | None = None,
) -> None:
    """Validate identity, safety policy, completeness and Python syntax."""
    required = {
        Path("__init__.py"),
        Path("const.py"),
        Path("diagnostics.py"),
        Path("lab_build.py"),
        Path("manifest.json"),
    }
    missing = required - package.keys()
    if missing:
        raise LabBuildError(
            "Lab package misses required files: "
            + ", ".join(sorted(path.as_posix() for path in missing))
        )
    if source_files is not None:
        expected = set(source_files) | {Path("lab_build.py")}
        if set(package) != expected:
            raise LabBuildError("Lab package does not mirror the source tree")

    manifest = json.loads(package[Path("manifest.json")])
    if manifest.get("domain") != LAB_DOMAIN or manifest.get("name") != LAB_NAME:
        raise LabBuildError("Lab manifest identity is invalid")

    setup = package[Path("__init__.py")].decode("utf-8")
    if "await async_setup_frontend" not in setup:
        raise LabBuildError("Lab bootstrap does not enable its isolated frontend")
    if "await async_setup_archiving" in setup:
        raise LabBuildError("Lab bootstrap still enables archiving")

    policy = package[Path("lab_build.py")].decode("utf-8")
    for expected in ("FRONTEND_ENABLED = True", "ARCHIVING_ENABLED = False"):
        if expected not in policy:
            raise LabBuildError("Lab safety policy is incomplete")

    for relative, content in package.items():
        if relative.suffix != ".py":
            continue
        try:
            compile(content, relative.as_posix(), "exec")
        except SyntaxError as err:
            raise LabBuildError(f"Invalid generated Python: {relative}") from err


def _validate_output_path(output_dir: Path) -> Path:
    output = output_dir.resolve()
    source = SOURCE_COMPONENT_DIR.resolve()
    repository = REPOSITORY_DIR.resolve()
    work_root = (REPOSITORY_DIR / "work").resolve()
    live_config = LIVE_CONFIG_ROOT.resolve()
    if output.name != LAB_DOMAIN:
        raise LabBuildError(f"Output directory must be named {LAB_DOMAIN}")
    if output == source or output == repository or output in repository.parents:
        raise LabBuildError("Refusing unsafe lab output path")
    if source in output.parents:
        raise LabBuildError("Lab output may not be inside the canonical component")
    if repository in output.parents and work_root not in output.parents:
        raise LabBuildError("Repository lab output must stay below work/")
    if output == live_config or live_config in output.parents:
        raise LabBuildError("Lab builder never writes directly to live HA config")
    if output.exists() and not output.is_dir():
        raise LabBuildError("Existing lab output is not a directory")
    return output


def _write_package(package: dict[Path, bytes], output_dir: Path) -> None:
    """Publish the complete package with rollback of an existing artifact."""
    output = _validate_output_path(output_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{LAB_DOMAIN}-", dir=output.parent)
    )
    candidate = staging_root / LAB_DOMAIN
    backup = staging_root / f"{LAB_DOMAIN}-previous"
    try:
        for relative, content in package.items():
            destination = candidate / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        written = {
            path.relative_to(candidate): path.read_bytes()
            for path in candidate.rglob("*")
            if path.is_file()
        }
        if written != package:
            raise LabBuildError("Written lab package differs from rendered output")

        had_previous = output.exists()
        if had_previous:
            output.replace(backup)
        try:
            candidate.replace(output)
        except Exception:
            if had_previous and backup.exists() and not output.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="validate a deterministic lab package without writing files",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="generate the complete lab component directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"component output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    try:
        package = render_lab_package()
        repeated = render_lab_package()
        if package != repeated:
            raise LabBuildError("Repeated rendering is not byte-identical")
        metadata = package[Path("lab_build.py")].decode("utf-8")
        build_id = next(
            line.split('"', 2)[1]
            for line in metadata.splitlines()
            if line.startswith("LAB_BUILD_ID = ")
        )
        if args.write:
            _write_package(package, args.output)
            print(f"WROTE {args.output}")
        else:
            print("OK deterministic Solesta Lab package")
        print(f"LAB_BUILD_ID {build_id}")
        return 0
    except (OSError, LabBuildError) as err:
        parser.error(str(err))


if __name__ == "__main__":
    raise SystemExit(main())
