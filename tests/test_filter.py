"""Tests for the geographic and magnitude filter (RF-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import Filter
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.filter import GeoFilter


def _event(distance_km: float, magnitude: float) -> SeismicEvent:
    return SeismicEvent(
        id="x",
        source="USGS",
        magnitude=magnitude,
        mag_type="mb",
        lat=10.0,
        lon=-66.0,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, tzinfo=UTC),
        distance_km=distance_km,
        severity="info",
    )


def _filter(**kw):
    return GeoFilter(Filter(**kw))


def test_accepts_within_radius_and_magnitude():
    assert _filter(radius_km=300, min_magnitude=2.5).accepts(_event(100.0, 4.0)) is True


def test_rejects_outside_radius():
    assert _filter(radius_km=300, min_magnitude=2.5).accepts(_event(400.0, 6.0)) is False


def test_rejects_low_magnitude():
    assert _filter(radius_km=300, min_magnitude=2.5).accepts(_event(50.0, 2.0)) is False


def test_radius_limit_is_inclusive():
    assert _filter(radius_km=300, min_magnitude=2.5).accepts(_event(300.0, 4.0)) is True


def test_magnitude_limit_is_inclusive():
    assert _filter(radius_km=300, min_magnitude=2.5).accepts(_event(50.0, 2.5)) is True
