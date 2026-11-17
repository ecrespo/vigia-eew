"""When the shaking reaches the reference point -- or when it did (ADR-039).

The roadmap promised this since the first release: *how long until it
shakes here?* Everything it needs is already in the event.

**The estimate.** S-wave travel time = hypocentral distance / 3.5 km/s, where
the hypocentral distance is the epicentral one and the depth, squared and
summed. Without the depth an earthquake seventy kilometres under the
reference point would read as zero seconds; with it, about twenty.

**Its assumptions, declared.** One velocity for every depth and distance; a
straight path; a preliminary location. Beyond some 150 km the fastest S path
runs through the mantle and this model is a few seconds late -- which is why
whoever displays a remaining time rounds it **down**. No travel-time table
and no dependency (decision D-9).

**The case that happens is the elapsed one.** Measured on three months of
history, no arrival within 1 000 km was received before its S wave; alerts
came a median of 19.5 minutes after it. So the result is signed, and the
negative side is the one that will be read.

Pure: an event and an instant in, a value out. The clock is the caller's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from vigia_eew.models import SeismicEvent

#: Velocity of the S wave, in km/s (decision D-9).
S_WAVE_KM_S = 3.5

#: How far ahead of the clock an origin time may be and still be believed.
#: Two machines' clocks disagree by seconds; an event minutes in the future
#: is a clock that is wrong somewhere, and an estimate from it would be too.
ORIGIN_AHEAD_TOLERANCE_S = 30.0


@dataclass(frozen=True, slots=True)
class ShakingEstimate:
    """When the S wave of one event reaches the reference point."""

    hypocentral_km: float
    #: Seconds the S wave takes from the hypocentre to the reference point.
    travel_s: float
    #: The instant it arrives. Fixed for an event: it does not depend on when
    #: it is asked, which is what lets a display recount against its own clock.
    arrival: datetime
    #: Seconds from the instant asked about until the arrival: positive while
    #: the shaking is still to come, negative once it should have arrived.
    remaining_s: float


def unavailable_reason(event: SeismicEvent, now: datetime) -> str | None:
    """Why there is no estimate for that event at that instant, or None if there is.

    For the log: an alert shown without the line should say why somewhere
    (REQ-ALE-013).
    """
    if not (math.isfinite(event.distance_km) and math.isfinite(event.depth_km)):
        return "the distance or the depth is not a finite number"
    ahead = (event.time_utc - now).total_seconds()
    if ahead > ORIGIN_AHEAD_TOLERANCE_S:
        return f"the origin time is {ahead:.0f} s ahead of the clock"
    return None


def estimate(event: SeismicEvent, now: datetime) -> ShakingEstimate | None:
    """The S wave's arrival at the reference point, as seen at `now`; or None.

    None never costs an alert: the caller shows it whole, without this line.
    """
    if unavailable_reason(event, now) is not None:
        return None
    hypocentral_km = math.hypot(event.distance_km, event.depth_km)
    travel_s = hypocentral_km / S_WAVE_KM_S
    arrival = event.time_utc + timedelta(seconds=travel_s)
    return ShakingEstimate(
        hypocentral_km=hypocentral_km,
        travel_s=travel_s,
        arrival=arrival,
        remaining_s=(arrival - now).total_seconds(),
    )
