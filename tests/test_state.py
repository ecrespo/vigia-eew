"""Tests for state persistence (RF-06, RF-10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
    s.register_alerted(AlertedId(id="us6000t8sx", source="USGS", time_utc=datetime.now(UTC)))
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
    s.register_alerted(AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC)))
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
    s.register_alerted(AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC)))
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


def test_a_failed_write_leaves_no_temp_file_behind(tmp_path, monkeypatch):
    """The atomic write cleans up after itself, and the old file survives."""
    s = _store(tmp_path)
    s.load()
    s.save()
    before = (tmp_path / "state.json").read_text(encoding="utf-8")

    def refuse(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("vigia_eew.state.os.replace", refuse)
    s.register_alerted(AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC)))
    with pytest.raises(OSError, match="disk full"):
        s.save()

    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]
    assert (tmp_path / "state.json").read_text(encoding="utf-8") == before


def test_the_trace_of_an_unknown_event_is_none(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.register_alerted(
        AlertedId(id="abc", source="EMSC", time_utc=datetime.now(UTC), trace_id="t-1")
    )

    assert s.trace_of("abc") == "t-1"
    assert s.trace_of("zzz") is None


def test_a_prevailing_arrival_replaces_its_signature(tmp_path):
    """REQ-PIP-010: one earthquake keeps one signature, the prevailing one."""
    s = _store(tmp_path)
    s.load()
    now = datetime.now(UTC)
    s.add_signature(EventSignature(lat=10, lon=-66, time_utc=now, magnitude=4.0, event_id="a"))
    s.add_signature(EventSignature(lat=11, lon=-67, time_utc=now, magnitude=5.0, event_id="b"))

    better = EventSignature(lat=10.1, lon=-66.1, time_utc=now, magnitude=4.2, event_id="a2")
    s.add_signature(better, replacing="a")

    assert [sig.event_id for sig in s.state.recent_signatures] == ["a2", "b"]


# --- T-180 · the last drill (REQ-UX-007, ADR-040, Data Model delta §4) -------------

import json  # noqa: E402

_DRILL_AT = datetime(2026, 12, 1, 14, 0, 3, tzinfo=UTC)


def test_there_is_no_last_drill_until_the_first_one(tmp_path):
    s = _store(tmp_path)
    s.load()

    assert s.last_drill() is None


def test_a_drill_presented_is_recorded_without_an_acknowledgement(tmp_path):
    s = _store(tmp_path)
    s.load()

    s.drill_presented(_DRILL_AT)

    again = _store(tmp_path)
    again.load()
    assert again.state.last_drill.presented_at == _DRILL_AT
    assert again.state.last_drill.acknowledged_at is None


def test_acknowledging_it_records_both_instants(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.drill_presented(_DRILL_AT)

    s.drill_acknowledged(_DRILL_AT + timedelta(seconds=38))

    again = _store(tmp_path)
    again.load()
    assert again.state.last_drill.presented_at == _DRILL_AT
    assert again.state.last_drill.acknowledged_at == _DRILL_AT + timedelta(seconds=38)


def test_only_the_last_drill_is_kept(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.drill_presented(_DRILL_AT)
    s.drill_acknowledged(_DRILL_AT + timedelta(seconds=5))

    s.drill_presented(_DRILL_AT + timedelta(days=30))

    assert s.last_drill().presented_at == _DRILL_AT + timedelta(days=30)
    assert s.last_drill().acknowledged_at is None


def test_an_acknowledgement_with_no_drill_is_ignored(tmp_path):
    s = _store(tmp_path)
    s.load()

    s.drill_acknowledged(_DRILL_AT)

    assert s.last_drill() is None


def test_a_state_written_before_drills_existed_still_loads(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps({"version": 1, "cursor_usgs_ms": 1782639238852, "alerted_ids": []}),
        encoding="utf-8",
    )

    s = StateStore(path)
    state = s.load()

    assert state.cursor_usgs_ms == 1782639238852
    assert state.last_drill is None
    assert state.version == 1


def test_the_schema_version_did_not_change(tmp_path):
    s = _store(tmp_path)
    s.load()
    s.drill_presented(_DRILL_AT)

    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["version"] == 1


def test_recording_a_drill_does_not_write_the_rest_of_a_stale_memory(tmp_path):
    """`--simulate` runs beside the agent, in another process.

    It read the state when it started. If recording its drill wrote that
    whole snapshot back, it would undo whatever the agent had saved since --
    an alerted id, and with it the rule that an earthquake alerts once.
    """
    simulate = _store(tmp_path)
    simulate.load()
    agent = _store(tmp_path)
    agent.load()
    agent.register_alerted(AlertedId(id="us6000t8sx", source="USGS", time_utc=_DRILL_AT))
    agent.update_usgs_cursor(1782639238852)
    agent.save()

    simulate.drill_presented(_DRILL_AT)
    simulate.drill_acknowledged(_DRILL_AT + timedelta(seconds=9))

    after = _store(tmp_path)
    after.load()
    assert after.already_alerted("us6000t8sx")
    assert after.state.cursor_usgs_ms == 1782639238852
    assert after.state.last_drill.acknowledged_at == _DRILL_AT + timedelta(seconds=9)


def test_the_agent_saving_does_not_erase_a_drill_another_process_recorded(tmp_path):
    agent = _store(tmp_path)
    agent.load()
    simulate = _store(tmp_path)
    simulate.load()
    simulate.drill_presented(_DRILL_AT)

    agent.update_usgs_cursor(1782639238852)
    agent.save()

    after = _store(tmp_path)
    after.load()
    assert after.state.last_drill.presented_at == _DRILL_AT
    assert agent.last_drill().presented_at == _DRILL_AT  # and the agent now knows of it


def test_an_older_drill_on_disk_does_not_replace_a_newer_one_in_memory(tmp_path):
    agent = _store(tmp_path)
    agent.load()
    other = _store(tmp_path)
    other.load()
    other.drill_presented(_DRILL_AT)
    agent.drill_presented(_DRILL_AT + timedelta(days=1))

    agent.save()

    assert agent.last_drill().presented_at == _DRILL_AT + timedelta(days=1)


def test_a_drill_recorded_with_no_file_yet_creates_it(tmp_path):
    s = StateStore(tmp_path / "fresh" / "state.json")

    s.drill_presented(_DRILL_AT)

    assert (
        json.loads((tmp_path / "fresh" / "state.json").read_text(encoding="utf-8"))["last_drill"][
            "acknowledged_at"
        ]
        is None
    )
