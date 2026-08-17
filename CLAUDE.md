# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Vigía-eew (`vigia-eew`) is a desktop agent (Python 3.11+, `src/` layout) that monitors
earthquakes in real time (EMSC WebSocket as the primary channel, plus USGS/FUNVISIS/GEOFON
REST polling as backups — global redundancy and Venezuela-only local coverage) and shows a
**non-dismissable** desktop alert when an event falls within the configured
radius/magnitude. Single process per machine, no single point of failure (each machine runs
its own agent).

## Knowledge layers — query these before grepping

Three context layers. **All three are local and gitignored** — none ships with a
clone, so build them once per machine (commands below). They exist so you don't
rediscover the codebase on every task.

1. **Intent — `lat.md/`** (local, **hand-authored, does not regenerate**). Why the code
   is the way it is: design decisions, domain rules, rejected alternatives. Run
   `lat search "<topic>"` **before** changing behavior — several constants that look
   arbitrary (dedup thresholds, the block-list country filter, the local-day boundary)
   are deliberate. When present, `lat check` must pass before a task is done; it
   validates every `[[link]]` and every `# @lat:` backlink in the source, and exits
   cleanly (skipping) when the directory is absent.
   Unlike the other two, **whoever holds this directory holds the only copy** — the
   source of truth it was seeded from is the ADR series in `docs/TECHNICAL-DESIGN.md`.
2. **Structure — `.codegraph/`** (local, self-maintaining). What the code is:
   `codegraph query <sym>`, `codegraph callers/callees <sym>`, `codegraph impact <sym>`
   before any non-trivial edit, `codegraph explore <area>` to orient. Never grep for
   definitions or callers when this is present.
3. **Meaning — `graphify-out/`** (local, gitignored). How it fits together across code
   *and* docs: `graphify query "<question>"`, `graphify path "A" "B"`,
   `graphify explain "X"`. `GRAPH_REPORT.md` is a one-page orientation. Edges are
   tagged EXTRACTED (explicit in source) vs INFERRED (resolved) — verify INFERRED
   against CodeGraph before trusting it.

Layers 2 and 3 rebuild themselves from the AST; **`lat.md/` is maintained by hand and
cannot be rebuilt**. If you make a non-obvious design decision, add or update its
section and link the code with `[[src/path.py#Symbol]]` plus a `# @lat: [[section-id]]`
comment at the code site. The `# @lat:` comments **are** committed, so they keep
documenting intent inline even where the directory itself is absent.

```bash
npm i -g @colbymchenry/codegraph lat.md && uv tool install graphifyy   # one-time
codegraph init        # build .codegraph/ — tree-sitter, zero LLM tokens
graphify update .     # build graphify-out/ — AST only, zero LLM tokens
lat check             # validate the intent layer (finishing gate; skips if absent)
```

## Commands

```bash
uv venv && uv pip install -e ".[dev]"   # setup (recommended); or: pip install -e ".[dev]"

pytest                                  # full suite
PYTHONPATH=src pytest -q                # if the package isn't installed editable
pytest tests/test_dedup.py::test_x -q   # a single test
VIGIA_GUI_TESTS=1 pytest                # includes the real-Tkinter smokes (opt-in, needs a display)

ruff check .                            # lint (line-length 100, rules E,F,I,UP,B)
mypy src                                # type check (strict = true)

vigia-eew --help
vigia-eew --simulate                    # injects a simulated earthquake (M6.1 La Guaira), no network
vigia-eew --check-config                # validates config.toml and exits
vigia-eew --install-autostart           # installs autostart (systemd/LaunchAgent/task) and exits
```

Quality gate before considering a task done: `pytest`, `ruff check .`, `mypy src` — all
three green.

CI mirrors this: `.github/workflows/ci.yml` runs the gate on pushes/PRs to `develop`;
`.github/workflows/security.yml` runs SAST/SCA/secret scans (bandit, pip-audit, gitleaks,
semgrep, trivy) on PRs to `main`. `.pre-commit-config.yaml` runs the same checks locally
(`uv run pre-commit install`): fast ones per commit, the heavier ones (pytest, pip-audit,
semgrep, trivy) pre-push. `build.yml` builds/publishes releases on a `vX.Y.Z` tag.

## Architecture

**A single asyncio process** per machine. Four ingestors feed a common `raw_queue`:

- `ingest/ws_emsc.py` (`WSIngestor`): EMSC WebSocket, **primary channel**, 15 s keepalive,
  reconnection with exponential backoff + jitter (`backoff.py`, shared with the supervisor).
- `ingest/rest_usgs.py` (`RESTReconciler`): USGS polling every 60 s with a **persisted
  cursor**, only reconciles what the WS may have missed; doesn't compete with the push.
- `ingest/rest_geofon.py` (`GEOFONPoller`, RF-39): GFZ Potsdam `fdsnws-event` polling every
  60 s, **text format** (pipe-delimited, not GeoJSON) with its own **persisted cursor**;
  independent global network so an EMSC/USGS outage or catalog gap doesn't leave the agent
  blind.
- `ingest/rest_funvisis.py` (`FUNVISISPoller`, RF-38): polls FUNVISIS's `maravilla.json`
  (Venezuela-only, ~20 most recent events, no push channel) every 60 s; catches small local
  earthquakes (M2-3) the international networks don't catalog. Tracks novelty with an
  **in-memory seen-set** (no cursor — the endpoint has no `starttime` param), seeded on the
  first poll so startup doesn't re-alert on already-published events.

A `pipeline/processor.py` (`Processor`) consumes `raw_queue` and chains
`pipeline/normalize.py` → `pipeline/filter.py` → `pipeline/dedup.py`:

- **Normalize**: maps each source's raw payload to the single internal contract
  `SeismicEvent` (`models.py`), computes distance (`geo.py::haversine_km`) and severity.
- **Filter**: discards by radius or minimum magnitude (config).
- **Dedup**: intra-source dedup by id, cross-source heuristic (≤100 km, ≤90 s, ≤0.5 mag)
  and handling of EMSC `update`s (updates the in-flight event instead of re-alerting).
  Recent ids/signatures are persisted in `state.py` (`StateStore`, atomic JSON via
  `platformdirs`).

`supervisor.py` (`Supervisor`) orchestrates the asyncio tasks (`ws`, `rest`, `geofon`,
`funvisis`, `pipeline`) and **restarts each one with backoff on failure**, without taking
down the process — it must never die from a transient network or parsing failure.

New/relevant events reach `notify/` (`AlertController` in `controller.py`), which
orchestrates three effects as **injectable callbacks** (so they can be tested without
real I/O): `create_window` (non-dismissable, topmost Tkinter, `alert_window.py`),
`play_sound` (`sound.py`, by severity), and `send_toast` (`toast.py`,
`desktop-notifier`). `queue.py` keeps **one alert at a time** and updates it in place on
an `update`.

**asyncio↔Tkinter bridge** (`app.py`, ADR-006 in `docs/TECHNICAL-DESIGN.md`): Tkinter
must run on the main thread, ingestion lives in asyncio on a separate worker thread.
`AsyncioTkBridge` (in `notify/queue.py`) crosses events between both via a thread-safe
queue + `widget.after()`. `Application` (`app.py`) wires all of this together; it exposes
`execute()` (the full agent) and `simulate()` (injects the event from `simulation.py`
without network, for `--simulate`).

A system tray icon (`tray.py`, `AgentState` in `agent_state.py`) shows connection status
and the last alert, and lets the user pause/resume notifications, edit the config, and
quit — best-effort, never blocks startup if the platform can't show it (RF-34).

User-facing text (alert window, toast, tray menu) is internationalized via `i18n.py`
(RF-35): the language is auto-detected from the OS locale by default, overridable with
`[notification] language` in `config.toml` (`"auto"`/`"en"`/`"es"`), falling back to
English for unsupported locales.

`autostart/` installs/uninstalls OS-native autostart (systemd `--user` on Linux,
LaunchAgent on macOS, scheduled task on Windows), invoked from `cli.py` via
`--install-autostart`/`--uninstall-autostart`.

### Recurring testing pattern

Inject dependencies (`connect`/`sleep`/`client`/`runner`/`create_window`/etc.) and
separate **pure logic** (command/unit/plist generation, formatting, calculations) from
**system effects** (network, real Tkinter, systemctl/launchctl/schtasks, audio). Real GUI
tests are marked `skipif` unless `VIGIA_GUI_TESTS=1`; the default suite runs headless.

## Spec-driven development (SDD)

The project is built **phase by phase** following `docs/IMPLEMENTATION-PLAN.md`, which
links `docs/PRD.md` (requirements RF-xx/RNF-xx), `docs/API-SPEC.md`
(EMSC/USGS/FUNVISIS/GEOFON/internal contracts), `docs/TECHNICAL-DESIGN.md` (numbered
ADRs), and `docs/DATA-MODEL.md`.
`ARCHITECTURE.md` has the Mermaid diagrams (data flow, sequence, states, deployment). If
a module not listed in `IMPLEMENTATION-PLAN.md` is added, that section (structure +
phase table + RF→module matrix) is updated along with the code.

Commit convention: one per completed phase (conventional `feat:`/`docs:`, body
describing what was added and why), ending with a `Co-Authored-By:` trailer naming the
model that generated it (see `git log`).

## Conventions

- **English** in code, docstrings, comments, commit messages, and artifacts (RNF-10).
  User-facing text is internationalized (see `i18n.py`, RF-35) — the source-of-truth
  strings in the codebase are English, with a Spanish translation shipped alongside.
- Every internal `datetime` is **tz-aware in UTC** (`models.py` validates this and
  rejects *naive* values); conversion to local time (`America/Caracas`) happens only in
  `notify/presentation.py`.
- The internal contract (`SeismicEvent`) is the only payload that crosses layers — see
  `API-SPEC.md` §3 for the EMSC/USGS/FUNVISIS/GEOFON field mapping and invariants (distance
  and severity are always derived).
