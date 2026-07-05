"""Event presentation for the alert (RF-18, RF-13, RNF-12).

**Pure** functions that transform a `SeismicEvent` (always in UTC) into readable
strings for the window and the toast, converting the time to the Venezuela
timezone (`America/Caracas`) only here (RNF-12). Also defines the color per
severity (RF-13). No GUI dependencies: this way presentation is tested without a
screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from vigia_eew.i18n import DEFAULT_LOCALE, t
from vigia_eew.models import SeismicEvent, SeverityLevel

VENEZUELA_ZONE = "America/Caracas"

# Color per severity (RF-13): blue (info), amber (warning), red (critical).
_COLOR_BY_SEVERITY: dict[SeverityLevel, str] = {
    "info": "#1565C0",
    "warning": "#F9A825",
    "critical": "#C62828",
}


@dataclass(frozen=True, slots=True)
class AlertData:
    """Fields already formatted for display in the alert window (RF-18)."""

    magnitude: str
    place: str
    distance: str
    depth: str
    local_time: str
    source: str
    severity: SeverityLevel


def severity_color(severity: SeverityLevel) -> str:
    """Returns the hex color associated with a severity (RF-13)."""
    return _COLOR_BY_SEVERITY[severity]


def _local_time(ev: SeismicEvent, zone: str) -> str:
    """Converts `time_utc` to the given zone and formats it (RNF-12)."""
    local = ev.time_utc.astimezone(ZoneInfo(zone))
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _place(ev: SeismicEvent, locale_code: str) -> str:
    return ev.place or ev.region or t("unknown_location", locale_code)


def format_event(
    ev: SeismicEvent,
    *,
    zone: str = VENEZUELA_ZONE,
    reference_name: str = "reference",
    locale_code: str = DEFAULT_LOCALE,
) -> AlertData:
    """Builds the readable alert fields from the event (RF-18, RF-35)."""
    return AlertData(
        magnitude=f"M {ev.magnitude:.1f}",
        place=_place(ev, locale_code),
        distance=f"{ev.distance_km:.0f} km from {reference_name}",
        depth=f"{ev.depth_km:.0f} km",
        local_time=_local_time(ev, zone),
        source=ev.source,
        severity=ev.severity,
    )


def toast_text(
    ev: SeismicEvent,
    *,
    zone: str = VENEZUELA_ZONE,
    reference_name: str = "reference",
    locale_code: str = DEFAULT_LOCALE,
) -> tuple[str, str]:
    """Returns (title, message) for the native toast (RF-14, RF-35)."""
    data = format_event(ev, zone=zone, reference_name=reference_name, locale_code=locale_code)
    title = t("toast_title", locale_code, magnitude=data.magnitude)
    message = f"{data.place} · {data.distance} · {data.local_time}"
    return title, message
