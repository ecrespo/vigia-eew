# Processing pipeline

Between the ingestors' `raw_queue` and the notification layer sits a fixed chain: normalize →
filter → dedup, driven by [[src/vigia_eew/pipeline/processor.py#Processor]].

The ordering is load-bearing, not stylistic: filtering runs before dedup so that a rejected event
never enters — and never pollutes — the "first reporter wins" dedup state.

## One internal contract, derived fields always derived

[[src/vigia_eew/pipeline/normalize.py#Normalizer]] maps each source's payload onto
[[src/vigia_eew/models.py#SeismicEvent]], the only structure that crosses layer boundaries.

Distance and severity are computed here and never carried over from a source payload, so two
sources reporting the same quake cannot disagree about how far away or how serious it is.
Field-by-field mappings and invariants live in `docs/API-SPEC.md` §3.

## Filtering: radius, magnitude, country, freshness

[[src/vigia_eew/pipeline/filter.py#GeoFilter]] applies four independent checks. Radius and
magnitude are the original requirement (RF-12); country and freshness were added later.

Both later checks follow the same fail-safe philosophy: when a check cannot be evaluated
confidently, it stays inert rather than risking a suppressed real alert.

### Country filter is a block-list, not an allow-list

An event is dropped only when it lies positively inside another country; offshore events and
events of undetermined country are kept.

This looks backwards until you know the geography: Venezuela's most dangerous earthquakes are
offshore ("NEAR COAST OF VENEZUELA") and outside any land polygon, so a strict "must be inside my
country" rule would drop exactly the events the product exists for.

The lookup is offline ray-casting against a bundled, reduced Natural Earth 1:110m dataset
([[src/vigia_eew/geocode.py#country_of]]) — no geospatial dependency, no per-event network call.
The accepted trade-off is coarse boundaries (±tens of km) near borders; the upgrade path is 1:50m.
Off by default. See ADR-014.

### Freshness uses the local calendar day rather than UTC

An event is discarded unless its `time_utc`, converted to the local calendar day of
`[notification] timezone`, is today.

A UTC day boundary was rejected because Venezuela is UTC-4: the boundary would fall at 8:00 pm
local, and a 9:00 pm quake — still "today" on the clock the alert itself displays — would be
treated as yesterday for four hours.

`today_only` defaults to **true**, unlike the country filter's default-false, because this is an
always-desired product rule rather than an opt-in narrowing. An invalid IANA timezone makes the
check inert with one logged warning. The clock is injected so tests can freeze "today". See
ADR-017 and [[state#Freshness has a second, query-side half]].

## Deduplication

[[src/vigia_eew/pipeline/dedup.py#Deduplicator]] resolves the consequence of having four sources:
the same earthquake arrives with four different ids.

There is no shared identifier across the networks and exact matching is fragile, so identity is
heuristic — the same quake if within ≤100 km, ≤90 s and ≤0.5 magnitude — layered on top of exact
intra-source id matching. Swarms can produce false merges or splits, which is why the thresholds
are configurable. The heuristic was already source-count-agnostic, so adding GEOFON as a fourth
source required no change to it. See ADR-004.

### EMSC `update` refreshes the alert instead of raising a new one

An `update` for an event already on screen updates that alert in place.

Raising a second window for a revised magnitude would train the user to dismiss alerts
reflexively, which is the one behavior the product cannot afford.
