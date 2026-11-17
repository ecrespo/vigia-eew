# HU-114 · The interface queries everything the store knows

> Epic **EP-13** · Priority **P1** · Effort M + M · Phase **F10**
> Items: B-46, B-50 · Requirements: REQ-HIS-005 *(strengthened)*, REQ-HIS-007, REQ-HIS-008,
> REQ-MAP-006, REQ-MAP-007 · Tasks: T-156..T-160

**As** a user asking why I was not warned about an earthquake three weeks ago,
**I want** to filter the history by date, network and distance, reach every row, and ask the map
which earthquake a symbol is,
**so that** I can find one earthquake without editing a file or reading a log.

## Context

`HistoryQuery` accepts six criteria. `HistoryView._build_filters` builds controls for two: minimum
magnitude and verdict. REQ-HIS-005 was verified against the store and not against the screen.

The list loads up to 500 rows and the table draws 150 (`TABLE_ROW_LIMIT`). `HistoryQuery.offset`
exists and nothing sets it. Rows 151 onward match the filter and cannot be seen.

On the map, a symbol is a `CircleMarker`: it has no tooltip and no events (P-1, checked
2026-11-16). A `Marker` holding a control has both. The symbols move to `MarkerLayer`.

**Where the state lives.** Filters and paging are state of `HistoryList`, which imports no toolkit.
The Flet controls only set it. That is what lets the terminal frontend reuse it (HU-121).

**What the map reads.** The table pages; the map does not. The map draws the whole filtered set up
to a declared bound and says when it stops short — otherwise turning a page would move the map.

## Acceptance criteria

```gherkin
Scenario: CA-114.1 · The five criteria are on the screen
  Given the history screen
  When its filters are listed
  Then there is a control for date range, minimum magnitude, maximum distance, verdict and network

Scenario: CA-114.2 · The table shows what the store returns
  Given a history with arrivals from three networks over sixty days
  When the user sets a date range and one network
  Then the table shows exactly the entries the store returns for that query

Scenario: CA-114.3 · Only what is in the history is offered
  Given a history with no arrival from GEOFON and no recovered entry
  When the network and verdict filters are opened
  Then GEOFON is not among the networks
  And "recovered" is not among the verdicts

Scenario: CA-114.4 · A date range that ends before it starts is refused
  Given a start date later than the end date
  When the user applies it
  Then the screen says the range is not valid
  And the entries on screen are those of the last valid filter

Scenario: CA-114.5 · Every matching entry can be reached
  Given a filter matched by more entries than one page holds
  When the user moves forward to the last page
  Then the last entry of the set is on screen
  And the status gives the stretch shown and the total
  And the total equals the store's count for that filter

Scenario: CA-114.6 · Changing a filter starts from the beginning
  Given the third page of a filtered set
  When the user changes any filter
  Then the first page of the new set is shown

Scenario: CA-114.7 · A symbol says which earthquake it is
  Given the map with symbols
  When the user points at one
  Then it shows the magnitude, local time, place, distance and verdict
  And they are those of the table entry for that row

Scenario: CA-114.8 · A chosen row points at its symbol
  Given the table and the map side by side
  When the user chooses an entry in the table
  Then exactly one symbol is highlighted and it stands for that row
  And it differs from the others in shape or outline, not only in colour

Scenario: CA-114.9 · A chosen symbol points at its row
  Given a symbol whose row is on another page of the table
  When the user chooses that symbol
  Then the table moves to the page that holds the row
  And the row is highlighted

Scenario: CA-114.10 · Without the map, the list still answers
  Given no connectivity and no cached tiles
  When the user filters and pages the list
  Then the list responds normally
  And the map says it is not available
```

## Definition of done

- [ ] Filter and paging state in `HistoryList`; `HistoryView` only sets it
- [ ] Controls for the three missing filters; networks and verdicts listed from the store
- [ ] A pager with the stretch and the total; `offset` in use
- [ ] The map reads the filtered set in full, bounded and declared
- [ ] Symbols as markers with a tooltip built from the list's own formatted row
- [ ] Selection keyed by row id, wired in `HistoryWindow`; the list still imports no map
- [ ] `tests/test_history_view.py` checks each filter against `HistoryStore.query`
