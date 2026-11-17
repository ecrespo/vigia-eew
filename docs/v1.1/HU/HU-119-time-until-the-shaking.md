# HU-119 · The alert says when the shaking arrives — or when it did

> Epic **EP-18** · Priority P2 · Effort S · Phase **F16** *(last, cuttable — D-7)*
> Item: B-52 (F-03) · Requirements: REQ-ALE-011..013 · Tasks: T-177, T-178
> Decision **D-9**: 3.5 km/s over the hypocentral distance; worded for the elapsed case.

**As** a user reading an alert,
**I want** to know how long until the shaking reaches me, or how long ago it should have,
**so that** I know whether I am being warned or told.

## Context

The roadmap has promised this since August (F-03). Everything it needs is in `SeismicEvent`.

**The case that happens is the elapsed one.** Measured on three months of local history (P-4): of 588
arrivals within 1 000 km, none was received before its S wave; the 179 alerts came a median of 19.5
minutes late. So the text is designed for *"the shaking should have arrived ≈ 19 min ago"*, and the
countdown is the rare branch — kept, because a faster source would make it the common one.

**The estimate (ADR-039).** S-wave travel time = hypocentral distance ÷ 3.5 km/s, where the
hypocentral distance is √(epicentral distance² + depth²). Without the depth, an earthquake 70 km
under the reference point would read as zero seconds; with it, about twenty.

**It is presented as an estimate.** It carries a mark of approximation in every language, a
remaining time is rounded **down**, and it never shows more precision than a preliminary location
supports. A constant 3.5 km/s runs a few seconds late beyond ~150 km; rounding down errs the safe
way.

**It never conditions the alert.** If the estimate cannot be computed, the alert is presented in
full without that line.

## Acceptance criteria

```gherkin
Scenario: CA-119.1 · With time ahead, a count that decreases
  Given an event whose S wave has not yet reached the reference point
  When its alert is on screen
  Then it shows the approximate seconds remaining
  And the figure decreases while the alert is on screen

Scenario: CA-119.2 · With the time elapsed, how long ago
  Given an event received twenty minutes after its S wave reached the reference point
  When its alert is on screen
  Then it says the shaking should already have arrived, about twenty minutes ago
  And that figure grows while the alert is on screen

Scenario: CA-119.3 · Never a negative time
  Given a count that reaches zero while the alert is on screen
  When the next update is shown
  Then the alert says the shaking should already have arrived
  And no negative figure is ever displayed

Scenario: CA-119.4 · The depth counts
  Given an event directly under the reference point at a depth of 70 km
  When the estimate is computed at its origin time
  Then it is about twenty seconds, not zero

Scenario: CA-119.5 · A remaining time is rounded down
  Given an estimate of 18.9 seconds remaining
  When it is displayed
  Then it shows 18, not 19

Scenario: CA-119.6 · It reads as an estimate in every language
  Given the alert in each language the product offers
  When the line about the shaking is read
  Then it carries a mark of approximation

Scenario: CA-119.7 · Without an estimate, the alert is whole
  Given an event whose origin time is later than the agent's clock
  When its alert is presented
  Then the alert is shown with all its guarantees and without the line about the shaking
  And the log says why the estimate could not be computed

Scenario: CA-119.8 · A revision recomputes it
  Given an alert on screen
  When the network revises the event's location or origin time
  Then the line about the shaking is recomputed from the revised data
```

## Definition of done

- [ ] `shaking.py`, pure: an estimate from an event and an instant, with the clock injected
- [ ] The line in the graphical alert and in the terminal one, updated while on screen
- [ ] Strings in English and Spanish, both with the approximation mark
- [ ] The method and its assumptions in `docs/TECHNICAL-DESIGN.md` (ADR-039) and `lat.md`
- [ ] No dependency added, and no travel-time table (D-9)
