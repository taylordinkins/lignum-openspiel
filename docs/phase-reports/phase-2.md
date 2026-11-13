# Phase 2 report: Engine A

**Branch:** `phase-2/engine-a` · **Date:** 2026-11-06 · **Status:** complete, awaiting merge.

## Exit criteria (PLAN.md §7)

| Criterion | Evidence |
|---|---|
| Rule tests green | `pytest -q -rxX`: **1144 passed, 3 xfailed** (R-063 buildings, Phase 4; two marker self-tests) |
| `random_sim_test` passes for every parameter combination | `pytest -q -m slow`: **265 passed** |
| 10,000 random games, zero invariant violations | `tools.sim_stats --games 3334 --players 2 3 4 --seed 1 --invariants --jobs 4`: **80,016 games** (24 configs × 3,334), **0 violations**, 0 crashes |
| `sim_stats` report | Dollar spread, game length and loans below |

Also: `ruff check` clean, `ruff format --check` clean, `pyright` 0 errors.

## sim_stats headlines (26,672 games per player count)

| Players | Final dollars min / mean / max | Decision steps min / mean / max | Loans per game | Tie rate |
|---|---|---|---|---|
| 2 | -16 / -15.79 / -4 | 157 / 192.7 / 246 | 4 | 89.3% |
| 3 | -16 / -15.81 / -4 | 241 / 288.6 / 351 | 6 | 86.2% |
| 4 | -16 / -15.82 / -3 | 323 / 384.0 / 471 | 8 | 83.0% |

Not a bug (rules-auditor, independent money ledger and winter oracle): seats reach year-2 winter unable to pay, two loans are forced by R-073 step 2, D9 forgives the rest, and with no Market (Phase 4) missing food costs $3. Random play therefore says nothing about scoring spread; see backlog.

## Reviews

- **rules-auditor: PASS**, no blockers, no open rules questions. 17 of 20 rule mutants killed; the 3 survivors became new winter tests.
- **code-reviewer: APPROVE**, no blockers. Clone independence, hidden-pick invariance, action-id ranges and returns probed and clean.

## Findings fixed (commit `c281722`)

play_text leaked bot hidden picks in PK; FS full-information string omitted `fs_pending`/`choosers`; token-move price, joiner income and joiner spaces now read from data; R-059 harness fixed and markers removed; new R-071/R-072 winter tests; stricter invariants plus an every-legal-action-applies slow check; sim_stats prints the invariant flag and counts ties by dollars; ACTIONS.md drift fixed (IDs unchanged); stale docstrings. Goldens regenerated: only observation-trace digests changed.

## Deferred (PLAN.md §9 Backlog)

Clone speed, per-step legality recompute, `_use_worker` for Phase 4 winter hut workers, `dump_scenario` hidden-pick caution for the server, biased-policy sim, R-063 pending until Phase 4.

## New decisions

D27: information state deferred to Phase 6 (`docs/OPENSPIEL_NOTES.md`).
