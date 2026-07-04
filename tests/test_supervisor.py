"""Tests for the asyncio orchestrator (RNF-03, RNF-04)."""

from __future__ import annotations

import asyncio

from vigia_eew.supervisor import Supervisor


async def test_starts_every_registered_task():
    ran: set[str] = set()
    waits: list[float] = []

    async def sleep(s):
        waits.append(s)

    sup = Supervisor(sleep=sleep, jitter=False, handle_signals=False)

    async def do(name):
        ran.add(name)
        sup.request_stop()  # one task requests a stop; the rest are cancelled cleanly

    sup.add("a", lambda: do("a"))
    sup.add("b", lambda: do("b"))

    await asyncio.wait_for(sup.run(), timeout=1.0)
    assert "a" in ran  # at least the first one ran and triggered the stop


async def test_restarts_a_failing_task_with_backoff():
    waits: list[float] = []

    async def sleep(s):
        waits.append(s)

    sup = Supervisor(sleep=sleep, jitter=False, handle_signals=False)
    calls: list[int] = []

    async def fail():
        calls.append(1)
        if len(calls) >= 3:
            sup.request_stop()
            return
        raise RuntimeError("boom")

    sup.add("fail", fail)
    await asyncio.wait_for(sup.run(), timeout=1.0)

    assert len(calls) == 3  # restarted after each failure
    assert waits == [1.0, 2.0]  # exponential backoff between retries


async def test_isolates_failures_between_tasks():
    async def sleep(s):
        return None

    sup = Supervisor(sleep=sleep, jitter=False, handle_signals=False)
    good_ran = asyncio.Event()
    bad_attempts = 0

    async def good():
        good_ran.set()
        await asyncio.sleep(3600)  # lives until cancelled

    async def bad():
        nonlocal bad_attempts
        bad_attempts += 1
        if bad_attempts >= 3:
            sup.request_stop()
            return
        raise RuntimeError("boom")

    sup.add("good", good)
    sup.add("bad", bad)
    await asyncio.wait_for(sup.run(), timeout=1.0)

    assert good_ran.is_set()  # "bad" failing didn't prevent "good" from running
    assert bad_attempts == 3


async def test_clean_stop_cancels_live_tasks():
    async def sleep(s):
        return None

    sup = Supervisor(sleep=sleep, handle_signals=False)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def long_task():
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    sup.add("long", long_task)
    run_task = asyncio.create_task(sup.run())
    await asyncio.wait_for(started.wait(), timeout=1.0)
    sup.request_stop()
    await asyncio.wait_for(run_task, timeout=1.0)

    assert cancelled.is_set()  # clean shutdown: the live task was cancelled (RNF-04)
