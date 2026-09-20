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

[[src/vigia_eew/tray.py#TrayIcon]] runs `pystray` on its own worker thread, leaving Tkinter the
sole owner of the main thread.

Both building and running it are wrapped so failures only log a warning, because two known
platform limitations cannot be fixed from this codebase: GNOME/Wayland without the AppIndicator
extension does not show legacy tray icons, and macOS's Cocoa requires `pystray.run()` on the main
thread, which conflicts with Tkinter.

The agent starting without a visible tray icon is the intended degraded behavior. `pystray` and
`Pillow` are a documented exception to the minimal-dependency rule. See ADR-012.

## Menu callbacks are scheduled by which thread they touch

Callbacks that may touch Tk (`resume` can create a window) are marshalled back with
`root.after(0, ...)`; callbacks that only shell out (`edit_config`) run on the icon's thread.

[[src/vigia_eew/agent_state.py#AgentState]] is the lock-protected snapshot those threads share.
It is process-lifetime only and deliberately not persisted.

## Textual naming hazards

Two method names in the TUI look arbitrary and are not; renaming them "for consistency" silently
breaks rendering.

The alert screen's update method is `update_data`, not `refresh` — `Widget.refresh()` already
exists and takes no arguments. The internal repaint is `_paint`, not `_render`: overriding
Textual's `Widget._render()` hook returns `None` instead of the widget's visual. See ADR-013.
