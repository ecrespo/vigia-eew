"""Pruebas de configuración (RF-24, RF-12)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vigia_eew.config import Settings, cargar_config

CONFIG_EJEMPLO = """
[referencia]
nombre = "Valencia"
lat = 10.1620
lon = -68.0077

[filtro]
radio_km = 150.0
magnitud_minima = 3.0

[fuentes.emsc]
ping_interval_s = 10

[fuentes.usgs]
intervalo_poll_s = 30

[severidad]
info_max = 3.5
atencion_max = 5.0
"""


def test_defaults_sin_archivo(tmp_path):
    # Ruta None y sin archivo de usuario -> defaults (Caracas).
    cfg = Settings()
    assert cfg.referencia.nombre == "Caracas"
    assert cfg.filtro.radio_km == 300.0
    assert cfg.fuentes_emsc.ping_interval_s == 15


def test_cargar_desde_toml(tmp_path):
    ruta = tmp_path / "config.toml"
    ruta.write_text(CONFIG_EJEMPLO, encoding="utf-8")
    cfg = cargar_config(ruta)
    assert cfg.referencia.nombre == "Valencia"
    assert cfg.filtro.radio_km == 150.0
    # Mapeo de secciones anidadas [fuentes.emsc] / [fuentes.usgs].
    assert cfg.fuentes_emsc.ping_interval_s == 10
    assert cfg.fuentes_usgs.intervalo_poll_s == 30
    assert cfg.severidad.info_max == 3.5


def test_ruta_inexistente_explicita_falla(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_config(tmp_path / "no_existe.toml")


def test_severidad_invalida():
    with pytest.raises(ValidationError):
        Settings(severidad={"info_max": 6.0, "atencion_max": 5.0})


def test_archivo_ejemplo_es_valido():
    # El config.toml.example del repo debe cargar sin errores.
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    ejemplo = raiz / "config.toml.example"
    cfg = cargar_config(ejemplo)
    assert cfg.referencia.nombre == "Caracas"
    assert cfg.notificacion.zona_horaria == "America/Caracas"
