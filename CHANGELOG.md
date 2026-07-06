# Changelog

Todas las versiones siguen [Versionado Semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`).
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Ver el procedimiento
de publicación en `packaging/RELEASING.md`.

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
