# Notification

The product promise is a single sentence: when a relevant earthquake happens,
the user cannot miss it. This file records the decisions that protect that
promise, and the deliberate trade-offs made against it.

What reaches this layer is decided in [[pipeline]]; how the layer is threaded is
in [[architecture#Tkinter owns the main thread; asyncio runs beside it]].

## The alert is not dismissable by design

[[src/vigia_eew/notify/alert_window.py#AlertWindow]] is topmost, undecorated,
steals focus, and closes on one path only: explicit acknowledgement. The TUI's
[[src/vigia_eew/tui.py#AlertScreen]] holds the same contract, with `escape`
bound to an explicit no-op so the usual reflex cannot close it.

Every convenience that normally makes a window polite — Escape, the close
button, click-outside, auto-dismiss on a timer — is a way for a warning to be
cancelled by muscle memory before it has been read. Removing them is the
feature, not an oversight, and any change here needs to preserve "the only exit
is a deliberate acknowledgement."

Acknowledgements are logged, so there is an audit trail of what the user
actually saw.

## One alert at a time, in order

[[src/vigia_eew/notify/queue.py#AlertQueue]] shows exactly one event and holds
the rest in order until it is acknowledged.

During a swarm, stacking modals would produce a pile of windows fighting for
focus, and the user would clear them blindly — the same reflex-dismissal
failure the previous section exists to prevent. Serializing keeps each alert
individually readable and individually acknowledged.

## Pausing delays alerts, it never drops events

`pause()` stops presentation only. Events keep flowing through the pipeline and
accumulating in the queue; `resume()` drains what built up.

This is an explicit trade against the "impossible to ignore" guarantee, made
because users asked to silence alerts temporarily (a meeting, a demo). The
guarantee that is *not* traded away is "no event is lost" — a paused agent
still ingests, dedupes, and records. Pausing must never be implemented as
dropping.

## Sound is its own layer, not the toast's

Audio is played by [[src/vigia_eew/notify/sound.py#SoundPlayer]] from bundled
per-severity assets, with the system bell as fallback — independently of the
native toast.

Relying on the toast's own sound would put the alert's audibility at the mercy
of Do Not Disturb and per-app notification settings, which are exactly the
settings a user turns on when they do not want to be interrupted. A seismic
alert has to survive that. Playback stays best-effort per
[[architecture#Failure isolation is a project-wide pattern]]: a headless box
with no audio device logs and moves on.

## Effects are injected so the contract is testable

[[src/vigia_eew/notify/controller.py#AlertController]] does not create windows,
play sounds, or send toasts. It receives `create_window`, `play_sound`, and
`send_toast` as callbacks.

The rules worth protecting here — one at a time, update in place, acknowledge
before the next, pause without loss — are logic, and they are only testable if
they are not welded to real I/O. This is also what lets the Tkinter and TUI
frontends share one controller: they differ only in which `create_window` is
passed in. Keep new effects on the same footing.

## Local time is a presentation concern

[[src/vigia_eew/notify/presentation.py#format_event]] and its helpers are pure
functions, and they are the only place a UTC instant becomes a local wall-clock
string.

Everything upstream is tz-aware UTC by invariant
([[pipeline#Every timestamp is UTC until the last moment]]). Confining the
conversion to one pure module means the display rule is unit-tested without a
GUI, and no timezone logic can drift into ingestion or dedup. Severity colors
are resolved here too, which is why the TUI can reuse them directly.

## User-facing strings are translated; the codebase is English

Source, comments, and commit messages are English (a project-wide rule), while
anything the user reads goes through [[src/vigia_eew/i18n.py#t]] and is
translated, with the language auto-detected from the OS locale unless
configured.

The English strings in the source are the source of truth; the Spanish
translation ships alongside. Unsupported locales fall back to English rather
than failing. A hardcoded user-visible string is a bug even when it is
English.
