"""Event presentation for the alert (RF-18, RF-13, RNF-12).

**Pure** functions that transform a `SeismicEvent` (always in UTC) into readable
strings for the window and the toast, converting the time to the Venezuela
timezone (`America/Caracas`) only here (RNF-12). Also defines the color per
severity (RF-13). No GUI dependencies: this way presentation is tested without a
screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from vigia_eew import shaking
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
    #: Where the alert's map puts the epicentre, and the magnitude it sizes the
    #: symbol by. Kept numeric next to the strings above: the map needs to
    #: compute with them, the labels only to read them.
    latitude: float = 0.0
    longitude: float = 0.0
    magnitude_value: float = 0.0
    #: The same position, phrased for reading ("10.60° N, 66.93° W").
    coordinates: str = ""
    #: The user's reference point, drawn next to the epicentre so the distance
    #: line in the text has something to point at. None when it is unknown.
    reference: tuple[float, float] | None = None
    reference_name: str = ""
    #: The instant the shaking should reach the reference point, or None when
    #: it could not be estimated (ADR-039). An instant rather than a sentence:
    #: the alert stays on screen, and whatever shows it recounts against its
    #: own clock with `shaking_line`.
    shaking_arrival: datetime | None = None
    #: A simulated alert -- `--simulate` or the scheduled drill -- which every
    #: frontend labels as one (REQ-UX-008).
    drill: bool = False
    #: Which zone `local_time` is in: its abbreviation ("CEST", or the offset
    #: where the zone has none) and its IANA name. "Local" is only local to
    #: whoever configured it, so the alert says which.
    zone_abbreviation: str = ""
    zone_name: str = ""

    @property
    def local_time_zoned(self) -> str:
        """The time with its zone: `2026-06-28 15:39:00 CEST (Europe/Madrid)`."""
        parts = [self.local_time]
        if self.zone_abbreviation:
            parts.append(self.zone_abbreviation)
        # The name only when it adds something: "UTC (UTC)" does not.
        if self.zone_name and self.zone_name != self.zone_abbreviation:
            parts.append(f"({self.zone_name})")
        return " ".join(parts)


def format_coordinates(lat: float, lon: float) -> str:
    """Latitude and longitude with hemispheres, as a person reads them."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}° {ns}, {abs(lon):.2f}° {ew}"


def severity_color(severity: SeverityLevel) -> str:
    """Returns the hex color associated with a severity (RF-13)."""
    return _COLOR_BY_SEVERITY[severity]


def format_moment(moment: datetime, zone: str = VENEZUELA_ZONE) -> str:
    """Converts an instant to the given zone and formats it for reading (RNF-12).

    Fail-safe on the zone, like every other reader of a configured timezone in
    this codebase: an unusable one shows UTC rather than refusing to show the
    time at all. A history that will not render because of a typo in a config
    field is worse than one that renders in the wrong zone and says so.
    """
    try:
        local = moment.astimezone(ZoneInfo(zone))
    except (ZoneInfoNotFoundError, ValueError):
        local = moment.astimezone(UTC)
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _zone_of(zone: str) -> ZoneInfo | None:
    """The zone of that name, or None when nobody knows it."""
    try:
        return ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        return None


# @lat: [[notification#The alert says the time in the configured zone]]
def zone_abbreviation(moment: datetime, zone: str) -> str:
    """How that zone is abbreviated at that instant: `CEST`, `JST`, `UTC-04:00`.

    At an instant, because the letters change with daylight saving. Many
    zones have no letters at all -- the tz database gives Caracas "-04" -- and
    a bare "-04" after a time reads as a mistake, so those are said as an
    offset from UTC. A zone nobody knows is UTC, which is what
    `format_moment` shows for it.
    """
    tz = _zone_of(zone)
    if tz is None:
        return "UTC"
    local = moment.astimezone(tz)
    name = local.tzname() or ""
    if name and name[0] not in "+-" and not name[0].isdigit():
        return name
    offset = local.utcoffset()
    minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{rest:02d}"


def _local_time(ev: SeismicEvent, zone: str) -> str:
    """Converts `time_utc` to the given zone and formats it (RNF-12)."""
    return format_moment(ev.time_utc, zone)


def _place(ev: SeismicEvent, locale_code: str) -> str:
    return ev.place or ev.region or t("unknown_location", locale_code)


def format_event(
    ev: SeismicEvent,
    *,
    zone: str = VENEZUELA_ZONE,
    reference_name: str = "reference",
    locale_code: str = DEFAULT_LOCALE,
    reference: tuple[float, float] | None = None,
    now: datetime | None = None,
) -> AlertData:
    """Builds the readable alert fields from the event (RF-18, RF-35).

    `now` is the clock the shaking is estimated against. With no estimate the
    alert is whole and simply lacks that line (REQ-ALE-013).
    """
    estimate = shaking.estimate(ev, now or datetime.now(UTC))
    return AlertData(
        magnitude=f"M {ev.magnitude:.1f}",
        place=_place(ev, locale_code),
        distance=f"{ev.distance_km:.0f} km from {reference_name}",
        depth=f"{ev.depth_km:.0f} km",
        local_time=_local_time(ev, zone),
        source=ev.source,
        severity=ev.severity,
        latitude=ev.lat,
        longitude=ev.lon,
        magnitude_value=ev.magnitude,
        coordinates=format_coordinates(ev.lat, ev.lon),
        reference=reference,
        reference_name=reference_name,
        shaking_arrival=estimate.arrival if estimate is not None else None,
        drill=ev.is_drill,
        zone_abbreviation=zone_abbreviation(ev.time_utc, zone),
        # A name that did not resolve is not shown: the time is in UTC.
        zone_name=zone if _zone_of(zone) is not None else "UTC",
    )


# @lat: [[notification#The alert says when the shaking arrives, or when it did]]
def shaking_line(arrival: datetime | None, now: datetime, locale_code: str = DEFAULT_LOCALE) -> str:
    """The sentence about the shaking as read at `now`; empty with no estimate.

    A time still ahead is whole seconds rounded **down**: the model runs a
    few seconds late at a distance, and the safe error is to say less. Once
    less than a second is left it is the elapsed sentence, so the count never
    shows a zero that reads as "now" nor a negative figure. Elapsed is seconds
    under a minute, whole minutes under two hours, whole hours beyond -- no
    more precision than a preliminary location supports.
    """
    if arrival is None:
        return ""
    remaining = (arrival - now).total_seconds()
    if remaining >= 1:
        return t("shaking_remaining", locale_code, seconds=math.floor(remaining))
    elapsed = max(0, math.floor(-remaining))
    if elapsed < 60:
        return t("shaking_elapsed_seconds", locale_code, seconds=elapsed)
    if elapsed < 2 * 3600:
        return t("shaking_elapsed_minutes", locale_code, minutes=elapsed // 60)
    return t("shaking_elapsed_hours", locale_code, hours=elapsed // 3600)


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
    if data.drill:
        title = f"{t('drill_short', locale_code)} · {title}"
    # The abbreviation and not the name: a toast is one line.
    message = f"{data.place} · {data.distance} · {data.local_time} {data.zone_abbreviation}"
    return title, message
