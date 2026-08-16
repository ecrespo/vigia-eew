# Pipeline

Everything between "a source said something" and "the user is alerted" happens
here: normalize, filter, deduplicate. This file records the domain rules that
are judgement calls rather than mechanics.

Sources are described in [[ingestion]]; what happens after acceptance is
[[notification]].

## SeismicEvent is the only cross-layer payload

[[src/vigia_eew/models.py#SeismicEvent]] is the single contract that crosses
layer boundaries. Source-specific shapes stop at
[[src/vigia_eew/pipeline/normalize.py#Normalizer]] and never travel further.

Four sources with four payload formats would otherwise leak their differences
into the filter, the dedup heuristic, and the alert window, and every new
source would touch all of them. With one normalized contract, adding a source
is a mapping exercise plus one literal in the `source` field.

Two invariants hold everywhere: **every datetime is tz-aware UTC** (the model
rejects naive values outright), and **distance and severity are always
derived**, never taken from a source. Local time exists only at the
presentation boundary — see
[[notification#Local time is a presentation concern]].

## Every timestamp is UTC until the last moment

Timestamps are normalized to tz-aware UTC on entry and converted to a local
zone only when rendered.

Seismic sources report in several conventions, and the users are in a
UTC-4 zone. Mixing naive and aware datetimes in dedup time-window arithmetic
produces wrong answers silently rather than raising, so the model validates
awareness instead of trusting callers. The one place local time is
authoritative is the day-boundary rule below, which is about human calendars
rather than instants.

## Filtering is a chain of independent, fail-safe checks

[[src/vigia_eew/pipeline/filter.py#GeoFilter]] accepts an event only if it
passes radius, magnitude, country, and freshness — evaluated **before**
deduplication so a rejected event never pollutes dedup state.

The ordering matters: if a stale or foreign event reached
[[src/vigia_eew/pipeline/dedup.py#Deduplicator]], it would be recorded as
"seen" and could suppress a later, legitimate report of the same earthquake
under the "first reporter wins" rule.

Every optional check in this chain is **fail-safe in the same direction**: when
the check cannot be evaluated, it goes inert and lets the event through. A
missed alert is a safety failure; a spurious alert is an annoyance. Any new
filter added here must fail the same way.

## The country filter is a block-list, not an allow-list

With `[filter] country_filter` enabled, an event is dropped only when it lies
*positively inside another country*. Offshore, oceanic, and
undetermined-country events are kept.

The naive reading — "only alert me about earthquakes in my country" — would
suppress exactly the events that matter most, because Venezuela's most
dangerous earthquakes are offshore and fall inside no land polygon at all. The
inverted rule keeps everything ambiguous and only removes what is confidently
somebody else's.

The lookup ([[src/vigia_eew/geocode.py#country_of]]) is offline point-in-polygon
against a bundled Natural Earth 1:110m dataset, with pure-Python ray casting and
a bounding-box pre-check — no geospatial dependency and no per-event network
call. The boundaries are coarse near borders (tens of km), which is acceptable
for a best-effort filter that is off by default; the upgrade path is the 1:50m
dataset.

The user's own country is derived from the already-resolved reference point, so
it works for manual and IP-detected references alike without an extra lookup.

## Only today's earthquakes are alerted

An event is discarded unless its `time_utc`, converted to the local calendar day
of the configured timezone, is *today*. This is on by default
(`[filter] today_only = true`).

Nothing else in the system bounds an event's age: `alerted_ids` records whether
something was alerted, never when it happened, so an old event that is merely
*new to the dedup store* would otherwise fire a full alert. This rule is the
authoritative guard and applies uniformly to all four sources regardless of how
they reached the pipeline.

**Local day, not UTC day** — Venezuela is UTC-4, so a UTC boundary falls at
8:00 pm local. An earthquake at 9:00 pm local is still "today" to the user and
to the clock shown in the alert; treating it as yesterday for four hours every
night would be a visible bug. The day is computed via
[[src/vigia_eew/timeutil.py#local_date]] with an **injected clock**, which is
what makes "today" freezable in tests without touching the system clock.

Unlike the country filter this defaults to *on*, because it is an always-desired
product rule rather than an opt-in narrowing. It stays configurable so a
backfill or demo run has an escape hatch.

## Cross-source dedup is heuristic because no shared id exists

Two events from different sources are treated as the same earthquake when they
are within **100 km, 90 s, and 0.5 magnitude** of each other.

There is no identifier shared across EMSC, USGS, FUNVISIS and GEOFON, and exact
matching on coordinates or time is hopeless — independent networks produce
genuinely different solutions for the same rupture. The thresholds encode how
far apart two solutions can plausibly be while still describing one event.

The known cost is misjudgement during swarms, where distinct earthquakes really
do occur within 90 s and 100 km of each other; the thresholds are configurable
for that reason. The heuristic is source-count-agnostic, which is why adding
GEOFON as a fourth source needed no change to it.

Intra-source repetition is handled separately and exactly, by id.

## An EMSC update refreshes the alert instead of raising a new one

When EMSC re-reports a known `unid` with a revised magnitude, the in-flight
alert is updated in place — on screen or in the queue — and no second alert is
raised.

Magnitude revisions are routine in the minutes after an earthquake. Alerting
again for each one would train the user to dismiss alerts reflexively, which
defeats the entire "impossible to ignore" premise in
[[notification#The alert is not dismissable by design]].

## State is pruned where it grows

[[src/vigia_eew/pipeline/dedup.py#Deduplicator#register]] calls
[[src/vigia_eew/state.py#StateStore#prune]] immediately before saving, dropping
`alerted_ids` and `recent_signatures` older than 24 h.

`register()` is the only path that grows the state and the only caller of
`save()`, so it is the natural hook. A separate periodic pruning task was
rejected: pruning has no externally visible effect until the next `save()`
anyway, so a fifth supervised task with its own backoff would buy nothing.

Accepted limitation: if the agent runs a long stretch with **zero** new alerts,
entries older than 24 h survive until the next `register()`. That is harmless —
nothing is growing either — but do not rely on `state.json` being tightly
pruned at every instant, only on it being bounded whenever it grows.

## Persisted state is written atomically

[[src/vigia_eew/state.py#StateStore]] writes to a temp file and `os.replace`s
it, and treats a missing or corrupt file as "start fresh" rather than an error.

A crash mid-write must not leave a state file that prevents the agent from
starting; a safety tool that refuses to boot because its cache is damaged has
chosen the wrong failure. Losing the cursor costs a small re-fetch, which the
day floor in [[ingestion#REST queries are floored at local midnight]] bounds
anyway.
