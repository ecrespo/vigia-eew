"""Pruebas del ingestor WebSocket EMSC (RF-01, RF-02, RF-03, RF-04)."""

from __future__ import annotations

import asyncio
import json

import pytest

from vigia_eew.config import FuenteEMSC
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.ws_emsc import WSIngestor

# Mensaje EMSC de ejemplo (API-SPEC §1.3).
_MENSAJE_EMSC = {
    "action": "create",
    "data": {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.90, 10.48, 12.0]},
        "id": "20260628_0000123",
        "properties": {
            "lat": 10.48,
            "lon": -66.90,
            "depth": 12.0,
            "mag": 6.1,
            "magtype": "mw",
            "time": "2026-06-28T13:39:00.0Z",
            "lastupdate": "2026-06-28T13:41:00.0Z",
            "unid": "20260628_0000123",
            "flynn_region": "NEAR COAST OF VENEZUELA",
        },
    },
}


# --- Dobles de prueba para el transporte WebSocket ---


class _FakeWS:
    """Conexión WS falsa: context manager + iterador asíncrono de mensajes."""

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
    """Factoría de conexión inyectable que registra los kwargs (keepalive)."""

    def __init__(self, conexiones):
        self._conexiones = list(conexiones)
        self.llamadas = []

    def __call__(self, url, **kw):
        self.llamadas.append((url, kw))
        return self._conexiones.pop(0)


class _SleepControlado:
    """Sleep falso que registra esperas y corta el bucle tras N llamadas."""

    def __init__(self, romper_en):
        self.esperas = []
        self._romper_en = romper_en

    async def __call__(self, segundos):
        self.esperas.append(segundos)
        if len(self.esperas) >= self._romper_en:
            raise asyncio.CancelledError


# --- Parseo de mensajes ---


def _ingestor(salida=None, **kw):
    return WSIngestor(FuenteEMSC(), salida or asyncio.Queue(), **kw)


def test_parsear_mensaje_valido():
    ing = _ingestor()
    msg = ing._parsear(json.dumps(_MENSAJE_EMSC))
    assert isinstance(msg, RawMessage)
    assert msg.fuente == "EMSC"
    assert msg.action == "create"
    assert msg.feature["properties"]["unid"] == "20260628_0000123"


def test_parsear_action_update():
    ing = _ingestor()
    crudo = dict(_MENSAJE_EMSC, action="update")
    msg = ing._parsear(json.dumps(crudo))
    assert msg is not None
    assert msg.action == "update"


def test_parsear_acepta_bytes():
    ing = _ingestor()
    msg = ing._parsear(json.dumps(_MENSAJE_EMSC).encode("utf-8"))
    assert msg is not None and msg.fuente == "EMSC"


def test_parsear_json_invalido_devuelve_none():
    ing = _ingestor()
    assert ing._parsear("{ no es json ") is None


def test_parsear_sin_data_devuelve_none():
    ing = _ingestor()
    assert ing._parsear(json.dumps({"action": "create"})) is None


# --- Bucle de conexión / reconexión ---


async def test_recibe_y_encola_evento():
    salida: asyncio.Queue[RawMessage] = asyncio.Queue()
    connect = _FakeConnect([_FakeWS([json.dumps(_MENSAJE_EMSC)])])
    sleep = _SleepControlado(romper_en=1)  # corta al primer backoff (tras agotar mensajes)
    ing = _ingestor(salida, connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    msg = salida.get_nowait()
    assert msg.fuente == "EMSC" and msg.action == "create"


async def test_pasa_keepalive_a_connect():
    cfg = FuenteEMSC(ping_interval_s=15, ping_timeout_s=20)
    connect = _FakeConnect([_FakeWS([])])
    sleep = _SleepControlado(romper_en=1)
    ing = WSIngestor(cfg, asyncio.Queue(), connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    _, kwargs = connect.llamadas[0]
    assert kwargs["ping_interval"] == 15
    assert kwargs["ping_timeout"] == 20


async def test_reconecta_tras_caida():
    # 1ª conexión cae con error; debe reconectar (2º connect) tras un backoff.
    connect = _FakeConnect(
        [
            _FakeWS([], error=ConnectionResetError("caída")),
            _FakeWS([json.dumps(_MENSAJE_EMSC)]),
        ]
    )
    sleep = _SleepControlado(romper_en=2)  # permite una reconexión, corta en el 2º backoff
    salida: asyncio.Queue[RawMessage] = asyncio.Queue()
    ing = _ingestor(salida, connect=connect, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert len(connect.llamadas) == 2  # reconectó
    assert salida.get_nowait().action == "create"  # 2ª conexión sí entregó


async def test_backoff_crece_entre_reintentos():
    # Sin jitter, las esperas deben crecer: 1 s, luego 2 s.
    connect = _FakeConnect([_FakeWS([]), _FakeWS([]), _FakeWS([])])
    sleep = _SleepControlado(romper_en=2)
    ing = _ingestor(asyncio.Queue(), connect=connect, sleep=sleep, jitter=False)

    with pytest.raises(asyncio.CancelledError):
        await ing.run()

    assert sleep.esperas == [1.0, 2.0]
