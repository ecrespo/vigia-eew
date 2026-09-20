# Architecture

Vigía-eew must show an alert the user cannot ignore, and must never miss a relevant earthquake.
Every structural decision below follows from those two goals.

Those goals are OBJ-1 ("impossible to ignore") and OBJ-3 ("zero lost events"), constrained by
RNF-06: the core stays a lightweight, portable Python process. Full rationale lives in
`docs/TECHNICAL-DESIGN.md` §11 (ADR-001..ADR-018); this file records the parts an agent needs
before changing anything.

## One agent per machine, no central relay

Each machine connects directly to the upstream networks. A central relay would be less code, but
it would be a single point of failure for a system whose value is availability at one moment.

N connections to EMSC is the accepted cost (RNF-02). The migration path to a relay (FastAPI + WS
fan-out reusing the internal contract) is documented in `docs/API-SPEC.md` §7 and deliberately
does not require a data-model change. See ADR-008.

## Push-primary, polling-backup

EMSC's WebSocket is primary because polling alone gives latency the product cannot afford. It is
not the only channel because EMSC documents that the WebSocket drops messages.

Polling is therefore a safety net, not a competitor: it reconciles what the push may have missed.
The direct consequence is that the same earthquake arrives more than once, which is what makes
cross-source dedup mandatory rather than optional. See ADR-001 and [[pipeline#Deduplication]].

## Supervisor that restarts its children

Ingestion runs as long-lived asyncio tasks under [[src/vigia_eew/supervisor.py#Supervisor]],
which restarts each task individually with exponential backoff instead of letting a failure
propagate.

The invariant is that the process must never die from a transient network or parsing failure — a
crashed agent is indistinguishable, to the user, from an earthquake that never happened. Backoff
is a shared pure helper ([[src/vigia_eew/backoff.py#exponential_backoff]]) so the WebSocket
reconnect loop and the supervisor use identical semantics. See ADR-009 and RNF-03.

## Asyncio and Tkinter split across two threads

Tk's event loop runs on the main thread and asyncio on a worker thread, crossing through one
thread-safe queue polled with `widget.after()`.

The inverse arrangement was rejected because Tk is not thread-safe. The value of this shape is
that there is exactly one integration point between the two worlds
([[src/vigia_eew/notify/queue.py#AsyncioTkBridge]]), so shutdown ordering and error handling only
have to be correct in one place. See ADR-006.

## The TUI is a separate run mode, not a second layer

`--tui` ([[src/vigia_eew/tui.py#VigiaTuiApp]]) exists so the agent can run on a headless server
over SSH. It is simpler than the GUI path on purpose, and the two modes do not compose.

Because Textual is already asyncio-native, this path has no bridge and no extra thread: the
`Supervisor` runs as a Textual worker on the same event loop and the `Processor` calls the alert
controller directly. ADR-006 is untouched. See ADR-013.

## Wayland is the known limit of the "impossible to ignore" guarantee

Tkinter was chosen over PyQt/PySide because it ships with CPython and supports `-topmost`,
`overrideredirect` and `focus_force` at zero dependency cost.

The documented re-evaluation trigger is a compositor that refuses those requests: under
GNOME/Wayland an X11/XWayland client cannot reliably force stacking or focus. ADR-010 designs a
decoupled D-Bus presentation frontend (plus an optional GNOME Shell extension) as the answer; it
is **designed but not implemented**. Anyone tempted to "fix" topmost behavior inside
`alert_window.py` should read ADR-003 and ADR-010 first — the problem is not in this codebase.
See [[notification#Non-dismissable alert contract]].
