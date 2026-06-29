"""Pruebas de la CLI (RF-26, RF-21)."""

from __future__ import annotations

import pytest

from vigia_eew.cli import main


class _FakeApp:
    creadas: list[_FakeApp] = []

    def __init__(self, cfg):
        self.cfg = cfg
        self.simulado = False
        self.ejecutado = False
        _FakeApp.creadas.append(self)

    def simular(self):
        self.simulado = True

    def ejecutar(self):
        self.ejecutado = True


def _crear(cfg):
    return _FakeApp(cfg)


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


def test_version_sale_limpio():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
