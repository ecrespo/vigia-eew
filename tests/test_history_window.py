"""One filter, two views (T-149, REQ-MAP-004, CA-112.6).

The table and the map are two readings of the same question, so there is one
filter and both obey it. A map showing symbols the table has already filtered
away is not a second opinion -- it is the product contradicting itself on one
screen.

The wiring is what this file checks: that the map is fed from the rows the
list produced, and from nowhere else.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vigia_eew.history import EventRecord, HistoryStore
from vigia_eew.notify.history_view import HistoryList

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _record(*, magnitude: float, event_id: str, verdict: str = "alerted") -> EventRecord:
    return EventRecord(
        correlation_id=f"tr-{event_id}",
        source="GEOFON",
        source_event_id=event_id,
        occurred_at=_WHEN,
        recorded_at=_WHEN,
        latitude=10.6,
        longitude=-66.9,
        depth_km=12.0,
        magnitude=magnitude,
        region="NEAR THE COAST OF VENEZUELA",
        distance_km=20.0,
        verdict=verdict,
        severity="warning" if verdict == "alerted" else None,
    )


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.open()
    store.record(_record(magnitude=6.1, event_id="big"))
    store.record(_record(magnitude=4.4, event_id="middling"))
    store.record(_record(magnitude=2.7, event_id="small", verdict="discarded"))
    yield store
    store.close()


# --- CA-112.6 · The same set, both ways -------------------------------------------


def test_the_map_is_drawn_from_the_rows_the_list_produced(store: HistoryStore) -> None:
    from vigia_eew.notify.history_map import plan

    listing = HistoryList(store)
    markers = plan(listing.records())

    assert {marker.record.source_event_id for marker in markers} == {
        row.record.source_event_id for row in listing.rows
    }


def test_filtering_reduces_rows_and_symbols_to_the_same_set(store: HistoryStore) -> None:
    from vigia_eew.notify.history_map import plan

    listing = HistoryList(store)
    listing.set_filter(min_magnitude=4.0)

    markers = plan(listing.records())

    assert {row.record.source_event_id for row in listing.rows} == {"big", "middling"}
    assert {marker.record.source_event_id for marker in markers} == {"big", "middling"}


def test_the_list_hands_over_records_not_the_strings_it_made(store: HistoryStore) -> None:
    """The map needs the coordinates the table turned into text."""
    listing = HistoryList(store)

    assert all(isinstance(record, EventRecord) for record in listing.records())
    assert len(listing.records()) == len(listing.rows)


# --- The screen that wires them together (Flet dataclasses: no display) ---------


def _table_rows(window) -> int:
    return len(window.table.table.rows)


def test_the_screen_shows_both_views(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)

    assert _table_rows(window) == 3
    assert len(window.map.markers) == 3


def test_one_filter_moves_both_views(store: HistoryStore) -> None:
    """CA-112.6 through the controls: one action, two views, one set."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    window.listing.set_filter(min_magnitude=4.0)
    window.refresh()

    assert _table_rows(window) == 2
    assert len(window.map.markers) == 2


def test_the_magnitude_field_filters_both_views(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    window.table._magnitude.value = "4"
    window.table._apply_magnitude()

    assert _table_rows(window) == 2
    assert len(window.map.markers) == 2


def test_sorting_the_table_leaves_the_map_showing_the_same_set(store: HistoryStore) -> None:
    """Order is a property of a table; what must not change is *which* earthquakes."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    before = {marker.record.source_event_id for marker in window.map.markers}

    window.table._sort("magnitude")

    assert {m.record.source_event_id for m in window.map.markers} == before


def test_the_screen_works_with_no_map_at_all(store: HistoryStore) -> None:
    """CA-112.2: the table is unaffected by a dead provider -- or no map."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store, with_map=False)

    assert window.map is None
    assert _table_rows(window) == 3


def test_the_map_opens_on_the_reference_point(store: HistoryStore) -> None:
    """A worldwide history's midpoint is the Atlantic; the user's point is not."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store, reference=(10.28, -67.85))
    centre = window.map.map.initial_center

    assert (centre.latitude, centre.longitude) == (10.28, -67.85)


# --- T-158 · the table pages, the map does not (ADR-032, REQ-HIS-008) -------------


@pytest.fixture(scope="module")
def long_store(tmp_path_factory) -> HistoryStore:
    """Built once for the module: every test here only reads it."""
    made = HistoryStore(tmp_path_factory.mktemp("long") / "long.sqlite3").open()
    for n in range(400):
        made.record(
            EventRecord(
                correlation_id=f"tr-{n}",
                source="EMSC",
                source_event_id=f"e-{n}",
                occurred_at=_WHEN + timedelta(minutes=n),
                recorded_at=_WHEN + timedelta(minutes=n),
                latitude=10.0 + n / 1000,
                longitude=-66.0,
                depth_km=10.0,
                magnitude=3.0 + (n % 30) / 10,
                region="SOMEWHERE",
                distance_km=50.0,
                verdict="discarded",
                reason="magnitude",
            )
        )
    yield made
    made.close()


def _on_map(window) -> set[str]:
    return {marker.record.source_event_id for marker in window.map.markers}


def test_the_list_hands_over_the_whole_filtered_set(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)

    everything = listing.everything(1000)

    assert len(listing.rows) == 150
    assert len(everything.records) == 400
    assert everything.total == 400
    assert everything.truncated is False


def test_the_whole_set_obeys_the_filter(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)
    listing.set_min_magnitude(5.0)

    everything = listing.everything(1000)

    assert everything.total == listing.total
    assert all(record.magnitude >= 5.0 for record in everything.records)
    assert len(everything.records) == listing.total


def test_the_map_shows_every_matching_earthquake_not_one_page(long_store) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(long_store)

    assert _table_rows(window) == 150
    assert len(window.map.markers) == 400


def test_turning_a_page_does_not_move_the_map(long_store: HistoryStore) -> None:
    """Otherwise "the same set" would mean "the same 150 rows"."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(long_store)
    before = _on_map(window)

    window.table._turn(+1)

    assert _on_map(window) == before
    assert _table_rows(window) == 150


def test_a_set_too_large_for_the_map_is_said_with_both_figures(long_store, monkeypatch) -> None:
    """Leaving earthquakes off without saying so under-reports the history."""
    from vigia_eew.notify import history_window
    from vigia_eew.notify.history_window import HistoryWindow

    monkeypatch.setattr(history_window, "MAP_SYMBOL_LIMIT", 100)

    window = HistoryWindow(long_store)

    assert len(window.map.markers) == 100
    assert window.map.truncation.visible is True
    assert "100" in window.map.truncation.value and "400" in window.map.truncation.value


def test_a_set_that_fits_says_nothing(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)

    assert window.map.truncation.visible is False


def test_without_the_map_the_list_still_filters_and_pages(long_store: HistoryStore) -> None:
    """CA-114.10: the list depends on the file and nothing else."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(long_store, with_map=False)
    window.table._turn(+1)
    window.table._distance.value = "10"
    window.table._apply_distance()

    assert window.map is None
    assert _table_rows(window) == 0


# --- T-159 · the tooltip is the table's own row (REQ-MAP-006, CA-114.7) -----------


def _tooltips(window) -> dict[str, str]:
    layer = next(layer for layer in window.map.map.layers if type(layer).__name__ == "MarkerLayer")
    return {
        planned.record.source_event_id: symbol.content.tooltip
        for symbol, planned in zip(layer.markers, window.map.markers, strict=True)
    }


def test_a_symbol_shows_the_data_of_its_table_entry(store: HistoryStore) -> None:
    """The magnitude, local time, place, distance and verdict -- as the table has them."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    tooltips = _tooltips(window)

    assert len(tooltips) == 3
    for row in window.listing.rows:
        tooltip = tooltips[row.record.source_event_id]
        for shown in (row.magnitude, row.time, row.place, row.distance, row.verdict):
            assert shown in tooltip


def test_the_tooltip_is_worded_by_the_list_not_by_the_map(store: HistoryStore) -> None:
    """One wording, so a symbol and its row cannot come to describe two earthquakes."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)

    for row in window.listing.rows:
        assert _tooltips(window)[row.record.source_event_id] == row.summary


def test_a_discarded_symbol_says_why(tmp_path: Path) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    held = HistoryStore(tmp_path / "why.sqlite3").open()
    held.record(
        EventRecord(
            correlation_id="tr-x",
            source="USGS",
            source_event_id="far",
            occurred_at=_WHEN,
            recorded_at=_WHEN,
            latitude=1.0,
            longitude=2.0,
            depth_km=10.0,
            magnitude=4.0,
            region="FAR AWAY",
            distance_km=900.0,
            verdict="discarded",
            reason="radius",
        )
    )

    window = HistoryWindow(held)

    assert "Outside the radius" in _tooltips(window)["far"]
    held.close()


# --- T-160 · the table and the map point at the same thing (REQ-MAP-007) ----------


def _selected_on_map(window) -> list[str]:
    return [m.record.source_event_id for m in window.map.markers if m.selected]


def _selected_in_table(window) -> list[int]:
    return [row.data for row in window.table.table.rows if row.selected]


def _row_id(window, event_id: str) -> int:
    everything = window.listing.everything(10_000)
    return next(r.id for r in everything.records if r.source_event_id == event_id)


def test_choosing_a_row_highlights_its_symbol(store: HistoryStore) -> None:
    """CA-114.8: exactly one, and it stands for that row."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    chosen = _row_id(window, "middling")

    window.table.choose(chosen)

    assert _selected_on_map(window) == ["middling"]
    assert _selected_in_table(window) == [chosen]


def test_choosing_another_row_moves_the_highlight(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    window.table.choose(_row_id(window, "middling"))

    window.table.choose(_row_id(window, "big"))

    assert _selected_on_map(window) == ["big"]


def test_choosing_the_chosen_row_again_lets_go_of_it(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    chosen = _row_id(window, "big")
    window.table.choose(chosen)

    window.table.choose(chosen)

    assert _selected_on_map(window) == []
    assert _selected_in_table(window) == []


def test_pressing_a_row_in_the_table_chooses_it(store: HistoryStore) -> None:
    """Through the control: what Flet calls when a row is pressed."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    row = window.table.table.rows[0]

    row.on_select_change(None)

    assert _selected_in_table(window) == [row.data]
    assert window.table.table.show_checkbox_column is False


def test_choosing_a_symbol_highlights_its_row(store: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    chosen = _row_id(window, "small")

    window.map.press(chosen)

    assert _selected_in_table(window) == [chosen]
    assert _selected_on_map(window) == ["small"]


def test_a_symbol_whose_row_is_on_another_page_brings_the_table_to_it(long_store) -> None:
    """CA-114.9: the table moves to the page that holds the row."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(long_store)
    oldest = _row_id(window, "e-0")  # newest first: the last row of the last page
    assert oldest not in [row.data for row in window.table.table.rows]

    window.map.press(oldest)

    assert window.listing.stretch == (301, 400, 400)
    assert _selected_in_table(window) == [oldest]
    assert _selected_on_map(window) == ["e-0"]


def test_a_filter_that_removes_the_chosen_earthquake_lets_go_of_it(store: HistoryStore) -> None:
    """A highlight on something no longer shown would point at nothing."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(store)
    window.table.choose(_row_id(window, "small"))

    window.table._magnitude.value = "4"
    window.table._apply_magnitude()

    assert _selected_on_map(window) == []
    assert _selected_in_table(window) == []
    assert window.table.selected is None


def test_turning_the_page_keeps_the_symbol_highlighted(long_store: HistoryStore) -> None:
    """The earthquake is still in the set and on the map; only its row left the page."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(long_store)
    window.table.choose(window.table.table.rows[0].data)
    chosen = _selected_on_map(window)

    window.table._turn(+1)

    assert _selected_on_map(window) == chosen
    assert _selected_in_table(window) == []


# --- T-162 · one earthquake, one symbol (REQ-HIS-009, CA-115.7) --------------------


@pytest.fixture
def twice(tmp_path: Path) -> HistoryStore:
    """One earthquake that came from two networks, and one that came from one."""
    from dataclasses import replace

    store = HistoryStore(tmp_path / "twice.sqlite3")
    store.open()
    first = replace(_record(magnitude=5.0, event_id="e1"), source="EMSC", correlation_id="q1")
    store.record(first)
    store.record(
        replace(first, source="USGS", source_event_id="u1", verdict="discarded", reason="duplicate")
    )
    store.record(replace(_record(magnitude=4.0, event_id="e2"), correlation_id="q2"))
    yield store
    store.close()


def _earthquakes_on_map(window) -> list[str]:
    return sorted(m.record.correlation_id for m in window.map.markers)


def _read_per_earthquake(window, on: bool = True) -> None:
    window.table.reading.value = on
    window.table.reading.on_change(None)


def test_per_earthquake_the_map_has_one_symbol_for_each(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(twice)
    assert _earthquakes_on_map(window) == ["q1", "q1", "q2"]

    _read_per_earthquake(window)

    assert _earthquakes_on_map(window) == ["q1", "q2"]
    assert _table_rows(window) == 2


def test_switching_back_shows_every_arrival_again(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(twice)
    _read_per_earthquake(window)

    _read_per_earthquake(window, on=False)

    assert _earthquakes_on_map(window) == ["q1", "q1", "q2"]


def test_an_arrival_the_earthquake_reading_hides_stops_being_the_chosen_one(
    twice: HistoryStore,
) -> None:
    """Chosen per arrival, then folded into its earthquake: nothing left to point at."""
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(twice)
    window.table.choose(_row_id(window, "u1"))

    _read_per_earthquake(window)

    assert window.table.selected is None
    assert _selected_on_map(window) == []
    assert window.table.arrivals.visible is False


def test_a_symbol_pressed_per_earthquake_lists_its_arrivals(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(twice)
    _read_per_earthquake(window)

    window.map.press(_row_id(window, "e1"))

    assert window.table.arrivals.visible is True
    assert len(window.table.arrivals.controls) == 1 + 2


def test_the_window_hands_the_list_the_order_of_trust(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_window import HistoryWindow

    window = HistoryWindow(twice, rank=("USGS", "EMSC"))

    assert window.listing.query.rank == ("USGS", "EMSC")


# --- T-166 · the playback, a third reading of the same query (HU-116) --------------


class _Timer:
    """Stands in for `FletShell.after`: queues, and runs on demand."""

    def __init__(self) -> None:
        self.pending: list = []

    def __call__(self, ms: int, action) -> None:
        self.pending.append(action)

    def tick(self) -> bool:
        if not self.pending:
            return False
        self.pending.pop(0)()
        return True

    def run_out(self) -> None:
        for _ in range(2000):
            if not self.tick():
                return
        raise AssertionError("the playback never stopped scheduling")


@pytest.fixture
def month(tmp_path: Path) -> HistoryStore:
    """Thirty earthquakes, one a day, magnitudes 3.0 to 5.9; the last came by two networks."""
    from dataclasses import replace

    store = HistoryStore(tmp_path / "month.sqlite3", prune_on_open=False)
    store.open()
    for day in range(30):
        base = _record(magnitude=3.0 + day / 10, event_id=f"d{day:02d}")
        store.record(replace(base, occurred_at=_WHEN + timedelta(days=day)))
    again = replace(
        _record(magnitude=5.9, event_id="d29-usgs", verdict="discarded"),
        source="USGS",
        correlation_id="tr-d29",
        reason="duplicate",
        occurred_at=_WHEN + timedelta(days=29),
    )
    store.record(again)
    yield store
    store.close()


def _playing_window(store: HistoryStore, **kwargs):
    from vigia_eew.notify.history_window import HistoryWindow

    timer = _Timer()
    return HistoryWindow(store, after=timer, zone="UTC", **kwargs), timer


def _magnitudes_on_map(window) -> list[float]:
    return sorted(round(m.record.magnitude, 1) for m in window.map.markers)


def test_without_a_timer_there_is_no_playback(month: HistoryStore) -> None:
    """Nothing could advance it; the screen is the table and the map, as before."""
    from vigia_eew.notify.history_window import HistoryWindow

    assert HistoryWindow(month).playback is None


def test_without_a_map_there_is_no_playback(month: HistoryStore) -> None:
    window, _timer = _playing_window(month, with_map=False)

    assert window.playback is None


def test_the_playback_reads_the_filtered_set_per_earthquake(month: HistoryStore) -> None:
    """ADR-035 §6: thirty-one arrivals in the table, thirty earthquakes to play."""
    window, _timer = _playing_window(month)

    assert window.listing.total == 31
    assert len(window.playback.timeline) == 30


def test_until_it_is_played_the_map_shows_the_whole_set(month: HistoryStore) -> None:
    window, timer = _playing_window(month)

    assert len(window.map.markers) == 31
    assert timer.pending == []


def test_a_frame_reaches_the_map_with_its_strengths(month: HistoryStore) -> None:
    """Three days of fading, an earthquake a day: three symbols, the newest in full."""
    window, _timer = _playing_window(month)

    window.playback.seek(10)

    by_age = sorted(window.map.markers, key=lambda m: m.record.occurred_at, reverse=True)
    assert len(by_age) == 3
    assert by_age[0].strength == 1.0
    assert by_age[0].strength > by_age[1].strength > by_age[2].strength > 0.0


def test_the_filter_governs_what_is_played(month: HistoryStore) -> None:
    """CA-116.8: no frame holds an earthquake the filter left out."""
    window, timer = _playing_window(month)
    window.table._magnitude.value = "5"
    window.table._apply_magnitude()
    assert len(window.playback.timeline) == 10

    window.playback.trail_switch.value = True
    window.playback.trail_switch.on_change(None)
    window.playback.play()
    seen: list[float] = []
    while timer.tick():
        seen.extend(_magnitudes_on_map(window))

    assert seen and min(seen) >= 5.0


def test_changing_the_filter_replaces_the_set_being_played(month: HistoryStore) -> None:
    """CA-116.8: the old playback stops, and the map shows what the filter selects."""
    window, timer = _playing_window(month)
    window.playback.play()
    timer.tick()

    window.table._magnitude.value = "5.5"
    window.table._apply_magnitude()
    timer.run_out()

    assert window.playback.playing is False
    assert window.playback.engaged is False
    assert len(window.playback.timeline) == 5
    assert _magnitudes_on_map(window) == [5.5, 5.6, 5.7, 5.8, 5.9, 5.9]  # the set, per arrival


def test_stopping_shows_the_whole_set_again(month: HistoryStore) -> None:
    window, _timer = _playing_window(month)
    window.playback.seek(4)
    assert len(window.map.markers) < 31

    window.playback.stop()

    assert len(window.map.markers) == 31
    assert all(marker.strength == 1.0 for marker in window.map.markers)


def test_turning_the_page_or_sorting_leaves_the_frame_on_the_map(month, monkeypatch) -> None:
    """Neither changes the set, so neither may take the map from the playback."""
    from vigia_eew.notify import history_view

    monkeypatch.setattr(history_view, "TABLE_ROW_LIMIT", 10)
    window, _timer = _playing_window(month)
    window.playback.seek(10)
    frame = [m.record.id for m in window.map.markers]

    window.table._turn(+1)
    window.table._sort("magnitude")

    assert [m.record.id for m in window.map.markers] == frame
    assert window.playback.step == 10


def test_choosing_a_row_during_the_playback_keeps_the_frame(month: HistoryStore) -> None:
    window, _timer = _playing_window(month)
    window.playback.seek(10)
    in_frame = window.map.markers[0].record.id

    window.table.choose(in_frame)

    assert len(window.map.markers) == 3
    assert [m.record.id for m in window.map.markers if m.selected] == [in_frame]


def test_a_set_too_large_plays_the_most_recent_and_says_so(month, monkeypatch) -> None:
    """CA-116.11 -- and the pause control still answers."""
    from vigia_eew.notify import history_window

    monkeypatch.setattr(history_window, "PLAYBACK_SYMBOL_LIMIT", 10)
    window, timer = _playing_window(month)
    window.table._sort("magnitude")  # the table's order is not the playback's

    playback = window.playback
    assert len(playback.timeline) == 10
    assert playback.timeline.period[0] == _WHEN + timedelta(days=20)
    assert playback.notice.visible is True
    assert "10" in playback.notice.value and "30" in playback.notice.value

    playback.play()
    timer.tick()
    playback.play_button.on_click(None)
    assert playback.playing is False


def test_playing_does_not_move_the_map(month: HistoryStore, monkeypatch) -> None:
    """CA-116.12: same centre, same zoom, and nothing that moves a map was called."""
    import flet_map as fm

    moved: list[str] = []
    for mover in ("move_to", "center_on", "zoom_to", "zoom_in", "zoom_out", "rotate_from"):
        monkeypatch.setattr(
            fm.Map, mover, lambda self, *a, _name=mover, **k: moved.append(_name), raising=True
        )
    window, timer = _playing_window(month, reference=(10.28, -67.85), zoom=7)
    the_map = window.map.map
    before = (the_map.initial_center, the_map.initial_zoom)

    window.playback.play()
    timer.run_out()

    assert window.playback.step == 29
    assert (the_map.initial_center, the_map.initial_zoom) == before
    assert moved == []


def test_without_tiles_the_playback_says_the_map_is_unavailable(month: HistoryStore) -> None:
    """CA-116.13: it is the same map, so it is the same notice."""
    window, timer = _playing_window(month)
    window.map._tile_failed(object())

    window.playback.play()
    timer.tick()

    assert window.map._notice.visible is True
    assert window.map.markers  # and the symbols are still played


def test_nothing_to_play_disables_the_control(month: HistoryStore) -> None:
    """CA-116.14."""
    window, _timer = _playing_window(month)

    window.table._magnitude.value = "9"
    window.table._apply_magnitude()

    assert window.playback.play_button.disabled is True
    assert window.playback.period.value == "Nothing to play"


def test_the_window_can_be_told_to_pause(month: HistoryStore) -> None:
    """What the shell calls when an alert covers the screen (REQ-TLP-006)."""
    window, timer = _playing_window(month)
    window.playback.play()
    timer.tick()

    window.pause_playback()
    timer.run_out()

    assert window.playback.playing is False
    assert window.playback.step == 1


def test_refreshing_the_screen_reads_the_set_to_play_again(month: HistoryStore) -> None:
    """The agent writes while the screen is open; coming back sees what it wrote."""
    from dataclasses import replace

    window, _timer = _playing_window(month)
    new = replace(_record(magnitude=4.0, event_id="late"), occurred_at=_WHEN + timedelta(days=40))
    month.record(new)

    window.refresh()

    assert len(window.playback.timeline) == 31
