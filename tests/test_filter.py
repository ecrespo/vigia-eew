"""Tests for the geographic and magnitude filter (RF-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import Filter
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.filter import GeoFilter


def _event(
    distance_km: float, magnitude: float, *, lat: float = 10.0, lon: float = -66.0
) -> SeismicEvent:
    return SeismicEvent(
        id="x",
        source="USGS",
        magnitude=magnitude,
        mag_type="mb",
        lat=lat,
        lon=lon,
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


# --- Country filter (RF-37): drop only events positively inside ANOTHER country ---


def _country_filter(user_country, country_of, **kw):
    kw.setdefault("radius_km", 300)
    kw.setdefault("min_magnitude", 2.5)
    kw.setdefault("country_filter", True)
    return GeoFilter(Filter(**kw), user_country=user_country, country_of=country_of)


def test_country_filter_rejects_other_country():
    f = _country_filter("VE", lambda lat, lon: "CO")
    assert f.accepts(_event(50.0, 4.0)) is False


def test_country_filter_keeps_same_country():
    f = _country_filter("VE", lambda lat, lon: "VE")
    assert f.accepts(_event(50.0, 4.0)) is True


def test_country_filter_keeps_offshore_unknown():
    # Ocean / offshore -> country_of returns None -> kept (not positively another country).
    f = _country_filter("VE", lambda lat, lon: None)
    assert f.accepts(_event(50.0, 4.0)) is True


def test_country_filter_disabled_keeps_other_country():
    f = _country_filter("VE", lambda lat, lon: "CO", country_filter=False)
    assert f.accepts(_event(50.0, 4.0)) is True


def test_country_filter_without_user_country_is_inactive():
    # Country couldn't be determined -> fail-safe, do not suppress.
    f = _country_filter(None, lambda lat, lon: "CO")
    assert f.accepts(_event(50.0, 4.0)) is True


def test_country_filter_never_overrides_radius():
    f = _country_filter("VE", lambda lat, lon: "VE")
    assert f.accepts(_event(400.0, 6.0)) is False  # still rejected by radius
