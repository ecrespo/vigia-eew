# PRD — Vigía-eew (Product Requirements Document)

| Field | Value |
|---|---|
| Product | **Vigía** (`vigia-eew`) — desktop seismic alert agent |
| Document version | 1.0 (draft for review) |
| Status | 🟡 Pending approval (SDD phase gate) |
| Date | 2026-06-28 |
| Author | Ernesto Crespo |
| Repository | https://github.com/ecrespo/vigia-eew |
| Methodology | Spec-Driven Development (specs precede code) |

> This PRD is the primary artifact. No application code is written until the full set of SDD
> artifacts (PRD, API Spec, Technical Design, Data Model, Implementation Plan) and
> `ARCHITECTURE.md` are approved. Every requirement has a **traceable ID** that is referenced
> from the rest of the documents and from the code.

---

## 1. Problem

A conventional desktop notification is **dismissible**: it gets silenced by "Do Not Disturb",
closed by an accidental click, or buried behind other windows. In a seismic emergency, that is
exactly what must not happen. The population and operational teams in Venezuela lack a **free,
self-hosted, and robust** tool that guarantees a relevant seismic alert **is seen and
acknowledged**, without depending on a phone, paid services, or API keys.

The project was born after the June 2026 Venezuela earthquake. Depending on the distance to the
epicenter, a real *push*-based alert can arrive **before the most destructive seismic waves**;
and when it doesn't, it still guarantees the alert is not lost and is logged.

## 2. Users and personas

| Persona | Description | Primary need |
|---|---|---|
| **P1 — Humanitarian operator** | Coordinates response at an NGO/civil protection agency. Has a workstation on 24/7. | The alert must interrupt any activity and require explicit acknowledgment; an auditable log. |
| **P2 — Technical citizen** | Advanced user (Linux/Win/macOS) who wants a personal alert on their machine. | Simple installation, autostart, configurable by reference point. |
| **P3 — Fleet administrator** | Deploys the agent across many machines. | Native per-OS packaging, autostart, no single point of failure. |

The primary user for the alert's UX design is **P1 (humanitarian operator)**.

## 3. Goals and success metrics

| ID | Goal | Metric / criterion |
|---|---|---|
| OBJ-1 | Impossible-to-ignore alert | The alert window only closes via the **ACKNOWLEDGED** button (not Esc, not X, not clicking outside). |
| OBJ-2 | Low latency via real push | Time from EMSC message received to window visible ≤ 1 s on typical hardware. |
| OBJ-3 | Zero missed events | Every event within the filter reported by EMSC **or** USGS ends up alerted (push + reconciliation). |
| OBJ-4 | 24/7 robustness | The agent never dies from a transient failure (WS down, 429/5xx, invalid JSON, network). |
| OBJ-5 | Frictionless cross-platform | Runs on Linux, Windows, and macOS; native autostart and installable artifacts. |
| OBJ-6 | Self-hosted and free | No API keys, no paid services; each machine runs its own agent. |

## 4. Use cases

| ID | Use case | Actor | Summary flow |
|---|---|---|---|
| CU-1 | Receive earthquake alert (push) | System/P1 | EMSC pushes `create` → normalize → passes filter → dedup (new) → on-screen alert + sound + toast. |
| CU-2 | Recover a missed event (fallback) | System | USGS FDSN (every 60 s) detects an event the WS didn't deliver → normalize → filter → dedup → alert. |
| CU-3 | Receive a magnitude correction | System | EMSC pushes an `update` for the same `unid` → the displayed event is updated **without** triggering a new alert. |
| CU-4 | Avoid a duplicate alert across sources | System | EMSC and USGS report the same earthquake → the dedup heuristic recognizes it → a single alert. |
| CU-5 | Acknowledge an alert | P1 | The user presses **ACKNOWLEDGED** → the window closes → the acknowledgment is logged → the next one in queue is shown. |
| CU-6 | Queue multiple earthquakes | System/P1 | Several simultaneous events → shown in order, one at a time. |
| CU-7 | Test the alert layer | P2/P3 | Run `vigia-eew --simulate` → injects an M6.1 near La Guaira → verifies the alert without a real earthquake. |
| CU-8 | Configure the filter | P2 | Edit `config.toml` (reference point, radius, minimum magnitude, severities). |
| CU-9 | Install autostart | P2/P3 | Run the OS autostart installer (user systemd / LaunchAgent / scheduled task). |
| CU-10 | Restart without re-alerting | System | After a restart, the persisted state prevents re-alerting already-acknowledged events. |

## 5. Functional requirements (RF)

### 5.1 Ingestion (primary push + fallback)
- **RF-01** — Connect via WebSocket to `wss://www.seismicportal.eu/standing_order/websocket` as the **primary channel** (real push, no high-frequency polling).
- **RF-02** — Send a **keepalive (ping) every ~15 s** over the WS; without a keepalive the socket dies silently.
- **RF-03** — **Perpetual reconnection** with exponential *backoff* upon detecting a WS closure; never remain with the socket down.
- **RF-04** — Process EMSC messages with `action` ∈ {`create`, `update`} and `data` as a GeoJSON Feature.
- **RF-05** — Query **USGS FDSN** over REST as a **low-frequency fallback (every 60 s)** solely to reconcile/recover events not delivered by the WS and to cover small local earthquakes.
- **RF-06** — Maintain a **persisted cursor** ("since the last event seen") for the USGS query.
- **RF-38** — Query **FUNVISIS**'s `maravilla.json` (the Venezuelan national seismic network, no real-time push available) via **low-frequency REST polling (every 60 s)** as a **Venezuela-only local coverage** source, catching the small local earthquakes (M2–3) that EMSC/USGS don't catalog. The endpoint is plain HTTP (FUNVISIS offers no valid HTTPS; the data is public). Only earthquakes appearing **after** the agent starts are alerted — the batch already published at startup seeds an in-memory seen-set instead of triggering alerts.
- **RF-39** — Query **GEOFON** (GFZ Potsdam, Germany)'s `fdsnws-event` REST service as an **additional independent low-frequency polling source (global network)**, providing redundant coverage from a different seismic network than EMSC/USGS, with **no API key required**.

### 5.2 Normalization
- **RF-07** — Normalize EMSC and USGS to a **common event schema**: `id`, `magnitude`, `magType`, `place/region`, `lat`, `lon`, `depth_km`, `time_utc`, `source`, `distance_km` to the reference point.
- **RF-08** — Calculate the `distance_km` between the epicenter and the reference point (haversine).

### 5.3 Deduplication
- **RF-09** — Treat as **the same earthquake** if it matches within **~100 km, ~90 s, and ~0.5 magnitude** across sources.
- **RF-10** — **Persist already-alerted `id`s** so they are not repeated after restarts.
- **RF-11** — Handle a WS `update` (magnitude correction) **without** triggering a new alert (updates the existing event).

### 5.4 Filtering (configurable)
- **RF-12** — Filter by **reference point (lat/lon), radius in km, and minimum magnitude**, all configurable.
- **RF-13** — Classify **severity by magnitude** (e.g. `<4` info, `4–5.5` warning, `5.5+` critical), configurable, changing the alert's **color and sound**.
- **RF-33** — When the user does **not** manually configure `[reference]`, **automatically detect** the geographic reference point via IP geolocation (best effort), cache the result so the lookup isn't repeated on every startup, and **silently fall back** to the default (Caracas) if detection fails, without blocking the agent's startup.

### 5.5 Notification (core requirement)
- **RF-14** — Show a **native OS toast** (informational) via `desktop-notifier` (Linux/Win/macOS).
- **RF-15** — Show an **overlay alert window** always on top (*topmost*), undecorated, large centered overlay or fullscreen.
- **RF-16** — The window **takes focus** when it appears and **re-raises itself** if it loses focus.
- **RF-17** — Play an **alarm sound**, more insistent depending on severity.
- **RF-18** — Display large and legible: **MAGNITUDE**, place/region, **distance** to the reference point, depth, **local time (Venezuela timezone)**, and source.
- **RF-19** — The window **does not close via Esc, the X, or a click outside**; only via the **ACKNOWLEDGED** button (an explicit close, not technically impossible, so as not to lock the user out in case of a bug).
- **RF-20** — **Queue multiple earthquakes** and display them in order.

### 5.6 Test mode
- **RF-21** — `--simulate` flag that **injects a fake event** (e.g. M6.1 near La Guaira) to validate the notification layer on each OS without waiting for a real earthquake.

### 5.7 Autostart
- **RF-22** — Allow **automatic startup at login**: Linux (user systemd), macOS (LaunchAgent/Login Item), Windows (scheduled task at logon).
- **RF-23** — Provide a command/script to **install and uninstall** autostart on each OS.

### 5.8 Configuration, logging, and CLI
- **RF-24** — Configuration in a **`config.toml`** file validated with **pydantic**, with sensible *defaults* (Caracas: lat 10.4806, lon -66.9036).
- **RF-25** — **Structured logging** to console and to a **rotating file**.
- **RF-26** — CLI with a console *entry point* **`vigia-eew`** (subcommands/flags: run, `--simulate`, install/uninstall autostart, config path).

### 5.9 Packaging and distribution
- **RF-27** — Publishable **PyPI** package with `pyproject.toml` (built with **hatchling**, managed with **uv**), semantic versioning.
- **RF-28** — **Windows**: `.exe` with PyInstaller (onefile, no console for the GUI).
- **RF-29** — **macOS**: `.app` bundle packaged into a `.dmg`.
- **RF-30** — **Linux**: AppImage (recommended) + `.deb` and `.rpm` (via `fpm`); snap optional/documented.
- **RF-31** — **Build CI**: GitHub Actions with a matrix (windows/macos/ubuntu-latest) producing all artifacts as *release assets*; plus local scripts (`build_windows.ps1`, `build_macos.sh`, `build_linux.sh`).
- **RF-32** — Document how to serve the `.deb` from a **self-hosted apt repository on Cloudflare R2**.

### 5.10 System tray icon
- **RF-34** — Show a **tray icon** (system tray) while the agent runs, with a menu: **status** (WS connected/reconnecting, last alert), **pause/resume notifications** (without losing events: only delays their presentation), **edit configuration** (opens `config.toml` with the OS's associated app), and **quit**. This is a **best-effort** enhancement: if the graphical backend is unavailable (no display, GNOME/Wayland without a tray extension, etc.), the agent keeps working normally, without the icon. Configurable (`[notification] tray_icon`, default `true`). Not activated in `--simulate` (RF-21).

### 5.11 Internationalization (i18n)
- **RF-35** — All user-facing text (alert window, toast, tray menu) must be internationalized. The language is **auto-detected from the OS locale** by default; a config parameter allows **overriding** it; the initial release supports **English and Spanish**; if the detected or configured language is not supported, the agent **falls back to English**.

### 5.12 Headless terminal dashboard (TUI)
- **RF-36** — Provide a **headless terminal dashboard** (`--tui`) as an alternative frontend to the desktop GUI + tray icon, for running the agent on a **server over SSH with no display**. It shows the live connection status (WS connected/reconnecting) and a log of recent alerts, and presents each relevant event as a **non-dismissable modal** inside the terminal: only an explicit acknowledgment (ENTER) closes it (same "impossible to ignore" contract as RF-19; Escape is disabled). Keyboard shortcuts: pause/resume notifications and quit. Combinable with `--simulate` (`--simulate --tui`) to test the modal without waiting for a real earthquake. In this mode there is **no toast and no tray icon** (no desktop session). The dashboard uses `textual` — a documented exception to RNF-06, the same as RF-34.

### 5.13 Country notification filter
- **RF-37** — Optionally restrict notifications to the user's **own country**: do not notify earthquakes located in a **different** country. To avoid dropping the offshore/coastal earthquakes that matter most (often the most dangerous), the rule is a **block-list**: an event is suppressed only when it falls **positively inside another country**; events over the sea / offshore / of undetermined country are **kept** (still subject to the radius and minimum magnitude of RF-12). The country of each earthquake is determined **offline** from a bundled boundary dataset (no per-event network calls, no new pip dependency). The user's country is derived from the reference point, or set explicitly (`[filter] country`). The feature is **opt-in and off by default** (`[filter] country_filter = false`): being a safety tool, it must never silence a real alert due to a country-detection gap (fail-safe — if the country can't be determined, the filter stays inert).

## 6. Non-functional requirements (RNF)

| ID | Category | Requirement |
|---|---|---|
| RNF-01 | Latency | EMSC received → window visible ≤ **1 s** (P95) on typical hardware. |
| RNF-02 | Availability | **24/7** operation; no single point of failure (each machine, its own agent). |
| RNF-03 | Robustness | The process **does not terminate** due to transient failures (WS down, timeouts, 429/5xx, invalid JSON, network loss). |
| RNF-04 | Concurrency | Based on **asyncio**; ingestion tasks do not block the UI. |
| RNF-05 | "Non-dismissible alert" | The alert cannot be hidden by an accidental click; only an explicit close (RF-19). |
| RNF-06 | Portability | Linux, Windows, macOS; UI defaults to **Tkinter** (zero extra dependencies). Explicit exception (RF-34, ADR-012): the tray icon uses `pystray` + `Pillow` — best effort, never blocks startup if unavailable on the platform. Explicit exception (RF-36, ADR-013): the optional headless dashboard (`--tui`) uses `textual`. |
| RNF-07 | Observability | Structured logs with levels; rotating file; connection/reconnection events logged. |
| RNF-08 | Maintainability/Traceability | Every code component traceable to a PRD RF. |
| RNF-09 | Security/Privacy | No API keys; no user data sent to third parties; read-only access to public sources. Explicit exception: automatic location detection (RF-33) queries an IP geolocation service, and only when the user has not manually set `[reference]` — can be disabled by setting the reference point manually. |
| RNF-10 | Language | Code, comments, and SDD artifacts in English; user-facing text (alert window, toast, tray menu) is internationalized (i18n) with OS-locale detection, a config override, and English/Spanish support, falling back to English for unsupported locales. |
| RNF-11 | Python version | **Python 3.11+** (uses the stdlib's `tomllib`). |
| RNF-12 | Time zone | Local time shown in **Venezuela's time zone** (America/Caracas, UTC-4). |

## 7. Acceptance criteria

| ID | Criterion (verifiable) | Covers |
|---|---|---|
| CA-01 | With `--simulate`, on **all three OSes**, the alert window appears on top, with sound, and **only** closes via ACKNOWLEDGED. | RF-15..RF-21, RNF-05 |
| CA-02 | Killing the WS network makes the agent retry with *backoff* and **reconnect** without intervention, without terminating the process. | RF-03, RNF-03 |
| CA-03 | With no event traffic, the WS stays alive thanks to the **ping every ~15 s** (not closed due to inactivity). | RF-02 |
| CA-04 | An event the WS didn't deliver appears via **USGS** within ≤ 60 s and generates an alert. | RF-05, OBJ-3 |
| CA-05 | The **same** earthquake reported by EMSC and USGS produces **a single** alert. | RF-09, CU-4 |
| CA-06 | An EMSC `update` **updates** the displayed event and does **not** create a new alert. | RF-11, CU-3 |
| CA-07 | After restarting the agent, **already-acknowledged** events **are not re-alerted**. | RF-10, CU-10 |
| CA-08 | Changing `radius`, `minimum magnitude`, and `severities` in `config.toml` changes behavior without touching code. | RF-12, RF-13, RF-24 |
| CA-09 | The time is shown in **America/Caracas** and the distance in km to the reference point. | RF-08, RF-18, RNF-12 |
| CA-10 | Autostart **installs and uninstalls** correctly on each OS. | RF-22, RF-23 |
| CA-11 | CI produces `.exe`, `.dmg`, AppImage, `.deb`, `.rpm`, and the PyPI package as artifacts. | RF-27..RF-31 |
| CA-12 | Without `[reference]` in `config.toml`, the agent detects the location via IP on first startup and **reuses the cache** on subsequent startups without calling the service again; if detection fails, it uses the default (Caracas) without failing to start. | RF-33 |
| CA-13 | Pausing from the tray icon stops showing new alerts without losing them (they are shown on resume); if the icon fails to start, the agent still works the same. | RF-34 |
| CA-14 | With the OS locale set to Spanish, the alert window, toast, and tray menu appear in Spanish; overriding the language in `config.toml` forces the configured language; an unsupported locale (e.g. French) falls back to English. | RF-35 |
| CA-15 | With `--tui` on a headless server, the dashboard shows the WS status and, on a relevant event, a **non-dismissable** modal that only ENTER closes (Escape does not); `--simulate --tui` shows the simulated modal without ingestion. | RF-36 |
| CA-16 | With `country_filter = true` and the user in Venezuela, an earthquake in Colombia/Trinidad within the radius is **not** notified, while an onshore Venezuelan quake and an offshore one near the Venezuelan coast **are** notified; with `country_filter = false` (default) behavior is unchanged. | RF-37 |
| CA-17 | A small (M2–3) Venezuelan earthquake reported only by **FUNVISIS** (not EMSC/USGS) is polled within ≤ 60 s and generates an alert; the batch already present at first startup does **not** trigger alerts. | RF-38, OBJ-3 |
| CA-18 | An earthquake reported by **GEOFON** but not by EMSC/USGS is polled within ≤ 60 s and generates an alert; a GEOFON report of the **same** earthquake already alerted via EMSC/USGS/FUNVISIS produces **no** duplicate alert. | RF-39, RF-09, OBJ-3 |

## 8. Out of scope (v1)

- Capturing phone notifications as a source (the source of truth is **public seismic APIs**).
- Real USGS push via PDL (heavy/Java): **fallback polling** is used instead.
- Central FastAPI relay with WebSocket *fan-out*: **documented as future work**, not implemented in v1 (each machine runs its own agent).
- Presentation frontend via **D-Bus** + **GNOME Shell extension** (modal with real *grab* on Wayland): **documented as future work** (ADR-010), not implemented in v1; the default remains Tkinter.
- Custom seismic prediction or intensity/shaking estimation (MMI/ShakeMap).
- Native mobile app, web dashboard, multi-user/accounts, centralized telemetry.
- Code signing with a paid certificate (the procedure is documented; actual signing depends on having the certificate).

## 9. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| EMSC's WS loses messages or suffers timeouts (documented). | Event not alerted. | USGS fallback + reconciliation with cursor (RF-05, RF-06). |
| OS "Do Not Disturb" silences toasts. | Alert not seen. | *Topmost* overlay window with focus (RF-15, RF-16) in addition to the toast. |
| Aggressive backoff saturates the endpoint. | Blocking/ban. | Exponential backoff with a cap and *jitter* (Technical Design). |
| Field differences between sources (`magtype` vs `magType`). | Poorly normalized data. | Normalizer with explicit per-source mapping (API Spec / Data Model). |
| Gatekeeper/SmartScreen block unsigned installers. | Installation friction. | Document codesigning/notarization and the trust procedure. |
| FUNVISIS/GEOFON endpoints change format or become unreachable (both are third-party, best-effort public services). | Loss of one redundant source; core EMSC/USGS coverage unaffected. | Each source polls independently with its own timeout/backoff; Supervisor restarts a failing poller without taking down the process (RF-38, RF-39). |

## 10. Traceability (summary)

RFs are mapped to components in `IMPLEMENTATION-PLAN.md` (RF→component matrix) and to decisions
in `TECHNICAL-DESIGN.md` (ADRs). Input/output contracts are in `API-SPEC.md`; data structures in
`DATA-MODEL.md`; the system view and diagrams in `ARCHITECTURE.md`.
