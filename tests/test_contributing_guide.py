"""Tests for the contribution guide (REQ-DEV-004, CA-109.5).

The guide is the one artefact whose whole purpose is to be read by someone
who has not read anything else. Its links are therefore load-bearing: a
broken one sends a first-time contributor to a 404 rather than to the
principles the project asks them to work by.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
README = REPO_ROOT / "README.md"


def test_the_guide_exists() -> None:
    assert CONTRIBUTING.is_file()


def test_the_guide_documents_the_quality_gate() -> None:
    """CA-109.5: the commands that decide whether a change is acceptable."""
    guide = CONTRIBUTING.read_text()
    for command in ("uv run pytest", "uv run ruff check .", "uv run mypy src"):
        assert command in guide


def test_the_guide_documents_the_commit_convention() -> None:
    """CA-109.5: how a commit is expected to read, with its prefixes."""
    guide = CONTRIBUTING.read_text()
    assert "Conventional Commits" in guide
    for prefix in ("feat:", "fix:", "docs:", "chore:"):
        assert prefix in guide


def test_every_relative_link_in_the_guide_resolves() -> None:
    """CA-109.5: including the one to the constitution.

    Checked as a set rather than by name: a guide whose link to the
    principles resolves while three others 404 has not done its job either.
    """
    guide = CONTRIBUTING.read_text()
    targets = re.findall(r"\]\((?!https?://|#)([^)#]+)", guide)
    assert targets, "the guide links nowhere"
    broken = [t for t in targets if not (REPO_ROOT / t).exists()]
    assert broken == [], f"unresolved links: {broken}"
    assert "docs/sdd/specs/00-CONSTITUTION.md" in targets


def test_the_readme_points_at_the_guide() -> None:
    """CA-109.5: findable from where a newcomer actually starts."""
    assert "CONTRIBUTING.md" in README.read_text()
