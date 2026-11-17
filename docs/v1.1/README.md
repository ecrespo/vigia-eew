# SDD kit v1.1 — Vigía-eew

> 2026-11-16 · Base commit: `bb58be8` (**v1.0.0** + Flet GUI, ADR-030) · Target: **v1.1.0**
> Scope input: the repository evaluation of 2026-11-16 and the maintainer's request — a history
> that can be seen, and a timelapse of earthquakes.
> Rigor level: **spec-anchored**, the same as the [v1.0 kit](../v1/README.md).

This folder is a **delta on the v1.0 kit**, not a new kit. It specifies ten backlog items (B-44 to
B-53) and inherits everything else by reference.

**Language.** This kit is written in English by the maintainer's decision of 2026-11-16, in line
with the repository convention (RNF-10). The v1.0 kit in `docs/v1/` stays in Spanish and is not
translated here. Identifier prefixes (`HU-`, `EP-`, `B-`, `T-`, `REQ-`, `CA-`) are kept so that
cross-references between the two kits keep working.

## Why v1.1 and not v2

Nothing here changes what the product is or breaks compatibility. Half of it closes what v1.0 left
half-done — a history built with no door, a `[MUST]` met only below the interface, two roadmap
features with no code — and the other half adds new readings of data already stored. There is no
schema migration: the history file keeps its version.

## The finding that orders everything else

**The history exists and cannot be opened.** Table, map and shared filter have been implemented and
tested since Phase 7 of v1.0. The only way in is the tray menu, and on GNOME/Wayland that menu may
not open. v1.0 solved that same problem for the configuration panel (REQ-GUI-009, `--settings`) and
not for the history.

That is why the first epic is a door and not the timelapse: the timelapse is a view inside a screen
that cannot be reached today.

## The artifacts

| # | Artifact | What it answers | Status |
|---|---|---|---|
| 00 | Constitution amendments | — | **Does not exist: none is needed** ([02 §12](02-PRD-DELTA.md)) |
| 01 | [Features](01-FEATURES.md) | The 10 items in 8 epics, with scope and non-scope | Draft — D-5..D-9 applied |
| 02 | [PRD delta (EARS)](02-PRD-DELTA.md) | 31 new requirements and 1 strengthened | Draft — D-5..D-9 applied |
| — | [User Stories HU-113..121](HU/INDEX-HU.md) | 84 acceptance criteria in Gherkin | Draft |
| 03 | [API Spec delta](03-API-SPEC-DELTA.md) | Command line, catalogue recovery, internal contracts | Draft |
| 04 | [Technical Design delta](04-TECHNICAL-DESIGN-DELTA.md) | ADR-031..041 | Draft |
| 05 | [Data Model delta](05-DATA-MODEL-DELTA.md) | A third verdict, two retentions, six keys, `last_drill`. **No schema change** | Draft |
| 06 | [Implementation Plan](06-IMPLEMENTATION-PLAN.md) | Phases F9..F16, dependencies, risk, cut | Draft |
| 07 | [Tasks](07-TASKS.md) | T-152..T-182, each with its REQ, its CA and its "Done" | Draft |
| 08 | [Analyze](08-ANALYZE.md) | Cross-artifact validation before any code: 15 findings | Draft |
| 09 | [Estimate](09-ESTIMATE.md) | 90–165 hours, with assumptions and range | Draft |
| 10 | [Spike: timelapse](10-SPIKE-TIMELAPSE.md) | What one redraw costs — verdict: viable with markers | Done |

**All of it is draft.** The method asks for a human checkpoint between artifacts. The maintainer
asked for the whole kit in one pass on 2026-11-16; the checkpoint is therefore one review of the
set, and the [Analyze](08-ANALYZE.md) is where to start it.

## Identifiers

They continue those of the v1.0 kit, with no overlap.

| Series | Last used | This kit |
|---|---|---|
| Backlog items | B-43 | **B-44..B-53** |
| Epics | EP-11 | **EP-12..EP-19** |
| User Stories | HU-112 | **HU-113..HU-121** |
| Tasks | T-151 | **T-152..T-182** |
| ADR | ADR-030 | **ADR-031..ADR-041** |
| Amendments | E-06 | *(none)* |
| Decisions | D-4 | **D-5..D-10** |
| Phases | F8 | **F9..F16** |
| Acceptance criteria | CA-112.x | **CA-113.x..CA-121.x** |
| Requirements | GUI-010 · HIS-006 · MAP-005 · ALE-010 · UX-006 | GUI-011..013 · HIS-007..015 · MAP-006..007 · ALE-011..013 · UX-007..009 · **TLP-001..008** · **EST-001..003** |

## Decisions

Six, **all resolved by the maintainer on 2026-11-16**. The alternatives are kept so the reasoning
can be revisited.

### D-5 · Which retention applies to what is recovered from the catalogue — **resolved: (a), 365 days**

Retention removes everything older than 90 days at startup. With recovery (EP-16) that collides:
recover a year, lose it on restart.

| Option | What it implies | Outcome |
|---|---|---|
| **(a) A retention of its own for recovered entries, 365 days, configurable separately** | Entries the agent evaluated stay at 90 days; recovered ones live longer. Two figures in `[history]`. No change for someone who recovers nothing | ✅ **Chosen** |
| (b) A single, longer retention | Raises the default for everything; multiplies the file size for everyone, since discards are most of the rows | Rejected |
| (c) No recovery beyond the retention in force | Recovery limited to 90 days; the timelapse never spans more than three months | Rejected |

**Consequences:** REQ-HIS-013 is closed with this wording; REQ-HIS-012 bounds how far back a
recovery can ask by that same figure; the Data Model delta (05) adds one configuration key and makes
the prune distinguish rows by provenance.

### D-6 · How the charts are drawn — **resolved: (a), existing controls**

| Option | What it implies | Outcome |
|---|---|---|
| **(a) With the controls already there** — bars built from containers | No dependency. Enough for bars; not enough if lines or fine axes are ever wanted | ✅ **Chosen** |
| (b) Add a Flet charting library | Better charts; a new dependency to justify, bound above, audit and ship in the binary | Rejected for now |
| (c) Figures in tables only | Cheapest; meets REQ-EST as worded | Rejected |

**Consequences:** no change to `pyproject.toml` dependencies in this version. A charting library
later is a new decision, not an extension of this one.

### D-7 · Whether EP-18 is in v1.1 — **resolved: (a), in, as the last phase**

The countdown (F-03) and the scheduled drill (F-13) have no technical relation to the history.

| Option | What it implies | Outcome |
|---|---|---|
| **(a) In, as the last phase and cuttable** | One version closes what was promised | ✅ **Chosen** |
| (b) Out, to a v1.2 of its own | v1.1 stays centred on the history and ships sooner | Rejected |

**Consequences:** EP-18 is the last phase of the Implementation Plan (06). Order of cutting if it
comes to that: EP-19, then EP-18, then EP-17, then EP-16.

### D-8 · What makes the playback redraw — **resolved: (a), an earthquake**

| Option | What it implies | Outcome |
|---|---|---|
| **(a) The playback advances from one earthquake to the next** | One redraw per earthquake of the played set. Fading is evaluated at each step from each symbol's age. Speed is how long a step stays on screen | ✅ **Chosen** |
| (b) A clock tick, several redraws a second | Smooth fading; a redraw rate that has nothing to do with the data, and that nobody has measured on `flet-map` | Rejected |

**Consequences:** REQ-TLP-007 says it; assumption P-2 changes from *"several redraws a second are
sustainable"* to *"one redraw of N symbols costs how much"*, which is what the EP-15 spike now
measures. A quiet month costs a handful of redraws instead of thousands.

### D-9 · How the time until the shaking is worked out and said — **resolved: the five points below**

Taken after measuring the local history (P-4, in the next section): no arrival within 1 000 km was
ever received before its S wave.

| # | Decided | Where it lands |
|---|---|---|
| 1 | Constant velocity, 3.5 km/s, over the **hypocentral** distance — √(distance² + depth²) | REQ-ALE-012; an ADR in 04 |
| 2 | The text is designed for the case that happens: it says **roughly how long ago** the shaking should have arrived | REQ-ALE-011 |
| 3 | A countdown, when there is one, **rounds down** and never promises more time than the calculation gives | REQ-ALE-012 |
| 4 | **No travel-time table and no dependency** while no source delivers within seconds | Non-scope of EP-18; reopened only with such a source (F-05) |
| 5 | EP-18 **stays the last phase and cuttable** | Confirms D-7 |

**Consequences:** the depth becomes an input of the estimate, which is what REQ-ALE-013 already
covers when it is missing. No dependency is added.

### D-10 · What a recovery asks the catalogues for — **resolved: (a), two keys of its own**

Raised by the Analyze (V-02): the design had to say it and no artifact before it did.

| Option | What it implies | Outcome |
|---|---|---|
| **(a) `[history] recovery_radius_km = 1000` and `recovery_min_magnitude = 2.5`** | *"My region"* is asked separately from *"what should wake me"*. About 200 arrivals a month around Caracas | ✅ **Chosen** |
| (b) Reuse the alert's `[filter] radius_km` and `min_magnitude` | No new key; the recovered history is only what would have alerted, and the playback is sparser | Rejected |

**Consequences:** T-167 is unblocked; F13 waits for nothing.

## A standing constraint: the alert keeps its form

Stated by the maintainer on 2026-11-16. The alert as it is on `main` — it takes the whole screen,
shows the earthquake's data, and shows the epicentre and the reference point on the map — is not
redesigned by anything in this kit. T-178 and T-179 add a line and a label to it; nothing else in
v1.1 touches `notify/alert_window.py` or `notify/map_view.py`.

## Checks made on 2026-11-16

Three of the four assumptions of [02 §11](02-PRD-DELTA.md) were put to the test. The fourth is the
EP-15 spike's.

| | Question | How it was checked | Outcome |
|---|---|---|---|
| **P-1** | Can a symbol on `flet-map` react to being pointed at or pressed? | Read `flet-map` 1.0.4, then a trial with the real client on a virtual display: pointer moved and clicked by `xdotool`, events logged, screen captured | **A `CircleMarker` cannot** — it has no events and no tooltip. **A `Marker` holding a control can**: its tooltip shows, `on_hover` and `on_click` fire, and the click does not also reach the map. `Map.on_tap` reports the coordinates of a tap on empty map. → the history's symbols move from `CircleLayer` to `MarkerLayer`; selection by proximity is not needed |
| **P-3** | Does EMSC offer a catalogue query by date range? | Against the live service | **Yes.** `https://www.seismicportal.eu/fdsnws/event/1/query` is a standard FDSN `fdsnws-event`: `starttime`/`endtime`, `latitude`/`longitude`/`maxradius` (degrees), `minmagnitude`, `limit`, `orderby`. `format=json` returns the same `properties` the WebSocket delivers (`unid`, `time`, `mag`, `magtype`, `depth`, `flynn_region`); `format=text` is GEOFON's pipe-delimited layout. HTTP 200 for a week of August 2026 and for December 2025. → EMSC **is** recoverable, and its `unid` is the id the agent already stores, so a repeated recovery collides on the existing unique key |
| **P-4** | Is a constant-velocity model acceptable for the countdown? | Against the local history: 14 360 arrivals, August to November 2026 | **The model is acceptable; the countdown will read "already arrived" in practice always.** See below |

**What P-1 costs.** A `Marker` carries a control per symbol where a `CircleMarker` is a painted
shape. That is heavier, and it is the figure the EP-15 spike has to measure — with markers, not
circles.

**What P-3 costs.** The endpoint is on the host already configured, at a different path from the
WebSocket's. It gets its own key in the configuration before it is used — a configuration change,
as [02 §12](02-PRD-DELTA.md) anticipated, not a constitutional one. FUNVISIS remains the only
network that cannot be recovered.

**What P-4 found.** Time from an earthquake happening to the agent receiving it, per network:

| Network | Arrivals | Fastest | Median |
|---|---|---|---|
| EMSC | 13 923 | 47 s | 40 min |
| FUNVISIS | 351 | 9.9 min | 19 min |
| USGS | 83 | 30 min | 4.9 h |
| GEOFON | 3 | 5.1 h | 11 h |

Against that, the S wave at 3.5 km/s takes 86 s to cover 300 km. Of the 588 arrivals within 1 000 km
**none** was received before its S wave: the closest missed by 69 s. Of the 179 that alerted, the
best case was 4 minutes late and the median 19.5 minutes late.

So the error of the velocity model — seconds — is not what decides anything; the delivery delay —
minutes — is. The recommendations that followed, **all five accepted by the maintainer as decision
D-9** and applied to REQ-ALE-011 and REQ-ALE-012:

1. **Accept the constant velocity**, 3.5 km/s, but over the **hypocentral** distance
   (√(distance² + depth²)) and not the epicentral one. For an earthquake 60 km deep under the
   reference point the epicentral model says zero seconds; the real figure is about seventeen.
2. **Design the text for the case that happens.** The branch REQ-ALE-011 treats as the exception —
   *"should already have arrived"* — is the only one the history has ever seen. It should say
   **roughly how long ago** (*"the shaking should have arrived ≈ 19 min ago"*), which is information,
   where a bare *"already arrived"* is only an apology.
3. **Round towards safety.** A constant 3.5 km/s runs late beyond ~150 km, where the fastest S path
   goes through the mantle — a few seconds at 300 km. When a countdown does show, it rounds down and
   never promises more time than the calculation gives.
4. **No travel-time table and no dependency** until there is a source that delivers in seconds
   (F-05, out of scope). A better model of a wave that has already passed buys nothing.
5. **EP-18 stays last and cuttable** (D-7). This measurement is an argument for keeping it there.

The same query is a preview of REQ-EST-002: the latency figure must be a median, not a mean. One in
ten EMSC arrivals reached the agent more than ten days after the earthquake.

## What is left out, and why it is said

The expected-intensity filter (F-04), SeedLink (F-05), tsunami (F-08), multiple reference points
(F-11), the central relay (B-33) and presentation under Wayland (B-20). None was among the ten
points. Wayland is still the product's biggest open risk and **this kit does not move it**.

## Status

| | |
|---|---|
| **Specifications** | All ten artifacts in draft, with D-5 to D-9 applied |
| **Constitution amendments** | None required |
| **Pending decisions** | **None** — V-02 was resolved as D-10 |
| **Unchecked assumptions** | **1** — P-5 (the system file dialog in the packaged binary; T-175). P-1, P-2 (measured by T-163) and P-3 are checked; P-4 is closed by D-9 |
| **Requirements not closed** | **1** — REQ-TLP-007's bound and step limits, which T-163 sets |
| **Estimate** | 90–165 hours for everything; 43–80 for the minimum cut (F9–F12) |
| **Branch** | `feature/v1.1.0`, from `develop` |
| **Implementation** | **F9..F12 done** (T-152..T-166), 2026-11-16. F13..F16 pending — progress in [07-TASKS](07-TASKS.md) |
| **Verified against the file system** | `cli.py` has no `--history`; `vigia-eew.desktop` has `Actions=Settings;Simulate;`; `HistoryView` has two filters; `offset` is unused in the interface; `SCHEMA_VERSION = 1`; no trace of F-03 or F-13 in `src/` |
| **Not verified** | The test suite was not run for this evaluation; the facts above come from reading the code. The P-1 trial ran on X11 under Xvfb, not on a Wayland session |

## Next step

**F13, tasks T-167..T-171**, once the maintainer approves it: each phase waits for a go-ahead.

Owed by the maintainer from F12: the playback observed on the packaged binary (T-166's last
criterion), and a rerun of the spike on the real session (10 §7).

```bash
vigia-eew --history    # today: "unrecognized arguments"
```
