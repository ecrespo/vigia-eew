"""Pruebas de los modelos de datos (RF-07, RF-13)."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest
from pydantic import ValidationError

from vigia_eew.models import (
    AlertedId,
    AppState,
    SeismicEvent,
    clasificar_severidad,
)


def _evento(**kw) -> SeismicEvent:
    base = dict(
        id="us6000t8sx",
        fuente="USGS",
        magnitud=4.3,
        mag_type="mb",
        lugar="19 km WSW of Morón, Venezuela",
        lat=10.4497,
        lon=-68.3766,
        profundidad_km=10.0,
        hora_utc=datetime(2026, 6, 28, 13, 33, 58, tzinfo=UTC),
        distancia_km=162.4,
        severidad="atencion",
    )
    base.update(kw)
    return SeismicEvent(**base)


def test_evento_valido():
    ev = _evento()
    assert ev.accion == "create"
    assert ev.mag_type == "mb"


def test_magtype_se_normaliza_a_minuscula():
    # USGS usa "magType" camelCase y EMSC "magtype"; el modelo unifica a minúscula.
    ev = _evento(mag_type="Mw")
    assert ev.mag_type == "mw"


def test_hora_naive_es_rechazada():
    with pytest.raises(ValidationError):
        _evento(hora_utc=datetime(2026, 6, 28, 13, 33, 58))  # sin tzinfo


def test_hora_se_convierte_a_utc():
    from datetime import timedelta

    tz = timezone(timedelta(hours=-4))  # America/Caracas
    ev = _evento(hora_utc=datetime(2026, 6, 28, 9, 33, 58, tzinfo=tz))
    assert ev.hora_utc.utcoffset() == UTC.utcoffset(None)
    assert ev.hora_utc.hour == 13  # 09:33 -04:00 == 13:33 UTC


def test_lat_lon_fuera_de_rango():
    with pytest.raises(ValidationError):
        _evento(lat=200.0)


def test_firma_coincide_con_evento():
    ev = _evento()
    f = ev.firma()
    assert f.lat == ev.lat and f.magnitud == ev.magnitud


@pytest.mark.parametrize(
    "mag,esperado",
    [(3.9, "info"), (4.0, "atencion"), (5.4, "atencion"), (5.5, "critico"), (6.1, "critico")],
)
def test_clasificar_severidad(mag, esperado):
    assert clasificar_severidad(mag, info_max=4.0, atencion_max=5.5) == esperado


def test_appstate_por_defecto():
    s = AppState()
    assert s.version == 1
    assert s.cursor_usgs_ms is None
    assert s.ids_alertados == []


def test_alerted_id_acepta_reconocido_none():
    a = AlertedId(id="x", fuente="EMSC", hora_utc=datetime(2026, 6, 28, tzinfo=UTC))
    assert a.reconocido_utc is None
