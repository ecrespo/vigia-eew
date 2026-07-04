"""Pruebas del autoarranque por LaunchAgent en macOS (RF-22, RF-23)."""

from __future__ import annotations

import plistlib

from vigia_eew.autostart.macos_launchagent import (
    LABEL,
    InstaladorLaunchAgent,
    plist_launchagent,
)


class _Runner:
    def __init__(self):
        self.cmds: list[list[str]] = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        return 0


def _instalador(tmp_path, runner):
    return InstaladorLaunchAgent(
        program_args=["/usr/bin/python", "-m", "vigia_eew.cli"],
        dir_agents=tmp_path,
        runner=runner,
    )


def test_plist_contiene_label_args_y_runatload():
    data = plistlib.loads(plist_launchagent(["/usr/bin/python", "-m", "vigia_eew.cli"]).encode())
    assert data["Label"] == LABEL
    assert data["ProgramArguments"] == ["/usr/bin/python", "-m", "vigia_eew.cli"]
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True


def test_instalar_escribe_plist_y_carga(tmp_path):
    runner = _Runner()
    inst = _instalador(tmp_path, runner)
    inst.instalar()

    ruta = tmp_path / f"{LABEL}.plist"
    assert ruta.exists()
    assert any("load" in c and "-w" in c for c in runner.cmds)


def test_esta_instalado(tmp_path):
    inst = _instalador(tmp_path, _Runner())
    assert inst.esta_instalado() is False
    inst.instalar()
    assert inst.esta_instalado() is True


def test_desinstalar_descarga_y_remueve(tmp_path):
    runner = _Runner()
    inst = _instalador(tmp_path, runner)
    inst.instalar()
    runner.cmds.clear()

    inst.desinstalar()
    assert (tmp_path / f"{LABEL}.plist").exists() is False
    assert any("unload" in c for c in runner.cmds)


def test_desinstalar_sin_instalar_no_falla(tmp_path):
    _instalador(tmp_path, _Runner()).desinstalar()  # no debe lanzar
