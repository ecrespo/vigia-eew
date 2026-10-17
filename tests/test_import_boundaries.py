"""Tests for the declared import boundaries (REQ-OBS-005, HU-103).

The file-level dependency graph has zero cycles today (`arch-eval/` P2-2).
These contracts do not repair a cycle -- they stop the first one, and with it
the kind of drift that turns a layered design into a ball of mud one import at
a time. The check itself runs in the gate; this module asserts that it is
declared and that the current tree satisfies it, so a violating import fails
the suite too, not only the hook.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every contract HU-103 expects to be enforced, by name.
EXPECTED_CONTRACTS = {
    "Layered architecture",
    "The pipeline does not know about presentation",
    "Ingestion knows nothing downstream",
    "The adapters are independent of one another",
}


def _contracts() -> dict[str, dict[str, object]]:
    """The import-linter contracts declared in pyproject.toml, keyed by name."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    declared = config.get("tool", {}).get("importlinter", {}).get("contracts", [])
    return {c["name"]: c for c in declared}


def test_every_expected_contract_is_declared() -> None:
    """CA-103.4: the boundary a violation would cross has a name to be reported by."""
    assert EXPECTED_CONTRACTS <= set(_contracts())


def test_pipeline_to_presentation_is_forbidden() -> None:
    """CA-103.4: the pipeline importing a notification module is a declared violation.

    Named explicitly rather than left to the layered contract: the scenario
    asks for the *violated contract* to be reported, and "forbidden" says
    which import is wrong far more directly than a layer ordering does.
    """
    contract = _contracts()["The pipeline does not know about presentation"]
    assert contract["type"] == "forbidden"
    assert "vigia_eew.pipeline" in contract["source_modules"]
    assert "vigia_eew.notify" in contract["forbidden_modules"]


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("lint-imports") is None, reason="import-linter not installed")
def test_current_tree_satisfies_every_contract() -> None:
    """CA-103.5: the contracts hold today, so any new cycle is the first failure.

    A layered contract is violated by exactly the upward import that a cycle
    between two layers requires, so this is also what keeps the graph acyclic.
    """
    result = subprocess.run(
        ["lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
