"""Pruebas de la cola de alertas y el puente asyncio↔Tk (RF-20, RF-11, ADR-006)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.queue import AlertQueue, PuenteAsyncioTk


def _ev(id="e1", accion="create", mag=6.0) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        fuente="EMSC",
        magnitud=mag,
        mag_type="mw",
        lat=10.5,
        lon=-66.9,
        profundidad_km=10.0,
        hora_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distancia_km=20.0,
        severidad="critico",
        accion=accion,
    )


class _Sink:
    def __init__(self):
        self.mostrados: list[SeismicEvent] = []
        self.actualizados: list[SeismicEvent] = []
        self.reconocidos: list[SeismicEvent] = []


def _cola(sink: _Sink) -> AlertQueue:
    return AlertQueue(
        mostrar=sink.mostrados.append,
        actualizar=sink.actualizados.append,
        al_reconocer=sink.reconocidos.append,
    )


# --- Cola: una alerta a la vez, en orden (RF-20) ---


def test_muestra_al_encolar():
    s = _Sink()
    cola = _cola(s)
    cola.encolar(_ev("a"))
    assert [e.id for e in s.mostrados] == ["a"]
    assert cola.actual is not None and cola.actual.id == "a"


def test_una_a_la_vez():
    s = _Sink()
    cola = _cola(s)
    cola.encolar(_ev("a"))
    cola.encolar(_ev("b"))
    assert [e.id for e in s.mostrados] == ["a"]  # b espera
    assert cola.pendientes == 1


def test_reconocer_muestra_siguiente():
    s = _Sink()
    cola = _cola(s)
    cola.encolar(_ev("a"))
    cola.encolar(_ev("b"))
    cola.reconocer()
    assert [e.id for e in s.mostrados] == ["a", "b"]
    assert [e.id for e in s.reconocidos] == ["a"]
    assert cola.actual is not None and cola.actual.id == "b"


def test_orden_fifo():
    s = _Sink()
    cola = _cola(s)
    for x in ("a", "b", "c"):
        cola.encolar(_ev(x))
    cola.reconocer()
    cola.reconocer()
    assert [e.id for e in s.mostrados] == ["a", "b", "c"]


def test_reconocer_sin_actual_no_rompe():
    s = _Sink()
    cola = _cola(s)
    cola.reconocer()  # no debe lanzar
    assert s.mostrados == []
    assert cola.actual is None


# --- Update en pantalla (RF-11) ---


def test_update_del_evento_en_curso_actualiza_sin_reencolar():
    s = _Sink()
    cola = _cola(s)
    cola.encolar(_ev("x", mag=6.0))
    cola.encolar(_ev("x", accion="update", mag=6.4))
    assert [e.id for e in s.mostrados] == ["x"]  # no se mostró otra vez
    assert [e.magnitud for e in s.actualizados] == [6.4]  # se actualizó en pantalla
    assert cola.actual is not None and cola.actual.magnitud == 6.4
    assert cola.pendientes == 0


def test_update_de_otro_id_se_encola():
    s = _Sink()
    cola = _cola(s)
    cola.encolar(_ev("x"))
    cola.encolar(_ev("y", accion="update"))
    assert cola.pendientes == 1
    assert s.actualizados == []


# --- Puente asyncio↔Tk (ADR-006) ---


def test_puente_drena_en_orden():
    recibidos: list[SeismicEvent] = []
    puente = PuenteAsyncioTk(sink=recibidos.append)
    for x in ("a", "b", "c"):
        puente.publicar(_ev(x))
    puente.drenar()
    assert [e.id for e in recibidos] == ["a", "b", "c"]


def test_puente_drenar_vacio_no_hace_nada():
    recibidos: list[SeismicEvent] = []
    PuenteAsyncioTk(sink=recibidos.append).drenar()
    assert recibidos == []


class _FakeWidget:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))


def test_puente_inicia_sondeo_programa_after():
    puente = PuenteAsyncioTk(sink=lambda e: None)
    widget = _FakeWidget()
    puente.iniciar_sondeo(widget, intervalo_ms=200)
    assert widget.after_calls[0][0] == 200
    assert callable(widget.after_calls[0][1])
