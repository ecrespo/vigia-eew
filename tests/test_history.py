"""Tests for the event history store (T-142/T-144, REQ-HIS-003/004, HU-111).

Every assertion runs against a **real SQLite file**. Migrations fail in the
details of the engine, not in the logic that calls them, so a fake connection
would prove nothing about the one thing this module has to get right: opening
somebody's existing history without losing a row of it.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vigia_eew.history import (
    SCHEMA_VERSION,
    EventRecord,
    HistoryQuery,
    HistoryStore,
    HistoryTooNew,
)

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
    yield store
    store.close()


# --- The schema -----------------------------------------------------------------


def test_opening_creates_the_table_and_stamps_the_version(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite3"
    HistoryStore(path).open().close()

    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "events" in tables


def test_the_five_indexes_the_queries_need_exist(tmp_path: Path) -> None:
    """DATA-MODEL §3bis.2: each one answers a filter of REQ-HIS-005.

    Listed by name rather than counted, so dropping the one that serves the
    date range -- the main query -- is a failure and not a smaller number.
    """
    path = tmp_path / "history.sqlite3"
    HistoryStore(path).open().close()

    with sqlite3.connect(path) as db:
        declared = db.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in declared}
    assert {
        "events_occurred_at",
        "events_magnitude",
        "events_verdict",
        "events_correlation_id",
        "events_location",
    } <= indexes


def test_opening_an_existing_history_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite3"
    first = HistoryStore(path)
    first.open()
    first.record(_record())
    first.close()

    second = HistoryStore(path)
    second.open()
    assert second.count() == 1
    second.close()


# --- CA-111.6 · Migration ---------------------------------------------------------


def _add_a_column(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE events ADD COLUMN felt INTEGER")


def test_a_history_of_an_older_schema_migrates_without_losing_rows(tmp_path: Path) -> None:
    """The rows are somebody's history. A migration that drops them is a bug."""
    path = tmp_path / "history.sqlite3"
    old = HistoryStore(path)
    old.open()
    old.record(_record())
    old.record(_record(source="EMSC", source_event_id="emsc-1"))
    old.close()

    migrated = HistoryStore(path, migrations=(*HistoryStore.MIGRATIONS, _add_a_column))
    migrated.open()

    assert migrated.count() == 2
    assert migrated.schema_version == SCHEMA_VERSION + 1
    migrated.close()


def test_a_failed_migration_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    """Applied in a transaction: half a migration is worse than none."""

    def explodes(db: sqlite3.Connection) -> None:
        db.execute("ALTER TABLE events ADD COLUMN felt INTEGER")
        raise sqlite3.OperationalError("interrupted")

    path = tmp_path / "history.sqlite3"
    first = HistoryStore(path)
    first.open()
    first.record(_record())
    first.close()

    broken = HistoryStore(path, migrations=(*HistoryStore.MIGRATIONS, explodes))
    with pytest.raises(sqlite3.OperationalError):
        broken.open()
    broken.close()

    intact = HistoryStore(path)
    intact.open()
    assert intact.schema_version == SCHEMA_VERSION
    assert intact.count() == 1
    intact.close()


def test_a_history_from_a_newer_version_is_not_touched(tmp_path: Path) -> None:
    """Downgrading somebody's file silently is worse than refusing to open it."""
    path = tmp_path / "history.sqlite3"
    HistoryStore(path).open().close()
    with sqlite3.connect(path) as db:
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")

    with pytest.raises(HistoryTooNew) as failure:
        HistoryStore(path).open()

    assert str(SCHEMA_VERSION + 5) in str(failure.value)
    assert str(SCHEMA_VERSION) in str(failure.value)


# --- Recording -------------------------------------------------------------------


def test_a_record_comes_back_as_it_went_in(store: HistoryStore) -> None:
    store.record(_record())

    row = store.rows()[0]
    assert row.source == "GEOFON"
    assert row.magnitude == 5.2
    assert row.verdict == "alerted"
    assert row.occurred_at == _WHEN


def test_timestamps_are_stored_as_iso_8601_in_utc(tmp_path: Path) -> None:
    """DATA-MODEL §3bis.1: in ISO-8601 with Z, lexical order *is* chronological.

    That is what lets the date-range queries and the index work without a
    conversion, and it keeps Art. 4 with no exception.
    """
    path = tmp_path / "history.sqlite3"
    store = HistoryStore(path)
    store.open()
    store.record(_record())
    store.close()

    with sqlite3.connect(path) as db:
        stored = db.execute("SELECT occurred_at FROM events").fetchone()[0]
    assert stored == "2026-09-19T12:00:00+00:00"


def test_a_discarded_event_keeps_the_reason_it_was_discarded(store: HistoryStore) -> None:
    """REQ-HIS-001: the question worth answering is why you were *not* warned."""
    store.record(_record(verdict="discarded", reason="radius", severity=None))

    row = store.rows()[0]
    assert row.verdict == "discarded"
    assert row.reason == "radius"


def test_the_same_arrival_twice_replaces_its_row(store: HistoryStore) -> None:
    """A revision from one network is the same arrival, not a second one."""
    store.record(_record(magnitude=5.2))
    store.record(_record(magnitude=5.4))

    assert store.count() == 1
    assert store.rows()[0].magnitude == 5.4


def test_the_same_id_from_another_network_is_a_separate_row(store: HistoryStore) -> None:
    """One row per **arrival**: two networks reporting one earthquake make two."""
    store.record(_record(source="GEOFON", source_event_id="shared"))
    store.record(_record(source="EMSC", source_event_id="shared"))

    assert store.count() == 2


# --- CA-111.3 · A duplicate is linked, not lost -----------------------------------


def test_a_duplicate_is_linked_to_the_row_that_alerted(store: HistoryStore) -> None:
    alerted = store.record(_record(correlation_id="tr-1", verdict="alerted"))

    duplicate = store.record(
        _record(
            correlation_id="tr-1",
            source="FUNVISIS",
            source_event_id="fun-1",
            verdict="discarded",
            reason="duplicate",
            severity=None,
        )
    )

    row = next(r for r in store.rows() if r.id == duplicate)
    assert row.superseded_by == alerted


def test_a_duplicate_with_nothing_to_link_to_is_still_recorded(store: HistoryStore) -> None:
    """State written before v1.0 carries no correlation id, and losing the row
    to that would trade the whole record for the link."""
    recorded = store.record(
        _record(correlation_id="", verdict="discarded", reason="duplicate", severity=None)
    )

    row = next(r for r in store.rows() if r.id == recorded)
    assert row.superseded_by is None


def test_a_discard_that_is_not_a_duplicate_links_to_nothing(store: HistoryStore) -> None:
    store.record(_record(verdict="alerted"))
    out_of_radius = store.record(
        _record(
            source="EMSC",
            source_event_id="emsc-1",
            verdict="discarded",
            reason="radius",
            severity=None,
        )
    )

    row = next(r for r in store.rows() if r.id == out_of_radius)
    assert row.superseded_by is None


# --- CA-111.7 · Retention (T-144) --------------------------------------------------


def test_pruning_removes_what_is_older_than_the_retention(store: HistoryStore) -> None:
    store.record(_record(source_event_id="old", occurred_at=_WHEN - timedelta(days=3)))
    store.record(_record(source_event_id="recent", occurred_at=_WHEN - timedelta(hours=2)))

    removed = store.prune(retention_days=1, now=_WHEN)

    assert removed == 1
    assert [row.source_event_id for row in store.rows()] == ["recent"]


def test_pruning_an_empty_history_removes_nothing(store: HistoryStore) -> None:
    assert store.prune(retention_days=1, now=_WHEN) == 0


def test_a_retention_of_zero_days_keeps_nothing_older_than_now(store: HistoryStore) -> None:
    store.record(_record(occurred_at=_WHEN - timedelta(seconds=1)))

    assert store.prune(retention_days=0, now=_WHEN) == 1


def test_opening_prunes_to_the_configured_retention(tmp_path: Path) -> None:
    """Pruning happens where the file is opened, not on a timer of its own.

    A periodic task would have nothing to do most of the time and would have
    to be supervised, restarted and shut down. The history only grows while
    the agent runs, so bounding it at each start is equivalent and far less
    machinery -- the same argument `state.py` settled for prune-on-register.
    """
    path = tmp_path / "history.sqlite3"
    seeded = HistoryStore(path)
    seeded.open()
    seeded.record(_record(occurred_at=_WHEN - timedelta(days=400)))
    seeded.record(_record(source_event_id="fresh", occurred_at=_WHEN))
    seeded.close()

    reopened = HistoryStore(path, retention_days=90, now=lambda: _WHEN)
    reopened.open()

    assert [row.source_event_id for row in reopened.rows()] == ["fresh"]
    reopened.close()


def test_retention_can_be_switched_off_by_configuration(tmp_path: Path) -> None:
    """Somebody who wants the whole record should be able to keep it."""
    path = tmp_path / "history.sqlite3"
    seeded = HistoryStore(path)
    seeded.open()
    seeded.record(_record(occurred_at=_WHEN - timedelta(days=4000)))
    seeded.close()

    reopened = HistoryStore(path, retention_days=0, now=lambda: _WHEN, prune_on_open=False)
    reopened.open()

    assert reopened.count() == 1
    reopened.close()


# --- REQ-HIS-006 · It does not leave the machine ------------------------------------


def test_the_store_opens_nothing_but_a_local_file(tmp_path: Path) -> None:
    """The store's only dependency is `sqlite3`; there is no client to point elsewhere."""
    import vigia_eew.history as history_module

    source = Path(history_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("http", "socket", "requests", "httpx", "urllib"):
        assert forbidden not in source, f"the history store mentions {forbidden}"


# --- CA-111.8 · Querying by the criteria that matter (T-145) ----------------------


def _populate(store: HistoryStore) -> None:
    """A history with spread across every axis the query offers."""
    store.record(
        _record(
            source="EMSC",
            source_event_id="emsc-old-big",
            occurred_at=_WHEN - timedelta(days=10),
            magnitude=6.1,
            distance_km=40.0,
            verdict="alerted",
        )
    )
    store.record(
        _record(
            source="USGS",
            source_event_id="usgs-recent-small",
            occurred_at=_WHEN - timedelta(hours=2),
            magnitude=2.7,
            distance_km=90.0,
            verdict="discarded",
            reason="magnitude",
            severity=None,
        )
    )
    store.record(
        _record(
            source="GEOFON",
            source_event_id="gfz-recent-big",
            occurred_at=_WHEN - timedelta(hours=1),
            magnitude=5.4,
            distance_km=250.0,
            verdict="alerted",
        )
    )
    store.record(
        _record(
            source="FUNVISIS",
            source_event_id="fun-recent-mid",
            occurred_at=_WHEN - timedelta(minutes=30),
            magnitude=4.2,
            distance_km=15.0,
            verdict="discarded",
            reason="radius",
            severity=None,
        )
    )


def test_a_query_by_magnitude_and_dates_returns_exactly_both(store: HistoryStore) -> None:
    """CA-111.8, word for word: *both* criteria, not either."""
    _populate(store)

    found = store.query(
        HistoryQuery(since=_WHEN - timedelta(days=1), min_magnitude=4.0),
    )

    assert {row.source_event_id for row in found} == {"gfz-recent-big", "fun-recent-mid"}


def test_an_empty_query_returns_everything(store: HistoryStore) -> None:
    _populate(store)

    assert len(store.query(HistoryQuery())) == 4


def test_the_upper_bound_of_the_range_is_inclusive(store: HistoryStore) -> None:
    _populate(store)

    found = store.query(HistoryQuery(until=_WHEN - timedelta(days=10)))

    assert [row.source_event_id for row in found] == ["emsc-old-big"]


def test_a_query_by_distance_keeps_what_is_near(store: HistoryStore) -> None:
    _populate(store)

    found = store.query(HistoryQuery(max_distance_km=50.0))

    assert {row.source_event_id for row in found} == {"emsc-old-big", "fun-recent-mid"}


def test_a_query_by_verdict_separates_the_two_groups(store: HistoryStore) -> None:
    _populate(store)

    assert len(store.query(HistoryQuery(verdict="alerted"))) == 2
    assert len(store.query(HistoryQuery(verdict="discarded"))) == 2


def test_a_query_by_network_takes_several(store: HistoryStore) -> None:
    _populate(store)

    found = store.query(HistoryQuery(sources=("EMSC", "GEOFON")))

    assert {row.source for row in found} == {"EMSC", "GEOFON"}


def test_a_network_whose_name_contains_another_is_not_matched_by_accident(
    store: HistoryStore,
) -> None:
    """The source filter is a membership test, not a substring search."""
    store.record(_record(source="EMSC", source_event_id="e-1"))

    assert store.query(HistoryQuery(sources=("MSC",))) == []


def test_results_can_be_ordered_by_any_of_the_criteria(store: HistoryStore) -> None:
    """CA-111.8's second half: ordered by any of those fields."""
    _populate(store)

    by_magnitude = store.query(HistoryQuery(order_by="magnitude", descending=True))
    assert [row.magnitude for row in by_magnitude] == [6.1, 5.4, 4.2, 2.7]

    by_distance = store.query(HistoryQuery(order_by="distance_km", descending=False))
    assert [row.distance_km for row in by_distance] == [15.0, 40.0, 90.0, 250.0]


def test_the_default_order_is_the_most_recent_first(store: HistoryStore) -> None:
    """What somebody opening a history wants to see is what just happened."""
    _populate(store)

    assert store.query(HistoryQuery())[0].source_event_id == "fun-recent-mid"


def test_an_order_the_schema_does_not_offer_is_refused(store: HistoryStore) -> None:
    """The ordering is the one part of the query that cannot be a bound value.

    So it is a lookup into a table of statements built from constants, and a
    key that is not in it fails here rather than reaching SQLite.
    """
    with pytest.raises(ValueError, match="rowid"):
        store.query(HistoryQuery(order_by="rowid; DROP TABLE events"))


def test_results_are_paginated(store: HistoryStore) -> None:
    _populate(store)

    first = store.query(HistoryQuery(limit=2))
    second = store.query(HistoryQuery(limit=2, offset=2))

    assert len(first) == len(second) == 2
    assert {row.id for row in first}.isdisjoint({row.id for row in second})


def test_the_matching_rows_can_be_counted_without_fetching_them(store: HistoryStore) -> None:
    """A page of fifty out of nine hundred still has to be able to say "of 900"."""
    _populate(store)

    assert store.count(HistoryQuery(min_magnitude=4.0)) == 3
    assert len(store.query(HistoryQuery(min_magnitude=4.0, limit=1))) == 1


def test_the_networks_present_in_the_history_can_be_listed(store: HistoryStore) -> None:
    """The filter offers what is actually there, not the four it hopes for."""
    _populate(store)

    assert store.sources() == ["EMSC", "FUNVISIS", "GEOFON", "USGS"]
