"""Spike T-163: what one redraw of the history map costs (REQ-TLP-007, closes P-2).

Run by hand, on a display; it is not part of the product nor of the test suite:

    uv run python scripts/spike_timelapse.py results.json

It opens a window holding the product's own `HistoryMap` -- minus the tile
layer, so that it touches no network -- and replaces the map's symbols again
and again, timing each replacement. Three painters are measured for each N:

  - ``markers``: every symbol a new `fm.Marker` holding a control, which is what
    `HistoryMap` does today on every redraw (ADR-033);
  - ``markers-kept``: the same markers kept between frames, one appended and
    the opacity of a tenth of them changed -- what a playback step changes;
  - ``circles``: every symbol a new painted `fm.CircleMarker`, the fallback the
    design kept in reserve.

**What a sample is.** The time from assigning the layer's symbols to the answer
of `Map.get_camera()`, a call that goes to the client and comes back. The
client handles messages in order on its UI thread, so the answer cannot arrive
before the patch has been applied; and the build and layout of one frame delay
the answer to the next. It is therefore the cost of a redraw *as the Python
side can observe it*, not a frame time read from the rasteriser.

The verdict, with the machine it was measured on, is in
`docs/v1.1/10-SPIKE-TIMELAPSE.md`.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import flet as ft
import flet_map as fm

from vigia_eew.history import EventRecord
from vigia_eew.notify.history_map import HistoryMap

SIZES = (50, 100, 200, 400, 800)
#: Redraws timed for each painter and size; the first two are discarded as warm-up.
REPEATS = 14
WARM_UP = 2
CENTRE = (10.4806, -66.9036)
_START = datetime(2026, 10, 1, tzinfo=UTC)


def _records(count: int, seed: int) -> list[EventRecord]:
    """`count` earthquakes scattered around the centre, a fifth of them alerted."""
    rng = random.Random(seed)
    return [
        EventRecord(
            id=index + 1,
            correlation_id=f"q{index}",
            source="EMSC",
            source_event_id=f"e{index}",
            occurred_at=_START + timedelta(minutes=index),
            recorded_at=_START + timedelta(minutes=index),
            latitude=CENTRE[0] + rng.uniform(-4, 4),
            longitude=CENTRE[1] + rng.uniform(-6, 6),
            depth_km=10.0,
            magnitude=rng.uniform(2.0, 6.5),
            region="SPIKE",
            distance_km=rng.uniform(5, 900),
            verdict="alerted" if index % 5 == 0 else "discarded",
        )
        for index in range(count)
    ]


def _circles(records: list[EventRecord], opacity: float) -> list[Any]:
    return [
        fm.CircleMarker(
            coordinates=fm.MapLatitudeLongitude(record.latitude, record.longitude),
            radius=4 + 2 * record.magnitude,
            color=ft.Colors.with_opacity(opacity, "#D32F2F"),
            border_color="#7F1010",
            border_stroke_width=2,
        )
        for record in records
    ]


async def main(page: ft.Page) -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "spike-timelapse.json"
    page.title = "Spike T-163"
    page.padding = 0
    page.window.width, page.window.height = 900, 760

    history = HistoryMap(centre=CENTRE, zoom=6)
    markers_layer = history._symbols
    circles_layer = fm.CircleLayer(circles=[])
    history.map.layers = [markers_layer, circles_layer]  # no tiles: no network
    page.add(history.view)
    page.update()
    await history.map.get_camera()

    async def timed(change: Any) -> float:
        started = time.perf_counter()
        change()
        page.update()
        await history.map.get_camera()
        return (time.perf_counter() - started) * 1000

    results: list[dict[str, Any]] = []

    def keep(painter: str, size: int, samples: list[float]) -> None:
        kept = sorted(samples[WARM_UP:])
        row = {
            "painter": painter,
            "symbols": size,
            "median_ms": round(statistics.median(kept), 1),
            "p90_ms": round(kept[int(len(kept) * 0.9) - 1], 1),
            "max_ms": round(kept[-1], 1),
        }
        results.append(row)
        print(row, flush=True)

    def clear() -> None:
        markers_layer.markers = []
        circles_layer.circles = []

    for size in SIZES:
        # --- every marker new, as HistoryMap redraws today ---
        await timed(clear)
        samples = []
        for repeat in range(REPEATS):
            records = _records(size, seed=repeat)
            samples.append(
                await timed(
                    lambda records=records: history.show(records, describe=lambda _record: "M")
                )
            )
        keep("markers", size, samples)

        # --- markers kept; a step appends one and fades a tenth ---
        await timed(clear)
        extra = _records(size + REPEATS, seed=99)
        history.show(extra[:size], describe=lambda _record: "M")
        page.update()
        await history.map.get_camera()
        samples = []
        for repeat in range(REPEATS):

            def step(
                repeat: int = repeat, size: int = size, extra: list[EventRecord] = extra
            ) -> None:
                kept = list(markers_layer.markers)
                for marker in kept[repeat % 10 :: 10]:
                    marker.content.opacity = 0.4 if repeat % 2 else 0.8
                history._records = extra[: size + repeat + 1]
                kept.append(history._symbol(_planned(extra[size + repeat])))
                markers_layer.markers = kept

            samples.append(await timed(step))
        keep("markers-kept", size, samples)

        # --- every circle new ---
        await timed(clear)
        samples = []
        for repeat in range(REPEATS):
            records = _records(size, seed=repeat)

            def paint(records: list[EventRecord] = records, repeat: int = repeat) -> None:
                circles_layer.circles = _circles(records, 0.4 if repeat % 2 else 0.8)

            samples.append(await timed(paint))
        keep("circles", size, samples)

    with open(out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    print("DONE", flush=True)
    await page.window.destroy()


def _planned(record: EventRecord) -> Any:
    from vigia_eew.notify.history_map import plan

    return plan([record])[0]


if __name__ == "__main__":
    ft.run(main)
