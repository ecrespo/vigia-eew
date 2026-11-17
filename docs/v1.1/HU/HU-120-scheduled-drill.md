# HU-120 · The agent tests itself

> Epic **EP-18** · Priority P2 · Effort S · Phase **F16** *(last, cuttable — D-7)*
> Item: B-52 (F-13) · Requirements: REQ-UX-007..009 · Tasks: T-179..T-181

**As** a user whose agent has not alerted in months,
**I want** it to run a drill by itself every so often,
**so that** I know the alert still works on this machine before I need it.

## Context

`--simulate` exists. What is missing is the agent firing it by itself. It is testing the smoke
detector: an agent that goes months without alerting has no other way to show it is alive.

**Off by default.** A product that opens a window that cannot be ignored, without anyone having
asked, is not a good first contact.

**A drill is labelled as a drill**, visibly and without reading the detail — and so is the alert
`--simulate` shows, which is the same thing asked for by hand.

**A drill is never a row of the history.** A simulated event does not go through the pipeline, and
the history is written by the pipeline. That is what lets the table, the map, the playback, the
figures and the export ignore drills without each filtering them out (X-3).

**A drill never displaces or delays a real alert.** REQ-ALE-005 says one alert at a time; this says
which wins.

**Where the record lives** (Data Model delta §4): `state.json`, as `last_drill` — when it was
presented and when it was acknowledged, if it was. It is operating state, not an earthquake, and
E-05 puts operating state in JSON. It is shown on the About screen.

## Acceptance criteria

```gherkin
Scenario: CA-120.1 · A drill that has come due is presented
  Given the scheduled drill enabled with an interval that has elapsed
  When the agent checks
  Then a simulated alert is presented

Scenario: CA-120.2 · Switched off, there is none
  Given the default configuration
  When the agent runs for longer than any interval
  Then no drill is presented

Scenario: CA-120.3 · The last drill can be consulted
  Given a drill that was presented and acknowledged
  When the user opens the About screen
  Then it shows when the last drill took place and that it was acknowledged

Scenario: CA-120.4 · A drill nobody acknowledged is recorded as such
  Given a drill that was replaced by a real alert before being acknowledged
  When the last drill is consulted
  Then it shows when it took place and that it was not acknowledged

Scenario: CA-120.5 · A drill says it is a drill
  Given a drill presented in each language the product offers
  When the alert is looked at without reading its detail
  Then it is labelled as a drill

Scenario: CA-120.6 · A drill is not an earthquake
  Given a drill that was presented and acknowledged
  When the history and its figures are read
  Then no entry presents it as an earthquake
  And no figure counts it

Scenario: CA-120.7 · A drill waits for a real alert
  Given a real alert on screen or queued
  When a drill comes due
  Then the drill is not presented until the queue is empty

Scenario: CA-120.8 · A real alert replaces a drill
  Given a drill on screen
  When a real alert arrives
  Then the real alert is presented without waiting for the drill to be acknowledged

Scenario: CA-120.9 · The manual simulation carries the same label
  When the user runs "vigia-eew --simulate"
  Then the alert is labelled as a drill

Scenario: CA-120.10 · Paused notifications postpone the drill
  Given notifications paused by the user
  When a drill comes due
  Then it is not presented until notifications are resumed
```

## Definition of done

- [ ] `[drill] enabled` (false) and `interval_days` in the schema, the example file and the panel
- [ ] `drill.py`, pure: whether a drill is due, with the clock injected
- [ ] `last_drill` in `state.json`, written atomically like the rest of it
- [ ] The label on every simulated alert, graphical and terminal, in both languages
- [ ] The queue postpones a drill behind a real alert and lets a real alert replace one
- [ ] A test that a drill never reaches the history sink
