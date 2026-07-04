"""Pruebas del ensamblaje de la aplicación (RF-26, wiring de supervisor/notificación)."""

from __future__ import annotations

import asyncio

from vigia_eew.app import Aplicacion
from vigia_eew.config import FuenteEMSC, FuenteUSGS, Referencia, Settings
from vigia_eew.simulacion import evento_simulado
from vigia_eew.state import StateStore


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


# --- Detección automática de ubicación por IP (RF-33) ---


def test_preparar_sin_resolver_no_llama_geoloc(tmp_path):
    llamadas: list[int] = []
    app = Aplicacion(
        Settings(),
        estado=StateStore(tmp_path / "state.json"),
        referencia_manual=False,
        detectar_ubicacion=lambda: llamadas.append(1) or None,
    )
    app._preparar()  # resolver_ubicacion=False por defecto (usado por --simulate)
    assert llamadas == []


def test_preparar_resuelve_ubicacion_automatica(tmp_path):
    detectada = Referencia(nombre="Maracaibo", lat=10.63, lon=-71.64)
    app = Aplicacion(
        Settings(),
        estado=StateStore(tmp_path / "state.json"),
        referencia_manual=False,
        detectar_ubicacion=lambda: detectada,
    )
    app._preparar(resolver_ubicacion=True)
    assert app.cfg.referencia.nombre == "Maracaibo"
    cacheada = app.estado.ubicacion_cacheada()
    assert cacheada is not None
    assert cacheada.nombre == "Maracaibo"


def test_preparar_respeta_referencia_manual(tmp_path):
    llamadas: list[int] = []
    app = Aplicacion(
        Settings(referencia={"nombre": "Valencia", "lat": 10.16, "lon": -68.0}),
        estado=StateStore(tmp_path / "state.json"),
        referencia_manual=True,
        detectar_ubicacion=lambda: llamadas.append(1) or Referencia(nombre="x", lat=0, lon=0),
    )
    app._preparar(resolver_ubicacion=True)
    assert llamadas == []
    assert app.cfg.referencia.nombre == "Valencia"


def test_preparar_usa_cache_sin_llamar_geoloc(tmp_path):
    ruta_estado = tmp_path / "state.json"
    previo = StateStore(ruta_estado)
    previo.cargar()
    previo.cachear_ubicacion(Referencia(nombre="Cache", lat=1.0, lon=2.0))
    previo.guardar()

    llamadas: list[int] = []
    app = Aplicacion(
        Settings(),
        estado=StateStore(ruta_estado),
        referencia_manual=False,
        detectar_ubicacion=lambda: llamadas.append(1) or None,
    )
    app._preparar(resolver_ubicacion=True)
    assert llamadas == []
    assert app.cfg.referencia.nombre == "Cache"


def test_preparar_fallback_a_default_si_geoloc_falla(tmp_path):
    app = Aplicacion(
        Settings(),
        estado=StateStore(tmp_path / "state.json"),
        referencia_manual=False,
        detectar_ubicacion=lambda: None,
    )
    app._preparar(resolver_ubicacion=True)
    assert app.cfg.referencia.nombre == "Caracas"  # default, sin cachear
    assert app.estado.ubicacion_cacheada() is None
