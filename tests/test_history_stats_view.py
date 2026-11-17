"""The summary on the screen (T-173, REQ-EST-001, REQ-EST-003, HU-118).

The arithmetic is `history_stats`' business and is tested there. This file is
about what reaches the screen: that every figure has beside it the number of
entries it was computed over and the period (CA-118.6), and that an empty set
is said rather than drawn as zeros (CA-118.7).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from vigia_eew.history import EventRecord
from vigia_eew.history_stats import summarise
from vigia_eew.notify.history_stats_view import (
    BAR_WIDTH,
    StatsView,
    describe,
    format_delay,
)

_DAY = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
_ZONE = "America/Caracas"


def _arrival(
    event_id: str,
    *,
    source: str = "EMSC",
    earthquake: str | None = None,
    occurred_at: datetime = _DAY,
    latency: timedelta = timedelta(minutes=40),
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
        region=None,
        distance_km=20.0,
        verdict=verdict,
        reason=reason,
    )


def _a_summary():
    first = _arrival("a1", earthquake="q1", magnitude=5.2)
    again = _arrival("a2", earthquake="q1", source="USGS", verdict="discarded", reason="duplicate")
    small = _arrival("b1", magnitude=2.4, verdict="discarded", reason="magnitude")
    far = _arrival(
        "c1",
        occurred_at=_DAY + timedelta(days=1),
        magnitude=6.3,
        verdict="discarded",
        reason="radius",
    )
    old = _arrival("g1", source="GEOFON", verdict="recovered", latency=timedelta(days=30))
    return summarise([first, small, far, old], [first, again, small, far, old], zone=_ZONE)


def _texts(control: Any) -> list[str]:
    """Every piece of text under a control, in the order it is laid out."""
    found: list[str] = []
    value = getattr(control, "value", None)
    if isinstance(value, str) and value:
        found.append(value)
    for child in getattr(control, "controls", None) or []:
        found.extend(_texts(child))
    content = getattr(control, "content", None)
    if content is not None:
        found.extend(_texts(content))
    return found


def _bars(control: Any) -> list[float]:
    """The width of every bar under a control."""
    found: list[float] = []
    if getattr(control, "data", None) == "bar":
        found.append(control.width)
    for child in getattr(control, "controls", None) or []:
        found.extend(_bars(child))
    content = getattr(control, "content", None)
    if content is not None:
        found.extend(_bars(content))
    return found


def _section(sections, title: str):
    return next(section for section in sections if section.title == title)


# --- What is said ---------------------------------------------------------------------


def test_there_is_a_section_for_each_figure_the_requirement_names() -> None:
    sections = describe(_a_summary(), locale_code="en", zone=_ZONE)

    assert [section.title for section in sections] == [
        "Earthquakes per day",
        "By magnitude",
        "By verdict",
        "Discarded, by reason",
        "Arrivals by network",
        "Delivery delay by network (median)",
    ]


def test_every_figure_has_its_sample_and_its_period_beside_it() -> None:
    sections = describe(_a_summary(), locale_code="en", zone=_ZONE)

    for section in sections:
        for line in section.lines:
            basis = line.basis or section.basis
            assert basis, f"{section.title} / {line.label} says nothing about its sample"
    assert _section(sections, "By magnitude").basis == (
        "Earthquakes counted: 4 · 2026-09-19 – 2026-09-20"
    )
    assert _section(sections, "Arrivals by network").basis == (
        "Arrivals counted: 5 · 2026-09-19 – 2026-09-20"
    )
    assert _section(sections, "Discarded, by reason").basis == (
        "Earthquakes counted: 2 · 2026-09-19 – 2026-09-20"
    )


def test_a_period_within_one_day_is_that_day() -> None:
    one = _arrival("only")

    sections = describe(summarise([one], [one], zone=_ZONE), locale_code="en", zone=_ZONE)

    assert _section(sections, "By verdict").basis == "Earthquakes counted: 1 · 2026-09-19"


def test_verdicts_and_reasons_are_worded_as_the_table_words_them() -> None:
    sections = describe(_a_summary(), locale_code="es", zone=_ZONE)

    assert {line.label for line in _section(sections, "Por veredicto").lines} == {
        "Alertado",
        "Descartado",
        "Recuperado",
    }
    assert {line.label for line in _section(sections, "Descartados, por motivo").lines} == {
        "Fuera del radio",
        "Bajo la magnitud mínima",
    }


def test_a_discard_without_a_reason_is_said_so() -> None:
    unexplained = _arrival("x", verdict="discarded")
    summary = summarise([unexplained], [unexplained], zone=_ZONE)

    section = _section(describe(summary, locale_code="en", zone=_ZONE), "Discarded, by reason")

    assert [line.label for line in section.lines] == ["No reason recorded"]


def test_with_nothing_discarded_the_reasons_are_left_out() -> None:
    alerted = _arrival("a")
    summary = summarise([alerted], [alerted], zone=_ZONE)

    titles = [section.title for section in describe(summary, locale_code="en", zone=_ZONE)]

    assert "Discarded, by reason" not in titles


def test_a_bar_is_as_long_as_its_share_of_the_largest() -> None:
    section = _section(describe(_a_summary(), locale_code="en", zone=_ZONE), "Earthquakes per day")

    assert [(line.label, line.value, line.fraction) for line in section.lines] == [
        ("2026-09-19", "3", 1.0),
        ("2026-09-20", "1", 1 / 3),
    ]


# --- The latency ----------------------------------------------------------------------


def test_each_network_shows_its_delay_with_its_own_sample() -> None:
    section = _section(
        describe(_a_summary(), locale_code="en", zone=_ZONE), "Delivery delay by network (median)"
    )

    by_source = {line.label: line for line in section.lines}
    assert by_source["EMSC"].value == "40 min"
    assert by_source["EMSC"].basis == "Live arrivals: 3 · 2026-09-19 – 2026-09-20"
    assert by_source["USGS"].basis == "Live arrivals: 1 · 2026-09-19"


def test_a_network_with_no_live_arrivals_shows_no_figure_not_zero() -> None:
    section = _section(
        describe(_a_summary(), locale_code="en", zone=_ZONE), "Delivery delay by network (median)"
    )

    geofon = next(line for line in section.lines if line.label == "GEOFON")
    assert geofon.value == "No figure"
    assert "0" not in geofon.value
    assert geofon.basis == "No live arrivals"
    assert geofon.fraction is None


def test_a_delay_is_said_in_the_unit_that_fits_it() -> None:
    assert format_delay(45) == "45 s"
    assert format_delay(40 * 60) == "40 min"
    assert format_delay(4.9 * 3600) == "4.9 h"
    assert format_delay(10 * 86400) == "10.0 d"
    assert format_delay(-3) == "-3 s"


# --- CA-118.7 · An empty set is said, not computed -------------------------------------


def test_an_empty_summary_has_no_sections() -> None:
    assert describe(summarise([], [], zone=_ZONE), locale_code="en", zone=_ZONE) == []


def test_an_empty_set_says_there_is_no_data_and_shows_no_figure() -> None:
    view = StatsView(locale_code="en", zone=_ZONE)

    view.show(summarise([], [], zone=_ZONE))

    assert _texts(view.view) == ["No data for this filter."]
    assert _bars(view.view) == []


# --- The controls ----------------------------------------------------------------------


def test_what_was_described_is_what_is_drawn() -> None:
    view = StatsView(locale_code="en", zone=_ZONE)

    view.show(_a_summary())

    shown = _texts(view.view)
    for section in view.sections:
        assert section.title in shown
        if section.basis:
            assert section.basis in shown
        for line in section.lines:
            assert line.label in shown
            assert line.value in shown
            if line.basis:
                assert line.basis in shown


def test_bars_are_containers_whose_width_follows_the_value() -> None:
    view = StatsView(locale_code="en", zone=_ZONE)

    view.show(_a_summary())

    widths = _bars(view.view)
    assert widths, "no bar was drawn"
    assert max(widths) == BAR_WIDTH
    assert all(0 < width <= BAR_WIDTH for width in widths)


def test_showing_another_summary_replaces_the_first() -> None:
    view = StatsView(locale_code="en", zone=_ZONE)
    view.show(_a_summary())

    view.show(summarise([], [], zone=_ZONE))

    assert view.sections == []
    assert _texts(view.view) == ["No data for this filter."]
