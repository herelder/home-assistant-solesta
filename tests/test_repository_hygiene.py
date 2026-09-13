"""Repository-wide checks that mirror publication expectations."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


REPOSITORY = Path(__file__).parents[1]
WORKFLOWS = REPOSITORY / ".github" / "workflows"
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")
ACTION_REFERENCE = re.compile(r"^\s*uses:\s*([^#\s]+)", re.MULTILINE)
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


class RepositoryHygieneTests(unittest.TestCase):
    """Keep common publication mistakes out of every pull request."""

    def test_all_json_files_are_valid(self):
        for path in sorted(REPOSITORY.rglob("*.json")):
            with self.subTest(path=path.relative_to(REPOSITORY)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_local_markdown_links_resolve(self):
        markdown_files = sorted(REPOSITORY.glob("*.md"))
        markdown_files.extend(sorted((REPOSITORY / "docs").glob("*.md")))
        for path in markdown_files:
            for raw_target in MARKDOWN_LINK.findall(
                path.read_text(encoding="utf-8")
            ):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if (
                    not target
                    or "://" in target
                    or target.startswith("mailto:")
                ):
                    continue
                with self.subTest(
                    path=path.relative_to(REPOSITORY), target=target
                ):
                    self.assertTrue((path.parent / target).resolve().exists())

    def test_external_workflow_actions_use_full_commit_shas(self):
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            contents = path.read_text(encoding="utf-8")
            for reference in ACTION_REFERENCE.findall(contents):
                if reference.startswith("./"):
                    continue
                action, separator, revision = reference.rpartition("@")
                with self.subTest(
                    path=path.relative_to(REPOSITORY), action=action
                ):
                    self.assertTrue(separator)
                    self.assertIsNotNone(COMMIT_SHA.fullmatch(revision))

    def test_generated_and_private_artifacts_are_absent(self):
        forbidden_names = {".DS_Store", ".env", "secrets.yaml"}
        forbidden_endings = (
            ".db-shm",
            ".db-wal",
            ".json.gz",
            ".sqlite-shm",
            ".sqlite-wal",
            ".sqlite3-shm",
            ".sqlite3-wal",
        )
        forbidden_suffixes = {
            ".db",
            ".har",
            ".log",
            ".pcap",
            ".pcapng",
            ".pyc",
            ".pyo",
            ".sqlite",
            ".sqlite3",
        }
        unexpected = [
            path.relative_to(REPOSITORY)
            for path in REPOSITORY.rglob("*")
            if path.is_file()
            and (
                path.name in forbidden_names
                or path.name.startswith(".env.")
                or path.name.endswith(forbidden_endings)
                or path.suffix.lower() in forbidden_suffixes
            )
        ]
        self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
