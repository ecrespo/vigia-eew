"""Tests for deduplication (RF-09, RF-10, RF-11; heuristic in TECHNICAL-DESIGN §5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigia_eew.config import Dedup
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.dedup import Deduplicator
from vigia_eew.state import StateStore

_BASE = datetime(2026, 6, 28, 13, 39, tzinfo=UTC)


def _ev(
    *,
    id="evt-1",
    source="EMSC",
    action="create",
    lat=10.5,
    lon=-66.9,
    mag=6.0,
    time=_BASE,
) -> SeismicEvent:
    return SeismicEvent(
        id=id,
        source=source,
        magnitude=mag,
        mag_type="mw",
        lat=lat,
        lon=lon,
        depth_km=10.0,
        time_utc=time,
        distance_km=20.0,
        severity="critical",
        action=action,
    )


def _dedup(tmp_path, **cfg):
    state = StateStore(tmp_path / "state.json")
    state.load()
    return Deduplicator(Dedup(**cfg), state), state


# --- Dedup by id (RF-10, RF-11) ---


def test_new_event(tmp_path):
    dedup, _ = _dedup(tmp_path)
    assert dedup.classify(_ev()) == "new"


def test_same_id_create_is_duplicate(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="abc"))
    assert dedup.classify(_ev(id="abc")) == "duplicate"


def test_same_id_update_is_update(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="abc"))
    assert dedup.classify(_ev(id="abc", action="update")) == "update"


def test_update_of_unalerted_id_is_new(tmp_path):
    # An "update" whose create was never alerted (e.g. filtered out) is treated as new.
    dedup, _ = _dedup(tmp_path)
    assert dedup.classify(_ev(id="never-seen", action="update")) == "new"


# --- Cross-source heuristic (RF-09) ---


def test_cross_source_duplicate(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="emsc-1", source="EMSC", lat=10.50, lon=-66.90, mag=6.0))
    # USGS: another id, close (<100 km), <90 s, <0.5 mag -> same earthquake.
    usgs = _ev(
        id="usgs-1", source="USGS", lat=10.55, lon=-66.93, mag=6.2,
        time=_BASE + timedelta(seconds=30),
    )
    assert dedup.classify(usgs) == "duplicate"


def test_geofon_duplicate_of_prior_source(tmp_path):
    # RF-39/CA-18 regression: a GEOFON report of an earthquake already alerted via
    # EMSC/USGS/FUNVISIS must not re-alert. The heuristic is source-count-agnostic, so a
    # fourth source needs no change — this guards that it keeps holding.
    for prior in ("EMSC", "USGS", "FUNVISIS"):
        dedup, _ = _dedup(tmp_path)
        dedup.register(_ev(id=f"{prior}-1", source=prior, lat=10.50, lon=-66.90, mag=6.0))
        geofon = _ev(
            id="gfz-1", source="GEOFON", lat=10.55, lon=-66.93, mag=6.2,
            time=_BASE + timedelta(seconds=30),
        )
        assert dedup.classify(geofon) == "duplicate", prior


def test_geofon_only_new_event_is_not_suppressed(tmp_path):
    # A GEOFON-first event no other source has reported is genuinely new.
    dedup, _ = _dedup(tmp_path)
    assert dedup.classify(_ev(id="gfz-1", source="GEOFON")) == "new"


def test_cross_source_far_away_is_new(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0))
    far = _ev(id="usgs-1", source="USGS", lat=13.0, lon=-69.0, mag=6.0)
    assert dedup.classify(far) == "new"


def test_cross_source_outside_window_is_new(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0, time=_BASE))
    late = _ev(
        id="usgs-1", source="USGS", lat=10.5, lon=-66.9, mag=6.0,
        time=_BASE + timedelta(seconds=200),
    )
    assert dedup.classify(late) == "new"


def test_cross_source_different_magnitude_is_new(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="emsc-1", lat=10.5, lon=-66.9, mag=6.0))
    other_mag = _ev(id="usgs-1", source="USGS", lat=10.5, lon=-66.9, mag=7.0)
    assert dedup.classify(other_mag) == "new"


# --- Persistence (RF-10) ---


def test_register_persists_id_and_signature(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="abc"))

    reloaded = StateStore(tmp_path / "state.json")
    reloaded.load()
    assert reloaded.already_alerted("abc")
    assert len(reloaded.state.recent_signatures) == 1


def test_survives_restart(tmp_path):
    dedup, _ = _dedup(tmp_path)
    dedup.register(_ev(id="abc"))

    # New Deduplicator over re-read state (simulates a restart, RF-10).
    state2 = StateStore(tmp_path / "state.json")
    state2.load()
    dedup2 = Deduplicator(Dedup(), state2)
    assert dedup2.classify(_ev(id="abc")) == "duplicate"
