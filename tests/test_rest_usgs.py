"""Pruebas del reconciliador REST USGS (RF-05, RF-06, RNF-03)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from vigia_eew.config import Filtro, FuenteUSGS, Referencia
from vigia_eew.ingest import RawMessage
from vigia_eew.ingest.rest_usgs import RESTReconciler
from vigia_eew.state import StateStore

# Respuesta USGS de ejemplo (API-SPEC §2.4), recortada.
_FEATURE = {
    "type": "Feature",
    "id": "us6000t8sx",
    "properties": {
        "mag": 4.3,
        "place": "19 km WSW of Morón, Venezuela",
        "time": 1782639238852,
        "updated": 1782655565862,
        "magType": "mb",
        "type": "earthquake",
    },
    "geometry": {"type": "Point", "coordinates": [-68.3766, 10.4497, 10]},
}
_FEATURE_2 = {
    "type": "Feature",
    "id": "us6000t900",
    "properties": {"mag": 4.5, "place": "Boca de Aroa", "time": 1782700000000, "magType": "mb"},
    "geometry": {"type": "Point", "coordinates": [-68.3, 10.6, 12]},
}


def _coleccion(*features):
    return {"type": "FeatureCollection", "metadata": {"status": 200}, "features": list(features)}


# --- Dobles de prueba para el cliente httpx ---


class _FakeResp:
    def __init__(self, status=200, payload=None, headers=None, json_error=False):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("json inválido")
        return self._payload


class _FakeClient:
    def __init__(self, resp=None, *, exc=None):
        self._resp = resp
        self._exc = exc
        self.llamadas: list[dict] = []

    async def get(self, url, *, params=None, timeout=None):
        self.llamadas.append({"url": url, "params": params, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._resp


def _reconciler(tmp_path, client, *, sleep=None):
    estado = StateStore(tmp_path / "state.json")
    estado.cargar()
    rec = RESTReconciler(
        FuenteUSGS(),
        Referencia(),
        Filtro(),
        estado,
        asyncio.Queue(),
        client=client,
        sleep=sleep or asyncio.sleep,
    )
    return rec, estado


# --- Construcción de la consulta ---


async def test_params_fijos_y_sin_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion()))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    params = client.llamadas[0]["params"]
    assert params["format"] == "geojson"
    assert params["latitude"] == Referencia().lat
    assert params["longitude"] == Referencia().lon
    assert params["maxradiuskm"] == Filtro().radio_km
    assert params["minmagnitude"] == Filtro().magnitud_minima
    assert params["orderby"] == "time"
    assert params["eventtype"] == "earthquake"
    assert "starttime" not in params  # sin cursor previo


async def test_params_incluyen_starttime_con_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion()))
    rec, estado = _reconciler(tmp_path, client)
    estado.actualizar_cursor_usgs(1782639238852)
    await rec.poll_once()

    params = client.llamadas[0]["params"]
    assert "starttime" in params
    assert params["starttime"].startswith("2026-")  # ISO-8601 derivado del cursor


# --- Emisión y cursor ---


async def test_emite_un_rawmessage_por_feature(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion(_FEATURE, _FEATURE_2)))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    msgs = [rec._salida.get_nowait(), rec._salida.get_nowait()]
    assert all(isinstance(m, RawMessage) for m in msgs)
    assert {m.feature["id"] for m in msgs} == {"us6000t8sx", "us6000t900"}
    assert msgs[0].fuente == "USGS" and msgs[0].action == "create"


async def test_avanza_y_persiste_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion(_FEATURE, _FEATURE_2)))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()

    # Cursor al `time` máximo visto y persistido en disco (RF-06).
    recargado = StateStore(tmp_path / "state.json")
    recargado.cargar()
    assert recargado.estado.cursor_usgs_ms == 1782700000000


async def test_respuesta_vacia_no_mueve_cursor(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion()))
    rec, estado = _reconciler(tmp_path, client)
    await rec.poll_once()
    assert estado.estado.cursor_usgs_ms is None


# --- Resiliencia (RNF-03) ---


async def test_429_respeta_retry_after(tmp_path):
    client = _FakeClient(_FakeResp(status=429, headers={"Retry-After": "120"}))
    rec, estado = _reconciler(tmp_path, client)
    espera = await rec.poll_once()
    assert espera == 120.0  # honra Retry-After
    assert rec._salida.empty()
    assert estado.estado.cursor_usgs_ms is None  # cursor intacto


async def test_5xx_no_rompe_y_reintenta(tmp_path):
    client = _FakeClient(_FakeResp(status=503))
    rec, _ = _reconciler(tmp_path, client)
    espera = await rec.poll_once()  # no debe lanzar
    assert espera == FuenteUSGS().intervalo_poll_s
    assert rec._salida.empty()


async def test_timeout_no_rompe(tmp_path):
    client = _FakeClient(exc=httpx.TimeoutException("timeout"))
    rec, estado = _reconciler(tmp_path, client)
    await rec.poll_once()  # no debe lanzar
    assert rec._salida.empty()
    assert estado.estado.cursor_usgs_ms is None


async def test_json_invalido_no_rompe(tmp_path):
    client = _FakeClient(_FakeResp(payload=None, json_error=True))
    rec, _ = _reconciler(tmp_path, client)
    await rec.poll_once()  # no debe lanzar
    assert rec._salida.empty()


# --- Bucle ---


class _SleepControlado:
    def __init__(self, romper_en):
        self.esperas: list[float] = []
        self._romper_en = romper_en

    async def __call__(self, segundos):
        self.esperas.append(segundos)
        if len(self.esperas) >= self._romper_en:
            raise asyncio.CancelledError


async def test_run_pollea_y_espera_intervalo(tmp_path):
    client = _FakeClient(_FakeResp(payload=_coleccion(_FEATURE)))
    sleep = _SleepControlado(romper_en=1)
    rec, _ = _reconciler(tmp_path, client, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await rec.run()

    assert sleep.esperas == [float(FuenteUSGS().intervalo_poll_s)]
    assert rec._salida.get_nowait().feature["id"] == "us6000t8sx"
