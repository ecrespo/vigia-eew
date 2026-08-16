# Vigía-eew — intent layer

This directory defines the high-level concepts, business logic, and design
decisions of Vigía-eew: a desktop agent that watches four seismic networks in
real time and raises an alert the user cannot dismiss by accident.

It records **why** the code is the way it is. The mechanics are in the code; the
requirements (RF/RNF), ADRs, and specs are in `docs/`. Read a section here
before changing behavior it governs — several rules that look like arbitrary
constants (dedup thresholds, a block-list country filter, a local-day boundary)
are deliberate and were chosen against rejected alternatives.

Managed by [lat.md](https://www.npmjs.com/package/lat.md): run `lat search
"<topic>"` to find a section, `lat check` to validate links.

## Index

The five topical files, in the order an event travels through the system.

- [[architecture]] — process shape, supervision, threading model, and the rules
  about what may take the agent down.
- [[ingestion]] — the four sources, why push is primary and polling is a safety
  net, and how each source tracks novelty.
- [[pipeline]] — the internal event contract, the filter chain, and the
  deduplication heuristic that makes four sources look like one.
- [[notification]] — the "impossible to ignore" contract, alert serialization,
  and the trade-offs deliberately made against it.
- [[configuration]] — how the agent learns the user's location, what it persists,
  and how it survives a reboot.
