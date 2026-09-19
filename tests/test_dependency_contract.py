"""Tests for the declared dependency contract (REQ-DEP-001..008, HU-101).

These assert facts about the *declared* metadata -- what `pyproject.toml`, the
lockfile and the CI workflows promise -- rather than about runtime behaviour.
A resolution that only the developer's machine can reproduce is exactly the
failure mode HU-101 exists to prevent, and it is invisible to every other test
in this suite.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_ENV_ACTION = REPO_ROOT / ".github" / "actions" / "setup-python-env" / "action.yml"

# Every assertion here reads the working tree through git or off disk.
pytestmark = pytest.mark.integration


def _tracked_files() -> set[str]:
    """Paths git tracks, as `git ls-files` reports them from the repo root."""
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(out.stdout.split())


def test_lockfile_is_tracked() -> None:
    """CA-101.1: the lockfile travels with the repository.

    `uv sync --frozen` can only reproduce an environment that ships; a
    gitignored lockfile protects the developer and nobody else.
    """
    assert "uv.lock" in _tracked_files()


def test_lockfile_is_not_ignored() -> None:
    """CA-101.1: nothing re-ignores the lockfile once it is tracked."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "uv.lock"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert ignored.returncode != 0, ".gitignore still excludes uv.lock"


def test_ci_cache_keys_on_the_lockfile() -> None:
    """CA-101.2: the CI cache depends on the lockfile again.

    While the lockfile was gitignored the default `**/uv.lock` glob matched
    nothing and errored the step, so the cache was keyed on pyproject.toml
    instead. That workaround is what this asserts has been undone.
    """
    action = SETUP_ENV_ACTION.read_text()
    assert "cache-dependency-glob: uv.lock" in action


def test_ci_cache_workaround_comment_is_gone() -> None:
    """CA-101.2: the comment that declared the workaround has disappeared.

    Left behind, it documents a constraint that no longer holds and invites
    the next reader to re-apply it.
    """
    action = SETUP_ENV_ACTION.read_text()
    assert "gitignored" not in action
