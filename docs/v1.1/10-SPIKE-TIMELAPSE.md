# Spike — what one redraw of the map costs

> Artifact 10 of the v1.1 kit · 2026-11-16 · Task **T-163** · Closes **P-2** and finding **V-01**
>
> **Verdict: viable with markers.** The playback does not need a second painter.

## 1. The question

The playback (EP-15, ADR-035) redraws the map once per earthquake. Nobody had measured what a
redraw of `flet-map` costs with N symbols, and since ADR-033 each symbol is a marker holding a
control rather than a painted circle. Four numbers did not exist: `PLAYBACK_SYMBOL_LIMIT`,
`MIN_DWELL`, `MAX_DWELL`, and the `MAP_SYMBOL_LIMIT` that F10 shipped as a provisional figure.

## 2. Method

`scripts/spike_timelapse.py`. It opens a window holding the product's own `HistoryMap` — without
the tile layer, so that it touches no network — and replaces the symbols fourteen times for each
size and painter. The first two replacements are discarded as warm-up.

| Painter | What it does on each redraw |
|---|---|
| **markers** | Every symbol a new `fm.Marker` holding a container with tooltip and press handler. What `HistoryMap` does today |
| **markers-kept** | The markers are kept; one is appended and a tenth change opacity. What a playback step actually changes |
| **circles** | Every symbol a new painted `fm.CircleMarker`. The fallback ADR-033 kept in reserve |

**What a sample is.** The time from assigning the layer's symbols to the answer of
`Map.get_camera()`, a call that goes to the client and comes back. The client handles messages in
order on its UI thread, so the answer cannot arrive before the patch is applied, and the build and
layout of one frame delay the answer to the next. It includes building the controls in Python,
diffing and serialising them, and the client applying them.

**What it is not.** It is not a frame time read from the rasteriser. A raster thread that fell
behind would drop frames without showing up here.

## 3. The machine

| | |
|---|---|
| CPU | AMD Ryzen AI 9 HX PRO 370, 24 threads |
| OS | Linux 7.0.0-43, Python 3.13.9 |
| Flet / flet-map | 1.0.4 / 1.0.4 |
| Display | **Xvfb, 1600×1000, software rendering** (no DRI3) — not the machine's Radeon 890M |
| Window | 900×760, map filling it, zoom 6 |

Software rendering is the pessimistic case for painting. It is also not the user's session: the
figures below are an upper estimate for this machine and say nothing about a slower one.

## 4. Results

Milliseconds per redraw.

| Symbols | markers · median | markers · p90 | markers · max | kept · median | kept · p90 | circles · median | circles · p90 |
|---|---|---|---|---|---|---|---|
| 50 | 10.9 | 13.4 | 18.1 | 4.0 | 4.1 | 3.8 | 6.7 |
| 100 | 21.7 | 27.2 | 31.7 | 11.8 | 15.9 | 8.8 | 10.6 |
| 200 | 45.6 | 51.1 | 57.3 | 19.6 | 27.9 | 14.2 | 16.3 |
| 400 | 85.6 | 94.5 | 110.4 | 67.2 | 73.5 | 27.1 | 28.9 |
| 800 | 187.9 | 218.2 | 270.1 | 154.2 | 165.2 | 71.2 | 81.8 |

- The cost is **linear** in the number of symbols: about **0.22 ms per marker** and **0.08 ms per
  circle**.
- A marker costs between two and a half and three times a circle.
- Keeping the markers between frames helps at small sizes and little at 400 and above: most of
  the cost is not in creating the controls.

## 5. The figures chosen

| Constant | Value | Why |
|---|---|---|
| `PLAYBACK_SYMBOL_LIMIT` | **400** | The largest size measured whose worst redraw (110 ms) fits inside the shortest step with room to spare |
| `MIN_DWELL` | **0.15 s** | 400 markers redraw in 86 ms (median), 110 ms (worst seen): a third of the step is left for the controls to respond |
| `MAX_DWELL` | **2 s** | Not a measurement — a judgement: long enough for a quiet week to read as quiet, short enough not to look stopped |
| `MAP_SYMBOL_LIMIT` | **500**, kept | Interpolated at about 110 ms per redraw. It is redrawn when a filter changes, not on a timer, and that is under the delay a keystroke tolerates. No longer provisional |

**`PLAYBACK_SYMBOL_LIMIT × MIN_DWELL` = 400 × 0.15 s = 60 s.** The condition `≤ 60 s` holds, with
nothing to spare: a set of exactly 400 earthquakes, every gap short enough to be clamped to the
minimum, plays in exactly one minute.

### For how many earthquakes

Thirty days play in under a minute for any set of **up to 400 earthquakes**. Counted on the
maintainer's history, per earthquake, over its last thirty days:

| Filter | Earthquakes | Plays in full |
|---|---|---|
| None | 6 017 | No — the 400 most recent, and the notice says so |
| Magnitude ≥ 4.5 | 380 | Yes |
| Alerted | 169 | Yes |
| Within 1 000 km | 222 | Yes |
| Within 1 000 km, magnitude ≥ 2.5 | 117 | Yes |
| Within 500 km | 85 | Yes |

The closing criterion of EP-15 is met on a **filtered** set, as V-01 foresaw, and cannot be met
unfiltered: thirty days of everything are six thousand steps.

## 6. Verdict

**Viable with markers.**

- T-165 paints through `HistoryMap`, with the same markers the static map uses. A paused frame
  therefore answers the pointer like the static map does.
- The *circles while playing* fallback is not built. It would buy a threefold margin and cost a
  second painter, and the measured margin does not call for it.
- The *markers-kept* optimisation is not built either: at the bound it saves a fifth, for a view
  that would have to track which control belongs to which earthquake.

## 7. What this does not establish

| Not established | Who can |
|---|---|
| The cost on the real session, with the GPU — expected lower | The maintainer: `uv run python scripts/spike_timelapse.py out.json` |
| The cost with the tile layer drawing | Same run with tiles; the spike left them out to stay off the network |
| The cost on a slower machine | Nobody yet. If `MIN_DWELL` proves short there, it is one constant |
| Thirty days in under a minute **on the packaged binary** (T-166's last criterion) | The maintainer, on a build |

If a rerun gives a worst redraw at 400 symbols above 150 ms, lower `PLAYBACK_SYMBOL_LIMIT` rather
than raise `MIN_DWELL`: the product of the two has to stay at or under sixty seconds.
