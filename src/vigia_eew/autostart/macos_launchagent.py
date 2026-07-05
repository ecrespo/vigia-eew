"""Autostart on macOS via LaunchAgent (RF-22, RF-23).

Writes a `.plist` to `~/Library/LaunchAgents` with `RunAtLoad` (starts on login)
and `KeepAlive` (relaunches it if it dies), and loads it with `launchctl load -w`.
Uninstalling unloads it and removes the file. The `runner` (`launchctl`) and the
directory are injectable so tests don't touch the real `launchd`.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
from collections.abc import Callable
from pathlib import Path

from vigia_eew.subprocess_env import system_env

_Runner = Callable[[list[str]], int]

LABEL = "com.vigia-eew.agent"


def launchagent_plist(program_args: list[str], *, label: str = LABEL) -> str:
    """Generate the LaunchAgent `.plist` content (pure)."""
    data = {
        "Label": label,
        "ProgramArguments": list(program_args),
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    return plistlib.dumps(data).decode("utf-8")


def _launchagents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _subprocess_runner(cmd: list[str]) -> int:
    # env=system_env() strips the PyInstaller-injected DYLD_LIBRARY_PATH so launchctl
    # loads the system libraries, not the ones bundled in the onefile temp dir.
    return subprocess.run(cmd, check=False, env=system_env()).returncode


class LaunchAgentInstaller:
    """Installs/uninstalls the agent's autostart via LaunchAgent."""

    def __init__(
        self,
        *,
        program_args: list[str],
        agents_dir: Path | None = None,
        runner: _Runner | None = None,
        label: str = LABEL,
        logger: logging.Logger | None = None,
    ) -> None:
        self._args = program_args
        self._dir = agents_dir or _launchagents_dir()
        self._runner = runner or _subprocess_runner
        self._label = label
        self._log = logger or logging.getLogger("vigia_eew.autostart.launchagent")

    @property
    def path(self) -> Path:
        return self._dir / f"{self._label}.plist"

    def is_installed(self) -> bool:
        return self.path.exists()

    def install(self) -> None:
        """Write the plist and load it to start on login (RF-22)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            launchagent_plist(self._args, label=self._label), encoding="utf-8"
        )
        self._runner(["launchctl", "load", "-w", str(self.path)])
        self._log.info("autostart_installed path=%s", self.path)

    def uninstall(self) -> None:
        """Unload the agent and remove the plist (RF-23)."""
        self._runner(["launchctl", "unload", "-w", str(self.path)])
        if self.path.exists():
            self.path.unlink()
        self._log.info("autostart_uninstalled")
