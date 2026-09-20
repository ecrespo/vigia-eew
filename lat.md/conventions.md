# Conventions and invariants

These rules hold across the whole codebase. They are cheap to violate accidentally and expensive
to fix afterwards, which is why they are written down rather than inferred from the code.

## Every internal datetime is tz-aware UTC

[[src/vigia_eew/models.py#SeismicEvent]] validates this and rejects naive values outright.

Conversion to local time happens in exactly two places: `notify/presentation.py` for display, and
[[src/vigia_eew/timeutil.py]] for the local-day and local-midnight boundaries the freshness rules
depend on. A naive datetime anywhere else is a bug, not a shortcut.

## Fail-safe beats fail-closed for anything that could suppress an alert

When a mechanism cannot do its job confidently, it becomes inert or degrades — it never suppresses
a real alert and never takes the process down.

Applied consistently across [[src/vigia_eew/geoloc.py]], [[src/vigia_eew/geocode.py]],
[[src/vigia_eew/notify/toast.py]] and [[src/vigia_eew/tray.py]]. The reasoning is asymmetric cost:
a spurious alert is an annoyance, a missed one is the product failing at the only moment it exists
for.

## Dependency injection separates pure logic from system effects

Clocks, `sleep`, `connect`, HTTP clients, subprocess runners and the three notification effects are
all injected.

This is not testing dogma — it is what makes the default suite run headless and deterministically:
freezing "today" without touching the system clock, driving backoff without waiting, and building
systemd units, launchd plists and schtasks commands as pure string generation verified without
ever calling `systemctl`, `launchctl` or `schtasks`.

Real-GUI tests are gated behind `VIGIA_GUI_TESTS=1` and are not part of the default run.

## English in the code, translations at the edge

Code, docstrings, comments, commit messages and SDD artifacts are English (RNF-10). Only
user-facing strings are internationalized.

Translation goes through [[src/vigia_eew/i18n.py]], with the language auto-detected from the OS
locale and overridable via `[notification] language`. The English strings in the source are the
source of truth; Spanish ships alongside.

## Config is read-only TOML validated by pydantic

`config.toml` is read with `tomllib` and validated by [[src/vigia_eew/config.py#Settings]].

`tomllib` is read-only and that is sufficient — nothing in v1 writes configuration. `.env` was
rejected as awkward for nested structures like per-severity thresholds. See ADR-007.

## The SDD artifacts are part of the deliverable

Adding a module means updating `docs/IMPLEMENTATION-PLAN.md` — its structure, phase table and
RF→module matrix — in the same change.

The plan links `docs/PRD.md` (RF/RNF requirements), `docs/API-SPEC.md` (external and internal
contracts), `docs/TECHNICAL-DESIGN.md` (numbered ADRs) and `docs/DATA-MODEL.md`; `ARCHITECTURE.md`
holds the diagrams.

ADR-015 and ADR-016 were written retroactively to bring the artifacts back in sync with shipped
code. That is a documented lapse, not the working style.

## Quality gate

`pytest`, `ruff check .` and `mypy src` (strict) must all be green before a task is done.

CI mirrors this on pushes and PRs to `develop`; security scanning (bandit, pip-audit, gitleaks,
semgrep, trivy) runs on PRs to `main`. Commits are conventional, one per completed phase, with a
`Co-Authored-By:` trailer naming the generating model.

## Thread ownership is declared, not inferred

Anything mutable that more than one thread touches has a row below, naming the thread it belongs
to and the primitive that makes the sharing safe.

The agent runs on three threads by design (ADR-006): the **main** thread owns Tkinter, a
**worker** thread owns the asyncio loop, and `pystray` runs the **tray** on its own.

This table exists because of ADR-002. The shutdown race was never a hard concurrency problem —
`Application._loop` and `._sup` were written on the worker thread and read from the Tk thread
with nothing in between, while [[src/vigia_eew/agent_state.py#AgentState]], two files away, was
already protecting exactly that kind of state with exactly the primitive needed. The criterion
existed. Nobody had written down that the question applied here too, so it never got asked.

| State | Written by | Read by | Synchronised with |
|---|---|---|---|
| `AgentRuntime` — the worker's loop and supervisor | worker | main (Tk), at shutdown and when publishing a toast | `threading.Lock` for the pair, plus a `threading.Event` so a reader arriving early waits instead of seeing None |
| `AgentState` — connection status and last alert | worker (ingestion), main (on showing an alert) | tray | `threading.Lock` on every accessor |
| `AsyncioTkBridge` — events crossing into the UI | worker | main (Tk), polled with `widget.after()` | `queue.Queue`, which is thread-safe by construction |
| `raw_queue` — arrivals awaiting the pipeline | worker only | worker only | none needed: `asyncio.Queue` is *not* thread-safe, and it never leaves the loop that owns it |
| `Supervisor._stop` | worker only | worker only | `asyncio.Event`; a stop from another thread goes through `loop.call_soon_threadsafe` |
| `AgentState.presentation` — whether the alert guarantee holds here | main, once at startup | tray | none needed: a frozen value decided before the tray thread exists, never mutated after |

Two rules follow from the table, and both have already been broken once:

- **Publish related state together.** `AgentRuntime` hands over the loop and the supervisor in one
  locked write. Two separate assignments create a window in which one is visible and the other is
  not, and a reader that arrives inside it draws the wrong conclusion.
- **Never touch an asyncio primitive from another thread.** `asyncio.Queue` and `asyncio.Event`
  belong to their loop. Crossing that boundary is `loop.call_soon_threadsafe`, every time.

Adding synchronised state means adding a row. A lock in the code with no row here is the drift
this table exists to prevent, and the suite fails if one appears.
