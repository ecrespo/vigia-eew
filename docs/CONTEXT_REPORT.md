# Context Report — graph-first context layers

Generated 2026-09-06 for `vigia-eew`. This report records what the three knowledge layers
(CodeGraph, Graphify, lat.md) contain, how they were built, how to refresh them, and what they
say about this repository.

The point of these layers is token efficiency: a question like "what breaks if I change
`SeismicEvent`?" costs one graph query instead of a grep-and-read sweep over 15 files, and the
answer is complete rather than best-effort.

---

## 1. Status of the three layers

| Layer | Tool | State | Artifacts in this repo |
|---|---|---|---|
| **Structure** — symbols, callers, impact | CodeGraph 1.6.0 | Built, **not committed** (see §4) | none — rebuild locally with `codegraph init .` |
| **Meaning** — semantic graph over code | Graphify 0.9.55 | Built, code-only | `graphify-out/` (`GRAPH_REPORT.md`, `graph.json`, `graph.html`) |
| **Intent** — decisions and business rules | lat.md 0.12.2 | Authored, `lat check` green | `lat.md/` (6 topical files + index) |

Consultation order for any task touching the code: **intent → structure → meaning → raw files.**
Stop as soon as you have the answer.

---

## 2. What each layer holds

### 2.1 CodeGraph (structure)

Indexed 84 files → **1,387 nodes, 3,490 edges** in 254 ms, zero LLM tokens (tree-sitter only).

```
function 495 · import 386 · method 255 · variable 89 · class 83 · file 79
python 79 files · yaml 5 files
```

Use it instead of grep for: `codegraph_search` (locate a symbol), `codegraph_callers` /
`codegraph_callees` (call graph), `codegraph_impact` (blast radius before an edit),
`codegraph_context` / `codegraph_explore` (orient inside an unfamiliar module).

Example of what it replaces: `codegraph impact SeismicEvent` returns **131 affected symbols**
across `models.py`, `pipeline/dedup.py`, `pipeline/processor.py` and 9 test modules — in one call.

### 2.2 Graphify (meaning)

**1,289 nodes · 2,821 edges · 74 communities**, 90% EXTRACTED / 10% INFERRED (296 inferred edges,
avg confidence 0.94). Built with `--code-only`, so the cost was **0 input / 0 output tokens**.

Findings worth keeping:

- **No import cycles detected.** The layered structure in `TECHNICAL-DESIGN.md` §2 holds in the
  actual code.
- **God nodes** (highest degree): `SeismicEvent` (67), `Application` (55), `StateStore` (50),
  `ReferencePoint` (44), `AgentState` (41), `RawMessage` (35). The first two are also the highest
  betweenness bridges (0.136 and 0.105) — expected for the single internal contract and the
  composition root, but they are the two symbols where a careless change costs the most.
- **74 communities**, all named. They map cleanly onto the documented layers (ingestion ×4,
  pipeline, notification, autostart ×3 platforms, config/state, i18n, TUI, tray), which is a good
  sign: the module boundaries in the plan are the boundaries the code actually has.
- **Knowledge gaps**: 3 isolated nodes (`build_linux.sh`, `build_macos.sh`, the project root) —
  build scripts with no code edges, harmless.
- **INFERRED edges to verify before trusting**: 27 on `ReferencePoint`, 25 on `StateStore`, 23
  each on `SeismicEvent` and `Application`. Confirm these with CodeGraph rather than assuming.

Open in a browser: `graphify-out/graph.html`. One-page orientation: `graphify-out/GRAPH_REPORT.md`.

### 2.3 lat.md (intent)

Six topical files, seeded from `docs/TECHNICAL-DESIGN.md` (ADR-001..ADR-018), `docs/PRD.md` and
`CLAUDE.md`. `lat check` passes with zero errors.

| File | Records |
|---|---|
| `architecture.md` | One agent per machine; push-primary/polling-backup; supervisor-restarts-children; the asyncio↔Tk two-thread split; TUI as a separate run mode; **Wayland as the known limit** of the topmost guarantee (ADR-010, designed but not implemented) |
| `ingestion.md` | Why each of the four sources exists; why GEOFON parses pipe-text and not GeoJSON; why FUNVISIS uses a seeded seen-set instead of a cursor; why distant-source events need no special-casing |
| `pipeline.md` | Why filter runs before dedup; why the country filter is a **block-list** (offshore quakes are the dangerous ones); why freshness uses the local calendar day and not UTC; the heuristic identity thresholds |
| `notification.md` | The non-dismissable contract; one-alert-at-a-time; pause delays but never drops; sound is its own layer because DND silences toasts; tray is best-effort; the two Textual naming hazards (`update_data` not `refresh`, `_paint` not `_render`) |
| `state.md` | What survives a restart and why; prune-on-register and its known limitation; the query-side half of the freshness rule; one-shot reference-point resolution and why it lives in `app.py` |
| `conventions.md` | UTC-only datetimes; fail-safe over fail-closed; DI as the reason the suite runs headless; language policy; SDD artifacts as part of the deliverable; the three-command quality gate |

These files record **why**, not how. They are the only layer a machine cannot rebuild from source,
and the only one that requires human/agent maintenance.

---

## 3. Reusable technical note — SQLite on FUSE/network mounts

**Symptom.** Building a SQLite-backed index directly inside a FUSE-mounted or network-mounted
working directory fails with `sqlite3.OperationalError: disk I/O error`, usually as soon as WAL
mode is enabled. Verified here: the mount reports filesystem type `fuseblk`, and a minimal
`PRAGMA journal_mode=WAL` + `CREATE TABLE` + `INSERT` fails on it while succeeding on native disk.

**Cause.** SQLite's locking and WAL shared-memory (`-shm`) require POSIX file-locking and mmap
semantics that FUSE and network filesystems frequently do not implement faithfully.

**Workaround — build on native disk, copy back only flat artifacts:**

```bash
rsync -a --exclude .git --exclude .venv /path/to/mounted/repo/ /tmp/work/repo/
cd /tmp/work/repo
codegraph init . -y                     # SQLite index → /tmp (native disk)
graphify extract . --code-only          # JSON/HTML artifacts, no SQLite constraint
graphify cluster-only .
rsync -a graphify-out/ /path/to/mounted/repo/graphify-out/   # flat files only
```

Copy back JSON, Markdown and HTML. **Do not** copy `.codegraph/db.sqlite` onto the mount — it will
fail to open there. This applies equally to any other SQLite-backed tool (embedding caches, local
vector stores, `lat reindex` backends).

---

## 4. What was and was not committed

**Written into the repo:**

- `graphify-out/` — `GRAPH_REPORT.md`, `graph.json`, `graph.html`, `.graphify_analysis.json`,
  `.graphify_labels.json` (+ `.sig`), `manifest.json`. Flat files, safe on any filesystem.
- `lat.md/` — the six intent files plus the index.
- `docs/CONTEXT_REPORT.md` — this file.

**Deliberately not written:**

- `.codegraph/` — its `db.sqlite` cannot live on the mount (§3), and it is a rebuildable local
  index. Each developer runs `codegraph init .` once; a file watcher keeps it fresh afterwards.

**Suggested `.gitignore` decision.** `graph.json` (1.5 MB) and `graph.html` (1.3 MB) are
regenerable. Commit `GRAPH_REPORT.md` and `lat.md/` (they are reviewed content); consider ignoring
the two large binaries-in-JSON if repo size matters:

```gitignore
.codegraph/
graphify-out/graph.json
graphify-out/graph.html
graphify-out/cache/
```

`lat.md/` should always be committed — it is documentation, and `lat check` can run in CI as a
lint step so doc/code drift fails the build.

---

## 5. Refreshing the layers

```bash
# Structure — self-maintaining via file watcher; force a rebuild if `codegraph status` looks stale
codegraph index .

# Meaning — AST-only re-parse of changed files, zero LLM cost, <5s
graphify update .
graphify hook install          # optional: post-commit/post-checkout hooks

# Intent — you maintain this one; it cannot auto-update
lat check                      # the finishing gate; must be green before a task is done
```

The division of labor: CodeGraph and Graphify maintain themselves; **lat.md is maintained by the
agent+human loop.** When a task introduces a non-obvious design decision, write the section in the
same task, then run `lat check`.

---

## 6. Known limitations of this build

1. **Graphify covers code only.** The 18 markdown documents (`PRD.md`, `TECHNICAL-DESIGN.md`,
   `API-SPEC.md`, `DATA-MODEL.md`, `ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, …) were skipped:
   the semantic pass needs an LLM backend, and none was configured in the build environment. The
   `docs/` content is instead represented in the **intent layer**, which is arguably its right home.
   To add the documents to the meaning graph later:

   ```bash
   graphify extract . --backend claude          # or gemini/openai/deepseek, with the API key set
   graphify extract ./docs --backend ollama --token-budget 4000   # free, local
   ```

2. **Community names are agent-authored, not LLM-pipeline-generated.** All 74 labels in
   `.graphify_labels.json` were written by inspecting community membership. They are accurate but
   will go stale if the clustering changes; `graphify label` with a backend will refresh them.

3. **No `// @lat:` code backlinks yet.** The intent sections link *into* code
   (`[[src/vigia_eew/models.py#SeismicEvent]]`), but the code does not yet link back. Adding
   `# @lat: [[section-id]]` comments at the governed call sites would make `lat refs` show every
   code site a decision touches, and would turn code review bidirectional. This requires editing
   source files and was left as an explicit follow-up rather than done unasked.

4. **`lat search` needs an embedding backend.** `lat locate`, `lat section`, `lat refs` and
   `lat check` are deterministic and work now; semantic search requires `lat reindex` with a
   configured backend.

5. **Nested section links need the full id.** A level-3 heading is not reachable as
   `[[file#Heading]]` — use the full path
   (`[[lat.md/pipeline#Processing pipeline#Filtering: …#Freshness uses the local calendar day rather than UTC]]`).
   `lat locate "<full id>"` resolves it. Level-2 headings work with the short form.

---

## 7. Suggested next steps

1. Run `codegraph init .` locally so the MCP tools (`codegraph_search`, `codegraph_impact`, …)
   appear in the agent's tool list — that is the layer with the highest payoff per unit of effort.
2. Decide the `.gitignore` question in §4 and commit `lat.md/` + `GRAPH_REPORT.md`.
3. Add `lat check` to `.pre-commit-config.yaml` alongside `ruff`/`mypy`, so intent drift is caught
   like any other lint failure.
4. Add the `# @lat:` backlinks (§6.3) — highest value at `Deduplicator.register()` (ADR-018),
   `GeoFilter.accepts()` (ADR-014/ADR-017) and `Application._resolve_automatic_reference()`
   (ADR-011), which are the three places where the code looks arbitrary without the decision.
5. When an LLM backend is available, run the full Graphify extraction so `docs/` joins the meaning
   graph and concepts link to code communities.
