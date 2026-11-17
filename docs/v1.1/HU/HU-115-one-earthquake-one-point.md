# HU-115 · One earthquake, one point

> Epic **EP-14** · Priority P1 · Effort S–M · Phase **F11**
> Item: B-47 · Requirement: REQ-HIS-009 · Tasks: T-161, T-162

**As** a user looking at the seismicity of my region,
**I want** an earthquake reported by two networks to be one line and one symbol,
**so that** the map does not show two earthquakes where there was one.

## Context

The history keeps one row per **arrival** (DATA-MODEL §3bis.1), and that is right for storing: *"it
came by two networks and this one prevailed"* is worth keeping. It is wrong for drawing. Two
symbols at one place read as a bigger earthquake, or as two.

This story adds a **second reading of the same rows**, grouped by `correlation_id`. Nothing is
deleted, merged or rewritten. The index it needs — `events_correlation_id` — already exists.

**Which arrival stands for the earthquake** (ADR-034):

1. the alerted one, if there is one;
2. otherwise the one that prevailed — the row whose `superseded_by` is empty;
3. otherwise the one from the best-ranked network (REQ-ING-011's order);
4. otherwise the earliest recorded.

**Filters apply to arrivals, then the arrivals are grouped.** Filtering by one network in this
reading shows the earthquakes that network reported, each once, represented by that network's
arrival.

It is a prerequisite of HU-116: without it the playback is born showing duplicates.

## Acceptance criteria

```gherkin
Scenario: CA-115.1 · One entry per earthquake
  Given an earthquake recorded from EMSC and from USGS
  When the user reads the history per earthquake
  Then it appears once
  And when the user reads it per arrival it appears twice

Scenario: CA-115.2 · Reading changes nothing
  Given a history file with a known number of rows
  When the user switches between the two readings several times
  Then the file has the same number of rows

Scenario: CA-115.3 · The alerted arrival stands for the earthquake
  Given an earthquake with one alerted arrival and one discarded as a duplicate
  When it is read per earthquake
  Then its data and verdict are those of the alerted arrival

Scenario: CA-115.4 · With no alert, the arrival that prevailed stands for it
  Given an earthquake whose arrivals were all discarded
  When it is read per earthquake
  Then its data are those of the arrival that was not superseded
  And if several were not, of the one from the best-ranked network

Scenario: CA-115.5 · The arrivals are still there
  Given an earthquake shown once in the per-earthquake reading
  When the user asks for its arrivals
  Then every arrival is listed with its network, its verdict and its reason

Scenario: CA-115.6 · The filter still means the same
  Given an earthquake reported by EMSC and USGS and a filter on USGS
  When it is read per earthquake
  Then it appears once, with the data of the USGS arrival
  And the total counts it once

Scenario: CA-115.7 · One symbol on the map
  Given the per-earthquake reading
  When the map is drawn
  Then each earthquake is one symbol
```

## Definition of done

- [ ] `HistoryQuery.reading`, with prepared statements for both readings and their counts
- [ ] `HistoryStore.arrivals(correlation_id)`
- [ ] A switch between readings on the screen; the map and the pager follow it
- [ ] ADR-034 in `lat.md/history.md`, linked from the statement that picks the representative
- [ ] A test that the row count of the file is unchanged by reading
