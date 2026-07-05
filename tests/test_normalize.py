"""Tests for the normalizer (RF-07, RF-08, RF-13; mapping in API-SPEC §3.1)."""

from __future__ import annotations

from datetime import UTC

from vigia_eew.config import ReferencePoint, Severity
from vigia_eew.ingest import RawMessage
from vigia_eew.models import SeismicEvent
from vigia_eew.pipeline.normalize import Normalizer

# --- Sample raw payloads (API-SPEC §1.3 and §2.4) ---

_EMSC_PROPS = {
    "lat": 10.60,
    "lon": -66.93,
    "depth": 12.0,
    "mag": 6.1,
    "magtype": "mw",
    "time": "2026-06-28T13:39:00.0Z",
    "lastupdate": "2026-06-28T13:41:00.0Z",
    "unid": "20260628_0000123",
    "flynn_region": "NEAR COAST OF VENEZUELA",
}
_EMSC = RawMessage(
    source="EMSC",
    action="create",
    feature={
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "20260628_0000123",
        "properties": dict(_EMSC_PROPS),
    },
)

_USGS = RawMessage(
    source="USGS",
    action="create",
    feature={
        "type": "Feature",
        "id": "us6000t8sx",
        "properties": {
            "mag": 4.3,
            "place": "19 km WSW of Morón, Venezuela",
            "time": 1782639238852,
            "updated": 1782655565862,
            "magType": "mb",
            "type": "earthquake",
        },
        "geometry": {"type": "Point", "coordinates": [-68.3766, 10.4497, 10]},
    },
)


def _normalizer():
    return Normalizer(ReferencePoint(), Severity())


def _emsc(**props):
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-66.93, 10.60, 12.0]},
        "id": "x",
        "properties": {**_EMSC_PROPS, **props},
    }
    return RawMessage(source="EMSC", action="create", feature=feature)


# --- EMSC ---


def test_normalizes_emsc():
    ev = _normalizer().normalize(_EMSC)
    assert isinstance(ev, SeismicEvent)
    assert ev.source == "EMSC"
    assert ev.id == "20260628_0000123"
    assert ev.magnitude == 6.1
    assert ev.mag_type == "mw"
    assert ev.region == "NEAR COAST OF VENEZUELA"
    assert ev.depth_km == 12.0
    assert ev.time_utc.tzinfo is not None
    assert ev.time_utc.astimezone(UTC).hour == 13
    assert ev.lastupdate_utc is not None


def test_emsc_magtype_is_normalized_to_lowercase():
    ev = _normalizer().normalize(_emsc(magtype="Mw"))
    assert ev is not None and ev.mag_type == "mw"


def test_emsc_preserves_update_action():
    msg = RawMessage(source="EMSC", action="update", feature=_EMSC.feature)
    ev = _normalizer().normalize(msg)
    assert ev is not None and ev.action == "update"


# --- USGS ---


def test_normalizes_usgs():
    ev = _normalizer().normalize(_USGS)
    assert isinstance(ev, SeismicEvent)
    assert ev.source == "USGS"
    assert ev.id == "us6000t8sx"
    assert ev.mag_type == "mb"
    assert ev.place == "19 km WSW of Morón, Venezuela"
    # Coordinates from geometry [lon, lat, depth].
    assert ev.lat == 10.4497
    assert ev.lon == -68.3766
    assert ev.depth_km == 10
    # Epoch ms -> UTC: 1782639238852 == 2026-06-28T13:33:58.852Z
    assert ev.time_utc.astimezone(UTC).second == 58
    assert ev.lastupdate_utc is not None


# --- Derived fields (RF-08, RF-13) ---


def test_distance_computed_via_haversine():
    ev = _normalizer().normalize(_USGS)
    assert ev is not None
    # Caracas -> Morón ≈ 162 km (API-SPEC §3).
    assert 158 < ev.distance_km < 166


def test_severity_by_magnitude():
    assert _normalizer().normalize(_EMSC).severity == "critical"  # mag 6.1
    assert _normalizer().normalize(_USGS).severity == "warning"  # mag 4.3


def test_severity_respects_config_thresholds():
    norm = Normalizer(ReferencePoint(), Severity(info_max=7.0, warning_max=8.0))
    assert norm.normalize(_EMSC).severity == "info"  # 6.1 < 7.0 with high thresholds


# --- Resilience (RNF-03) ---


def test_feature_without_fields_returns_none():
    msg = RawMessage(source="EMSC", action="create", feature={"properties": {}})
    assert _normalizer().normalize(msg) is None


def test_invalid_time_returns_none():
    ev = _normalizer().normalize(_emsc(time="not-a-date"))
    assert ev is None


def test_unknown_source_returns_none():
    msg = RawMessage(source="SIMULATED", action="create", feature=_EMSC.feature)
    # The normalizer only maps EMSC/USGS; SIMULATED is built by the CLI (Phase 5).
    assert _normalizer().normalize(msg) is None
