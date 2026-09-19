"""Map tiles from OpenStreetMap, on demand and cached (REQ-MAP-001, REQ-MAP-005).

This module is the only place in the agent that talks to the tile provider,
and amendment E-06 is the reason it is worth being careful about: until v1.0
the agent contacted seismic sources and, once, a geolocation service. A map
adds a **new kind of destination**, and the amendment bounds it -- reachable
only while the user has the map open.

That bound is kept structurally rather than by intention. Nothing constructs a
`TileClient` except the map window, and a test walks the package's imports to
prove no second caller has appeared. A request can only happen because
somebody is looking at a map.

The consequence that cannot be engineered away is **declared instead**: while
the map is open, the provider can infer roughly which area the user is looking
at. The cache reduces it and the on-demand fetching bounds it; neither removes
it (ADR-027).

No new dependency, which is what made the map defensible at all: `httpx` was
already here for the REST sources and `Pillow` for the tray icon.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir

from vigia_eew import __version__
from vigia_eew.config import APP_NAME

#: The published tile scheme. Not configurable: a second provider is a second
#: network destination, and E-06 says that takes an amendment, not a setting.
TILE_URL = "https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"

#: What the data licence requires on screen wherever a tile is (REQ-MAP-005).
ATTRIBUTION = "© OpenStreetMap contributors"

#: Every tile the scheme serves is 256×256.
TILE_SIZE = 256

#: How many tiles to keep. 512 at 256×256 is a few tens of megabytes -- enough
#: for the zones one person actually revisits, bounded enough that nobody
#: notices it on their disk.
DEFAULT_MAX_TILES = 512

#: The project's home, so the provider has somewhere to go if this client ever
#: misbehaves. Their usage policy asks for a contact, not just a name.
_CONTACT = "https://github.com/ecrespo/vigia-eew"

Fetcher = Callable[[str, dict[str, str]], bytes]


def user_agent() -> str:
    """How the client identifies itself (REQ-MAP-005, CA-112.8).

    The tile usage policy requires an application name, a version and a way to
    get in touch; an anonymous client is blocked, and rightly so.
    """
    return f"vigia-eew/{__version__} (+{_CONTACT})"


def default_cache_dir() -> Path:
    """Where tiles live: the platform's **cache** directory, not the data one.

    That distinction is the whole design (DATA-MODEL §3bis.5). Losing this
    costs a download; losing the state costs a repeated alert. Being somewhere
    the user -- or the operating system -- can clear without consequence is
    what makes it a cache rather than data.
    """
    return Path(user_cache_dir(APP_NAME)) / "tiles"


@dataclass(frozen=True, slots=True)
class TileRef:
    """One tile of the slippy map: a zoom level and a position in its grid."""

    zoom: int
    x: int
    y: int

    @property
    def name(self) -> str:
        return f"{self.zoom}_{self.x}_{self.y}.png"

    @property
    def url(self) -> str:
        return TILE_URL.format(zoom=self.zoom, x=self.x, y=self.y)


def tile_of(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """The fractional tile coordinates of a point (Web Mercator).

    Fractional on purpose: the whole number says which tile, and the remainder
    says where inside it, which is what the map needs to place a marker.

    Note the y axis points **south**. It is the sign error this projection is
    famous for, and there is a test whose only job is to catch it.
    """
    latitude = max(min(lat, 85.05112878), -85.05112878)
    radians = math.radians(latitude)
    scale = 2.0**zoom
    x = (lon + 180.0) / 360.0 * scale
    y = (1.0 - math.asinh(math.tan(radians)) / math.pi) / 2.0 * scale
    return x, y


def tiles_covering(lat: float, lon: float, *, zoom: int, width: int, height: int) -> list[TileRef]:
    """The tiles a viewport of that size, centred there, actually shows.

    What it shows and nothing more: no speculative ring, no neighbouring zoom
    levels, no prefetching (CA-112.8). Tiles off the edge of the grid are left
    out rather than requested -- there is no tile x=-1, and asking for one is a
    404 the provider counts against this client.
    """
    centre_x, centre_y = tile_of(lat, lon, zoom)
    half_x = width / (2 * TILE_SIZE)
    half_y = height / (2 * TILE_SIZE)
    limit = 2**zoom
    refs = []
    for x in range(math.floor(centre_x - half_x), math.floor(centre_x + half_x) + 1):
        for y in range(math.floor(centre_y - half_y), math.floor(centre_y + half_y) + 1):
            if 0 <= x < limit and 0 <= y < limit:
                refs.append(TileRef(zoom, x, y))
    return refs


class TileCache:
    """Tiles on disk, bounded, least-recently-used first out the door."""

    def __init__(self, directory: Path | str | None = None, *, max_tiles: int = DEFAULT_MAX_TILES):
        self.directory = Path(directory) if directory is not None else default_cache_dir()
        self.max_tiles = max_tiles

    def path_of(self, ref: TileRef) -> Path:
        return self.directory / ref.name

    def count(self) -> int:
        if not self.directory.exists():
            return 0
        return sum(1 for _ in self.directory.glob("*.png"))

    def get(self, ref: TileRef) -> bytes | None:
        """The cached tile, or None. Reading one marks it as recently used."""
        path = self.path_of(ref)
        try:
            data = path.read_bytes()
        except OSError:
            return None
        self._touch(path)
        return data

    def put(self, ref: TileRef, data: bytes) -> None:
        """Files a tile away and evicts down to the bound if that took it over."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path_of(ref).write_bytes(data)
        self._evict()

    def _touch(self, path: Path) -> None:
        """Marks a tile as used now, which is what makes the eviction LRU.

        Best-effort: a filesystem that will not let us set a timestamp turns
        the policy back into "oldest first", which is a worse cache and not a
        broken one.
        """
        try:
            os.utime(path, None)
        except OSError:  # pragma: no cover - depends on the filesystem
            pass

    def _evict(self) -> None:
        tiles = sorted(self.directory.glob("*.png"), key=lambda p: p.stat().st_mtime)
        for path in tiles[: max(0, len(tiles) - self.max_tiles)]:
            path.unlink(missing_ok=True)


class TileClient:
    """Fetches a tile, once, and only when something asks for it.

    The fetcher is injected so the tests can count requests and read their
    headers -- which is the only way to check "no bulk downloads" and "the
    client identifies itself" at all.
    """

    def __init__(
        self,
        cache: TileCache | None = None,
        *,
        fetch: Fetcher | None = None,
        timeout_s: float = 10.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.cache = cache if cache is not None else TileCache()
        self._fetch = fetch
        self._timeout_s = timeout_s
        self._log = logger or logging.getLogger("vigia_eew.tiles")

    def tile(self, ref: TileRef) -> bytes | None:
        """The tile's bytes, from the cache or the provider; None if neither.

        A failure returns nothing and is **not** cached. Caching a "no" would
        leave a zone blank long after the network came back, which is the kind
        of bug that looks like the map is simply broken.
        """
        cached = self.cache.get(ref)
        if cached is not None:
            return cached
        try:
            data = self._download(ref)
        except Exception as exc:  # noqa: BLE001 - the map degrades, it does not fall over
            self._log.warning("tile_unavailable ref=%s detail=%s", ref.name, exc)
            return None
        try:
            self.cache.put(ref, data)
        except OSError as exc:
            # The tile is in hand. Failing to file it away is not a reason to
            # drop it -- it only means the next viewing pays for it again.
            self._log.warning("tile_cache_write_failed ref=%s detail=%s", ref.name, exc)
        return data

    def _download(self, ref: TileRef) -> bytes:
        headers = {"User-Agent": user_agent()}
        if self._fetch is not None:
            return self._fetch(ref.url, headers)
        import httpx

        response = httpx.get(ref.url, headers=headers, timeout=self._timeout_s)
        response.raise_for_status()
        return bytes(response.content)
