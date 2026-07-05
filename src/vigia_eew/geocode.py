"""Offline reverse geocoding: which country contains a lat/lon (RF-37).

`country_of(lat, lon)` returns the ISO-A2 code of the country whose land boundary
contains the point, or `None` for open ocean / no match. It powers the optional
country notification filter (`pipeline/filter.py`): an event is dropped only if it
falls **positively inside another country**; ocean/offshore points (`None`) are kept.

Boundaries come from a bundled, reduced Natural Earth 1:110m dataset
(`assets/countries.geojson`, public domain). Point-in-polygon is pure Python (ray
casting with a bounding-box pre-check and hole support) — no geospatial dependency,
matching the project's zero-extra-deps default (RNF-06). The dataset is loaded once,
lazily, and cached.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# A ring is a list of (lon, lat) vertices; a polygon is [exterior, *holes];
# an index entry is (iso, bbox, polygon) with bbox = (min_lon, min_lat, max_lon, max_lat).
_Ring = list[tuple[float, float]]
_Polygon = list[_Ring]
_Entry = tuple[str, tuple[float, float, float, float], _Polygon]
_Index = list[_Entry]

_ASSET_NAME = "countries.geojson"
_cached_index: _Index | None = None


def _asset_path() -> Path:
    return Path(__file__).parent / "assets" / _ASSET_NAME


def _polygons(geometry: dict[str, Any]) -> list[_Polygon]:
    """Normalize a GeoJSON Polygon/MultiPolygon into a list of polygons."""
    coords = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        raw_polygons = [coords]
    else:  # MultiPolygon
        raw_polygons = coords
    polygons: list[_Polygon] = []
    for raw in raw_polygons:
        polygons.append([[(float(x), float(y)) for x, y in ring] for ring in raw])
    return polygons


def _bbox(ring: _Ring) -> tuple[float, float, float, float]:
    lons = [x for x, _ in ring]
    lats = [y for _, y in ring]
    return (min(lons), min(lats), max(lons), max(lats))


def load_index(geojson: dict[str, Any]) -> _Index:
    """Build a lookup index from a GeoJSON FeatureCollection (pure, testable)."""
    index: _Index = []
    for feature in geojson["features"]:
        iso = feature["properties"]["iso"]
        for polygon in _polygons(feature["geometry"]):
            index.append((iso, _bbox(polygon[0]), polygon))
    return index


def _default_index() -> _Index:
    global _cached_index
    if _cached_index is None:
        with _asset_path().open(encoding="utf-8") as fh:
            _cached_index = load_index(json.load(fh))
    return _cached_index


def _point_in_ring(x: float, y: float, ring: _Ring) -> bool:
    """Ray-casting point-in-polygon test for a single ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _point_in_polygon(x: float, y: float, polygon: _Polygon) -> bool:
    """Inside the exterior ring and outside every hole."""
    if not _point_in_ring(x, y, polygon[0]):
        return False
    return not any(_point_in_ring(x, y, hole) for hole in polygon[1:])


def country_of(lat: float, lon: float, *, index: _Index | None = None) -> str | None:
    """ISO-A2 code of the country containing (lat, lon), or None (ocean / no match)."""
    idx = index if index is not None else _default_index()
    for iso, (min_lon, min_lat, max_lon, max_lat), polygon in idx:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            if _point_in_polygon(lon, lat, polygon):
                return iso
    return None
