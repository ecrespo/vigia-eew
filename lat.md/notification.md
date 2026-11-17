# Notification

The notification layer is where the product's core promise lives: an alert the user cannot
dismiss by reflex.

[[src/vigia_eew/notify/controller.py#AlertController]] orchestrates three effects — window, sound,
toast — as injectable callbacks, which is what lets the whole layer be tested without a display,
an audio device or a notification daemon.

## Non-dismissable alert contract

The alert window is topmost, undecorated and focus-stealing, and only an explicit acknowledgement
closes it.

`Escape`, the window-manager close button and focus loss are all deliberately non-closing. The
TUI's modal ([[src/vigia_eew/tui.py#AlertScreen]]) binds `escape` to an explicit no-op for the
same reason, so both frontends honor the same contract. Any change that makes an alert easier to
dismiss is a product regression, not a usability improvement. See RF-19 and OBJ-1.

## One alert at a time

[[src/vigia_eew/notify/queue.py#AlertQueue]] shows a single alert and updates it in place when an
`update` arrives for the same event.

Stacking windows during a swarm would produce a pile the user clears without reading — the
opposite of the intent.

## Pausing delays presentation, it never drops events

`AlertQueue.pause()` stops only the "show the next one" step; incoming events keep queuing and
`resume()` drains what accumulated.

This is a conscious trade of OBJ-1 (immediacy) against OBJ-3 (zero lost events) in favor of
OBJ-3, and it was explicitly requested. A pause implementation that discarded events while paused
would be wrong. See ADR-012.

## Sound is its own layer, not the toast's

Severity-scaled audio is played by [[src/vigia_eew/notify/sound.py#SoundPlayer]] from bundled WAV
assets, with the system bell as fallback.

Relying on the toast's own sound was rejected because "Do Not Disturb" silences it — precisely in
the situation where the alert matters most. See ADR-005.

## Tray icon is best effort and must never block startup

[[src/vigia_eew/tray.py#TrayIcon]] runs `pystray` on its own worker thread, leaving Flet's UI
loop the sole owner of the main thread.

Both building and running it are wrapped so failures only log a warning, because two known
platform limitations cannot be fixed from this codebase: GNOME/Wayland without the AppIndicator
extension does not show legacy tray icons, and macOS's Cocoa requires `pystray.run()` on the main
thread, which conflicts with the UI loop.

The agent starting without a visible tray icon is the intended degraded behavior. `pystray` and
`Pillow` are a documented exception to the minimal-dependency rule. See ADR-012.

## Menu callbacks are scheduled by which thread they touch

Callbacks that may touch the UI (opening the panel, pausing) are marshalled back with
`shell.after(0, ...)`; callbacks that only shell out (`edit_config`) run on the icon's thread.

[[src/vigia_eew/agent_state.py#AgentState]] is the lock-protected snapshot those threads share.
It is process-lifetime only and deliberately not persisted.

## A door into every screen that is not the tray

[[src/vigia_eew/app.py#Application]]`.open_history()` runs the history on its own — no ingestion,
no bridge, no tray — and `vigia-eew --history` is that mode.

It is the twin of `open_settings()` ([[configuration#A door into the panel that is not the tray]])
and exists for the same reason: on GNOME/Wayland the packaged agent's tray menu does not open.

v1.0 found that problem for the panel and solved it there. The history had been built two phases
earlier, was tested, met its requirements at module level, and could not be opened on the
maintainer's own desktop. REQ-GUI-011 is the rule that came out of it: **a screen reachable only
from the tray does not exist for that user**, so every screen gets a command-line option and a
launcher action, and `scripts/check_packaging_assets.py` fails a desktop entry that loses one.

`--history` is dispatched before `--settings`. Given both, the history opens and the navigation
leads to the panel; the other order would be as good, and one of them had to be written down.

A history that cannot be read shows a notice with the store's own reason instead of an empty
window. While the tray was the only way in, doing nothing on failure was enough. A window opened
on purpose has to say why it has nothing to show.

## Navigation is part of the screen

[[src/vigia_eew/notify/navigation.py#framed]] puts the bar — history, settings, About — **inside
each screen's view**. [[src/vigia_eew/wiring.py#Wiring]] composes it; the shell never sees it as
anything but part of the screen it was handed.

That placement is the design. [[src/vigia_eew/notify/flet_shell.py#FletShell]] renders the alert
if there is one and the screen otherwise, so a bar that lives in the screen is absent whenever an
alert has the window. A bar owned by the shell would have to be hidden under an alert by a
condition, and a condition is what somebody removes by accident. REQ-GUI-013 is met by where the
control is, not by a rule about when to show it.

Switching screens discards nothing. The panel and the history window outlive a trip to another
screen: an unsaved edit is still in its field, still marked unsaved, and a filter is still set.
That is why there is no "save before leaving?" dialog — it would interrupt a move that loses
nothing.

The destination the user is on is disabled, not only tinted, following the rule the history map
applies to alerts and discards: a difference that survives a screenshot and a reader who cannot
tell two colours apart.

## A screen is told when an alert covers it

[[src/vigia_eew/notify/flet_shell.py#FletShell]] keeps the screen across an alert and renders the
same object afterwards. `show_screen` takes two optional callbacks, `on_covered` and
`on_uncovered`, and calls each once per change.

The shell already preserved the screen; what it did not do was say so. A screen with something
running — the history's playback — needs to stop when the alert takes the window, or a timer that
keeps redrawing would be the one thing still competing with the alert. With the notice it pauses
and is found where it was (REQ-TLP-006).

The notice comes **after** the render, and a callback that raises is logged and swallowed. By the
time a screen hears it has been covered the alert is already on the window, so nothing the screen
does about it can keep the alert off.

A screen opened while an alert is up is born covered. One closed while covered is never told it is
back: there is nobody left to tell.

## Textual naming hazards

Two method names in the TUI look arbitrary and are not; renaming them "for consistency" silently
breaks rendering.

The alert screen's update method is `update_data`, not `refresh` — `Widget.refresh()` already
exists and takes no arguments. The internal repaint is `_paint`, not `_render`: overriding
Textual's `Widget._render()` hook returns `None` instead of the widget's visual. See ADR-013.

## Text from a network is never markup

The place, the region and the identifiers of an earthquake are whatever a network sent, and the
terminal toolkit reads square brackets in a string as markup.

A tag would restyle the screen; an unbalanced one **raises while drawing**. In
[[src/vigia_eew/tui.py#AlertScreen]] that meant an earthquake whose place held a stray `[/x]`
produced no alert at all — the failure Art. 1 exists to rule out, reachable from a feed. So every
widget that shows such text is built with markup off, and the cells of
[[src/vigia_eew/tui.py#HistoryScreen]] are `Text` objects rather than strings. The graphical
frontend is not affected: Flet's `Text` has no markup.

The rule for new terminal widgets: a string that came from outside the program goes in as `Text`
or into a widget with `markup=False`, never as a bare string.

## The alert says when the shaking arrives, or when it did

Under the distance the alert carries one more line: how long until the shaking reaches the
reference point, or how long ago it should have (REQ-ALE-011..013, ADR-039).

[[src/vigia_eew/shaking.py#estimate]] is one velocity over the hypocentral distance: 3.5 km/s
across the epicentral distance and the depth, squared and summed. Without the depth an earthquake
70 km under the reference point would read as zero seconds; with it, about twenty. No travel-time
table and no dependency (decision D-9).

**The case that happens is the elapsed one.** On three months of history no arrival within
1 000 km was received before its S wave; alerts came a median of 19.5 minutes after it. So the
sentence was designed for *"the shaking should already have arrived ≈ 19 min ago"*, and the
countdown is the rare branch — kept, because a faster source would make it the common one. It has
only ever been seen with an injected clock.

**It reads as an estimate.** [[src/vigia_eew/notify/presentation.py#shaking_line]] puts the
approximation mark in every branch and both languages. A time still ahead is whole seconds rounded
**down** — beyond some 150 km the fastest S path runs through the mantle and the model is a few
seconds late, so the safe error is to say less. With under a second left it becomes the elapsed
sentence: never a zero that reads as "now", never a negative figure. Elapsed is seconds, then
minutes, then — beyond two hours, which the ADR did not foresee and USGS's median delay makes
ordinary — hours.

**The event carries an instant, not a sentence.** `AlertData.shaking_arrival` is fixed for an
event; the alert stays on screen, so each frontend recounts against its own clock once a second —
[[src/vigia_eew/notify/alert_window.py#AlertWindow]] on the shell's timer, changing one control's
value and only when the sentence changed, and [[src/vigia_eew/tui.py#AlertScreen]] on Textual's
interval. A revision replaces the instant and the next count uses it.

**It never conditions the alert.** With an origin time ahead of the clock by more than half a
minute, or an input that is not a number, there is no estimate: the alert is whole and lacks the
line, and [[src/vigia_eew/notify/controller.py#AlertController]] logs why.

## The agent tests itself, and says that it is a test

An agent that goes months without alerting has no other way to show it still can, so it can be
told to run a drill every so many days (REQ-UX-007, ADR-040). Off by default.

A product that opens a window that cannot be ignored without anyone having asked is not a good
first contact, hence the default. Switched on, [[src/vigia_eew/drill.py#DrillScheduler]] is one
more supervised task: it waits a minute after the agent starts, then wakes hourly, and offers a
drill when [[src/vigia_eew/drill.py#is_due]] says so. A task and not a UI timer because the
agent's tasks are restarted when they fail and stopped with the rest; a UI timer is neither.

**A drill is the simulated event, and the source says so.** `SeismicEvent.is_drill` is
`source == "SIMULATED"` — no flag to keep in step. Every such alert is labelled as a drill before
anything else on it, in both frontends and both languages, and so is its toast; `--simulate` is
the same thing asked for by hand and carries the same label.

**A drill is never a row of the history.** It is injected at the controller and the history is
written by the pipeline, so the table, the map, the playback, the figures and the export ignore
drills without any of them filtering anything out. A test pins that down.

The scheduler decides *when*; it does not decide *whether*
([[lat.md/notification#A drill never costs a real alert]]). It only **offers**, across to the UI
thread where the controller lives, and a drill nobody took is still due at the next wake.

## A drill never costs a real alert

REQ-ALE-005 says one alert at a time; REQ-UX-009 says which wins.
[[src/vigia_eew/notify/queue.py#AlertQueue]] is the component the guarantee rests on, and this is
the one rule F16 added to it.

**A drill is taken only by an idle queue.** [[src/vigia_eew/notify/queue.py#AlertQueue#offer_drill]]
refuses it — it does not queue it — while an alert is on screen or waiting, and while
notifications are paused. A drill that queued would be shown right behind a real earthquake, or
the instant the user resumed; neither is a moment anybody chose.

**A real alert does not wait behind a drill.** Arriving while one is on screen, it closes the
drill *without acknowledgement* and takes its place. `on_acknowledge` is not called for the drill:
nobody saw it out, and the record says so
([[lat.md/state#The last drill is patched into the file, not saved over it]]). The windows gained
a `close()` for this and nothing else may use it — an alert that can be closed without ENTER is
exactly what the contract above forbids, so it is reachable only through the queue, only for a
drill.

Every queue test that existed before the rule passes unchanged; they are the specification of
what did not move.

## The alert says the time in the configured zone

`[notification] timezone` is the one zone every time on screen is said in, and the alert reads
it like everything else does.

It did not, until v1.1.0. The key governed the freshness filter, the history, its figures and the
About screen, but [[src/vigia_eew/wiring.py#Wiring#build_controller]] built the controller — and
the toaster — without it, and both fell back to their default, Caracas. Nobody outside UTC-4 had
looked: the alert said *Local time* and was four hours off in Madrid. The tests on the controller
passed a zone by hand, which is why none of them saw it; the ones added with the fix go through
the wiring.

**And it says which zone.** "Local time" is only local to whoever configured it, so the alert
names it: `2026-06-28 15:39:00 CEST (Europe/Madrid)`.
[[src/vigia_eew/notify/presentation.py#zone_abbreviation]] is computed at the earthquake's own
instant, because the letters change with daylight saving. Many zones have no letters — the tz
database gives Caracas `-04` — and a bare `-04` after a time reads as a mistake, so those are
said as an offset: `UTC-04:00`. The window and the terminal show abbreviation and name; the
toast, being one line, the abbreviation alone. A name that did not resolve is not shown beside a
time that is in UTC.

Internally every instant stays UTC; the conversion happens once, in
[[src/vigia_eew/notify/presentation.py#format_moment]], which is fail-safe: a zone nobody knows
shows UTC rather than costing the alert.
