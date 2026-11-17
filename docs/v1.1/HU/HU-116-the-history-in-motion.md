# HU-116 · The history in motion

> Epic **EP-15** · Priority P1 · Effort M–L · Phase **F12**
> Item: B-48 · Requirements: REQ-TLP-001..008 · Tasks: T-163..T-166
> **Starts with a spike** (T-163). Decision **D-8**: the playback advances by earthquake.

**As** a user who wants to understand how the seismicity of my region unfolded,
**I want** to play the history on the map in the order it happened,
**so that** I can tell a swarm from an aftershock sequence and a quiet week from an active one.

## Context

A static map of ninety days answers *"where"*. Playback answers *"in what order"* and *"at what
pace"*, which no table conveys.

**It advances by earthquake, not by clock (D-8).** A step is the next earthquake of the filtered
set. The window is redrawn when a step is taken and not in between. How strongly each earlier
symbol is drawn is worked out at that step from its age in the history's time. Speed is how long a
step stays on screen: in proportion to the real gap to the next earthquake, between a declared
minimum and maximum.

**It is a third reading of one query** — table, map, playback — and reads the per-earthquake
grouping (HU-115), so that no earthquake plays twice.

**Two parts.** A pure function decides what is visible at each step (`notify/timelapse.py`, no
toolkit). A control paints it (`notify/timelapse_view.py`). Everything the requirements promise
about order, seeking, speed and fading is checked on the first, with no screen and no clock.

### The spike comes first

Nobody has measured what one redraw of `flet-map` costs with N symbols — and since HU-114 the
symbols are markers carrying a control, not painted circles. T-163 measures it and writes the
verdict down. Two figures come out: the bound on simultaneous symbols and the shortest step. If
markers are too heavy, the playback draws circles while playing and markers when paused: it needs
no tooltip to play.

## Acceptance criteria

```gherkin
Scenario: CA-116.1 · Nothing appears before it happened
  Given a filtered set of earthquakes
  When any step of the playback is inspected
  Then every visible symbol belongs to an earthquake that happened at or before that step's instant

Scenario: CA-116.2 · One redraw per earthquake
  Given a set of forty earthquakes spread over ninety days
  When it is played from start to end
  Then the map is redrawn forty times

Scenario: CA-116.3 · Pausing freezes what is shown
  Given a playback running
  When the user pauses it
  Then what the map shows does not change until it is resumed

Scenario: CA-116.4 · Seeking and playing agree
  Given a playback
  When the user seeks to an earthquake
  Then the map shows exactly what continuous playback shows on reaching that earthquake

Scenario: CA-116.5 · Speed changes when, not what
  Given the same set played at two speeds
  When the same step is reached in both
  Then both show the same symbols at the same strength

Scenario: CA-116.6 · A step is never too short nor too long
  Given two earthquakes one second apart and two a week apart
  When they are played at any speed
  Then each step stays on screen no less than the minimum and no more than the maximum

Scenario: CA-116.7 · The instant is in view, in local time
  Given a playback on screen
  When any step is shown
  Then the instant of that step is displayed in the configured time zone
  And the period the playback spans is displayed

Scenario: CA-116.8 · The filter governs what is played
  Given a minimum-magnitude filter
  When the playback runs
  Then no earthquake below that magnitude appears
  And changing the filter changes the set being played

Scenario: CA-116.9 · What is recent stands out
  Given the fading interval and the trail switched off
  When a symbol is followed through the steps
  Then it is at its strongest at the step of its own earthquake
  And it never gets stronger afterwards
  And it is gone once the interval has passed
  And with the trail switched on it stays, at its weakest

Scenario: CA-116.10 · An alert interrupts the playback
  Given a playback running
  When an alert is presented and then acknowledged
  Then the alert was presented with all its guarantees
  And the playback is shown again, paused, at the step it was on

Scenario: CA-116.11 · A set too large is declared
  Given a filtered set larger than the bound on simultaneous symbols
  When it is played
  Then a notice says that not everything is shown and how much is
  And the pause control responds

Scenario: CA-116.12 · Playing does not move the map
  Given a playback run from start to end with no user action
  When the map's centre and zoom are compared before and after
  Then they are the same

Scenario: CA-116.13 · Without tiles it says so
  Given no connectivity and no cached tiles
  When the playback is opened
  Then the notice that the map is not available is shown

Scenario: CA-116.14 · Nothing to play
  Given a filter that matches no earthquake
  When the playback is opened
  Then it says there is nothing to play
  And the play control is disabled
```

## Definition of done

- [ ] Spike written up in `10-SPIKE-TIMELAPSE.md` with the two figures and a verdict
- [ ] `notify/timelapse.py` imports no toolkit; its tests need no display and no clock
- [ ] Play, pause, seek, speed and trail controls; the instant and the period always in view
- [ ] The playback reads `HistoryList`'s query; it has no query of its own
- [ ] It pauses when the shell covers the screen (HU-113) and never pans or zooms
- [ ] The bound and the step limits are named constants citing the spike
- [ ] `lat.md/history.md` records D-8 and the two-part split, with backlinks
