# Architecture

Vigía-eew is a single asyncio process per machine, watching four seismic
networks. This file records the structural decisions: how the process is
shaped, why it has no server component, and why it must never die.

The domain rules live in [[pipeline]], the sources in [[ingestion]], and the
alert contract in [[notification]].

## One agent per machine, no central relay

Each machine runs its own agent and talks to the upstream networks directly.
There is deliberately no central relay in v1.

A relay (one server fanning events out to many desktops) would be less traffic
overall, but it is a single point of failure for a safety tool: if the relay is
down during an earthquake, every user is blind at once. Four independent
sources per machine trades bandwidth for the property that no single outage can
silence everyone. The migration path to a FastAPI relay with WebSocket fan-out
is documented in `docs/API-SPEC.md` §7 and reuses the same internal contract
([[pipeline#SeismicEvent is the only cross-layer payload]]), so adopting it
later would not break the data model.

The consequence accepted here is N connections to EMSC instead of one.

## The supervisor must outlive every failure

[[src/vigia_eew/supervisor.py#Supervisor]] runs each long-lived task (`ws`,
`rest`, `geofon`, `funvisis`, `pipeline`) and restarts it with backoff when it
raises, without taking the process down.

This is the load-bearing resilience decision: a background safety agent that
exits on a transient DNS failure or a malformed payload is worse than useless,
because the user believes they are covered. Every failure mode is therefore
absorbed rather than propagated — a dropped WebSocket reconnects, a 429 honors
`Retry-After` and keeps its cursor, a schema violation discards that one item,
and an exception in any task restarts just that task.

Waits are computed by [[src/vigia_eew/backoff.py#exponential_backoff]], which
is a pure function shared with [[src/vigia_eew/ingest/ws_emsc.py#WSIngestor]]
so reconnect timing is tested without sleeping.

## Failure isolation is a project-wide pattern

Every optional, environment-dependent effect is best-effort: it catches its own
exceptions, logs a warning, and lets the agent continue degraded rather than
not at all.

This applies to the tray icon ([[src/vigia_eew/tray.py#TrayIcon]], which cannot
render under GNOME+Wayland without an extension), native toasts
([[src/vigia_eew/notify/toast.py#Toaster]]), sound
([[src/vigia_eew/notify/sound.py#SoundPlayer]], routinely absent on a headless
box), and IP geolocation
([[src/vigia_eew/geoloc.py#detect_ip_location]], which returns `None` instead of
raising). The rule when adding a new effect: if the platform can refuse it, it
must not be able to stop ingestion.

The alert window itself is the one thing that is *not* best-effort — see
[[notification#The alert is not dismissable by design]].

## Tkinter owns the main thread; asyncio runs beside it

Tkinter must run its event loop on the main thread, and ingestion is asyncio.
The agent therefore runs Tk on the main thread and the asyncio loop on a worker
thread, crossing between them through
[[src/vigia_eew/notify/queue.py#AsyncioTkBridge]] — a thread-safe queue drained
by `widget.after()`.

The inverse arrangement (asyncio on the main thread, Tk on a worker) was
rejected because Tk is not thread-safe and misbehaves subtly rather than
failing loudly. Keeping the crossing to a single bounded object means there is
exactly one place to reason about thread affinity, and shutdown can be
coordinated from it.

Anything reached from another thread that may touch Tk must be scheduled back
with `root.after(0, ...)`; this is why the tray's *resume* callback hops
threads but its *edit config* callback does not.

## The TUI is a second frontend, not a layer on top

`--tui` ([[src/vigia_eew/tui.py#VigiaTuiApp]]) exists so the agent is usable on
a headless server over SSH, where there is no display for the Tkinter window or
the tray icon.

It deliberately does **not** reuse the bridge above. Textual is already
asyncio-native, so the [[src/vigia_eew/supervisor.py#Supervisor]] runs as a
Textual worker on the *same* event loop and
[[src/vigia_eew/pipeline/processor.py#Processor]] calls the controller
directly — no second thread, no queue crossing. The TUI path is genuinely
simpler than the GUI path, and that asymmetry is intentional rather than an
oversight.

What it shares is the effect contract: the same
[[src/vigia_eew/notify/controller.py#AlertController]] is built with
`create_window` pointing at the TUI's modal instead of a Tk window. Toast and
tray are absent in this mode because a headless server has no desktop session
to receive them.

## Dependencies are kept out unless a frontend needs them

The default desktop path is built on the standard library plus the minimum
async stack: Tkinter for the window (bundled with CPython), `websockets` for
the push channel, `httpx` for REST.

Tkinter was chosen over PyQt/PySide because it can do `-topmost`,
`overrideredirect` and `focus_force` at zero install weight; the Qt bindings
buy better aesthetics for 50–100 MB and a licensing question, which is a bad
trade for a tool whose UI is one urgent modal. `websockets` over Tornado for
the same reason — a full framework for one socket is unnecessary.

Three dependencies are documented exceptions, each admitted only for an
optional frontend: `pystray` + `Pillow` for the tray icon, and `textual` for
the TUI. None of them do networking or telemetry. Adding a dependency to the
*core* ingestion path needs a stronger argument than convenience.
