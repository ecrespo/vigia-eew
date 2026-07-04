"""Autoarranque en Linux mediante systemd `--user` (RF-22, RF-23).

Escribe un *unit* en el directorio de systemd del usuario y lo habilita con
`systemctl --user enable --now`, de modo que el agente arranque al iniciar sesión y
se reinicie ante fallos (`Restart=on-failure`). La desinstalación deshabilita y borra
el unit. El `runner` (que ejecuta `systemctl`) y el directorio son inyectables para
poder probar sin tocar el systemd real.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

_Runner = Callable[[list[str]], int]

NOMBRE_UNIDAD = "vigia-eew.service"
_DESCRIPCION = "Vigía-eew — agente de alerta sísmica"


def unidad_systemd(exec_cmd: str, *, descripcion: str = _DESCRIPCION) -> str:
    """Genera el contenido del unit de systemd (puro)."""
    return (
        "[Unit]\n"
        f"Description={descripcion}\n"
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


def _dir_systemd_usuario() -> Path:
    """Directorio de units de usuario (respeta `XDG_CONFIG_HOME`)."""
    base = os.environ.get("XDG_CONFIG_HOME")
    raiz = Path(base) if base else Path.home() / ".config"
    return raiz / "systemd" / "user"


def _runner_subprocess(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


class InstaladorSystemd:
    """Instala/desinstala el autoarranque del agente vía systemd --user."""

    def __init__(
        self,
        *,
        exec_cmd: str,
        dir_unidades: Path | None = None,
        runner: _Runner | None = None,
        descripcion: str = _DESCRIPCION,
        logger: logging.Logger | None = None,
    ) -> None:
        self._exec = exec_cmd
        self._dir = dir_unidades or _dir_systemd_usuario()
        self._runner = runner or _runner_subprocess
        self._descripcion = descripcion
        self._log = logger or logging.getLogger("vigia_eew.autostart.systemd")

    @property
    def ruta(self) -> Path:
        return self._dir / NOMBRE_UNIDAD

    def esta_instalado(self) -> bool:
        return self.ruta.exists()

    def instalar(self) -> None:
        """Escribe el unit y lo habilita para arrancar al iniciar sesión (RF-22)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            unidad_systemd(self._exec, descripcion=self._descripcion), encoding="utf-8"
        )
        self._runner(["systemctl", "--user", "daemon-reload"])
        self._runner(["systemctl", "--user", "enable", "--now", NOMBRE_UNIDAD])
        self._log.info("autostart_instalado ruta=%s", self.ruta)

    def desinstalar(self) -> None:
        """Deshabilita el servicio y borra el unit (RF-23)."""
        self._runner(["systemctl", "--user", "disable", "--now", NOMBRE_UNIDAD])
        if self.ruta.exists():
            self.ruta.unlink()
        self._runner(["systemctl", "--user", "daemon-reload"])
        self._log.info("autostart_desinstalado")
