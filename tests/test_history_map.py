"""Tests for the history map (T-148, REQ-MAP-002/003/005, HU-112).

The map is a **view on the list**, and the whole phase is arranged so that
losing it costs nothing else. So the tests that matter most here are the ones
where there is no map: no tiles, no network, nothing to draw — and the history
still answers the question it exists for.

What to draw is decided by `plan()`, which needs no display: where each tile
goes, how big each symbol is, which symbols are alerts. The canvas only paints
what the plan already decided.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
from vigia_eew.tiles import ATTRIBUTION, TILE_SIZE, TileRef

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


class _Tiles:
    """A tile provider that always has the tile, and counts who asked."""

    def __init__(self, *, available: bool = True) -> None:
        self.asked: list[TileRef] = []
        self._available = available

    def tile(self, ref: TileRef) -> bytes | None:
        self.asked.append(ref)
        return b"PNG" if self._available else None


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
    tiles = _Tiles()

    drawing = plan(
        [_record(event_id="a"), _record(lat=10.8, lon=-67.1, event_id="b")],
        tiles=tiles,
        zoom=7,
        width=TILE_SIZE * 2,
        height=TILE_SIZE * 2,
    )

    assert len(drawing.markers) == 2
    assert {marker.record.source_event_id for marker in drawing.markers} == {"a", "b"}


def test_two_earthquakes_in_different_places_land_in_different_places() -> None:
    drawing = plan(
        [_record(lat=10.0, lon=-67.0, event_id="a"), _record(lat=11.0, lon=-66.0, event_id="b")],
        tiles=_Tiles(),
        zoom=8,
        width=TILE_SIZE * 3,
        height=TILE_SIZE * 3,
    )

    first, second = drawing.markers
    assert (first.x, first.y) != (second.x, second.y)
    assert second.x > first.x  # further east
    assert second.y < first.y  # further north


def test_the_plan_asks_only_for_the_tiles_under_the_viewport() -> None:
    tiles = _Tiles()

    plan([_record()], tiles=tiles, zoom=7, width=TILE_SIZE, height=TILE_SIZE)

    assert 1 <= len(tiles.asked) <= 4


def test_the_attribution_travels_with_the_plan() -> None:
    """CA-112.7: it is part of what a map *is*, not decoration added later."""
    drawing = plan([_record()], tiles=_Tiles(), zoom=7, width=TILE_SIZE, height=TILE_SIZE)

    assert drawing.attribution == ATTRIBUTION


# --- CA-112.2 · No tiles is a state, not a failure --------------------------------


def test_with_no_tile_at_all_the_map_declares_itself_unavailable() -> None:
    drawing = plan([_record()], tiles=_Tiles(available=False), zoom=7, width=256, height=256)

    assert drawing.available is False
    assert drawing.tiles == []


def test_an_unavailable_map_draws_no_markers() -> None:
    """A dot at pixel (100, 200) with no map under it means nothing.

    Drawing the symbols over a blank rectangle would look like a map and be a
    picture of nowhere. Saying the map is unavailable is the honest answer,
    and the list is already on screen answering the real question.
    """
    drawing = plan([_record()], tiles=_Tiles(available=False), zoom=7, width=256, height=256)

    assert drawing.markers == []


def test_a_map_with_tiles_is_available() -> None:
    drawing = plan([_record()], tiles=_Tiles(), zoom=7, width=256, height=256)

    assert drawing.available is True
    assert drawing.tiles != []


def test_a_provider_that_raises_is_still_only_an_unavailable_map() -> None:
    """Art. 3: the window must not fall over because a tile server did."""

    class _Broken:
        def tile(self, ref: TileRef) -> bytes | None:
            raise OSError("no route to host")

    drawing = plan([_record()], tiles=_Broken(), zoom=7, width=256, height=256)

    assert drawing.available is False


def test_a_partly_cached_zone_still_draws() -> None:
    """One tile in hand is a map; demanding all of them would waste the cache."""

    class _Patchy:
        def __init__(self) -> None:
            self.calls = 0

        def tile(self, ref: TileRef) -> bytes | None:
            self.calls += 1
            return b"PNG" if self.calls == 1 else None

    drawing = plan([_record()], tiles=_Patchy(), zoom=7, width=TILE_SIZE * 2, height=TILE_SIZE * 2)

    assert drawing.available is True
    assert len(drawing.tiles) == 1
    assert drawing.markers != []


# --- The canvas (opt-in: VIGIA_GUI_TESTS=1) ---------------------------------------


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_canvas_draws_the_attribution_and_a_legend(tmp_path: Path) -> None:
    """CA-112.5 and CA-112.7 on the real widget: both are always on screen."""
    import tkinter as tk

    from vigia_eew.notify.history_map import HistoryMap

    root = tk.Tk()
    map_view = HistoryMap(root, tiles=_Tiles(available=False))
    map_view.show([_record()])
    root.update_idletasks()

    texts = [
        map_view.canvas.itemcget(item, "text")
        for item in map_view.canvas.find_all()
        if map_view.canvas.type(item) == "text"
    ]
    assert any(ATTRIBUTION in text for text in texts)
    assert any("Alerted" in text for text in texts)
    assert any("Discarded" in text for text in texts)
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_an_unavailable_map_says_so_on_the_canvas(tmp_path: Path) -> None:
    import tkinter as tk

    from vigia_eew.notify.history_map import HistoryMap

    root = tk.Tk()
    map_view = HistoryMap(root, tiles=_Tiles(available=False))
    map_view.show([_record()])
    root.update_idletasks()

    texts = " ".join(
        map_view.canvas.itemcget(item, "text")
        for item in map_view.canvas.find_all()
        if map_view.canvas.type(item) == "text"
    )
    assert "unavailable" in texts.lower()
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_a_real_tile_reaches_the_canvas(tmp_path: Path) -> None:
    """The Pillow-to-Tk bridge, which is the packaging risk ADR-027 names.

    A real PNG, decoded by Pillow and handed to a real Tk canvas. If that
    bridge is missing -- in a frozen binary it is exactly the kind of thing
    that goes missing -- this is where it shows.
    """
    import io
    import tkinter as tk

    from PIL import Image

    from vigia_eew.notify.history_map import HistoryMap

    buffer = io.BytesIO()
    Image.new("RGB", (TILE_SIZE, TILE_SIZE), "green").save(buffer, format="PNG")
    png = buffer.getvalue()

    class _Real:
        def tile(self, ref: TileRef) -> bytes | None:
            return png

    root = tk.Tk()
    map_view = HistoryMap(root, tiles=_Real())
    map_view.show([_record()])
    root.update_idletasks()

    images = [i for i in map_view.canvas.find_all() if map_view.canvas.type(i) == "image"]
    assert images, "no tile reached the canvas"
    assert map_view.drawing.available is True
    root.destroy()


def test_the_real_window_tests_run_in_ci_and_not_only_here() -> None:
    """A check only the developer runs is a check that stops being run.

    The widget smokes are what catch the failures that need a real toolkit --
    a `PhotoImage` bound to the wrong interpreter, a control that never
    reached the panel, an alert that will not build. CI already installs Xvfb
    for them; this asserts it also switches them on (REQ-DEV-003).
    """
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text()

    assert "VIGIA_GUI_TESTS" in workflow
    assert "xvfb-run" in workflow
