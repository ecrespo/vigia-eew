"""Pruebas del ensamblaje de la aplicación (RF-26, wiring de supervisor/notificación)."""

from __future__ import annotations

import asyncio

from vigia_eew.app import Aplicacion
from vigia_eew.config import FuenteEMSC, FuenteUSGS, Settings
from vigia_eew.simulacion import evento_simulado


class _FakeVentana:
    def actualizar(self, datos):
        pass


def _app(**cfg_kw) -> Aplicacion:
    return Aplicacion(Settings(**cfg_kw))


# --- Wiring del supervisor según fuentes habilitadas ---


def test_supervisor_con_ambas_fuentes():
    app = _app()
    sup = app._construir_supervisor(asyncio.Queue(), object())
    assert sup.nombres == ["ws", "rest", "pipeline"]


def test_supervisor_sin_emsc():
    app = _app(fuentes_emsc=FuenteEMSC(habilitado=False))
    sup = app._construir_supervisor(asyncio.Queue(), object())
    assert sup.nombres == ["rest", "pipeline"]


def test_supervisor_sin_usgs():
    app = _app(fuentes_usgs=FuenteUSGS(habilitado=False))
    sup = app._construir_supervisor(asyncio.Queue(), object())
    assert sup.nombres == ["ws", "pipeline"]


# --- Controlador de notificación construido por la app ---


def test_controlador_formatea_y_muestra():
    app = _app()
    vistos: list = []
    ctrl = app._construir_controlador(
        lambda datos, severidad, al_reconocer: vistos.append((datos, severidad)) or _FakeVentana(),
    )
    ctrl.encolar(evento_simulado(app.cfg.referencia, app.cfg.severidad))
    assert len(vistos) == 1
    datos, severidad = vistos[0]
    assert datos.magnitud == "M 6.1"
    assert severidad == "critico"
    assert "La Guaira" in datos.lugar
