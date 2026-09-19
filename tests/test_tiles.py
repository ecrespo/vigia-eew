"""Tests for the map tile client (T-147, REQ-MAP-001/005, HU-112).

This is the one part of the product that talks to a destination the agent had
no business contacting before v1.0, so amendment E-06 bounds it: the tile
provider is reachable **only while the user has the map open**.

Every test here runs with an injected provider. Not for speed -- for the
assertion itself: what is being checked is how many requests happen and what
they carry, and that is only checkable when the requests are counted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vigia_eew.tiles import (
    ATTRIBUTION,
    TILE_SIZE,
    TileCache,
    TileClient,
    TileRef,
    tile_of,
    tiles_covering,
    user_agent,
)


class _Provider:
    """Stands in for OpenStreetMap: counts calls and remembers their headers."""

    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._fails = fails

    def __call__(self, url: str, headers: dict[str, str]) -> bytes:
        self.calls.append((url, headers))
        if self._fails:
            raise OSError("no route to host")
        return b"PNG" + url.encode()


@pytest.fixture
def cache(tmp_path: Path) -> TileCache:
    return TileCache(tmp_path / "tiles")


# --- The projection --------------------------------------------------------------


def test_a_coordinate_lands_on_the_tile_that_contains_it() -> None:
    """Caracas at zoom 7, against the numbering OpenStreetMap publishes.

    Worked out from the definition rather than read off the implementation:
    x = (-66.9036 + 180) / 360 x 128 = 40.21, and
    y = (1 - asinh(tan(10.4806°)) / pi) / 2 x 128 = 60.25.
    """
    x, y = tile_of(10.4806, -66.9036, 7)

    assert (int(x), int(y)) == (40, 60)
    assert round(x, 2) == 40.21
    assert round(y, 2) == 60.25


def test_the_whole_world_is_one_tile_at_zoom_zero() -> None:
    for lat, lon in ((0.0, 0.0), (60.0, -170.0), (-60.0, 170.0)):
        x, y = tile_of(lat, lon, 0)
        assert (int(x), int(y)) == (0, 0)


def test_going_east_increases_x_and_going_north_decreases_y() -> None:
    """The y axis points south, which is the mistake worth having a test for."""
    west, north = tile_of(20.0, -70.0, 8)
    east, south = tile_of(10.0, -60.0, 8)

    assert east > west
    assert south > north


def test_a_viewport_asks_only_for_the_tiles_it_shows() -> None:
    """CA-112.8: no bulk downloads, no speculative ring around the edges."""
    covering = tiles_covering(10.5, -66.9, zoom=7, width=TILE_SIZE, height=TILE_SIZE)

    assert 1 <= len(covering) <= 4  # a one-tile viewport straddles at most a corner
    assert all(ref.zoom == 7 for ref in covering)


def test_a_bigger_viewport_asks_for_more_tiles_and_no_more() -> None:
    small = tiles_covering(10.5, -66.9, zoom=7, width=TILE_SIZE, height=TILE_SIZE)
    large = tiles_covering(10.5, -66.9, zoom=7, width=TILE_SIZE * 3, height=TILE_SIZE * 3)

    assert len(large) > len(small)
    assert len(large) <= 16


def test_tiles_off_the_edge_of_the_world_are_not_requested() -> None:
    """There is no tile x=-1. Asking for one is a 404 the provider counts."""
    covering = tiles_covering(85.0, -180.0, zoom=2, width=TILE_SIZE * 4, height=TILE_SIZE * 4)

    assert all(0 <= ref.x < 4 and 0 <= ref.y < 4 for ref in covering)


# --- CA-112.8 · The client says who it is ----------------------------------------


def test_the_request_identifies_the_application_and_its_version() -> None:
    """The tile usage policy requires it, and an anonymous client gets blocked."""
    from vigia_eew import __version__

    assert user_agent().startswith(f"vigia-eew/{__version__}")


def test_every_request_carries_that_identity(cache: TileCache) -> None:
    provider = _Provider()
    client = TileClient(cache, fetch=provider)

    client.tile(TileRef(7, 44, 62))

    _url, headers = provider.calls[0]
    assert headers["User-Agent"] == user_agent()


def test_the_url_is_the_published_tile_scheme(cache: TileCache) -> None:
    provider = _Provider()
    client = TileClient(cache, fetch=provider)

    client.tile(TileRef(7, 44, 62))

    assert provider.calls[0][0].endswith("/7/44/62.png")


def test_the_attribution_the_licence_requires_is_declared_here() -> None:
    assert ATTRIBUTION == "© OpenStreetMap contributors"


# --- CA-112.1 · Nothing is requested until somebody asks -------------------------


def test_building_a_client_requests_nothing(cache: TileCache) -> None:
    """The map being closed is the default state of the agent's whole life."""
    provider = _Provider()

    TileClient(cache, fetch=provider)

    assert provider.calls == []


def test_only_the_map_knows_about_the_tile_client() -> None:
    """CA-112.1 structurally: there is no other caller that could fire a request.

    Checked against the imports of the whole package rather than by watching
    traffic, because "no requests while closed" is a property of who can call
    this at all -- and a new caller added in a year is exactly what would break
    it quietly.
    """
    import ast

    import vigia_eew

    root = Path(vigia_eew.__file__).parent
    importers = set()
    for module in root.rglob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("tiles"):
                importers.add(module.name)
            elif isinstance(node, ast.Import):
                if any(alias.name.endswith("tiles") for alias in node.names):
                    importers.add(module.name)

    assert importers <= {"history_map.py", "tiles.py"}, importers


# --- CA-112.3 · The cache stops the second request -------------------------------


def test_a_tile_already_seen_is_not_requested_again(cache: TileCache) -> None:
    provider = _Provider()
    client = TileClient(cache, fetch=provider)
    ref = TileRef(7, 44, 62)

    first = client.tile(ref)
    second = client.tile(ref)

    assert first == second
    assert len(provider.calls) == 1


def test_the_cache_survives_a_new_client(tmp_path: Path) -> None:
    """Coming back to a zone tomorrow is the case the cache exists for."""
    provider = _Provider()
    ref = TileRef(7, 44, 62)
    TileClient(TileCache(tmp_path / "tiles"), fetch=provider).tile(ref)

    TileClient(TileCache(tmp_path / "tiles"), fetch=provider).tile(ref)

    assert len(provider.calls) == 1


def test_a_different_zoom_is_a_different_tile(cache: TileCache) -> None:
    provider = _Provider()
    client = TileClient(cache, fetch=provider)

    client.tile(TileRef(7, 44, 62))
    client.tile(TileRef(8, 44, 62))

    assert len(provider.calls) == 2


def test_the_cache_is_bounded_and_drops_the_least_recently_used(tmp_path: Path) -> None:
    """Tiles are disposable. What is not disposable is the user's disk.

    The three ages are set explicitly rather than by writing quickly and
    hoping: on a filesystem with one-second timestamps, "written in this
    order" and "has distinct mtimes" are not the same statement.
    """
    import os

    cache = TileCache(tmp_path / "tiles", max_tiles=3)
    client = TileClient(cache, fetch=_Provider())
    for index in range(3):
        client.tile(TileRef(7, index, 0))
        os.utime(cache.path_of(TileRef(7, index, 0)), (1000 + index, 1000 + index))

    client.tile(TileRef(7, 0, 0))  # a cache hit: it is now the most recently used
    client.tile(TileRef(7, 9, 9))  # a miss, which evicts down to the bound

    assert cache.count() == 3
    assert cache.get(TileRef(7, 0, 0)) is not None, "the one just read was evicted"
    assert cache.get(TileRef(7, 1, 0)) is None, "the least recently used survived"


def test_the_cache_lives_outside_the_state_directory(tmp_path: Path) -> None:
    """A cache the user -- or the OS -- can delete without consequence.

    That is the whole distinction: losing it costs a download, while losing
    the state costs a repeated alert (DATA-MODEL §3bis.5).
    """
    from vigia_eew.state import default_state_path
    from vigia_eew.tiles import default_cache_dir

    assert default_cache_dir() != default_state_path().parent


# --- REQ-MAP-002 · A provider that is not there costs nothing --------------------


def test_a_provider_that_fails_returns_nothing_rather_than_raising(cache: TileCache) -> None:
    """Art. 3: the map degrades, the window does not fall over."""
    client = TileClient(cache, fetch=_Provider(fails=True))

    assert client.tile(TileRef(7, 44, 62)) is None


def test_a_failure_is_not_cached_as_an_answer(cache: TileCache) -> None:
    """Caching "no" would keep a zone blank long after the network came back."""
    failing = _Provider(fails=True)
    client = TileClient(cache, fetch=failing)
    ref = TileRef(7, 44, 62)
    client.tile(ref)

    working = _Provider()
    assert TileClient(cache, fetch=working).tile(ref) is not None


def test_an_unwritable_cache_still_serves_the_tile(tmp_path: Path, monkeypatch) -> None:
    """The tile is in hand; failing to file it away is not a reason to drop it."""
    cache = TileCache(tmp_path / "tiles")
    provider = _Provider()
    client = TileClient(cache, fetch=provider)
    monkeypatch.setattr(
        TileCache, "put", lambda *_a, **_k: (_ for _ in ()).throw(OSError("read-only"))
    )

    assert client.tile(TileRef(7, 44, 62)) is not None


def test_the_suite_itself_cannot_reach_the_provider() -> None:
    """The guard in `conftest.py`, asserted rather than assumed.

    A test run that quietly downloads from OpenStreetMap is a test run
    sending traffic on somebody's behalf -- found by discovering real tiles in
    the developer's cache directory after a run. Every test that needs tiles
    injects a source; anything reaching for the real one fails here.
    """
    client = TileClient(TileCache())

    with pytest.raises(RuntimeError, match="must not fetch"):
        client._download(TileRef(7, 40, 60))


def test_the_cache_used_by_the_suite_is_not_the_developer_s(tmp_path: Path) -> None:
    from vigia_eew.tiles import default_cache_dir

    assert "pytest" in str(default_cache_dir()) or str(tmp_path) in str(default_cache_dir())
