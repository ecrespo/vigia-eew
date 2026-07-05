"""Geographic and magnitude filter (RF-12).

`GeoFilter` decides whether an already-normalized `SeismicEvent` is relevant: within
the configured radius of the reference point and with sufficient magnitude. It is
applied before deduplication (TECHNICAL-DESIGN §2): it cheaply discards what is
irrelevant. Both limits are **inclusive** (an event exactly on the radius edge or at
the minimum magnitude passes).
"""

from __future__ import annotations

from vigia_eew.config import Filter
from vigia_eew.models import SeismicEvent


class GeoFilter:
    """Accepts or discards events by distance and magnitude (RF-12)."""

    def __init__(self, cfg: Filter) -> None:
        self._cfg = cfg

    def accepts(self, ev: SeismicEvent) -> bool:
        """True if the event is within the radius and meets the minimum magnitude."""
        return ev.distance_km <= self._cfg.radius_km and ev.magnitude >= self._cfg.min_magnitude
