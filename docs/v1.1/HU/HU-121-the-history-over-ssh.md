# HU-121 · The history over SSH

> Epic **EP-19** · Priority P3 · Effort M · Phase **F15**
> Item: B-53 · Requirement: REQ-HIS-015 `[SHOULD]` · Task: T-176
> **The first thing to be cut.**

**As** an operator of a machine with no display,
**I want** the history list in the terminal dashboard, with the same filters,
**so that** I can tell why that machine did not alert without reading its log.

## Context

`--tui` exists for machines with no display, which is where a queryable history saves the most.

**Only the list.** No map and no playback: they do not fit in a terminal, and v1.0 already fixed
which of the views is the feature.

`HistoryList` imports no toolkit — it decides what is shown and draws nothing — and since HU-114 it
owns the filters and the paging. The terminal frontend reuses it as it is and adds a screen.

It follows the precedent of REQ-GUI-006 (the panel in the TUI), deferred in v1.0 for the same
reason: it is a `[SHOULD]`.

## Acceptance criteria

```gherkin
Scenario: CA-121.1 · The list is in the terminal
  Given the agent running with "--tui"
  When the user opens the history
  Then the list of entries is shown with its filters and its pager

Scenario: CA-121.2 · The same filter gives the same entries
  Given the same history and the same verdict filter
  When it is read in the terminal and in the graphical interface
  Then both show the same entries in the same order

Scenario: CA-121.3 · A history that cannot be opened does not stop the dashboard
  Given a history file that cannot be read
  When the user opens the history in the terminal
  Then it says the history is not available
  And the dashboard keeps working

Scenario: CA-121.4 · An alert takes the terminal
  Given the history list open in the terminal
  When an alert is presented
  Then the alert is shown over the list
  And after it is acknowledged the list is back
```

## Definition of done

- [ ] A history screen in `tui.py` built on `HistoryList`, with a key binding to open it
- [ ] Its own read connection to the store, like the graphical screen
- [ ] A test that compares its rows with `HistoryList`'s for the same query
- [ ] No map, no playback, no import of Flet
