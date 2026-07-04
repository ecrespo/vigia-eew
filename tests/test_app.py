"""Pruebas del ensamblaje de la aplicación (RF-26, wiring de supervisor/notificación)."""

from __future__ import annotations

import asyncio

from vigia_eew.app import Aplicacion
from vigia_eew.config import FuenteEMSC, FuenteUSGS, Notificacion, Referencia, Settings
from vigia_eew.simulacion import evento_simulado
from vigia_eew.state import StateStore
from vigia_eew.tray import IconoBandeja


class _FakeVentana:
    def actualizar(self, datos):
        pass


class _FakeRaiz:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))

    def quit(self):
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


# --- Ícono de bandeja (RF-34) ---


def test_construir_tray_deshabilitado_devuelve_none():
    app = _app(notificacion=Notificacion(icono_bandeja=False))
    assert app._construir_tray() is None


def test_construir_tray_habilitado_devuelve_icono():
    app = _app()
    icono = app._construir_tray()
    assert isinstance(icono, IconoBandeja)


def test_alternar_pausa_programa_en_hilo_de_tk():
    app = _app()
    app._root = _FakeRaiz()
    ctrl = app._construir_controlador(lambda datos, severidad, al_reconocer: _FakeVentana())
    assert ctrl.pausado is False

    app._alternar_pausa()
    assert len(app._root.after_calls) == 1
    ms, callback = app._root.after_calls[0]
    assert ms == 0
    callback()  # ejecuta lo agendado, como haría el mainloop real de Tk
    assert ctrl.pausado is True


def test_salir_desde_tray_programa_quit():
    app = _app()
    app._root = _FakeRaiz()
    app._salir_desde_tray()
    assert len(app._root.after_calls) == 1
    ms, callback = app._root.after_calls[0]
    assert ms == 0
    assert callable(callback)


def test_editar_config_usa_ruta_explicita(monkeypatch, tmp_path):
    ruta = tmp_path / "config.toml"
    llamadas = []
    import vigia_eew.app as app_mod

    monkeypatch.setattr(app_mod.tray, "abrir_config", lambda r: llamadas.append(r))
    app = Aplicacion(Settings(), ruta_config=ruta)
    app._editar_config()
    assert llamadas == [ruta]


def test_editar_config_usa_ruta_default_sin_config_explicito(monkeypatch):
    llamadas = []
    import vigia_eew.app as app_mod

    monkeypatch.setattr(app_mod.tray, "abrir_config", lambda r: llamadas.append(r))
    app = _app()
    app._editar_config()
    assert len(llamadas) == 1
    assert llamadas[0] == app_mod.ruta_config_predeterminada()
