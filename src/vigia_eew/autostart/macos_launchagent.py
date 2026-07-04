"""Autoarranque en macOS mediante LaunchAgent (RF-22, RF-23).

Escribe un `.plist` en `~/Library/LaunchAgents` con `RunAtLoad` (arranca al iniciar
sesión) y `KeepAlive` (lo relanza si muere), y lo carga con `launchctl load -w`. La
desinstalación lo descarga y borra. El `runner` (`launchctl`) y el directorio son
inyectables para probar sin tocar el `launchd` real.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
from collections.abc import Callable
from pathlib import Path

_Runner = Callable[[list[str]], int]

LABEL = "com.vigia-eew.agent"


def plist_launchagent(program_args: list[str], *, label: str = LABEL) -> str:
    """Genera el contenido del `.plist` del LaunchAgent (puro)."""
    datos = {
        "Label": label,
        "ProgramArguments": list(program_args),
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    return plistlib.dumps(datos).decode("utf-8")


def _dir_launchagents() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _runner_subprocess(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


class InstaladorLaunchAgent:
    """Instala/desinstala el autoarranque del agente vía LaunchAgent."""

    def __init__(
        self,
        *,
        program_args: list[str],
        dir_agents: Path | None = None,
        runner: _Runner | None = None,
        label: str = LABEL,
        logger: logging.Logger | None = None,
    ) -> None:
        self._args = program_args
        self._dir = dir_agents or _dir_launchagents()
        self._runner = runner or _runner_subprocess
        self._label = label
        self._log = logger or logging.getLogger("vigia_eew.autostart.launchagent")

    @property
    def ruta(self) -> Path:
        return self._dir / f"{self._label}.plist"

    def esta_instalado(self) -> bool:
        return self.ruta.exists()

    def instalar(self) -> None:
        """Escribe el plist y lo carga para arrancar al iniciar sesión (RF-22)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            plist_launchagent(self._args, label=self._label), encoding="utf-8"
        )
        self._runner(["launchctl", "load", "-w", str(self.ruta)])
        self._log.info("autostart_instalado ruta=%s", self.ruta)

    def desinstalar(self) -> None:
        """Descarga el agente y borra el plist (RF-23)."""
        self._runner(["launchctl", "unload", "-w", str(self.ruta)])
        if self.ruta.exists():
            self.ruta.unlink()
        self._log.info("autostart_desinstalado")
