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
