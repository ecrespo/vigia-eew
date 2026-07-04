"""Pruebas del ícono de bandeja (RF-34). Lógica pura; sin arrancar pystray real."""

from __future__ import annotations

import subprocess
import sys

from vigia_eew.estado_agente import EstadoAgente
from vigia_eew.tray import (
    IconoBandeja,
    _comando_abrir,
    abrir_config,
    construir_icono,
    ruta_icono_predeterminada,
)

# --- Comando de SO para abrir un archivo (puro) ---


def test_comando_abrir_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _comando_abrir(tmp_path / "config.toml") == ["xdg-open", str(tmp_path / "config.toml")]


def test_comando_abrir_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _comando_abrir(tmp_path / "config.toml") == ["open", str(tmp_path / "config.toml")]


def test_comando_abrir_windows_usa_startfile(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    assert _comando_abrir(tmp_path / "config.toml") is None


# --- abrir_config: crea el archivo si falta y lo abre (efecto aislado) ---


def test_abrir_config_crea_archivo_si_falta(monkeypatch, tmp_path):
    ruta = tmp_path / "sub" / "config.toml"
    llamadas = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: llamadas.append(cmd))
    monkeypatch.setattr(sys, "platform", "linux")

    abrir_config(ruta)

    assert ruta.exists()
    assert llamadas == [["xdg-open", str(ruta)]]


def test_abrir_config_no_pisa_archivo_existente(monkeypatch, tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text("[filtro]\nmagnitud_minima = 4.0\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: None)
    monkeypatch.setattr(sys, "platform", "linux")

    abrir_config(ruta)

    assert "magnitud_minima" in ruta.read_text(encoding="utf-8")


def test_abrir_config_falla_no_lanza(monkeypatch, tmp_path):
    ruta = tmp_path / "config.toml"

    def _falla(cmd):
        raise OSError("no hay xdg-open")

    monkeypatch.setattr(subprocess, "Popen", _falla)
    monkeypatch.setattr(sys, "platform", "linux")

    abrir_config(ruta)  # no debe lanzar


# --- Construcción del ícono (sin arrancar el backend real) ---


def test_ruta_icono_predeterminada_existe():
    assert ruta_icono_predeterminada().exists()


def test_construir_icono_arma_menu_con_acciones():
    estado = EstadoAgente()
    llamadas = {"pausa": 0, "config": 0, "salir": 0}
    icono = construir_icono(
        estado=estado,
        pausado=lambda: False,
        alternar_pausa=lambda: llamadas.__setitem__("pausa", llamadas["pausa"] + 1),
        editar_config=lambda: llamadas.__setitem__("config", llamadas["config"] + 1),
        salir=lambda: llamadas.__setitem__("salir", llamadas["salir"] + 1),
    )
    items = list(icono.menu)
    textos = [str(i.text) for i in items if i.text is not None]
    assert any("conectad" in t.lower() or "reconectando" in t.lower() for t in textos)
    assert any("pausar" in t.lower() for t in textos)
    assert any("editar configuración" in t.lower() for t in textos)
    assert any("salir" in t.lower() for t in textos)

    # Disparar cada acción invoca el callback inyectado (sin tocar pystray real).
    for item in items:
        if item.text and "salir" in str(item.text).lower():
            item(icono)
    assert llamadas["salir"] == 1


# --- IconoBandeja: aislamiento de fallos (RF-34) ---


class _IconoFalso:
    def __init__(self, *, falla_run=None):
        self._falla_run = falla_run
        self.detenido = False

    def run(self):
        if self._falla_run is not None:
            raise self._falla_run

    def stop(self):
        self.detenido = True


def test_iniciar_no_propaga_fallo_del_backend():
    icono = IconoBandeja(_IconoFalso(falla_run=RuntimeError("sin display")))
    icono.iniciar()  # no debe lanzar
    icono._hilo.join(timeout=2.0)
    assert icono._hilo.is_alive() is False


def test_detener_llama_stop_y_espera_el_hilo():
    falso = _IconoFalso()
    icono = IconoBandeja(falso)
    icono.iniciar()
    icono.detener()
    assert falso.detenido is True
