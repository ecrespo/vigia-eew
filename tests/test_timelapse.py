"""Tests for the playback's timeline (T-164, REQ-TLP-001/002/005/007, ADR-035, HU-116).

Everything the playback promises about order, seeking, speed and fading is
decided by a pure function, and so it is checked here with no screen and no
clock. The control that paints a frame has its own file.
"""

from __future__ import annotations

import ast
import random
from datetime import UTC, datetime, timedelta

import pytest

from vigia_eew.history import EventRecord
from vigia_eew.notify import timelapse
from vigia_eew.notify.timelapse import (
    LEVELS,
    MAX_DWELL,
    MIN_DWELL,
    PLAYBACK_SYMBOL_LIMIT,
    SPEEDS,
    Timeline,
)

_START = datetime(2026, 9, 1, tzinfo=UTC)
_FADE = timedelta(days=2)


def _quake(index: int, after: timedelta) -> EventRecord:
    return EventRecord(
        id=index,
        correlation_id=f"q{index}",
        source="EMSC",
        source_event_id=f"e{index}",
        occurred_at=_START + after,
        recorded_at=_START + after,
        latitude=10.0,
        longitude=-66.0,
        depth_km=10.0,
        magnitude=4.0,
        region=None,
        distance_km=50.0,
        verdict="discarded",
    )


def _generated(seed: int, count: int = 60) -> list[EventRecord]:
    """A set with bursts, long silences and ties, in no particular order."""
    rng = random.Random(seed)
    moment = timedelta()
    quakes = []
    for index in range(count):
        moment += rng.choice(
            [timedelta(), timedelta(seconds=1), timedelta(hours=3), timedelta(days=4)]
        )
        quakes.append(_quake(index + 1, moment))
    rng.shuffle(quakes)
    return quakes


def _strengths(timeline: Timeline, step: int) -> dict[int, float]:
    return {record.id: strength for record, strength in timeline.frame(step).symbols}


# --- Steps ------------------------------------------------------------------------


def test_the_steps_are_the_earthquakes_in_the_order_they_happened() -> None:
    quakes = [_quake(1, timedelta(days=3)), _quake(2, timedelta(days=1)), _quake(3, timedelta())]

    timeline = Timeline(quakes, fade=_FADE)

    assert len(timeline) == 3
    assert [timeline.frame(i).instant for i in range(3)] == [
        _START,
        _START + timedelta(days=1),
        _START + timedelta(days=3),
    ]


def test_earthquakes_at_the_same_instant_share_a_step() -> None:
    quakes = [_quake(1, timedelta()), _quake(2, timedelta()), _quake(3, timedelta(hours=1))]

    timeline = Timeline(quakes, fade=_FADE)

    assert len(timeline) == 2
    assert set(_strengths(timeline, 0)) == {1, 2}


def test_an_empty_set_has_no_steps_and_no_period() -> None:
    timeline = Timeline([], fade=_FADE)

    assert len(timeline) == 0
    assert timeline.period is None
    with pytest.raises(IndexError):
        timeline.frame(0)


def test_the_period_runs_from_the_first_earthquake_to_the_last() -> None:
    timeline = Timeline([_quake(1, timedelta(days=2)), _quake(2, timedelta())], fade=_FADE)

    assert timeline.period == (_START, _START + timedelta(days=2))


def test_a_step_outside_the_timeline_is_refused() -> None:
    timeline = Timeline([_quake(1, timedelta())], fade=_FADE)

    for step in (-1, 1):
        with pytest.raises(IndexError):
            timeline.frame(step)


# --- The three invariants of 03 §6, over generated sets -----------------------------


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("trail", [False, True])
def test_nothing_appears_before_it_happened(seed: int, trail: bool) -> None:
    """CA-116.1."""
    timeline = Timeline(_generated(seed), fade=_FADE, trail=trail)

    for step in range(len(timeline)):
        frame = timeline.frame(step)
        assert all(record.occurred_at <= frame.instant for record, _ in frame.symbols)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("trail", [False, True])
def test_a_symbol_is_strongest_at_its_own_step_and_never_grows(seed: int, trail: bool) -> None:
    """CA-116.9."""
    quakes = _generated(seed)
    timeline = Timeline(quakes, fade=_FADE, trail=trail)
    last: dict[int, float] = {}

    for step in range(len(timeline)):
        frame = timeline.frame(step)
        now = _strengths(timeline, step)
        for record in quakes:
            if record.occurred_at == frame.instant:
                assert now[record.id] == 1.0
            if record.id in last:
                assert now.get(record.id, 0.0) <= last[record.id]
        last = now


@pytest.mark.parametrize("seed", range(4))
def test_a_frame_depends_only_on_its_step(seed: int) -> None:
    """CA-116.4 and CA-116.5: however it was reached, at whatever speed."""
    quakes = _generated(seed)
    played = Timeline(quakes, fade=_FADE)
    sought = Timeline(list(reversed(quakes)), fade=_FADE)
    reached_by_playing = []
    for step in range(len(played)):
        for speed in SPEEDS.values():
            played.dwell(step, speed)  # asking how long changes nothing
        reached_by_playing.append(played.frame(step))

    for step in random.Random(seed).sample(range(len(sought)), k=len(sought)):
        assert sought.frame(step) == reached_by_playing[step]


# --- Fading (REQ-TLP-005) -----------------------------------------------------------


def test_intensity_comes_in_a_few_levels_from_one_down() -> None:
    assert LEVELS[0] == 1.0
    assert list(LEVELS) == sorted(LEVELS, reverse=True)
    assert 2 <= len(LEVELS) <= 6
    assert all(0.0 < level <= 1.0 for level in LEVELS)


def test_a_symbol_is_gone_once_the_interval_has_passed() -> None:
    quakes = [_quake(1, timedelta()), _quake(2, _FADE - timedelta(seconds=1)), _quake(3, _FADE)]

    timeline = Timeline(quakes, fade=_FADE)

    assert _strengths(timeline, 1)[1] == LEVELS[-1]  # just inside: at its weakest
    assert 1 not in _strengths(timeline, 2)  # at the interval: gone


def test_with_the_trail_on_it_stays_at_its_weakest() -> None:
    quakes = [_quake(1, timedelta()), _quake(2, _FADE * 10)]

    timeline = Timeline(quakes, fade=_FADE, trail=True)

    assert _strengths(timeline, 1) == {1: LEVELS[-1], 2: 1.0}


def test_only_the_levels_are_ever_used() -> None:
    timeline = Timeline(_generated(3), fade=_FADE, trail=True)

    used = {s for step in range(len(timeline)) for s in _strengths(timeline, step).values()}

    assert used <= set(LEVELS)


# --- How long a step stays (REQ-TLP-007, CA-116.6) ----------------------------------


def test_the_limits_come_from_the_spike_and_fit_in_a_minute() -> None:
    """10-SPIKE-TIMELAPSE §5: thirty days in under a minute needs this product."""
    assert 0 < MIN_DWELL < MAX_DWELL
    assert PLAYBACK_SYMBOL_LIMIT * MIN_DWELL <= 60.0


def test_a_step_is_never_too_short_nor_too_long() -> None:
    quakes = [
        _quake(1, timedelta()),
        _quake(2, timedelta(seconds=1)),
        _quake(3, timedelta(seconds=1) + timedelta(weeks=1)),
    ]
    timeline = Timeline(quakes, fade=_FADE)

    for speed in SPEEDS.values():
        for step in range(len(timeline)):
            assert MIN_DWELL <= timeline.dwell(step, speed) <= MAX_DWELL
    slowest = min(SPEEDS.values())
    assert timeline.dwell(0, slowest) == MIN_DWELL  # a second apart
    assert timeline.dwell(1, slowest) == MAX_DWELL  # a week apart


def test_between_the_limits_a_step_stays_in_proportion_to_the_real_gap() -> None:
    day = SPEEDS["day"]  # a day of history per second of viewing
    quakes = [_quake(1, timedelta()), _quake(2, timedelta(hours=12)), _quake(3, timedelta(days=1))]
    timeline = Timeline(quakes, fade=_FADE)

    assert timeline.dwell(0, day) == pytest.approx(0.5)
    assert timeline.dwell(0, day * 2) == pytest.approx(0.25)


def test_the_last_step_stays_the_longest() -> None:
    timeline = Timeline([_quake(1, timedelta()), _quake(2, timedelta(hours=1))], fade=_FADE)

    assert timeline.dwell(1, SPEEDS["day"]) == MAX_DWELL


def test_the_speeds_are_history_time_per_second_of_viewing() -> None:
    """ADR-035 §4: six hours, a day, a week."""
    assert list(SPEEDS.values()) == [6 * 3600.0, 86_400.0, 7 * 86_400.0]


# --- Seeking (REQ-TLP-002) ----------------------------------------------------------


def test_seeking_lands_on_the_last_earthquake_at_or_before_an_instant() -> None:
    quakes = [_quake(1, timedelta()), _quake(2, timedelta(days=1)), _quake(3, timedelta(days=5))]
    timeline = Timeline(quakes, fade=_FADE)

    assert timeline.step_at(_START + timedelta(days=1)) == 1
    assert timeline.step_at(_START + timedelta(days=3)) == 1
    assert timeline.step_at(_START + timedelta(days=30)) == 2
    assert timeline.step_at(_START - timedelta(days=1)) == 0  # before everything: the start


# --- The module is pure -------------------------------------------------------------


def test_the_timeline_imports_no_toolkit() -> None:
    """No screen, no clock, no file: only the record type and the standard library."""
    with open(timelapse.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for forbidden in ("flet", "flet_map", "time", "asyncio", "sqlite3"):
        assert not any(name == forbidden or name.startswith(forbidden + ".") for name in imported)
