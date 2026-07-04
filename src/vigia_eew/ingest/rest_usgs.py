"""Reconciliador REST USGS FDSN — respaldo de baja frecuencia (RF-05, RF-06, ADR-002).

`RESTReconciler` consulta el servicio FDSN de USGS cada `intervalo_poll_s` para
recuperar eventos que el WebSocket EMSC pudo perder y cubrir pequeños sismos locales.
No compite con el push: baja frecuencia, bajo peso (TECHNICAL-DESIGN §4).

  - **Cursor persistido** (RF-06): consulta con `starttime` = último `time` procesado;
    tras procesar, avanza el cursor al máximo visto y lo guarda (sobrevive reinicios).
  - **Resiliencia** (RNF-03, API-SPEC §2.5): 429 honra `Retry-After`; 5xx/timeout/JSON
    inválido se registran y se reintenta en el siguiente ciclo, sin abortar ni perder cursor.

El cliente HTTP (`httpx`) y el `sleep` se inyectan para probar sin red.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from ..config import Filtro, FuenteUSGS, Referencia
from ..state import StateStore
from . import RawMessage

_SleepFn = Callable[[float], Any]


class RESTReconciler:
    """Polling FDSN de USGS con cursor persistido; publica `RawMessage` en `salida`."""

    def __init__(
        self,
        cfg: FuenteUSGS,
        referencia: Referencia,
        filtro: Filtro,
        estado: StateStore,
        salida: asyncio.Queue[RawMessage],
        *,
        client: httpx.AsyncClient | None = None,
        sleep: _SleepFn = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self._cfg = cfg
        self._referencia = referencia
        self._filtro = filtro
        self._estado = estado
        self._salida = salida
        self._client = client
        self._sleep = sleep
        self._log = logger or logging.getLogger("vigia_eew.ingest.rest")

    def _construir_params(self, cursor_ms: int | None) -> dict[str, Any]:
        """Arma los parámetros de la consulta FDSN (API-SPEC §2.2)."""
        params: dict[str, Any] = {
            "format": "geojson",
            "latitude": self._referencia.lat,
            "longitude": self._referencia.lon,
            "maxradiuskm": self._filtro.radio_km,
            "minmagnitude": self._filtro.magnitud_minima,
            "orderby": "time",
            "eventtype": "earthquake",
        }
        if cursor_ms is not None:
            momento = datetime.fromtimestamp(cursor_ms / 1000, tz=UTC)
            params["starttime"] = momento.strftime("%Y-%m-%dT%H:%M:%S")
        return params

    async def poll_once(self) -> float:
        """Ejecuta una consulta y procesa la respuesta.

        Returns:
            Segundos a esperar antes del siguiente poll (normalmente `intervalo_poll_s`;
            mayor si un 429 indica `Retry-After`).
        """
        intervalo = float(self._cfg.intervalo_poll_s)
        cursor = self._estado.estado.cursor_usgs_ms
        params = self._construir_params(cursor)

        if self._client is None:
            raise RuntimeError("RESTReconciler requiere un cliente httpx (inyectado o creado).")

        try:
            resp = await self._client.get(
                self._cfg.url, params=params, timeout=self._cfg.timeout_s
            )
        except httpx.HTTPError as exc:
            self._log.warning("usgs_error_red tipo=%s detalle=%s", type(exc).__name__, exc)
            return intervalo

        if resp.status_code == 429:
            retry = _retry_after_segundos(resp.headers, defecto=intervalo)
            self._log.warning("usgs_429 retry_after_s=%.1f", retry)
            return retry
        if resp.status_code >= 500:
            self._log.warning("usgs_5xx status=%d", resp.status_code)
            return intervalo
        if resp.status_code != 200:
            self._log.warning("usgs_status_inesperado status=%d", resp.status_code)
            return intervalo

        try:
            datos = resp.json()
            features = datos["features"]
        except (ValueError, KeyError, TypeError) as exc:
            self._log.warning("usgs_json_invalido detalle=%s", exc)
            return intervalo

        max_time = await self._procesar_features(features)
        if max_time is not None:
            self._estado.actualizar_cursor_usgs(max_time)
            self._estado.guardar()
        return intervalo

    async def _procesar_features(self, features: Any) -> int | None:
        """Encola cada Feature como `RawMessage`; devuelve el `time` máximo visto."""
        if not isinstance(features, list):
            self._log.warning("usgs_features_no_es_lista")
            return None
        max_time: int | None = None
        for feature in features:
            if not isinstance(feature, dict):
                continue
            await self._salida.put(RawMessage(fuente="USGS", action="create", feature=feature))
            tiempo = _time_ms(feature)
            if tiempo is not None and (max_time is None or tiempo > max_time):
                max_time = tiempo
        return max_time

    async def run(self) -> None:
        """Bucle de polling perpetuo. Termina solo al ser cancelado."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        while True:
            espera = await self.poll_once()
            await self._sleep(espera)


def _retry_after_segundos(headers: Any, *, defecto: float) -> float:
    """Lee `Retry-After` (segundos) de las cabeceras; usa `defecto` si falta o es inválido."""
    bruto = headers.get("Retry-After")
    if bruto is None:
        return defecto
    try:
        return max(defecto, float(bruto))
    except (TypeError, ValueError):
        return defecto


def _time_ms(feature: dict[str, Any]) -> int | None:
    """Extrae `properties.time` (epoch ms) de un Feature, o None si no es entero."""
    propiedades = feature.get("properties")
    if not isinstance(propiedades, dict):
        return None
    tiempo = propiedades.get("time")
    return tiempo if isinstance(tiempo, int) else None
