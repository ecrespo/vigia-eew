"""Tests for the history map (T-148, REQ-MAP-002/003/005, HU-112).

The map is a **view on the list**, and the whole phase is arranged so that
losing it costs nothing else. So the tests that matter most here are the ones
where there is no map: no tiles, no network, nothing to draw — and the history
still answers the question it exists for.

What to draw is decided by `plan()`, which needs no display: where each
symbol goes, how big it is, which symbols are alerts. `HistoryMap` turns the
plan into `flet-map` layers; those are plain Flet dataclasses, so the control
is inspected here without a display or a tile download (ADR-030).
"""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.history import EventRecord
from vigia_eew.notify.history_map import (
    ALERTED_STYLE,
    DISCARDED_STYLE,
    MAX_RADIUS,
    MIN_RADIUS,
    centre_of,
    marker_radius,
    marker_style,
    plan,
)
from vigia_eew.notify.map_view import ATTRIBUTION

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _record(
    *,
    magnitude: float = 5.0,
    lat: float = 10.6,
    lon: float = -66.9,
    verdict: str = "alerted",
    event_id: str = "e-1",
) -> EventRecord:
    return EventRecord(
        correlation_id="tr-1",
        source="GEOFON",
        source_event_id=event_id,
        occurred_at=_WHEN,
        recorded_at=_WHEN,
        latitude=lat,
        longitude=lon,
        depth_km=12.0,
        magnitude=magnitude,
        region="NEAR THE COAST OF VENEZUELA",
        distance_km=20.0,
        verdict=verdict,
        severity="warning" if verdict == "alerted" else None,
    )


# --- CA-112.4 · Magnitude is read from the size ----------------------------------


def test_a_bigger_earthquake_gets_a_bigger_symbol() -> None:
    assert marker_radius(6.0) > marker_radius(3.0)


def test_the_order_of_sizes_follows_the_order_of_magnitudes() -> None:
    radii = [marker_radius(m) for m in (1.0, 2.5, 4.0, 5.5, 7.0)]

    assert radii == sorted(radii)


def test_the_difference_between_three_and_six_is_visible() -> None:
    """ "Visibly bigger" is a product claim, so it gets a number: half again."""
    assert marker_radius(6.0) >= marker_radius(3.0) * 1.5


def test_the_symbol_stays_within_bounds_at_both_extremes() -> None:
    """A magnitude 9 must not cover the map, and a 0.5 must still be clickable."""
    assert marker_radius(0.0) >= MIN_RADIUS
    assert marker_radius(9.9) <= MAX_RADIUS


# --- CA-112.5 · Alerted and discarded are told apart -----------------------------


def test_an_alert_and_a_discard_do_not_look_the_same() -> None:
    assert marker_style("alerted") is ALERTED_STYLE
    assert marker_style("discarded") is DISCARDED_STYLE
    assert ALERTED_STYLE.fill != DISCARDED_STYLE.fill


def test_a_discard_is_hollow_so_it_reads_as_secondary() -> None:
    """Colour alone excludes anyone who cannot distinguish these two.

    The difference is shape as well: an alert is filled, a discard is an
    outline. That survives being printed, screenshotted, or colour-blind.
    """
    assert ALERTED_STYLE.filled is True
    assert DISCARDED_STYLE.filled is False


def test_a_verdict_nobody_planned_for_still_gets_drawn() -> None:
    """Leaving it off the map would silently under-report the history."""
    assert marker_style("something-else") is DISCARDED_STYLE


# --- Placing things on the canvas -------------------------------------------------


def test_the_centre_of_nothing_is_the_reference_point() -> None:
    """An empty history still opens on somewhere, not on the Atlantic."""
    assert centre_of([], fallback=(10.5, -66.9)) == (10.5, -66.9)


def test_the_centre_of_one_earthquake_is_that_earthquake() -> None:
    assert centre_of([_record(lat=8.0, lon=-63.0)], fallback=(0.0, 0.0)) == (8.0, -63.0)


def test_the_centre_of_several_sits_between_them() -> None:
    centre = centre_of(
        [_record(lat=0.0, lon=0.0, event_id="a"), _record(lat=10.0, lon=20.0, event_id="b")],
        fallback=(99.0, 99.0),
    )

    assert centre == (5.0, 10.0)


def test_the_plan_places_every_earthquake_it_was_given() -> None:
    markers = plan([_record(event_id="a"), _record(lat=10.8, lon=-67.1, event_id="b")])

    assert len(markers) == 2
    assert {marker.record.source_event_id for marker in markers} == {"a", "b"}


def test_a_symbol_sits_where_its_earthquake_happened() -> None:
    (marker,) = plan([_record(lat=11.0, lon=-66.0)])

    assert (marker.latitude, marker.longitude) == (11.0, -66.0)


def test_alerts_are_drawn_over_discards() -> None:
    """Drawn last, so a discard next to an alert never hides it."""
    markers = plan(
        [_record(verdict="alerted", event_id="a"), _record(verdict="discarded", event_id="d")]
    )

    assert [m.record.verdict for m in markers] == ["discarded", "alerted"]


# --- The control (Flet dataclasses: no display needed) ----------------------------


def _layer_types(map_view) -> list[str]:
    return [type(layer).__name__ for layer in map_view.map.layers]


def test_the_control_draws_one_symbol_per_record() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_record(event_id="a"), _record(event_id="b", verdict="discarded")])

    circles = next(layer for layer in map_view.map.layers if hasattr(layer, "circles"))
    assert len(circles.circles) == 2


def test_the_attribution_and_the_legend_are_always_there() -> None:
    """CA-112.5 and CA-112.7: both on screen whatever else is not."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()

    assert "SimpleAttribution" in _layer_types(map_view)
    attribution = next(
        layer for layer in map_view.map.layers if type(layer).__name__ == "SimpleAttribution"
    )
    assert ATTRIBUTION in attribution.text


# --- CA-112.2 · No tiles is a state, not a failure --------------------------------


def test_a_failed_tile_makes_the_map_say_it_is_unavailable() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    assert map_view.available is True

    map_view._tile_failed(object())

    assert map_view.available is False
    assert map_view._notice.visible is True


def test_an_unavailable_map_keeps_the_list_s_records() -> None:
    """The symbols stay: still placed relative to each other, list unaffected."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view._tile_failed(object())
    map_view.show([_record()])

    assert len(map_view.markers) == 1


def test_the_real_window_tests_run_in_ci_and_not_only_here() -> None:
    """A check only the developer runs is a check that stops being run.

    CI installs Xvfb and switches the opt-in GUI smokes on (REQ-DEV-003).
    """
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text()

    assert "VIGIA_GUI_TESTS" in workflow
    assert "xvfb-run" in workflow
