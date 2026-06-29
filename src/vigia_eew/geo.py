"""Utilidades geográficas.

Cálculo de distancia entre dos puntos sobre la superficie terrestre mediante la
fórmula de Haversine. Es la base para `SeismicEvent.distancia_km` (RF-08) y para
la deduplicación inter-fuente (RF-09), que compara distancias entre epicentros.
"""

from __future__ import annotations

import math

# Radio medio de la Tierra en kilómetros (ver DATA-MODEL §5).
RADIO_TIERRA_KM: float = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Devuelve la distancia en kilómetros entre dos coordenadas (grados decimales).

    Usa la fórmula de Haversine, adecuada para distancias sobre una esfera. El error
    frente a un modelo elipsoidal es < 0.5 %, irrelevante para filtrado y dedup sísmicos.

    Args:
        lat1, lon1: latitud y longitud del primer punto, en grados.
        lat2, lon2: latitud y longitud del segundo punto, en grados.

    Returns:
        Distancia en kilómetros (>= 0).
    """
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    # asin(sqrt(a)) es numéricamente estable para distancias pequeñas.
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return RADIO_TIERRA_KM * c
