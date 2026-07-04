"""Detección de ubicación por IP (RF-33) — mejor esfuerzo, sin bloquear el arranque.

Cuando el usuario no configura `[referencia]` en `config.toml`, `Aplicacion` recurre a
`detectar_ubicacion_ip()` para estimar el punto de referencia geográfico consultando un
servicio HTTPS público de geolocalización por IP (`ipapi.co`, sin API key). Cualquier
fallo (red, timeout, status inesperado, JSON inválido o campos faltantes) se traduce a
`None`: el llamador hace fallback al default (Caracas) sin impedir que el agente arranque,
mismo principio de aislamiento de fallos que `notify/toast.py`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Referencia

URL_GEOLOCALIZACION_IP = "https://ipapi.co/json/"
TIMEOUT_S = 5.0


def _parsear_respuesta(datos: dict[str, Any]) -> Referencia | None:
    """Traduce el JSON de `ipapi.co` a una `Referencia`. Pura, testeable con fixtures."""
    try:
        lat = float(datos["latitude"])
        lon = float(datos["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    nombre = datos.get("city") or datos.get("country_name") or "Ubicación detectada"
    try:
        return Referencia(nombre=str(nombre), lat=lat, lon=lon)
    except ValueError:
        # Incluye pydantic.ValidationError (subclase de ValueError): lat/lon fuera de rango.
        return None


def detectar_ubicacion_ip(
    *, client: httpx.Client | None = None, logger: logging.Logger | None = None
) -> Referencia | None:
    """Intenta detectar el punto de referencia por IP; `None` si falla (RF-33)."""
    log = logger or logging.getLogger("vigia_eew.geoloc")
    cliente = client or httpx.Client()
    try:
        try:
            resp = cliente.get(URL_GEOLOCALIZACION_IP, timeout=TIMEOUT_S)
        except httpx.HTTPError as exc:
            log.warning("geoloc_error_red tipo=%s detalle=%s", type(exc).__name__, exc)
            return None

        if resp.status_code != 200:
            log.warning("geoloc_status_inesperado status=%d", resp.status_code)
            return None

        try:
            datos = resp.json()
        except ValueError as exc:
            log.warning("geoloc_json_invalido detalle=%s", exc)
            return None

        referencia = _parsear_respuesta(datos)
        if referencia is None:
            log.warning("geoloc_respuesta_incompleta")
        return referencia
    finally:
        if client is None:
            cliente.close()
