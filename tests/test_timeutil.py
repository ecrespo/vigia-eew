"""Tests for the local-day bounds of the history's date filter (REQ-HIS-007, ADR-032).

The user thinks in calendar days where they live; the history stores instants
in UTC. The conversion lives beside the other local-day boundary (RF-40), so
that "a day" means one thing everywhere.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from vigia_eew.timeutil import local_day_bounds

CARACAS = "America/Caracas"  # UTC-4, no daylight saving


def test_a_local_day_starts_at_local_midnight() -> None:
    since, _ = local_day_bounds(date(2026, 9, 19), None, CARACAS)

    assert since == datetime(2026, 9, 19, 4, 0, tzinfo=UTC)


def test_a_local_day_ends_just_before_the_next_local_midnight() -> None:
    _, until = local_day_bounds(None, date(2026, 9, 19), CARACAS)

    assert until == datetime(2026, 9, 20, 4, 0, tzinfo=UTC) - timedelta(microseconds=1)


def test_one_day_spans_twenty_four_hours() -> None:
    since, until = local_day_bounds(date(2026, 9, 19), date(2026, 9, 19), CARACAS)

    assert since is not None and until is not None
    assert until - since == timedelta(days=1) - timedelta(microseconds=1)


def test_an_open_side_stays_open() -> None:
    assert local_day_bounds(None, None, CARACAS) == (None, None)
    assert local_day_bounds(date(2026, 9, 19), None, CARACAS)[1] is None


def test_a_range_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(ValueError, match="before"):
        local_day_bounds(date(2026, 9, 20), date(2026, 9, 19), CARACAS)


def test_an_unknown_zone_falls_back_to_utc_days() -> None:
    """Fail-safe like the rest of this module: a filter in UTC beats no filter."""
    since, until = local_day_bounds(date(2026, 9, 19), date(2026, 9, 19), "Not/AZone")

    assert since == datetime(2026, 9, 19, tzinfo=UTC)
    assert until == datetime(2026, 9, 20, tzinfo=UTC) - timedelta(microseconds=1)
