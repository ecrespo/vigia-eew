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
    # today_only defaults off here: these radius/magnitude/country tests use a fixed
    # 2026-06-28 event date unrelated to freshness, which has its own tests below.
    kw.setdefault("today_only", False)
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
    kw.setdefault("today_only", False)
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


# --- Freshness filter (RF-40): only alert on the current local calendar day ---


def _fresh_event(time_utc, *, distance_km=50.0, magnitude=4.0):
    return SeismicEvent(
        id="x",
        source="USGS",
        magnitude=magnitude,
        mag_type="mb",
        lat=10.0,
        lon=-66.0,
        depth_km=10.0,
        time_utc=time_utc,
        distance_km=distance_km,
        severity="info",
    )


def _freshness_filter(*, now, timezone="UTC", today_only=True):
    return GeoFilter(Filter(today_only=today_only), timezone=timezone, now=now)


def test_freshness_accepts_event_from_today():
    now = lambda: datetime(2026, 7, 17, 15, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now)
    event = _fresh_event(datetime(2026, 7, 17, 9, 0, tzinfo=UTC))
    assert f.accepts(event) is True


def test_freshness_rejects_event_from_yesterday():
    now = lambda: datetime(2026, 7, 17, 1, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now)
    event = _fresh_event(datetime(2026, 7, 16, 23, 0, tzinfo=UTC))
    assert f.accepts(event) is False


def test_freshness_rejects_event_from_tomorrow():
    # A clock-skew/edge case, not expected in practice, but the rule is symmetric:
    # only "today" passes, not "today or later".
    now = lambda: datetime(2026, 7, 17, 23, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now)
    event = _fresh_event(datetime(2026, 7, 18, 1, 0, tzinfo=UTC))
    assert f.accepts(event) is False


def test_freshness_uses_local_day_not_utc_day():
    # 21:00 local (America/Caracas, UTC-4) on the 17th is 01:00 UTC on the 18th.
    # Using the local day (not UTC) must still treat this as "today" if `now` is the
    # same local evening.
    now = lambda: datetime(2026, 7, 18, 0, 30, tzinfo=UTC)  # 2026-07-17 20:30 VET  # noqa: E731
    f = _freshness_filter(now=now, timezone="America/Caracas")
    event = _fresh_event(datetime(2026, 7, 18, 1, 0, tzinfo=UTC))  # 2026-07-17 21:00 VET
    assert f.accepts(event) is True


def test_freshness_disabled_keeps_old_event():
    now = lambda: datetime(2026, 7, 17, 15, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now, today_only=False)
    event = _fresh_event(datetime(2020, 1, 1, tzinfo=UTC))
    assert f.accepts(event) is True


def test_freshness_invalid_timezone_is_inert_failsafe():
    now = lambda: datetime(2026, 7, 17, 15, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now, timezone="Not/AZone")
    event = _fresh_event(datetime(2020, 1, 1, tzinfo=UTC))  # would otherwise be rejected
    assert f.accepts(event) is True  # inert: never silently suppresses


def test_freshness_never_overrides_radius_or_magnitude():
    now = lambda: datetime(2026, 7, 17, 15, 0, tzinfo=UTC)  # noqa: E731
    f = _freshness_filter(now=now)
    today = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
    assert f.accepts(_fresh_event(today, distance_km=400.0)) is False  # still rejected
    assert f.accepts(_fresh_event(today, magnitude=1.0)) is False  # still rejected
