"""Pruebas del evento simulado (RF-21, DATA-MODEL §4)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import Referencia, Severidad
from vigia_eew.simulacion import evento_simulado


def test_evento_simulado_la_guaira():
    ev = evento_simulado(Referencia(), Severidad())
    assert ev.fuente == "SIMULADO"
    assert ev.magnitud == 6.1
    assert ev.lat == 10.60
    assert ev.lon == -66.93
    assert ev.accion == "create"


def test_severidad_critica_por_magnitud():
    ev = evento_simulado(Referencia(), Severidad())
    assert ev.severidad == "critico"  # 6.1 >= atencion_max (5.5)


def test_distancia_calculada_desde_referencia():
    # Caracas (default) está a ~15 km de La Guaira.
    ev = evento_simulado(Referencia(), Severidad())
    assert 5 < ev.distancia_km < 40


def test_distancia_crece_con_referencia_lejana():
    lejana = Referencia(nombre="Maracaibo", lat=10.65, lon=-71.65)
    ev = evento_simulado(lejana, Severidad())
    assert ev.distancia_km > 400


def test_hora_utc_tz_aware():
    fijo = datetime(2026, 6, 28, 17, 39, tzinfo=UTC)
    ev = evento_simulado(Referencia(), Severidad(), ahora=fijo)
    assert ev.hora_utc == fijo
    assert ev.hora_utc.tzinfo is not None
