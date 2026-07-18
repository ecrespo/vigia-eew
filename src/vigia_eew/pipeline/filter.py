"""Geographic, magnitude, and freshness filter (RF-12, RF-37, RF-40).

`GeoFilter` decides whether an already-normalized `SeismicEvent` is relevant: within
the configured radius of the reference point and with sufficient magnitude. It is
applied before deduplication (TECHNICAL-DESIGN §2): it cheaply discards what is
irrelevant. Both limits are **inclusive** (an event exactly on the radius edge or at
the minimum magnitude passes).

Optionally (RF-37, opt-in via `[filter] country_filter`) it also drops events that
fall **positively inside another country** — offshore/ocean events (whose country is
unknown) are kept, so coastal earthquakes are never missed. The user's country and the
reverse-geocoding callable are injected so the filter stays testable without the real
boundary dataset, and so it's inert (backward compatible) when they aren't provided.

Also (RF-40, on by default via `[filter] today_only`) it drops events whose origin time
doesn't fall on the **current local calendar day** (per the configured timezone) — this
is what keeps the agent from alerting on stale REST backlog or a replayed old signature,
regardless of which of the 4 sources reports it (ADR-017). Like the country filter, it
is **fail-safe**: an invalid/unsupported timezone leaves it inert rather than risking a
silently dropped real alert. The clock is injected for deterministic tests.
"""

from __future__ import annotations

from collections.abc import Callable

from vigia_eew.config import Filter
from vigia_eew.models import SeismicEvent
from vigia_eew.timeutil import Clock, default_clock, local_date

_CountryOf = Callable[[float, float], str | None]


class GeoFilter:
    """Accepts or discards events by distance, magnitude, country, and freshness."""

    def __init__(
        self,
        cfg: Filter,
        *,
        user_country: str | None = None,
        country_of: _CountryOf | None = None,
        timezone: str = "UTC",
        now: Clock = default_clock,
    ) -> None:
        self._cfg = cfg
        self._user_country = user_country
        self._country_of = country_of
        self._timezone = timezone
        self._now = now

    def accepts(self, ev: SeismicEvent) -> bool:
        """True if the event passes the radius, magnitude, country, and freshness checks."""
        if ev.distance_km > self._cfg.radius_km or ev.magnitude < self._cfg.min_magnitude:
            return False
        if not self._passes_country(ev):
            return False
        return self._passes_freshness(ev)

    def _passes_country(self, ev: SeismicEvent) -> bool:
        """Reject only if the event is positively inside another country (RF-37)."""
        if (
            not self._cfg.country_filter
            or self._user_country is None
            or self._country_of is None
        ):
            return True
        event_country = self._country_of(ev.lat, ev.lon)
        return event_country is None or event_country == self._user_country

    def _passes_freshness(self, ev: SeismicEvent) -> bool:
        """Reject events that didn't originate on the current local day (RF-40).

        Fail-safe: an invalid/unsupported timezone leaves the check inert (never
        suppresses) rather than risking a silently dropped real alert.
        """
        if not self._cfg.today_only:
            return True
        today = local_date(self._now(), self._timezone)
        if today is None:
            return True
        event_day = local_date(ev.time_utc, self._timezone)
        return event_day == today
