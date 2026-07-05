"""Tests for the data models (RF-07, RF-13)."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest
from pydantic import ValidationError

from vigia_eew.models import (
    AlertedId,
    AppState,
    SeismicEvent,
    classify_severity,
)


def _event(**kw) -> SeismicEvent:
    base = dict(
        id="us6000t8sx",
        source="USGS",
        magnitude=4.3,
        mag_type="mb",
        place="19 km WSW of Morón, Venezuela",
        lat=10.4497,
        lon=-68.3766,
        depth_km=10.0,
        time_utc=datetime(2026, 6, 28, 13, 33, 58, tzinfo=UTC),
        distance_km=162.4,
        severity="warning",
    )
    base.update(kw)
    return SeismicEvent(**base)


def test_valid_event():
    ev = _event()
    assert ev.action == "create"
    assert ev.mag_type == "mb"


def test_magtype_is_normalized_to_lowercase():
    # USGS uses camelCase "magType" and EMSC "magtype"; the model unifies to lowercase.
    ev = _event(mag_type="Mw")
    assert ev.mag_type == "mw"


def test_naive_time_is_rejected():
    with pytest.raises(ValidationError):
        _event(time_utc=datetime(2026, 6, 28, 13, 33, 58))  # no tzinfo


def test_time_is_converted_to_utc():
    from datetime import timedelta

    tz = timezone(timedelta(hours=-4))  # America/Caracas
    ev = _event(time_utc=datetime(2026, 6, 28, 9, 33, 58, tzinfo=tz))
    assert ev.time_utc.utcoffset() == UTC.utcoffset(None)
    assert ev.time_utc.hour == 13  # 09:33 -04:00 == 13:33 UTC


def test_lat_lon_out_of_range():
    with pytest.raises(ValidationError):
        _event(lat=200.0)


def test_signature_matches_event():
    ev = _event()
    f = ev.signature()
    assert f.lat == ev.lat and f.magnitude == ev.magnitude


@pytest.mark.parametrize(
    "mag,expected",
    [(3.9, "info"), (4.0, "warning"), (5.4, "warning"), (5.5, "critical"), (6.1, "critical")],
)
def test_classify_severity(mag, expected):
    assert classify_severity(mag, info_max=4.0, warning_max=5.5) == expected


def test_appstate_defaults():
    s = AppState()
    assert s.version == 1
    assert s.cursor_usgs_ms is None
    assert s.alerted_ids == []


def test_alerted_id_accepts_acknowledged_none():
    a = AlertedId(id="x", source="EMSC", time_utc=datetime(2026, 6, 28, tzinfo=UTC))
    assert a.acknowledged_utc is None
