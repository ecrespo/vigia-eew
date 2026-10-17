"""Tests for what the two maps share: sizes, the alert's camera, the caption (ADR-030)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from vigia_eew.models import SeismicEvent
from vigia_eew.notify import map_view
from vigia_eew.notify.presentation import format_coordinates, format_event


def _data(*, lat=10.6, lon=-66.93, reference=(10.48, -66.90), magnitude=6.1):
    ev = SeismicEvent(
        id="x",
        source="EMSC",
        magnitude=magnitude,
        mag_type="mw",
        place="NEAR COAST OF VENEZUELA",
        lat=lat,
        lon=lon,
        depth_km=12.0,
        time_utc=datetime(2026, 6, 28, 13, 39, tzinfo=UTC),
        distance_km=162.0,
        severity="critical",
    )
    return format_event(ev, reference_name="Caracas", reference=reference)


def test_coordinates_read_with_their_hemispheres() -> None:
    assert format_coordinates(10.6, -66.93) == "10.60° N, 66.93° W"
    assert format_coordinates(-33.45, 151.2) == "33.45° S, 151.20° E"


def test_the_caption_carries_zone_coordinates_and_magnitude() -> None:
    caption = map_view.epicentre_caption(_data())

    assert "M 6.1" in caption
    assert "NEAR COAST OF VENEZUELA" in caption
    assert "10.60° N, 66.93° W" in caption


def test_the_caption_is_translated() -> None:
    assert "Coordenadas" in map_view.epicentre_caption(_data(), "es")


def test_without_a_reference_the_camera_sits_on_the_epicentre() -> None:
    camera = map_view.alert_camera(_data(reference=None))

    assert camera.centre == (10.6, -66.93)
    assert camera.zoom == map_view.EPICENTRE_ZOOM


def test_a_nearby_reference_is_framed_with_the_epicentre() -> None:
    camera = map_view.alert_camera(_data(lat=10.6, lon=-66.93, reference=(10.28, -67.85)))

    assert camera.centre == ((10.6 + 10.28) / 2, (-66.93 - 67.85) / 2)


def test_the_further_apart_the_wider_the_frame() -> None:
    near = map_view.alert_camera(_data(reference=(10.28, -67.85)))
    far = map_view.alert_camera(_data(reference=(8.0, -72.0)))

    assert far.zoom < near.zoom


def test_a_reference_across_an_ocean_is_left_out_of_the_frame() -> None:
    camera = map_view.alert_camera(_data(lat=38.0, lon=142.0, reference=(10.5, -66.9)))

    assert camera.centre == (38.0, 142.0)


def test_the_fit_fills_the_viewport_with_the_span() -> None:
    """At the computed zoom, `span` degrees of longitude cover the viewport."""
    zoom = map_view.zoom_to_fit(4.0, viewport_px=512)
    pixels = 4.0 / 360.0 * 256 * 2**zoom

    assert abs(pixels - 512) < 1


def test_the_fit_is_clamped_at_both_ends() -> None:
    assert map_view.zoom_to_fit(0.0) <= map_view.EPICENTRE_ZOOM + 2
    assert map_view.zoom_to_fit(360.0) >= 2.0


# --- E-06 · Tiles are fetched only while a map is on screen ------------------

_PACKAGE = Path(map_view.__file__).resolve().parents[1]
#: The views that put a map on screen -- the only modules allowed to build one.
_MAP_VIEWS = {"notify.map_view", "notify.alert_window", "notify.history_map"}


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_only_the_map_views_can_reach_the_tile_provider() -> None:
    """Nothing but a map on screen can build a tile layer (ADR-027, ADR-030).

    The Flet client fetches the tiles, so the bound is on who can put a
    `TileLayer` on a page: `flet_map` and `map_view` imported anywhere else
    is a second caller, which is exactly what would break E-06 quietly.
    """
    offenders = []
    for path in _PACKAGE.rglob("*.py"):
        module = ".".join(path.relative_to(_PACKAGE).with_suffix("").parts)
        if module in _MAP_VIEWS:
            continue
        reached = {
            name
            for name in _imports(path)
            if name.split(".")[0] == "flet_map" or name.endswith("map_view")
        }
        if reached:
            offenders.append((module, sorted(reached)))

    assert offenders == []


def test_the_tile_url_is_named_in_one_place() -> None:
    holders = [
        path.name
        for path in _PACKAGE.rglob("*.py")
        if "tile.openstreetmap.org" in path.read_text(encoding="utf-8")
    ]

    assert holders == ["map_view.py"]
