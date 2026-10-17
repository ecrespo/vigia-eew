"""Shared test fixtures.

Isolate the whole suite from the real user directories: tests must never read
the developer's `~/.config/vigia-eew/config.toml` nor seed one there (RF-24),
and must never write a history into their data directory either. Each test
gets unique, non-existent default paths under `tmp_path`.

The history half of this was added after a test run created a real
`history.sqlite3` on the machine running it -- the same mistake the config
fixture already existed to prevent, one directory over.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch, tmp_path):
    from vigia_eew import config as config_module

    monkeypatch.setattr(
        config_module,
        "default_config_path",
        lambda: tmp_path / "vigia-eew" / "config.toml",
    )

    from vigia_eew import history as history_module

    monkeypatch.setattr(
        history_module,
        "default_history_path",
        lambda: tmp_path / "vigia-eew" / "history.sqlite3",
    )


@pytest.fixture(autouse=True)
def _no_desktop_client(monkeypatch):
    """The suite never starts the Flet desktop client.

    Not a convenience: the client is a native process that opens a window and,
    through the maps, downloads OpenStreetMap tiles -- a test run doing that is
    a test run sending traffic on somebody's behalf. Every test that runs a
    mode injects `run_ui`; anything that reaches for the real one fails here.
    """
    from vigia_eew import app as app_module
    from vigia_eew import wiring as wiring_module

    def refuse(_main):
        raise RuntimeError("the suite must not start the Flet client; inject run_ui")

    monkeypatch.setattr(app_module, "run_flet", refuse)
    monkeypatch.setattr(wiring_module, "run_flet", refuse)


# --- Test doubles for the WebSocket transport ---------------------------------
#
# Shared rather than copied: the same 23 lines lived in `test_ws_emsc.py` and
# `test_resilience.py`, and a fake that drifts between two files is a fake that
# passes in one place and lies in the other.


class FakeWS:
    """Fake WS connection: async context manager plus async iterator of messages.

    With `error`, raises it once the messages run out -- which is how the
    reconnection tests get a disconnect to happen at a chosen moment.
    """

    def __init__(self, messages, *, error=None):
        self._messages = list(messages)
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration


class FakeConnect:
    """Injectable connection factory; records the kwargs so keepalive is checkable."""

    def __init__(self, connections):
        self._connections = list(connections)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return self._connections.pop(0)


# --- Test double for the Flet window -----------------------------------------------


class FakeShell:
    """Stands in for `FletShell`: records what would be shown, runs `after` on demand.

    `after` queues instead of running, like the real shell crossing threads;
    `run_pending()` is the UI loop getting to them.
    """

    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []
        self.screens: list[tuple[str, str, object]] = []
        self.alerts: list[object] = []
        self.screen_key: str | None = None
        self.quit_calls = 0
        self.updates = 0
        self.page = type("Page", (), {"bgcolor": None})()

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))

    def run_pending(self) -> None:
        calls, self.after_calls = self.after_calls, []
        for _ms, callback in calls:
            callback()

    def show_screen(self, key, title, view):
        self.screen_key = key
        self.screens.append((key, title, view))

    def close_screen(self):
        self.screen_key = None

    def show_alert(self, view, *, configure, on_enter, bgcolor):
        self.alerts.append(view)
        self.on_enter = on_enter

    def clear_alert(self, view):
        if view in self.alerts:
            self.alerts.remove(view)

    def update(self):
        self.updates += 1

    def quit(self):
        self.quit_calls += 1


@pytest.fixture
def fake_shell() -> FakeShell:
    return FakeShell()
