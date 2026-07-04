"""Tests for state persistence (RF-06, RF-10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigia_eew.config import ReferencePoint
from vigia_eew.models import AlertedId, EventSignature
from vigia_eew.state import StateStore


def _store(tmp_path) -> StateStore:
    return StateStore(tmp_path / "state.json")


def test_initial_load_is_empty(tmp_path):
    s = _store(tmp_path)
    state = s.load()
    assert state.alerted_ids == []
    assert state.cursor_usgs_ms is None


def test_round_trip_persistence(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.register_alerted(
        AlertedId(id="us6000t8sx", source="USGS", time_utc=datetime.now(UTC))
    )
    s.update_usgs_cursor(1782639238852)
    s.save()

    # New instance that reloads from disk (simulates restart, RF-10).
    s2 = _store(tmp_path)
    s2.load()
    assert s2.already_alerted("us6000t8sx")
    assert s2.state.cursor_usgs_ms == 1782639238852


def test_no_realert_after_restart(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.register_alerted(
        AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC))
    )
    s.save()
    s2 = _store(tmp_path)
    s2.load()
    assert s2.already_alerted("abc") is True
    assert s2.already_alerted("other") is False


def test_cursor_only_advances(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.update_usgs_cursor(100)
    s.update_usgs_cursor(50)  # lower: must not move backwards
    assert s.state.cursor_usgs_ms == 100
    s.update_usgs_cursor(200)
    assert s.state.cursor_usgs_ms == 200


def test_mark_acknowledged(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.register_alerted(
        AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC))
    )
    s.mark_acknowledged("abc")
    assert s.state.alerted_ids[0].acknowledged_utc is not None


def test_prune_by_age(tmp_path):
    s = _store(tmp_path)
    s.load()
    now = datetime.now(UTC)
    old = now - timedelta(hours=48)
    s.register_alerted(AlertedId(id="old", source="USGS", time_utc=old))
    s.register_alerted(AlertedId(id="new", source="USGS", time_utc=now))
    s.add_signature(EventSignature(lat=10, lon=-66, time_utc=old, magnitude=4.0))
    s.prune(now=now)
    ids = {a.id for a in s.state.alerted_ids}
    assert ids == {"new"}
    assert s.state.recent_signatures == []


def test_corrupt_state_does_not_break(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ this is not valid json ", encoding="utf-8")
    s = StateStore(path)
    state = s.load()  # must not raise; starts fresh
    assert state.alerted_ids == []


def test_atomic_write_leaves_a_single_file(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.save()
    files = list(tmp_path.iterdir())
    # Only state.json should remain, no dangling .tmp files.
    assert [p.name for p in files] == ["state.json"]


def test_cached_location_empty_by_default(tmp_path):
    s = _store(tmp_path)
    s.load()
    assert s.cached_location() is None


def test_cache_and_retrieve_location(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.cache_location(ReferencePoint(name="Maracaibo", lat=10.63, lon=-71.64))
    s.save()

    s2 = _store(tmp_path)
    s2.load()
    cached = s2.cached_location()
    assert cached is not None
    assert cached.name == "Maracaibo"
    assert cached.lat == 10.63
    assert cached.lon == -71.64
