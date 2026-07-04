"""Pruebas del autoarranque por systemd --user (RF-22, RF-23)."""

from __future__ import annotations

from vigia_eew.autostart.linux_systemd import InstaladorSystemd, unidad_systemd


class _Runner:
    def __init__(self):
        self.cmds: list[list[str]] = []

    def __call__(self, cmd):
        self.cmds.append(cmd)
        return 0


def _instalador(tmp_path, runner):
    return InstaladorSystemd(
        exec_cmd="/usr/bin/python -m vigia_eew.cli",
        dir_unidades=tmp_path,
        runner=runner,
    )


# --- Generación del unit (pura) ---


def test_unidad_contiene_execstart_y_wantedby():
    texto = unidad_systemd("/usr/bin/python -m vigia_eew.cli", descripcion="Vigía")
    assert "ExecStart=/usr/bin/python -m vigia_eew.cli" in texto
    assert "WantedBy=default.target" in texto
    assert "Restart=on-failure" in texto
    assert "Description=Vigía" in texto


# --- Instalar / desinstalar ---


def test_instalar_escribe_unit_y_habilita(tmp_path):
    runner = _Runner()
    inst = _instalador(tmp_path, runner)
    inst.instalar()

    ruta = tmp_path / "vigia-eew.service"
    assert ruta.exists()
    assert "ExecStart=" in ruta.read_text(encoding="utf-8")
    # daemon-reload + enable --now
    assert ["systemctl", "--user", "daemon-reload"] in runner.cmds
    assert any("enable" in c and "--now" in c for c in runner.cmds)


def test_esta_instalado(tmp_path):
    inst = _instalador(tmp_path, _Runner())
    assert inst.esta_instalado() is False
    inst.instalar()
    assert inst.esta_instalado() is True


def test_desinstalar_remueve_unit_y_deshabilita(tmp_path):
    runner = _Runner()
    inst = _instalador(tmp_path, runner)
    inst.instalar()
    runner.cmds.clear()

    inst.desinstalar()
    assert (tmp_path / "vigia-eew.service").exists() is False
    assert any("disable" in c and "--now" in c for c in runner.cmds)


def test_desinstalar_sin_instalar_no_falla(tmp_path):
    inst = _instalador(tmp_path, _Runner())
    inst.desinstalar()  # no debe lanzar aunque no exista el unit
    assert inst.esta_instalado() is False
