"""Tests for the declared dependency contract (REQ-DEP-001..008, HU-101).

These assert facts about the *declared* metadata -- what `pyproject.toml`, the
lockfile and the CI workflows promise -- rather than about runtime behaviour.
A resolution that only the developer's machine can reproduce is exactly the
failure mode HU-101 exists to prevent, and it is invisible to every other test
in this suite.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_ENV_ACTION = REPO_ROOT / ".github" / "actions" / "setup-python-env" / "action.yml"
SECURITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security.yml"
BUILD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: Amendment E-01. 3.12 entered security-only, so the floor declared by a
#: project about to call itself 1.0.0 would be a runtime that no longer
#: receives bug fixes.
RUNTIME_FLOOR = "3.13"

#: Resolved only on macOS or Windows, so a Linux-only audit never sees them
#: (docs/code-audit/analysis/deps-omitidas-plataforma.txt).
PLATFORM_ONLY_PACKAGES = (
    "colorama",
    "pyobjc-core",
    "pyobjc-framework-cocoa",
    "pyobjc-framework-quartz",
    "pywin32-ctypes",
    "rubicon-objc",
)

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


def test_the_platform_only_packages_are_in_the_lockfile() -> None:
    """CA-101.8: the six packages a Linux-only audit cannot reach are real.

    If the lockfile stopped resolving them the gap would close by accident,
    and the audit matrix below would be guarding nothing.
    """
    lockfile = (REPO_ROOT / "uv.lock").read_text()
    for package in PLATFORM_ONLY_PACKAGES:
        assert f'name = "{package}"' in lockfile


def test_composition_is_audited_on_every_platform() -> None:
    """CA-101.8: each platform is audited on its own runner.

    Six of the fifteen runtime packages only resolve on macOS or Windows.
    Auditing from Linux alone reports nine and calls it the tree.
    """
    workflow = SECURITY_WORKFLOW.read_text()
    audit_job = workflow.split("pip-audit:", 1)[1].split("\n  # ", 1)[0]
    for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
        assert runner in audit_job


def test_the_runtime_floor_is_declared_once_per_place() -> None:
    """CA-101.5: pyproject, ruff and mypy declare the same floor.

    Three declarations of the same fact drift apart silently: ruff and mypy
    keep linting against a grammar and a stdlib the project no longer
    supports, and nothing fails to say so.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    major, minor = RUNTIME_FLOOR.split(".")

    assert config["project"]["requires-python"] == f">={RUNTIME_FLOOR}"
    assert config["tool"]["ruff"]["target-version"] == f"py{major}{minor}"
    assert config["tool"]["mypy"]["python_version"] == RUNTIME_FLOOR


def test_no_classifier_advertises_an_unsupported_runtime() -> None:
    """CA-101.5: the package does not claim a version it no longer supports.

    A classifier is what PyPI shows and what a resolver reads; leaving 3.11
    there invites an install that `requires-python` will then refuse.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    classifiers = config["project"]["classifiers"]
    assert "Programming Language :: Python :: 3.11" not in classifiers
    assert "Programming Language :: Python :: 3.12" not in classifiers
    assert f"Programming Language :: Python :: {RUNTIME_FLOOR}" in classifiers


def test_the_three_build_jobs_pin_the_declared_floor() -> None:
    """CA-101.5: the three binaries are built on the runtime the project declares.

    These three live in a CI file nobody opens while editing pyproject.toml,
    which is exactly why they were still on 3.11.
    """
    workflow = BUILD_WORKFLOW.read_text()
    pinned = re.findall(r'python-version: "([^"]+)"', workflow)
    assert len(pinned) == 3, f"expected three build jobs, found {len(pinned)}"
    assert set(pinned) == {RUNTIME_FLOOR}


def test_compatibility_is_verified_on_two_versions() -> None:
    """CA-101.6: the suite runs on the floor and on the version above it.

    A floor verified on one interpreter is a floor nobody has tested moving
    off, which is how the next bump becomes a surprise.
    """
    workflow = CI_WORKFLOW.read_text()
    assert RUNTIME_FLOOR in workflow
    assert "3.14" in workflow


def _declared_ranges() -> dict[str, str]:
    """The runtime dependency ranges, keyed by lowercase package name."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    ranges = {}
    for spec in config["project"]["dependencies"]:
        name = re.split(r"[<>=!~\[]", spec, maxsplit=1)[0].strip()
        ranges[name.lower()] = spec[len(name) :].strip()
    return ranges


def test_the_pillow_floor_is_its_security_floor() -> None:
    """CA-101.3: the floor no longer admits versions with published advisories.

    Pillow>=10.0 admitted 34 known advisories. The lockfile resolved a clean
    version, but the range is the only thing the published package declares,
    so it is what anyone installing from PyPI actually gets bounded by.
    """
    assert _declared_ranges()["pillow"] == ">=12.3.0,<13"
