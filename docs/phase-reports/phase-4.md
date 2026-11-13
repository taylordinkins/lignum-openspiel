# Phase 4 report: Engine B

**Branch:** `phase-4/planned-work-buildings` · **Date:** 2026-11-07 · **Status:** complete, awaiting your merge and ✋ playtest #2.

## Exit criteria (PLAN.md §7)

As Phase 2, for the new rules (planned work, huts, craftwork and Trade selling, all 10 buildings, `easy_winter`); you then play a full Joinery game through the shell.

| Check | Evidence (final run) |
|---|---|
| Lint, format, types | `ruff check` clean, `ruff format --check` 148 files clean, `pyright` 0 errors |
| Fast tests | `pytest -q -rxX`: **1973 passed, 2 xfailed** (both marker self-tests) |
| Slow tests | `pytest -q -m slow -rxX`: **265 passed** (incl. 3 and 4 players) |
| Random sims | `tools.sim_stats --games 400 --invariants --seed 11`: **9,600 games, 24 configs, 0 invariant violations**, all terminate (max 493 decision steps vs `MAX_DECISIONS` 3000) |
| Phase 4 coverage | all 13 counted Phase 4 actions played (BUY_SAW, BUY_FOOD, CHOOSE_BUILDING, PLAN_WORK, SELL_SET, SELL_EQUIP, BUILD_HUT, HUT_TOKEN/AREA/FOOD/DRY, USE_PW_LOGDRIVING, TAKE_OVERTIME) |
| Goldens | 4 replay exactly (new `p4_joinery_phase4_std` uses planned work, huts, buildings, craftwork) |
| Pending markers | none remain (R-096 example test fixed and unmarked) |

Random play ties in 80–86% of games and every seat takes the maximum loans, so the sim stats prove termination and invariants, not balance.

## Reviews

- **rules-auditor:** PASS, no blocker or must-fix. 1,800-game fuzz against an independent spec oracle (about 500k checks), 0 problems; 20 mutants, 15 caught. Four test gaps found (R-094 non-firewood, R-091 four-set, R-102 winter and own-area, R-090 Market entry), all closed by new tests.
- **code-reviewer:** CHANGES NEEDED, 1 blocker (Market buy/sell-food loop, below); the rest should-fix or minor. Blocker fixed and re-covered by tests; the final full run is green.

## Findings fixed

1. **Blocker: unbounded Market loop.** With the Marketstand, `BUY_FOOD`/`SELL_FOOD` could alternate forever (10,034 actions vs limit 3000). Per-visit exclusion (your decision 2026-11-07): after one is played in a visit the other is illegal; flag `visit_food` in state, observer string and tensor. Documented in `docs/ACTIONS.md` §6.
2. PW Sawing `disks_per_saw` and Small Storage Area `capacity` are read from data (guarded only; the state still models one extra disk and one stored piece).
3. `BUILD_HUT` label token count from `SET_SIZE` / `tokens_needed`; pick-log round label skips winter rounds.
4. Observer prints `win_closed` whenever set; `wturn` encodes the pair state in its own slot; scenario dump raises `S-MIDTURN` at RS/WS after `TAKE_OVERTIME` and dumps `cut_lost`.
5. R-096 spec-example test: fixture fixed, marker removed, assertions untouched.

**Existing tests edited (needs your OK):**
- `test_R108_marketstand_sells_food_...`: setup only (seat starts with food 3, money 2 instead of buying first); assertions unchanged.
- `test_picks_round_label` (server): one assertion changed; the old one encoded the wrong winter label.
- `tests/harness.py::phase_of` reads the phase directly instead of via `dump_scenario` (the new guard raises mid-Overtime); the R-097 test is unchanged.
- `tests/test_playthroughs.py`: golden count 3 to 4 (unit 15).

**Goldens:** the observer string gained `visit L/N/F`, so all four goldens' digests changed. Only the digests were rewritten; histories, labels, players and returns are identical to HEAD. Two older files (`p2_joinery_win_loss_std`, `p4_joinery_margin_std`) cannot be reproduced by the current `make_playthroughs` even from an unmodified HEAD, so they were rehashed by replaying their stored history instead of regenerated.

## Deferred (PLAN.md §9 Backlog)

Should-fix and minor items: scenario dump `w_dirty` pair close looks like a turn start; invariant drying check is skipped game-wide once any hut exists; `make_playthroughs` does not reproduce two older goldens; `disks_per_saw` and storage `capacity` are guarded, not generalised; own-area hut food same-turn case untested.

## New decisions

D30: Market food buy and sell are mutually exclusive within one visit (2026-11-07). Spec amended 2026-11-07 with your approval: R-064/R-097 Overtime and the WS node apply to round 4 as well as round 8 (ruling 2026-11-06).
