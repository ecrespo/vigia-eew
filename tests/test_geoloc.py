"""Pruebas de detección de ubicación por IP (RF-33)."""

from __future__ import annotations

import httpx

from vigia_eew.geoloc import detectar_ubicacion_ip


class _RespuestaFalsa:
    def __init__(self, status_code=200, payload=None, *, json_invalido=False):
        self.status_code = status_code
        self._payload = payload or {}
        self._json_invalido = json_invalido

    def json(self):
        if self._json_invalido:
            raise ValueError("no es json")
        return self._payload


class _ClienteFalso:
    def __init__(self, respuesta=None, *, excepcion=None):
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.cerrado = False

    def get(self, url, *, timeout=None):
        if self._excepcion is not None:
            raise self._excepcion
        return self._respuesta

    def close(self):
        self.cerrado = True


def test_deteccion_exitosa():
    cliente = _ClienteFalso(
        _RespuestaFalsa(200, {"city": "Caracas", "latitude": 10.5, "longitude": -66.9})
    )
    ref = detectar_ubicacion_ip(client=cliente)
    assert ref is not None
    assert ref.nombre == "Caracas"
    assert ref.lat == 10.5
    assert ref.lon == -66.9


def test_error_de_red_devuelve_none():
    cliente = _ClienteFalso(excepcion=httpx.ConnectError("sin red"))
    assert detectar_ubicacion_ip(client=cliente) is None


def test_status_no_200_devuelve_none():
    cliente = _ClienteFalso(_RespuestaFalsa(503))
    assert detectar_ubicacion_ip(client=cliente) is None


def test_json_invalido_devuelve_none():
    cliente = _ClienteFalso(_RespuestaFalsa(200, json_invalido=True))
    assert detectar_ubicacion_ip(client=cliente) is None


def test_campos_faltantes_devuelve_none():
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"city": "Caracas"}))  # sin lat/lon
    assert detectar_ubicacion_ip(client=cliente) is None


def test_lat_lon_fuera_de_rango_devuelve_none():
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"latitude": 999.0, "longitude": -66.9}))
    assert detectar_ubicacion_ip(client=cliente) is None


def test_sin_ciudad_usa_nombre_generico():
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"latitude": 1.0, "longitude": 2.0}))
    ref = detectar_ubicacion_ip(client=cliente)
    assert ref is not None
    assert ref.nombre


def test_cliente_inyectado_no_se_cierra():
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"latitude": 1.0, "longitude": 2.0}))
    detectar_ubicacion_ip(client=cliente)
    assert cliente.cerrado is False
