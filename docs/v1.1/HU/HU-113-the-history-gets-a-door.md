# HU-113 · The history gets a door

> Epic **EP-12** · Priority **P0** · Effort S + M · Phase **F9**
> Items: B-44, B-45 · Requirements: REQ-GUI-011..013 · Tasks: T-152..T-155

**As** a user on a desktop where the tray menu does not open,
**I want** to open the history from the command line or the launcher, and move between the screens
inside the window,
**so that** a screen that was built and tested is one I can actually reach.

## Context

The history can be opened from one place: the tray menu (`tray.py` → `Application._open_history` →
`Wiring.open_history`). On GNOME/Wayland that menu may not open. v1.0 met the same problem for the
configuration panel and solved it with `--settings` (REQ-GUI-009, T-150); the history, built two
phases earlier, never got it.

`Application.open_settings()` is eight lines. `open_history()` is its twin.

The second half is navigation. `FletShell` shows one screen and offers no way to another: someone
who opens the panel with `--settings` has to close the window and launch again to see the history.
A navigation bar inside the window removes the dependency on the tray for all three screens.

**What must not move:** the shell's precedence — alert > screen > nothing. Navigation belongs to the
screen. While an alert is up it is not there to be pressed.

## Acceptance criteria

```gherkin
Scenario: CA-113.1 · The history opens without the agent or the tray
  Given a machine with no tray icon available
  When the user runs "vigia-eew --history"
  Then the history screen opens
  And no ingestion starts and no tray icon is created
  And the process ends when the window is closed

Scenario: CA-113.2 · The launcher offers it
  Given the desktop entry installed by a package
  When its declared actions are read
  Then one of them runs "vigia-eew --history"

Scenario: CA-113.3 · A history that cannot be opened says so
  Given a history file written by a newer version of the agent
  When the user runs "vigia-eew --history"
  Then the window says the history is not available and why
  And the configuration and About screens can still be reached

Scenario: CA-113.4 · Every screen leads to the others
  Given the window opened with "vigia-eew --settings"
  When the user chooses the history in the navigation
  Then the history screen is shown
  And choosing the configuration returns to the panel

Scenario: CA-113.5 · An unsaved edit survives the trip
  Given a value edited and not saved in the configuration panel
  When the user goes to the history and comes back
  Then the edited value is still in its field
  And the panel still marks it as unsaved

Scenario: CA-113.6 · Navigation is not there while an alert is
  Given the history screen open and an alert presented over it
  When the window is inspected
  Then it shows the alert and no navigation control
  And no keyboard shortcut changes what the window shows

Scenario: CA-113.7 · The screen comes back as it was
  Given the history screen open with a filter set
  When an alert is presented and then acknowledged
  Then the history screen is shown again with that filter
```

## Definition of done

- [ ] `--history` in `cli.py`, dispatched before the other modes, like `--settings`
- [ ] `Application.open_history()` and a launcher action on every packaged platform
- [ ] Navigation between the three screens, absent while an alert is shown
- [ ] The panel instance survives navigation; nothing unsaved is dropped by switching
- [ ] A screen is told when an alert covers it and when it is back (used by HU-116)
- [ ] `lat.md/notification.md` records that navigation is part of the screen, with backlinks
