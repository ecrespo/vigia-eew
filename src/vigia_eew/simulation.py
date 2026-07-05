"""Simulated event for `--simulate` (RF-21, DATA-MODEL §4).

Builds a `SeismicEvent` with `source="SIMULATED"` (M6.1 near La Guaira) to
validate the notification layer on every OS **without waiting for a real
earthquake** (CU-7). Distance and severity are derived the same way as for a
real event: distance to the configured reference point and severity from the
config thresholds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import ReferencePoint, Severity
from vigia_eew.geo import haversine_km
from vigia_eew.models import SeismicEvent, classify_severity

# Simulated epicenter: near La Guaira, Venezuela.
_SIM_LAT = 10.60
_SIM_LON = -66.93
_SIM_MAG = 6.1


def simulated_event(
    reference: ReferencePoint,
    severity: Severity,
    *,
    now: datetime | None = None,
) -> SeismicEvent:
    """Returns the simulated M6.1 La Guaira seismic event (RF-21)."""
    time_utc = now or datetime.now(UTC)
    distance_km = haversine_km(reference.lat, reference.lon, _SIM_LAT, _SIM_LON)
    level = classify_severity(_SIM_MAG, severity.info_max, severity.warning_max)
    return SeismicEvent(
        id="SIM-0001",
        source="SIMULATED",
        magnitude=_SIM_MAG,
        mag_type="mw",
        place="near La Guaira, Venezuela",
        region="NEAR COAST OF VENEZUELA",
        lat=_SIM_LAT,
        lon=_SIM_LON,
        depth_km=10.0,
        time_utc=time_utc,
        distance_km=distance_km,
        severity=level,
        action="create",
    )
