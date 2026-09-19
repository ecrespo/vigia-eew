# Contributing to Vigía-eew

Vigía-eew is an earthquake alert agent. When it works, somebody gets a few seconds of
warning; when it fails, they get nothing and never know it failed. That asymmetry is why
this project asks for more evidence than most before calling a change done — not because
the process is valuable in itself.

Before anything else, read [the project constitution](docs/sdd/specs/00-CONSTITUTION.md).
It is nine short articles, it is not optional reading, and it settles most of the
questions a first change raises.

---

## Getting set up

**The fast path is the devcontainer.** Open the repository in a container and everything
below is already done: the interpreter, the Tk system libraries, a virtual display, the
dependencies and the git hooks.

The obstacle it removes is worth knowing about even if you set up by hand. The agent
imports `tkinter` at load time, no Python base image ships it, and uv's managed CPython —
which does carry the `_tkinter` module — still resolves `libtcl8.6` and `libtk8.6` against
the **system**. Without those two packages the import fails after a completely green
`uv sync`, which looks like a code problem and is not.

By hand, on Debian or Ubuntu:

```bash
sudo apt-get install -y libtk8.6 libtcl8.6 libxss1 xvfb
uv sync --frozen --extra dev --extra security
uv run pre-commit install
```

`--frozen` is deliberate: it installs the resolution the project verified rather than
re-resolving it. `uv.lock` is versioned for exactly that reason.

> Always run project commands through `uv run`. It guarantees the declared dependencies and
> the declared interpreter, instead of whichever system Python happens to have the packages.

---

## The quality gate

Three commands decide whether a change is acceptable, and all three must be green:

```bash
uv run pytest         # the test suite
uv run ruff check .   # lint
uv run mypy src       # type check, strict
```

Those three are the floor, not the ceiling. Article 8 asks for eight dimensions, and the
hooks run the rest for you:

```bash
uv run pre-commit run --all-files                      # the commit-stage gate
uv run pre-commit run --all-files --hook-stage pre-push  # the slower ones too
```

| | What it checks |
|---|---|
| `ruff` / `ruff format --check` | Lint and formatting. Formatting is a rule, not a preference |
| `mypy src` | Types, in `strict` mode |
| `lint-imports` | The four declared import boundaries, from `[tool.importlinter]` |
| `bandit`, `semgrep` | Static analysis for security |
| `gitleaks` | Secrets, in the tree and in history |
| `pip-audit`, `trivy` | Known advisories in the dependency tree |
| `scripts/check_coverage.py` | Coverage per criticality group: 85 % pipeline, state, config writer and history; 70 % ingest and tiles; 40 % adapters |

If a boundary check fails, read the contract name in the output before changing the code.
It is usually telling you that the change belongs somewhere else.

---

## Writing the change

**Tests come first.** Write the failing test, watch it fail for the reason you expect, then
make it pass. A test written after the fix proves the code works; it does not prove the
problem was ever there. Most requirements already have their acceptance criteria written as
Gherkin scenarios under [`docs/v1/HU/`](docs/v1/HU/) and
[`docs/reverse-sdd/HU/`](docs/reverse-sdd/HU/) — start from those rather than inventing a
criterion.

**Separate pure logic from system effects.** The pattern is everywhere in this codebase:
inject the dependency (`connect`, `sleep`, `client`, `runner`, `create_window`) and test the
decision without the I/O. Command generation, parsing, formatting and filtering are all
testable with no network, no display and no subprocess.

**Mark what crosses a boundary.** `@pytest.mark.integration` for a real process, file or
tool; `@pytest.mark.gui` for a real UI toolkit. The commit-stage batch is
`uv run pytest -m "not integration and not gui"`, and it should stay fast.

**Real-GUI tests are opt-in locally and always on in CI.** `VIGIA_GUI_TESTS=1 uv run pytest`
runs them; you need a display, which the devcontainer provides, or `xvfb-run -a` in front. CI
sets the variable, so **measure coverage the same way** or the gate will disagree with it:

```bash
VIGIA_GUI_TESTS=1 xvfb-run -a uv run pytest --cov=vigia_eew --cov-branch \
    --cov-report=json:coverage.json
uv run python scripts/check_coverage.py coverage.json
```

Without the variable the widget modules measure near zero and
`scripts/check_coverage.py` fails on a tree CI is perfectly happy with. The reason those tests
run in CI at all is that they catch what only appears when a widget is really created -- a
control that never reached the configuration panel, an image bound to the wrong Tk
interpreter, an alert window that will not build.

**Every `datetime` is timezone-aware and in UTC.** `models.py` rejects naive values.
Conversion to local time happens at the edges, in `notify/presentation.py` and `timeutil.py`.

**Code, comments, docstrings and commit messages are in English** (RNF-10). User-facing text
is translated through `i18n.py` instead of being written in place.

---

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), one per task or coherent
group, with a body that explains **what changed and why** — the why is the part a diff
cannot show.

| Prefix | For |
|---|---|
| `feat:` | New capability |
| `fix:` | A defect, in behaviour that was supposed to work |
| `docs:` | Documentation and decision records |
| `test:` | Tests, when they are the deliverable |
| `refactor:` | Structure, with behaviour unchanged |
| `style:` | Formatting only, never mixed with anything else |
| `chore:` | Tooling, releases, housekeeping |

Cite the requirement you are implementing (`REQ-xxx-nnn`) and the criterion that verifies it
(`CA-nnn.n`). A change with no requirement means either the requirement is missing or the
change is.

---

## If the specification is wrong

Stop. Update the specification, or open a change proposal in
[`docs/sdd/changes/`](docs/sdd/changes/), and only then continue. Never let the code and the
specification diverge in silence — that is what Article 9 asks for, and a lint will
eventually enforce it.

---

## Where things are

| | |
|---|---|
| [Constitution](docs/sdd/specs/00-CONSTITUTION.md) | The nine articles, and the amendment register |
| [`CLAUDE.md`](CLAUDE.md) | Architecture at a glance: ingestion, pipeline, notification, the asyncio↔Tk bridge |
| [`docs/PRD.md`](docs/PRD.md) | Requirements of the shipped product (RF-xx / RNF-xx) |
| [`docs/TECHNICAL-DESIGN.md`](docs/TECHNICAL-DESIGN.md) | The numbered ADRs |
| [`docs/v1/07-TASKS.md`](docs/v1/07-TASKS.md) | What is being built for 1.0.0, and what is done |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Diagrams: data flow, sequence, states, deployment |
