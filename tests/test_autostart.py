"""Pruebas de la fachada de autoarranque (RF-22, RF-23, RF-26)."""

from __future__ import annotations

import sys

import pytest

from vigia_eew.autostart import comando_agente, crear_instalador
from vigia_eew.autostart.linux_systemd import InstaladorSystemd
from vigia_eew.autostart.macos_launchagent import InstaladorLaunchAgent
from vigia_eew.autostart.windows_task import InstaladorSchtasks


def test_comando_agente_apunta_al_cli():
    cmd = comando_agente()
    assert cmd[-2:] == ["-m", "vigia_eew.cli"]
    assert "python" in cmd[0].lower()


def test_comando_agente_congelado_usa_solo_el_ejecutable(monkeypatch):
    # Empaquetado con PyInstaller (RF-28..RF-30): el propio binario ya es el agente,
    # no un intérprete que acepte `-m`.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd = comando_agente()
    assert cmd == [sys.executable]


def test_crear_instalador_linux():
    assert isinstance(crear_instalador("linux"), InstaladorSystemd)


def test_crear_instalador_macos():
    assert isinstance(crear_instalador("darwin"), InstaladorLaunchAgent)


def test_crear_instalador_windows():
    assert isinstance(crear_instalador("win32"), InstaladorSchtasks)


def test_crear_instalador_por_defecto_usa_plataforma_actual():
    # No debe lanzar en la plataforma de ejecución (Linux/macOS/Windows).
    inst = crear_instalador()
    assert hasattr(inst, "instalar") and hasattr(inst, "desinstalar")
    assert sys.platform in ("linux", "darwin", "win32")


def test_so_no_soportado_falla_claro():
    with pytest.raises(NotImplementedError):
        crear_instalador("sunos5")
