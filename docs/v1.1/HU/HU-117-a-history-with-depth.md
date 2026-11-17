# HU-117 · A history with depth

> Epic **EP-16** · Priority P2 · Effort M · Phase **F13**
> Item: B-49 *(absorbs B-32)* · Requirements: REQ-HIS-010..013 · Tasks: T-167..T-171
> Decision **D-5**: recovered entries keep their own retention, 365 days.

**As** a user who has just installed the agent, or whose agent was off for two weeks,
**I want** to complete the history from the networks' catalogues,
**so that** the map and the playback show my region's seismicity and not only what the agent
happened to see.

## Context

The history only knows what the agent saw while running. For an alerting tool that is correct; for
a view of the region it is the limitation that weighs most.

**What can be recovered (P-3, checked 2026-11-16):** EMSC, USGS and GEOFON — three FDSN
`fdsnws-event` catalogues that take a date range. EMSC's is at a path of its own on the host
already configured and gets its own configuration key. **FUNVISIS cannot**: its endpoint returns
the ~20 most recent events and takes no dates. The small local earthquakes only FUNVISIS catalogues
will not be in what is recovered, and the outcome says so.

**Recovered earthquakes were never evaluated.** Nobody was alerted or not alerted about them. So
*recovered* is a **third verdict** beside *alerted* and *discarded* (ADR-037): the honest answer to
*"why was I not warned?"* for those rows is *"the agent was not watching"*.

**Recovery is a separate path** (ADR-036). It writes to the history and nowhere else: not the raw
queue, not the pipeline, not the alert controller, not `state.json`. An earthquake from a month ago
cannot open a window.

**What is recovered:** the earthquakes within `[history] recovery_radius_km` of the reference
point, at or above `[history] recovery_min_magnitude`. Those are the two keys that say what *"my
region"* means for this purpose; they are separate from the alert radius on purpose.

**How it joins what is there.** The same arrival — same network, same id — is left alone. The same
earthquake from another network joins the existing earthquake, by the heuristic the deduplicator
already uses (RF-09), as one more arrival. A row the agent evaluated is never replaced by a
recovered one; a recovered row **is** replaced if the agent later evaluates that arrival live.

## Acceptance criteria

```gherkin
Scenario: CA-117.1 · An empty history is completed
  Given an empty history and the three recoverable networks configured
  When the user recovers the last 30 days
  Then the history holds entries from that period

Scenario: CA-117.2 · It says what it could not recover
  Given FUNVISIS among the configured networks
  When a recovery ends
  Then the outcome names FUNVISIS as not recoverable
  And gives the reason: it offers no query by date

Scenario: CA-117.3 · Nothing recovered alerts
  Given a period holding earthquakes inside the radius and above the minimum magnitude
  When that period is recovered
  Then no alert window, sound or notification is presented

Scenario: CA-117.4 · Recovered is its own verdict
  Given a history with recovered entries
  When they are inspected
  Then none has the verdict "alerted" or "discarded"
  And the verdict filter can isolate them
  And they are drawn differently from alerted and discarded on the table, the map and the playback

Scenario: CA-117.5 · Repeating it changes nothing
  Given a period already recovered
  When the same recovery is run again
  Then the history has the same number of rows

Scenario: CA-117.6 · It does not reach beyond the retention
  Given a retention of 365 days for recovered entries
  When the user asks to recover 400 days
  Then the request is refused
  And the refusal names the limit

Scenario: CA-117.7 · One network down does not stop the others
  Given one of three recoverable networks failing
  When a recovery is run
  Then the other two are recovered
  And the failure is logged and named in the outcome

Scenario: CA-117.8 · What the agent decided is kept
  Given an alerted entry in the history
  When the period that contains it is recovered
  Then that entry is still alerted, with the same data

Scenario: CA-117.9 · An earthquake already known gains an arrival, not a twin
  Given an earthquake the agent recorded from EMSC
  When a recovery brings the same earthquake from USGS
  Then the per-earthquake reading shows it once
  And its arrivals list both networks

Scenario: CA-117.10 · Each kind of entry has its own retention
  Given recovered entries 200 days old and an evaluated entry 100 days old
  When the agent is restarted with the default retentions
  Then the recovered entries are still there
  And the evaluated entry is gone
  And a recovered entry older than 365 days is gone
  And changing either retention does not change the other

Scenario: CA-117.11 · Recovery touches only the history
  Given the operating state file before a recovery
  When the recovery ends
  Then the file is byte for byte the same

Scenario: CA-117.12 · A live evaluation outranks a recovered row
  Given a recovered entry for an arrival
  When the agent later evaluates that same arrival live
  Then the entry carries the agent's verdict, not "recovered"
```

## Definition of done

- [ ] `[emsc] catalog_url`, `[history] recovered_retention_days`, `recovery_radius_km` and
      `recovery_min_magnitude` in the schema, the example file and the panel
- [ ] `backfill.py`, behind an import contract that forbids it the pipeline and the presentation
- [ ] `--backfill DAYS` on the command line and a *Recover…* action on the history screen
- [ ] The prune tells the two kinds of row apart
- [ ] A third style on the map, with its legend entry, that does not rely on colour alone
- [ ] No schema change: `SCHEMA_VERSION` stays at 1 (ADR-037)
- [ ] `docs/API-SPEC.md` documents the EMSC catalogue; `lat.md/history.md` records ADR-036 and 037
