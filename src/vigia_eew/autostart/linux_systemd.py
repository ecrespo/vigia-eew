"""Autostart on Linux via systemd `--user` (RF-22, RF-23).

Writes a unit to the user's systemd directory and enables it with
`systemctl --user enable --now`, so the agent starts on login and restarts on
failure (`Restart=on-failure`). Uninstalling disables the unit and removes it. The
`runner` (which runs `systemctl`) and the directory are injectable so tests don't
touch the real systemd.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

_Runner = Callable[[list[str]], int]

UNIT_NAME = "vigia-eew.service"
_DESCRIPTION = "Vigía-eew — seismic alert agent"


def systemd_unit(exec_cmd: str, *, description: str = _DESCRIPTION) -> str:
    """Generate the systemd unit content (pure)."""
    return (
        "[Unit]\n"
        f"Description={description}\n"
        "After=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_cmd}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _user_systemd_dir() -> Path:
    """User unit directory (respects `XDG_CONFIG_HOME`)."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "systemd" / "user"


def _subprocess_runner(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


class SystemdInstaller:
    """Installs/uninstalls the agent's autostart via systemd --user."""

    def __init__(
        self,
        *,
        exec_cmd: str,
        unit_dir: Path | None = None,
        runner: _Runner | None = None,
        description: str = _DESCRIPTION,
        logger: logging.Logger | None = None,
    ) -> None:
        self._exec = exec_cmd
        self._dir = unit_dir or _user_systemd_dir()
        self._runner = runner or _subprocess_runner
        self._description = description
        self._log = logger or logging.getLogger("vigia_eew.autostart.systemd")

    @property
    def path(self) -> Path:
        return self._dir / UNIT_NAME

    def is_installed(self) -> bool:
        return self.path.exists()

    def install(self) -> None:
        """Write the unit and enable it to start on login (RF-22)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            systemd_unit(self._exec, description=self._description), encoding="utf-8"
        )
        self._runner(["systemctl", "--user", "daemon-reload"])
        self._runner(["systemctl", "--user", "enable", "--now", UNIT_NAME])
        self._log.info("autostart_installed path=%s", self.path)

    def uninstall(self) -> None:
        """Disable the service and remove the unit (RF-23)."""
        self._runner(["systemctl", "--user", "disable", "--now", UNIT_NAME])
        if self.path.exists():
            self.path.unlink()
        self._runner(["systemctl", "--user", "daemon-reload"])
        self._log.info("autostart_uninstalled")
