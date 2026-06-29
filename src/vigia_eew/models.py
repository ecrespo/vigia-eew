"""Modelos de datos (pydantic v2).

Implementa el contrato interno definido en `docs/DATA-MODEL.md`:
  - `SeismicEvent`: evento sísmico normalizado (RF-07).
  - `AlertedId`, `EventSignature`, `AppState`: estado persistido (RF-06, RF-10).
  - `clasificar_severidad`: derivación de severidad por magnitud (RF-13).

Invariante clave: todos los `datetime` son *tz-aware* en UTC. La conversión a hora
local (America/Caracas) ocurre solo en la capa de presentación (RF-18, RNF-12).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Alias de tipos del dominio ---
Fuente = Literal["EMSC", "USGS", "SIMULADO"]
Severidad = Literal["info", "atencion", "critico"]
Accion = Literal["create", "update"]


def _exigir_utc(valor: datetime | None) -> datetime | None:
    """Valida que un datetime sea tz-aware y lo normaliza a UTC.

    Se rechaza un datetime *naive* (sin zona) para evitar ambigüedades de tiempo,
    que en una alerta sísmica serían peligrosas.
    """
    if valor is None:
        return None
    if valor.tzinfo is None:
        raise ValueError("El datetime debe ser tz-aware (incluir zona horaria).")
    return valor.astimezone(UTC)


def clasificar_severidad(magnitud: float, info_max: float, atencion_max: float) -> Severidad:
    """Clasifica la severidad de un sismo según su magnitud (RF-13).

    Por defecto (config): `< info_max` -> info, `< atencion_max` -> atencion,
    en otro caso -> critico. Los umbrales son configurables (ver `Settings`).
    """
    if magnitud < info_max:
        return "info"
    if magnitud < atencion_max:
        return "atencion"
    return "critico"


class SeismicEvent(BaseModel):
    """Evento sísmico normalizado que circula entre las capas del agente (RF-07)."""

    id: str
    fuente: Fuente
    magnitud: float
    mag_type: str
    lugar: str | None = None
    region: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    profundidad_km: float = Field(ge=0)
    hora_utc: datetime
    lastupdate_utc: datetime | None = None
    distancia_km: float = Field(ge=0)
    severidad: Severidad
    accion: Accion = "create"

    @field_validator("hora_utc", "lastupdate_utc")
    @classmethod
    def _validar_utc(cls, v: datetime | None) -> datetime | None:
        return _exigir_utc(v)

    @field_validator("mag_type")
    @classmethod
    def _normalizar_magtype(cls, v: str) -> str:
        # EMSC usa `magtype` (minúscula) y USGS `magType` (camelCase); unificamos.
        return v.strip().lower()

    def firma(self) -> EventSignature:
        """Produce la firma usada en la deduplicación inter-fuente (RF-09)."""
        return EventSignature(
            lat=self.lat, lon=self.lon, hora_utc=self.hora_utc, magnitud=self.magnitud
        )


class EventSignature(BaseModel):
    """Huella mínima de un evento para detectar duplicados entre fuentes (RF-09)."""

    lat: float
    lon: float
    hora_utc: datetime
    magnitud: float

    @field_validator("hora_utc")
    @classmethod
    def _validar_utc(cls, v: datetime) -> datetime:
        validado = _exigir_utc(v)
        assert validado is not None  # hora_utc es obligatorio aquí
        return validado


class AlertedId(BaseModel):
    """Registro de un evento ya alertado, para no repetir tras reinicios (RF-10)."""

    id: str
    fuente: str
    hora_utc: datetime
    reconocido_utc: datetime | None = None  # auditoría del acknowledge (OBJ-1)

    @field_validator("hora_utc", "reconocido_utc")
    @classmethod
    def _validar_utc(cls, v: datetime | None) -> datetime | None:
        return _exigir_utc(v)


class AppState(BaseModel):
    """Estado persistido del agente (RF-06, RF-10). Ver `state.py`."""

    version: int = 1
    cursor_usgs_ms: int | None = None
    ids_alertados: list[AlertedId] = Field(default_factory=list)
    firmas_recientes: list[EventSignature] = Field(default_factory=list)
