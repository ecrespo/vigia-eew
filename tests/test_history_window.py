"""One filter, two views (T-149, REQ-MAP-004, CA-112.6).

The table and the map are two readings of the same question, so there is one
filter and both obey it. A map showing symbols the table has already filtered
away is not a second opinion -- it is the product contradicting itself on one
screen.

The wiring is what this file checks: that the map is fed from the rows the
list produced, and from nowhere else.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vigia_eew.history import EventRecord, HistoryStore
from vigia_eew.notify.history_view import HistoryList
from vigia_eew.tiles import TileRef

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


class _Tiles:
    def tile(self, ref: TileRef) -> bytes | None:
        return b"PNG"


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
    drawing = plan(listing.records(), tiles=_Tiles(), zoom=7, width=512, height=512)

    assert {marker.record.source_event_id for marker in drawing.markers} == {
        row.record.source_event_id for row in listing.rows
    }


def test_filtering_reduces_rows_and_symbols_to_the_same_set(store: HistoryStore) -> None:
    from vigia_eew.notify.history_map import plan

    listing = HistoryList(store)
    listing.set_filter(min_magnitude=4.0)

    drawing = plan(listing.records(), tiles=_Tiles(), zoom=7, width=512, height=512)

    assert {row.record.source_event_id for row in listing.rows} == {"big", "middling"}
    assert {marker.record.source_event_id for marker in drawing.markers} == {"big", "middling"}


def test_the_list_hands_over_records_not_the_strings_it_made(store: HistoryStore) -> None:
    """The map needs the coordinates the table turned into text."""
    listing = HistoryList(store)

    assert all(isinstance(record, EventRecord) for record in listing.records())
    assert len(listing.records()) == len(listing.rows)


# --- The window that wires them together ------------------------------------------


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_window_shows_both_views(store: HistoryStore) -> None:
    import tkinter as tk

    from vigia_eew.notify.history_window import HistoryWindow

    root = tk.Tk()
    window = HistoryWindow(root, store, tiles=_Tiles())
    root.update_idletasks()

    assert len(window.view.table.get_children()) == 3
    assert len(window.map.drawing.markers) == 3
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_one_filter_moves_both_views(store: HistoryStore) -> None:
    """CA-112.6 through the widgets: one action, two views, one set."""
    import tkinter as tk

    from vigia_eew.notify.history_window import HistoryWindow

    root = tk.Tk()
    window = HistoryWindow(root, store, tiles=_Tiles())
    root.update_idletasks()

    window.listing.set_filter(min_magnitude=4.0)
    window.refresh()
    root.update_idletasks()

    assert len(window.view.table.get_children()) == 2
    assert len(window.map.drawing.markers) == 2


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_sorting_the_table_leaves_the_map_showing_the_same_set(
    store: HistoryStore,
) -> None:
    """Order is a property of a table; a map has no rows to reorder.

    What must not change is *which* earthquakes are on it.
    """
    import tkinter as tk

    from vigia_eew.notify.history_window import HistoryWindow

    root = tk.Tk()
    window = HistoryWindow(root, store, tiles=_Tiles())
    root.update_idletasks()
    before = {marker.record.source_event_id for marker in window.map.drawing.markers}

    window.view._sort("magnitude")
    root.update_idletasks()

    assert {m.record.source_event_id for m in window.map.drawing.markers} == before
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_window_works_with_no_map_at_all(store: HistoryStore) -> None:
    """CA-112.2 on the real window: the table is unaffected by a dead provider."""
    import tkinter as tk

    from vigia_eew.notify.history_window import HistoryWindow

    class _Nothing:
        def tile(self, ref: TileRef) -> bytes | None:
            return None

    root = tk.Tk()
    window = HistoryWindow(root, store, tiles=_Nothing())
    root.update_idletasks()

    assert window.map.drawing.available is False
    assert len(window.view.table.get_children()) == 3
    root.destroy()
