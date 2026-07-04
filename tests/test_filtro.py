"""Pruebas del filtro geográfico y de magnitud (RF-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import Filtro
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.filtro import GeoFilter


def _evento(distancia_km: float, magnitud: float) -> SeismicEvent:
    return SeismicEvent(
        id="x",
        fuente="USGS",
        magnitud=magnitud,
        mag_type="mb",
        lat=10.0,
        lon=-66.0,
        profundidad_km=10.0,
        hora_utc=datetime(2026, 6, 28, tzinfo=UTC),
        distancia_km=distancia_km,
        severidad="info",
    )


def _filtro(**kw):
    return GeoFilter(Filtro(**kw))


def test_acepta_dentro_de_radio_y_magnitud():
    assert _filtro(radio_km=300, magnitud_minima=2.5).acepta(_evento(100.0, 4.0)) is True


def test_rechaza_fuera_de_radio():
    assert _filtro(radio_km=300, magnitud_minima=2.5).acepta(_evento(400.0, 6.0)) is False


def test_rechaza_magnitud_baja():
    assert _filtro(radio_km=300, magnitud_minima=2.5).acepta(_evento(50.0, 2.0)) is False


def test_limite_radio_es_inclusivo():
    assert _filtro(radio_km=300, magnitud_minima=2.5).acepta(_evento(300.0, 4.0)) is True


def test_limite_magnitud_es_inclusivo():
    assert _filtro(radio_km=300, magnitud_minima=2.5).acepta(_evento(50.0, 2.5)) is True
