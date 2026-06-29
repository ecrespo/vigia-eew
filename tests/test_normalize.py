"""Pruebas del normalizador (RF-07, RF-08, RF-13; mapeo en API-SPEC §3.1)."""

from __future__ import annotations

from datetime import UTC

from vigia_eew.config import Referencia, Severidad
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.normalize import Normalizer

# --- Crudos de ejemplo (API-SPEC §1.3 y §2.4) ---

_EMSC_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "lastupdate": "2026-06-28T13:41:00.0Z",
    "unid": "20260628_0000123",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}
_EMSC = RawMessage(
    fuente="EMSC",
    action="create",
    feature={
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "20260628_0000123",
        "properties": dict(_EMSC_PROPS),
    },
)

_USGS = RawMessage(
    fuente="USGS",
    action="create",
    feature={
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
    },
)


def _normalizador():
    return Normalizer(Referencia(), Severidad())


def _emsc(**props):
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "x",
        "properties": {**_EMSC_PROPS, **props},
    }
    return RawMessage(fuente="EMSC", action="create", feature=feature)


# --- EMSC ---


def test_normaliza_emsc():
    ev = _normalizador().normalizar(_EMSC)
    assert isinstance(ev, SeismicEvent)
    assert ev.fuente == "EMSC"
    assert ev.id == "20260628_0000123"
    assert ev.magnitud == 6.1
    assert ev.mag_type == "mw"
    assert ev.region == "NEAR COAST OF VENEZUELA"
    assert ev.profundidad_km == 12.0
    assert ev.hora_utc.tzinfo is not None
    assert ev.hora_utc.astimezone(UTC).hour == 13
    assert ev.lastupdate_utc is not None


def test_emsc_magtype_se_normaliza_a_minuscula():
    ev = _normalizador().normalizar(_emsc(magtype="Mw"))
    assert ev is not None and ev.mag_type == "mw"


def test_emsc_preserva_accion_update():
    msg = RawMessage(fuente="EMSC", action="update", feature=_EMSC.feature)
    ev = _normalizador().normalizar(msg)
    assert ev is not None and ev.accion == "update"


# --- USGS ---


def test_normaliza_usgs():
    ev = _normalizador().normalizar(_USGS)
    assert isinstance(ev, SeismicEvent)
    assert ev.fuente == "USGS"
    assert ev.id == "us6000t8sx"
    assert ev.mag_type == "mb"
    assert ev.lugar == "19 km WSW of Morón, Venezuela"
    # Coordenadas desde geometry [lon, lat, depth].
    assert ev.lat == 10.4497
    assert ev.lon == -68.3766
    assert ev.profundidad_km == 10
    # Epoch ms -> UTC: 1782639238852 == 2026-06-28T13:33:58.852Z
    assert ev.hora_utc.astimezone(UTC).second == 58
    assert ev.lastupdate_utc is not None


# --- Derivados (RF-08, RF-13) ---


def test_distancia_calculada_haversine():
    ev = _normalizador().normalizar(_USGS)
    assert ev is not None
    # Caracas -> Morón ≈ 162 km (API-SPEC §3).
    assert 158 < ev.distancia_km < 166


def test_severidad_por_magnitud():
    assert _normalizador().normalizar(_EMSC).severidad == "critico"  # mag 6.1
    assert _normalizador().normalizar(_USGS).severidad == "atencion"  # mag 4.3


def test_severidad_respeta_umbrales_de_config():
    norm = Normalizer(Referencia(), Severidad(info_max=7.0, atencion_max=8.0))
    assert norm.normalizar(_EMSC).severidad == "info"  # 6.1 < 7.0 con umbrales altos


# --- Resiliencia (RNF-03) ---


def test_feature_sin_campos_devuelve_none():
    msg = RawMessage(fuente="EMSC", action="create", feature={"properties": {}})
    assert _normalizador().normalizar(msg) is None


def test_tiempo_invalido_devuelve_none():
    ev = _normalizador().normalizar(_emsc(time="no-es-fecha"))
    assert ev is None


def test_fuente_desconocida_devuelve_none():
    msg = RawMessage(fuente="SIMULADO", action="create", feature=_EMSC.feature)
    # El normalizador solo mapea EMSC/USGS; SIMULADO lo construye el CLI (Fase 5).
    assert _normalizador().normalizar(msg) is None
