"""Normalizador de eventos (RF-07, RF-08, RF-13; mapeo en API-SPEC §3.1).

`Normalizer` traduce un `RawMessage` (crudo EMSC o USGS) al `SeismicEvent` común que
circula por el resto del pipeline. Resuelve las diferencias entre fuentes:

  - EMSC: `magtype` minúscula, tiempos en ISO-8601, id en `properties.unid`,
    coordenadas en `properties`.
  - USGS: `magType` camelCase, tiempos en epoch ms, id en el Feature,
    coordenadas en `geometry.coordinates` [lon, lat, depth].

Calcula los campos **derivados** (`distancia_km` por haversine, `severidad` por umbrales)
y exige que los tiempos queden tz-aware en UTC (lo garantiza `SeismicEvent`). Ante un
crudo inválido registra y devuelve `None` (descartar sin abortar, RNF-03).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from ..config import Referencia, Severidad
from ..geo import haversine_km
from ..ingest import RawMessage
from ..models import Accion, SeismicEvent, clasificar_severidad


class Normalizer:
    """Convierte `RawMessage` en `SeismicEvent`, resolviendo el mapeo por fuente."""

    def __init__(
        self,
        referencia: Referencia,
        severidad: Severidad,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._referencia = referencia
        self._severidad = severidad
        self._log = logger or logging.getLogger("vigia_eew.pipeline.normalize")

    def normalizar(self, msg: RawMessage) -> SeismicEvent | None:
        """Normaliza un crudo a `SeismicEvent`; devuelve None si es inválido."""
        try:
            if msg.fuente == "EMSC":
                campos = self._mapear_emsc(msg)
            elif msg.fuente == "USGS":
                campos = self._mapear_usgs(msg)
            else:
                self._log.warning("normalize_fuente_desconocida fuente=%s", msg.fuente)
                return None
            return self._construir(campos, msg.action)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            self._log.warning(
                "normalize_descartado fuente=%s tipo=%s detalle=%s",
                msg.fuente,
                type(exc).__name__,
                exc,
            )
            return None

    def _mapear_emsc(self, msg: RawMessage) -> dict[str, Any]:
        p = msg.feature["properties"]
        return {
            "id": str(p["unid"]),
            "fuente": "EMSC",
            "magnitud": float(p["mag"]),
            "mag_type": str(p["magtype"]),
            "lugar": p.get("flynn_region"),
            "region": p.get("flynn_region"),
            "lat": float(p["lat"]),
            "lon": float(p["lon"]),
            "profundidad_km": float(p["depth"]),
            "hora_utc": _parse_iso(p["time"]),
            "lastupdate_utc": _parse_iso_opcional(p.get("lastupdate")),
        }

    def _mapear_usgs(self, msg: RawMessage) -> dict[str, Any]:
        p = msg.feature["properties"]
        coords = msg.feature["geometry"]["coordinates"]
        return {
            "id": str(msg.feature["id"]),
            "fuente": "USGS",
            "magnitud": float(p["mag"]),
            "mag_type": str(p["magType"]),
            "lugar": p.get("place"),
            "region": None,  # USGS no expone región Flynn; derivarla queda fuera de v1.
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "profundidad_km": float(coords[2]),
            "hora_utc": _epoch_ms_a_utc(p["time"]),
            "lastupdate_utc": _epoch_ms_opcional(p.get("updated")),
        }

    def _construir(self, campos: dict[str, Any], accion: str) -> SeismicEvent:
        distancia = haversine_km(
            self._referencia.lat, self._referencia.lon, campos["lat"], campos["lon"]
        )
        severidad = clasificar_severidad(
            campos["magnitud"], self._severidad.info_max, self._severidad.atencion_max
        )
        accion_valida: Accion = "update" if accion == "update" else "create"
        return SeismicEvent(
            **campos,
            distancia_km=distancia,
            severidad=severidad,
            accion=accion_valida,
        )


def _parse_iso(valor: Any) -> datetime:
    """Parsea un tiempo ISO-8601 (EMSC) a datetime tz-aware en UTC."""
    if not isinstance(valor, str):
        raise ValueError(f"tiempo ISO no es texto: {valor!r}")
    texto = valor.strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    dt = datetime.fromisoformat(texto)  # 3.11+ acepta fracción de longitud variable
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_iso_opcional(valor: Any) -> datetime | None:
    return _parse_iso(valor) if valor is not None else None


def _epoch_ms_a_utc(valor: Any) -> datetime:
    """Convierte epoch en milisegundos (USGS) a datetime tz-aware en UTC."""
    if not isinstance(valor, int | float):
        raise ValueError(f"epoch ms no es numérico: {valor!r}")
    return datetime.fromtimestamp(valor / 1000, tz=UTC)


def _epoch_ms_opcional(valor: Any) -> datetime | None:
    return _epoch_ms_a_utc(valor) if valor is not None else None
