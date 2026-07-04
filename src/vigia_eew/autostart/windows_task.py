"""Autoarranque en Windows mediante tarea programada (`schtasks`) (RF-22, RF-23).

Crea una tarea con disparador **onlogon** (arranca al iniciar sesión) con privilegios
limitados, y la borra al desinstalar. No escribe ficheros: el estado vive en el
Programador de tareas, consultado con `schtasks /query`. El `runner` (`schtasks`) es
inyectable para probar sin tocar el sistema real.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

_Runner = Callable[[list[str]], int]

TASK_NAME = "VigiaEEW"


def comando_crear(task_name: str, exec_cmd: str) -> list[str]:
    """Comando `schtasks` para crear la tarea de inicio de sesión (puro)."""
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


def comando_borrar(task_name: str) -> list[str]:
    """Comando `schtasks` para borrar la tarea (puro)."""
    return ["schtasks", "/delete", "/tn", task_name, "/f"]


def comando_consulta(task_name: str) -> list[str]:
    """Comando `schtasks` para consultar si la tarea existe (puro)."""
    return ["schtasks", "/query", "/tn", task_name]


def _runner_subprocess(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode


class InstaladorSchtasks:
    """Instala/desinstala el autoarranque del agente vía tarea programada."""

    def __init__(
        self,
        *,
        exec_cmd: str,
        runner: _Runner | None = None,
        task_name: str = TASK_NAME,
        logger: logging.Logger | None = None,
    ) -> None:
        self._exec = exec_cmd
        self._runner = runner or _runner_subprocess
        self._task = task_name
        self._log = logger or logging.getLogger("vigia_eew.autostart.schtasks")

    def esta_instalado(self) -> bool:
        return self._runner(comando_consulta(self._task)) == 0

    def instalar(self) -> None:
        """Crea la tarea programada de inicio de sesión (RF-22)."""
        self._runner(comando_crear(self._task, self._exec))
        self._log.info("autostart_instalado tarea=%s", self._task)

    def desinstalar(self) -> None:
        """Borra la tarea programada (RF-23)."""
        self._runner(comando_borrar(self._task))
        self._log.info("autostart_desinstalado tarea=%s", self._task)
