"""Pruebas de la ventana de alerta no descartable (RF-15, RF-16, RF-19)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.alert_window import (
    AlertWindow,
    configurar_no_descartable,
    tomar_foco,
)
from vigia_eew.notify.presentacion import DatosAlerta, formatear_evento


def _datos() -> DatosAlerta:
    ev = SeismicEvent(
        id="x",
        fuente="EMSC",
        magnitud=6.1,
        mag_type="mw",
        lugar="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        profundidad_km=12.0,
        hora_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distancia_km=162.0,
        severidad="critico",
    )
    return formatear_evento(ev, nombre_referencia="Caracas")


class _FakeRaiz:
    """Raíz Tk falsa que registra la configuración aplicada."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.binds: dict = {}
        self.protocolos: dict = {}
        self.destruida = False

    def overrideredirect(self, v):
        self.calls.append(("overrideredirect", v))

    def attributes(self, *a):
        self.calls.append(("attributes", *a))

    def protocol(self, name, fn):
        self.protocolos[name] = fn

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def lift(self):
        self.calls.append(("lift",))

    def focus_force(self):
        self.calls.append(("focus_force",))

    def destroy(self):
        self.destruida = True


# --- Política no descartable (RF-15, RF-16, RF-19) ---


def test_politica_topmost_y_sin_decoracion():
    r = _FakeRaiz()
    configurar_no_descartable(r, al_cerrar_intento=lambda: None)
    assert ("overrideredirect", True) in r.calls
    assert ("attributes", "-topmost", True) in r.calls


def test_politica_x_no_cierra():
    r = _FakeRaiz()

    def cerrar():
        return None

    configurar_no_descartable(r, al_cerrar_intento=cerrar)
    assert r.protocolos["WM_DELETE_WINDOW"] is cerrar


def test_politica_escape_no_cierra():
    r = _FakeRaiz()
    configurar_no_descartable(r, al_cerrar_intento=lambda: None)
    assert "<Escape>" in r.binds
    assert r.binds["<Escape>"](None) == "break"  # interrumpe el evento, no cierra


def test_politica_focusout_se_reeleva():
    r = _FakeRaiz()
    configurar_no_descartable(r, al_cerrar_intento=lambda: None)
    assert "<FocusOut>" in r.binds
    r.binds["<FocusOut>"](None)
    assert ("lift",) in r.calls and ("focus_force",) in r.calls


def test_tomar_foco_eleva_y_fuerza_foco():
    r = _FakeRaiz()
    tomar_foco(r)
    assert ("lift",) in r.calls and ("focus_force",) in r.calls


# --- Reconocimiento (RF-19, CU-5) ---


def test_reconocer_llama_callback_y_destruye():
    rec: list[int] = []
    w = AlertWindow(_datos(), al_reconocer=lambda: rec.append(1), raiz=_FakeRaiz(), construir=False)
    w.reconocer()
    assert rec == [1]
    assert w.raiz.destruida is True


def test_reconocer_es_idempotente():
    rec: list[int] = []
    w = AlertWindow(_datos(), al_reconocer=lambda: rec.append(1), raiz=_FakeRaiz(), construir=False)
    w.reconocer()
    w.reconocer()
    assert rec == [1]  # un solo reconocimiento aunque se invoque dos veces


def test_intento_de_cierre_no_destruye():
    w = AlertWindow(_datos(), al_reconocer=lambda: None, raiz=_FakeRaiz(), construir=False)
    w._intento_cierre()  # X / WM_DELETE_WINDOW
    assert w.raiz.destruida is False


# --- Smoke con Tkinter real (opt-in: VIGIA_GUI_TESTS=1) ---


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="prueba de GUI real; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_construye_ventana_real():
    import tkinter as tk

    raiz = tk.Tk()
    rec: list[int] = []
    w = AlertWindow(_datos(), al_reconocer=lambda: rec.append(1), raiz=raiz)
    raiz.update()
    # El árbol de widgets se construyó (etiquetas + botón RECONOCIDO).
    # No se verifica `-topmost` por consulta: con overrideredirect la ventana queda
    # sin gestionar por el WM y el atributo no es consultable de forma fiable.
    assert len(raiz.winfo_children()) > 0
    w.reconocer()
    assert rec == [1]


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="prueba de GUI real; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_detalle_tiene_wraplength():
    # Sin wraplength, una línea larga (p. ej. "Hora local (Venezuela): ...") se
    # recorta contra el borde de la ventana en vez de bajar de línea (ventana fija,
    # no redimensionable). Ver alert_window.py::_construir.
    import tkinter as tk

    raiz = tk.Tk()
    AlertWindow(_datos(), al_reconocer=lambda: None, raiz=raiz)
    raiz.update()
    etiquetas = [w for w in raiz.winfo_children() if isinstance(w, tk.Label)]
    detalle = next(w for w in etiquetas if "Hora local" in w.cget("text"))
    assert int(detalle.cget("wraplength")) > 0


@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="prueba de GUI real; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_alto_ventana_alcanza_para_el_contenido():
    # La ventana no es redimensionable ni scrolleable (overrideredirect, RF-15): el
    # alto fijado debe ser siempre >= lo que el contenido empaquetado realmente pide,
    # medido en la propia pantalla (fuentes/DPI reales), no un número fijo adivinado.
    import tkinter as tk

    raiz = tk.Tk()
    w = AlertWindow(_datos(), al_reconocer=lambda: None, raiz=raiz)
    raiz.update_idletasks()
    alto_ventana = int(raiz.geometry().split("+")[0].split("x")[1])
    assert alto_ventana >= raiz.winfo_reqheight()
    w.reconocer()
