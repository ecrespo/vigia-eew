# Changelog

Todas las versiones siguen [Versionado Semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`).
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Ver el procedimiento
de publicación en `packaging/RELEASING.md`.

## [Sin publicar]

## [1.0.0] - 2026-09-19

The first stable release. What makes it 1.0.0 is not the feature list: it is that
the product now **says where its central promise holds and where it does not**, and
that every claim in this file is checked by something that fails when it stops
being true.

### Added
- **Configuration panel** (REQ-GUI-001..005) — every setting is reachable from the
  tray without opening a text file: 43 fields in 11 collapsible sections, validated
  as you type against the same schema the agent starts with, with per-section and
  whole-file "restore defaults". The controls are **derived from the configuration
  models**, so a field added to the code appears in the panel by itself. The menu
  keeps **both** ways in: the panel and the file, because the file is what lets you
  version it with Git, copy it between machines and edit it over SSH.
- **Writable `config.toml` that survives being written** (REQ-CFG-009..012) — saving
  preserves every comment in the file, writes through a temporary file and an atomic
  rename with the previous version kept as `config.toml.bak`, refuses to overwrite an
  edit made elsewhere while the panel was open, and validates before the disk is
  touched. Only the fields actually changed are written, so `[reference]` stays absent
  and the IP location detection keeps working.
- **Network priority** (REQ-ING-011, REQ-PIP-010, REQ-GUI-008) — each source declares
  a priority, ordered from a list in the panel, and when the same earthquake arrives
  through two networks the **data of the higher-ranked one prevails**, whichever
  arrived first. Until now the fastest network won, which is an accident of latency.
  Priority decides whose data is shown and **never whether to alert**: a network
  nobody ranked still alerts on an earthquake only it catalogued.
- **Event history** (REQ-HIS-001..006) — every evaluated arrival is recorded with its
  verdict and, for a discard, the reason: outside the radius, below the minimum
  magnitude, another country, not from today, already reported by another network.
  A local SQLite file that never leaves the machine, with a versioned schema that
  migrates itself, and retention configurable (90 days by default) applied when the
  agent starts. The history is a **consequence** of an alert, never a condition of
  one: it is written off the path between an arrival and its presentation, and an
  agent that cannot write its history is still an agent that alerts.
- **History window** (REQ-HIS-005, REQ-MAP-001..005) — the record as a filterable,
  sortable table with the reason for each discard in words, and a map of
  OpenStreetMap tiles beside it. Symbols are sized by magnitude and alerts are told
  apart from discards by shape as well as colour. One filter governs both views.
  Tiles are requested **only while the map is open**, cached so a zone already
  visited is not requested again, and the client identifies itself as the usage
  policy requires; `© OpenStreetMap contributors` is on screen wherever a tile is.
  With no connection and nothing cached the map says it is unavailable and the table
  carries on working.
- **Declared scope of the alert guarantee** (REQ-ALE-003) — the README, the tray menu
  and the first line of the log now state whether the "impossible to ignore" alert
  actually holds in this session. Measured, not assumed: GNOME under Wayland does not
  advertise `zwlr_layer_shell_v1`, so **no client can keep that promise there with any
  toolkit** (`docs/v1/10-SPIKE-WAYLAND.md`). REQ-ALE-004 is a `[SHOULD]` for that
  reason, and `-fullscreen` is honoured today as a mitigation.
- **ENTER acknowledges the alert** in the desktop window, as it already did in the
  terminal frontend — and it is what lets the release pipeline drive a real alert
  without a pointer.
- **Declarative source registry** — adding a seismic network is one declaration that
  carries its own translation, instead of three edits in three shapes that nothing
  enforced you had found all of.
- **End-to-end correlation id** — one arrival's journey through the five stages is a
  single search in the log, and a discarded duplicate is linked to the arrival that
  did alert.
- **Development container and contribution guide** (REQ-DEV-001..004) — the
  environment comes up in one step, with a virtual display for the real-window tests.

### Changed
- **BREAKING — minimum Python is now 3.13** (`requires-python = ">=3.13"`,
  REQ-DEP-004). 3.12 entered *security-only* maintenance: it still receives security
  patches but no longer bug fixes, which is not a runtime a project calling itself
  1.0.0 should declare as its floor. Ratified as constitutional amendment E-01.
  **Installs on 3.11 or 3.12 are now refused by the resolver**; this is the moment to
  do it, since after a 1.0.0 the same change would need a major version. The
  declaration is consistent across all five places it lives.
- **Every dependency range is bounded above** except `tzdata`, which is exempt by
  amendment E-04 — its major version is the year of publication, so a ceiling would
  freeze the timezone rules themselves. The Pillow floor is its **security** floor:
  `>=10.0` admitted 34 published advisories.
- **`uv.lock` is versioned**, so a clean install resolves the versions that were
  verified, and the minimum-resolution tree is audited in CI rather than only the
  locked one.
- **The Linux binary declares the base it is built on** (`ubuntu-22.04`, glibc 2.35)
  instead of inheriting whatever the runner happened to be, so the compatibility
  floor stops moving on its own.
- **The quality gate measures all eight dimensions** it claims to: format,
  duplication, cognitive and structural complexity, import boundaries, coverage per
  criticality group, and the drift between the code and its recorded decisions.
  CI also runs the **real-window tests** now, not only the headless ones.

### Fixed
- **Shutdown race** (REQ-OPS-002) — a quit arriving before the worker thread
  published its loop and supervisor left the ingestion tasks uncancelled. Demonstrated
  by a test written to fail first, and a second defect found only by running the
  suite under coverage: `Supervisor.run()` discarded a stop requested before it
  started.
- **No binary is published without having been run** (REQ-OPS-008) — v0.1.x shipped
  twice with a packaging resource that was missing only at runtime. Each of the three
  build jobs now launches what it just built and requires it to present an alert;
  on Linux it also acknowledges it and requires a clean exit.

### Security
- **`anyio` moved to 4.15.1** (REQ-DEP-003) — 4.14.1 carried CVE-2026-63374 (critical:
  IDNA 2003 host-name encoding in `TLSStream` allows potential TLS certificate
  spoofing), CVE-2026-64847 and CVE-2026-63349. It reaches the tree through `httpx`,
  which is how the agent talks to three of its four seismic sources, so the TLS one is
  squarely on the path that matters. Caught by the pre-push audit while cutting this
  release, which is what that gate is for.

## [0.6.0] - 2026-07-17

### Added
- **Event freshness filter** (`[filter] today_only`, RF-40) — the agent now alerts only on
  earthquakes whose origin time falls on the **current local calendar day** (per
  `[notification] timezone`), regardless of which of the 4 sources reports them or when. This
  stops alerts on stale REST backlog or a replayed old signature. On by default; fail-safe
  (inert, never suppresses) if the configured timezone is invalid. Turn it off with
  `today_only = false`.
- **Bounded REST backlog floor** (RF-41) — the USGS and GEOFON pollers now floor their
  effective `starttime` at 00:00 local time today whenever the persisted cursor is `None`
  (fresh install) or older than that floor (a stale cursor after a long outage). This bounds
  how much history a single poll fetches and parses without changing what gets alerted (the
  freshness filter above stays authoritative).

### Fixed
- **Unbounded state growth** (RF-42) — `Deduplicator.register()` now prunes `alerted_ids` /
  `recent_signatures` entries older than 24 h before persisting, so `state.json` no longer
  grows without limit over the agent's lifetime. `StateStore.prune()` already existed and was
  unit-tested but was never invoked from any run path.

### Changed
- New shared module `timeutil.py` centralizes the "local calendar day" / local-midnight
  boundary computation and the `ZoneInfo` fail-safe handling used by both the freshness filter
  and the REST backlog floor. Design rationale in `TECHNICAL-DESIGN.md` ADR-017 (RF-40/RF-41)
  and ADR-018 (RF-42). No new dependency.

## [0.5.0] - 2026-07-06

### Added
- **GEOFON as a fourth ingestion source** (`[sources.geofon]`, RF-39) — an independent
  global seismic network operated by GFZ Potsdam. It adds redundant global coverage from a
  **different network** than EMSC/USGS, so an outage or missed catalog entry at one provider
  no longer leaves the agent blind. Polled every 60 s via its standard FDSN `fdsnws-event`
  service (same family as USGS) with **no API key**; the response is parsed as pipe-delimited
  text (`format=text`), not GeoJSON. Uses a persisted `starttime` cursor like the USGS backup,
  participates fully in cross-source deduplication (a GEOFON report of an already-alerted event
  does not re-alert), and runs as its own supervised, fault-isolated task. Enabled by default;
  turn it off with `[sources.geofon] enabled = false`. New module `ingest/rest_geofon.py`; no
  new dependency (reuses `httpx`).

## [0.4.1] - 2026-07-05

### Fixed
- **Headless import safety (RF-36)**: `vigia-eew --tui` crashed at startup on a host with no
  X display (`Xlib.error.DisplayNameError`) — exactly the headless-server scenario the TUI is
  for. `tray.py` imported `pystray` at module level and pystray connects to its GUI backend at
  import time; `app.py` imports `tray`, so importing the agent required a display. pystray is
  now imported lazily inside `build_icon`, so `vigia_eew.app` (and `--tui`) import with no
  display. Regression-tested (`test_app_imports_without_display`).

### Changed
- Development infrastructure (no runtime effect): GitHub Actions CI on `develop`
  (ruff/mypy/pytest) and a security gate on PRs to `main` (bandit, semgrep, pip-audit,
  gitleaks, trivy), mirrored locally by `.pre-commit-config.yaml`. `main` is now
  branch-protected (PRs + green checks required); releases are cut on `develop` and promoted
  via PR (see `packaging/RELEASING.md`).

## [0.4.0] - 2026-07-05

### Added
- **FUNVISIS as a third ingestion source** (`[sources.funvisis]`, RF-05) — **Venezuela-only**
  local coverage. EMSC/USGS don't catalog the small local Venezuelan earthquakes (M2-3);
  the national network FUNVISIS does. The agent now polls FUNVISIS's `maravilla.json` (its
  web map's GeoJSON; there is no real-time push) so those local events trigger alerts.
  Enabled by default and harmless elsewhere (FUNVISIS reports only Venezuelan events, which
  fall outside a non-VE user's radius). To avoid a startup burst, only earthquakes appearing
  *after* the agent starts are alerted — the batch already published at startup is recorded
  as seen, not alerted. Polled over plain HTTP (FUNVISIS offers no valid HTTPS; the data is
  public). New module `ingest/rest_funvisis.py`; times are converted from Venezuela local
  (VET) to UTC. Turn it off with `[sources.funvisis] enabled = false`.

## [0.3.1] - 2026-07-05

### Changed
- Release pipeline (CI): the wheel/sdist is now published to PyPI from a dedicated
  `publish-pypi` job that runs **only after** the Python package and every native binary
  (`.exe`/`.dmg`/AppImage/`.deb`/`.rpm`) have built successfully, so an irreversible PyPI
  upload never happens on a partially failed release. No runtime code changes — this is the
  first version published to PyPI through the automated pipeline.

## [0.3.0] - 2026-07-05

### Added
- **First-run config seeding** (RF-24): when no `config.toml` exists at the per-OS config
  path, the agent now creates that directory and seeds it from a bundled template on
  startup, so every user gets a documented, editable `config.toml` to customize. The
  template ships inside the wheel and the native artifacts (`.exe`/`.dmg`/AppImage/`.deb`/
  `.rpm`) as a package resource, resolved the same way in editable checkouts, `pipx`
  installs and the PyInstaller-frozen binary. Seeding is idempotent (never overwrites an
  existing file) and best-effort (an `OSError` is logged and the agent starts on defaults
  anyway). The template's `[reference]` section is **commented out**, so seeding preserves
  the IP-based location auto-detection on first run (RF-33). The tray's "Edit
  configuration…" also seeds the full template instead of a stub (RF-34).

### Changed
- `config.toml.example` moved into the package (`src/vigia_eew/config.toml.example`) as the
  single source of truth for both the shipped example and the first-run seed.

## [0.2.1] - 2026-07-05

### Added
- Optional **country notification filter** (`[filter] country_filter`, RF-37): when
  enabled, earthquakes located in a *different* country are not notified; events over the
  sea / offshore / of undetermined country are kept (still subject to `radius_km` and
  `min_magnitude`), so coastal quakes are never missed. The country is determined
  **offline** from a bundled Natural Earth boundary dataset (`assets/countries.geojson`,
  point-in-polygon in pure Python — no new dependency, no per-event network calls). The
  user's country is derived from the reference point or set explicitly (`[filter] country`).
  Opt-in, **off by default**; fail-safe (never suppresses if the country can't be
  determined). New module `geocode.py`.

### Fixed
- Autostart install from the packaged binary printed dynamic-loader errors
  (`systemctl: .../libcrypto.so.3: version 'OPENSSL_3.4.0' not found`) and could silently
  fail: the PyInstaller onefile bundle injects its temp library path into
  `LD_LIBRARY_PATH`, which leaked into spawned system binaries so `systemctl` loaded the
  bundled (older) OpenSSL instead of the system's. System subprocesses
  (`systemctl`/`launchctl`/`schtasks`/`xdg-open`/audio players) are now launched with a
  sanitized environment (`subprocess_env.py`) that restores/removes that injected path.
- `--version` reported a stale `0.1.0` (the hardcoded `__version__` was never bumped past
  the 0.1.0 release). It is now derived from the installed distribution metadata, so it
  always matches the released version.

## [0.2.0] - 2026-07-04

### Changed
- **Breaking**: the entire codebase (source, tests, docs) and `config.toml` are now in
  English (RNF-10 updated). Every Python identifier, module filename, and TOML
  key/section was renamed (e.g. `[referencia]` → `[reference]`, `magnitud_minima` →
  `min_magnitude`, `[fuentes.emsc]` → `[sources.emsc]`, `[notificacion]` →
  `[notification]`, etc. — see `config.toml.example` for the full new schema).
  Existing `config.toml` files must be rewritten with the new keys.

### Added
- Headless TUI dashboard (`--tui`, RF-36): an alternative terminal frontend to the
  desktop GUI + tray icon, for running the agent on a server over SSH with no display.
  Shows the live WS connection status and a log of recent alerts, and presents each
  relevant event as a **non-dismissable** modal inside the terminal (only ENTER
  acknowledges it; Escape is disabled — same contract as RF-19). Keys: `p`
  pause/resume, `q` quit. Combinable with `--simulate` (`--simulate --tui`). No toast or
  tray icon in this mode. New module `tui.py` (built on `textual`) and
  `Application.run_tui()`.
- Internationalization (i18n, RF-35): user-facing text (alert window, toast, tray menu)
  is now translated based on `[notification] language` (`"auto"` detects the OS locale,
  or set `"en"`/`"es"` explicitly). Falls back to English for unsupported locales.
  New module `i18n.py`.
- System tray icon (RF-34): menu with status (WS connected/reconnecting, last alert),
  pause/resume notifications (without losing events — only delays their presentation),
  edit `config.toml` with the OS's associated app, and quit. New toggle
  `[notification] tray_icon` (default `true`). Best-effort: if the graphical backend is
  unavailable (GNOME/Wayland without a tray extension, unvalidated macOS, etc.) the agent
  keeps running normally without the icon. Not activated in `--simulate`. New
  dependencies: `pystray` + `Pillow` (documented RNF-06 exception).

### Fixed
- The "Local time (Venezuela): ..." line of the alert window was clipped against the edge
  (the date was visible but the time was cut off). Cause: the detail `Label` had no
  `wraplength`, so a line wider than the (fixed, non-resizable per RF-15) window was drawn
  outside the visible area instead of wrapping. Added a `wraplength` matching the real
  window width (fixed or fullscreen) in `notify/alert_window.py`.
- After the fix above, content could still be clipped against the **bottom** edge on
  machines with different font/DPI metrics: the window height was a fixed constant (620px)
  that didn't reflect what the content actually needed. The height is now measured with
  `winfo_reqheight()` after packing the content (on the user's real screen) and the window
  is sized to that value (with a 620px visual floor), instead of guessing a constant.

## [0.1.3] - 2026-07-04

### Agregado
- Detección automática del punto de referencia geográfico por geolocalización de IP
  (`geoloc.py`, RF-33) cuando el usuario no define `[referencia]` en `config.toml`. Se
  detecta una sola vez y se cachea en `state.json`; si falla (sin red, timeout, etc.) se
  usa el default (Caracas) sin bloquear el arranque. No se activa en `--simulate` (RF-21
  sigue funcionando sin red).
- `config.toml.example` documenta cómo bajar `magnitud_minima` a un umbral más estricto
  (ej. `3.0`) y cómo desactivar la detección automática fijando `[referencia]` a mano.

### Corregido
- El `.deb` instalado (release v0.1.2) fallaba al arrancar con
  `ModuleNotFoundError: No module named 'desktop_notifier.resources'`. Causa:
  `desktop_notifier.common` carga su ícono default con
  `importlib.resources.files("desktop_notifier.resources")` — una referencia dinámica
  por nombre de módulo que el análisis estático de PyInstaller no detecta, así que ese
  subpaquete (con `python.png`) quedaba fuera del binario. Se agregó
  `collect_data_files("desktop_notifier")` a `datas` y `desktop_notifier.resources` a
  `hiddenimports` en `packaging/vigia-eew.spec`. Verificado localmente: el binario
  onefile de Linux reconstruido ya no lanza el error y llega a mostrar la alerta con
  `--simulate`.

## [0.1.2] - 2026-07-04

### Corregido
- El PNG 1x1 introducido en 0.1.1 era una imagen válida pero de una resolución que
  `linuxdeploy` rechaza (exige una de la lista fija 8x8..512x512). Se reemplaza por
  un PNG **64x64** sólido generado con la stdlib de Python (`struct`+`zlib`, sin
  depender de Pillow). Detectado en el run de CI del tag `v0.1.1`.

## [0.1.1] - 2026-07-04

### Corregido
- `packaging/build_linux.sh` generaba un ícono placeholder **vacío** para el AppImage,
  lo que hacía fallar a `linuxdeploy` (CImg no puede decodificar un archivo de 0 bytes
  como PNG). Se reemplazó por un PNG 1x1 transparente válido. Detectado en el primer
  run real de `.github/workflows/build.yml` (tag `v0.1.0`): PyPI, Windows y macOS
  construyeron bien; solo falló el job de Linux.

## [0.1.0] - 2026-07-04

### Agregado
- Núcleo del agente: ingestión EMSC (WebSocket, push primario) + USGS (REST, respaldo),
  pipeline de normalización/filtro/deduplicación, notificación (ventana no descartable,
  toast, sonido por severidad) y persistencia de estado (Fases 1–4).
- CLI (`vigia-eew`), ensamblaje del agente y modo `--simulate` (Fase 5).
- Autoarranque multiplataforma: systemd `--user` (Linux), LaunchAgent (macOS), tarea
  programada (Windows) vía `--install-autostart`/`--uninstall-autostart` (Fase 6).
- Verificación de resiliencia end-to-end y validación real de `--simulate` en Linux (Fase 7).
- Empaquetado: build de PyPI (wheel/sdist), especificación PyInstaller y scripts de build
  por SO, workflow de CI/CD con matriz de release (Fase 8).

[Sin publicar]: https://github.com/ecrespo/vigia-eew/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/ecrespo/vigia-eew/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ecrespo/vigia-eew/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ecrespo/vigia-eew/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ecrespo/vigia-eew/releases/tag/v0.1.0
