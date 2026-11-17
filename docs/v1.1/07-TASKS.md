# Tasks — Vigía-eew v1.1

> Artifact 07 of the v1.1 kit · Source specs: [02-PRD-DELTA](02-PRD-DELTA.md) ·
> [03-API-SPEC-DELTA](03-API-SPEC-DELTA.md) · [04-TECHNICAL-DESIGN-DELTA](04-TECHNICAL-DESIGN-DELTA.md) ·
> [05-DATA-MODEL-DELTA](05-DATA-MODEL-DELTA.md) · [06-IMPLEMENTATION-PLAN](06-IMPLEMENTATION-PLAN.md)
> **31 tasks** covering the 8 phases · Base commit `bb58be8`

## Conventions

- **Order = execution order**, except those marked `[P]`, which share no file and no dependency
  with the task before them.
- **States:** `[ ]` pending · `[~]` in progress · `[x] date` done · `[!]` blocked, with a note.
- **Done** is a command or a concrete observation, never "finished".
- Every task cites the requirement it implements. A task with no requirement means the requirement
  is missing or the task is not needed.
- **Progress is marked in this file**, so that any session can resume.
- **Test first** (the project's workflow): each task writes its failing test before its code.
- Every task leaves the gate green — `uv run pytest`, `uv run ruff check .`, `uv run mypy src`,
  `lat check` — and updates the `lat.md` section it names, with backlinks in both directions.
- Hours are effort for one person who knows the code, tests and specification included
  ([09-ESTIMATE](09-ESTIMATE.md)).

> **First batch: T-152 to T-155.** Run, review, adjust, and only then go on. F9 does not touch the
> schema, the configuration or the pipeline, and it is verified with one command.
>
> **F9 is done** (2026-11-16): 773 tests, gate green. Next batch: **F10, T-156 to T-160**.

## A constraint on every task

**The alert keeps its form.** As it is on `main`: it takes the whole screen, shows the earthquake's
data, and shows the epicentre and the reference point on the map (`notify/alert_window.py`,
`notify/map_view.py`, ADR-030). Stated by the maintainer on 2026-11-16. No task here redesigns it.
The two that touch it — T-178 (a line about the shaking) and T-179 (the drill label) — **add** to
it and change nothing else, and each asserts the existing alert tests unchanged in its *Done*.

---

## F9 · The history gets a door

### [x] 2026-11-16 T-152 · `--history`
- **What**: the option in `cli.py`, dispatched before the other modes, and
  `Application.open_history()` as the twin of `open_settings()`: standalone window, no agent, no
  tray. A history that cannot be opened shows a notice instead of an empty window.
- **REQ**: REQ-GUI-011 · **CA**: CA-113.1, CA-113.3
- **Files**: `src/vigia_eew/{cli,app,wiring}.py`, `tests/test_cli.py`, `tests/test_app.py`
- **Depends on**: —
- **Done**: `vigia-eew --history` opens the history and the process ends when the window closes;
  `vigia-eew --help` lists it; with a history file from a newer schema the window says so.
- **Hours**: 1–2
- **As built**: `--history` wins over `--settings` when both are given. The wiring is now the one
  owner of the run's `config.toml` path (`Wiring.config_file`), which is what let `app.py` stay
  under its 300-line limit. The notice for an unreadable history is `unavailable_view`.

### [x] 2026-11-16 T-153 · A launcher action on every packaged platform **[P]**
- **What**: a *History* action in `vigia-eew.desktop`, and its equivalent wherever T-150 and T-151
  gave the settings one (Windows installer, macOS bundle). The packaging-assets check learns it.
- **REQ**: REQ-GUI-011 · **CA**: CA-113.2
- **Files**: `packaging/vigia-eew.desktop`, `packaging/vigia-eew.iss`, `packaging/build_*.{sh,ps1}`,
  `scripts/check_packaging_assets.py`, `tests/test_packaging_assets.py`
- **Depends on**: T-152
- **Done**: `desktop-file-validate packaging/vigia-eew.desktop` is clean and its `Actions` are
  `Settings;History;Simulate;`; the assets check fails if the action is removed.
- **Hours**: 1–2
- **As built**: Linux gets the action **and** a launcher entry of its own
  (`vigia-eew-history.desktop`), as the settings did in T-151; Windows gets a Start Menu shortcut.
  macOS has no settings entry to mirror, so it gets none. The checker also fails an action that
  runs the wrong option.

### [x] 2026-11-16 T-154 · Navigation between the three screens
- **What**: `notify/navigation.py` — a bar with history, settings and About — composed into each
  screen's view by `Wiring`. The panel instance survives navigation, so an unsaved edit is still in
  its field on return.
- **REQ**: REQ-GUI-012 · **CA**: CA-113.4, CA-113.5 · **ADR**: ADR-031
- **Files**: `src/vigia_eew/notify/navigation.py` *(new)*, `src/vigia_eew/wiring.py`,
  `src/vigia_eew/notify/{history_window,config_panel,about_window}.py`, `src/vigia_eew/i18n.py`,
  `tests/test_navigation.py` *(new)*
- **Depends on**: T-152
- **Done**: from `--settings`, the history is reached and returned from without closing the window;
  a field edited and not saved keeps its value and its unsaved mark across the trip.
- **lat.md**: `notification.md` — navigation is part of the screen.
- **Hours**: 3–6
- **As built**: the history window outlives navigation too, so a filter survives the trip as an
  unsaved edit does. The bar follows `[notification] language`; the panel and About stay in English
  (T-151's decision). One existing assertion changed: `test_about_from_the_panel_returns_to_the_panel`
  compared the shell's view with `panel.view` by identity and now looks inside the frame.

### [x] 2026-11-16 T-155 · Navigation never competes with an alert; a screen knows when it is covered
- **What**: a test that pins the precedence with navigation present, and the `on_covered` /
  `on_uncovered` callbacks of `FletShell.show_screen()`.
- **REQ**: REQ-GUI-013 · **CA**: CA-113.6, CA-113.7 · **ADR**: ADR-031 · **X**: X-4
- **Files**: `src/vigia_eew/notify/flet_shell.py`, `tests/test_flet_shell.py`,
  `tests/test_presentation_guarantee.py`
- **Depends on**: T-154
- **Done**: with an alert presented, the page's controls are the alert and nothing else; no
  navigation call changes them; after acknowledgement the same screen object is rendered and its
  callbacks were called once each, in order.
- **Hours**: 2–4
- **As built**: three of the tests pin behaviour the design already gives — the bar is inside the
  screen — and passed when written; they are there so that moving the bar into the shell fails.
  Observed on the real client, on a virtual X display: `vigia-eew --history` opens the history with
  the bar, and *Settings* on the bar opens the panel.

---

## F10 · The interface queries everything the store knows

### [ ] T-156 · The list owns the filters and the paging
- **What**: `HistoryList` gains the period (local days → UTC bounds through `timeutil`), the
  maximum distance, the networks, the pages and `stretch`; `HistoryStore.verdicts()`. An invalid
  period is refused and the query stays as it was.
- **REQ**: REQ-HIS-005, REQ-HIS-007, REQ-HIS-008 · **CA**: CA-114.2, CA-114.3, CA-114.4, CA-114.5,
  CA-114.6 · **ADR**: ADR-032 · **X**: X-1, X-7
- **Files**: `src/vigia_eew/history.py`, `src/vigia_eew/notify/history_view.py`,
  `src/vigia_eew/timeutil.py`, `tests/test_history_view.py`, `tests/test_history.py`
- **Depends on**: T-152
- **Done**: for each of the five criteria, the rows of `HistoryList` equal `HistoryStore.query` for
  the same query; with 400 matching rows the last page ends at row 400 and `stretch` is
  `(301, 400, 400)`; `HistoryList`'s module still imports no toolkit.
- **Hours**: 3–5

### [ ] T-157 · The controls
- **What**: date range, maximum distance and network controls in `HistoryView`; the verdict and
  network options listed from the store; a pager showing the stretch and the total.
- **REQ**: REQ-HIS-007, REQ-HIS-008 · **CA**: CA-114.1, CA-114.5
- **Files**: `src/vigia_eew/notify/history_view.py`, `src/vigia_eew/i18n.py`,
  `tests/test_history_view.py`
- **Depends on**: T-156
- **Done**: the five filters are on the screen in both languages; the status reads
  *"151–300 of 1 240"*; `TABLE_ROW_LIMIT` is the page size and nothing loads more than it shows.
- **Hours**: 4–7

### [ ] T-158 · The map reads the whole filtered set **[P]**
- **What**: `HistoryList.everything(limit)`; `HistoryWindow` feeds the map from it instead of from
  the table's page; a notice when the set exceeds `MAP_SYMBOL_LIMIT`.
- **REQ**: REQ-HIS-008, REQ-MAP-004 *(inherited)* · **CA**: CA-114.5, CA-114.10 · **ADR**: ADR-032
- **Files**: `src/vigia_eew/notify/{history_view,history_window,history_map}.py`,
  `tests/test_history_window.py`
- **Depends on**: T-156
- **Done**: turning a page does not change the map's symbols; with a set above the limit the notice
  gives both figures.
- **Note**: `MAP_SYMBOL_LIMIT` is provisional until T-163 and says so in its comment.
- **Hours**: 1–3

### [ ] T-159 · Symbols are markers, with a tooltip
- **What**: `HistoryMap.show()` builds a `MarkerLayer`; the tooltip is the list's own formatted row
  (`HistoryList.row_for`).
- **REQ**: REQ-MAP-006 · **CA**: CA-114.7 · **ADR**: ADR-033
- **Files**: `src/vigia_eew/notify/{history_map,history_window}.py`, `tests/test_history_map.py`
- **Depends on**: T-158
- **Done**: every marker's tooltip equals the text of the table row for the same record; the GUI
  smoke shows a tooltip on hover (`VIGIA_GUI_TESTS=1`); `plan()`'s existing tests pass unchanged.
- **lat.md**: `history.md` — why markers and not circles (P-1).
- **Hours**: 3–5

### [ ] T-160 · The table and the map point at the same thing
- **What**: selection keyed by row id. A row chosen highlights its marker — thicker ring and larger
  size; a marker pressed selects its row, moving the table to its page (`HistoryList.go_to`).
- **REQ**: REQ-MAP-007 · **CA**: CA-114.8, CA-114.9 · **ADR**: ADR-033 · **X**: X-6
- **Files**: `src/vigia_eew/notify/{history_map,history_view,history_window}.py`,
  `tests/test_history_window.py`, `tests/test_history_map.py`
- **Depends on**: T-159
- **Done**: after a selection `plan()` yields exactly one selected marker and it carries that row's
  id; its size and ring differ from the rest with colours ignored; the import test on the list
  still passes.
- **Hours**: 3–6

---

## F11 · One earthquake, one point

### [ ] T-161 · The per-earthquake reading in the store
- **What**: `HistoryQuery.reading` and the network rank; prepared statements for the earthquake
  reading in each ordering, its count, and `HistoryStore.arrivals()`.
- **REQ**: REQ-HIS-009 · **CA**: CA-115.1, CA-115.2, CA-115.3, CA-115.4, CA-115.6 · **ADR**: ADR-034
- **Files**: `src/vigia_eew/history.py`, `tests/test_history.py`
- **Depends on**: T-156
- **Done**: an earthquake with two arrivals returns one row in the earthquake reading and two in the
  arrival one; the representative follows the four-step order, one test per step; the file's row
  count is equal before and after; a test asserts `sqlite3.sqlite_version_info >= (3, 25)`.
- **lat.md**: `history.md` — which arrival stands for an earthquake.
- **Hours**: 3–6

### [ ] T-162 · The switch, and the arrivals of an earthquake
- **What**: a control to switch readings; the pager, the map and the status follow it; from an
  earthquake, its arrivals with network, verdict and reason.
- **REQ**: REQ-HIS-009 · **CA**: CA-115.5, CA-115.7
- **Files**: `src/vigia_eew/notify/{history_view,history_window}.py`, `src/vigia_eew/i18n.py`,
  `tests/test_history_view.py`, `tests/test_history_window.py`
- **Depends on**: T-161, T-160
- **Done**: in the earthquake reading the map has one marker per `correlation_id`; the arrivals of a
  two-network earthquake list both.
- **Hours**: 3–5

---

## F12 · The history in motion

### [ ] T-163 · Spike: what one redraw costs
- **What**: measure, on the real client, the time to replace the map layer's symbols for N = 50,
  100, 200, 400, 800 — with markers and with circles — and write the verdict.
- **REQ**: REQ-TLP-007 · **Closes**: P-2
- **Files**: `docs/v1.1/10-SPIKE-TIMELAPSE.md` *(new)*, a script under `scripts/`
- **Depends on**: T-159
- **Done**: the document gives, with the method and the machine: the cost per redraw against N for
  both kinds of symbol; the values chosen for `PLAYBACK_SYMBOL_LIMIT`, `MAP_SYMBOL_LIMIT`,
  `MIN_DWELL` and `MAX_DWELL`; whether `PLAYBACK_SYMBOL_LIMIT × MIN_DWELL ≤ 60 s`; and one of
  *viable with markers* / *viable with circles while playing* / *not viable*.
- **Note**: **this task delivers a document and a decision, not product code.** If the verdict is
  *not viable*, T-165 and T-166 are not started (06 §3, stop rule).
- **Hours**: 3–6

### [ ] T-164 · The timeline
- **What**: `notify/timelapse.py`, pure: steps, `frame`, intensity by age, `dwell`, `step_at`.
- **REQ**: REQ-TLP-001, REQ-TLP-002, REQ-TLP-005, REQ-TLP-007 · **CA**: CA-116.1, CA-116.4,
  CA-116.5, CA-116.6, CA-116.9 · **ADR**: ADR-035
- **Files**: `src/vigia_eew/notify/timelapse.py` *(new)*, `tests/test_timelapse.py` *(new)*,
  `pyproject.toml` (import contract)
- **Depends on**: T-163, T-161
- **Done**: the three invariants of 03 §6 hold over generated sets; `dwell` of gaps of one second
  and one week both fall inside `[MIN_DWELL, MAX_DWELL]`; the module imports no toolkit and the
  contract fails if it does.
- **lat.md**: `history.md` — D-8, and why a frame depends only on its step.
- **Hours**: 4–7

### [ ] T-165 · The playback control
- **What**: `notify/timelapse_view.py`: play, pause, a slider over the steps, speed, trail switch,
  the instant in local time and the period; advancing with `FletShell.after()`.
- **REQ**: REQ-TLP-002, REQ-TLP-003, REQ-TLP-007 · **CA**: CA-116.2, CA-116.3, CA-116.7, CA-116.14
- **Files**: `src/vigia_eew/notify/timelapse_view.py` *(new)*, `src/vigia_eew/i18n.py`,
  `tests/test_timelapse_view.py` *(new)*
- **Depends on**: T-164
- **Done**: playing a set of forty earthquakes paints forty frames, counted on an injected painter;
  after pause no further frame is painted; the label is the frame's instant in the configured zone;
  with an empty set the play control is disabled.
- **Hours**: 5–9

### [ ] T-166 · A third reading of the same query
- **What**: the playback inside `HistoryWindow`, fed by `HistoryList.everything()` in the earthquake
  reading; a filter change replaces the set; the bound's notice; pause on `on_covered`; the map's
  unavailable notice inherited; no call that moves the map.
- **REQ**: REQ-TLP-004, REQ-TLP-006, REQ-TLP-007, REQ-TLP-008 · **CA**: CA-116.8, CA-116.10,
  CA-116.11, CA-116.12, CA-116.13 · **X**: X-4, X-5
- **Files**: `src/vigia_eew/notify/{history_window,history_map,timelapse_view}.py`,
  `tests/test_history_window.py`, `tests/test_presentation_guarantee.py`
- **Depends on**: T-165, T-155
- **Done**: with a minimum-magnitude filter no smaller earthquake is in any frame; an alert during
  playback is presented and, once acknowledged, the playback is paused on the same step; over a
  whole playback the map's centre and zoom are unchanged; thirty days of the local history play in
  under a minute at the top speed, observed on the packaged binary.
- **Hours**: 4–7

---

## F13 · A history with depth

### [ ] T-167 · The four keys
- **What**: `[emsc] catalog_url`, `[history] recovered_retention_days`, `recovery_radius_km`,
  `recovery_min_magnitude` in the schema and the example file; the EMSC catalogue in
  `docs/API-SPEC.md`.
- **REQ**: REQ-HIS-010, REQ-HIS-013 · **CA**: CA-117.10
- **Files**: `src/vigia_eew/config.py`, `src/vigia_eew/config.toml.example`, `docs/API-SPEC.md`,
  `docs/DATA-MODEL.md`, `tests/test_config.py`, `tests/test_config_panel.py`
- **Depends on**: —
- **Done**: `vigia-eew --check-config` accepts the example file; the four keys appear in the panel
  without a line of panel code; an existing `config.toml` without them loads with the defaults.
- **Hours**: 2–3

### [ ] T-168 · Two retentions, and who may overwrite whom **[P]**
- **What**: `prune()` with two cut-offs; `record_recovered()` with `DO NOTHING`; `near()`; a test
  that the live `record()` overwrites a recovered row; the *received live* predicate.
- **REQ**: REQ-HIS-011, REQ-HIS-012, REQ-HIS-013 · **CA**: CA-117.5, CA-117.8, CA-117.10, CA-117.12
  · **ADR**: ADR-037 · **X**: X-2
- **Files**: `src/vigia_eew/history.py`, `src/vigia_eew/wiring.py`, `tests/test_history.py`
- **Depends on**: T-167
- **Done**: after `prune` at the defaults, a recovered row 200 days old is there, an evaluated row
  100 days old is not, a recovered row 400 days old is not; changing one retention leaves the other
  kind of row untouched; `SCHEMA_VERSION` is still 1.
- **lat.md**: `history.md` — recovered is a verdict, not a column.
- **Hours**: 2–4

### [ ] T-169 · Reading a period from a catalogue
- **What**: `ingest/catalogue.py` — windows of 30 days, pages of 1 000, one retry — and
  `SourceSpec.recovery` for the four sources, FUNVISIS declaring why it has none.
- **REQ**: REQ-HIS-010, REQ-HIS-012 · **CA**: CA-117.1, CA-117.2, CA-117.7 · **ADR**: ADR-036
- **Files**: `src/vigia_eew/ingest/catalogue.py` *(new)*, `src/vigia_eew/ingest/registry.py`,
  `tests/test_catalogue.py` *(new)*, `tests/test_source_registry.py`
- **Depends on**: T-167
- **Done**: with an injected client, a 65-day period makes three windowed requests per network and
  pages until a short page; a 500 is retried once and then reported; the registry's validation fails
  for a source that declares neither a reader nor a reason. One test marked `integration` reads a
  day from each live service.
- **Hours**: 5–9

### [ ] T-170 · `backfill.py`
- **What**: the orchestration of ADR-036: priority order, normalise, join by the deduplicator's
  predicate (extracted to a function both use), `record_recovered`, the per-network outcome, the
  bound by retention, and the import contract.
- **REQ**: REQ-HIS-010, REQ-HIS-011, REQ-HIS-012 · **CA**: CA-117.3, CA-117.5, CA-117.6, CA-117.7,
  CA-117.8, CA-117.9, CA-117.11
- **Files**: `src/vigia_eew/backfill.py` *(new)*, `src/vigia_eew/pipeline/dedup.py`,
  `pyproject.toml` (import contract), `tests/test_backfill.py` *(new)*, `tests/test_dedup.py`
- **Depends on**: T-168, T-169, T-161
- **Done**: a second run leaves the row count equal; `state.json` is byte for byte the same before
  and after; an alerted row keeps its verdict and data; the same earthquake from a second network
  takes the first one's `correlation_id`; 400 days are refused before any request, naming 365; the
  contract fails if `backfill` imports `notify`, `supervisor`, `state` or `pipeline.processor`; the
  deduplicator's own tests pass unchanged.
- **lat.md**: `history.md` — recovery is a separate path; `pipeline.md` — the shared predicate.
- **Hours**: 5–9

### [ ] T-171 · `--backfill`, *Recover…*, and a third style
- **What**: the command-line option with its outcome and exit codes; the action on the history
  screen, on a worker thread, refreshing the views; the *recovered* style on the table, the map and
  the playback, with its legend entry and its strings.
- **REQ**: REQ-HIS-010, REQ-HIS-011 · **CA**: CA-117.1, CA-117.2, CA-117.4, CA-117.6 · **X**: X-1,
  X-5
- **Files**: `src/vigia_eew/{cli,app,wiring}.py`, `src/vigia_eew/notify/{history_map,history_view,
  history_window,timelapse_view}.py`, `src/vigia_eew/i18n.py`, `tests/test_cli.py`,
  `tests/test_history_map.py`
- **Depends on**: T-170
- **Done**: on an empty history, `vigia-eew --backfill 90` prints one line per configured network,
  FUNVISIS among them with its reason, and the history then holds rows from the period; the verdict
  filter offers *recovered* and isolates them; the three styles differ with colours ignored; the
  rows are still there after a restart.
- **Hours**: 4–7

---

## F14 · Figures and data out

### [ ] T-172 · The figures
- **What**: `history_stats.py`, pure: the splits over earthquakes and over arrivals, the median
  latency over arrivals received live, every figure with its sample size and period.
- **REQ**: REQ-EST-001, REQ-EST-002, REQ-EST-003 · **CA**: CA-118.1..CA-118.5, CA-118.7 · **ADR**:
  ADR-038 · **X**: X-2, X-8
- **Files**: `src/vigia_eew/history_stats.py` *(new)*, `tests/test_history_stats.py` *(new)*,
  `pyproject.toml` (import contract)
- **Depends on**: T-161, T-168
- **Done**: each split adds up to its own count; recovered rows do not move a latency; a network
  with none has no figure; nine arrivals within the hour and one ten days late give a figure within
  the hour; an empty input gives an empty summary, not zeros.
- **Hours**: 3–5

### [ ] T-173 · The summary on the screen
- **What**: `notify/history_stats_view.py`: the figures, bars built from containers, each with its
  sample size and period; a way to it from the history screen.
- **REQ**: REQ-EST-001, REQ-EST-003 · **CA**: CA-118.6, CA-118.7
- **Files**: `src/vigia_eew/notify/history_stats_view.py` *(new)*,
  `src/vigia_eew/notify/history_window.py`, `src/vigia_eew/i18n.py`,
  `tests/test_history_stats_view.py` *(new)*
- **Depends on**: T-172
- **Done**: every figure in the view has its sample size beside it; changing a filter changes the
  summary; no dependency was added to `pyproject.toml`.
- **Hours**: 4–6

### [ ] T-174 · The exporter **[P]**
- **What**: `history_export.py`, pure: CSV and GeoJSON.
- **REQ**: REQ-HIS-014 · **CA**: CA-118.9, CA-118.10, CA-118.11
- **Files**: `src/vigia_eew/history_export.py` *(new)*, `tests/test_history_export.py` *(new)*,
  `pyproject.toml` (import contract)
- **Depends on**: T-161
- **Done**: the CSV's first row names the columns and every instant parses as UTC with offset; the
  GeoJSON loads as a `FeatureCollection` with `[longitude, latitude]`; an `ast` test finds no
  network import in the module.
- **Hours**: 2–4

### [ ] T-175 · *Export…*
- **What**: the action on the history screen: format, destination by the system dialog or by a path
  field where the dialog is not available, an atomic write, and the error shown when it fails.
- **REQ**: REQ-HIS-014 · **CA**: CA-118.8, CA-118.12 · **Closes**: P-5
- **Files**: `src/vigia_eew/notify/{history_view,history_window}.py`, `src/vigia_eew/i18n.py`,
  `tests/test_history_window.py`
- **Depends on**: T-174, T-162
- **Done**: with a filter matching more than a page, the file has as many entries as the filter's
  count in the reading on screen; writing to a read-only directory shows the error and leaves no
  file; the dialog was tried on the packaged binary and the result is recorded here.
- **lat.md**: `history.md` — the reading of REQ-HIS-006 the export rests on.
- **Hours**: 2–4

---

## F15 · The history over SSH

### [ ] T-176 · The list in the terminal
- **What**: a `HistoryScreen` in the Textual app, built on `HistoryList` with its own read
  connection: the table, the filters, the pager; a key to open it.
- **REQ**: REQ-HIS-015 · **CA**: CA-121.1..CA-121.4 · **ADR**: ADR-041 · **X**: X-7
- **Files**: `src/vigia_eew/tui.py`, `src/vigia_eew/wiring.py`, `tests/test_tui.py`
- **Depends on**: T-157
- **Done**: for the same query the screen's rows equal `HistoryList.rows`; an unreadable history
  shows a notice and the dashboard still updates; an alert is pushed over the list and the list is
  back after it.
- **Hours**: 4–8

---

## F16 · What v1.0 promised, and the cut

### [ ] T-177 · The estimate
- **What**: `shaking.py`, pure: hypocentral distance, 3.5 km/s, the signed time, `None` when it
  cannot be computed.
- **REQ**: REQ-ALE-011, REQ-ALE-012, REQ-ALE-013 · **CA**: CA-119.4, CA-119.7 · **ADR**: ADR-039
- **Files**: `src/vigia_eew/shaking.py` *(new)*, `tests/test_shaking.py` *(new)*, `pyproject.toml`
  (import contract), `docs/TECHNICAL-DESIGN.md`
- **Depends on**: —
- **Done**: an event under the reference point at 70 km gives 20 s at its origin time; an origin
  time ahead of the clock gives `None`; the method and its assumptions are in the ADR.
- **Hours**: 2–3

### [ ] T-178 · The alert shows it
- **What**: the line in `AlertData`, formatted — remaining rounded down, elapsed in seconds or
  minutes, the approximation mark — in both languages; the graphical and the terminal alert update
  it once a second while on screen and recompute it on a revision.
- **REQ**: REQ-ALE-011, REQ-ALE-012, REQ-ALE-013 · **CA**: CA-119.1, CA-119.2, CA-119.3, CA-119.5,
  CA-119.6, CA-119.8
- **Files**: `src/vigia_eew/notify/{presentation,alert_window,controller}.py`, `src/vigia_eew/tui.py`,
  `src/vigia_eew/i18n.py`, `tests/test_presentation.py`, `tests/test_alert_window.py`,
  `tests/test_presentation_guarantee.py`
- **Depends on**: T-177
- **Done**: 18.9 s remaining displays 18; a count that reaches zero becomes the elapsed sentence and
  never a negative number; `--simulate` shows the line; with `estimate` returning `None` the alert's
  other guarantees are asserted unchanged and a log line names the reason.
- **Hours**: 3–6

### [ ] T-179 · A drill says it is a drill **[P]**
- **What**: every alert whose source is `SIMULATED` carries the label, in both frontends and both
  languages; a test that a simulated event never reaches the history sink.
- **REQ**: REQ-UX-008 · **CA**: CA-120.5, CA-120.6, CA-120.9 · **ADR**: ADR-040 · **X**: X-3
- **Files**: `src/vigia_eew/notify/{presentation,alert_window}.py`, `src/vigia_eew/tui.py`,
  `src/vigia_eew/i18n.py`, `tests/test_simulation.py`, `tests/test_history_pipeline.py`
- **Depends on**: —
- **Done**: `vigia-eew --simulate` shows the label; after it, the history has no row with source
  `SIMULATED`.
- **Hours**: 2–3

### [ ] T-180 · The schedule
- **What**: `[drill]` in the schema and the example file; `drill.py`; `last_drill` in `AppState` and
  `StateStore`; a supervised task that wakes hourly; the last drill on the About screen.
- **REQ**: REQ-UX-007 · **CA**: CA-120.1, CA-120.2, CA-120.3, CA-120.10
- **Files**: `src/vigia_eew/{config,drill,models,state,supervisor,wiring}.py`,
  `src/vigia_eew/config.toml.example`, `src/vigia_eew/notify/about.py`, `docs/DATA-MODEL.md`,
  `tests/test_drill.py` *(new)*, `tests/test_state.py`, `tests/test_supervisor.py`
- **Depends on**: T-179
- **Done**: with the clock injected past the interval a drill is enqueued; with the default
  configuration none ever is; with notifications paused none is; after acknowledgement `state.json`
  holds both instants and the About screen shows them; an old `state.json` without the field loads.
- **Hours**: 3–6

### [ ] T-181 · A drill against a real alert
- **What**: `AlertQueue.idle`; a drill is enqueued only when the queue is idle; a real event arriving
  while a drill is on screen closes it unacknowledged and is shown.
- **REQ**: REQ-UX-009 · **CA**: CA-120.4, CA-120.7, CA-120.8
- **Files**: `src/vigia_eew/notify/{queue,controller}.py`, `tests/test_alert_queue.py`,
  `tests/test_controller.py`, `tests/test_presentation_guarantee.py`
- **Depends on**: T-180
- **Done**: with a real alert shown or pending, a due drill is not shown until the queue empties;
  with a drill shown, a real alert is on screen without an acknowledgement having been given, and
  `last_drill.acknowledged_at` is null; every existing queue test passes unchanged.
- **Note**: this changes the component Art. 1 rests on. The existing tests are the specification of
  what must not change, and they are run before and after.
- **Hours**: 2–4

### [ ] T-182 · The v1.1.0 cut
- **What**: version `1.1.0`; the changelog; `README.md` and `CLAUDE.md` (the new options and
  modules); `docs/IMPLEMENTATION-PLAN.md` (structure, phase table, requirement → module matrix);
  the roadmap and the backlog; a note in `docs/v1/HU/HU-112` on its drift; this kit's README.
- **REQ**: Art. 9 · **Covers**: every phase that ships
- **Files**: `pyproject.toml`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `docs/IMPLEMENTATION-PLAN.md`,
  `docs/features/ROADMAP.md`, `docs/BACKLOG-PRIORIZADO.md`, `docs/v1/HU/HU-112-mapa-del-historico.md`,
  `docs/v1.1/README.md`, `tests/test_release_cut.py`
- **Depends on**: every task of the phases that ship
- **Done**: the gate and the GUI smokes are green; each shipped phase's exit criterion was observed
  on the packaged binary and noted here; `vigia-eew --help` on that binary lists `--history` and
  `--backfill`.
- **Note**: this task is not cut with EP-18. If F16's other tasks are dropped, it closes whichever
  phase is last.
- **Hours**: 2–4

---

## Traceability matrix

Every requirement in scope has at least one task. Every task cites at least one requirement.

| Requirement | Tasks | Criteria that verify it |
|---|---|---|
| REQ-GUI-011 | T-152, T-153 | CA-113.1, CA-113.2, CA-113.3 |
| REQ-GUI-012 | T-154 | CA-113.4, CA-113.5 |
| REQ-GUI-013 | T-155 | CA-113.6, CA-113.7 |
| REQ-HIS-005 *(strengthened)* | T-156 | CA-114.1, CA-114.2 |
| REQ-HIS-007 | T-156, T-157 | CA-114.1..CA-114.4 |
| REQ-HIS-008 | T-156, T-157, T-158 | CA-114.5, CA-114.6 |
| REQ-MAP-006 | T-159 | CA-114.7 |
| REQ-MAP-007 | T-160 | CA-114.8, CA-114.9 |
| REQ-HIS-009 | T-161, T-162 | CA-115.1..CA-115.7 |
| REQ-TLP-001 | T-164 | CA-116.1 |
| REQ-TLP-002 | T-164, T-165 | CA-116.3, CA-116.4, CA-116.5 |
| REQ-TLP-003 | T-165 | CA-116.7 |
| REQ-TLP-004 | T-166 | CA-116.8 |
| REQ-TLP-005 | T-164 | CA-116.9 |
| REQ-TLP-006 | T-166 | CA-116.10 |
| REQ-TLP-007 | T-163, T-164, T-165, T-166 | CA-116.2, CA-116.6, CA-116.11, CA-116.14 |
| REQ-TLP-008 | T-166 | CA-116.12 |
| REQ-HIS-010 | T-167, T-169, T-170, T-171 | CA-117.1, CA-117.2 |
| REQ-HIS-011 | T-168, T-170, T-171 | CA-117.3, CA-117.4, CA-117.12 |
| REQ-HIS-012 | T-168, T-169, T-170 | CA-117.5..CA-117.9, CA-117.11 |
| REQ-HIS-013 | T-167, T-168 | CA-117.10 |
| REQ-EST-001 | T-172, T-173 | CA-118.1, CA-118.2, CA-118.7 |
| REQ-EST-002 | T-172 | CA-118.3, CA-118.4, CA-118.5 |
| REQ-EST-003 | T-172, T-173 | CA-118.6 |
| REQ-HIS-014 | T-174, T-175 | CA-118.8..CA-118.12 |
| REQ-HIS-015 | T-176 | CA-121.1..CA-121.4 |
| REQ-ALE-011 | T-177, T-178 | CA-119.1, CA-119.2, CA-119.3, CA-119.8 |
| REQ-ALE-012 | T-177, T-178 | CA-119.4, CA-119.5, CA-119.6 |
| REQ-ALE-013 | T-177, T-178 | CA-119.7 |
| REQ-UX-007 | T-180 | CA-120.1, CA-120.2, CA-120.3, CA-120.10 |
| REQ-UX-008 | T-179 | CA-120.5, CA-120.6, CA-120.9 |
| REQ-UX-009 | T-181 | CA-120.4, CA-120.7, CA-120.8 |

CA-114.10 (the list without the map) and CA-116.13 (no tiles) verify REQ-MAP-002, inherited from
v1.0; they are in T-158 and T-166.

## Tasks by phase

| Phase | Tasks | Count | Hours |
|---|---|---|---|
| F9 | T-152..T-155 | 4 | 7–14 |
| F10 | T-156..T-160 | 5 | 14–26 |
| F11 | T-161, T-162 | 2 | 6–11 |
| F12 | T-163..T-166 | 4 | 16–29 |
| F13 | T-167..T-171 | 5 | 18–32 |
| F14 | T-172..T-175 | 4 | 11–19 |
| F15 | T-176 | 1 | 4–8 |
| F16 | T-177..T-182 | 6 | 14–26 |
| **Total** | | **31** | **90–165** |
