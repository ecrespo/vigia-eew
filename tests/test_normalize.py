"""Tests for the normalizer (RF-07, RF-08, RF-13; mapping in API-SPEC §5.1)."""

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
    # Caracas -> Morón ≈ 162 km (API-SPEC §5).
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
    # The normalizer maps EMSC/USGS/FUNVISIS/GEOFON; SIMULATED is built by the CLI (Phase 5).
    assert _normalizer().normalize(msg) is None


# --- FUNVISIS (Venezuela-only local coverage) ---


def _funvisis(**props):
    base = {
        "phoneFormatted": "9.8 km",
        "phone": "2.3",
        "address": "45 km al norte    de Maracay",
        "city": "09:18",
        "country": "Venezuela",
        "postalCode": "05-07-2026",
        "state": "9.8 km",
        "lat": "10.64",
        "long": "-67.52",
    }
    return RawMessage(
        source="FUNVISIS",
        action="create",
        feature={
            "type": "Feature",
            "id": "funvisis-05-07-2026-09:18-10.64--67.52",
            "geometry": {"type": "Point", "coordinates": [-67.52, 10.64]},
            "properties": {**base, **props},
        },
    )


def test_normalizes_funvisis():
    ev = _normalizer().normalize(_funvisis())
    assert isinstance(ev, SeismicEvent)
    assert ev.source == "FUNVISIS"
    assert ev.id == "funvisis-05-07-2026-09:18-10.64--67.52"
    assert ev.magnitude == 2.3
    assert ev.mag_type == "ml"
    assert ev.lat == 10.64 and ev.lon == -67.52
    assert ev.depth_km == 9.8
    assert ev.region == "Venezuela"
    # Padded place name is collapsed to single spaces.
    assert ev.place == "45 km al norte de Maracay"


def test_funvisis_time_is_vet_converted_to_utc():
    # 09:18 VET (America/Caracas, -04) -> 13:18 UTC.
    ev = _normalizer().normalize(_funvisis(city="09:18", postalCode="05-07-2026"))
    assert ev is not None
    moment = ev.time_utc.astimezone(UTC)
    assert (moment.year, moment.month, moment.day) == (2026, 7, 5)
    assert (moment.hour, moment.minute) == (13, 18)
    assert ev.lastupdate_utc is None


def test_funvisis_malformed_depth_returns_none():
    assert _normalizer().normalize(_funvisis(phoneFormatted="")) is None


# --- GEOFON (independent global network, FDSN text) ---


def _geofon(**cols):
    # A GEOFON row pre-split by the poller into a {column: value} dict (API-SPEC §4.3).
    base = {
        "EventID": "gfz2020smye",
        "Time": "2020-01-15T12:00:00.0",
        "Latitude": "10.60",
        "Longitude": "-66.93",
        "Depth/km": "12.0",
        "MagType": "Mw",
        "Magnitude": "6.1",
        "EventLocationName": "NEAR COAST OF VENEZUELA",
        "EventType": "earthquake",
    }
    return RawMessage(source="GEOFON", action="create", feature={**base, **cols})


def test_normalizes_geofon():
    ev = _normalizer().normalize(_geofon())
    assert isinstance(ev, SeismicEvent)
    assert ev.source == "GEOFON"
    assert ev.id == "gfz2020smye"
    assert ev.magnitude == 6.1
    assert ev.mag_type == "mw"  # "Mw" normalized to lowercase like EMSC/USGS
    assert ev.lat == 10.60 and ev.lon == -66.93
    assert ev.depth_km == 12.0
    assert ev.place == "NEAR COAST OF VENEZUELA"
    assert ev.region is None
    assert ev.time_utc.astimezone(UTC).hour == 12
    assert ev.lastupdate_utc is None


def test_geofon_malformed_magnitude_returns_none():
    assert _normalizer().normalize(_geofon(Magnitude="")) is None


def test_funvisis_malformed_date_returns_none():
    assert _normalizer().normalize(_funvisis(postalCode="nope")) is None
