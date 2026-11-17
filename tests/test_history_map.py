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

    assert len(_symbols(map_view)) == 2


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


# --- T-159 · a symbol can be pointed at (REQ-MAP-006, ADR-033) --------------------
#
# P-1, checked on the real client: a `CircleMarker` has no tooltip and no
# events; a `Marker` holding a control has both. So the symbols are markers.


def _symbols(map_view) -> list:
    layer = next(layer for layer in map_view.map.layers if type(layer).__name__ == "MarkerLayer")
    return layer.markers


def test_the_symbols_are_markers_not_painted_circles() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_record(event_id="a")])

    assert "MarkerLayer" in _layer_types(map_view)
    assert "CircleLayer" not in _layer_types(map_view)


def test_a_symbol_says_what_it_is_told_to_say() -> None:
    """CA-114.7: the map does not word an earthquake itself; it is handed the words."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show(
        [_record(event_id="a", magnitude=5.5)],
        describe=lambda record: f"about {record.source_event_id}",
    )

    assert [symbol.content.tooltip for symbol in _symbols(map_view)] == ["about a"]


def test_a_symbol_with_nothing_to_say_has_no_tooltip() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_record(event_id="a")])

    assert _symbols(map_view)[0].content.tooltip is None


def test_a_marker_is_as_big_as_its_magnitude_says() -> None:
    """The size the plan worked out is the size drawn: diameter = twice the radius."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show(
        [_record(event_id="small", magnitude=3.0), _record(event_id="big", magnitude=6.5)]
    )

    by_id = {planned.record.source_event_id: planned for planned in map_view.markers}
    for symbol, planned in zip(_symbols(map_view), map_view.markers, strict=True):
        assert symbol.width == symbol.height == 2 * planned.radius
        assert symbol.content.border_radius == planned.radius
    assert by_id["big"].radius > by_id["small"].radius


def test_an_alert_is_filled_and_a_discard_is_hollow_on_the_marker_too() -> None:
    """CA-112.5 survives the change of control: the difference is not only a colour."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_record(event_id="a"), _record(event_id="d", verdict="discarded")])

    by_verdict = {
        planned.record.verdict: symbol.content
        for symbol, planned in zip(_symbols(map_view), map_view.markers, strict=True)
    }
    assert by_verdict["alerted"].bgcolor is not None
    assert by_verdict["discarded"].bgcolor is None
    assert by_verdict["alerted"].border is not None and by_verdict["discarded"].border is not None


def test_a_marker_sits_where_its_earthquake_happened() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_record(event_id="a")])

    symbol, planned = _symbols(map_view)[0], map_view.markers[0]
    assert (symbol.coordinates.latitude, symbol.coordinates.longitude) == (
        planned.latitude,
        planned.longitude,
    )


# --- T-160 · the selected symbol (REQ-MAP-007, ADR-033) ---------------------------


def _stored(event_id: str, row_id: int, **overrides) -> EventRecord:
    from dataclasses import replace

    return replace(_record(event_id=event_id, **overrides), id=row_id)


def test_exactly_one_symbol_is_selected_and_it_is_the_row_s() -> None:
    """CA-114.8: keyed by the row a symbol stands for, not by where it is."""
    records = [_stored("a", 1), _stored("b", 2), _stored("c", 3)]

    markers = plan(records, selected=2)

    assert [marker.record.id for marker in markers if marker.selected] == [2]


def test_nothing_is_selected_when_the_row_is_not_on_the_map() -> None:
    markers = plan([_stored("a", 1)], selected=99)

    assert not any(marker.selected for marker in markers)


def test_the_selected_symbol_differs_in_size_and_ring_not_only_in_colour() -> None:
    """Two earthquakes of one magnitude and one verdict: only the selection differs."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_stored("a", 1), _stored("b", 2)])
    map_view.select(2)

    drawn = {
        planned.record.id: symbol
        for symbol, planned in zip(_symbols(map_view), map_view.markers, strict=True)
    }
    assert drawn[2].width > drawn[1].width
    assert drawn[2].content.border.top.width > drawn[1].content.border.top.width


def test_the_selected_symbol_is_drawn_over_the_others() -> None:
    markers = plan([_stored("a", 1), _stored("b", 2), _stored("c", 3)], selected=1)

    assert markers[-1].record.id == 1


def test_selecting_does_not_change_which_earthquakes_are_drawn() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_stored("a", 1), _stored("b", 2)])
    before = {marker.record.id for marker in map_view.markers}

    map_view.select(1)
    map_view.select(None)

    assert {marker.record.id for marker in map_view.markers} == before
    assert not any(marker.selected for marker in map_view.markers)


def test_pressing_a_symbol_reports_its_row() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    pressed: list[int] = []
    map_view = HistoryMap(on_select=pressed.append)
    map_view.show([_stored("a", 1), _stored("b", 2)])
    target = next(
        symbol
        for symbol, planned in zip(_symbols(map_view), map_view.markers, strict=True)
        if planned.record.id == 2
    )

    target.content.on_click(None)

    assert pressed == [2]


def test_a_selection_survives_a_redraw_of_the_same_set() -> None:
    """The filters redraw the map; the earthquake the user chose is still chosen."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    records = [_stored("a", 1), _stored("b", 2)]
    map_view.show(records)
    map_view.select(2)

    map_view.show(records)

    assert [marker.record.id for marker in map_view.markers if marker.selected] == [2]


# --- Nothing above the map may take the pointer from it ---------------------------
#
# Found on the real client, not here: the "map unavailable" notice sat in a
# container that filled the whole stack, above the map. With painted circles
# nobody noticed; with markers, no symbol could be pointed at or pressed.


def _is_positioned(control) -> bool:
    return any(getattr(control, side, None) is not None for side in ("left", "top", "right"))


def test_nothing_that_covers_the_map_takes_the_pointer_from_it() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    stack = map_view.view.content
    above = stack.controls[stack.controls.index(map_view.map) + 1 :]

    assert above, "the legend and the notice are drawn over the map"
    for layer in above:
        assert _is_positioned(layer) or type(layer).__name__ == "TransparentPointer", (
            f"{type(layer).__name__} fills the stack above the map and swallows the pointer"
        )


def test_the_notice_is_still_shown_over_the_map_when_a_tile_fails() -> None:
    """The fix must not cost CA-112.2: the notice is still there, and still centred."""
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view._tile_failed(object())
    stack = map_view.view.content
    holder = next(c for c in stack.controls if type(c).__name__ == "TransparentPointer")

    assert holder.content.content is map_view._notice
    assert map_view._notice.visible is True


# --- T-166 · a symbol can be drawn weaker (REQ-TLP-005) -----------------------------


def _numbered(row_id: int, *, magnitude: float) -> EventRecord:
    """A record as the store returns it: with the id of its row."""
    from dataclasses import replace

    return replace(_record(magnitude=magnitude, event_id=f"e-{row_id}"), id=row_id)


def test_a_symbol_is_drawn_at_full_strength_unless_told_otherwise() -> None:
    (marker,) = plan([_numbered(7, magnitude=4.0)])

    assert marker.strength == 1.0


def test_the_plan_carries_the_strength_each_earthquake_was_given() -> None:
    records = [_numbered(7, magnitude=4.0), _numbered(8, magnitude=5.0)]

    markers = plan(records, strengths={7: 0.45})

    assert {marker.record.id: marker.strength for marker in markers} == {7: 0.45, 8: 1.0}


def test_a_weaker_symbol_is_a_more_transparent_control() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    records = [_numbered(7, magnitude=4.0), _numbered(8, magnitude=5.0)]

    map_view.show(records, strengths={7: 0.45})

    opacity = {
        marker.record.id: symbol.content.opacity
        for marker, symbol in zip(map_view.markers, _symbols(map_view), strict=True)
    }
    assert opacity == {7: 0.45, 8: 1.0}


def test_showing_without_strengths_forgets_the_ones_of_a_frame() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    records = [_numbered(7, magnitude=4.0)]
    map_view.show(records, strengths={7: 0.45})

    map_view.show(records)

    assert [marker.strength for marker in map_view.markers] == [1.0]


def test_selecting_keeps_the_strengths_of_the_frame_on_screen() -> None:
    from vigia_eew.notify.history_map import HistoryMap

    map_view = HistoryMap()
    map_view.show([_numbered(7, magnitude=4.0)], strengths={7: 0.45})

    map_view.select(7)

    (marker,) = map_view.markers
    assert (marker.selected, marker.strength) == (True, 0.45)
