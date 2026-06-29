"""Pruebas de utilidades geográficas (RF-08)."""

from __future__ import annotations

from vigia_eew.geo import haversine_km


def test_distancia_cero():
    assert haversine_km(10.0, -66.0, 10.0, -66.0) == 0.0


def test_caracas_la_guaira_aprox():
    # Caracas (10.4806, -66.9036) a La Guaira (~10.60, -66.93): ~13-15 km.
    d = haversine_km(10.4806, -66.9036, 10.60, -66.93)
    assert 10 < d < 20


def test_simetria():
    a = haversine_km(10.0, -66.0, 12.0, -68.0)
    b = haversine_km(12.0, -68.0, 10.0, -66.0)
    assert abs(a - b) < 1e-9


def test_orden_de_magnitud_grados():
    # ~1 grado de latitud ≈ 111 km.
    d = haversine_km(0.0, 0.0, 1.0, 0.0)
    assert 110 < d < 112
