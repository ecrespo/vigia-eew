"""Geographic and magnitude filter (RF-12, RF-37).

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
"""

from __future__ import annotations

from collections.abc import Callable

from vigia_eew.config import Filter
from vigia_eew.models import SeismicEvent

_CountryOf = Callable[[float, float], str | None]


class GeoFilter:
    """Accepts or discards events by distance, magnitude, and (optionally) country."""

    def __init__(
        self,
        cfg: Filter,
        *,
        user_country: str | None = None,
        country_of: _CountryOf | None = None,
    ) -> None:
        self._cfg = cfg
        self._user_country = user_country
        self._country_of = country_of

    def accepts(self, ev: SeismicEvent) -> bool:
        """True if the event passes the radius, magnitude, and country checks."""
        if ev.distance_km > self._cfg.radius_km or ev.magnitude < self._cfg.min_magnitude:
            return False
        return self._passes_country(ev)

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
