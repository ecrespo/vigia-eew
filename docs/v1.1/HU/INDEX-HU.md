# User Stories — v1.1

> 9 stories · **84 acceptance criteria** in Gherkin · Input: [02-PRD-DELTA](../02-PRD-DELTA.md)

These stories continue the series of [`docs/v1/HU/`](../../v1/HU/INDICE-HU.md) (HU-101..HU-112),
which describe what v1.0 built. They are written in English, like the rest of this kit; the
identifier prefixes are kept so that cross-references between the two kits keep working.

| Story | Capability | Epic | Prio | Phase | CA | Items |
|---|---|---|---|---|---|---|
| [HU-113](HU-113-the-history-gets-a-door.md) | The history gets a door | EP-12 | **P0** | F9 | 7 | B-44, B-45 |
| [HU-114](HU-114-the-interface-queries-everything.md) | The interface queries everything the store knows | EP-13 | P1 | F10 | 10 | B-46, B-50 |
| [HU-115](HU-115-one-earthquake-one-point.md) | One earthquake, one point | EP-14 | P1 | F11 | 7 | B-47 |
| [HU-116](HU-116-the-history-in-motion.md) | The history in motion | EP-15 | P1 | F12 | 14 | B-48 |
| [HU-117](HU-117-a-history-with-depth.md) | A history with depth | EP-16 | P2 | F13 | 12 | B-49 |
| [HU-118](HU-118-figures-and-data-out.md) | Figures and data out | EP-17 | P2 | F14 | 12 | B-51 |
| [HU-119](HU-119-time-until-the-shaking.md) | The alert says when the shaking arrives — or when it did | EP-18 | P2 | F16 | 8 | B-52 |
| [HU-120](HU-120-scheduled-drill.md) | The agent tests itself | EP-18 | P2 | F16 | 10 | B-52 |
| [HU-121](HU-121-the-history-over-ssh.md) | The history over SSH | EP-19 | P3 | F15 | 4 | B-53 |

**Total: 84 criteria** over 10 backlog items.

## The two to read first

**HU-113** is the one everything else waits for: a screen that cannot be opened makes the other
eight stories invisible. It is also the cheapest, and it is verified with one command.

**HU-116** is the request this kit starts from, and the only one that begins with a spike. Its
bound on simultaneous symbols and its shortest step are figures that do not exist until T-163
measures them.

## Unhappy paths

Every story has at least one criterion for when things go wrong, because that is where a
specification written from the happy path stops:

| Story | Criteria |
|---|---|
| HU-113 | CA-113.3 (history cannot be opened) |
| HU-114 | CA-114.4 (invalid date range), CA-114.10 (no map) |
| HU-115 | CA-115.4 (no alerted arrival to stand for the earthquake) |
| HU-116 | CA-116.11 (set too large), CA-116.13 (no tiles), CA-116.14 (nothing to play) |
| HU-117 | CA-117.2 (network not recoverable), CA-117.6 (beyond retention), CA-117.7 (network down) |
| HU-118 | CA-118.4 (no live arrivals), CA-118.7 (empty set), CA-118.12 (file cannot be written) |
| HU-119 | CA-119.3 (count reaches zero), CA-119.7 (no estimate) |
| HU-120 | CA-120.4 (drill not acknowledged), CA-120.7, CA-120.8, CA-120.10 (drill against a real alert or a pause) |
| HU-121 | CA-121.3 (history cannot be opened) |
