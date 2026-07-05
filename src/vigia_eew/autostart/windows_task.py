"""Autostart on Windows via scheduled task (`schtasks`) (RF-22, RF-23).

Creates a task with an **onlogon** trigger (starts on login) with limited
privileges, and deletes it on uninstall. It writes no files: the state lives in
Task Scheduler, queried with `schtasks /query`. The `runner` (`schtasks`) is
injectable so tests don't touch the real system.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from vigia_eew.subprocess_env import system_env

_Runner = Callable[[list[str]], int]

TASK_NAME = "VigiaEEW"


def create_command(task_name: str, exec_cmd: str) -> list[str]:
    """`schtasks` command to create the login task (pure)."""
    return [
        "schtasks",
        "/create",
        "/tn",
        task_name,
        "/tr",
        exec_cmd,
        "/sc",
        "onlogon",
        "/rl",
        "limited",
        "/f",
    ]


def delete_command(task_name: str) -> list[str]:
    """`schtasks` command to delete the task (pure)."""
    return ["schtasks", "/delete", "/tn", task_name, "/f"]


def query_command(task_name: str) -> list[str]:
    """`schtasks` command to check whether the task exists (pure)."""
    return ["schtasks", "/query", "/tn", task_name]


def _subprocess_runner(cmd: list[str]) -> int:
    # env=system_env() is a no-op off-Windows/unfrozen; kept for consistency with the
    # other backends so a frozen build never leaks the bundle's library path.
    return subprocess.run(cmd, check=False, env=system_env()).returncode


class SchtasksInstaller:
    """Installs/uninstalls the agent's autostart via scheduled task."""

    def __init__(
        self,
        *,
        exec_cmd: str,
        runner: _Runner | None = None,
        task_name: str = TASK_NAME,
        logger: logging.Logger | None = None,
    ) -> None:
        self._exec = exec_cmd
        self._runner = runner or _subprocess_runner
        self._task = task_name
        self._log = logger or logging.getLogger("vigia_eew.autostart.schtasks")

    def is_installed(self) -> bool:
        return self._runner(query_command(self._task)) == 0

    def install(self) -> None:
        """Create the scheduled login task (RF-22)."""
        self._runner(create_command(self._task, self._exec))
        self._log.info("autostart_installed task=%s", self._task)

    def uninstall(self) -> None:
        """Delete the scheduled task (RF-23)."""
        self._runner(delete_command(self._task))
        self._log.info("autostart_uninstalled task=%s", self._task)
