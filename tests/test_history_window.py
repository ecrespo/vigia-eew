"""One filter, two views (T-149, REQ-MAP-004, CA-112.6).

The table and the map are two readings of the same question, so there is one
filter and both obey it. A map showing symbols the table has already filtered
away is not a second opinion -- it is the product contradicting itself on one
screen.

The wiring is what this file checks: that the map is fed from the rows the
list produced, and from nowhere else.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
