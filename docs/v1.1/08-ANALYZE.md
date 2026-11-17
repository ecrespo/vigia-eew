# Analyze — Vigía-eew v1.1

> Artifact 08 of the v1.1 kit · 2026-11-16 · Base commit `bb58be8`
> Cross-artifact validation of 01–07 and the nine User Stories, **before any code**.
>
> Verdict: **ready to implement F9 to F11. F12 starts with a spike that can stop it. Two values
> await the maintainer before F13.**

## 1. Checks run

| Check | How | Result |
|---|---|---|
| Every requirement has a task | Script over 02 and 07 | ✅ 32 of 32 |
| Every task cites a requirement | Script over 07 | ✅ 31 of 31 (T-182 cites Art. 9) |
| Every acceptance criterion is in a task | Script, ranges expanded | ✅ 84 of 84 |
| Every criterion is in the traceability matrix | Script | ✅ 84 of 84 — 82 under a v1.1 requirement, 2 under REQ-MAP-002, inherited |
| No criterion cited that does not exist | Script | ✅ |
| Every backlog item is in exactly one epic | By reading 01 §2 | ✅ 10 of 10 |
| Every epic has a phase, every phase an exit | By reading 06 §3 | ✅ 8 of 8 |
| Hours in 07 add up to 09 | Script | ✅ 90–165 |
| Identifier ranges do not collide with v1.0 | `grep` over `docs/` and `src/` | ✅ |
| `lat check` | Run | ✅ |
| The test suite | **Not run** | ⚪ This kit changes no code |

### 1.1 Figures verified against the repository, not quoted from memory

| Claim | Where it is made | Verified |
|---|---|---|
| `cli.py` has no `--history` | 01 §1 | `grep` — true |
| `Actions=Settings;Simulate;` | 01 §1 | `packaging/vigia-eew.desktop:18` |
| The screen builds two filters of six | 01 §1 | `HistoryView._build_filters` — magnitude and verdict |
| `offset` is never set by the interface | 01 §1 | Only reset to 0, `history_view.py:148` |
| `events_correlation_id` exists | 04 ADR-034 | `history.py`, `_INDEXES` |
| `record()` replaces the row of the same arrival | 04 ADR-037 | Its docstring and `_UPSERT` |
| `prune()` already clears dangling `superseded_by` | 05 §2.3 | `history.py`, `prune` |
| `FletShell` keeps the screen across an alert | 04 ADR-031 | `_render`: `_screen` is not cleared by `show_alert` |
| A simulated event is injected at the controller | 04 ADR-040 | `Application._inject_simulated_alert` → `enqueue` |
| `SeismicEvent.depth_km` is required and ≥ 0 | 04 ADR-039 | `models.py:80` |
| `CircleMarker` has no events; `Marker` content does | 04 ADR-033 | `flet_map/circle_layer.py`; trial on the real client |
| EMSC serves an FDSN catalogue by date range | 03 §3 | Live request, HTTP 200 |
| 109 / 91 / 4 events in October 2026 | 05 §2.3 | Live requests to the three services |
| No arrival within 1 000 km beat its S wave | README, 02 | Query over the local history, read-only |

### 1.2 A figure this Analyze corrected

Earlier drafts of 01, 02 and the README said the latency was measured over **a year** of local
history. The file spans 2025-11-12 to 2026-11-16, but four rows account for the first nine months:
14 366 of its rows are from **August to November 2026**. The texts now say three months. The
conclusions do not change — they rest on the 588 arrivals within 1 000 km, all recent — but the
sample is a quarter, not a year.

---

## 2. Coverage

### Requirement → task → criterion

The full matrix is in [07-TASKS](07-TASKS.md). Summary by area:

| Area | Requirements | Tasks | Criteria |
|---|---|---|---|
| GUI | 3 | T-152..T-155 | 7 |
| HIS | 9 + 1 strengthened | T-156..T-158, T-161, T-162, T-167..T-171, T-174..T-176 | 34 |
| MAP | 2 | T-159, T-160 | 3 |
| TLP | 8 | T-163..T-166 | 13 |
| EST | 3 | T-172, T-173 | 7 |
| ALE | 3 | T-177, T-178 | 8 |
| UX | 3 | T-179..T-181 | 10 |
| MAP-002 *(inherited)* | — | T-158, T-166 | 2 |
| **Total** | **32** | **31** | **84** |

### Backlog item → epic → phase

| Item | Epic | Phase | Story |
|---|---|---|---|
| B-44, B-45 | EP-12 | F9 | HU-113 |
| B-46, B-50 | EP-13 | F10 | HU-114 |
| B-47 | EP-14 | F11 | HU-115 |
| B-48 | EP-15 | F12 | HU-116 |
| B-49 | EP-16 | F13 | HU-117 |
| B-51 | EP-17 | F14 | HU-118 |
| B-53 | EP-19 | F15 | HU-121 |
| B-52 | EP-18 | F16 | HU-119, HU-120 |

---

## 3. Findings

🔴 blocks a phase · 🟡 to know before building · 🟢 resolved here · ⚪ intentional

| # | Finding | Sev. | Phase it touches |
|---|---|---|---|
| V-01 | P-2 is open: one redraw of the map is unmeasured | 🔴 | F12 |
| V-02 | Two recovery defaults were chosen by the design, not by the maintainer — **resolved, D-10** | 🟢 | F13 |
| V-03 | A requirement worded for the user was verified on a module | 🟡 | process |
| V-04 | A v1.0 agent reads a recovered row as a discard | 🟡 | F13 |
| V-05 | After 90 days an earthquake the agent evaluated reads as *recovered* | 🟡 | F13 |
| V-06 | Joining recovered arrivals reuses a heuristic tuned for a live stream | 🟡 | F13 |
| V-07 | The per-earthquake reading changes little in today's data | 🟡 | F11 |
| V-08 | The countdown branch has never occurred | 🟡 | F16 |
| V-09 | T-181 changes the alert queue | 🟡 | F16 |
| V-10 | The system file dialog is unverified in the packaged binary | 🟡 | F14 |
| V-11 | The P-1 trial ran under X11 | 🟡 | F10 |
| V-12 | The effort labels of 01 understate the bottom-up estimate | 🟡 | all |
| V-13 | The schema migration announced in 01 is not needed | 🟢 | F13 |
| V-14 | REQ-ALE-013's criterion named a case the contract cannot produce | 🟢 | F16 |
| V-15 | `docs/v1/HU/HU-112` still describes the map on Tk and Pillow | ⚪ | — |

### V-01 · P-2 is open 🔴

Nobody has measured what replacing the map's symbols costs, and ADR-033 made each symbol heavier.
REQ-TLP-007's bound, the shortest step, and `MAP_SYMBOL_LIMIT` — already used in F10 — are numbers
that do not exist.

**It blocks T-165 and T-166, not F9–F11.** T-163 is the first task of F12 and delivers a verdict.
F10 ships with a provisional `MAP_SYMBOL_LIMIT`, marked as such in its comment, and T-163 replaces
it. The plan has a stop rule (06 §3): a verdict of *not viable* sends EP-15 back to design.

**One consequence to keep in view.** EP-15 closes on *"thirty days play in under a minute"*. With a
step per earthquake that needs `PLAYBACK_SYMBOL_LIMIT × MIN_DWELL ≤ 60 s`. October 2026 alone holds
8 774 arrivals in the local history; unfiltered, thirty days are thousands of steps. The criterion
can only be met on a **filtered** set — which is what a user would play — and T-163 has to say for
how many earthquakes.

### V-02 · Two defaults nobody decided — resolved 🟢

> **Resolved on 2026-11-16 as D-10:** the maintainer accepted the two keys and their defaults.
> What follows is the finding as it was raised.

ADR-036 needed to say what a recovery asks the catalogues for, and no artifact before it did. The
design introduced `[history] recovery_radius_km = 1000` and `recovery_min_magnitude = 2.5`.

They are reasoned — 2.5 is the floor `API-SPEC.md` already uses for USGS, and at those values a
month is ~200 arrivals — but they are **a proposal**. The alternative is to reuse the alert's own
`[filter] radius_km` and `min_magnitude` and add no key; it is simpler and makes the recovered
history *"the earthquakes that would have alerted"*, which is narrower than *"my region's
seismicity"* and makes for a sparser playback.

**Blocks T-167.** It needs a yes, or other figures, from the maintainer. Nothing before F13 depends
on it.

### V-03 · Verified against the module, not the user 🟡

REQ-HIS-005 says *"WHEN the user queries the history"*. Its criterion said *"a query"* without
saying whose, and a test on `HistoryStore.query` satisfied it. The interface offered two of five
filters and the requirement was marked met.

This kit strengthens the criterion. The lesson is for every requirement here: where one says *the
user*, its criterion names the screen. CA-114.1 does; the cut condition (06 §5) asks for each exit
criterion to be observed on the packaged binary.

### V-04 · A downgrade reads recovered rows as discards 🟡

`marker_style()` draws an unknown verdict as a discard, deliberately, so that nothing is left off
the map. A v1.0 agent pointed at a history holding `recovered` rows will therefore show them as
discarded, with no reason. It is degraded and not broken, and it only happens on a downgrade.

Accepted. The alternative — bumping the schema version so that v1.0 refuses the file
(`HistoryTooNew`) — would make a downgrade lose the whole history to protect a label.

### V-05 · The agent's verdict ages out before the earthquake does 🟡

With D-5, an earthquake the agent alerted on and that was also recovered loses its evaluated row at
90 days and keeps its recovered one until 365. From day 91 it reads as *recovered*: the fact that
the user was alerted is gone.

That is what two retentions mean, and it is honest by what the row is. But it is a consequence the
decision did not spell out. If it is not wanted, the remedy is in configuration — raise
`retention_days` — not in code.

### V-06 · A heuristic tuned for a stream, applied to a catalogue 🟡

Recovery joins an arrival to an existing earthquake with the deduplicator's predicate: ≤ 100 km,
≤ 90 s, ≤ 0.5 magnitude. Those thresholds were set for preliminary solutions arriving minutes
apart. A catalogue read months later holds **revised** solutions, and a revised magnitude can sit
more than 0.5 from the preliminary one the agent stored. Such an earthquake would fail to join and
appear twice in the per-earthquake reading.

T-170's tests use synthetic data and cannot show how often this happens. Its `integration` test
should recover a week the local history already holds and report how many earthquakes ended up
with two `correlation_id`s. If the rate is material, the thresholds for recovery become their own
constants.

### V-07 · One earthquake, one point — for 47 earthquakes 🟡

The local history holds 14 370 arrivals and 14 323 distinct `correlation_id`s: **47 earthquakes**
have more than one arrival. EMSC is 97 % of the rows; USGS is 83 and GEOFON 3.

So on today's data EP-14 changes little that can be seen, and its criteria will be verified mostly
on constructed cases. It becomes visible with recovery, which brings ~90 USGS events a month into a
region where EMSC brings ~110. EP-14 stays where it is — F12 and F13 both need it — but nobody
should expect its effect on the map before F13.

### V-08 · The countdown has never happened 🟡

REQ-ALE-011's first branch — a count that decreases — has not occurred once in three months: the
fastest EMSC arrival took 47 s, and within 1 000 km the closest miss was 69 s. D-9 took this in:
the text is designed for the elapsed case. It is restated here because CA-119.1 will only ever be
verified with an injected clock, and the feature's real value is the sentence of CA-119.2.

### V-09 · T-181 changes the component Art. 1 rests on 🟡

`AlertQueue` gains a rule: a real alert closes a drill. It is small, and it is in the one place
where a mistake costs an alert. T-181 runs the existing queue tests before and after, unchanged, as
the specification of what must not move; `test_presentation_guarantee.py` gains the two cases.

It is also the argument for D-7's order of cutting: dropping EP-18 drops this risk.

### V-10 · The file dialog 🟡

`FilePicker.save_file()` exists in Flet 1.0.4. On Linux it relies on a system helper (`zenity` is
present on the development machine); nothing guarantees it on a user's. ADR-038 specifies a path
field as fallback and T-175 records what the packaged binary did. P-5 closes there.

### V-11 · P-1 was tried under X11 🟡

The trial that showed a marker's tooltip, hover and click ran on a virtual X display. Flutter's
hit-testing is inside the client and should not depend on the display server, but *should* is not
*was observed*. T-159's GUI smoke runs on the maintainer's GNOME/Wayland session before F10 exits.

### V-12 · The labels understate the work 🟡

01 §2 gives each epic an order of magnitude — S ≤ 1 h, M ≤ half a day. Bottom-up, with tests, the
gate, both languages and the specification, the same epics come to **90–165 hours**
([09-ESTIMATE](09-ESTIMATE.md)): two to three times the labels. The labels order the epics
correctly and price them wrongly. 09 is the figure.

### V-13 · No schema migration — resolved 🟢

01 said EP-16 needed the first migration. ADR-037 shows it does not: *recovered* is a value of a
column that has no constraint on its values, and the index the per-earthquake reading needs is in
the initial schema. 01, the README and HU-117 were corrected. The risk that goes with a first
migration of a user's own record leaves the plan.

### V-14 · An example the contract cannot produce — resolved 🟢

REQ-ALE-013's criterion used *"an event with no depth"*. `SeismicEvent.depth_km` is required and
non-negative; such an event cannot be built. The criterion now uses a case that can occur — an
origin time later than the agent's clock — and CA-119.7 follows it.

### V-15 · HU-112's drift — intentional ⚪

`docs/v1/HU/HU-112` describes the map on a Tk canvas with Pillow; ADR-030 moved it to `flet-map`.
This kit does not rewrite a closed kit. T-182 adds a note to it.

---

## 4. Result by category

### Coverage — ✅
32 requirements, 31 tasks, 84 criteria; nothing orphaned in either direction.

### Constitution — ✅
No amendment needed. Checked again with the design in front of it:

| Reading made in 02 §12 | Still holds? |
|---|---|
| Recovery adds no network destination | ✅ Same host as the EMSC WebSocket, declared by its own key (`[emsc] catalog_url`). **A new key is a declaration, which E-06 (a) asks for**; it is not a new kind of destination |
| Playback does not widen the use of tiles | ✅ ADR-035 §5: the view never moves the map; CA-116.12 tests it |
| Export does not transmit | ✅ ADR-038: no network import, tested |

Art. 1 has four criteria that set a real alert against something new — CA-113.6, CA-116.10,
CA-120.7, CA-120.8 — and one that keeps recovery from alerting, CA-117.3.

### Ambiguity — ⚠️ one finding
V-02. Two values chosen by the design.

### Terminology — ✅
*Arrival* and *earthquake* are used in the sense of DATA-MODEL §3bis.1 throughout. *Verdict* has
three values everywhere it is listed. *Drill* covers both `--simulate` and the scheduled one.
*Step* is the playback's unit; *frame* is what a step shows.

### Unhappy paths — ✅
Every story has at least one (INDEX-HU). Checked specifically: history cannot be opened (113.3,
121.3); invalid input (114.4, 117.6); a network down (117.7); nothing to show (116.14, 118.7); a
file that cannot be written (118.12); an estimate that cannot be computed (119.7).

### Data — ✅
No schema change; one optional field in `state.json`; six configuration keys with defaults, so an
existing `config.toml` loads untouched (T-167's Done).

### Executability of the tasks — ✅
Every *Done* is a command or an observation. Two tasks deliver something other than code and say
so: T-163 (a document and a verdict) and T-182 (the cut).

### Orphan tasks — ✅
None. T-182 cites Art. 9 rather than a requirement, as the cut task of v1.0 did.

---

## 5. What this Analyze cannot close

| What | Why | What closes it |
|---|---|---|
| The bound, the step limits, `MAP_SYMBOL_LIMIT` | They are measurements | T-163 |
| Whether EP-15's closing criterion can be met, and for how many earthquakes | It follows from those figures | T-163 |
| The recovery defaults | They are the maintainer's to set | A decision (V-02) |
| How often a recovered arrival fails to join its earthquake | It depends on real catalogue revisions | T-170's integration test (V-06) |
| The file dialog on a user's machine | It depends on what is installed there | T-175 |
| Markers under Wayland | The trial was under X11 | T-159's smoke |

## 6. Verdict

| Phase | Verdict |
|---|---|
| **F9 · Door** | ✅ **Done**, 2026-11-16 |
| **F10 · Full query** | ✅ **Done**, 2026-11-16 — `MAP_SYMBOL_LIMIT` still provisional (V-01); the Wayland smoke (V-11) still owed |
| **F11 · One earthquake** | ✅ Ready (V-07 is about expectations, not about the work) |
| **F12 · Timelapse** | ⚠️ **T-163 first.** T-164 can follow it at once; T-165 and T-166 wait for its verdict |
| **F13 · Depth** | ✅ Ready — V-02 resolved as D-10 |
| **F14 · Figures and export** | ✅ Ready |
| **F15 · TUI** | ✅ Ready |
| **F16 · v1.0 promises and cut** | ✅ Ready, with V-09 in view |

**Nothing found requires rewriting a requirement.** Two were reworded during this pass (V-13,
V-14), both towards what the code can actually do.
