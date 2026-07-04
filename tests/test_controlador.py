"""Pruebas del controlador de alertas (orquesta cola + ventana + sonido + toast)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.estado_agente import EstadoAgente
from vigia_eew.models import SeismicEvent
from vigia_eew.notify.controlador import ControladorAlertas


def _ev(id="e1", accion="create", mag=6.1) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        fuente="EMSC",
        magnitud=mag,
        mag_type="mw",
        lugar="La Guaira",
        lat=10.6,
        lon=-66.93,
        profundidad_km=10.0,
        hora_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distancia_km=15.0,
        severidad="critico",
        accion=accion,
    )


class _FakeVentana:
    def __init__(self, datos, severidad, al_reconocer):
        self.datos = datos
        self.severidad = severidad
        self.al_reconocer = al_reconocer
        self.actualizada = None

    def actualizar(self, datos):
        self.actualizada = datos


class _Cap:
    def __init__(self):
        self.ventanas: list[_FakeVentana] = []
        self.sonidos: list[str] = []
        self.toasts: list[SeismicEvent] = []

    def crear_ventana(self, datos, severidad, al_reconocer):
        v = _FakeVentana(datos, severidad, al_reconocer)
        self.ventanas.append(v)
        return v


def _controlador(cap, *, con_sonido=True, con_toast=True):
    return ControladorAlertas(
        crear_ventana=cap.crear_ventana,
        reproducir_sonido=cap.sonidos.append if con_sonido else None,
        enviar_toast=cap.toasts.append if con_toast else None,
        nombre_referencia="Caracas",
    )


def test_encolar_muestra_ventana_sonido_y_toast():
    cap = _Cap()
    ctrl = _controlador(cap)
    ctrl.encolar(_ev())
    assert len(cap.ventanas) == 1
    assert cap.ventanas[0].datos.magnitud == "M 6.1"
    assert cap.sonidos == ["critico"]
    assert [e.id for e in cap.toasts] == ["e1"]


def test_una_a_la_vez_y_reconocer_muestra_siguiente():
    cap = _Cap()
    ctrl = _controlador(cap)
    ctrl.encolar(_ev("a"))
    ctrl.encolar(_ev("b"))
    assert len(cap.ventanas) == 1  # b espera
    cap.ventanas[0].al_reconocer()  # usuario pulsa RECONOCIDO
    assert len(cap.ventanas) == 2
    assert cap.ventanas[1].datos is not None


def test_update_actualiza_ventana_en_curso():
    cap = _Cap()
    ctrl = _controlador(cap)
    ctrl.encolar(_ev("x", mag=6.1))
    ctrl.encolar(_ev("x", accion="update", mag=6.5))
    assert len(cap.ventanas) == 1  # no se creó otra
    assert cap.ventanas[0].actualizada is not None
    assert cap.ventanas[0].actualizada.magnitud == "M 6.5"


def test_sin_sonido_ni_toast_no_falla():
    cap = _Cap()
    ctrl = _controlador(cap, con_sonido=False, con_toast=False)
    ctrl.encolar(_ev())
    assert len(cap.ventanas) == 1
    assert cap.sonidos == [] and cap.toasts == []


# --- Pausar/reanudar (RF-34) ---


def test_pausar_y_reanudar_delegan_a_la_cola():
    cap = _Cap()
    ctrl = _controlador(cap)
    ctrl.pausar()
    assert ctrl.pausado is True
    ctrl.encolar(_ev("a"))
    assert cap.ventanas == []  # no se muestra mientras está pausado
    ctrl.reanudar()
    assert ctrl.pausado is False
    assert len(cap.ventanas) == 1


# --- EstadoAgente: última alerta (RF-34) ---


def test_mostrar_actualiza_estado_agente():
    cap = _Cap()
    estado = EstadoAgente()
    ctrl = ControladorAlertas(
        crear_ventana=cap.crear_ventana, nombre_referencia="Caracas", estado=estado
    )
    ctrl.encolar(_ev())
    assert estado.ultima_alerta is not None
    assert "M 6.1" in estado.ultima_alerta
    assert "La Guaira" in estado.ultima_alerta
