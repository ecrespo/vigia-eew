"""Tests for the quality gate's own configuration (REQ-OBS-003..007, HU-102).

The gate is only a gate if it is declared. These assert what
`pyproject.toml` promises about test selection, formatting and coverage --
the parts of Art. 8 that no other test would notice going missing.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pytest_config() -> dict[str, object]:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return config["tool"]["pytest"]["ini_options"]


def test_test_type_markers_are_declared() -> None:
    """CA-102.5: `integration` and `gui` exist as declared markers.

    Declared, not merely used: an undeclared marker is a typo away from
    silently selecting nothing.
    """
    declared = " ".join(_pytest_config()["markers"])
    assert "integration:" in declared
    assert "gui:" in declared


def test_unknown_markers_are_an_error() -> None:
    """CA-102.5: a misspelled marker fails instead of quietly matching nothing."""
    addopts = _pytest_config().get("addopts", "")
    assert "--strict-markers" in addopts


@pytest.mark.integration
def test_fast_batch_leaves_out_the_slow_tests() -> None:
    """CA-102.5: `-m "not integration and not gui"` collects only unit tests.

    Asserted by collection rather than by clock: a wall-time budget would
    make this test fail on a loaded machine for reasons that have nothing to
    do with the selection being right.
    """
    collected = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "not integration and not gui",
            "--collect-only",
            "-q",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout

    # Drives a real Textual app; the slowest file in the suite.
    assert "test_tui.py" not in collected
    # Shell out to git and to lint-imports respectively.
    assert "test_dependency_contract.py" not in collected
    assert "test_current_tree_satisfies_every_contract" not in collected
    # ...while the pure logic that the commit gate exists to protect stays in.
    assert "test_dedup.py" in collected
    assert "test_filter.py" in collected


def test_format_rule_is_in_the_commit_gate() -> None:
    """CA-102.3: an unformatted file is rejected before the commit exists.

    In the hook, not only in CI: a rule that only fires after the push has
    already let the diff it was meant to prevent into the branch.
    """
    hooks = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    assert "ruff format --check" in hooks


def test_format_rule_is_in_continuous_integration() -> None:
    """CA-102.3: and in CI, so a bypassed hook is still caught."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "ruff format --check" in ci


def _gate_text() -> str:
    """Everything the gate runs, hooks and CI together."""
    hooks = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    return hooks + ci


def test_duplication_is_measured_by_the_gate() -> None:
    """CA-102.6: dimension 1 of Article 8 is enforced, not just reported.

    The audit measured 0.95 % and moved on. A number nobody enforces is a
    number that only ever goes up.
    """
    assert "jscpd" in _gate_text()


def test_cognitive_complexity_is_measured_by_the_gate() -> None:
    """CA-102.6: dimension 2, on the axis that predicts unreadable code.

    Cyclomatic complexity counts branches; cognitive complexity counts how
    much a reader has to hold in their head, which is the thing that hurts.
    Both run: lizard covers structure and length, flake8 covers the reader.
    """
    gate = _gate_text()
    assert "CCR001" in gate
    assert "lizard" in gate


def test_the_complexity_ceiling_is_the_one_the_audit_declared() -> None:
    """The threshold starts at 16 because two functions are already there.

    16 is `rest_geofon._process_text` exactly, so the gate holds the line
    without blocking on work that belongs to T-127. Lowering it to 12 is
    that task's job, and this assertion makes the change deliberate rather
    than incidental.
    """
    assert "--max-cognitive-complexity=16" in _gate_text()


def test_duplication_runs_where_its_cost_belongs() -> None:
    """jscpd shells out to npx, so it runs before push, not on every commit."""
    hooks = (REPO_ROOT / ".pre-commit-config.yaml").read_text()
    jscpd_block = hooks.split("id: jscpd", 1)[1].split("- id:", 1)[0]
    assert "pre-push" in jscpd_block
