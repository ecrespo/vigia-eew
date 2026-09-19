"""Tests for the history list view (T-146, REQ-HIS-005, HU-111).

This is the task that delivers the whole point of the history: somebody asks
"why was I not warned about that earthquake?", and the answer is a row with a
reason in it. The plan says so in as many words -- if scope had to be cut, the
map goes and this does not.

So the rules live in `HistoryList`, which needs no display and no network, and
the widget tree is a thin thing on top with its own opt-in smoke.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vigia_eew.history import EventRecord, HistoryStore
from vigia_eew.notify.history_view import COLUMNS, HistoryList

_WHEN = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _record(**overrides: object) -> EventRecord:
    fields: dict = {
        "correlation_id": "tr-1",
        "source": "GEOFON",
        "source_event_id": "gfz-1",
        "occurred_at": _WHEN,
        "recorded_at": _WHEN,
        "latitude": 10.6,
        "longitude": -66.9,
        "depth_km": 12.0,
        "magnitude": 5.2,
        "region": "NEAR THE COAST OF VENEZUELA",
        "distance_km": 20.0,
        "severity": "warning",
        "verdict": "alerted",
        "reason": None,
    }
    fields.update(overrides)
    return EventRecord(**fields)


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.open()
    store.record(
        _record(
            source="EMSC",
            source_event_id="emsc-big",
            magnitude=6.1,
            distance_km=40.0,
            occurred_at=_WHEN - timedelta(days=2),
        )
    )
    store.record(
        _record(
            source="USGS",
            source_event_id="usgs-small",
            magnitude=2.7,
            distance_km=90.0,
            verdict="discarded",
            reason="magnitude",
            severity=None,
            occurred_at=_WHEN - timedelta(hours=3),
        )
    )
    store.record(
        _record(
            source="FUNVISIS",
            source_event_id="fun-far",
            magnitude=4.4,
            distance_km=900.0,
            verdict="discarded",
            reason="radius",
            severity=None,
            occurred_at=_WHEN - timedelta(hours=1),
        )
    )
    yield store
    store.close()


@pytest.fixture
def listing(store: HistoryStore) -> HistoryList:
    return HistoryList(store)


# --- What the table shows --------------------------------------------------------


def test_it_opens_on_the_most_recent_first(listing: HistoryList) -> None:
    assert [row.source for row in listing.rows] == ["FUNVISIS", "USGS", "EMSC"]


def test_a_discarded_earthquake_shows_why(listing: HistoryList) -> None:
    """The question the whole feature exists to answer, in one cell."""
    far = next(row for row in listing.rows if row.source == "FUNVISIS")

    assert far.verdict == "Discarded"
    assert far.reason == "Outside the radius"


def test_an_alerted_earthquake_has_no_reason_to_show(listing: HistoryList) -> None:
    alerted = next(row for row in listing.rows if row.source == "EMSC")

    assert alerted.verdict == "Alerted"
    assert alerted.reason == ""


def test_every_reason_the_pipeline_can_give_has_words(listing: HistoryList) -> None:
    """A reason with no translation would reach the user as `freshness`.

    The filter and the deduplicator between them produce exactly these five;
    the test fails if one is added upstream without a phrase for it here.
    """
    from vigia_eew.notify.history_view import REASONS

    assert set(REASONS) == {"radius", "magnitude", "country", "freshness", "duplicate"}
    for reason in REASONS:
        assert REASONS[reason] != reason


def test_an_unknown_reason_is_shown_rather_than_hidden(store: HistoryStore) -> None:
    """A row the product cannot phrase is still a row somebody needs to see."""
    store.record(
        _record(source_event_id="odd", verdict="discarded", reason="eclipse", severity=None)
    )

    listing = HistoryList(store)

    assert any(row.reason == "eclipse" for row in listing.rows)


def test_the_rows_are_formatted_for_reading_not_for_arithmetic(listing: HistoryList) -> None:
    row = next(row for row in listing.rows if row.source == "EMSC")

    assert row.magnitude == "M 6.1"
    assert row.distance == "40 km"
    assert ":" in row.time  # a local time, not an epoch


def test_the_columns_are_declared_once(listing: HistoryList) -> None:
    """The header and the row are built from one list, so they cannot disagree."""
    assert [column.key for column in COLUMNS] == [
        "time",
        "magnitude",
        "place",
        "distance",
        "source",
        "verdict",
        "reason",
    ]
    row = listing.rows[0]
    for column in COLUMNS:
        assert isinstance(getattr(row, column.key), str)


def test_it_says_how_many_of_how_many(listing: HistoryList) -> None:
    listing.page_size = 2
    listing.refresh()

    assert len(listing.rows) == 2
    assert listing.total == 3


def test_an_empty_history_is_a_state_not_an_error(tmp_path: Path) -> None:
    empty = HistoryStore(tmp_path / "empty.sqlite3")
    empty.open()

    listing = HistoryList(empty)

    assert listing.rows == []
    assert listing.total == 0
    empty.close()


# --- Filtering and sorting (CA-111.8) ---------------------------------------------


def test_filtering_by_magnitude_reduces_the_rows(listing: HistoryList) -> None:
    listing.set_filter(min_magnitude=5.0)

    assert [row.source for row in listing.rows] == ["EMSC"]


def test_filtering_by_verdict_separates_them(listing: HistoryList) -> None:
    listing.set_filter(verdict="discarded")

    assert {row.verdict for row in listing.rows} == {"Discarded"}


def test_filtering_by_network_offers_what_is_there(listing: HistoryList) -> None:
    assert listing.available_sources == ["EMSC", "FUNVISIS", "USGS"]

    listing.set_filter(sources=("EMSC",))

    assert [row.source for row in listing.rows] == ["EMSC"]


def test_clearing_a_filter_brings_the_rows_back(listing: HistoryList) -> None:
    listing.set_filter(min_magnitude=5.0)
    listing.set_filter(min_magnitude=None)

    assert len(listing.rows) == 3


def test_sorting_by_a_column_reorders_the_rows(listing: HistoryList) -> None:
    listing.sort_by("magnitude")

    assert [row.magnitude for row in listing.rows] == ["M 6.1", "M 4.4", "M 2.7"]


def test_sorting_by_the_same_column_twice_reverses_it(listing: HistoryList) -> None:
    listing.sort_by("magnitude")
    listing.sort_by("magnitude")

    assert [row.magnitude for row in listing.rows] == ["M 2.7", "M 4.4", "M 6.1"]


def test_a_column_that_cannot_be_sorted_is_left_alone(listing: HistoryList) -> None:
    """`place` is free text from four different catalogues; sorting it sorts
    nothing anyone means. Refusing beats an order that looks meaningful."""
    before = [row.source for row in listing.rows]

    listing.sort_by("place")

    assert [row.source for row in listing.rows] == before


def test_the_filters_are_one_object_both_views_can_read(listing: HistoryList) -> None:
    """T-149 depends on this: the map reads the same query the table ran."""
    listing.set_filter(min_magnitude=5.0)

    assert listing.query.min_magnitude == 5.0


# --- REQ-MAP-002 · The list needs nothing but the file ----------------------------


def test_the_list_view_imports_nothing_that_needs_a_network(tmp_path: Path) -> None:
    """The list is the feature; the map is a view on top of it (Art. 3).

    Asserted against what the module *imports*, because the property worth
    keeping is that the list cannot come to depend on connectivity -- not
    that it happened not to today. Prose about the map is fine; an import of
    it is not.
    """
    import ast

    import vigia_eew.notify.history_view as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for forbidden in ("httpx", "socket", "urllib", "requests", "vigia_eew.tiles"):
        assert not any(name.startswith(forbidden) for name in imported), (
            f"the list view imports {forbidden}"
        )


def test_it_is_in_spanish_when_the_agent_is(store: HistoryStore) -> None:
    """RNF-10: the strings in the code are English and Spanish ships with it."""
    listing = HistoryList(store, locale_code="es")

    far = next(row for row in listing.rows if row.source == "FUNVISIS")
    assert far.verdict == "Descartado"
    assert far.reason == "Fuera del radio"


# --- The widget tree (opt-in: VIGIA_GUI_TESTS=1) ----------------------------------


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_real_table_shows_a_row_per_arrival(store: HistoryStore) -> None:
    import tkinter as tk

    from vigia_eew.notify.history_view import HistoryView

    root = tk.Tk()
    view = HistoryView(root, HistoryList(store))
    root.update_idletasks()

    assert len(view.table.get_children()) == 3
    assert view.table["columns"] == tuple(column.key for column in COLUMNS)
    root.destroy()


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_filtering_in_the_real_table_reduces_it(store: HistoryStore) -> None:
    import tkinter as tk

    from vigia_eew.notify.history_view import HistoryView

    root = tk.Tk()
    view = HistoryView(root, HistoryList(store))
    root.update_idletasks()

    view.listing.set_filter(min_magnitude=5.0)
    view.refresh()
    root.update_idletasks()

    assert len(view.table.get_children()) == 1
    root.destroy()


# --- Reaching it from the tray (REQ-HIS-005) --------------------------------------


def test_the_tray_offers_the_history() -> None:
    from vigia_eew.agent_state import AgentState
    from vigia_eew.tray import build_icon

    icon = build_icon(
        state=AgentState(),
        paused=lambda: False,
        toggle_pause=lambda: None,
        edit_config=lambda: None,
        exit=lambda: None,
        open_history=lambda: None,
    )

    texts = [str(item.text) for item in icon.menu if item.text is not None]
    assert any(t.lower().startswith("history") for t in texts)


def test_opening_the_history_is_scheduled_on_the_tk_thread(monkeypatch, tmp_path: Path) -> None:
    """Tkinter is not thread-safe and the tray is not on its thread (ADR-006)."""
    import vigia_eew.wiring as wiring_module
    from vigia_eew.app import Application
    from vigia_eew.config import Settings

    opened: list[int] = []
    monkeypatch.setattr(wiring_module.Wiring, "open_history", lambda self, root: opened.append(1))

    class _FakeRoot:
        def __init__(self) -> None:
            self.after_calls: list[tuple[int, object]] = []

        def after(self, ms, callback):
            self.after_calls.append((ms, callback))

    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._root = _FakeRoot()

    app._open_history()

    assert len(app._root.after_calls) == 1
    app._root.after_calls[0][1]()
    assert opened == [1]


@pytest.mark.gui
@pytest.mark.skipif(
    not os.environ.get("VIGIA_GUI_TESTS"), reason="real GUI test; opt-in VIGIA_GUI_TESTS=1"
)
def test_smoke_the_tray_entry_opens_one_history_window(tmp_path: Path) -> None:
    import tkinter as tk

    from vigia_eew.agent_state import AgentState
    from vigia_eew.config import Settings
    from vigia_eew.state import StateStore
    from vigia_eew.wiring import Wiring

    root = tk.Tk()
    root.withdraw()
    wiring = Wiring(Settings(), StateStore(tmp_path / "state.json"), AgentState())

    first = wiring.open_history(root)
    second = wiring.open_history(root)
    root.update_idletasks()

    assert first is second
    assert len([w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]) == 1
    root.destroy()
