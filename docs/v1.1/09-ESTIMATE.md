# Effort estimate — Vigía-eew v1.1

> Artifact 09 of the v1.1 kit · 2026-11-16 · Base: the 31 tasks of [07-TASKS.md](07-TASKS.md)
>
> **This is an engineering estimate, not a commitment.** It is published with its method, its
> assumptions and its sources of error so that the number can be argued with instead of believed.

## 1. Assumptions, which are half the number

| Assumption | Value |
|---|---|
| Profile | **One person** who knows the code and the stack |
| Working day | 8 h of effective work on these tasks |
| Includes | Writing the test first, the code, passing the gate, both languages, and updating the specification and `lat.md` (Art. 9) |
| **Does not include** | Waiting for decisions (V-02), review by others, interruptions |
| **Does not include** | Rework if the spike's verdict changes F12's design |

**The distinction that changes the reading most:** these are **hours of effort**, not calendar
days. Part-time work — the usual case for a single-maintainer project — stretches the calendar in
proportion.

## 2. The estimate

Built **bottom-up**, task by task, with a low–high range. The *likely* column is the midpoint.

| Phase | Epic | Tasks | Low (h) | High (h) | Likely (h) | Working days |
|---|---|---|---|---|---|---|
| F9 · The history gets a door | EP-12 | 4 | 7 | 14 | 10.5 | 1–2 |
| F10 · Full query | EP-13 | 5 | 14 | 26 | 20 | 2–3.5 |
| F11 · One earthquake, one point | EP-14 | 2 | 6 | 11 | 8.5 | 1–1.5 |
| **F12 · Timelapse** | EP-15 | 4 | **16** | **29** | 22.5 | 2–4 |
| F13 · A history with depth | EP-16 | 5 | 18 | 32 | 25 | 2.5–4 |
| F14 · Figures and export | EP-17 | 4 | 11 | 19 | 15 | 1.5–2.5 |
| F15 · The history over SSH | EP-19 | 1 | 4 | 8 | 6 | 0.5–1 |
| F16 · v1.0 promises and cut | EP-18 | 6 | 14 | 26 | 20 | 2–3.5 |
| **Total** | | **31** | **90** | **165** | **127.5** | **11–21** |

### By cut

| Cut | Phases | Low (h) | High (h) | Working days |
|---|---|---|---|---|
| **Minimum — the request** | F9–F12 | 43 | 80 | 5.5–10 |
| + depth | F9–F13 | 61 | 112 | 7.5–14 |
| + figures and export | F9–F14 | 72 | 131 | 9–16.5 |
| + TUI | F9–F15 | 76 | 139 | 9.5–17.5 |
| **Everything** | F9–F16 | 90 | 165 | 11–21 |

T-182 — the cut of the release, 2–4 h — is counted in F16. On any smaller cut it still has to be
done; add it.

## 3. Where the range comes from

| Phase | What widens it |
|---|---|
| F9 | Little. It copies T-150. The spread is the navigation's layout on a narrow window |
| F10 | Flet's date controls and the multi-select for networks; the selected marker's look; the Wayland smoke |
| F11 | Whether one window-function statement per ordering stays readable, or is better split |
| **F12** | **The spike.** A verdict of *circles while playing* adds a second painter to T-165; *not viable* stops the phase |
| F13 | Three live services, each with its dialect and its limits; how often a recovered arrival fails to join (V-06) |
| F14 | The file dialog on the packaged binary (V-10) |
| F15 | Textual's table and inputs; nothing unknown |
| F16 | T-181: any existing queue test that fails after the change is a design question, not a typo |

## 4. Against the labels of 01

01 §2 labels each epic S, M or L (S ≤ 1 h, M ≤ half a day, L > 1 day). Read as hours:

| Epic | Label | Label as hours | Bottom-up |
|---|---|---|---|
| EP-12 | S + M | ≤ 5 | 7–14 |
| EP-13 | M + M | ≤ 8 | 14–26 |
| EP-14 | S–M | 1–4 | 6–11 |
| EP-15 | M–L | 4–8+ | 16–29 |
| EP-16 | M | ≤ 4 | 18–32 |
| EP-17 | M | ≤ 4 | 11–19 |
| EP-18 | S + S | ≤ 2 | 14–26 |
| EP-19 | M | ≤ 4 | 4–8 |

The bottom-up figure is two to three times the labels everywhere but EP-19, and far more for EP-16
and EP-18. The labels priced the change to the code. The tasks price the change **done**: its test
written first, both frontends, both languages, the import contracts, the specification. EP-16 and
EP-18 are the two that turned out to be five and five tasks rather than one idea each.

**The labels still order the epics correctly. Use this table for the number.**

## 5. Sources of error

| Source | Direction | Size |
|---|---|---|
| The spike's verdict (V-01) | up | Up to a redesign of F12 — not in the range |
| Recovery defaults undecided (V-02) | neither | Calendar, not effort |
| Flet 1.0 controls behaving differently on the real client than as dataclasses | up | Hours per control; the v1.0 Flet migration saw it |
| Verification on the packaged binary (06 §5) | up | A build per phase that ships; not counted per task |
| Familiarity with the patterns already in the code | down | Every new module follows one that exists |

## 6. What this estimate does not say

- **When.** It has no calendar.
- **That the high figure is a ceiling.** It is the upper end of what was foreseen.
- **Anything about what was left out** — Wayland (B-20) above all, which remains the product's
  largest open risk and is not priced here because it is not in this kit.
