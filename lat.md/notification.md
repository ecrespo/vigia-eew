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
