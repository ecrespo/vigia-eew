"""Autoarranque al iniciar sesión (RF-22, RF-23).

Cada SO tiene su mecanismo: **systemd --user** (Linux), **LaunchAgent** (macOS) y
**tarea programada / schtasks** (Windows). Cada backend separa la *generación* del
artefacto (unit/plist/comando, puro y testeable) del *runner* del sistema (inyectable),
y expone una interfaz común (`Instalador`): `instalar()`, `desinstalar()`, `esta_instalado()`.

`crear_instalador()` selecciona el backend por plataforma; la CLI lo usa para
`--install-autostart` / `--uninstall-autostart`. `comando_agente()` define cómo se lanza
el agente (RF-26) en el artefacto de autoarranque.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable
from typing import Protocol

from .linux_systemd import InstaladorSystemd
from .macos_launchagent import InstaladorLaunchAgent
from .windows_task import InstaladorSchtasks

_Runner = Callable[[list[str]], int]


class Instalador(Protocol):
    """Interfaz común de los instaladores de autoarranque."""

    def instalar(self) -> None: ...
    def desinstalar(self) -> None: ...
    def esta_instalado(self) -> bool: ...


def comando_agente() -> list[str]:
    """Comando que lanza el agente desde el autoarranque (RF-26).

    Usa el intérprete actual con `-m vigia_eew.cli`, robusto frente a la instalación
    del *console script*. En Windows prefiere `pythonw.exe` (sin consola para la GUI).
    """
    ejecutable = sys.executable
    if sys.platform == "win32" and ejecutable.lower().endswith("python.exe"):
        sin_consola = ejecutable[: -len("python.exe")] + "pythonw.exe"
        ejecutable = sin_consola
    return [ejecutable, "-m", "vigia_eew.cli"]


def crear_instalador(
    plataforma: str | None = None,
    *,
    exec_cmd: str | None = None,
    runner: _Runner | None = None,
) -> Instalador:
    """Devuelve el instalador de autoarranque adecuado para la plataforma.

    Args:
        plataforma: identificador estilo `sys.platform`; por defecto el actual.
        exec_cmd: comando del agente ya formateado; por defecto se deriva de `comando_agente`.
        runner: ejecutor de comandos del sistema (inyectable para pruebas).

    Raises:
        NotImplementedError: si la plataforma no tiene mecanismo de autoarranque soportado.
    """
    plataforma = plataforma or sys.platform
    args = comando_agente()

    if plataforma.startswith("linux"):
        return InstaladorSystemd(exec_cmd=exec_cmd or shlex.join(args), runner=runner)
    if plataforma == "darwin":
        return InstaladorLaunchAgent(program_args=args, runner=runner)
    if plataforma == "win32":
        return InstaladorSchtasks(
            exec_cmd=exec_cmd or subprocess.list2cmdline(args), runner=runner
        )
    raise NotImplementedError(f"Autoarranque no soportado en la plataforma: {plataforma}")
