"""Pruebas del autoarranque por tarea programada en Windows (RF-22, RF-23)."""

from __future__ import annotations

from vigia_eew.autostart.windows_task import (
    TASK_NAME,
    InstaladorSchtasks,
    comando_borrar,
    comando_crear,
)


class _FakeSchtasks:
    """Runner falso que simula el estado de la tarea programada."""

    def __init__(self):
        self.cmds: list[list[str]] = []
        self.existe = False

    def __call__(self, cmd):
        self.cmds.append(cmd)
        if "/create" in cmd:
            self.existe = True
            return 0
        if "/delete" in cmd:
            self.existe = False
            return 0
        if "/query" in cmd:
            return 0 if self.existe else 1
        return 0


def _instalador(runner):
    return InstaladorSchtasks(exec_cmd='"C:\\Py\\pythonw.exe" -m vigia_eew.cli', runner=runner)


# --- Generación de comandos (pura) ---


def test_comando_crear_onlogon():
    cmd = comando_crear("VigiaEEW", "exe")
    assert cmd[:2] == ["schtasks", "/create"]
    assert "/tn" in cmd and "VigiaEEW" in cmd
    assert "/tr" in cmd and "exe" in cmd
    assert cmd[cmd.index("/sc") + 1] == "onlogon"


def test_comando_borrar():
    cmd = comando_borrar("VigiaEEW")
    assert cmd[:2] == ["schtasks", "/delete"]
    assert "VigiaEEW" in cmd and "/f" in cmd


# --- Instalar / desinstalar ---


def test_instalar_crea_tarea():
    runner = _FakeSchtasks()
    inst = _instalador(runner)
    inst.instalar()
    assert any("/create" in c for c in runner.cmds)
    assert inst.esta_instalado() is True


def test_desinstalar_borra_tarea():
    runner = _FakeSchtasks()
    inst = _instalador(runner)
    inst.instalar()
    inst.desinstalar()
    assert any("/delete" in c for c in runner.cmds)
    assert inst.esta_instalado() is False


def test_usa_task_name_por_defecto():
    runner = _FakeSchtasks()
    InstaladorSchtasks(exec_cmd="x", runner=runner).instalar()
    assert TASK_NAME in runner.cmds[0]
