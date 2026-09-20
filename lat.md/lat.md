This directory defines the high-level concepts, business logic, and architecture of this project using markdown. It is managed by [lat.md](https://www.npmjs.com/package/lat.md) — a tool that anchors source code to these definitions. Install the `lat` command with `npm i -g lat.md` and run `lat --help`.

- [[architecture]] — why the agent is one process per machine, push-primary with polling backup, and where the "impossible to ignore" guarantee stops (Wayland).
- [[ingestion]] — the four upstream sources, what gap each one closes, and why their polling strategies deliberately differ.
- [[pipeline]] — normalize → filter → dedup: the ordering invariant, the block-list country filter, local-day freshness, and heuristic cross-source identity.
- [[notification]] — the non-dismissable alert contract, one-alert-at-a-time, pause semantics, and the best-effort tray icon.
- [[configuration]] — why the file stayed read-only for six versions, what the writer refuses to do, and why only changed fields are written.
- [[state]] — what survives a restart and why, prune-on-register and its known limitation, and one-shot reference-point resolution.
- [[history]] — one row per evaluated arrival with the reason for every discard, why it is SQLite against the constitution's own rule, and why it can never cost an alert.
- [[conventions]] — the invariants that hold everywhere: UTC datetimes, fail-safe degradation, dependency injection, language policy, and the quality gate.
