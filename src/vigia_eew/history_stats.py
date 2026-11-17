"""The figures of a period: what the history adds up to (REQ-EST-001..003, ADR-038).

The history answers *"why was I not warned about that earthquake?"* one row at
a time. This answers the questions a row cannot: how many there were, of what
size, what became of them -- and the one only this product can answer, how long
each network takes to deliver an earthquake after it happens.

**Two bases, and each figure names its own (X-8).** What is said about
earthquakes -- per day, by magnitude, by verdict and reason -- counts
earthquakes. What is said about networks -- the split by network, the latency
-- counts arrivals, because a network is measured by what it delivered. So
`summarise` takes both readings of one filter, and every figure carries the
number of entries it was computed over and the period they span as fields of
the result (REQ-EST-003), not as text a view may or may not add.

Pure: two sequences in, one value out. No toolkit, no database, no network --
the caller reads the store, and a test on this module's imports keeps it so.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median

from vigia_eew.history import EventRecord, received_live
from vigia_eew.timeutil import local_date

#: The first and the last instant of what a figure was computed over.
Period = tuple[datetime, datetime]

#: Lower edges of the magnitude bands, one unit each. Below the first is one
#: band and from the last on is another: under M2 almost nothing is catalogued,
#: and above M7 there are too few to split.
MAGNITUDE_EDGES = (2, 3, 4, 5, 6, 7)

#: The key of a discard nobody gave a reason for. It is counted like any other:
#: leaving it out would make the reasons add up to less than the discarded.
NO_REASON = ""


@dataclass(frozen=True, slots=True)
class Bar:
    """One category of a split, and how many entries fell in it."""

    key: str
    count: int


@dataclass(frozen=True, slots=True)
class Split:
    """A set divided into categories that add up to it (CA-118.1)."""

    bars: tuple[Bar, ...]
    #: How many entries were divided: what the bars add up to.
    sample: int
    #: What an entry is here: `"earthquake"` or `"arrival"` (X-8).
    base: str
    period: Period | None


@dataclass(frozen=True, slots=True)
class Latency:
    """How long one network takes to deliver an earthquake after it happens.

    The **median** of `recorded_at - occurred_at`, in seconds, over the
    arrivals the agent received live. A median because one arrival in ten can
    come days late, and a mean would report those days as the typical delay.
    `None` when the network has no live arrival: that is "no figure", which is
    not zero (CA-118.4).
    """

    source: str
    median_s: float | None
    #: The live arrivals it was computed over.
    sample: int
    period: Period | None


@dataclass(frozen=True, slots=True)
class Summary:
    """Every figure of one filtered set."""

    earthquakes: int
    arrivals: int
    period: Period | None
    per_day: Split
    by_magnitude: Split
    by_verdict: Split
    #: Among the discarded earthquakes only; it adds up to them.
    by_reason: Split
    by_source: Split
    #: One per network present, in name order.
    latency: tuple[Latency, ...]

    @property
    def empty(self) -> bool:
        """Nothing matched: there is no figure to show, which is not a zero (CA-118.7)."""
        return self.earthquakes == 0 and self.arrivals == 0


def band_of(magnitude: float) -> str:
    """The magnitude band an earthquake falls in: `M<2`, `M2` .. `M6`, `M7+`."""
    first, last = MAGNITUDE_EDGES[0], MAGNITUDE_EDGES[-1]
    if magnitude < first:
        return f"M<{first}"
    if magnitude >= last:
        return f"M{last}+"
    return f"M{int(magnitude)}"


_BAND_ORDER = (
    f"M<{MAGNITUDE_EDGES[0]}",
    *(f"M{edge}" for edge in MAGNITUDE_EDGES[:-1]),
    f"M{MAGNITUDE_EDGES[-1]}+",
)


def summarise(
    earthquakes: Sequence[EventRecord],
    arrivals: Sequence[EventRecord],
    *,
    zone: str,
) -> Summary:
    """The figures of one filter, from its two readings.

    `earthquakes` is the per-earthquake reading -- one arrival standing for
    each -- and `arrivals` the per-arrival one. `zone` is the user's: a day is
    a local calendar day, falling back to UTC when the zone is not known.
    """
    discarded = [record for record in earthquakes if record.verdict == "discarded"]
    return Summary(
        earthquakes=len(earthquakes),
        arrivals=len(arrivals),
        period=_period(earthquakes) or _period(arrivals),
        per_day=_split(earthquakes, lambda r: _day(r.occurred_at, zone), "earthquake", sorted),
        by_magnitude=_split(
            earthquakes, lambda r: band_of(r.magnitude), "earthquake", _in_band_order
        ),
        by_verdict=_split(earthquakes, lambda r: r.verdict, "earthquake"),
        by_reason=_split(discarded, lambda r: r.reason or NO_REASON, "earthquake"),
        by_source=_split(arrivals, lambda r: r.source, "arrival"),
        latency=tuple(
            _latency(source, [record for record in arrivals if record.source == source])
            for source in sorted({record.source for record in arrivals})
        ),
    )


def _split(
    records: Sequence[EventRecord],
    key: Callable[[EventRecord], str],
    base: str,
    order: Callable[[Iterable[str]], Iterable[str]] | None = None,
) -> Split:
    """Divides those records by `key`. Largest first unless an order is given."""
    counts = Counter(key(record) for record in records)
    keys = order(counts) if order else sorted(counts, key=lambda k: (-counts[k], k))
    return Split(
        bars=tuple(Bar(k, counts[k]) for k in keys),
        sample=len(records),
        base=base,
        period=_period(records),
    )


def _in_band_order(bands: Iterable[str]) -> list[str]:
    present = set(bands)
    return [band for band in _BAND_ORDER if band in present]


def _day(moment: datetime, zone: str) -> str:
    """The local calendar day of an instant, as `YYYY-MM-DD`."""
    day = local_date(moment, zone) or moment.astimezone(UTC).date()
    return day.isoformat()


def _period(records: Sequence[EventRecord]) -> Period | None:
    """From the first of those to happen to the last, or None when there are none."""
    if not records:
        return None
    moments = [record.occurred_at for record in records]
    return (min(moments), max(moments))


def _latency(source: str, arrivals: Sequence[EventRecord]) -> Latency:
    """That network's delay, over what the agent received from it while running.

    A recovered entry is left out: its "reception" is the moment somebody
    pressed a button, which says nothing about the network (X-2).
    """
    live = [record for record in arrivals if received_live(record)]
    if not live:
        return Latency(source, None, 0, None)
    delays = [(record.recorded_at - record.occurred_at).total_seconds() for record in live]
    return Latency(source, float(median(delays)), len(live), _period(live))
