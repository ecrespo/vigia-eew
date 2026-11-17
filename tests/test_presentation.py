"""Tests for the presentation layer (RF-18, RF-13, RNF-12)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.presentation import (
    format_event,
    severity_color,
    toast_text,
)


def _ev(**kw) -> SeismicEvent:
    base = dict(
        id="20260628_0000123",
        source="EMSC",
        magnitude=6.1,
        mag_type="mw",
        place="NEAR COAST OF VENEZUELA",
        region="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        depth_km=12.0,
        # 13:39 UTC == 09:39 in America/Caracas (UTC-4).
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=162.4,
        severity="critical",
    )
    base.update(kw)
    return SeismicEvent(**base)


def test_formats_magnitude():
    data = format_event(_ev(), reference_name="Caracas")
    assert data.magnitude == "M 6.1"


def test_distance_rounded_with_reference():
    data = format_event(_ev(), reference_name="Caracas")
    assert data.distance == "162 km from Caracas"


def test_depth():
    data = format_event(_ev(), reference_name="Caracas")
    assert data.depth == "12 km"


def test_local_time_in_venezuela_zone():
    data = format_event(_ev(), reference_name="Caracas")
    # RNF-12: UTC to Venezuela local time conversion in the presentation layer.
    assert "09:39:00" in data.local_time


def test_place_uses_region_if_no_place():
    data = format_event(_ev(place=None), reference_name="Caracas")
    assert data.place == "NEAR COAST OF VENEZUELA"


def test_place_placeholder_if_nothing_available():
    data = format_event(_ev(place=None, region=None), reference_name="Caracas")
    assert data.place == "Unknown location"


def test_source_and_severity_propagate():
    data = format_event(_ev(), reference_name="Caracas")
    assert data.source == "EMSC"
    assert data.severity == "critical"


def test_color_by_severity():
    assert severity_color("info") != severity_color("critical")
    assert severity_color("critical") == "#C62828"
    assert severity_color("warning") == "#F9A825"


def test_toast_text_includes_magnitude_and_place():
    title, message = toast_text(_ev(), reference_name="Caracas")
    assert "6.1" in title
    assert "NEAR COAST OF VENEZUELA" in message
    assert "162 km from Caracas" in message


# --- T-178 · the line about the shaking (REQ-ALE-011..013, ADR-039) ----------------

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402

from vigia_eew.notify.presentation import shaking_line  # noqa: E402

_ARRIVAL = datetime(2026, 6, 28, 13, 40, tzinfo=UTC)


def _line(seconds_from_arrival: float, locale_code: str = "en") -> str:
    """The line as read that many seconds after (or, negative, before) the arrival."""
    return shaking_line(_ARRIVAL, _ARRIVAL + timedelta(seconds=seconds_from_arrival), locale_code)


def test_the_event_carries_the_instant_the_shaking_arrives():
    # 350 km at the surface: one hundred seconds after the origin.
    data = format_event(_ev(distance_km=350.0, depth_km=0.0), now=datetime.now(UTC))

    assert data.shaking_arrival == datetime(2026, 6, 28, 13, 40, 40, tzinfo=UTC)


def test_with_time_ahead_the_line_counts_the_seconds_remaining():
    assert _line(-42) == "Shaking expected in ≈ 42 s"


def test_a_remaining_time_is_rounded_down():
    """CA-119.5: 18.9 s displays 18. The model runs late; this errs the safe way."""
    assert _line(-18.9) == "Shaking expected in ≈ 18 s"


def test_the_count_decreases_as_the_clock_advances():
    """CA-119.1."""
    shown = [_line(-seconds) for seconds in (3, 2, 1)]

    assert shown == [
        "Shaking expected in ≈ 3 s",
        "Shaking expected in ≈ 2 s",
        "Shaking expected in ≈ 1 s",
    ]


@pytest.mark.parametrize("seconds", [-0.9, -0.1, 0.0, 0.4])
def test_a_count_that_reaches_zero_becomes_the_elapsed_sentence(seconds):
    """CA-119.3: never a zero that reads as "now", never a negative figure."""
    line = _line(seconds)

    assert line == "The shaking should already have arrived ≈ 0 s ago"
    assert "-" not in line


def test_under_a_minute_ago_is_said_in_seconds():
    assert _line(47.8) == "The shaking should already have arrived ≈ 47 s ago"


def test_minutes_ago_is_said_in_whole_minutes():
    """CA-119.2: the case that happens."""
    assert _line(20 * 60 + 31) == "The shaking should already have arrived ≈ 20 min ago"


def test_the_elapsed_figure_grows_as_the_clock_advances():
    assert [_line(60 * minutes) for minutes in (1, 2, 3)] == [
        f"The shaking should already have arrived ≈ {minutes} min ago" for minutes in (1, 2, 3)
    ]


def test_hours_ago_is_said_in_hours():
    assert _line(4.8 * 3600) == "The shaking should already have arrived ≈ 4 h ago"


@pytest.mark.parametrize("locale_code", ["en", "es"])
@pytest.mark.parametrize("seconds", [-30, 30, 1800, 4 * 3600])
def test_it_reads_as_an_estimate_in_every_language(locale_code, seconds):
    """CA-119.6: the approximation mark, in every branch and both languages."""
    assert "≈" in _line(seconds, locale_code)


def test_the_line_in_spanish():
    assert _line(-42, "es") == "Sacudida estimada en ≈ 42 s"
    assert _line(1260, "es") == "La sacudida ya debió llegar hace ≈ 21 min"


def test_without_an_estimate_there_is_no_line_and_the_rest_is_whole():
    """CA-119.7: an origin time ahead of the clock."""
    ev = _ev()
    data = format_event(ev, reference_name="Caracas", now=ev.time_utc - timedelta(minutes=10))

    assert data.shaking_arrival is None
    assert shaking_line(data.shaking_arrival, datetime.now(UTC), "en") == ""
    assert (data.magnitude, data.place, data.depth) == ("M 6.1", "NEAR COAST OF VENEZUELA", "12 km")
    assert data.distance == "162 km from Caracas"


# --- T-179 · a drill says it is a drill (REQ-UX-008, ADR-040) ----------------------


def test_a_simulated_event_is_presented_as_a_drill():
    assert format_event(_ev(source="SIMULATED")).drill is True


def test_an_event_from_a_network_is_not_a_drill():
    for source in ("EMSC", "USGS", "FUNVISIS", "GEOFON"):
        assert format_event(_ev(source=source)).drill is False


def test_the_toast_of_a_drill_says_so_in_its_title():
    title, _message = toast_text(_ev(source="SIMULATED"), locale_code="en")
    real, _ = toast_text(_ev(), locale_code="en")

    assert title.startswith("DRILL")
    assert "DRILL" not in real


def test_the_drill_label_exists_in_both_languages():
    from vigia_eew.i18n import t

    assert t("drill_label", "en") == "DRILL — this is not a real earthquake"
    assert t("drill_label", "es") == "SIMULACRO — no es un sismo real"
