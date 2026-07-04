"""Configuración del agente (RF-24, RF-12).

Carga y valida `config.toml` con pydantic v2. Lectura con `tomllib` (stdlib 3.11+).
Resolución de la ruta de config (DATA-MODEL §3.3):
  1. Ruta explícita (flag CLI `--config`).
  2. `config.toml` en el directorio de config del usuario (`platformdirs`).
  3. Defaults embebidos si no existe archivo (el agente arranca sin configuración previa).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import BaseModel, Field

APP_NAME = "vigia-eew"
NOMBRE_ARCHIVO_CONFIG = "config.toml"


class Referencia(BaseModel):
    """Punto de referencia geográfico (RF-12). Default: Caracas."""

    nombre: str = "Caracas"
    lat: float = Field(default=10.4806, ge=-90, le=90)
    lon: float = Field(default=-66.9036, ge=-180, le=180)


class Filtro(BaseModel):
    """Filtro geográfico y de magnitud (RF-12)."""

    radio_km: float = Field(default=300.0, gt=0)
    magnitud_minima: float = Field(default=2.5, ge=0)


class FuenteEMSC(BaseModel):
    """Parámetros del WebSocket EMSC (RF-01, RF-02, RF-03)."""

    habilitado: bool = True
    url: str = "wss://www.seismicportal.eu/standing_order/websocket"
    ping_interval_s: int = Field(default=15, gt=0)
    ping_timeout_s: int = Field(default=20, gt=0)
    backoff_max_s: int = Field(default=60, gt=0)


class FuenteUSGS(BaseModel):
    """Parámetros del respaldo USGS FDSN (RF-05, RF-06)."""

    habilitado: bool = True
    url: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    intervalo_poll_s: int = Field(default=60, gt=0)
    timeout_s: int = Field(default=15, gt=0)


class Dedup(BaseModel):
    """Umbrales de deduplicación inter-fuente (RF-09)."""

    distancia_km: float = Field(default=100.0, gt=0)
    ventana_s: int = Field(default=90, gt=0)
    delta_magnitud: float = Field(default=0.5, ge=0)


class Severidad(BaseModel):
    """Umbrales de severidad por magnitud (RF-13).

    `info_max` debe ser menor que `atencion_max`.
    """

    info_max: float = 4.0
    atencion_max: float = 5.5

    def model_post_init(self, __context: object) -> None:
        if self.info_max >= self.atencion_max:
            raise ValueError("severidad.info_max debe ser menor que severidad.atencion_max")


class Notificacion(BaseModel):
    """Parámetros de la capa de notificación (RF-15, RF-18, RNF-12)."""

    pantalla_completa: bool = False
    zona_horaria: str = "America/Caracas"
    sonido: bool = True


class LoggingCfg(BaseModel):
    """Parámetros de logging (RF-25)."""

    nivel: str = "INFO"
    archivo: str = "vigia-eew.log"
    max_bytes: int = Field(default=1_048_576, gt=0)
    backups: int = Field(default=3, ge=0)


class Settings(BaseModel):
    """Configuración completa del agente (RF-24)."""

    referencia: Referencia = Field(default_factory=Referencia)
    filtro: Filtro = Field(default_factory=Filtro)
    fuentes_emsc: FuenteEMSC = Field(default_factory=FuenteEMSC)
    fuentes_usgs: FuenteUSGS = Field(default_factory=FuenteUSGS)
    dedup: Dedup = Field(default_factory=Dedup)
    severidad: Severidad = Field(default_factory=Severidad)
    notificacion: Notificacion = Field(default_factory=Notificacion)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)


def ruta_config_predeterminada() -> Path:
    """Ruta de `config.toml` en el directorio de config del usuario (multiplataforma)."""
    return Path(user_config_dir(APP_NAME)) / NOMBRE_ARCHIVO_CONFIG


def _mapear_claves_toml(data: dict[str, Any]) -> dict[str, Any]:
    """Traduce nombres de sección del TOML a los campos de `Settings`.

    En el TOML las fuentes se anidan como `[fuentes.emsc]` / `[fuentes.usgs]`,
    pero en `Settings` se llaman `fuentes_emsc` / `fuentes_usgs` para evitar un
    submodelo intermedio. Esta función hace ese puente sin perder validación.
    """
    resultado = dict(data)
    fuentes = resultado.pop("fuentes", None)
    if isinstance(fuentes, dict):
        if "emsc" in fuentes:
            resultado["fuentes_emsc"] = fuentes["emsc"]
        if "usgs" in fuentes:
            resultado["fuentes_usgs"] = fuentes["usgs"]
    return resultado


def _resolver_ruta_config(ruta: Path | str | None) -> Path | None:
    """Resuelve la ruta efectiva de `config.toml`, o `None` si no hay archivo (RF-24).

    Args:
        ruta: ruta explícita a un `config.toml`. Si es None, se busca en el
            directorio de config del usuario.

    Raises:
        FileNotFoundError: si se pasa una `ruta` explícita que no existe.
    """
    if ruta is not None:
        ruta = Path(ruta)
        if not ruta.exists():
            raise FileNotFoundError(f"No existe el archivo de configuración: {ruta}")
        return ruta
    candidata = ruta_config_predeterminada()
    return candidata if candidata.exists() else None


def cargar_config(ruta: Path | str | None = None) -> Settings:
    """Carga y valida la configuración (RF-24).

    Args:
        ruta: ruta explícita a un `config.toml`. Si es None, se busca en el
            directorio de config del usuario; si tampoco existe, se usan defaults.

    Returns:
        Una instancia validada de `Settings`.

    Raises:
        FileNotFoundError: si se pasa una `ruta` explícita que no existe.
        tomllib.TOMLDecodeError: si el archivo no es TOML válido.
        pydantic.ValidationError: si los valores no cumplen el esquema.
    """
    ruta_efectiva = _resolver_ruta_config(ruta)
    if ruta_efectiva is None:
        # Sin archivo: defaults sensatos (Caracas). El agente arranca igual.
        return Settings()

    with open(ruta_efectiva, "rb") as fh:
        data = tomllib.load(fh)
    return Settings(**_mapear_claves_toml(data))


def tiene_referencia_manual(ruta: Path | str | None = None) -> bool:
    """True si `[referencia]` está definida explícitamente en el `config.toml` (RF-33).

    Sin archivo de configuración (ni explícito ni en el directorio de usuario), no hay
    referencia manual: `Aplicacion` dispara la detección automática por IP en su lugar.
    """
    ruta_efectiva = _resolver_ruta_config(ruta)
    if ruta_efectiva is None:
        return False
    with open(ruta_efectiva, "rb") as fh:
        data = tomllib.load(fh)
    return "referencia" in data
