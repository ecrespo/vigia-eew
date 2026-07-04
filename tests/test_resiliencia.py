"""Pruebas de resiliencia end-to-end (Fase 7, F7-4; CA-02, CA-04, CA-05, CA-07).

Los escenarios de fallo unitarios (WS caído, 429/5xx, JSON inválido, reinicio) ya están
cubiertos donde se implementó cada componente (`test_ws_emsc.py`, `test_rest_usgs.py`,
`test_supervisor.py`, `test_dedup.py`, `test_state.py`). Este módulo cierra la brecha que
quedaba: los mismos criterios de aceptación pero **a través del pipeline completo**
(`Procesador` con `Normalizer`/`GeoFilter`/`Deduplicator` reales) o combinando dos
componentes que hasta ahora solo se probaron por separado (`WSIngestor` dentro de un
`Supervisor` real).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from vigia_eew.config import Dedup, Filtro, FuenteEMSC, Referencia, Severidad
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.ws_emsc import WSIngestor
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.pipeline.filtro import GeoFilter
from vigia_eew.pipeline.normalize import Normalizer
from vigia_eew.pipeline.procesador import Procesador
from vigia_eew.state import StateStore
from vigia_eew.supervisor import Supervisor

# --- Fixtures crudas: mismo sismo (M6.1, cerca de Caracas) reportado por ambas fuentes ---

_EMSC_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "unid": "emsc-1",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}


def _raw_emsc(accion="create", **props) -> RawMessage:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "emsc-1",
        "properties": {**_EMSC_PROPS, **props},
    }
    return RawMessage(fuente="EMSC", action=accion, feature=feature)


def _raw_usgs(
    *, id_="us-1", lat=10.60, lon=-66.93, depth=12.0, mag=6.1, hora: datetime
) -> RawMessage:
    feature = {
        "type": "Feature",
        "id": id_,
        "properties": {
            "mag": mag,
            "place": "19 km WSW of Morón, Venezuela",
            "time": int(hora.timestamp() * 1000),
            "magType": "mw",
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
    }
    return RawMessage(fuente="USGS", action="create", feature=feature)


class _Captura:
    def __init__(self):
        self.alertados: list = []
        self.actualizados: list = []


def _procesador(tmp_path, captura, estado=None):
    estado = estado or StateStore(tmp_path / "state.json")
    estado.cargar()
    entrada: asyncio.Queue[RawMessage] = asyncio.Queue()
    proc = Procesador(
        entrada,
        Normalizer(Referencia(), Severidad()),
        GeoFilter(Filtro()),
        Deduplicator(Dedup(), estado),
        al_alertar=captura.alertados.append,
        al_actualizar=captura.actualizados.append,
    )
    return proc, estado


# --- CA-04: el respaldo USGS entrega, por sí solo, una alerta a través de todo el pipeline ---


async def test_evento_solo_usgs_genera_alerta_via_pipeline_completo(tmp_path):
    """Evento que el WS nunca vio (solo llegó por USGS) sigue disparando alerta (RF-05, OBJ-3)."""
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)
    hora = datetime(2026, 6, 28, 13, 39, 0, tzinfo=UTC)
    await proc.procesar_uno(_raw_usgs(hora=hora))
    assert [e.id for e in cap.alertados] == ["us-1"]
    assert cap.alertados[0].fuente == "USGS"


# --- CA-05: el mismo sismo por las dos fuentes produce una sola alerta, en el pipeline real ---


async def test_mismo_sismo_por_ambas_fuentes_una_sola_alerta(tmp_path):
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)

    await proc.procesar_uno(_raw_emsc())  # EMSC llega primero → alerta
    hora_usgs = datetime(2026, 6, 28, 13, 39, 25, tzinfo=UTC)  # 25 s después (ventana_s=90)
    await proc.procesar_uno(
        _raw_usgs(id_="us-1", lat=10.62, lon=-66.95, mag=6.3, hora=hora_usgs)  # cerca, Δmag=0.2
    )

    assert len(cap.alertados) == 1  # el reporte de USGS fue deduplicado, no una 2ª alerta
    assert cap.alertados[0].fuente == "EMSC"


async def test_mismo_sismo_fuera_de_heuristica_no_se_deduplica(tmp_path):
    """Control negativo: si la magnitud difiere más de lo tolerado, se trata como otro sismo."""
    cap = _Captura()
    proc, _ = _procesador(tmp_path, cap)

    await proc.procesar_uno(_raw_emsc())
    hora_usgs = datetime(2026, 6, 28, 13, 39, 25, tzinfo=UTC)
    await proc.procesar_uno(
        _raw_usgs(id_="us-2", lat=10.62, lon=-66.95, mag=3.0, hora=hora_usgs)  # Δmag=3.1 > 0.5
    )

    assert len(cap.alertados) == 2  # no hay heurística que los una: dos sismos distintos


# --- CA-07: al "reiniciar" el agente (StateStore en disco reabierto), no se re-alerta ---


async def test_reinicio_del_agente_no_realerta_evento_ya_visto(tmp_path):
    ruta_estado = tmp_path / "state.json"
    cap1 = _Captura()
    proc1, _ = _procesador(tmp_path, cap1, estado=StateStore(ruta_estado))
    await proc1.procesar_uno(_raw_emsc())
    assert len(cap1.alertados) == 1

    # "Reinicio": instancia nueva de Procesador+StateStore leyendo el mismo archivo.
    cap2 = _Captura()
    proc2, _ = _procesador(tmp_path, cap2, estado=StateStore(ruta_estado))
    await proc2.procesar_uno(_raw_emsc())  # mismo id que antes del reinicio

    assert cap2.alertados == []  # ya estaba alertado; el reinicio no lo repite


# --- CA-02 a nivel de integración: WSIngestor real corriendo dentro de un Supervisor real ---


class _FakeWS:
    def __init__(self, mensajes, *, error=None):
        self._mensajes = list(mensajes)
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._mensajes:
            return self._mensajes.pop(0)
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration


class _FakeConnect:
    def __init__(self, conexiones):
        self._conexiones = list(conexiones)

    def __call__(self, url, **kw):
        return self._conexiones.pop(0)


async def test_supervisor_mantiene_vivo_al_ws_ingestor_tras_una_caida():
    """El WSIngestor real, supervisado, sigue entregando mensajes tras una caída (CA-02)."""
    import json

    mensaje = json.dumps(
        {
            "action": "create",
            "data": {
                "type": "Feature",
                "id": "x",
                "geometry": {"type": "Point", "coordinates": [-66.9, 10.48, 12.0]},
                "properties": {**_EMSC_PROPS, "unid": "emsc-1"},
            },
        }
    )
    connect = _FakeConnect(
        [
            _FakeWS([], error=ConnectionResetError("caída simulada")),
            _FakeWS([mensaje]),
        ]
    )

    async def sleep_rapido(_segundos):
        await asyncio.sleep(0)  # no hay que esperar de verdad en el test

    salida: asyncio.Queue[RawMessage] = asyncio.Queue()
    ingestor = WSIngestor(FuenteEMSC(), salida, connect=connect, sleep=sleep_rapido, jitter=False)

    sup = Supervisor(sleep=sleep_rapido, jitter=False, manejar_senales=False)
    sup.add("ws", ingestor.run)

    run_task = asyncio.create_task(sup.run())
    try:
        msg = await asyncio.wait_for(salida.get(), timeout=1.0)
    finally:
        sup.solicitar_parada()
        await asyncio.wait_for(run_task, timeout=1.0)

    assert msg.fuente == "EMSC" and msg.feature["properties"]["unid"] == "emsc-1"
