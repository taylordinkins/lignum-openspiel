# Phase 6 report: Bots

**Branch:** `phase-6/bots` · **Date:** 2026-11-10 · **Status:** complete, awaiting your merge and ✋ playtest #4.

## Exit criteria (PLAN.md §7)

MCTS clearly beats random and heuristic over a few hundred 2-player games; you play against each.

| Check | Evidence |
|---|---|
| Lint, format, types | `ruff check` clean, `ruff format --check` 174 files clean, `pyright` 0 errors |
| Fast tests | `pytest -q -rxX`: **2118 passed, 2 xfailed** (marker self-tests), 0 xpassed |
| Slow tests | `pytest -q -m slow -rxX`: **260 passed** (21m13s), no test over 10 min |
| Web | `typecheck` clean; `vitest` **159 passed**; `check:api` no schema diff |
| MCTS vs heuristic | `mcts-fast` (60 sims) **153/200 wins, 0.765, 95% CI [0.702, 0.818]**; mean final $ +3.06 vs -6.74 |
| MCTS vs random | `mcts-fast` **60/60 wins, CI [0.940, 1.000]**; mean final $ +19.7 vs -15.9 |
| Full-strength `mcts` | 1000 sims vs heuristic: 11/20, no better than `mcts-fast` (cap-limited, ~15 min/game) |
| Pending markers | none remain for Phase 6 rules |
| Tasks | units 1–11 ticked |

Details and the debugging round: `docs/bot-tournament.md`. Heuristic vs random: 299.5/300.

## What landed

Engine search speed (`search_clone`), information state with pick log (D27), `lignum/bots/` (value function, heuristic per D32/D29, hidden-pick resampler, IS-MCTS and determinized MCTS), server/lobby seats `heuristic`, `mcts`, `mcts-fast` with time caps, `tools/tournament.py` (seat rotation, Wilson CI, final dollars), `spike/` removed with the C++ crash canary moved to `tests/`.

## Reviews

- **rules-auditor:** PASS. No blocker or must-fix; hidden-pick leak probe (300 nodes, 500 seat checks) 0 differences; 0 voluntary heuristic loans in 69 games; all prices from data. 2 should-fix, 4 minor.
- **code-reviewer:** CHANGES NEEDED on first pass: 1 must-fix, 2 should-fix, 3 minor.

## Findings fixed

1. **Must-fix (code-reviewer):** `clone()` dropped history, `move_number` and `serialize()`. Now `clone()` is an exact copy; bots use the separate fast `search_clone()` (~1 µs vs ~175 µs). New tests for history/serialize round-trip; the vacuous speed-test assertion was replaced with a real one.

## Findings deferred (PLAN.md §9 Backlog)

MCTS tree keyed by action path rather than information state (R-038/D22); no D29 loan test; time caps make tournaments load-dependent; route planner Planned Work cost; Storeroom food value; hard-coded value weights; plus smaller items.

## Decisions

D33 (MCTS design: heuristic rollouts depth 40, `search_clone`, path-keyed search, departure from D22). One existing test was edited in unit 7 (`tests/server/test_bots.py`: `mcts` is now a valid seat type, invalid example became `mcts:50`), as noted in the commit message.

## For playtest #4

Start the server (`tools/dev.sh`), create a lobby game with a bot seat of each kind (Heuristic, MCTS fast, MCTS) and play. `mcts` is slow (up to 10 s per move, ~60 sims) and no stronger than `mcts-fast`. Watch for illegal moves, stalls and the bots' end-game play (selling wood, tasks, loans).
