# Implementation Plan — Vigía-eew

| Field | Value |
|---|---|
| Document | Implementation plan by phases, dependencies, and traceability |
| Version | 1.0 (draft for review) |
| Status | 🟡 Pending approval |
| Related | `PRD.md`, `TECHNICAL-DESIGN.md`, `DATA-MODEL.md`, `API-SPEC.md`, `ARCHITECTURE.md` |

> **Strict** order by layers (aligned with the project's work plan): SDD → structure →
> ingestion → dedup/filter → notification → autostart → `--simulate` verification → packaging/CI.
> **Phase gate**: Phase 0 (this set of artifacts) must be approved **before** coding starts.

---

## 1. Proposed project structure

```
vigia-eew/
├── pyproject.toml              # uv + hatchling, deps, entry point `vigia-eew`
├── README.md
├── CHANGELOG.md                # Keep a Changelog + semantic versioning (RF-27)
├── ARCHITECTURE.md
├── docs/                       # SDD artifacts (this set)
│   ├── PRD.md
│   ├── API-SPEC.md
│   ├── TECHNICAL-DESIGN.md
│   ├── DATA-MODEL.md
│   └── IMPLEMENTATION-PLAN.md
├── src/vigia_eew/
│   ├── __init__.py
│   ├── cli.py                  # entry point, flags, --simulate, --tui (dispatches to Application)
│   ├── app.py                  # Application: run()/simulate()/run_tui() wiring (ADR-006/ADR-013)
│   ├── tui.py                  # headless Textual dashboard + modal alert (--tui, RF-36)
│   ├── simulation.py           # simulated_event (M6.1 La Guaira)
│   ├── config.py               # Settings (pydantic) + config.toml loading + first-run seeding
│   ├── config.toml.example     # bundled template; seeded to the OS config path on first run (RF-24)
│   ├── models.py                # SeismicEvent, AppState, signatures
│   ├── geo.py                  # haversine_km (shared by normalize and dedup)
│   ├── geocode.py              # offline lat/lon -> country, point-in-polygon (RF-37)
│   ├── subprocess_env.py       # sanitized env for system subprocesses (PyInstaller onefile)
│   ├── backoff.py               # exponential_backoff (shared by ws_emsc and supervisor)
│   ├── supervisor.py            # asyncio orchestrator (tasks + backoff restart)
│   ├── ingest/
│   │   ├── __init__.py         # RawMessage (raw wrapper, source→pipeline)
│   │   ├── ws_emsc.py          # WSIngestor (keepalive, reconnection)
│   │   ├── rest_usgs.py        # RESTReconciler (60 s poll, cursor)
│   │   ├── rest_funvisis.py    # FUNVISISPoller (Venezuela-only local coverage, RF-38)
│   │   └── rest_geofon.py      # GEOFONPoller (GFZ Potsdam fdsnws-event, text format, cursor, RF-39)
│   ├── pipeline/
│   │   ├── __init__.py         # pipeline docstring
│   │   ├── normalize.py        # Normalizer (per-source mapping, geo.haversine_km, severity)
│   │   ├── filter.py           # GeoFilter (radius + magnitude, inclusive bounds)
│   │   ├── dedup.py            # Deduplicator (new/update/duplicate)
│   │   └── processor.py        # Processor (pipeline_task: normalize→filter→dedup)
│   ├── notify/
│   │   ├── __init__.py         # notification layer docstring
│   │   ├── presentation.py     # human-readable formatting + severity color (pure)
│   │   ├── toast.py            # desktop-notifier (urgency by severity)
│   │   ├── alert_window.py     # undismissable Tkinter window + policy
│   │   ├── queue.py            # AlertQueue + asyncio↔Tk bridge
│   │   ├── controller.py       # AlertController (queue + window + sound + toast)
│   │   └── sound.py            # audio layer by severity
│   ├── autostart/              # autostart (inside the package: used by the CLI)
│   │   ├── __init__.py         # create_installer(platform) + agent_command()
│   │   ├── linux_systemd.py    # install/uninstall systemd --user
│   │   ├── macos_launchagent.py # LaunchAgent plist (launchctl)
│   │   └── windows_task.py     # scheduled task (schtasks /sc onlogon)
│   ├── state.py                # StateStore (atomic JSON, platformdirs)
│   ├── geoloc.py                # detect_ip_location (RF-33, IP-based fallback)
│   ├── agent_state.py           # AgentState (thread-safe snapshot for the tray, RF-34)
│   ├── tray.py                  # system tray icon (pystray, best-effort, RF-34)
│   ├── logging_conf.py         # structured + rotating logging
│   ├── i18n.py                  # i18n: OS-locale detection + en/es translation catalog (RF-35)
│   └── assets/                 # info/warning/critical.wav, tray_icon.png, countries.geojson (generated)
├── packaging/
│   ├── entrypoint.py            # entry script for PyInstaller (not a pip entry point)
│   ├── vigia-eew.spec           # PyInstaller spec (onefile; .app BUNDLE on macOS)
│   ├── build_linux.sh           # AppImage + .deb/.rpm (fpm)
│   ├── build_windows.ps1        # PyInstaller onefile (.exe)
│   ├── build_macos.sh           # .app → .dmg (codesign/notarize doc)
│   ├── RELEASING.md             # release procedure (versioning, tag, CI)
│   └── apt-r2/                  # apt repo doc/utilities on Cloudflare R2
├── tests/
└── .github/workflows/build.yml # windows/macos/ubuntu matrix → release assets
```

## 2. Phases, tasks, and dependencies

### Phase 0 — SDD (this set) · 🟡 approval gate
| ID | Task | Depends on | Deliverable |
|---|---|---|---|
| F0-1 | PRD, API Spec, Technical Design, Data Model, Implementation Plan | — | `docs/*.md` |
| F0-2 | `ARCHITECTURE.md` with Mermaid diagrams | F0-1 | `ARCHITECTURE.md` |
| F0-3 | **Review and approval** | F0-1, F0-2 | ✅ green light to start coding |

### Phase 1 — Structure + data model
| ID | Task | Depends on | RF |
|---|---|---|---|
| F1-1 | `pyproject.toml` (uv/hatchling, deps, entry point) | F0-3 | RF-26, RF-27 |
| F1-2 | `models.py` (`SeismicEvent`, `AppState`, signatures) | F1-1 | RF-07 |
| F1-3 | `config.py` + `config.toml.example` | F1-1 | RF-24, RF-12 |
| F1-4 | `logging_conf.py` (console + rotating) | F1-1 | RF-25 |
| F1-5 | `state.py` (atomic JSON, platformdirs) | F1-2 | RF-06, RF-10 |
| F1-6 | `geo.py` (`haversine_km`, shared by normalize and dedup) | F1-1 | RF-08 |

### Phase 2 — Ingestion (primary push + backup)
| ID | Task | Depends on | RF |
|---|---|---|---|
| F2-0a | `backoff.py` (`exponential_backoff`, equal jitter, shared by ws_emsc and supervisor) | F1-1 | RF-03, RNF-03 |
| F2-0b | `ingest/__init__.py` (`RawMessage`: raw wrapper, source→pipeline) | F1-2 | RF-07 |
| F2-1 | `ws_emsc.py`: connection, **15 s keepalive**, **backoff reconnection** | F2-0a, F2-0b | RF-01, RF-02, RF-03, RF-04 |
| F2-2 | `rest_usgs.py`: 60 s poll, **persisted cursor**, 429/5xx handling | F2-0b, F1-5 | RF-05, RF-06 |
| F2-3 | `supervisor.py`: asyncio tasks + backoff restart + clean shutdown (SIGINT/SIGTERM) | F2-0a, F2-1, F2-2 | RNF-03, RNF-04 |

### Phase 3 — Normalization, filter, and dedup
| ID | Task | Depends on | RF |
|---|---|---|---|
| F3-1 | `normalize.py`: per-source mapping, severity (uses `geo.haversine_km` from F1-6) | F2-*, F1-6 | RF-07, RF-08, RF-13 |
| F3-2 | `filter.py`: radius + minimum magnitude | F3-1 | RF-12 |
| F3-3 | `dedup.py`: inter-source heuristic, persisted ids, `update` | F3-1, F1-5 | RF-09, RF-10, RF-11 |

### Phase 4 — Notification (core requirement)
| ID | Task | Depends on | RF |
|---|---|---|---|
| F4-5 | `presentation.py`: magnitude/place/distance/depth/local time/source + color (pure) | F3-1 | RF-18, RF-13, RNF-12 |
| F4-1 | `toast.py` with `desktop-notifier` (urgency by severity, isolated failure) | F4-5 | RF-14 |
| F4-3 | `sound.py`: audio by severity (increasing insistence) + WAV assets | F4-5 | RF-17 |
| F4-2 | `alert_window.py`: topmost Tkinter, focus, undismissable, ACKNOWLEDGED | F4-5 | RF-15..RF-19 |
| F4-4 | `queue.py`: queue (one at a time) + in-place `update` + asyncio↔Tk bridge (ADR-006) | F4-2 | RF-20, RF-11 |

### Phase 5 — CLI + simulation mode
| ID | Task | Depends on | RF |
|---|---|---|---|
| F5-a | `pipeline/processor.py`: `pipeline_task` (normalize→filter→dedup→alert) | F3-* | RF-07..RF-13 |
| F5-b | `app.py`: `Application` (ingestion+pipeline+notification wiring, asyncio/Tk threads) + `notify/controller.py` | F2-3, F4-*, F5-a | RF-26, RNF-04 |
| F5-1 | `cli.py`: startup, `--config`, `--check-config`, dispatch to `Application` | F5-b | RF-26 |
| F5-2 | `simulation.py` + `--simulate` (M6.1 La Guaira) | F5-b, F5-1 | RF-21 |

### Phase 6 — Autostart
| ID | Task | Depends on | RF |
|---|---|---|---|
| F6-1 | Linux systemd `--user` (install/uninstall) | F5-1 | RF-22, RF-23 |
| F6-2 | macOS LaunchAgent (install/uninstall) | F5-1 | RF-22, RF-23 |
| F6-3 | Windows scheduled task (install/uninstall) | F5-1 | RF-22, RF-23 |

### Phase 7 — `--simulate` verification on all 3 OSes
| ID | Task | Depends on | CA | Status |
|---|---|---|---|---|
| F7-1 | Validate undismissable alert + sound on Linux | F5-2 | CA-01 | ✅ Verified (real GNOME/Wayland): `--simulate` showed the topmost/undecorated window, triggered sound, and only closed after ACKNOWLEDGED; the process ended cleanly. |
| F7-2 | Validate on Windows | F5-2 | CA-01 | ⏳ Pending — no Windows machine available in this development environment. |
| F7-3 | Validate on macOS (focus/topmost) | F5-2 | CA-01, ADR-003 | ⏳ Pending — no macOS machine available in this development environment. |
| F7-4 | Resilience tests (WS down, 429, invalid JSON, restart) | F2-*, F3-* | CA-02..CA-07 | ✅ `tests/test_resilience.py`: closes at the full-pipeline level (real `Processor`) what F2/F3 already covered per component — CA-02 (real supervised `WSIngestor`), CA-04 (USGS-only alert), CA-05 (end-to-end inter-source dedup), and CA-07 (restart does not re-alert). |

> F7-2/F7-3 require running `vigia-eew --simulate` manually on Windows/macOS and visually
> confirming CA-01 (window in front, focused, sound, only ACKNOWLEDGED closes it). Without
> those machines, Phase 7 remains partially verified: the core (pipeline + resilience) has
> automated cross-platform evidence; the Tkinter frontend only has real evidence on Linux.

### Phase 8 — Packaging and distribution
| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F8-1 | PyPI (uv/hatchling), semantic versioning | F5-* | RF-27 | ✅ Verified: `uv build` produces a wheel+sdist (including `assets/*.wav`); installed in a clean venv, `vigia-eew --check-config` works. `CHANGELOG.md` + `packaging/RELEASING.md` document the process. |
| F8-2 | Windows `.exe` (PyInstaller onefile, no console) | F5-* | RF-28 | 🟡 `packaging/vigia-eew.spec` + `build_windows.ps1` written; the `.spec` was actually tested on Linux (produces a working onefile binary). The `.exe` itself requires running on Windows (PyInstaller doesn't cross-compile) — pending in CI (F8-5) or manually. |
| F8-3 | macOS `.app`→`.dmg` (+codesign/notarization doc) | F5-* | RF-29 | 🟡 `build_macos.sh` written (uses the same `.spec`, with a `BUNDLE` block conditional on `darwin`); codesign/notarization doc without a certificate (out of scope for v1). Requires macOS to run — pending in CI or manually. |
| F8-4 | Linux AppImage + `.deb`/`.rpm` (fpm) + snap doc | F5-* | RF-30 | 🟡 `build_linux.sh` written and syntax-validated; the onefile binary was actually built and run in this environment. AppImage/`.deb`/`.rpm` need `linuxdeploy`/`appimagetool`/`fpm`, not installed here (they are in CI, F8-5) — the script detects them and warns if missing instead of failing. Snap: doc only (out of scope for v1). |
| F8-5 | GitHub Actions matrix → release assets + local scripts | F8-1..F8-4 | RF-31 | 🟡 `.github/workflows/build.yml` written (ubuntu/windows/macos matrix + Release job), YAML syntactically validated. Not executed (requires pushing a `v*` tag on GitHub); installs `fpm`/`linuxdeploy`/`appimagetool` on the ubuntu runner before invoking `build_linux.sh`. |
| F8-6 | Apt repo doc on Cloudflare R2 | F8-4 | RF-32 | ✅ `packaging/apt-r2/README.md`: repo structure, publishing with `reprepro`+`aws s3 sync`, client-side usage. Documented as a future evolution, no bucket or pipeline activated yet. |

> This development environment is Linux with no Windows/macOS available (same limitation as
> Phase 7): F8-2/F8-3 could only be authored and partially validated (the shared `.spec`
> was tested end-to-end on Linux). Full verification of those two binaries remains
> pending on CI (F8-5) or a real machine of the corresponding OS.

> **2026-07-04 update**: release `v0.1.2` ran on real CI (GitHub Actions) and ended in
> `success`, publishing the 7 expected assets (wheel, sdist, `.exe`, `.dmg`, AppImage,
> `.deb`, `.rpm`). F8-2, F8-3, and F8-5 are now **✅ actually verified**, not just
> authored — this document had not been updated until now to reflect that.

### Phase 9 — Automatic IP-based location detection (RF-33)
| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F9-1 | `geoloc.py`: `detect_ip_location` (injectable HTTP client, never raises) | F1-3 | RF-33 | ✅ |
| F9-2 | `models.py`/`state.py`: `DetectedLocation` + cache in `AppState`/`StateStore` | F1-2, F1-5 | RF-33 | ✅ |
| F9-3 | `config.py`: `has_manual_reference` (exposes whether `[reference]` is present in the TOML, no network) | F1-3 | RF-33 | ✅ |
| F9-4 | `app.py`: `Application._resolve_automatic_reference` (cache → geoloc → fallback), only in `run()` | F9-1, F9-2, F5-b | RF-33 | ✅ |
| F9-5 | `cli.py`: passes `manual_reference` to `Application` | F9-3, F5-1 | RF-33 | ✅ |

### Phase 10 — System tray icon (RF-34)
| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F10-1 | `agent_state.py`: `AgentState` (thread-safe snapshot: WS connected, last alert) | F1-1 | RF-34 | ✅ |
| F10-2 | `tray.py`: `build_icon`/`TrayIcon` (pystray, menu, best-effort) + generated icon (`assets/tray_icon.png`) | F10-1 | RF-34 | ✅ |
| F10-3 | `notify/queue.py`: `AlertQueue.pause`/`resume` (doesn't lose events, only delays presentation) | F4-4 | RF-34 | ✅ |
| F10-4 | `notify/controller.py`: exposes `pause`/`resume`/`paused`; updates `AgentState` on show | F10-1, F10-3 | RF-34 | ✅ |
| F10-5 | `ingest/ws_emsc.py`: updates `AgentState` on connect/reconnect | F10-1, F2-1 | RF-34 | ✅ |
| F10-6 | `config.py`: `[notification] tray_icon` (default `true`) | F1-3 | RF-34 | ✅ |
| F10-7 | `app.py`: `_build_tray`/`_toggle_pause`/`_exit_from_tray`/`_edit_config`, only in `run()` | F10-2, F10-4, F10-6, F5-b | RF-34 | ✅ |
| F10-8 | `cli.py`: passes `config_path` to `Application` (so "edit configuration" opens the file currently in use) | F10-7, F5-1 | RF-34 | ✅ |

### Phase 11 — Headless TUI dashboard (RF-36, ADR-013)
| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F11-1 | `tui.py`: `AlertScreen` (`ModalScreen`, non-dismissable — ENTER acknowledges, Escape no-op) + `_AlertHandle` (`.refresh`→`update_data`) | F4-4 | RF-36 | ✅ |
| F11-2 | `tui.py`: `VigiaTuiApp` (status bar, alerts log, `p`/`q` bindings, `on_start` hook, supervisor worker) | F11-1, F1-1 | RF-36 | ✅ |
| F11-3 | `app.py`: `_controller_for_tui`/`_wire_tui`/`run_tui(simulate=...)`/`_inject_simulated_alert` (no toast/tray/bridge) | F11-2, F5-b | RF-36 | ✅ |
| F11-4 | `cli.py`: `--tui` flag, dispatch to `run_tui` (combinable with `--simulate`) | F11-3, F5-1 | RF-36 | ✅ |
| F11-5 | `pyproject.toml`: `textual` dependency (RNF-06 exception) | — | RF-36 | ✅ |

Tests: `tests/test_tui.py` (13, using Textual's headless `App.run_test()` — no `VIGIA_GUI_TESTS`
gate needed) covers compose/status/push/acknowledge/Escape-no-op/refresh/pause/quit and the full
`--simulate --tui` wiring end to end; `tests/test_app.py` and `tests/test_cli.py` cover the
wiring and dispatch. Verified in a real pseudo-terminal (modal renders M 6.1 / La Guaira /
SIMULATED with footer bindings). Gate green: 255 passed, 3 skipped; ruff + mypy strict clean.

### Phase 12 — Country notification filter (RF-37, ADR-014)
| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F12-1 | `geocode.py`: `country_of(lat, lon)` offline point-in-polygon (ray casting + bbox, holes) | F1-3 | RF-37 | ✅ |
| F12-2 | `assets/countries.geojson` + `packaging/build_countries_geojson.py` (Natural Earth 1:110m, reduced) | — | RF-37 | ✅ |
| F12-3 | `config.py`: `[filter] country_filter` (default `false`) + `country` (`"auto"`/ISO-A2) | F1-3 | RF-37 | ✅ |
| F12-4 | `pipeline/filter.py`: `GeoFilter` drops events positively inside another country (offshore kept) | F3, F12-1 | RF-37 | ✅ |
| F12-5 | `app.py`: `_resolve_user_country`/`_build_geo_filter` (fail-safe inert), used by `execute()`/`run_tui()` | F12-3, F12-4, F5-b | RF-37 | ✅ |

Tests: `tests/test_geocode.py` (synthetic polygons + real-asset smokes VE/CO/ocean),
`tests/test_filter.py` (block-list semantics: other-country dropped, same/offshore/disabled
kept), `tests/test_config.py`, `tests/test_app.py` (config-override vs auto-from-reference,
fail-safe). Verified end to end against the real dataset: Caracas kept, Bogotá/Trinidad/Lima
dropped, offshore Venezuela kept. Gate green; ruff + mypy strict clean. No new pip dependency
(bundled data asset; RNF-06 unaffected). Also in this cycle: `subprocess_env.py` fixes the
PyInstaller onefile `LD_LIBRARY_PATH` leak into `systemctl`/`launchctl`/`schtasks`/`xdg-open`/
audio players.

### Phase 13 — FUNVISIS local coverage source (RF-38, ADR-015)

> Documented retroactively: shipped in v0.4.0 ahead of this table being updated, to bring the
> SDD artifacts back in sync with the code (RNF-08). Marked ✅ to match `CHANGELOG.md`.

| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F13-1 | `ingest/rest_funvisis.py`: `FUNVISISPoller` (poll `maravilla.json`, in-memory seen-set seeded on first poll) | F2-0b | RF-38 | ✅ |
| F13-2 | `config.py`: `FUNVISISSource` + `[sources.funvisis]` in `config.toml.example` | F1-3 | RF-38 | ✅ |
| F13-3 | `models.py`: `SeismicEvent.source` gains `"FUNVISIS"` | F1-2 | RF-38 | ✅ |
| F13-4 | `supervisor.py`: wires the FUNVISIS polling task alongside `ws_task`/`rest_task` | F13-1, F2-3 | RF-38 | ✅ |

Tests: unit coverage for `FUNVISISPoller` (seen-set seeding vs. later-poll novelty, HTTP error
handling) plus config validation for `[sources.funvisis]`. Gate green: `pytest`, `ruff check .`,
`mypy src` all pass with FUNVISIS wired in.

### Phase 14 — GEOFON independent global-network source (RF-39, ADR-016)

| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F14-1 | `ingest/rest_geofon.py`: `GEOFONPoller` (poll `fdsnws-event`, `format=text`, pipe-delimited parsing, persisted cursor) | F2-0b, F1-5 | RF-39 | ✅ |
| F14-2 | `config.py`: `GEOFONSource` + `[sources.geofon]` in `config.toml.example` | F1-3 | RF-39 | ✅ |
| F14-3 | `models.py`: `SeismicEvent.source` gains `"GEOFON"` (+ `AppState.cursor_geofon_ms`, `StateStore.update_geofon_cursor`) | F1-2 | RF-39 | ✅ |
| F14-4 | `app.py`: wires the GEOFON polling task alongside the existing ones (supervisor stays source-agnostic) | F14-1, F2-3 | RF-39 | ✅ |
| F14-5 | `pipeline/dedup.py`: cross-source heuristic covers a 4th source without changes (regression tests) | F14-3, F3-3 | RF-09 | ✅ |

Tests: `tests/test_rest_geofon.py` covers the text-format parser (header/row split, non-earthquake
rows skipped, malformed row discarded without aborting the batch, header-less body ignored), cursor
advancement + persistence, and HTTP 204/429/5xx/timeout handling; `tests/test_normalize.py` gains a
GEOFON mapping case (string coercion, `Mw`→lowercase, `Depth/km` column) plus a malformed-value
discard; `tests/test_config.py` validates `[sources.geofon]`; `tests/test_dedup.py` gains the CA-18
regression (a GEOFON report of an already-alerted EMSC/USGS/FUNVISIS event is a duplicate, while a
GEOFON-first event is new); `tests/test_app.py` asserts the `geofon` task wiring. The text-parsing
branch lives in the poller (which builds a `{column: value}` dict per row), so `RawMessage.feature`
stays a dict and `Normalizer._map_geofon` mirrors the other sources' field mapping. Gate green:
327 passed, 3 skipped; ruff + mypy strict clean. No new pip dependency (reuses `httpx`; RNF-06
unaffected).

### Phase 15 — Event freshness & state hygiene (RF-40, RF-41, RF-42, ADR-017, ADR-018)

> Closes 3 gaps found auditing the 4-source implementation against the requirement "show only
> today's earthquakes, first source to report a given quake wins, and don't leak state forever":
> (1) no day-of-event filter existed at all; (2) USGS/GEOFON's first poll (or a poll after a
> stale cursor) could fetch a multi-day backlog; (3) `StateStore.prune()` was dead code — written,
> unit-tested, never called.

| ID | Task | Depends on | RF | Status |
|---|---|---|---|---|
| F15-1 | `config.py`: `Filter.today_only: bool = True`; `config.toml.example` documents `[filter] today_only` | F1-3 | RF-40 | ⏳ |
| F15-2 | `pipeline/filter.py`: `GeoFilter` gains a freshness check — event's `time_utc` converted to `[notification] timezone`'s local day must equal "today" at an **injected clock**'s current time; fail-safe (inert) if the timezone string is invalid | F15-1, F3-2 | RF-40 | ⏳ |
| F15-3 | `app.py`: `_build_geo_filter` passes `self.cfg.notification.timezone` (and the real clock) into `GeoFilter`, mirroring how it already wires the country filter | F15-2 | RF-40 | ⏳ |
| F15-4 | `ingest/rest_usgs.py` + `ingest/rest_geofon.py`: `_build_params` floors the effective `starttime` at 00:00 local time (`[notification] timezone`) whenever the persisted cursor is `None` **or** older than that floor | F15-1, F2-2, F14-1 | RF-41 | ⏳ |
| F15-5 | `pipeline/dedup.py`: `Deduplicator.register()` calls `self._state.prune()` immediately before `save()` | F1-5, F3-3 | RF-42 | ⏳ |
| F15-6 | Tests: `test_filter.py` (freshness pass/discard, injected clock, invalid-timezone fail-safe), `test_rest_usgs.py`/`test_rest_geofon.py` (starttime floored on `None`/stale cursor, untouched when fresh), `test_dedup.py` (`register()` prunes stale entries before persisting), `test_config.py` (`today_only` default/override) | F15-2, F15-4, F15-5 | RF-40, RF-41, RF-42 | ⏳ |

> Design rationale for all 3 items lives in `TECHNICAL-DESIGN.md` ADR-017 (RF-40/RF-41) and
> ADR-018 (RF-42) — including why "local day" and not "UTC day", why the query floor doesn't
> replace the pipeline filter, and why pruning is hooked into `register()` rather than a timer.

## 3. Traceability matrix: RF → component

| RF | Component(s) | Phase |
|---|---|---|
| RF-01..RF-04 | `ingest/ws_emsc.py`, `backoff.py` | F2 |
| RF-05, RF-06 | `ingest/rest_usgs.py`, `state.py` | F2 |
| RF-07 | `pipeline/normalize.py`, `models.py`, `ingest/__init__.py` (`RawMessage`) | F3/F2 |
| RF-08 | `geo.py` (`haversine_km`), `pipeline/normalize.py` | F1/F3 |
| RF-09, RF-10, RF-11 | `pipeline/dedup.py`, `geo.py`, `state.py` | F3 |
| RF-12 | `pipeline/filter.py`, `config.py` | F3 |
| RF-13 | `pipeline/normalize.py`, `notify/sound.py`, `notify/presentation.py` (color) | F3/F4 |
| RF-14 | `notify/toast.py`, `notify/presentation.py` | F4 |
| RF-15..RF-19 | `notify/alert_window.py` | F4 |
| RF-18 | `notify/presentation.py`, `notify/alert_window.py` | F4 |
| RF-20 | `notify/queue.py`, `notify/controller.py` | F4 |
| RF-21 | `simulation.py`, `cli.py` (`--simulate`), `app.py` | F5 |
| RF-22, RF-23 | `autostart/*` | F6 |
| RF-24 | `config.py` | F1 |
| RF-25 | `logging_conf.py` | F1 |
| RF-26 | `cli.py`, `app.py`, `pipeline/processor.py`, `pyproject.toml` | F1/F5 |
| RF-27..RF-32 | `packaging/*`, `.github/workflows/build.yml` | F8 |
| RF-33 | `geoloc.py`, `config.py` (`has_manual_reference`), `state.py`/`models.py` (`DetectedLocation`), `app.py`, `cli.py` | F9 |
| RF-34 | `tray.py`, `agent_state.py`, `notify/queue.py` (pause/resume), `notify/controller.py`, `ingest/ws_emsc.py`, `config.py`, `app.py`, `cli.py` | F10 |
| RF-35 | `i18n.py`, `config.py`, `notify/presentation.py`, `notify/alert_window.py`, `notify/toast.py`, `tray.py` | TBD (placeholder, wiring to be finalized) |
| RF-36 | `tui.py`, `app.py` (`run_tui`/`_wire_tui`/`_controller_for_tui`), `cli.py` (`--tui`), `pyproject.toml` | F11 |
| RF-37 | `geocode.py`, `assets/countries.geojson`, `pipeline/filter.py`, `config.py`, `app.py` (`_build_geo_filter`) | F12 |
| RF-38 | `ingest/rest_funvisis.py`, `config.py`, `models.py`, `supervisor.py` | F13 |
| RF-39 | `ingest/rest_geofon.py`, `config.py`, `models.py`, `state.py`, `pipeline/normalize.py`, `app.py`, `pipeline/dedup.py` | F14 |
| RF-40 | `pipeline/filter.py`, `config.py`, `app.py` | F15 |
| RF-41 | `ingest/rest_usgs.py`, `ingest/rest_geofon.py`, `config.py` | F15 |
| RF-42 | `pipeline/dedup.py`, `state.py` | F15 |

## 4. Test strategy (summary)

| Level | Focus | Covers |
|---|---|---|
| Unit | normalization (EMSC/USGS mapping), haversine, severity, dedup heuristic | RF-07..RF-13 |
| Integration | ingestion with a fake WS server + recorded USGS responses (fixtures) | RF-01..RF-06 |
| Resilience | fault injection: WS shutdown, 429/5xx, invalid JSON, restart | RNF-03, CA-02..CA-07 |
| Unit | freshness filter with an injected clock (today/yesterday/tomorrow, invalid timezone fail-safe), REST `starttime` floor on `None`/stale cursor, `Deduplicator.register()` pruning | RF-40, RF-41, RF-42, CA-19..CA-21 |
| Manual/E2E | `--simulate` on all 3 OSes (undismissable alert, focus, sound) | CA-01 |

> Fixtures: use the real verified events (M4.3 Morón, M4.5 Boca de Aroa) and the simulated M6.1.

## 5. Dependencies (stack)

| Dependency | Use | RF/ADR |
|---|---|---|
| `websockets` | EMSC WS (native keepalive) | RF-01/ADR-009 |
| `httpx` | async USGS/FUNVISIS/GEOFON REST | RF-05/RF-38/RF-39/ADR-009 |
| `pydantic` (v2) | model/config validation | RF-07/RF-24 |
| `desktop-notifier` | cross-platform toast | RF-14 |
| Tkinter (stdlib) | alert window | RF-15/ADR-003 |
| `platformdirs` | state/config paths | RF-06/RF-10 |
| `tomllib` (stdlib) | reads `config.toml` | RF-24/ADR-007 |
| `tzdata`/zoneinfo | America/Caracas time | RF-18/RNF-12 |
| PyInstaller, fpm, linuxdeploy | packaging | RF-28..RF-30 |
| `pystray` | tray icon (best-effort) | RF-34/ADR-012 |
| `Pillow` | tray icon image (`pystray` requirement) | RF-34/ADR-012 |
| `textual` | headless TUI dashboard (`--tui`) | RF-36/ADR-013 |

## 6. Milestones and delivery order

1. **M0**: Phase 0 approved (SDD gate). ← *current status*
2. **M1**: Phases 1–3 (core: ingestion + pipeline) with unit/integration tests green.
3. **M2**: Phases 4–5 (notification + `--simulate`) demonstrable on Linux.
4. **M3**: Phases 6–7 (autostart + verification on all 3 OSes).
5. **M4**: Phase 8 (packaging + CI with release assets).
6. **M5**: Phase 9 (automatic IP-based location detection, RF-33).
7. **M6**: Phase 10 (system tray icon, RF-34).
8. **M7**: Phase 11 (headless TUI dashboard `--tui`, RF-36).
9. **M8**: Phase 12 (country notification filter, RF-37).
10. **M9**: Phase 13 (FUNVISIS local coverage source, RF-38).
11. **M10**: Phase 14 (GEOFON independent global-network source, RF-39).
12. **M11**: Phase 15 (event freshness filter, bounded REST backlog, `prune()` wiring — RF-40, RF-41, RF-42).
