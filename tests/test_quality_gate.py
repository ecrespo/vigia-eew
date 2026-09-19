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
