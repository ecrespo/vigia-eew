"""When the shaking arrives, or when it did (T-177, REQ-ALE-011..013, ADR-039).

One velocity over the hypocentral distance, and nothing else: no travel-time
table and no dependency (decision D-9). The case that happens is the elapsed
one -- on three months of history no arrival beat its S wave -- so the sign of
the result matters as much as its size.
"""

from __future__ import annotations

import ast
import math
from datetime import UTC, datetime, timedelta

import pytest

from vigia_eew import shaking
from vigia_eew.models import SeismicEvent
from vigia_eew.shaking import S_WAVE_KM_S, estimate, unavailable_reason

_ORIGIN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _event(*, distance_km: float = 0.0, depth_km: float = 10.0, time_utc=_ORIGIN) -> SeismicEvent:
    return SeismicEvent(
        id="e1",
        source="EMSC",
        magnitude=5.5,
        mag_type="mw",
        lat=10.6,
        lon=-66.9,
        depth_km=depth_km,
        time_utc=time_utc,
        distance_km=distance_km,
        severity="warning",
    )


def test_the_s_wave_travels_at_three_and_a_half_kilometres_a_second() -> None:
    assert S_WAVE_KM_S == 3.5


def test_under_the_reference_point_the_depth_is_the_whole_distance() -> None:
    """CA-119.4: seventy kilometres down is about twenty seconds, not zero."""
    result = estimate(_event(distance_km=0.0, depth_km=70.0), _ORIGIN)

    assert result is not None
    assert result.travel_s == pytest.approx(20.0)
    assert result.remaining_s == pytest.approx(20.0)
    assert result.arrival == _ORIGIN + timedelta(seconds=20)


def test_the_distance_is_the_hypocentral_one() -> None:
    result = estimate(_event(distance_km=300.0, depth_km=400.0), _ORIGIN)

    assert result is not None
    assert result.hypocentral_km == pytest.approx(500.0)
    assert result.travel_s == pytest.approx(500.0 / 3.5)


def test_before_the_wave_arrives_the_time_is_ahead() -> None:
    result = estimate(_event(distance_km=350.0, depth_km=0.0), _ORIGIN + timedelta(seconds=40))

    assert result is not None
    assert result.remaining_s == pytest.approx(60.0)


def test_after_it_arrived_the_time_is_behind() -> None:
    """The case that happens: received twenty minutes after the wave."""
    received = _ORIGIN + timedelta(seconds=100, minutes=20)

    result = estimate(_event(distance_km=350.0, depth_km=0.0), received)

    assert result is not None
    assert result.remaining_s == pytest.approx(-20 * 60)


def test_the_arrival_does_not_depend_on_when_it_is_asked() -> None:
    event = _event(distance_km=350.0, depth_km=0.0)

    early, late = estimate(event, _ORIGIN), estimate(event, _ORIGIN + timedelta(hours=3))

    assert early is not None and late is not None
    assert early.arrival == late.arrival


def test_an_origin_time_ahead_of_the_clock_gives_no_estimate() -> None:
    """CA-119.7: an event from the future is a clock that is wrong somewhere."""
    event = _event(time_utc=_ORIGIN + timedelta(minutes=10))

    assert estimate(event, _ORIGIN) is None
    assert "ahead of the clock" in (unavailable_reason(event, _ORIGIN) or "")


def test_a_few_seconds_of_clock_skew_are_tolerated() -> None:
    event = _event(distance_km=350.0, depth_km=0.0, time_utc=_ORIGIN + timedelta(seconds=3))

    assert estimate(event, _ORIGIN) is not None
    assert unavailable_reason(event, _ORIGIN) is None


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_a_distance_that_is_not_a_number_gives_no_estimate(bad: float) -> None:
    event = _event().model_copy(update={"distance_km": bad})

    assert estimate(event, _ORIGIN) is None
    assert "finite" in (unavailable_reason(event, _ORIGIN) or "")


def test_a_depth_that_is_not_a_number_gives_no_estimate() -> None:
    event = _event().model_copy(update={"depth_km": math.nan})

    assert estimate(event, _ORIGIN) is None


def test_the_module_is_pure() -> None:
    with open(shaking.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert imported <= {"__future__", "math", "dataclasses", "datetime", "vigia_eew.models"}
