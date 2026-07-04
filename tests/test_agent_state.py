"""Tests for the shared state used by the tray icon (RF-34)."""

from __future__ import annotations

from vigia_eew.agent_state import AgentState


def test_defaults():
    e = AgentState()
    assert e.ws_connected is False
    assert e.last_alert is None


def test_mark_connected_and_reconnecting():
    e = AgentState()
    e.mark_connected()
    assert e.ws_connected is True
    e.mark_reconnecting()
    assert e.ws_connected is False


def test_mark_last_alert():
    e = AgentState()
    e.mark_last_alert("M 6.1 · near La Guaira · 2026-06-28 13:39:00")
    assert e.last_alert == "M 6.1 · near La Guaira · 2026-06-28 13:39:00"
