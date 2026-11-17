# PRD delta — Vigía-eew v1.1

> Artifact 02 of the v1.1 kit · Notation: **EARS** · 2026-11-16 · Base commit: `bb58be8`
> Base documents this one extends: [`docs/sdd/specs/01-PRD.md`](../sdd/specs/01-PRD.md) and
> [`docs/v1/02-PRD-DELTA.md`](../v1/02-PRD-DELTA.md)

## 1. Scope

**31 new requirements**, and **one inherited requirement whose criterion is strengthened**.

| Origin | Count | What they are |
|---|---|---|
| Inherited and strengthened | 1 | REQ-HIS-005: met in the store, not in the interface |
| New in this delta | 31 | Access, full query, per-earthquake view, timelapse, recovery, figures, countdown, drill |
| **Total in scope** | **32** | |

The v1.0 requirements this delta does **not** touch — REQ-HIS-001..004, REQ-HIS-006 and
REQ-MAP-001..005 — are not repeated. They stand as written and several new ones rest on them; where
that is so, the requirement is cited rather than restated.

### Notation

EARS keywords in English: **THE SYSTEM SHALL** (ubiquitous), **WHEN … THE SYSTEM SHALL**
(event-driven), **WHILE …** (state-driven), **WHERE …** (optional feature), **IF … THEN THE SYSTEM
SHALL** (unwanted behaviour). `[MUST]` requirements use SHALL; `[SHOULD]` ones use SHOULD.

### Identifier convention

`REQ-{AREA}-{NNN}`, canonical regular expression `REQ-[A-Z]{2,3}-\d{3}` — the base PRD's own.

| Area | Range this delta uses | Why |
|---|---|---|
| GUI | **011-013** | The v1.0 delta reaches GUI-010 |
| HIS | **007-015** | The v1.0 delta reaches HIS-006 |
| MAP | **006-007** | The v1.0 delta reaches MAP-005 |
| ALE | **011-013** | The base PRD reaches ALE-010 |
| UX | **007-009** | The base PRD reaches UX-006 |
| **TLP** | 001-008 | **New area**: time-based playback of the history |
| **EST** | 001-003 | **New area**: figures from the history |

Ranges checked against the repository on 2026-11-16: the highest number in use for each area across
`docs/` and `src/` is GUI-010, HIS-006, MAP-005, ALE-010 and UX-006. `TLP` and `EST` appear in no
file.

---

## 2. Inherited and strengthened requirement

### REQ-HIS-005 `[MUST]` — The history is queried by the criteria that matter

**The wording does not change.** It says that when the user queries the history, the system shall
allow filtering by date range, magnitude, distance, verdict and source network.

**What changes is what it is verified against.** Its original criterion — a query by minimum
magnitude and date range returns exactly the entries that satisfy both — can be met, and was met,
by a test on `HistoryStore.query`. The interface in front of the user offers magnitude and verdict,
and nothing else.

*Verifiable criterion added:* **each of the five criteria can be set from the history screen**,
without editing a file or writing a query. REQ-HIS-007 develops it.

*Lesson noted for the Analyze:* a requirement worded in terms of the user was verified in terms of
the module. The criterion said "a query" and did not say who makes it. · **B-46**

---

## 3. REQ-GUI — Access and navigation *(extends)*

### REQ-GUI-011 `[MUST]` — The history is reachable without the tray *(ubiquitous)*
THE SYSTEM SHALL offer at least one way to open the history screen that does not depend on the tray
icon: a command-line option, and an action on the application launcher entry of every packaged
platform.

*Verifiable criterion:* `vigia-eew --history` opens the history screen without starting the agent
or the tray, and ends when it is closed; the desktop entry the packages install declares an action
that invokes it.
*Rationale: it is REQ-GUI-009 applied to the screen that was left out. On GNOME/Wayland the tray
menu may not open, and a screen reachable only from there does not exist for that user.* · **B-44**

### REQ-GUI-012 `[MUST]` — Every screen leads to the others *(event-driven)*
WHEN the user has a screen open — configuration, history or About — THE SYSTEM SHALL let them move
to any of the others without closing the window or resorting to the tray or a terminal.

IF the user switches screens with unsaved configuration changes, THEN THE SYSTEM SHALL NOT discard
them unless the user decides so.

*Verifiable criterion:* opening with `--settings`, the history can be reached and returned from; a
value edited and not saved in the panel is still there on return, or the user was asked before
losing it.
*Rationale: the second clause exists because today the problem cannot arise — there is no way to
switch screens — and with this requirement it can.* · **B-45**

### REQ-GUI-013 `[MUST]` — Navigation never competes with an alert *(unwanted behaviour)*
IF an alert is on screen, THEN THE SYSTEM SHALL NOT show the navigation, and SHALL NOT let a
navigation action hide, displace or close the alert.

*Verifiable criterion:* with an alert presented, no navigation action — by control, by keyboard or
by a second command-line invocation — changes what the window shows; once it is acknowledged, the
screen that was there returns.
*Rationale: Art. 1. The alert > screen > nothing precedence is v1.0's and this delta inherits it
without exception. Adding controls to the window is the easiest way to break it by accident.* ·
**B-45**

---

## 4. REQ-HIS — Event history *(extends)*

### REQ-HIS-007 `[MUST]` — Every history filter is in the interface *(ubiquitous)*
THE SYSTEM SHALL offer on the history screen a control for each criterion of REQ-HIS-005: date
range, minimum magnitude, maximum distance, verdict and source network. The lists of networks and
of verdicts SHALL be those present in the history.

*Verifiable criterion:* with a date range and a network set, the table shows exactly the entries
the store returns for that same query; a network absent from the history is not offered as a filter.
*Rationale: the store already does it. What is missing is the controls. The verdicts are listed
from the history, like the networks, so that a verdict added later — REQ-HIS-011's — needs no change
here.* · **B-46**

### REQ-HIS-008 `[MUST]` — Every entry that matches the filter can be reached *(event-driven)*
WHEN the number of entries matching the filter exceeds what the table shows at once, THE SYSTEM
SHALL let the user go through all of them, and SHALL state which stretch is on screen and out of
how many.

*Verifiable criterion:* with more entries than one page, the last entry of the set is reached by
moving forward; the status text gives the stretch and the total, and the total equals the store's
count.
*Rationale: today the table draws 150 of up to 500 loaded and there is no way to see the rest. A
history that hides rows without saying which does not answer "why was I not warned?" for those
rows.* · **B-46**

### REQ-HIS-009 `[MUST]` — An earthquake can be read as one earthquake *(event-driven)*
WHEN the user consults the history in the per-earthquake reading, THE SYSTEM SHALL show a single
entry for each earthquake, with the data of the arrival that prevailed, and SHALL let every arrival
of that earthquake be consulted from it.

THE SYSTEM SHALL keep the per-arrival reading. Neither reading SHALL modify or delete rows.

*Verifiable criterion:* an earthquake recorded from two networks appears once in the per-earthquake
reading and twice in the per-arrival one; the file's row count is the same before and after
switching between them.
*Rationale: one row per arrival is right for storing and wrong for drawing. An earthquake painted
twice at the same point looks like a bigger one, or like two.* · **B-47**

### REQ-HIS-010 `[MUST]` — The history can be completed from the catalogue *(event-driven)*
WHEN the user asks to recover a period, THE SYSTEM SHALL query the catalogue of the configured
networks that allow it, and SHALL record in the history the earthquakes of that period that were
not already there.

THE SYSTEM SHALL report which configured networks do **not** support recovery.

*Verifiable criterion:* on an empty history, recovering the last 30 days leaves entries from that
period; the outcome names the networks nothing could be recovered from, and why.
*Rationale: the history only knows what the agent saw while running. FUNVISIS offers no query by
date, and staying silent about it would make an incomplete history look complete. EMSC, USGS and
GEOFON do offer one — EMSC's was verified on 2026-11-16 (P-3).* · **B-49**

### REQ-HIS-011 `[MUST]` — What is recovered is not mistaken for what was evaluated, and never alerts *(unwanted behaviour)*
IF an entry comes from a recovery, THEN THE SYSTEM SHALL record it with that provenance, SHALL show
it distinguishably from alerted and discarded entries in the table, on the map and in playback, and
SHALL NOT present an alert, a sound or a notification for it.

*Verifiable criterion:* after recovering a period that holds earthquakes inside the radius and
above the minimum magnitude, no alert is presented; no recovered entry has the verdict "alerted" or
"discarded"; the verdict filter can isolate them.
*Rationale: they were not evaluated. Giving them a verdict would falsify the question the history
exists to answer — the honest answer for those rows is "the agent was not watching". And an
earthquake from a month ago cannot open a window: RF-40 stands without exception.* · **B-49**

### REQ-HIS-012 `[MUST]` — Recovery is bounded, repeatable and isolated *(ubiquitous)*
THE SYSTEM SHALL limit how far back a recovery can ask to the retention that applies to recovered
entries (REQ-HIS-013); SHALL produce the same history when the same recovery is repeated; and SHALL
carry on with the remaining networks when one fails.

IF the history already holds an entry the agent evaluated for the same earthquake, THEN the
recovery SHALL NOT replace it or alter its verdict.

*Verifiable criterion:* repeating a recovery does not change the row count; asking for a period
that reaches further back than the retention is refused, naming the limit; with one network down,
the others are recovered and the failure is logged; an alerted row is still alerted after its
period is recovered.
*Rationale: Art. 3 for one network failing. The bound is the retention because recovering what the
next startup would delete is not a feature. The last clause protects the most valuable datum in the
history: what the agent decided at the time.* · **B-49**

### REQ-HIS-013 `[MUST]` — Recovered entries have their own retention *(state-driven)*
WHILE the history holds recovered entries, THE SYSTEM SHALL apply to them a retention of their own,
declared and configurable separately from that of the entries the agent evaluated, with a default of
**365 days**.

THE SYSTEM SHALL keep applying the existing retention — 90 days by default — to the entries the
agent evaluated.

*Verifiable criterion:* after recovering a period of 200 days and restarting the agent, the
recovered entries are still in the history; an evaluated entry older than its own retention is
removed at that same restart; a recovered entry older than 365 days is removed; changing either
figure does not change the other.
*Rationale: recovering a year and losing it on restart is not a feature. REQ-HIS-004 stands — the
history is bounded — and this requirement says with which bound for each kind of row. Someone who
never recovers anything sees no change in behaviour or in file size.*

> **Decision D-5, resolved by the maintainer on 2026-11-16:** a separate retention for recovered
> entries, 365 days. The alternatives — one longer retention for everything, or limiting recovery to
> the 90 days in force — are recorded in [README §Decisions](README.md). · **B-49**

### REQ-HIS-014 `[MUST]` — The history is exported to a local file *(event-driven)*
WHEN the user asks for it, THE SYSTEM SHALL write the entries matching the current filter to a file
the user chooses, in an open tabular format and in an open geographic format.

THE SYSTEM SHALL NOT open any network connection in order to export.

*Verifiable criterion:* the exported file holds exactly as many entries as the current filter's
count in the reading on screen — per arrival or per earthquake (REQ-HIS-009) — not just those on the
visible page; instants are in UTC with an offset; the exporting module
imports no network library.
*Rationale: REQ-HIS-006 forbids the agent transmitting the history. It does not forbid the user
saving their own data to their own disk, and that reading is written here rather than assumed.* ·
**B-51**

### REQ-HIS-015 `[SHOULD]` — The history is queried from the terminal *(optional feature)*
WHERE the agent runs with the terminal frontend, THE SYSTEM SHOULD offer the history list with the
same filters as the graphical interface.

*Verifiable criterion:* in `--tui`, the list filtered by verdict shows the same entries as the
graphical interface with the same filter.
*Rationale: it is where it saves the most — on a machine with no display the alternative is reading
the log. No map and no playback: they do not fit, and v1.0 already fixed which of the views is the
feature.* · **B-53**

---

## 5. REQ-MAP — Geographic view *(extends)*

### REQ-MAP-006 `[MUST]` — Every symbol says which earthquake it is *(event-driven)*
WHEN the user points at a symbol on the map, THE SYSTEM SHALL show the magnitude, the instant in
local time, the place, the distance and the verdict of the earthquake it stands for.

*Verifiable criterion:* the data shown for a symbol are those of the table entry for that same
earthquake.
*Rationale: a view whose argument is "where" and that cannot answer "which one is that?" delivers
half. Checked on 2026-11-16 (P-1): the symbols have to be markers holding a control; the painted
circles the map uses today cannot be pointed at.* · **B-50**

### REQ-MAP-007 `[MUST]` — The table and the map point at the same thing *(event-driven)*
WHEN the user chooses an entry in the table, THE SYSTEM SHALL highlight its symbol on the map; and
WHEN the user chooses a symbol on the map, THE SYSTEM SHALL highlight its entry in the table.

*Verifiable criterion:* after an entry is chosen, exactly one symbol is highlighted and it is the
one standing for that row; the distinction does not rely on colour alone.
*Rationale: it is REQ-MAP-004 taken from "the same set" to "the same element". The last clause
follows the rule the map already applies between alerts and discards.* · **B-50**

---

## 6. REQ-TLP — Time-based playback *(new area)*

A **third reading** of the history query, beside the table and the map. It inherits without
restating REQ-MAP-001 (tiles only while the map is open), REQ-MAP-002 (no tiles means it says so),
REQ-MAP-003 (magnitude is read at a glance) and REQ-MAP-005 (visible attribution).

### REQ-TLP-001 `[MUST]` — The history plays in the order it happened *(event-driven)*
WHEN the user starts playback, THE SYSTEM SHALL show on the map the earthquakes of the filtered set
in chronological order of occurrence, so that no earthquake appears before the instant it happened.

*Verifiable criterion:* for any instant of the playback, every visible symbol belongs to an
earthquake whose time of occurrence is earlier than or equal to it.
*Rationale: it is the property that makes this a playback and not an animation. It is checked on
the function that decides the frames, with no screen.* · **B-48**

### REQ-TLP-002 `[MUST]` — The user governs the playback *(event-driven)*
THE SYSTEM SHALL let the user pause and resume the playback, seek to any earthquake of the period,
and choose the speed among several declared ones.

*Verifiable criterion:* after pausing, what is shown does not change; seeking to an instant
produces exactly what continuous playback shows at that instant; changing the speed does not change
what is shown at a given instant, only when it is reached.
*Rationale: the second condition is what stops seeking and playing from coming to disagree. The
instants of a playback are those of its earthquakes (REQ-TLP-007), so seeking lands on one of
them.* · **B-48**

### REQ-TLP-003 `[MUST]` — The instant being played is always in view *(ubiquitous)*
WHILE the playback is on screen, THE SYSTEM SHALL show the instant being played, in the configured
local time, and the whole period it spans.

*Verifiable criterion:* the instant shown belongs to the frame on screen and is in the time zone of
`[notification] timezone`.
*Rationale: dots that appear with no date say nothing. Art. 4: conversion to local time happens at
presentation, and only there.* · **B-48**

### REQ-TLP-004 `[MUST]` — Playback obeys the same filter *(event-driven)*
WHEN the user changes a history filter, THE SYSTEM SHALL apply the same change to the set being
played.

*Verifiable criterion:* with a minimum-magnitude filter, no earthquake below it appears in the
playback; the set played is the same one the table pages through in full.
*Rationale: REQ-MAP-004 extended to the third reading. One query, three ways to read it.* · **B-48**

### REQ-TLP-005 `[MUST]` — What is recent is told apart from what is past *(ubiquitous)*
THE SYSTEM SHALL draw each earthquake at its strongest at the instant it happens and fade it
progressively over a declared interval, after which it is no longer shown or stays as a trail, as
the user chooses.

*Verifiable criterion:* a symbol's intensity is at its maximum at its time of occurrence and does
not grow afterwards; once the interval has passed, with the trail off, it is gone.
*Rationale: without fading, the playback ends up being the static map, which already exists. What
it adds is seeing what has just happened. The interval is measured in the history's time, not the
viewer's: how faded a symbol is depends on how long before the earthquake being shown it happened,
whatever the speed.* · **B-48**

### REQ-TLP-006 `[MUST]` — An alert interrupts the playback *(unwanted behaviour)*
IF an alert is presented while a playback is running, THEN THE SYSTEM SHALL pause it and yield the
window to the alert; and WHEN the alert is acknowledged, THE SYSTEM SHALL restore the playback,
paused, at the same instant.

*Verifiable criterion:* a simulated alert during playback is presented with all its guarantees;
after it is acknowledged, the playback is paused at the instant it was at.
*Rationale: Art. 1. Nothing the user was looking at outranks an earthquake, and a timer that keeps
redrawing the window is exactly what could compete with the alert.* · **B-48**

### REQ-TLP-007 `[MUST]` — Playback is bounded and does not block the interface *(state-driven)*
WHILE the playback is running, THE SYSTEM SHALL keep the interface able to respond to the controls,
and SHALL limit simultaneous symbols to a declared bound.

THE SYSTEM SHALL redraw the playback when an earthquake of the played set happens, and SHALL NOT
redraw it at a fixed interval of time. Each step SHALL stay on screen in proportion to the real time
to the next earthquake, between a declared minimum and a declared maximum.

IF the set exceeds what the bound allows to be shown, THEN THE SYSTEM SHALL say so on screen rather
than silently leave earthquakes out.

*Verifiable criterion:* with a set larger than the bound, pause responds, and a notice states that
not everything is being shown and how much is; a playback of N earthquakes redraws N times, however
long the period; two earthquakes a second apart and two a week apart each stay on screen no less
than the minimum and no more than the maximum.
*Rationale: the table already had this problem and solved it by declaring its limit. Leaving things
out without saying so under-reports, which is worse than drawing modestly. Redrawing by earthquake
ties the cost to the data: a quiet month is a handful of redraws, not thousands of identical ones.*

> **Decision D-8, resolved by the maintainer on 2026-11-16:** the playback advances by earthquake,
> not by clock.
>
> **The bound and the shortest step are numbers that do not exist yet.** They come out of the spike
> EP-15 starts with; until then this requirement fixes the shape, not the figures. · **B-48**

### REQ-TLP-008 `[MUST]` — Playing fetches no extra tiles *(ubiquitous)*
THE SYSTEM SHALL NOT pan or zoom the map as an effect of the playback. The framing SHALL change
only by the user's action.

*Verifiable criterion:* over a whole playback with no user intervention, the map's centre and zoom
level do not change.
*Rationale: E-06 bounds tile requests to what the user is looking at. A playback that wandered the
map on its own would request tiles nobody decided to request, and would reveal to the provider the
whole extent of the history.* · **B-48**

---

## 7. REQ-EST — Figures from the history *(new area)*

### REQ-EST-001 `[MUST]` — The period is summarised in figures *(event-driven)*
WHEN the user consults the summary, THE SYSTEM SHALL show, for the filtered set, the number of
earthquakes per day, their split by magnitude, by source network and by verdict, and, among the
discarded, by reason.

*Verifiable criterion:* each split adds up to the current filter's count of what it counts:
earthquakes (REQ-HIS-009) for the splits per day, by magnitude and by verdict and reason; arrivals
for the split by network.
*Rationale: the criterion is deliberately an arithmetic identity — it is what catches a split that
counts twice or drops a category.* · **B-51**

### REQ-EST-002 `[MUST]` — Each network shows how long it takes to report *(event-driven)*
THE SYSTEM SHALL show, for each network, the typical time elapsed between an earthquake happening
and the agent receiving it, computed **only** over the entries the agent received live.

*Verifiable criterion:* an entry recovered from the catalogue does not alter its network's latency;
a network with no live entries shows no figure, rather than showing zero; one arrival received days
late does not move the figure the way it would move a mean.
*Rationale: it is the one figure only this product can give, and the one that turns REQ-ING-011's
network order into an informed decision. Recovered entries are excluded because their "reception"
is the moment the user pressed a button.* · **B-51**

### REQ-EST-003 `[MUST]` — Every figure says what it was computed over *(ubiquitous)*
THE SYSTEM SHALL accompany every figure with the number of entries it was computed over and the
period it spans.

*Verifiable criterion:* every figure on screen has its sample size in view.
*Rationale: "median latency of 40 s" over three earthquakes and over three hundred are not the same
claim.* · **B-51**

> **Decision D-6, resolved by the maintainer on 2026-11-16:** the charts are drawn with the controls
> the interface already has, with no new dependency. These three requirements are met by figures and
> bars; none of them calls for a charting library.

---

## 8. REQ-ALE — Alert presentation *(extends)*

### REQ-ALE-011 `[MUST]` — The alert says how long until the shaking, or that it should already have arrived *(event-driven)*
WHEN an alert is presented, THE SYSTEM SHALL show the estimated time until the shaking reaches the
reference point, updated while the alert is on screen.

IF the estimated time has already elapsed, THEN THE SYSTEM SHALL say that the shaking should
already have arrived and approximately how long ago, and SHALL NOT show a negative time or omit the
datum.

*Verifiable criterion:* for an event whose origin time leaves travel time ahead, the alert shows a
count that decreases; for one received later than its travel time, it shows the sentence that it
should already have arrived, with the approximate time elapsed since, which grows while the alert
is on screen.
*Rationale: with catalogue sources the second case is the one that happens — in three months of local
history, no arrival within 1 000 km was received before its S wave, and alerts came a median of 19.5
minutes late (P-4). The alert is designed for that case: "≈ 19 min ago" is information, where a
bare "already arrived" is only an apology.* · **B-52**

### REQ-ALE-012 `[MUST]` — The estimate is presented as an estimate *(ubiquitous)*
THE SYSTEM SHALL present the time until the shaking as an approximation, without a precision the
method of calculation does not support. THE SYSTEM SHALL compute it over the distance to the
hypocentre — the epicentral distance and the depth together — and SHALL NOT show more time remaining
than the calculation gives.

*Verifiable criterion:* the text carries a mark of approximation in every language the product
offers; the method and its assumptions are documented; an earthquake directly under the reference
point at a depth of 70 km gives about twenty seconds, not zero; a remaining time is rounded down,
never up.
*Rationale: it is a constant-velocity model over a distance computed from a preliminary location.
"18 seconds" stated as a fact is a promise the calculation cannot keep. The two errors that can be
removed cheaply are removed: ignoring the depth, which reads a deep earthquake as already here; and
rounding up, which is the unsafe direction — the model already runs a few seconds late at long
range.*

> **Decision D-9, resolved by the maintainer on 2026-11-16:** a constant 3.5 km/s over the
> hypocentral distance; no travel-time table and no dependency while no source delivers within
> seconds. · **B-52**

### REQ-ALE-013 `[MUST]` — With no data to estimate from, the alert is presented all the same *(unwanted behaviour)*
IF the time until the shaking cannot be computed, THEN THE SYSTEM SHALL present the full alert
without that datum, and SHALL log why it could not be computed.

*Verifiable criterion:* an event whose estimate cannot be computed — an origin time later than the
agent's clock — produces an alert with all its guarantees; the log names the reason.
*Rationale: Art. 1 and Art. 3. The countdown enriches the alert; it is never a condition of it.* ·
**B-52**

---

## 9. REQ-UX — Experience *(extends)*

### REQ-UX-007 `[MUST]` — The drill can be scheduled *(optional feature)*
WHERE the user has enabled the scheduled drill, THE SYSTEM SHALL present a simulated alert at the
configured interval, and SHALL keep a record of when the last one took place and whether it was
acknowledged.

*Verifiable criterion:* with an interval that has come due, a drill is presented; after it is
acknowledged, the date of the last drill can be consulted; with the option off, none is presented.
*Rationale: it is testing the smoke detector. An agent that goes months without alerting has no
other way to show it still works on that machine. Where the record is kept is fixed in the Data
Model delta (05), within REQ-UX-008: wherever it is, it is not a row of the history's `events`. Off
by default: a product that opens a window
that cannot be ignored without anyone having asked is not a good first contact.* · **B-52**

### REQ-UX-008 `[MUST]` — A drill is not mistaken for an earthquake *(ubiquitous)*
THE SYSTEM SHALL label every simulated alert as a drill, visibly without reading the detail, and
SHALL NOT record it in the history as an earthquake.

*Verifiable criterion:* a drill's alert carries the label in every language; after a drill, no
history entry presents it as an alerted earthquake; the REQ-EST figures do not count it.
*Rationale: Art. 1 in the other direction. An alert that makes someone believe the ground is
shaking when it is not spends the credibility of the one that is.* · **B-52**

### REQ-UX-009 `[MUST]` — A drill never displaces or delays a real alert *(unwanted behaviour)*
IF a real alert is on screen or queued when a drill comes due, THEN THE SYSTEM SHALL postpone the
drill. IF a real alert arrives while a drill is on screen, THEN the real alert SHALL be presented
without waiting for the drill to be acknowledged.

*Verifiable criterion:* with a real alert presented, a due drill does not appear until the queue is
empty; with a drill presented, a real alert replaces it.
*Rationale: REQ-ALE-005 says "one alert at a time". This requirement says which one wins, and the
answer cannot be "whichever came first".* · **B-52**

> **Decision D-7, resolved by the maintainer on 2026-11-16:** the six requirements of sections 8
> and 9 are in v1.1, as its last phase, and they are what is cut if the release has to ship sooner.

---

## 10. Coverage and traceability

### 10.1 Requirement → item → epic

| Requirements | Item | Epic |
|---|---|---|
| REQ-GUI-011 | B-44 | EP-12 |
| REQ-GUI-012, REQ-GUI-013 | B-45 | EP-12 |
| REQ-HIS-005 *(strengthened)*, REQ-HIS-007, REQ-HIS-008 | B-46 | EP-13 |
| REQ-MAP-006, REQ-MAP-007 | B-50 | EP-13 |
| REQ-HIS-009 | B-47 | EP-14 |
| REQ-TLP-001..008 | B-48 | EP-15 |
| REQ-HIS-010..013 | B-49 | EP-16 |
| REQ-EST-001..003, REQ-HIS-014 | B-51 | EP-17 |
| REQ-ALE-011..013, REQ-UX-007..009 | B-52 | EP-18 |
| REQ-HIS-015 | B-53 | EP-19 |

All **ten items** are covered. No requirement lacks an item.

### 10.2 Split

| Area | Requirements | MUST | SHOULD |
|---|---|---|---|
| HIS (extends) | 9 | 8 | 1 |
| **TLP (new)** | **8** | **8** | 0 |
| GUI (extends) | 3 | 3 | 0 |
| **EST (new)** | **3** | **3** | 0 |
| ALE (extends) | 3 | 3 | 0 |
| UX (extends) | 3 | 3 | 0 |
| MAP (extends) | 2 | 2 | 0 |
| Inherited, strengthened | 1 | 1 | 0 |
| **Total** | **32** | **31** | **1** |

The only `[SHOULD]` is REQ-HIS-015, and it is the first thing to be cut.

### 10.3 Requirements that are not closed

One requirement has a part this document **cannot** fix. It is said here so that nobody reads it as
finished:

| Requirement | What is missing | What closes it |
|---|---|---|
| REQ-TLP-007 | The value of the symbol bound, and of the shortest and longest step | The EP-15 spike |

REQ-HIS-013 was open pending D-5 and is now closed.

### 10.4 Gherkin criteria

The Gherkin acceptance criteria go in User Stories HU-113 to HU-121, written **after this document
is approved**: they derive from it almost one to one, and writing them earlier would specify twice
what can still change.

---

## 11. Open questions

Things this PRD took for granted that could not be checked by reading the repository. Three were
checked on 2026-11-16; the evidence is in [README §Checks](README.md).

| # | Assumption | Affects | Status |
|---|---|---|---|
| P-1 | `flet-map` can react to the user pointing at or pressing a symbol | REQ-MAP-006, REQ-MAP-007 | **Checked — true for a `Marker`, false for a `CircleMarker`.** The history's symbols become markers. Selection by proximity is not needed |
| P-2 | One redraw of the layer is cheap enough for the playback | REQ-TLP-007 | **Open — the EP-15 spike.** Narrowed by D-8: the question is the cost of one redraw of N symbols, no longer a rate per second |
| P-3 | EMSC offers a catalogue query by date range besides the WebSocket | REQ-HIS-010 | **Checked — true.** A standard FDSN service on the configured host, at another path; it gets its own configuration key. The Analyze sets that key against E-06 (a) |
| P-4 | F-03's constant-velocity model (~3.5 km/s) is acceptable as a first version | REQ-ALE-011, REQ-ALE-012 | **Closed by D-9 — acceptable, over the hypocentral distance.** In three months of local history no arrival within 1 000 km beat its S wave, so REQ-ALE-011 is worded for the elapsed case |
| P-5 | The system's save-file dialog is available where the packaged binary runs | REQ-HIS-014 | **Open — T-175.** Found while designing the export (ADR-038). If it is not, the destination is typed into a path field |

---

## 12. Constitution check

Against [`docs/sdd/specs/00-CONSTITUTION.md`](../sdd/specs/00-CONSTITUTION.md) and its amendments
E-01 to E-06.

| Article | How this delta complies |
|---|---|
| Art. 1 (the alert is the product) | **REQ-GUI-013, REQ-TLP-006 and REQ-UX-009**: neither navigation, nor playback, nor a drill competes with a real alert. REQ-HIS-011: what is recovered never alerts. REQ-ALE-013: the countdown does not condition the alert |
| Art. 2 (no event is lost; no alert repeats) | REQ-HIS-012: recovery does not alter what the agent already decided, and repeating it does not duplicate |
| Art. 3 (fail-safe) | REQ-HIS-012 (one network down does not abort the others), REQ-ALE-013, and REQ-MAP-002 inherited by the playback |
| Art. 4 (instants in UTC) | REQ-TLP-003 and REQ-MAP-006 convert to local time only at presentation; REQ-HIS-014 exports in UTC |
| Art. 5 (executable boundaries) | The rule "the list imports neither the map nor the network" extends to the per-earthquake reading and to the export |
| Art. 7 (injectable, headless) | REQ-TLP-001, 002 and 005 are verified on the function that decides the frames, with no screen and no real clock |
| Art. 9 (spec and code together) | This document precedes the code it describes |

### Amendments this delta requires: none

Three readings support that statement. They are written down so they can be argued with, not taken
as given:

1. **Recovery adds no network destination.** E-06 (a) authorises the seismic sources declared in
   the configuration. Recovery queries those same networks. **P-3 settled the condition**: EMSC's
   catalogue is on the host already declared, at a path that is not — so it is declared in the
   configuration, with a key of its own, before it is used. That is a configuration change, not a
   constitutional one.
2. **Playback does not widen the use of tiles.** E-06 (c) authorises them only while the user has
   the map open. Playback is an open map, and REQ-TLP-008 stops it from asking for more than the
   user framed.
3. **Export does not transmit.** REQ-HIS-006 and amendment E-06 are about data going out to third
   parties. Writing a file where the user says is not that.

**E-05 is untouched**: the history stays in SQLite and the operating state in JSON. Recovery writes
only to the history — not to `state.json`, not to the cursors, not to the deduplicator. D-5 adds a
second retention figure for one kind of row; the history is still bounded, which is all REQ-HIS-004
and E-05 ask.

**Exceptions requested: none.** D-6 was resolved without adding a dependency, so the constitution's
rule on new dependencies is not engaged.
