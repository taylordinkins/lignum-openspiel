# Phase 7 report: Better bots

**Branch:** `phase-7/bot-value-fit` · **Date:** 2026-11-12 · **Status:** closed early by user decision (D42), awaiting your merge and ✋ playtest #5. Trained agents are not started.

## Exit criteria (PLAN.md §7) and evidence

| Criterion | Result |
|---|---|
| Tuned heuristic with fitted value beats `heuristic-v1` (lower bound > 0.5) | **Not met as written.** The fitted value (v5) lost to v4, 0.398 [0.332, 0.467]. The user adopted `heuristic-v6` (v4 + own-turn solver) as the best heuristic on the dollar numbers: 0.570 [0.501, 0.637] vs v4 (seeds 113-115, marginal). Not run against v1 directly. |
| MCTS+solver beats `mcts-fast` at equal or lower ms/move | **Met at 20 sims only:** `mcts-solver:20` 0.902 [0.853, 0.936] vs `mcts-fast:20` (seeds 122-127), 222 vs 334 ms/move. `mcts-fast` at 20 sims is a weak baseline. Not measured: vs `mcts-fast:60`, vs `heuristic-v6`. |
| Breakdown shows where the gain comes from | Done per unit in `docs/bot-tournament.md` (v6 gain is wood sales, +$3.3 a game). |
| Server seats exist | heuristic-v1..v7 are registered; `mcts-solver` is not a server seat, and there was no 3p/4p legality smoke test of the new seats (unit 6 deferred, D42). |

## Checks run at close

- `ruff check` clean, `pyright` 0 errors.
- Fast suite `uv run pytest -q`: 2222 passed, 2 xfailed (run on the 5c commit, 2a6cd58; after it only PLAN.md and agent-memory notes changed).
- **Not run:** `pytest -m slow` (the run was stopped), `check_third_party`, `npm run check:api` (the code-reviewer confirmed `web/openapi.json` matches `app.openapi()`). The engine, spec and card data are unchanged (rules-auditor diff check), so the slow engine sims are not expected to change.

## What landed

Units 1a-1g (heuristic-v1 frozen, ledger, funnel, v2-v4), 2 (`tools/collect_games.py`, 400 games), 3a/3b (`tools/fit_value.py`, fitted value, v5 not adopted), 5b (`lignum/bots/solver.py`, v6), task planner (`lignum/bots/plan.py`, v7, set aside), 5c (`mcts-solver` knobs). Unit 4 skipped (user). Unit 6 deferred. Results: `docs/bot-tournament.md`, decisions D41-D42.

## Reviews

- **rules-auditor:** PASS. No blocker or must-fix; engine, spec, card data untouched; no card values hard-coded in new bot code (two board values noted); solver turn boundary sound. 3 should-fix (Small Storage piece in round 8, planner phase timing, winter capacity in the planner) and 4 minor, all bot-quality only.
- **code-reviewer:** APPROVE. No blocker or must-fix. 3 should-fix (planner cache thread race, MCTS dropping the v7 plan weights, `fit_value` not checking the value profile) and 2 minor.
- Earlier spot audits (units 3b, 5): approved; their small findings were fixed before commit.

## Findings fixed / deferred

Fixed during the phase: all unit 3b and unit 5/5c review findings. **Deferred to PLAN.md §9 Backlog:** every close-time should-fix and minor finding above (none fixed; the fix pass was stopped by the user).

## New decisions

D41 (results: v5 not adopted, v6 adopted, v7 set aside, unit 4 skipped), D42 (closed with unit 6 deferred; exit as written not met).

## Next

Playtest #5 (you), then interview trained agents (algorithm, budget, C++ port; MCTS speed in Python is the constraint), and the deferred unit 6 work.
