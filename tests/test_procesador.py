"""Pruebas del procesador del pipeline (une normalize→filtro→dedup, RF-07..RF-13)."""

from __future__ import annotations

import asyncio

import pytest

from vigia_eew.config import Dedup, Filtro, Referencia, Severidad
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filtro import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.procesador import Procesador
from vigia_eew.state import StateStore

_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "unid": "emsc-1",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}


def _raw(accion="create", **props) -> RawMessage:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "emsc-1",
        "properties": {**_PROPS, **props},
    }
    return RawMessage(fuente="EMSC", action=accion, feature=feature)


class _Captura:
    def __init__(self):
        self.alertados: list[SeismicEvent] = []
        self.actualizados: list[SeismicEvent] = []


def _procesador(tmp_path, captura, *, radio=300.0):
    estado = StateStore(tmp_path / "state.json")
    estado.cargar()
    entrada: asyncio.Queue[RawMessage] = asyncio.Queue()
    proc = Procesador(
        entrada,
        Normalizer(Referencia(), Severidad()),
        GeoFilter(Filtro(radio_km=radio)),
        Deduplicator(Dedup(), estado),
        al_alertar=captura.alertados.append,
        al_actualizar=captura.actualizados.append,
    )
    return proc, entrada


async def test_evento_nuevo_relevante_alerta(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)
    await proc.procesar_uno(_raw())
    assert [e.id for e in cap.alertados] == ["emsc-1"]


async def test_evento_fuera_de_radio_no_alerta(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap, radio=1.0)  # radio diminuto
    await proc.procesar_uno(_raw())
    assert cap.alertados == []


async def test_crudo_invalido_no_alerta(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)
    await proc.procesar_uno(RawMessage(fuente="EMSC", action="create", feature={"properties": {}}))
    assert cap.alertados == []


async def test_duplicado_no_alerta_dos_veces(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)
    await proc.procesar_uno(_raw())
    await proc.procesar_uno(_raw())  # mismo id
    assert len(cap.alertados) == 1


async def test_update_actualiza_no_alerta(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)
    await proc.procesar_uno(_raw())  # create (alerta + registra)
    await proc.procesar_uno(_raw(accion="update", mag=6.4))
    assert len(cap.alertados) == 1
    assert [e.magnitud for e in cap.actualizados] == [6.4]


async def test_run_consume_de_la_cola(tmp_path):
    cap = _Captura()
    proc, entrada = _procesador(tmp_path, cap)
    entrada.put_nowait(_raw())
    tarea = asyncio.create_task(proc.run())
    await asyncio.sleep(0.05)
    tarea.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarea
    assert [e.id for e in cap.alertados] == ["emsc-1"]
