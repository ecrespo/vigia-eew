"""Geographic utilities.

Computes the distance between two points on the Earth's surface using the
Haversine formula. It underlies `SeismicEvent.distance_km` (RF-08) and
inter-source deduplication (RF-09), which compares distances between epicenters.
"""

from __future__ import annotations

import math

# Mean Earth radius in kilometers (see DATA-MODEL §5).
EARTH_RADIUS_KM: float = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns the distance in kilometers between two coordinates (decimal degrees).

    Uses the Haversine formula, suitable for distances on a sphere. The error
    versus an ellipsoidal model is < 0.5%, irrelevant for seismic filtering and dedup.

    Args:
        lat1, lon1: latitude and longitude of the first point, in degrees.
        lat2, lon2: latitude and longitude of the second point, in degrees.

    Returns:
        Distance in kilometers (>= 0).
    """
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    # asin(sqrt(a)) is numerically stable for small distances.
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_KM * c
