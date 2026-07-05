"""Tests for the simulated event (RF-21, DATA-MODEL §4)."""

from __future__ import annotations

from datetime import UTC, datetime

from vigia_eew.config import ReferencePoint, Severity
from vigia_eew.simulation import simulated_event


def test_simulated_event_la_guaira():
    ev = simulated_event(ReferencePoint(), Severity())
    assert ev.source == "SIMULATED"
    assert ev.magnitude == 6.1
    assert ev.lat == 10.60
    assert ev.lon == -66.93
    assert ev.action == "create"


def test_critical_severity_by_magnitude():
    ev = simulated_event(ReferencePoint(), Severity())
    assert ev.severity == "critical"  # 6.1 >= warning_max (5.5)


def test_distance_calculated_from_reference():
    # Caracas (default) is ~15 km from La Guaira.
    ev = simulated_event(ReferencePoint(), Severity())
    assert 5 < ev.distance_km < 40


def test_distance_grows_with_far_reference():
    far = ReferencePoint(name="Maracaibo", lat=10.65, lon=-71.65)
    ev = simulated_event(far, Severity())
    assert ev.distance_km > 400


def test_time_utc_is_tz_aware():
    fixed = datetime(2026, 6, 28, 17, 39, tzinfo=UTC)
    ev = simulated_event(ReferencePoint(), Severity(), now=fixed)
    assert ev.time_utc == fixed
    assert ev.time_utc.tzinfo is not None
