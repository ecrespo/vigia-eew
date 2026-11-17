"""The scheduled drill (T-180, REQ-UX-007, ADR-040).

Testing the smoke detector: an agent that goes months without alerting has no
other way to show it still can. `is_due` is the whole decision and is pure;
the scheduler around it only wakes, asks, and offers -- with the clock and the
sleep injected, so "a month passes" is a line in a test.
"""

from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from vigia_eew import drill
from vigia_eew.drill import CHECK_EVERY_S, FIRST_CHECK_S, DrillScheduler, is_due

_NOW = datetime(2026, 12, 1, 14, 0, tzinfo=UTC)


def test_a_drill_is_due_once_the_interval_has_passed() -> None:
    assert is_due(_NOW - timedelta(days=30, seconds=1), _NOW, 30) is True


def test_a_drill_is_not_due_before_the_interval_has_passed() -> None:
    assert is_due(_NOW - timedelta(days=29, hours=23), _NOW, 30) is False


def test_exactly_the_interval_is_due() -> None:
    assert is_due(_NOW - timedelta(days=30), _NOW, 30) is True


def test_with_no_drill_ever_the_first_one_is_due() -> None:
    """Somebody switched it on: the first drill is the proof they asked for."""
    assert is_due(None, _NOW, 30) is True


def test_a_last_drill_in_the_future_is_not_due() -> None:
    """A clock that was set back must not fire a drill on every wake."""
    assert is_due(_NOW + timedelta(days=2), _NOW, 30) is False


class _World:
    """The clock, the sleep and the record of what was offered."""

    def __init__(self, last: datetime | None, *, wakes: int) -> None:
        self.now = _NOW
        self.last = last
        self.slept: list[float] = []
        self.offered: list[datetime] = []
        self._wakes = wakes

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        if len(self.slept) > self._wakes:
            raise asyncio.CancelledError
        self.now += timedelta(seconds=seconds)

    def scheduler(self, interval_days: int = 30) -> DrillScheduler:
        return DrillScheduler(
            interval_days=interval_days,
            last_drill=lambda: self.last,
            offer=lambda: self.offered.append(self.now),
            now=lambda: self.now,
            sleep=self.sleep,
        )


async def _run(world: _World, **kwargs) -> None:
    with pytest.raises(asyncio.CancelledError):
        await world.scheduler(**kwargs).run()


async def test_a_drill_that_has_come_due_is_offered() -> None:
    """CA-120.1."""
    world = _World(_NOW - timedelta(days=31), wakes=1)

    await _run(world)

    assert len(world.offered) == 1


async def test_it_waits_a_moment_after_starting_and_then_wakes_hourly() -> None:
    world = _World(_NOW, wakes=3)

    await _run(world)

    assert world.slept[:3] == [FIRST_CHECK_S, CHECK_EVERY_S, CHECK_EVERY_S]
    assert CHECK_EVERY_S == 3600


async def test_nothing_is_offered_before_the_interval_passes() -> None:
    world = _World(_NOW - timedelta(days=29), wakes=5)

    await _run(world)

    assert world.offered == []


async def test_the_drill_is_offered_within_an_hour_of_falling_due() -> None:
    due_at = _NOW + timedelta(hours=2, minutes=30)
    world = _World(due_at - timedelta(days=30), wakes=6)

    await _run(world)

    assert world.offered
    assert timedelta(0) <= world.offered[0] - due_at <= timedelta(hours=1)


async def test_a_drill_nobody_took_is_offered_again_at_the_next_wake() -> None:
    """Refused -- paused, or a real alert up -- it stays due (CA-120.7, CA-120.10)."""
    world = _World(_NOW - timedelta(days=31), wakes=3)

    await _run(world)

    assert len(world.offered) == 3


async def test_once_presented_it_is_not_offered_again_until_the_next_interval() -> None:
    world = _World(_NOW - timedelta(days=31), wakes=4)
    scheduler = DrillScheduler(
        interval_days=30,
        last_drill=lambda: world.last,
        offer=lambda: (world.offered.append(world.now), setattr(world, "last", world.now)),
        now=lambda: world.now,
        sleep=world.sleep,
    )

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run()

    assert len(world.offered) == 1


async def test_an_offer_that_fails_does_not_end_the_schedule(caplog) -> None:
    world = _World(_NOW - timedelta(days=31), wakes=2)

    def broken() -> None:
        raise RuntimeError("the window is gone")

    scheduler = DrillScheduler(
        interval_days=30,
        last_drill=lambda: world.last,
        offer=broken,
        now=lambda: world.now,
        sleep=world.sleep,
    )

    with caplog.at_level("WARNING"), pytest.raises(asyncio.CancelledError):
        await scheduler.run()

    assert len(world.slept) == 3  # it kept waking
    assert any("drill_offer_failed" in r.getMessage() for r in caplog.records)


def test_the_module_knows_nothing_about_alerts_or_screens() -> None:
    with open(drill.__file__, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(name.startswith("vigia_eew") for name in imported)
    assert not any(name.split(".")[0] in ("flet", "textual", "time") for name in imported)
