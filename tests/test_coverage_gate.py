"""Tests for the per-criticality coverage gate (REQ-OBS-003, HU-102).

A single global `fail_under` lets a well-covered module pay for a bare one:
the number stays up while the code that decides whether to alert someone
goes untested. The gate therefore asks each group for its own figure, and
the pure decision -- which module is short, and of what -- is separated from
reading the report so it can be tested without producing one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _checker():
    """Load the gate script without shipping it inside the package."""
    spec = importlib.util.spec_from_file_location(
        "check_coverage", REPO_ROOT / "scripts" / "check_coverage.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules[cls.__module__];
    # an unregistered module makes @dataclass fail at definition time.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_thresholds_are_set_by_criticality() -> None:
    """CA-102.2: 85 % for the pipeline and state, 70 % for ingestion, 40 % for adapters."""
    threshold_for = _checker().threshold_for
    assert threshold_for("src/vigia_eew/pipeline/dedup.py") == 85.0
    assert threshold_for("src/vigia_eew/state.py") == 85.0
    assert threshold_for("src/vigia_eew/ingest/ws_emsc.py") == 70.0
    assert threshold_for("src/vigia_eew/notify/alert_window.py") == 40.0
    assert threshold_for("src/vigia_eew/autostart/linux_systemd.py") == 40.0


def test_branch_coverage_is_measured() -> None:
    """CA-102.2: lines and branches, not only lines.

    A filter whose every line runs but whose else-branch never does reports
    100 % on lines, and it is the else-branch that drops the earthquake.
    """
    import tomllib

    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert config["tool"]["coverage"]["run"]["branch"] is True


def test_a_module_below_its_threshold_is_reported() -> None:
    """CA-102.1: the failure names the module and the figure it owes."""
    violations = _checker().violations(
        {
            "files": {
                "src/vigia_eew/pipeline/dedup.py": {"summary": {"percent_covered": 71.0}},
                "src/vigia_eew/ingest/ws_emsc.py": {"summary": {"percent_covered": 96.1}},
            }
        }
    )
    assert len(violations) == 1
    short = violations[0]
    assert short.path == "src/vigia_eew/pipeline/dedup.py"
    assert short.covered == 71.0
    assert short.required == 85.0


def test_a_module_at_its_threshold_passes() -> None:
    """The threshold is a floor, not a target to exceed."""
    assert (
        _checker().violations(
            {"files": {"src/vigia_eew/state.py": {"summary": {"percent_covered": 85.0}}}}
        )
        == []
    )


def test_unclassified_modules_are_not_gated() -> None:
    """Only the three declared groups carry a figure.

    `app.py` and `cli.py` are assembly; holding them to the pipeline's bar
    would be measuring the wiring, not the decisions.
    """
    checker = _checker()
    assert checker.threshold_for("src/vigia_eew/app.py") is None
    bare = {"files": {"src/vigia_eew/app.py": {"summary": {"percent_covered": 1.0}}}}
    assert checker.violations(bare) == []
