"""The figures of a period (T-172, REQ-EST-001..003, HU-118, ADR-038).

Two bases, and each figure names its own (X-8): what is said about earthquakes
counts earthquakes, what is said about networks counts arrivals. The first
criterion is deliberately an arithmetic identity -- every split adds up to the
count of what it counts -- because that is what catches a split that counts
twice or drops a category.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta

from vigia_eew import history_stats
from vigia_eew.history import EventRecord
from vigia_eew.history_stats import band_of, summarise

_DAY = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
_ZONE = "America/Caracas"


def _arrival(
    event_id: str,
    *,
    source: str = "EMSC",
    earthquake: str | None = None,
    occurred_at: datetime = _DAY,
    latency: timedelta = timedelta(minutes=5),
    magnitude: float = 4.5,
    verdict: str = "alerted",
    reason: str | None = None,
) -> EventRecord:
    return EventRecord(
        correlation_id=earthquake or f"tr-{event_id}",
        source=source,
        source_event_id=event_id,
        occurred_at=occurred_at,
        recorded_at=occurred_at + latency,
        latitude=10.6,
        longitude=-66.9,
        depth_km=12.0,
        magnitude=magnitude,
        region="NEAR THE COAST OF VENEZUELA",
        distance_km=20.0,
        verdict=verdict,
        reason=reason,
    )


def _total(split) -> int:
    return sum(bar.count for bar in split.bars)


def _a_period() -> tuple[list[EventRecord], list[EventRecord]]:
    """Three earthquakes over two days; the first came by two networks."""
    first = _arrival("a1", earthquake="q1", magnitude=5.2)
    again = _arrival(
        "a2", earthquake="q1", source="USGS", magnitude=5.1, verdict="discarded", reason="duplicate"
    )
    small = _arrival("b1", magnitude=2.4, verdict="discarded", reason="magnitude")
    far = _arrival(
        "c1",
        source="GEOFON",
        occurred_at=_DAY + timedelta(days=1),
        magnitude=6.3,
        verdict="discarded",
        reason="radius",
    )
    return [first, small, far], [first, again, small, far]


# --- CA-118.1 · Every split adds up -------------------------------------------------


def test_the_splits_about_earthquakes_add_up_to_the_earthquakes() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    assert summary.earthquakes == 3
    for split in (summary.per_day, summary.by_magnitude, summary.by_verdict):
        assert _total(split) == 3
        assert split.sample == 3
        assert split.base == "earthquake"


def test_the_split_by_network_adds_up_to_the_arrivals() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    assert summary.arrivals == 4
    assert _total(summary.by_source) == 4
    assert summary.by_source.sample == 4
    assert summary.by_source.base == "arrival"
    assert {bar.key: bar.count for bar in summary.by_source.bars} == {
        "EMSC": 2,
        "USGS": 1,
        "GEOFON": 1,
    }


def test_the_reasons_add_up_to_the_discarded_earthquakes() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    discarded = {bar.key: bar.count for bar in summary.by_verdict.bars}["discarded"]
    assert discarded == 2
    assert _total(summary.by_reason) == discarded
    assert summary.by_reason.sample == discarded
    assert {bar.key for bar in summary.by_reason.bars} == {"magnitude", "radius"}


def test_a_discard_with_no_reason_is_still_counted_among_the_reasons() -> None:
    unexplained = _arrival("x", verdict="discarded", reason=None)

    summary = summarise([unexplained], [unexplained], zone=_ZONE)

    assert _total(summary.by_reason) == 1


# --- CA-118.2 · A day counts earthquakes --------------------------------------------


def test_an_earthquake_from_two_networks_counts_once_on_its_day() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    assert [(bar.key, bar.count) for bar in summary.per_day.bars] == [
        ("2026-09-19", 2),
        ("2026-09-20", 1),
    ]


def test_a_day_is_the_users_day_not_the_utc_one() -> None:
    # 02:00 UTC on the 20th is still the evening of the 19th in Caracas.
    late = _arrival("late", occurred_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC))

    summary = summarise([late], [late], zone=_ZONE)

    assert [bar.key for bar in summary.per_day.bars] == ["2026-09-19"]


def test_a_zone_nobody_knows_falls_back_to_utc_days() -> None:
    late = _arrival("late", occurred_at=datetime(2026, 9, 20, 2, 0, tzinfo=UTC))

    summary = summarise([late], [late], zone="Nowhere/At_All")

    assert [bar.key for bar in summary.per_day.bars] == ["2026-09-20"]


# --- The magnitude bands -------------------------------------------------------------


def test_a_band_holds_its_lower_edge_and_not_its_upper_one() -> None:
    assert band_of(1.9) == "M<2"
    assert band_of(2.0) == "M2"
    assert band_of(2.99) == "M2"
    assert band_of(6.3) == "M6"
    assert band_of(7.0) == "M7+"
    assert band_of(9.1) == "M7+"


def test_the_bands_go_from_the_smallest_to_the_largest() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    assert [(bar.key, bar.count) for bar in summary.by_magnitude.bars] == [
        ("M2", 1),
        ("M5", 1),
        ("M6", 1),
    ]


# --- CA-118.3, CA-118.4, CA-118.5 · Latency ------------------------------------------


def _latency(summary, source: str):
    return next(figure for figure in summary.latency if figure.source == source)


def test_latency_is_the_median_delay_of_a_networks_live_arrivals() -> None:
    arrivals = [
        _arrival(f"e{minutes}", latency=timedelta(minutes=minutes)) for minutes in (10, 20, 60)
    ]

    summary = summarise(arrivals, arrivals, zone=_ZONE)

    figure = _latency(summary, "EMSC")
    assert figure.median_s == 20 * 60
    assert figure.sample == 3


def test_recovered_entries_do_not_move_a_latency() -> None:
    live = [_arrival(f"e{minutes}", latency=timedelta(minutes=minutes)) for minutes in (10, 20)]
    recovered = [
        _arrival(f"r{days}", latency=timedelta(days=days), verdict="recovered") for days in (30, 60)
    ]

    without = _latency(summarise(live, live, zone=_ZONE), "EMSC")
    with_them = _latency(summarise(live + recovered, live + recovered, zone=_ZONE), "EMSC")

    assert with_them.median_s == without.median_s
    assert with_them.sample == without.sample == 2


def test_a_network_with_only_recovered_entries_has_no_figure_rather_than_zero() -> None:
    recovered = [_arrival("r1", source="GEOFON", latency=timedelta(days=30), verdict="recovered")]

    figure = _latency(summarise(recovered, recovered, zone=_ZONE), "GEOFON")

    assert figure.median_s is None
    assert figure.sample == 0
    assert figure.period is None


def test_one_arrival_ten_days_late_leaves_the_figure_within_the_hour() -> None:
    arrivals = [_arrival(f"e{n}", latency=timedelta(minutes=5 * n)) for n in range(1, 10)]
    arrivals.append(_arrival("late", latency=timedelta(days=10)))

    figure = _latency(summarise(arrivals, arrivals, zone=_ZONE), "EMSC")

    assert figure.median_s is not None
    assert figure.median_s < 3600
    assert figure.sample == 10


def test_each_network_has_its_own_latency() -> None:
    arrivals = [
        _arrival("e1", source="EMSC", latency=timedelta(minutes=40)),
        _arrival("u1", source="USGS", latency=timedelta(hours=5)),
    ]

    summary = summarise(arrivals, arrivals, zone=_ZONE)

    assert _latency(summary, "EMSC").median_s == 40 * 60
    assert _latency(summary, "USGS").median_s == 5 * 3600
    assert [figure.source for figure in summary.latency] == ["EMSC", "USGS"]


# --- REQ-EST-003 · Every figure says what it was computed over ----------------------


def test_every_split_carries_its_sample_and_the_period_it_spans() -> None:
    earthquakes, arrivals = _a_period()

    summary = summarise(earthquakes, arrivals, zone=_ZONE)

    span = (_DAY, _DAY + timedelta(days=1))
    assert summary.period == span
    for split in (summary.per_day, summary.by_magnitude, summary.by_verdict, summary.by_source):
        assert split.period == span
    # Both discards of this period fall one on each day.
    assert summary.by_reason.period == span


def test_a_latency_spans_the_live_arrivals_it_was_computed_over() -> None:
    arrivals = [
        _arrival("e1", occurred_at=_DAY),
        _arrival("e2", occurred_at=_DAY + timedelta(days=3)),
        _arrival("r1", occurred_at=_DAY - timedelta(days=40), verdict="recovered"),
    ]

    figure = _latency(summarise(arrivals, arrivals, zone=_ZONE), "EMSC")

    assert figure.period == (_DAY, _DAY + timedelta(days=3))


# --- CA-118.7 · An empty set is said, not computed ----------------------------------


def test_an_empty_input_gives_an_empty_summary_not_zeros() -> None:
    summary = summarise([], [], zone=_ZONE)

    assert summary.empty
    assert summary.period is None
    assert summary.latency == ()
    for split in (
        summary.per_day,
        summary.by_magnitude,
        summary.by_verdict,
        summary.by_reason,
        summary.by_source,
    ):
        assert split.bars == ()
        assert split.period is None


def test_a_summary_with_something_in_it_is_not_empty() -> None:
    earthquakes, arrivals = _a_period()

    assert not summarise(earthquakes, arrivals, zone=_ZONE).empty


def test_with_nothing_discarded_there_are_no_reasons_to_show() -> None:
    alerted = _arrival("a")

    summary = summarise([alerted], [alerted], zone=_ZONE)

    assert summary.by_reason.bars == ()
    assert summary.by_reason.sample == 0


# --- The module is pure -------------------------------------------------------------


def test_the_figures_import_no_toolkit_no_network_and_no_database() -> None:
    with open(history_stats.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for forbidden in ("flet", "flet_map", "httpx", "websockets", "socket", "urllib", "sqlite3"):
        assert not any(name == forbidden or name.startswith(forbidden + ".") for name in imported)
