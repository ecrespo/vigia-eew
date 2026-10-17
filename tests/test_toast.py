"""Tests for the native toast (RF-14, RNF-03)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from desktop_notifier import Urgency

from vigia_eew.models import SeismicEvent
from vigia_eew.notify.toast import Toaster


def _ev(severity="critical", **kw) -> SeismicEvent:
    base = dict(
        id="x",
        source="EMSC",
        magnitude=6.1,
        mag_type="mw",
        place="NEAR COAST OF VENEZUELA",
        lat=10.6,
        lon=-66.93,
        depth_km=12.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=162.0,
        severity=severity,
    )
    base.update(kw)
    return SeismicEvent(**base)


class _FakeNotifier:
    def __init__(self, *, fails=False):
        self.sent: list[dict] = []
        #: Counted separately from `sent`: the failure path has to be
        #: distinguishable from never having been called at all.
        self.sent_attempts = 0
        self._fails = fails

    async def send(self, *, title, message, urgency, **kw):
        self.sent_attempts += 1
        if self._fails:
            raise RuntimeError("dbus down")
        self.sent.append({"title": title, "message": message, "urgency": urgency})


async def test_sends_toast_with_title_and_message():
    notifier = _FakeNotifier()
    await Toaster(notifier=notifier, reference_name="Caracas").notify(_ev())
    assert len(notifier.sent) == 1
    sent = notifier.sent[0]
    assert "6.1" in sent["title"]
    assert "Caracas" in sent["message"]


async def test_urgency_by_severity():
    async def urgency_of(sev):
        n = _FakeNotifier()
        await Toaster(notifier=n).notify(_ev(severity=sev))
        return n.sent[0]["urgency"]

    assert await urgency_of("info") == Urgency.Low
    assert await urgency_of("warning") == Urgency.Normal
    assert await urgency_of("critical") == Urgency.Critical


async def test_notifier_failure_is_swallowed_and_recorded(caplog):
    """A toast failure cannot bring down the alert (RNF-03), and must not be silent.

    "Does not raise" was the old assertion, and a `notify()` whose body was
    deleted passed it too. What is actually required is that the attempt
    happened, that it failed, and that the failure left a trace.
    """
    notifier = _FakeNotifier(fails=True)

    with caplog.at_level(logging.WARNING):
        await Toaster(notifier=notifier).notify(_ev())

    assert notifier.sent_attempts >= 1
    assert "toast" in caplog.text.lower()
