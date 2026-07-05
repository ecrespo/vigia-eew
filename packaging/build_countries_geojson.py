"""Generate the bundled country-boundaries asset for offline reverse geocoding (RF-37).

Downloads Natural Earth 1:110m Admin-0 countries (public domain) and reduces it to a
compact GeoJSON with only an ISO-A2 `iso` property and rounded coordinates, small
enough to ship in the wheel/binary. Run manually to refresh the asset:

    uv run python packaging/build_countries_geojson.py

Source: https://github.com/nvkelso/natural-earth-vector (public domain, CC0).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_110m_admin_0_countries.geojson"
)
OUTPUT = (
    Path(__file__).resolve().parent.parent / "src" / "vigia_eew" / "assets" / "countries.geojson"
)
_COORD_DECIMALS = 3  # ~110 m; matches the 1:110m source resolution


def _iso_code(props: dict) -> str:
    """Best available ISO-A2 code, working around Natural Earth's `-99` gaps."""
    for key in ("ISO_A2", "ISO_A2_EH", "WB_A2", "POSTAL"):
        value = props.get(key)
        if value and value != "-99":
            return str(value)
    return "XX"


def _round_coords(node: object) -> object:
    """Recursively round coordinate numbers to `_COORD_DECIMALS`."""
    if isinstance(node, list):
        return [_round_coords(item) for item in node]
    if isinstance(node, float):
        return round(node, _COORD_DECIMALS)
    return node


def main() -> None:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as resp:  # noqa: S310 - fixed public URL
        source = json.load(resp)

    features = [
        {
            "type": "Feature",
            "properties": {"iso": _iso_code(feature["properties"])},
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": _round_coords(feature["geometry"]["coordinates"]),
            },
        }
        for feature in source["features"]
    ]
    reduced = {"type": "FeatureCollection", "features": features}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(reduced, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KiB, {len(features)} countries)")


if __name__ == "__main__":
    main()
