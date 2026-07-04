"""Pruebas de la CLI (RF-26, RF-21)."""

from __future__ import annotations

import pytest

from vigia_eew.cli import main


class _FakeApp:
    creadas: list[_FakeApp] = []

    def __init__(self, cfg, *, referencia_manual=True):
        self.cfg = cfg
        self.referencia_manual = referencia_manual
        self.simulado = False
        self.ejecutado = False
        _FakeApp.creadas.append(self)

    def simular(self):
        self.simulado = True

    def ejecutar(self):
        self.ejecutado = True


def _crear(cfg, **kwargs):
    return _FakeApp(cfg, **kwargs)


def setup_function():
    _FakeApp.creadas.clear()


def test_simulate_invoca_simular():
    rc = main(["--simulate"], crear_app=_crear)
    assert rc == 0
    assert _FakeApp.creadas[-1].simulado is True


def test_run_por_defecto_invoca_ejecutar():
    rc = main([], crear_app=_crear)
    assert rc == 0
    assert _FakeApp.creadas[-1].ejecutado is True


def test_check_config_no_crea_app(capsys):
    rc = main(["--check-config"], crear_app=_crear)
    assert rc == 0
    assert _FakeApp.creadas == []  # check-config no arranca el agente
    assert "Config OK" in capsys.readouterr().out


def test_config_inexistente_falla():
    with pytest.raises(FileNotFoundError):
        main(["--config", "/ruta/que/no/existe.toml"], crear_app=_crear)


def test_sin_config_referencia_no_manual():
    # Sin --config y sin config.toml de usuario en este entorno de test -> no manual.
    rc = main([], crear_app=_crear)
    assert rc == 0
    assert _FakeApp.creadas[-1].referencia_manual is False


def test_config_con_referencia_es_manual(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text('[referencia]\nnombre = "Test"\nlat = 1.0\nlon = 2.0\n', encoding="utf-8")
    rc = main(["--config", str(ruta)], crear_app=_crear)
    assert rc == 0
    assert _FakeApp.creadas[-1].referencia_manual is True


def test_version_sale_limpio():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


class _FakeInstalador:
    def __init__(self):
        self.instalado = False
        self.desinstalado = False

    def instalar(self):
        self.instalado = True

    def desinstalar(self):
        self.desinstalado = True


def test_install_autostart_invoca_instalar(capsys):
    inst = _FakeInstalador()
    rc = main(["--install-autostart"], crear_app=_crear, crear_instalador=lambda: inst)
    assert rc == 0
    assert inst.instalado is True
    assert _FakeApp.creadas == []  # no arranca el agente


def test_uninstall_autostart_invoca_desinstalar():
    inst = _FakeInstalador()
    rc = main(["--uninstall-autostart"], crear_app=_crear, crear_instalador=lambda: inst)
    assert rc == 0
    assert inst.desinstalado is True
    assert _FakeApp.creadas == []
