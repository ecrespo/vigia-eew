"""Tests for offline reverse geocoding (RF-37).

`country_of(lat, lon)` returns the ISO-A2 code of the country containing the point,
or None for open ocean / no match. Point-in-polygon is pure Python; tests use small
synthetic polygons so they don't depend on the bundled Natural Earth asset, plus a
couple of smokes against the real bundled data.
"""

from __future__ import annotations

from vigia_eew.geocode import country_of, load_index

# Country "AA": square lon [0,2] x lat [0,2] with a square hole around the center.
# Country "BB": a separate square lon [10,12] x lat [10,12], as a MultiPolygon.
_SYNTHETIC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"iso": "AA"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],  # exterior
                    [[0.8, 0.8], [1.2, 0.8], [1.2, 1.2], [0.8, 1.2], [0.8, 0.8]],  # hole
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"iso": "BB"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]]],
            },
        },
    ],
}


def test_point_inside_polygon_returns_iso():
    idx = load_index(_SYNTHETIC)
    assert country_of(0.5, 0.5, index=idx) == "AA"  # lat=0.5, lon=0.5


def test_point_in_hole_is_not_inside():
    idx = load_index(_SYNTHETIC)
    assert country_of(1.0, 1.0, index=idx) is None  # center falls in the hole


def test_point_outside_all_polygons_returns_none():
    idx = load_index(_SYNTHETIC)
    assert country_of(5.0, 5.0, index=idx) is None


def test_point_in_multipolygon_returns_iso():
    idx = load_index(_SYNTHETIC)
    assert country_of(11.0, 11.0, index=idx) == "BB"


def test_point_on_far_ocean_returns_none():
    idx = load_index(_SYNTHETIC)
    assert country_of(-40.0, -120.0, index=idx) is None


# --- Smokes against the real bundled Natural Earth asset ---


def test_bundled_asset_locates_venezuela():
    assert country_of(10.48, -66.90) == "VE"  # Caracas


def test_bundled_asset_locates_colombia():
    assert country_of(4.71, -74.07) == "CO"  # Bogotá


def test_bundled_asset_open_ocean_is_none():
    assert country_of(0.0, -30.0) is None  # mid-Atlantic
