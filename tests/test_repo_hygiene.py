"""Repository hygiene guardrails.

These tests prevent sensitive artifacts (database backups containing real users'
PII, password hashes, CPFs and GPS coordinates) from being committed to git.
"""
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORBIDDEN_SUFFIXES = (".db", ".db.bak", ".sqlite", ".sqlite3")


def _tracked_db_files():
    result = subprocess.run(
        ["git", "-C", ROOT, "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().lower().endswith(FORBIDDEN_SUFFIXES)
    ]


@pytest.mark.skipif(
    not os.path.isdir(os.path.join(ROOT, ".git")),
    reason="not a git repository",
)
def test_no_database_backups_are_tracked():
    """Sensitive database/backup files must never be committed to git."""
    assert _tracked_db_files() == [], (
        "Database files are tracked in git; remove them and scrub history: "
        f"{_tracked_db_files()}"
    )
