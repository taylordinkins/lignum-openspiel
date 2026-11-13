# Strategist bot (`strategist` seat)

A fast, plan-driven scripted policy (`lignum/bots/strategist.py`), distilled from the rules (base
game plus Joinery and Buildings, `docs/RULES_SPEC.md`) and from Opus game 0
(`data/llm_games/export/opus_game0/`). No search, no LLM in the loop: about 0.1 ms per decision,
about 50 ms for a whole 2-player game. It reads the tasks, planned-work cards, buildings and winter
cards from the state, so nothing is tied to one deal. One-off work outside the PLAN.md phases
(user request 2026-11-12).

## Strategy

- **Tasks are the engine.** Every task needs milled hardwood, and softwood logs are the next
  bottleneck. A task is taken only when the expected hardwood and softwood supply covers it
  (`task_value`): pieces held, Overtime plans, the winter bonuses, area wood and a board rate.
- **Slot reservations by drying stage** (`make_slot_plan`): a log in zone z reaches stage s at
  the (s+1-z)-th following tasks phase (one drying step between consecutive tasks phases, winter
  included). Reserved logs are not sold, enter drying first, and are placed when they fit. The
  Small Storage Area piece and drying-hut tokens cover slots that are too late.
- **Winter**: firewood is milled for heat on a schedule (the next winter's shortfall spread over
  the rounds before it; all remaining heat in a Heating Supply round). The next winter's food is
  bought in the last round before it, with the money held back from other purchases.
- **Round plan** (`_round_plan`): which pieces to cut and carry, workers to hire (the mill worker
  and hut workers fill in for $1 hires), saws and sawyers, all within money left after the task
  fee, saws for hardwood and the food reserve.
- **Route**: a dynamic program over the remaining stops, each discounted by the chance it is
  lost to the opponent first (`keep_*` weights), plus the value of reaching the clearing first
  when sharing a cutting area (`contest_weight`).
- **Area pick**: expected value under a model of the opponents' picks (a generic wood model
  blended with each opponent's own needs); being first in travel order makes sharing cheaper.
- **Round 8**: one hut worker, a sledge and a saw are kept so the winter bonus hardwood can be
  sledged, milled and placed on an open stage-0 hardwood slot.

## Results (2 players, joinery side, 200 games, seats rotated)

| Matchup | Strategist $ | Opponent $ | Win rate |
|---|---|---|---|
| vs `heuristic-v6`, seeds 2000-2199 | 57 | 18 | 0.93 |
| self-play, seeds 3000-3199 | 32 | 32 | 0.5 |

Earlier bots scored about $20 against each other; Opus game 0 scored $80. The gap to $80 is
tasks (about 1.8 completed a game against Opus's 3); in self-play both seats compete for the same
areas and tokens. Not tried yet: more board hardwood capture, task overlap, contention-aware play.

Things that did not help (all within noise of about +-1.3 $): single-weight changes (21 tried),
the ES tuner below at 96 games per candidate, and one-step rollouts at strategic decisions
(`lignum/bots/rollout.py`, `RolloutStrategist`; $53 vs $52 on 48 games, much slower). Buying food
before saws at the Market cost about $8 a game: sawing capacity is worth more than the winter
safety.

## Use and tuning

- Seat type `strategist` in the server and lobby (`server/bots.py`, `web/src/shell/seatTypes.ts`).
- `StrategistBot(weights={...})` overrides entries of `DEFAULT_WEIGHTS`; `trace=True` re-raises
  internal errors instead of falling back to a safe legal action.
- `uv run python -m tools.tune_strategist --iters 20 --pop 8 --games 120 --procs 12` runs a simple
  evolution strategy over the weights against `strategist,heuristic-v6`. For a usable signal give
  each candidate several hundred games and keep the self-play opponent fixed.
- Tests: `tests/bots/test_strategist.py` (2-4 players and the base side with `trace=True`;
  `-m slow` checks it beats `heuristic-v6` by $15).
