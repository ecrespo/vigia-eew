"""Agent configuration (RF-24, RF-12).

Loads and validates `config.toml` with pydantic v2. Read via `tomllib` (stdlib 3.11+).
Config path resolution (DATA-MODEL §3.3):
  1. Explicit path (CLI flag `--config`).
  2. `config.toml` in the user's config directory (`platformdirs`).
  3. Built-in defaults if no file exists (the agent still starts without prior config).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import BaseModel, Field

APP_NAME = "vigia-eew"
CONFIG_FILE_NAME = "config.toml"


class ReferencePoint(BaseModel):
    """Geographic reference point (RF-12). Default: Caracas."""

    name: str = "Caracas"
    lat: float = Field(default=10.4806, ge=-90, le=90)
    lon: float = Field(default=-66.9036, ge=-180, le=180)


class Filter(BaseModel):
    """Geographic and magnitude filter (RF-12)."""

    radius_km: float = Field(default=300.0, gt=0)
    min_magnitude: float = Field(default=2.5, ge=0)


class EMSCSource(BaseModel):
    """EMSC WebSocket parameters (RF-01, RF-02, RF-03)."""

    enabled: bool = True
    url: str = "wss://www.seismicportal.eu/standing_order/websocket"
    ping_interval_s: int = Field(default=15, gt=0)
    ping_timeout_s: int = Field(default=20, gt=0)
    backoff_max_s: int = Field(default=60, gt=0)


class USGSSource(BaseModel):
    """USGS FDSN backup parameters (RF-05, RF-06)."""

    enabled: bool = True
    url: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    poll_interval_s: int = Field(default=60, gt=0)
    timeout_s: int = Field(default=15, gt=0)


class Dedup(BaseModel):
    """Inter-source deduplication thresholds (RF-09)."""

    distance_km: float = Field(default=100.0, gt=0)
    window_s: int = Field(default=90, gt=0)
    magnitude_delta: float = Field(default=0.5, ge=0)


class Severity(BaseModel):
    """Severity thresholds by magnitude (RF-13).

    `info_max` must be less than `warning_max`.
    """

    info_max: float = 4.0
    warning_max: float = 5.5

    def model_post_init(self, __context: object) -> None:
        if self.info_max >= self.warning_max:
            raise ValueError("severity.info_max must be less than severity.warning_max")


class Notification(BaseModel):
    """Notification layer parameters (RF-15, RF-18, RNF-12)."""

    fullscreen: bool = False
    timezone: str = "America/Caracas"
    sound: bool = True
    tray_icon: bool = True
    language: str = "auto"
    """User-facing language (RF-35): "auto" (OS locale), "en", or "es"."""


class LoggingCfg(BaseModel):
    """Logging parameters (RF-25)."""

    level: str = "INFO"
    file: str = "vigia-eew.log"
    max_bytes: int = Field(default=1_048_576, gt=0)
    backups: int = Field(default=3, ge=0)


class Settings(BaseModel):
    """Full agent configuration (RF-24)."""

    reference: ReferencePoint = Field(default_factory=ReferencePoint)
    filter: Filter = Field(default_factory=Filter)
    sources_emsc: EMSCSource = Field(default_factory=EMSCSource)
    sources_usgs: USGSSource = Field(default_factory=USGSSource)
    dedup: Dedup = Field(default_factory=Dedup)
    severity: Severity = Field(default_factory=Severity)
    notification: Notification = Field(default_factory=Notification)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)


def default_config_path() -> Path:
    """Path to `config.toml` in the user's config directory (cross-platform)."""
    return Path(user_config_dir(APP_NAME)) / CONFIG_FILE_NAME


def _map_toml_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Translates TOML section names to `Settings` fields.

    In the TOML file the sources are nested as `[sources.emsc]` / `[sources.usgs]`,
    but in `Settings` they're called `sources_emsc` / `sources_usgs` to avoid an
    intermediate submodel. This function bridges that gap without losing validation.
    """
    result = dict(data)
    sources = result.pop("sources", None)
    if isinstance(sources, dict):
        if "emsc" in sources:
            result["sources_emsc"] = sources["emsc"]
        if "usgs" in sources:
            result["sources_usgs"] = sources["usgs"]
    return result


def _resolve_config_path(path: Path | str | None) -> Path | None:
    """Resolves the effective `config.toml` path, or `None` if there is no file (RF-24).

    Args:
        path: explicit path to a `config.toml`. If None, it's looked up in the
            user's config directory.

    Raises:
        FileNotFoundError: if an explicit `path` is given that doesn't exist.
    """
    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {path}")
        return path
    candidate = default_config_path()
    return candidate if candidate.exists() else None


def load_config(path: Path | str | None = None) -> Settings:
    """Loads and validates the configuration (RF-24).

    Args:
        path: explicit path to a `config.toml`. If None, it's looked up in the
            user's config directory; if that doesn't exist either, defaults are used.

    Returns:
        A validated `Settings` instance.

    Raises:
        FileNotFoundError: if an explicit `path` is given that doesn't exist.
        tomllib.TOMLDecodeError: if the file is not valid TOML.
        pydantic.ValidationError: if the values don't match the schema.
    """
    effective_path = _resolve_config_path(path)
    if effective_path is None:
        # No file: sensible defaults (Caracas). The agent starts anyway.
        return Settings()

    with open(effective_path, "rb") as fh:
        data = tomllib.load(fh)
    return Settings(**_map_toml_keys(data))


def has_manual_reference(path: Path | str | None = None) -> bool:
    """True if `[reference]` is explicitly defined in `config.toml` (RF-33).

    With no config file (neither explicit nor in the user directory), there is no
    manual reference: `Application` triggers automatic IP-based detection instead.
    """
    effective_path = _resolve_config_path(path)
    if effective_path is None:
        return False
    with open(effective_path, "rb") as fh:
        data = tomllib.load(fh)
    return "reference" in data
