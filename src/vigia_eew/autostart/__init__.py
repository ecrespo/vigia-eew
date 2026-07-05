"""Autostart on login (RF-22, RF-23).

Each OS has its own mechanism: **systemd --user** (Linux), **LaunchAgent** (macOS), and
**scheduled task / schtasks** (Windows). Each backend separates the *generation* of the
artifact (unit/plist/command, pure and testable) from the system *runner* (injectable),
and exposes a common interface (`Installer`): `install()`, `uninstall()`, `is_installed()`.

`create_installer()` selects the backend by platform; the CLI uses it for
`--install-autostart` / `--uninstall-autostart`. `agent_command()` defines how the
agent is launched (RF-26) in the autostart artifact.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable
from typing import Protocol

from vigia_eew.autostart.linux_systemd import SystemdInstaller
from vigia_eew.autostart.macos_launchagent import LaunchAgentInstaller
from vigia_eew.autostart.windows_task import SchtasksInstaller

_Runner = Callable[[list[str]], int]


class Installer(Protocol):
    """Common interface for autostart installers."""

    def install(self) -> None: ...
    def uninstall(self) -> None: ...
    def is_installed(self) -> bool: ...


def agent_command() -> list[str]:
    """Command that launches the agent from autostart (RF-26).

    Packaged (PyInstaller, RF-28..RF-30): `sys.frozen` is `True` and `sys.executable`
    **is** the agent's own binary (`.exe`/AppImage) — invoked directly, without `-m`.
    In a development checkout: uses the current interpreter with `-m vigia_eew.cli`,
    robust against how the *console script* is installed. On Windows it prefers
    `pythonw.exe` (no console window for the GUI).
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    executable = sys.executable
    if sys.platform == "win32" and executable.lower().endswith("python.exe"):
        no_console = executable[: -len("python.exe")] + "pythonw.exe"
        executable = no_console
    return [executable, "-m", "vigia_eew.cli"]


def create_installer(
    platform: str | None = None,
    *,
    exec_cmd: str | None = None,
    runner: _Runner | None = None,
) -> Installer:
    """Return the autostart installer appropriate for the platform.

    Args:
        platform: `sys.platform`-style identifier; defaults to the current one.
        exec_cmd: already-formatted agent command; defaults to one derived from
            `agent_command`.
        runner: system command executor (injectable for tests).

    Raises:
        NotImplementedError: if the platform has no supported autostart mechanism.
    """
    platform = platform or sys.platform
    args = agent_command()

    if platform.startswith("linux"):
        return SystemdInstaller(exec_cmd=exec_cmd or shlex.join(args), runner=runner)
    if platform == "darwin":
        return LaunchAgentInstaller(program_args=args, runner=runner)
    if platform == "win32":
        return SchtasksInstaller(
            exec_cmd=exec_cmd or subprocess.list2cmdline(args), runner=runner
        )
    raise NotImplementedError(f"Autostart not supported on platform: {platform}")
