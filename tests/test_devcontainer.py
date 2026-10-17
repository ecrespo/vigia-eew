"""Tests for the contribution environment (REQ-DEV-001..003, HU-109).

The obstacle this environment removes is specific to this project and not
at all obvious: the GUI is Flet (ADR-030), whose Linux desktop client is a
Flutter binary that links GTK 3 **from the system**. A base image without it
fails only when a window opens. A contributor hits that with no hint of where
to go.

Docker cannot run inside the suite, so what is asserted here is that the
declaration contains what the acceptance criteria require. The behaviour
behind each assertion was verified by hand against a real virtual display
before the file was written.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEVCONTAINER = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def _config() -> dict:
    """Parse devcontainer.json, which is JSONC: comments are part of the format."""
    text = DEVCONTAINER.read_text()
    without_comments = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return json.loads(without_comments)


def _commands() -> str:
    config = _config()
    keys = ("onCreateCommand", "postCreateCommand", "postStartCommand")
    return " ".join(str(config.get(key, "")) for key in keys)


def test_the_system_gui_libraries_are_installed() -> None:
    """CA-109.2: the Flet desktop client can open a window.

    The client links GTK 3 from the system, so an image without it fails when
    the window opens -- after a green `uv sync`, which makes it look like a
    code problem.
    """
    assert "libgtk-3-0" in _commands()


def test_dependencies_are_synced_without_manual_steps() -> None:
    """CA-109.1: `uv run vigia-eew --check-config` works on a fresh container."""
    assert "uv sync" in _commands()


def test_the_gate_installs_itself() -> None:
    """CA-109.3: the hooks are installed for the contributor, not by them.

    A gate somebody has to remember to install is a gate that catches the
    second commit, never the first.
    """
    assert "pre-commit install" in _commands()


def test_a_virtual_display_is_available() -> None:
    """CA-109.4: the real-GUI tests can be run, not just skipped."""
    config = _config()
    assert "xvfb" in _commands().lower()
    assert config["containerEnv"]["DISPLAY"]


def test_the_interpreter_matches_the_declared_floor() -> None:
    """The image brings the version the project requires.

    Building it on the old floor and redoing it after the runtime bump is
    the duplicated work HU-109 sequences this task after F1's T-111 to avoid.
    """
    import tomllib

    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    floor = config["project"]["requires-python"].removeprefix(">=")
    assert floor in json.dumps(_config())
