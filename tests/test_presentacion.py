"""Pruebas de la capa de presentación (RF-18, RF-13, RNF-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.presentacion import (
    color_severidad,
    formatear_evento,
    texto_toast,
)


def _ev(**kw) -> SeismicEvent:
    base = dict(
        id="20260628_0000123",
        fuente="EMSC",
        magnitud=6.1,
        mag_type="mw",
        lugar="NEAR COAST OF VENEZUELA",
        region="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        profundidad_km=12.0,
        # 13:39 UTC == 09:39 en America/Caracas (UTC-4).
        hora_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distancia_km=162.4,
        severidad="critico",
    )
    base.update(kw)
    return SeismicEvent(**base)


def test_formatea_magnitud():
    datos = formatear_evento(_ev(), nombre_referencia="Caracas")
    assert datos.magnitud == "M 6.1"


def test_distancia_redondeada_con_referencia():
    datos = formatear_evento(_ev(), nombre_referencia="Caracas")
    assert datos.distancia == "162 km de Caracas"


def test_profundidad():
    datos = formatear_evento(_ev(), nombre_referencia="Caracas")
    assert datos.profundidad == "12 km"


def test_hora_local_en_zona_venezuela():
    datos = formatear_evento(_ev(), nombre_referencia="Caracas")
    # RNF-12: conversión de UTC a hora de Venezuela en la presentación.
    assert "09:39:00" in datos.hora_local


def test_lugar_usa_region_si_no_hay_lugar():
    datos = formatear_evento(_ev(lugar=None), nombre_referencia="Caracas")
    assert datos.lugar == "NEAR COAST OF VENEZUELA"


def test_lugar_placeholder_si_no_hay_nada():
    datos = formatear_evento(_ev(lugar=None, region=None), nombre_referencia="Caracas")
    assert datos.lugar == "Ubicación desconocida"


def test_fuente_y_severidad_se_propagan():
    datos = formatear_evento(_ev(), nombre_referencia="Caracas")
    assert datos.fuente == "EMSC"
    assert datos.severidad == "critico"


def test_color_por_severidad():
    assert color_severidad("info") != color_severidad("critico")
    assert color_severidad("critico") == "#C62828"
    assert color_severidad("atencion") == "#F9A825"


def test_texto_toast_incluye_magnitud_y_lugar():
    titulo, mensaje = texto_toast(_ev(), nombre_referencia="Caracas")
    assert "6.1" in titulo
    assert "NEAR COAST OF VENEZUELA" in mensaje
    assert "162 km de Caracas" in mensaje
