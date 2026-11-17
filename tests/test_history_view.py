"""Tests for the history list view (T-146, REQ-HIS-005, HU-111).

This is the task that delivers the whole point of the history: somebody asks
"why was I not warned about that earthquake?", and the answer is a row with a
reason in it. The plan says so in as many words -- if scope had to be cut, the
map goes and this does not.

So the rules live in `HistoryList`, which needs no display and no network, and
the widget tree is a thin thing on top with its own opt-in smoke.
"""

from __future__ import annotations

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

    for forbidden in (
        "httpx",
        "socket",
        "urllib",
        "requests",
        "flet_map",
        "vigia_eew.notify.history_map",
        "vigia_eew.notify.map_view",
    ):
        assert not any(name.startswith(forbidden) for name in imported), (
            f"the list view imports {forbidden}"
        )


def test_it_is_in_spanish_when_the_agent_is(store: HistoryStore) -> None:
    """RNF-10: the strings in the code are English and Spanish ships with it."""
    listing = HistoryList(store, locale_code="es")

    far = next(row for row in listing.rows if row.source == "FUNVISIS")
    assert far.verdict == "Descartado"
    assert far.reason == "Fuera del radio"


# --- The controls (Flet dataclasses: no display needed) --------------------------


def test_the_real_table_shows_a_row_per_arrival(store: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(store))

    assert len(view.table.rows) == 3
    assert len(view.table.columns) == len(COLUMNS)


def test_filtering_in_the_real_table_reduces_it(store: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(store))
    view.listing.set_filter(min_magnitude=5.0)
    view.refresh()

    assert len(view.table.rows) == 1


def test_the_verdict_menu_filters_by_verdict(store: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(store))
    view._verdict.value = "discarded"
    view._apply_verdict()
    discarded = len(view.table.rows)
    view._clear()

    assert 0 < discarded < 3
    assert len(view.table.rows) == 3


def test_a_long_history_draws_a_bounded_table_and_says_so(tmp_path: Path) -> None:
    """A Flutter DataTable lays out every cell; 500 rows took seconds to appear."""
    from vigia_eew.notify import history_view
    from vigia_eew.notify.history_view import HistoryView

    many = HistoryStore(tmp_path / "many.sqlite3")
    many.open()
    for n in range(history_view.TABLE_ROW_LIMIT + 5):
        many.record(_record(source_event_id=f"e-{n}"))
    view = HistoryView(HistoryList(many))

    assert len(view.table.rows) == history_view.TABLE_ROW_LIMIT
    assert str(history_view.TABLE_ROW_LIMIT) in view.status.value
    many.close()


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


def test_opening_the_history_is_scheduled_on_the_ui_thread(
    monkeypatch, tmp_path: Path, fake_shell
) -> None:
    """Flet's controls belong to the UI loop and the tray is not on it (ADR-006)."""
    import vigia_eew.wiring as wiring_module
    from vigia_eew.app import Application
    from vigia_eew.config import Settings

    opened: list[int] = []
    monkeypatch.setattr(wiring_module.Wiring, "open_history", lambda self, shell: opened.append(1))

    app = Application(Settings(), config_path=tmp_path / "config.toml")
    app._shell = fake_shell

    app._open_history()

    assert len(fake_shell.after_calls) == 1
    assert opened == []
    fake_shell.run_pending()
    assert opened == [1]


def test_the_tray_entry_opens_one_history_screen(tmp_path: Path, fake_shell) -> None:
    from vigia_eew.agent_state import AgentState
    from vigia_eew.config import Settings
    from vigia_eew.state import StateStore
    from vigia_eew.wiring import Wiring

    wiring = Wiring(Settings(), StateStore(tmp_path / "state.json"), AgentState())

    first = wiring.open_history(fake_shell)
    second = wiring.open_history(fake_shell)

    assert first is second
    assert [key for key, _title, _view in fake_shell.screens] == ["history"]
    wiring.close_history()


# --- T-156 · the list owns every filter and the paging (REQ-HIS-005/007/008) -----
#
# REQ-HIS-005 was met by the store and not by the screen: the interface offered
# two filters of five. These tests are written against the list -- the object
# the screen and the terminal both drive -- and compare it with the store.

from datetime import date  # noqa: E402

from vigia_eew.history import HistoryQuery  # noqa: E402

UTC_ZONE = "UTC"


def _ids(records) -> list[str]:
    return [record.source_event_id for record in records]


def _listed(listing: HistoryList) -> list[str]:
    return _ids(row.record for row in listing.rows)


@pytest.fixture
def utc_listing(store: HistoryStore) -> HistoryList:
    return HistoryList(store, zone=UTC_ZONE)


def test_a_period_is_given_in_local_days(store: HistoryStore) -> None:
    """CA-114.2: the last day of the fixture, as the user's calendar has it."""
    listing = HistoryList(store, zone=UTC_ZONE)

    listing.set_period(date(2026, 9, 19), date(2026, 9, 19))

    assert set(_listed(listing)) == {"usgs-small", "fun-far"}
    expected = store.query(
        HistoryQuery(
            since=datetime(2026, 9, 19, tzinfo=UTC),
            until=datetime(2026, 9, 20, tzinfo=UTC) - timedelta(microseconds=1),
            limit=listing.page_size,
        )
    )
    assert _listed(listing) == _ids(expected)


def test_a_period_follows_the_configured_zone(store: HistoryStore) -> None:
    """In Caracas the 17th ends at 04:00 UTC on the 18th: the first event is inside."""
    listing = HistoryList(store, zone="America/Caracas")

    listing.set_period(date(2026, 9, 17), date(2026, 9, 17))

    assert _listed(listing) == ["emsc-big"]


def test_a_period_can_be_open_on_either_side(utc_listing: HistoryList) -> None:
    utc_listing.set_period(None, date(2026, 9, 18))
    assert _listed(utc_listing) == ["emsc-big"]

    utc_listing.set_period(date(2026, 9, 19), None)
    assert set(_listed(utc_listing)) == {"usgs-small", "fun-far"}

    utc_listing.set_period(None, None)
    assert len(utc_listing.rows) == 3


def test_a_period_that_ends_before_it_starts_is_refused(utc_listing: HistoryList) -> None:
    """CA-114.4: refused, and what was on screen stays."""
    utc_listing.set_period(date(2026, 9, 19), date(2026, 9, 19))
    before = (utc_listing.query, _listed(utc_listing))

    with pytest.raises(ValueError):
        utc_listing.set_period(date(2026, 9, 20), date(2026, 9, 19))

    assert (utc_listing.query, _listed(utc_listing)) == before


def test_a_maximum_distance_is_a_filter(store: HistoryStore, utc_listing: HistoryList) -> None:
    utc_listing.set_max_distance(100.0)

    assert set(_listed(utc_listing)) == {"emsc-big", "usgs-small"}
    assert _listed(utc_listing) == _ids(
        store.query(HistoryQuery(max_distance_km=100.0, limit=utc_listing.page_size))
    )


def test_networks_are_a_filter(store: HistoryStore, utc_listing: HistoryList) -> None:
    utc_listing.set_sources(["EMSC", "FUNVISIS"])

    assert set(_listed(utc_listing)) == {"emsc-big", "fun-far"}
    assert _listed(utc_listing) == _ids(
        store.query(HistoryQuery(sources=("EMSC", "FUNVISIS"), limit=utc_listing.page_size))
    )


def test_no_network_chosen_means_every_network(utc_listing: HistoryList) -> None:
    utc_listing.set_sources(["EMSC"])
    utc_listing.set_sources([])

    assert len(utc_listing.rows) == 3


def test_a_date_range_and_a_network_combine(store: HistoryStore, utc_listing) -> None:
    """CA-114.2, as worded: a range and a network, and exactly what the store says."""
    utc_listing.set_period(date(2026, 9, 19), date(2026, 9, 19))
    utc_listing.set_sources(["USGS"])

    assert _listed(utc_listing) == ["usgs-small"]
    assert utc_listing.total == store.count(utc_listing.query) == 1


def test_only_the_verdicts_in_the_history_are_offered(tmp_path: Path) -> None:
    """CA-114.3: a verdict nobody has seen is a filter that can only return nothing."""
    only_alerts = HistoryStore(tmp_path / "alerts.sqlite3").open()
    only_alerts.record(_record())

    listing = HistoryList(only_alerts)

    assert listing.available_verdicts == ["alerted"]
    assert listing.available_sources == ["GEOFON"]
    only_alerts.close()


# --- Paging (REQ-HIS-008, CA-114.5, CA-114.6) -------------------------------------


@pytest.fixture(scope="module")
def long_store(tmp_path_factory) -> HistoryStore:
    """400 arrivals a minute apart: e-0 is the oldest, e-399 the newest.

    Built once for the module: every test here only reads it, and four hundred
    commits per test is what made this file the slowest in the suite.
    """
    made = HistoryStore(tmp_path_factory.mktemp("long") / "long.sqlite3").open()
    for n in range(400):
        made.record(
            _record(
                source_event_id=f"e-{n}",
                occurred_at=_WHEN + timedelta(minutes=n),
                magnitude=3.0 + (n % 30) / 10,
            )
        )
    yield made
    made.close()


def test_a_page_is_what_the_table_can_draw(long_store: HistoryStore) -> None:
    from vigia_eew.notify.history_view import TABLE_ROW_LIMIT

    listing = HistoryList(long_store)

    assert listing.page_size == TABLE_ROW_LIMIT == 150
    assert len(listing.rows) == 150
    assert listing.stretch == (1, 150, 400)


def test_every_matching_entry_can_be_reached(long_store: HistoryStore) -> None:
    """CA-114.5: the last entry of the set is on the last page."""
    listing = HistoryList(long_store)

    listing.next_page()
    assert listing.stretch == (151, 300, 400)
    listing.next_page()

    assert listing.stretch == (301, 400, 400)
    assert _listed(listing)[-1] == "e-0"  # newest first, so the oldest comes last
    assert listing.total == long_store.count(listing.query)


def test_the_pages_together_are_the_whole_set_once(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)
    seen = _listed(listing)
    while listing.has_next:
        listing.next_page()
        seen += _listed(listing)

    assert len(seen) == 400
    assert len(set(seen)) == 400


def test_there_is_no_page_past_the_last_nor_before_the_first(long_store) -> None:
    listing = HistoryList(long_store)
    assert listing.has_previous is False

    listing.previous_page()
    assert listing.stretch == (1, 150, 400)

    listing.next_page()
    listing.next_page()
    assert listing.has_next is False
    listing.next_page()
    assert listing.stretch == (301, 400, 400)

    listing.previous_page()
    assert listing.stretch == (151, 300, 400)


def test_changing_a_filter_returns_to_the_first_page(long_store: HistoryStore) -> None:
    """CA-114.6: page three of the old set means nothing in the new one."""
    listing = HistoryList(long_store)
    listing.next_page()
    listing.next_page()

    listing.set_min_magnitude(3.0)

    assert listing.stretch[0] == 1


def test_sorting_returns_to_the_first_page(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)
    listing.next_page()

    listing.sort_by("magnitude")

    assert listing.stretch[0] == 1


def test_an_empty_set_has_an_empty_stretch(tmp_path: Path) -> None:
    empty = HistoryStore(tmp_path / "empty2.sqlite3").open()

    listing = HistoryList(empty)

    assert listing.stretch == (0, 0, 0)
    assert listing.has_next is False
    empty.close()


def test_the_stretch_is_said_in_words(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)
    listing.next_page()

    assert listing.stretch_text == "151–300 of 400"
    assert HistoryList(long_store, locale_code="es").stretch_text == "1–150 de 400"


# --- T-157 · the controls (CA-114.1; Flet dataclasses, no display) ----------------


def _view(store: HistoryStore, **kwargs):
    from vigia_eew.notify.history_view import HistoryView

    return HistoryView(HistoryList(store, zone=UTC_ZONE), **kwargs)


def _shown(view) -> list[str]:
    return [row.data for row in view.table.rows]


def test_the_five_criteria_are_on_the_screen(store: HistoryStore) -> None:
    """CA-114.1: each can be set from the screen, without editing a file."""
    view = _view(store)

    assert set(view.filters) == {"period", "magnitude", "distance", "verdict", "sources"}


def test_the_period_fields_filter_by_day(store: HistoryStore) -> None:
    view = _view(store)

    view._since.value = "2026-09-19"
    view._until.value = "2026-09-19"
    view._apply_period()

    assert len(view.table.rows) == 2
    assert view._period_error.visible is False


def test_a_half_typed_date_is_not_a_filter_yet(store: HistoryStore) -> None:
    view = _view(store)

    view._since.value = "2026-09-"
    view._apply_period()

    assert len(view.table.rows) == 3
    assert view._period_error.visible is False


def test_a_period_that_ends_before_it_starts_is_said_on_screen(store: HistoryStore) -> None:
    """CA-114.4: the screen says so and keeps the entries of the last valid filter."""
    view = _view(store)
    view._since.value = "2026-09-19"
    view._apply_period()
    assert len(view.table.rows) == 2

    view._until.value = "2026-09-18"
    view._apply_period()

    assert view._period_error.visible is True
    assert view._period_error.value
    assert len(view.table.rows) == 2

    view._until.value = "2026-09-19"
    view._apply_period()
    assert view._period_error.visible is False


def test_the_distance_field_filters_by_distance(store: HistoryStore) -> None:
    view = _view(store)

    view._distance.value = "100"
    view._apply_distance()

    assert len(view.table.rows) == 2


def test_the_networks_offered_are_the_ones_in_the_history(store: HistoryStore) -> None:
    """CA-114.3: GEOFON is not in this history, so it is not offered."""
    view = _view(store)

    assert [chip.data for chip in view._source_chips.controls] == ["EMSC", "FUNVISIS", "USGS"]


def test_choosing_networks_filters_by_them(store: HistoryStore) -> None:
    view = _view(store)

    view._toggle_source("EMSC")
    assert _shown_sources(view) == {"EMSC"}

    view._toggle_source("USGS")
    assert _shown_sources(view) == {"EMSC", "USGS"}

    view._toggle_source("EMSC")
    view._toggle_source("USGS")
    assert len(view.table.rows) == 3  # none chosen is every network


def _shown_sources(view) -> set[str]:
    return {row.record.source for row in view.listing.rows}


def test_a_chosen_network_is_marked_as_chosen(store: HistoryStore) -> None:
    view = _view(store)

    view._toggle_source("USGS")

    chosen = {chip.data: chip.selected for chip in view._source_chips.controls}
    assert chosen == {"EMSC": False, "FUNVISIS": False, "USGS": True}


def test_the_verdicts_offered_are_the_ones_in_the_history(tmp_path: Path) -> None:
    """CA-114.3, and X-1: a verdict added later needs no change in the control."""
    held = HistoryStore(tmp_path / "three.sqlite3").open()
    held.record(_record(source_event_id="a"))
    held.record(_record(source_event_id="b", verdict="recovered"))
    view = _view(held)

    keys = [option.key for option in view._verdict.options]

    assert keys == [view._any, "alerted", "recovered"]
    view._verdict.value = "recovered"
    view._apply_verdict()
    assert len(view.table.rows) == 1
    held.close()


def test_the_pager_moves_through_the_set_and_says_where_it_is(long_store) -> None:
    """CA-114.5: the stretch and the total, and the way to the rest."""
    view = _view(long_store)
    assert view.status.value == "1–150 of 400"
    assert view._previous.disabled is True
    assert view._next.disabled is False

    view._turn(+1)
    view._turn(+1)

    assert view.status.value == "301–400 of 400"
    assert len(view.table.rows) == 100
    assert view._next.disabled is True
    assert view._previous.disabled is False

    view._turn(-1)
    assert view.status.value == "151–300 of 400"


def test_nothing_loads_more_than_it_shows(long_store: HistoryStore) -> None:
    view = _view(long_store)

    assert len(view.listing.rows) == len(view.table.rows) == 150


def test_clearing_resets_every_control(store: HistoryStore) -> None:
    view = _view(store)
    view._since.value = "2026-09-19"
    view._apply_period()
    view._distance.value = "50"
    view._apply_distance()
    view._toggle_source("USGS")

    view._clear()

    assert (view._since.value, view._until.value, view._distance.value) == ("", "", "")
    assert not any(chip.selected for chip in view._source_chips.controls)
    assert len(view.table.rows) == 3


def test_the_new_controls_are_translated(store: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(store, locale_code="es", zone=UTC_ZONE), locale_code="es")

    assert view._since.label == "Desde"
    assert view._until.label == "Hasta"
    assert view._distance.label == "Distancia máxima (km)"
    assert view.status.value == "1–3 de 3"


# --- T-160 · going to the page that holds a row (CA-114.9) ------------------------


def test_the_list_goes_to_the_page_that_holds_a_row(long_store: HistoryStore) -> None:
    listing = HistoryList(long_store)
    target = next(r for r in listing.everything(1000).records if r.source_event_id == "e-100")

    assert listing.go_to(target.id, limit=1000) is True

    assert listing.stretch == (151, 300, 400)  # e-100 is the 300th, newest first
    assert target.id in [row.record.id for row in listing.rows]


def test_going_to_a_row_that_is_not_in_the_set_changes_nothing(long_store) -> None:
    listing = HistoryList(long_store)
    listing.next_page()

    assert listing.go_to(987_654, limit=1000) is False
    assert listing.stretch == (151, 300, 400)


# --- The calendar beside each date field ------------------------------------------


class _DialogPage:
    def __init__(self) -> None:
        self.dialogs: list = []
        self.updates = 0

    def show_dialog(self, dialog) -> None:
        self.dialogs.append(dialog)

    def update(self) -> None:
        self.updates += 1


def test_each_date_field_has_a_calendar_that_is_always_in_view(store: HistoryStore) -> None:
    """`suffix` only shows while the field has focus; an icon nobody sees is no help."""
    view = _view(store)

    for field in (view._since, view._until):
        assert field.suffix_icon is not None
        assert field.suffix is None


def test_a_day_picked_on_the_calendar_becomes_the_filter(store: HistoryStore) -> None:
    view = _view(store)
    page = _DialogPage()
    view._page_of = lambda _field: page

    view._since.suffix_icon.on_click(None)
    picker = page.dialogs[-1]
    picker.value = datetime(2026, 9, 19, tzinfo=UTC)
    picker.on_change(type("Event", (), {"control": picker})())

    assert view._since.value == "2026-09-19"
    assert len(view.table.rows) == 2
    assert page.updates == 1


def test_a_calendar_with_no_page_to_open_on_does_nothing(store: HistoryStore) -> None:
    """The field still takes a typed date; the calendar is a convenience."""
    view = _view(store)

    view._since.suffix_icon.on_click(None)  # the view is not on a page in this test

    assert view._since.value in (None, "")
    assert len(view.table.rows) == 3


# --- T-162 · the switch between readings, and an earthquake's arrivals (HU-115) ---


@pytest.fixture
def twice(tmp_path: Path) -> HistoryStore:
    """One earthquake from two networks, and another from one."""
    store = HistoryStore(tmp_path / "twice.sqlite3")
    store.open()
    store.record(_record(source="EMSC", source_event_id="e1", correlation_id="q1"))
    store.record(
        _record(
            source="USGS",
            source_event_id="u1",
            correlation_id="q1",
            verdict="discarded",
            reason="duplicate",
        )
    )
    store.record(
        _record(
            source="EMSC",
            source_event_id="e2",
            correlation_id="q2",
            occurred_at=_WHEN - timedelta(hours=1),
        )
    )
    yield store
    store.close()


def test_the_list_reads_per_arrival_until_told_otherwise(twice: HistoryStore) -> None:
    listing = HistoryList(twice)

    assert listing.reading == "arrival"
    assert len(listing.rows) == 3


def test_the_list_can_be_read_per_earthquake(twice: HistoryStore) -> None:
    """CA-115.1: the rows, the total and the whole set all follow the reading."""
    listing = HistoryList(twice)

    listing.set_reading("earthquake")

    assert [row.record.correlation_id for row in listing.rows] == ["q1", "q2"]
    assert listing.stretch == (1, 2, 2)
    assert len(listing.everything(100).records) == 2


def test_switching_the_reading_returns_to_the_first_page(twice: HistoryStore) -> None:
    listing = HistoryList(twice, page_size=2)
    listing.next_page()
    assert listing.query.offset == 2

    listing.set_reading("earthquake")

    assert listing.query.offset == 0


def test_clearing_the_filters_keeps_the_reading(twice: HistoryStore) -> None:
    """The reading is how the set is looked at, not a filter on it."""
    listing = HistoryList(twice, rank=("USGS", "EMSC"))
    listing.set_reading("earthquake")
    listing.set_min_magnitude(9.0)

    listing.clear_filters()

    assert listing.reading == "earthquake"
    assert listing.query.rank == ("USGS", "EMSC")
    assert len(listing.rows) == 2


def test_the_list_words_the_arrivals_of_an_earthquake(twice: HistoryStore) -> None:
    """CA-115.5: each with its network, its verdict and its reason."""
    listing = HistoryList(twice, locale_code="en")
    listing.set_reading("earthquake")

    arrivals = listing.arrivals_of(listing.rows[0].record)

    assert [(a.source, a.verdict, a.reason) for a in arrivals] == [
        ("EMSC", "Alerted", ""),
        ("USGS", "Discarded", "Already reported by another network"),
    ]


def test_an_arrival_tied_to_nothing_is_its_own_only_arrival(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "loose.sqlite3").open()
    store.record(_record(correlation_id=""))
    listing = HistoryList(store)

    assert [a.source for a in listing.arrivals_of(listing.rows[0].record)] == ["GEOFON"]
    store.close()


def test_the_screen_has_a_switch_between_the_readings(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(twice))
    assert view.reading.value is False
    assert len(view.table.rows) == 3

    view.reading.value = True
    view.reading.on_change(None)

    assert view.listing.reading == "earthquake"
    assert len(view.table.rows) == 2
    assert view.status.value == view.listing.stretch_text

    view.reading.value = False
    view.reading.on_change(None)

    assert len(view.table.rows) == 3


def _arrival_lines(view) -> list[str]:
    return [text.value for text in view.arrivals.controls[1:]]


def test_choosing_an_earthquake_lists_its_arrivals(twice: HistoryStore) -> None:
    """CA-115.5, from the screen."""
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(twice, locale_code="en"), locale_code="en")
    view.reading.value = True
    view.reading.on_change(None)
    assert view.arrivals.visible is False

    view.choose(view.listing.rows[0].record.id)

    assert view.arrivals.visible is True
    lines = _arrival_lines(view)
    assert len(lines) == 2
    assert "EMSC" in lines[0] and "Alerted" in lines[0]
    assert "USGS" in lines[1] and "Discarded" in lines[1]
    assert "Already reported by another network" in lines[1]


def test_letting_go_of_the_earthquake_puts_its_arrivals_away(twice: HistoryStore) -> None:
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(twice))
    view.reading.value = True
    view.reading.on_change(None)
    chosen = view.listing.rows[0].record.id
    view.choose(chosen)

    view.choose(chosen)

    assert view.arrivals.visible is False


def test_per_arrival_a_chosen_row_lists_no_arrivals(twice: HistoryStore) -> None:
    """Every arrival is already a row there; the list would repeat the table."""
    from vigia_eew.notify.history_view import HistoryView

    view = HistoryView(HistoryList(twice))

    view.choose(view.listing.rows[0].record.id)

    assert view.arrivals.visible is False
