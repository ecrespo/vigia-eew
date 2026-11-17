# HU-118 · Figures and data out

> Epic **EP-17** · Priority P2 · Effort M · Phase **F14**
> Item: B-51 · Requirements: REQ-EST-001..003, REQ-HIS-014 · Tasks: T-172..T-175
> Decision **D-6**: bars drawn with the controls already there; no new dependency.

**As** a user deciding which network should go first,
**I want** the period summarised in figures, each network's delivery delay, and the data in a file,
**so that** I decide with numbers and can open my own data elsewhere.

## Context

The second half of F-10 (*"local history **and statistics**"*), which v1.0 did not address.

**The figure only this product can give** is each network's latency: `recorded_at − occurred_at`,
two columns already stored. Measured on three months of local history it is 40 minutes for EMSC, 19 for
FUNVISIS and 4.9 hours for USGS, at the median — and one EMSC arrival in ten reached the agent more
than ten days late, which is why the figure is a median and not a mean.

**Two bases, and each figure names its own (X-8).** Figures about earthquakes — per day, by
magnitude, by verdict and reason — count earthquakes (HU-115). Figures about networks — the split
by network, the latency — count arrivals. Each split adds up to the count of what it counts.

**The export writes the reading on screen**, in full and not only the visible page, to a file the
user chooses: CSV and GeoJSON. It opens no connection. REQ-HIS-006 forbids the agent transmitting
the history; it does not forbid the user saving their own data to their own disk.

Both halves are pure modules — `history_stats.py`, `history_export.py` — with no toolkit and no
network library, and a test on their imports keeps them that way.

## Acceptance criteria

```gherkin
Scenario: CA-118.1 · Every split adds up
  Given a filtered set
  When the summary is computed
  Then the splits per day, by magnitude and by verdict each add up to the count of earthquakes
  And the split by network adds up to the count of arrivals

Scenario: CA-118.2 · A day counts earthquakes
  Given an earthquake recorded from two networks on one day
  When the earthquakes per day are read
  Then that day counts it once

Scenario: CA-118.3 · Latency ignores what was recovered
  Given a network with live arrivals and recovered entries
  When its latency is computed
  Then adding or removing recovered entries does not change it

Scenario: CA-118.4 · No live arrivals, no figure
  Given a network whose only entries were recovered
  When its latency is shown
  Then it shows that there is no figure, not zero

Scenario: CA-118.5 · One late arrival does not move the figure
  Given a network with nine arrivals delivered within an hour and one delivered ten days late
  When its latency is computed
  Then the figure is within the hour

Scenario: CA-118.6 · Every figure says what it was computed over
  Given the summary on screen
  When any figure is read
  Then the number of entries it was computed over and the period are in view beside it

Scenario: CA-118.7 · An empty set is said, not computed
  Given a filter that matches nothing
  When the summary is opened
  Then it says there is no data for that filter
  And no figure is shown as zero

Scenario: CA-118.8 · The export holds the whole filtered set
  Given a filtered set larger than one page of the table
  When the user exports it
  Then the file holds as many entries as the filter's count in the reading on screen

Scenario: CA-118.9 · The tabular file opens in a spreadsheet
  Given an exported tabular file
  When it is read
  Then its first row names the columns
  And every instant is in UTC with its offset

Scenario: CA-118.10 · The geographic file opens in a GIS
  Given an exported geographic file
  When it is read
  Then it is a valid feature collection
  And each point is given as longitude, then latitude

Scenario: CA-118.11 · Exporting opens no connection
  Given the exporting module
  When its imports are inspected
  Then it imports no network library

Scenario: CA-118.12 · A file that cannot be written is said
  Given a destination that cannot be written
  When the user exports
  Then the screen says the file could not be written and why
  And no partial file is left behind
```

## Definition of done

- [x] `history_stats.py` and `history_export.py`, pure, with an import test each
- [x] A summary view inside the history screen, with bars built from containers
- [x] Latency as a median over live arrivals, with its sample size
- [x] An *Export…* action that offers CSV and GeoJSON and writes atomically
- [x] A way to give the destination that works where the system file dialog does not (P-5) —
  the path field is always there; the dialog on the packaged binary is still to be observed
- [x] `lat.md/history.md` records the reading of REQ-HIS-006 the export rests on
