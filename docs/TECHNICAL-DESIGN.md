# Technical Design — Vigía-eew

| Field | Value |
|---|---|
| Document | Technical design and architecture decisions (ADRs) |
| Version | 1.0 (draft for review) |
| Status | 🟡 Pending approval |
| Related | `PRD.md`, `API-SPEC.md`, `DATA-MODEL.md`, `ARCHITECTURE.md`, `IMPLEMENTATION-PLAN.md` |

---

## 1. Summary

Vigía is a single long-lived **asyncio process** per machine. A **primary push channel**
(EMSC WebSocket) and a **lightweight safety net** (USGS polling every 60 s) feed an
**internal queue**. A *pipeline* normalizes → filters → deduplicates and, when an event is new
and relevant, delivers it to the **notification layer**, which shows a **non-dismissable alert
window** in addition to a native toast. Critical state (alerted ids, USGS cursor) is
**persisted** to survive restarts.

Guiding principles: **push first** (RF-01), **never die** from transient failures (RNF-03),
**non-dismissable** (RF-19/RNF-05), and **traceability** RF→code (RNF-08).

## 2. Logical architecture (layers)

```
External sources ──▶ Ingestion ──▶ Asyncio queue ──▶ Normalization ──▶ Filter ──▶ Dedup ──▶ Notification
                                                                                  │
                                                                        Persistence (state)
```

| Layer | Component | Responsibility | RF |
|---|---|---|---|
| Ingestion | `WSIngestor` (EMSC) | WS connection, keepalive, reconnection, emit raw messages | RF-01..RF-04 |
| Ingestion | `RESTReconciler` (USGS) | 60 s polling, cursor, emit raw messages | RF-05, RF-06 |
| Normalization | `Normalizer` | Raw→normalized event, distance, severity | RF-07, RF-08, RF-13 |
| Filter | `GeoFilter` | Radius + minimum magnitude | RF-12 |
| Dedup | `Deduplicator` | Cross-source heuristic; updates; persisted ids | RF-09..RF-11 |
| Notification | `Notifier` (toast) + `AlertWindow` (overlay) + `AlertQueue` | Toast + window + queue + sound | RF-14..RF-21 |
| Persistence | `StateStore` | Alerted ids + cursor on disk | RF-06, RF-10 |
| Config | `Settings` (pydantic) | Load/validate `config.toml` | RF-24 |
| Platform | `autostart/` | systemd/LaunchAgent/scheduled task | RF-22, RF-23 |
| CLI | `cli` (`vigia-eew`) | Startup, `--simulate`, autostart | RF-21, RF-26 |

## 3. Concurrency model (asyncio) — RNF-04

Asyncio tasks coordinated by an orchestrator (`Supervisor`):

- **T1 `ws_task`**: keeps the WS alive (keepalive + reconnection), publishes raw messages to
  `raw_queue`.
- **T2 `rest_task`**: 60 s loop; publishes raw messages to `raw_queue`.
- **T3 `pipeline_task`**: consumes `raw_queue` → normalizes → filters → dedups → if applicable,
  `alert_queue`.
- **T4 UI layer**: the GUI (Tkinter) runs on the **main thread**; a thread-safe *bridge* passes
  events from `alert_queue` (asyncio) to the UI (see ADR-006).
- **T5 tray icon** (RF-34, ADR-012): `pystray.Icon.run()` runs on its own **worker thread**
  (neither asyncio nor Tk); its callbacks that touch Tk (pause/resume, quit) are scheduled back
  onto the main thread with `root.after(0, ...)`, the same pattern as the T4 bridge.

Resilience: each *task* is wrapped in a guard that catches exceptions, logs them, and **restarts
the task with backoff** without bringing down the process (a "supervisor that restarts children"
pattern). Clean shutdown via `asyncio` + signals (SIGINT/SIGTERM).

```
Supervisor
 ├─ ws_task ──────┐
 ├─ rest_task ────┼──▶ raw_queue ──▶ pipeline_task ──▶ alert_queue ──▶ UI bridge ──▶ AlertWindow
 └─ watchdog      ┘
```

## 4. Real-time strategy: push-primary / polling-backup

- **Primary (push)**: the WS delivers events with minimal latency (RF-01). A 15 s keepalive
  (RF-02) and perpetual reconnection with backoff (RF-03) guarantee continuity.
- **Backup (polling)**: USGS every 60 s (RF-05) **only** recovers what the WS missed and covers
  small local events. It doesn't compete with the push: low frequency, lightweight.
- **Why not polling as primary**: high latency and unnecessary load; the WS already delivers
  real push.
- **Why USGS via polling and not WS**: USGS doesn't offer a simple public WebSocket (its push
  mechanism is PDL, heavy/Java) → cursor-based polling is the low-cost option (ADR-002).

## 5. Deduplication and handling of `update`

### 5.1 Rules (RF-09..RF-11)
1. **Intra-source dedup by id**: if the `id`/`unid` is already in `alerted_ids`, don't re-alert.
2. **EMSC `update`**: same `unid` already seen → **update** the event (e.g. magnitude) in the
   window if it's on screen/in the queue; **do not** generate a new alert (RF-11).
3. **Cross-source dedup (heuristic)**: two events from different sources are the same earthquake
   if **Δdistance ≤ 100 km** and **Δtime ≤ 90 s** and **Δmagnitude ≤ 0.5** (RF-09). A time
   window of recent events is kept for comparison.
4. **Persistence**: `alerted_ids` and recent "signatures" are saved so they aren't repeated
   after restarts (RF-10).

### 5.2 Pseudocode
```python
def is_duplicate(ev, recent, alerted_ids):
    if ev.id in alerted_ids:
        return True                      # already alerted (same id)
    for r in recent:                     # cross-source heuristic
        if (haversine(ev, r) <= 100 and
            abs(ev.time - r.time) <= 90 and
            abs(ev.mag - r.mag) <= 0.5):
            return True
    return False
```

## 6. Filtering and severity

- **Filter** (RF-12): discard if `distance_km > radius` or `magnitude < min_magnitude`.
- **Severity** (RF-13): configurable thresholds; by default `<4 info`, `4–5.5 warning`,
  `5.5+ critical`. Each level defines the alert's **color** and **sound profile**.
- **Reference point** (RF-12/RF-33): if the user doesn't define `[reference]`, `Application`
  resolves one via IP geolocation before starting the pipeline (details in ADR-011).

## 7. State persistence — RF-06, RF-10

- Format: **JSON** in the user's data directory (`platformdirs`): e.g.
  `~/.local/share/vigia-eew/state.json` (Linux), `%LOCALAPPDATA%` (Windows),
  `~/Library/Application Support` (macOS).
- Content: `usgs_cursor` (epoch ms), `alerted_ids` (pruned by age), `recent_signatures`,
  `detected_location` (cache of the IP geolocation, RF-33).
- **Atomic** writes (write to temp + `os.replace`) to avoid corruption on crash.
- Schema in `DATA-MODEL.md`.

## 8. Error handling and reconnection — RNF-03

| Failure | Strategy |
|---|---|
| WS closed / ping_timeout | Perpetual reconnection with **exponential backoff + jitter** (e.g. 1,2,4,8…≤60 s). |
| USGS 429 | Honor `Retry-After`; skip the cycle; keep the cursor. |
| USGS 5xx / timeout | Warning log; retry on the next cycle. |
| Invalid JSON / schema | Validate with pydantic; discard the item; continue. |
| Total network loss | Both ingestors keep retrying; the process stays alive; once the network returns, USGS reconciles. |
| Exception in a task | The `Supervisor` catches it, logs it, and restarts that task with backoff. |
| UI failure | Isolated from the pipeline; ingestion continues; showing the alert is retried. |
| IP geolocation fails (network/timeout/JSON/status) | `geoloc.py` never raises: it returns `None`; `Application` falls back to the default (Caracas) without blocking startup (ADR-011). |
| Tray icon fails to start (no graphical backend, GNOME/Wayland without the extension, exception from `pystray`) | `TrayIcon` catches the exception **inside its own thread** and logs a *warning*; the agent keeps running normally, without the icon (ADR-012). |

## 9. Logging and observability — RNF-07

- **Structured** logging (key=value / optional JSON) to the **console** and a **rotating file**
  (`logging.handlers.RotatingFileHandler`).
- Logged events: WS connection/disconnection, reconnections and backoff, USGS polls (count,
  cursor), filtered events, alerts shown, and **acknowledgments** (audit trail, OBJ-1).

## 10. Security and privacy — RNF-09
- No API keys; read-only access to public sources; no user data is sent to third parties.
- **Exception** (RF-34, ADR-012): `pystray` + `Pillow` are new dependencies exclusive to the
  tray icon, a documented exception to RNF-06 ("zero extra dependencies" for the default UI).
  They do no networking or telemetry; local GUI only.
- Strict input validation (pydantic) for external messages.
- **Explicit exception** (RF-33, ADR-011): if there is no manual `[reference]`, an IP
  geolocation service is queried (`ipapi.co`) — the source IP is visible to that third party,
  just as in any HTTP request. It's triggered only by the absence of manual configuration
  (never with explicit user data) and can be disabled entirely by setting `[reference]` in
  `config.toml`.

---

## 11. Design decisions (ADRs)

> Short format: context → decision → alternatives considered and rejected → consequences.

### ADR-001 — WebSocket push as the primary channel (not polling)
- **Context**: minimal latency is required (OBJ-2) and no events should be lost (OBJ-3).
- **Decision**: EMSC WebSocket as **primary** (RF-01); USGS polling only as **backup** (RF-05).
- **Alternatives considered and rejected**: *(a)* polling only → high latency and load;
  *(b)* WS only → the WS documents message loss; without a safety net, events would be lost.
- **Consequences**: dual source → need for **cross-source dedup** (ADR-004).

### ADR-002 — USGS via cursor-based polling (not PDL)
- **Context**: USGS doesn't offer a simple public WS; its push mechanism (PDL) is heavy/Java.
- **Decision**: FDSN polling every 60 s with a **persisted cursor** (RF-05, RF-06).
- **Alternatives considered and rejected**: integrating PDL (complexity/JVM, against
  "self-hosted and lightweight").
- **Consequences**: a window of up to ~60 s to recover what the WS missed (acceptable as a
  backup).

### ADR-003 — Tkinter by default for the alert (not PyQt/PySide)
- **Context**: a cross-platform, *topmost*, focus-stealing alert, without heavy dependencies
  (RNF-06).
- **Decision**: **Tkinter** (bundled with CPython, zero extra dependencies). It supports
  `-topmost`, `overrideredirect`, `attributes('-fullscreen')`, `focus_force`, `lift`.
- **Alternatives considered and rejected**: PyQt/PySide (better aesthetics/keyboard handling,
  but +50–100 MB, licensing, more complex packaging). It will only be reconsidered if Tkinter
  fails to reliably deliver "always on top" on some OS. *Re-evaluation trigger*: if focus can't
  be reliably forced on macOS, or on **GNOME/Wayland** where the compositor restricts
  topmost/focus (decision in **ADR-010**).
- **Consequences**: a plainer UI; sound is handled by a separate layer (ADR-005).

### ADR-004 — Heuristic dedup by (distance, time, magnitude)
- **Context**: EMSC and USGS assign different ids to the same earthquake.
- **Decision**: same earthquake if ≤100 km, ≤90 s, ≤0.5 mag (RF-09) + intra-source dedup by id +
  handling of `update` (RF-11).
- **Alternatives considered and rejected**: relying on a shared id (none exists across sources);
  exact matching (fragile).
- **Consequences**: possible false positives/negatives during swarms; configurable thresholds.

### ADR-005 — Decoupled, cross-platform sound
- **Context**: sound must scale with severity and work across 3 OSes (RF-17).
- **Decision**: a dedicated audio layer; a per-OS strategy (playing a bundled WAV; fallback to
  the system bell). Asset selection based on severity.
- **Alternatives considered and rejected**: relying only on the toast's sound (mutable by
  "Do Not Disturb").
- **Consequences**: audio assets must be bundled with the package; the asset path is resolved
  at runtime.

### ADR-006 — Asyncio↔Tkinter bridge (UI on the main thread)
- **Context**: Tkinter requires the main thread; ingestion lives in asyncio.
- **Decision**: run Tkinter's event loop on the main thread and the asyncio loop on a worker
  thread; pass events through a thread-safe queue + `widget.after()` to poll the queue.
- **Alternatives considered and rejected**: running asyncio on the main thread and Tk on another
  (Tk isn't thread-safe).
- **Consequences**: a single, well-bounded integration point; coordinated shutdown of both loops.

### ADR-007 — Config in `config.toml` (pydantic) + `uv`/hatchling tooling
- **Context**: structured config (nested severities) and modern tooling.
- **Decision**: **`config.toml`** read with `tomllib` (stdlib 3.11+) and validated by
  **pydantic** (RF-24); the project is managed with **uv**; built with **hatchling** (RF-27).
- **Alternatives considered and rejected**: `.env` (awkward for nested structures); setuptools
  (more verbose).
- **Consequences**: `tomllib` is read-only (writing config isn't needed in v1).

### ADR-008 — No central relay in v1 (one agent per machine)
- **Context**: avoiding a single point of failure (RNF-02); simplicity for v1.
- **Decision**: each machine runs its own agent. The migration path to a central relay
  (FastAPI) with WS *fan-out* reusing the internal contract is **documented** (API Spec §4).
- **Alternatives considered and rejected**: a central relay in v1 (SPOF, more ops overhead).
- **Consequences**: N connections to EMSC (acceptable); the future evolution doesn't break the
  data model.

### ADR-009 — `websockets` + `httpx` (not Tornado)
- **Context**: EMSC's official example uses Tornado; the target stack is modern asyncio.
- **Decision**: **`websockets`** for WS (native `ping_interval` keepalive) and async **`httpx`**
  for REST.
- **Alternatives considered and rejected**: Tornado (a full framework that's unnecessary),
  `aiohttp` (valid; `httpx` chosen for ergonomics/timeouts).
- **Consequences**: minimal dependencies, idiomatic with asyncio.

### ADR-010 — Decoupled presentation frontend via D-Bus + optional GNOME Shell extension
- **Context**: the core "impossible to ignore" guarantee (OBJ-1, RF-15/16/19) depends on
  *topmost* + focus stealing + no window decoration. Under **Wayland** (GNOME's default today),
  an X11/XWayland app like **Tkinter** **cannot** reliably force `-topmost`, `focus_force`, or
  `overrideredirect`: the compositor controls stacking and focus. This is the *re-evaluation
  trigger* anticipated in ADR-003. The core (ingestion/pipeline/state) is Python and
  cross-platform (RNF-06), and we don't want to lose that.
- **Decision**: decouple **presentation** from the **core**. The Python agent remains the only
  source of truth (ingestion → pipeline → normalized `SeismicEvent`) and publishes alerts over
  an optional **D-Bus channel**; presentation frontends **subscribe** to it.
  - **Default** frontend: the **Tkinter** window (ADR-003), bundled and cross-platform.
  - **Optional GNOME** frontend: a **GNOME Shell extension** (GJS) that listens on the D-Bus
    channel and shows a `ModalDialog` with a real screen/keyboard *grab* — the **most reliable**
    way to be "impossible to ignore" on GNOME/Wayland, by living inside the compositor.
  - The acknowledgment (ACKNOWLEDGED) flows **back** to the agent over D-Bus, so that the state
    and audit trail (`acknowledged_utc`, RF-10) remain in the Python core.
  - **v1: not implemented**; documented as a future evolution. Tkinter remains the default on
    all 3 OSes.
- **Alternatives considered and rejected**:
  - *Rewriting the whole app as a GNOME extension (GJS)*: loses portability (RNF-06) and the
    Python core, and puts the agent inside the shell's process (a risk for 24/7 operation,
    RNF-02/03).
  - *Forcing Tkinter's topmost harder on Wayland*: not reliable; the compositor has the final
    say.
  - *Relying only on the critical toast (`desktop-notifier`)*: mutable by "Do Not Disturb"
    (RF-19).
- **Consequences**:
  - A minimal **D-Bus contract** needs to be defined (reusing the internal `SeismicEvent`, the
    same way as the ADR-008 relay): the agent emits `Alert(event)` and the frontend calls
    `Acknowledge(id)`. The detailed design of this bridge is left as a future item.
  - The `AlertController` gains a second output "backend" (publishing to D-Bus) alongside the
    Tk window; the choice is made per platform/configuration.
  - The distribution gains an optional artifact (extension via extensions.gnome.org or
    bundled), independent of the Python package.

#### Detailed D-Bus contract design (elaboration of ADR-010 — design only, not implemented)

> Elaborates on ADR-010's pending "Option 3". It doesn't change the decision, it makes it
> implementable.

**Bus and names** (D-Bus reverse-DNS convention, user session — not the *system bus*, not root):
- Bus: **session bus** (`DBUS_SESSION_BUS_ADDRESS`), consistent with "unprivileged" (RNF-09).
- Service name: `org.vigia_eew.Agent`.
- Object path: `/org/vigia_eew/Agent`.
- **Versioned** interface (allows breaking changes without ambiguity): `org.vigia_eew.Agent.Alerts1`.

**Surface of the `Alerts1` interface**

| Member | Type | Direction | Payload | Internal equivalent |
|---|---|---|---|---|
| signal `NewAlert` | `(s)` | agent → frontend(s) | `SeismicEvent` as JSON (same schema as API-SPEC §3) | `AlertController._show` |
| signal `AlertUpdated` | `(s)` | agent → frontend(s) | `SeismicEvent` JSON, `action="update"` (RF-11) | `AlertController._update` |
| method `Acknowledge` | `(s) -> (b)` | frontend → agent | event `id` | `AlertQueue.acknowledge` → `AlertController._acknowledged` |
| method `GetActive` | `() -> (s)` | frontend → agent | `""` if there is no active alert, or the current `SeismicEvent` JSON | `AlertController`'s internal state |
| method `Ping` | `() -> (s)` | frontend → agent | agent version (`"1.0"`) | agent-availability detection |

The internal contract (`SeismicEvent`, API-SPEC §3) is reused verbatim, serialized with
`model_dump_json()`: a single `string` argument avoids defining a parallel D-Bus *struct* and
keeps a single source of truth for the schema (the same approach as the ADR-008 relay).

**Fit with `AlertController` (second output backend)**

`AlertController` today directly invokes `create_window` (Tk), `play_sound`, and `send_toast`
as injectable callbacks. The D-Bus bridge is modeled as a **fourth callback of the same kind**
(`publish_dbus: Callable[[SeismicEvent], None] | None`), invoked from `_show` and `_update`
alongside the existing ones — it does **not** replace Tk, it's added on top:

```
_show(ev)      → create_window(...) + play_sound(...) + send_toast(...) + publish_dbus(ev)
_update(ev)    → window.update(...)                                       + publish_dbus(ev)
Acknowledge(id) (incoming) → self._alert_queue.acknowledge(...)   # same path as the Tk window's "ACKNOWLEDGED"
```

The D-Bus service (`org.vigia_eew.Agent`) runs in the agent's same asyncio process (the
`dbus-fast` library, already present as a transitive dependency of `desktop-notifier`);
`Acknowledge` received over D-Bus is dispatched to the correct thread/loop the same way the Tk
window's "ACKNOWLEDGED" click is dispatched today (the same asyncio↔UI bridge from ADR-006, not
a new one).

**Frontend selection by platform/config (RF-22 doesn't apply; this is presentation config)**

- New config (v1 of the design, to be added later to `config.toml`): `[notification] frontend =
  "tk" | "auto"`. Default **`"tk"`** on all 3 OSes (current behavior, unchanged).
- With `"auto"` on Linux: the agent detects GNOME + Wayland (`XDG_CURRENT_DESKTOP` contains
  `"GNOME"`, `XDG_SESSION_TYPE == "wayland"`) **and** that the extension is active, by querying
  `org.freedesktop.DBus.NameHasOwner` for a well-known name that the extension would publish
  (e.g. `org.gnome.Shell.Extensions.VigiaEew`). If both conditions hold, the Tk window is
  **skipped** for that alert (avoiding two non-dismissable overlays competing for focus) and
  only the D-Bus signal is emitted; in any other case (extension absent, other OS, X11), Tk
  remains the only frontend, just as it does today.
- The toast (`desktop-notifier`) and the sound (`sound.py`) are **not** affected by this
  selection: they always keep firing, as they are independent redundant channels (RF-14,
  RF-17).

**Failure isolation (RNF-03 — never die because of this)**

Publishing to D-Bus (or nobody listening) must **never** prevent the Tk window from showing:
the same pattern as `toast.py` (isolated failure, warning log, the alert still gets shown). If
`"auto"` detects the extension but the signal fails to emit (bus down, extension closed between
detection and sending), the agent must **fall back to Tk again** for that specific alert, rather
than assuming it was shown.

**What's left to go from design to code** (out of scope unless explicitly requested):
implementing the D-Bus service (`dbus-fast` `ServiceInterface`), the `publish_dbus` callback and
its wiring in `app.py`/`config.py`, the `"auto"` detection, and — on the other end, outside the
Python package — the GNOME Shell extension (GJS) that consumes the signal and calls
`Acknowledge`.

### ADR-011 — Reference point: manual with automatic IP-based fallback (RF-33)

- **Context**: RF-12 requires a configurable reference point (lat/lon), but until now it was
  **100% manual** (`config.toml`, defaulting to Caracas). A new user who configures nothing ends
  up with a geographic filter centered on a point that isn't theirs, without realizing it.
- **Decision**: if the user does **not** define `[reference]` in `config.toml`, `Application`
  detects the location by IP (`geoloc.py`, endpoint documented in `API-SPEC.md` §4) **exactly
  once**, before starting the pipeline, and persists it in `state.json` (`detected_location`) so
  the lookup isn't repeated on subsequent startups. If a manual `[reference]` already exists, or
  a location is already cached, the API is **never** called. If detection fails (no network,
  timeout, unexpected response), it falls back to the hardcoded default (Caracas) without
  caching the failure, so it can be retried on the next startup.
- **Where the decision lives**: in `app.py` (`Application._prepare`/
  `_resolve_automatic_reference`), not in `config.py`. `config.py` remains a pure TOML
  read/validation function (no networking or state I/O); it only exposes whether `[reference]`
  was present (`has_manual_reference`). `cli.py` computes that boolean and passes it to
  `Application` when constructing it.
- **Why not in `--simulate`**: RF-21 requires simulation mode to work **without a network**;
  that's why `simulate()` never passes `resolve_location=True` to `_prepare`, regardless of
  whether a manual reference exists or not.
- **Alternatives considered and rejected**: (a) real OS-level geolocation
  (CoreLocation/Windows Location API/GeoClue) — much more accurate, but requires three separate
  native integrations and system permissions, against RNF-06 (a single portable Python core);
  (b) detecting and overwriting the reference on **every** startup — rejected because it depends
  on the network on every startup and burns through the free service's quota faster, with no
  real benefit (a machine's location doesn't change between startups).
- **Consequences**: a new optional external dependency (RNF-09, see §10); a new field in the
  persisted state (`DATA-MODEL.md` §2); `geoloc.py` follows the same failure-isolation pattern
  as `notify/toast.py` (never raises, there's always a fallback).

### ADR-012 — Tray icon with `pystray`, separate thread, best effort (RF-34)

- **Context**: the agent runs in the background (autostart) with no persistent UI; the user
  asked for a tray icon to see status, pause notifications, edit the config, and quit without
  depending on the terminal.
- **Decision**: `tray.py` builds a `pystray.Icon` (the only practical cross-platform library for
  this) and runs it on a **separate worker thread** (`TrayIcon.start`), leaving **Tkinter as the
  sole owner of the main thread** (ADR-006 is unchanged). Menu callbacks that may touch Tk
  (`resume` can trigger the creation of a window) are scheduled back onto the Tk thread with
  `root.after(0, ...)`; the ones that don't touch Tk (`edit_config`, which only does
  `subprocess.Popen`/`os.startfile`) run directly on the icon's thread.
- **Shared state**: `AgentState` (new, `agent_state.py`) is a small snapshot protected by a
  `threading.Lock` — `WSIngestor` updates it on connect/reconnect (asyncio thread),
  `AlertController` updates it when showing an alert (Tk thread), and the icon reads it (its own
  thread) for the menu's dynamic text. It isn't persisted: it lives only while the process runs.
- **Pausing without losing events**: `AlertQueue.pause()` only stops
  `_show_next_if_free`; incoming events keep being queued normally. `resume()` drains what
  accumulated — preserving OBJ-3 ("zero lost events") at the cost of delaying presentation
  while paused, a deliberate trade-off against OBJ-1 that the user explicitly asked for.
- **Best effort, isolated from failures** (the same principle as `toast.py`/`geoloc.py`):
  building the icon (`Application._build_tray`) and running it (`TrayIcon._run`, inside its own
  thread) are wrapped in `try/except` blocks that only log a *warning*. This is motivated by two
  known limitations that can't be solved from this codebase: (a) under **GNOME + Wayland**
  without the `AppIndicator`/`KStatusNotifierItem` extension, GNOME Shell doesn't show legacy
  tray icons — the agent still starts, it just isn't visible; (b) on **macOS**, `pystray`
  requires its `run()` to live on the main thread (a Cocoa requirement), which potentially
  conflicts with Tkinter — with no macOS machine available in this environment to validate it
  (the same limitation as F7-2/F7-3), it's left as best effort rather than blocking the design.
- **New dependencies**: `pystray` + `Pillow` — a documented exception to RNF-06 (see §10);
  `Pillow` is required by `pystray`'s API (`Icon(icon=PIL.Image)`), and can't be avoided.
- **Icon artwork**: generated once with Pillow (circle + concentric waves, critical-severity
  color) and committed as `src/vigia_eew/assets/tray_icon.png` — the same approach as the
  `.wav` files from Phase 4 (a generated asset, without keeping the generator script in the
  repo).
- **Consequences**: a new `tray.py` module, a new `agent_state.py`; `WSIngestor` and
  `AlertController` gain an optional `state` parameter; `Application` gains `config_path` so
  that "edit configuration" opens the file actually in use (not always the default).

## 12. Traceability

Every ADR and component references an RF from `PRD.md`. The complete RF→module matrix is in
`IMPLEMENTATION-PLAN.md`. The concrete data structures are in `DATA-MODEL.md`. The external
contracts are in `API-SPEC.md`. The views and diagrams are in `ARCHITECTURE.md`.
