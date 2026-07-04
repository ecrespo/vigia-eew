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
