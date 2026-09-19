# Persisted state

[[src/vigia_eew/state.py#StateStore]] persists the few things that must survive a restart: which
events were already alerted, the REST cursors, and the IP-detected reference location.

Everything else is deliberately in-memory. Writes are atomic JSON via `platformdirs`, so a crash
mid-write cannot leave a corrupt file that would make the agent re-alert history.

## What restart safety actually protects

The user-visible invariant is that restarting the agent must not replay alerts the user already
acknowledged.

That is why `alerted_ids` and `recent_signatures` are persisted rather than recomputed, and why
the FUNVISIS seen-set — which achieves the same effect by seeding on first poll — does not need
to be.

## Pruning happens where the state grows

[[src/vigia_eew/pipeline/dedup.py#Deduplicator]]`.register()` calls `prune()` immediately before
`save()`.

`prune()` and its 24 h `MAX_AGE` existed with a unit test since the original state-persistence
phase but were never called from any run path, so the state grew unbounded for the process
lifetime.

A separate periodic pruning task in the supervisor was rejected: pruning has no externally visible
effect until the next `save()`, and `register()` is the sole site where the state grows and then
saves, so tying them together is equivalent and far simpler. `MAX_AGE` is intentionally not
exposed in `config.toml` — it is internal state hygiene, not user-facing behavior. See ADR-018.

### Known limitation of prune-on-register

If the agent runs a long stretch with zero new alerts, entries older than 24 h are not pruned
until the next `register()`.

This is harmless — nothing is being added either — but it means `state.json` is "pruned whenever
it grows", not "always tightly pruned". Do not build anything that depends on the stronger
reading.

## Freshness has a second, query-side half

[[src/vigia_eew/ingest/rest_usgs.py#RESTReconciler]] and
[[src/vigia_eew/ingest/rest_geofon.py#GEOFONPoller]] floor their `starttime` at local midnight
whenever the persisted cursor is missing or older than that floor.

This changes nothing about what gets alerted — the pipeline filter already guarantees that. It
bounds how much irrelevant history a fresh install or a week-long outage fetches and parses on
catch-up. The boundary itself is shared in [[src/vigia_eew/timeutil.py#local_midnight_ms]].

Implementing only this half was rejected because it covers neither EMSC (push, no `starttime`) nor
FUNVISIS (seen-set), and would leave a floor bug with no downstream safety net. See ADR-017 and
[[lat.md/pipeline#Processing pipeline#Filtering: radius, magnitude, country, freshness#Freshness uses the local calendar day rather than UTC]].

## Reference point resolution happens once, in the application layer

If `[reference]` is absent from `config.toml`, [[src/vigia_eew/wiring.py#Wiring]] detects the
location by IP exactly once before starting the pipeline and caches it in the persisted state.

A manual reference or a cached location means the API is never called. Detection failure falls
back to the hardcoded default without caching the failure, so it retries next startup.

This lives in the wiring and not in `config.py` on purpose: `config.py` stays a pure TOML
read-and-validate function with no network or state I/O, exposing only whether `[reference]` was
present. Re-detecting on every startup was rejected — a machine's location does not change between
startups, and it would burn the free service's quota. `--simulate` never resolves the location,
because simulation must work with no network at all. See ADR-011.


## `StateStore` is a facade, and that is deliberate

It exposes twelve public methods over a single persisted document, which static analysis reads as
a class doing too much (code-audit P3-4). Splitting it into cohesive views -- alerts, cursors,
location -- was considered and rejected.

The methods look unrelated because the *questions* are unrelated. What they share is the thing
that actually matters here: **one document, one atomic write**. `state.json` is written by
temp-file-and-rename so that a crash mid-write cannot leave the agent unable to start, and that
guarantee is a property of the file, not of any one group of fields. Three view objects over one
document would each need a reference back to the single writer, which is the facade again with
more indirection and one more chance to save twice.

The methods are also not symmetric in weight. `save()` and `prune()` are about the file;
`already_alerted()`, `trace_of()` and `cached_location()` are questions; the rest are single-field
updates that do not persist on their own. Grouping them by subject would hide that.

So: a facade over one atomic document, on purpose. The rule that follows is that nothing outside
`StateStore` writes `state.json`, and nothing inside it writes anything else.
