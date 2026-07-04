"""Evento simulado para `--simulate` (RF-21, DATA-MODEL §4).

Construye un `SeismicEvent` con `fuente="SIMULADO"` (M6.1 cerca de La Guaira) para
validar la capa de notificación en cada SO **sin esperar un sismo real** (CU-7). La
distancia y la severidad se derivan igual que para un evento real: distancia al punto
de referencia configurado y severidad por los umbrales de config.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .config import Referencia, Severidad
from .geo import haversine_km
from .models import SeismicEvent, clasificar_severidad

# Epicentro simulado: cerca de La Guaira, Venezuela.
_SIM_LAT = 10.60
_SIM_LON = -66.93
_SIM_MAG = 6.1


def evento_simulado(
    referencia: Referencia,
    severidad: Severidad,
    *,
    ahora: datetime | None = None,
) -> SeismicEvent:
    """Devuelve el evento sísmico simulado M6.1 La Guaira (RF-21)."""
    hora = ahora or datetime.now(UTC)
    distancia = haversine_km(referencia.lat, referencia.lon, _SIM_LAT, _SIM_LON)
    nivel = clasificar_severidad(_SIM_MAG, severidad.info_max, severidad.atencion_max)
    return SeismicEvent(
        id="SIM-0001",
        fuente="SIMULADO",
        magnitud=_SIM_MAG,
        mag_type="mw",
        lugar="cerca de La Guaira, Venezuela",
        region="NEAR COAST OF VENEZUELA",
        lat=_SIM_LAT,
        lon=_SIM_LON,
        profundidad_km=10.0,
        hora_utc=hora,
        distancia_km=distancia,
        severidad=nivel,
        accion="create",
    )
