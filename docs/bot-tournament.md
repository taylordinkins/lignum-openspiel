# Bot tournament results (Phase 6, unit 10)

Status: **first run, MCTS does not yet beat the heuristic.** Unit 10 is not closed.

Setup: `uv run python -m tools.tournament --players 2 --games 100 --seed {1,2,3} --bots A,B`
(2 players, seat rotation, ties split). Win = 1 per game; 95% Wilson CI; pooled over seeds.
`mcts` = ISMCTSBot 1000 sims / 10 s cap; `mcts-fast` = 60 sims / 2 s cap (`server/bots.py`).
Cost: `mcts` ~62 s/game, `heuristic` ~0.3 s/game, so 300 `mcts` games were not run (~3.5 h each).

| Pairing | Games | First bot win rate | 95% CI |
|---|---|---|---|
| mcts-fast vs random | 300 | 0.985 | [0.964, 0.994] |
| mcts-fast vs heuristic | 300 | 0.148 | [0.113, 0.193] |
| heuristic vs random | 300 | 0.998 | [0.984, 1.000] |
| mcts vs random | 60 | 0.667 | [0.541, 0.773] |
| mcts vs heuristic | 60 | 0.058 | [0.022, 0.148] |

Caveats: the `mcts` runs shared 12 cores with 9 processes, so the 10 s cap may have cut
simulations per move; time-capped bots are not exactly reproducible. The tool does not report ms/move.

Open problems:
- Exit criterion (MCTS clearly beats random and heuristic) is not met: both MCTS settings lose to heuristic.
- `mcts` (1000 sims) does worse vs random than `mcts-fast` (60 sims); suspect the time cap under load
  or a rollout/prior problem. Needs investigation before tuning sim counts.
- Seat strings such as `mcts:50` are not supported, so sim counts cannot be swept from the CLI.

## Debugging round (2026-11-10)

Diagnosis: rollouts were random and capped at 15 plies in a 168+ decision game, so leaves were scored
almost only by `value()` (backed up as tanh(margin/25)). With more sims the search over-optimises that
estimate and drifts from the heuristic prior (300 sims at depth-0 leaves: 2% win vs heuristic), which
explains why 1000 sims did worse than 60. The 10 s cap was not the cause (~1 s/move at 1000 sims).
The "mcts vs random" result was mostly draws: random seats always end at -16 and mcts did too in 3/6 games.

2p vs heuristic, 24 games each (seeds 1-3, 8-game shards); final dollars are engine totals:

| mcts-fast variant (60 sims) | Win rate | Mean $ (mcts) | Margin |
|---|---|---|---|
| random rollout, depth 15 (baseline) | 0.146 | -13.2 | -14.4 |
| random rollout, depth 3 | 0.229 | -11.2 | -6.5 |
| value at leaf, no rollout | 0.271 | -9.5 | -2.9 |
| heuristic rollout, depth 15 | 0.354 | -5.8 | -4.5 |
| heuristic rollout, depth 40 (now default) | 0.750 | +6.7 | +12.8 |

Not yet measured: `mcts` (1000 sims) with heuristic rollouts, depth 80, 200 sims, larger prior weight.
Heuristic rollouts are slow (~15 min per 8 games at 60 sims with 3 shards in parallel).

## Rerun with heuristic rollouts (2026-11-10)

2 players, seat-balanced, `mcts-fast` = 60 sims, heuristic rollouts depth 40. Shard seeds 1001-1010 (A), 2001-2003 (B).

| Pairing | Games | mcts-fast win rate | 95% CI | mean $ (mcts-fast / opp) | mean margin |
|---|---|---|---|---|---|
| mcts-fast vs heuristic | 200 | 0.765 | [0.702, 0.818] | +3.06 / -6.74 | +9.80 |
| mcts-fast vs random | 60 | 1.000 | [0.940, 1.000] | +19.72 / -15.88 | +35.60 |

Cost: ~117 s/game vs heuristic and ~154 s/game vs random with 3-10 concurrent jobs on 12 cores.
Exit criterion (MCTS clearly beats random and heuristic, CI lower bound > 0.5) is met by `mcts-fast`.
Full-strength `mcts` (1000 sims) vs heuristic, 20 games, was still running when this was written
(results in the scratchpad `run2/C1.json`, `C2.json`); not part of the exit claim. Pooled medians
unavailable (JSON holds only per-shard summaries).

Full-strength `mcts` (1000 sims, 10 s cap) vs heuristic, 20 games (seeds 3001-3002): 11 of 20 wins
(0.55), mean $ about -2 vs -5; about 15 min per game. Not better than `mcts-fast`: with heuristic
rollouts a simulation costs 150-180 ms (4 players), so the cap leaves only ~60 sims per move.

## How to run reproducibly (Phase 7, unit 1b)

`mcts`, `mcts-fast` and `mcts:SIMS` seats stop at a wall-clock cap (10 s, 2 s, 10 s), so under CPU
load they play fewer simulations and results vary. For comparisons pass `--no-time-cap`: the cap is
dropped and the sim count alone bounds the search (`mcts:60` = 60 sims; `mcts-fast` = 60; `mcts` =
1000). Server seats keep their caps for live play; only the tournament tool uncaps.

    uv run python -m tools.tournament --players 2 --games 100 --seed 1 --bots heuristic-v1,mcts-fast --no-time-cap

With the same seed, bots and flag, the action histories are identical (tested for a sim-capped game).
Each report also gives:
- mean final dollars per bot by component (wood sales, tasks, joinery, Office, craftwork, winter
  payments, loans = proceeds minus repayment, other = start money, spending, small incomes), summing
  exactly to the engine's final dollars; `--json` has every component (`mean_breakdown`) and the
  attribution rules are in `tools/ledger.py`;
- ms/move (mean and p90 of the time to choose, over every decision including forced ones) in
  `ms_per_move`. Timings are wall-clock, so compare them only between runs on a similarly loaded machine.

## Phase 7 baselines: `heuristic-v1` (2026-11-11, unit 1c)

2 players, joinery side, `win_loss`, head-to-head with seat rotation, 100 games per seed, no MCTS seat.
Dollars are final engine totals; component columns come from `tools/ledger.py` (loans = proceeds minus
repayment; other = start money, spending, joiner income and small incomes). Pooled CIs are hand-computed
Wilson intervals; per-seed JSON is in the session scratchpad only.

| Pairing | Seeds | Games | `heuristic-v1` win rate | 95% CI | mean $ |
|---|---|---|---|---|---|
| `heuristic-v1` vs random | 1-3 | 300 | 0.998 | [0.984, 1.000] | +14.8 vs -15.8 |
| `heuristic-v1` self-play | 11-13 | 300 (600 seat-games) | 0.500 by construction | n/a | -4.5 |

Mean final dollars by component:

| Lineup | wood | tasks | joinery | office | craft | winter | loans | other | total |
|---|---|---|---|---|---|---|---|---|---|
| `heuristic-v1` (vs random) | 53.9 | 0.0 | 0.0 | 1.3 | 16.1 | -37.2 | -2.9 | -16.3 | 14.8 |
| random | 4.3 | 0.0 | 0.0 | 0.0 | 0.6 | -14.8 | -8.0 | 2.1 | -15.8 |
| `heuristic-v1` (self-play) | 33.4 | 0.0 | 0.0 | 0.6 | 8.2 | -25.2 | -7.8 | -13.7 | -4.5 |

Speed: `heuristic-v1` about 0.3 ms/move mean (p90 0.2 ms); random 0.03 ms.

Reading: the bot earns nothing from tasks and joinery and almost nothing from Office, and winter costs it
$25-37 a game. Against a human's $60+, those are the gaps (user note, 2026-11-11). The `mcts-fast` baseline
for `heuristic-v1` was skipped on purpose (D36); the Phase 6 figure above (76.5% for `mcts-fast`) stands.

## Phase 7 unit 1d/1e: `heuristic-v2` vs `heuristic-v1` (2026-11-12)

`heuristic-v2` = v1 plus winter provisioning (saws, food, full-weight stored heat), a task pipeline
(plan, take, place, dry), a bearer backlog rule (unit 1e) and joiner discipline (at most 2 joiners,
keep one milled log per kind for joinery). Bot policy only. Weights: `data/bots/heuristic_v2.yaml`.
Tuned on seeds 21-22 (100 games each); sanity seeds 31-32; **held-out exit seeds 101-103** (never used
for tuning; seeds 104-199 stay reserved). 2 players, joinery side, `win_loss`, 100 games per seed.

| Seeds | Games | v2 win rate | 95% CI | mean $ v2 / v1 |
|---|---|---|---|---|
| 101-103 (held out) | 300 | 0.948 | [0.917, 0.968] | +21.2 / -4.7 |
| 31-32 (sanity, before joiner step) | 200 | 0.955 | n/a | +20.7 / -5.1 |

Held-out mean final dollars by component (seed 101 / 102 / 103 averaged, rounded):

| Bot | wood | tasks | joinery | office | craft | winter | loans | other | total |
|---|---|---|---|---|---|---|---|---|---|
| v2 | 24.4 | 2.3 | 3.1 | 0.1 | 8.8 | -2.9 | -2.0 | -12.7 | 21.2 |
| v1 | 31.9 | 0.0 | 0.0 | 0.5 | 7.7 | -24.6 | -8.0 | -12.3 | -4.7 |

Funnels, per game (v2 / v1): winter heat units missed 0.6 / 13.1, feed units missed 0.5 / 2.5, D9
forgiven dollars 0.4 / 22; tasks taken 0.34 / 2.0, completed 0.16 / 0; joiners hired 2.0 / 3.0,
joinery pieces placed and sold 0.58 / 0.

Exit check for unit 1d: v2 beats v1 on held-out seeds (lower bound 0.917 > 0.5), tasks completed > 0,
winter shortfall down (about -25 to about -3 dollars per game). Where the +26 dollar swing comes from:
winter +21.7, loans +6.0 (fewer forced loans), joinery +3.1, tasks +2.3, craftwork +1.1, offset by wood sales -7.5 (firewood now goes to the heat store instead of being sold). The bearer backlog (unit 1e) is what makes that trade pay: it lifted v2 from about +4 to about +20 by moving cut wood to the sawmill.

Remaining gap to a human's $60+: v2 completes only about 0.16 tasks and places about 0.6 joinery pieces
per game; wood throughput into drying (milled logs reaching drying 2 and the task slots) is the limit.
Unit 2 collects data with v2 (plus `mcts-fast` games), so the fit sees these payoffs.

## Phase 7 unit 1f: `heuristic-v3` (task-first) vs `heuristic-v2` (2026-11-12) — negative result

`heuristic-v3` = v2 plus a task-first policy (profile key `task_first`): a small feasibility scheduler
values a finishable task near its full reward and an unfinishable one at 0 (replacing the partial-credit
weight), used for take, commit and value; drying capacity (1 unmilled or 2 milled logs per area) in the
schedule; wood a held task needs is kept out of the sale; hidden-pick weights favour kinds held tasks
still need. Bot policy only. Weights: `data/bots/heuristic_v3.yaml`. v2 behaviour unchanged (identical
JSON on a 20-game seed-21 run before and after). Tuned on seeds 21-22; **held-out seeds 101-103**,
2 players, joinery side, `win_loss`, head-to-head with seat rotation, 100 games per seed.

| Bot | Games | Win rate | 95% CI (Wilson) | Mean $ | Margin |
|---|---|---|---|---|---|
| v3 | 300 | 0.502 | [0.445, 0.558] | 18.9 | -0.7 |
| v2 | 300 | 0.498 | [0.442, 0.555] | 19.6 | +0.7 |

Exit (lower bound > 0.5) **not met**; v3 is not adopted and stays registered for the record.

Mean final dollars by component (averaged over the three seeds):

| Bot | wood | tasks | joinery | office | craft | winter | loans | other | total |
|---|---|---|---|---|---|---|---|---|---|
| v3 | 26.1 | 1.2 | 3.0 | 0.2 | 8.1 | -4.2 | -2.9 | -12.0 | 18.9 |
| v2 | 26.0 | 2.0 | 2.5 | 0.1 | 8.3 | -4.2 | -3.0 | -12.0 | 19.6 |

Penalties (per game, v3 / v2): winter feed shortfall -2.22 / -2.14, heat shortfall -1.98 / -2.10, loan
cost -2.9 / -3.0, forced loans 0.75 / 0.79 ($3.0 / $3.2), forced sales 0.39 / 0.43 ($0.6 / $0.6),
forgiven dollars (not money) 1.10 / 0.77, task cards bought -0.55 / -0.31.

Task funnel (per game, v3 / v2): taken 0.55 / 0.31, completed 0.08 / 0.14, left incomplete 0.47 / 0.17;
mean completion round 7.1 / 7.1 (rounds 6-8). v3 completes about 15% of the cards it takes, v2 about 45%.
Human reference: 2-3 completed. Backlog: 0.47 incomplete per game means the feasibility gate is not
gating; revisit after the throughput unit (1g). Tuning-seed sweep (seeds 21-22): take threshold 0.3 took
0.87 cards a game and lost (win 0.45), 0.7 took 0.09 (0.505), 0.5 took 0.51 (0.522, noise about ±3.5).

### Correction: the value of a task

The first diagnosis said a completed task nets only "$4-6" over selling its wood. That was wrong. From
`data/components` (`cards.yaml`, `setup.yaml`), net of the $1 card, a task's premium over selling its pieces is:

- from the sale area at base price: $4-15 (median $9, mean $9.6);
- at the drying stage the task requires: $2-12 (median $8);
- after drying every piece to +2: $1-9 (median $4). This is where the "$4-6" came from, and it is not a
  fair comparison (it prices the sale at the most favourable drying).

Rewards average $18.3 against $9.1 for the same pieces sold at the required stage (about 2x). Tasks are
worth pursuing. All 19 task cards need milled hardwood (1 disc -> 1 log), so tasks are gated by hardwood
cutting and sawing capacity, not by the decision logic. Unit 1g (`heuristic-v4`) works on throughput.

## Phase 7 unit 1g: throughput, `heuristic-v4` vs `heuristic-v2` (2026-11-12) — negative result

Bot policy only; v2 stays frozen. Funnel (`tools/ledger.py` `wood_flow`, `python -m tools.wood_flow`):
v2 cuts about 9.7 pieces a game, of which only about 1.1 are hardwood (every task card needs milled
hardwood); about 4.5 reach the sawing area and 4.1-4.3 are sawn (about 93% of arrivals), so sawing is
not the limit. No complete human game exists in `playtest/` (12 bug-report prefixes of a 4-player game
vs random bots, 37-109 actions), so no human comparison was possible.

A/B on tuning seeds 21+22 (200 games per variant, 2 players, joinery side, vs v2; every CI contains
0.5 unless marked):

| Variant | Win rate | 95% CI | Mean $ (v2) |
|---|---|---|---|
| base v4 (copy of v2) | 0.515 | [0.446, 0.583] | 18.7 (17.8) |
| `mill_saws=1` | 0.537 | [0.468, 0.605] | 19.7 (17.8) |
| `mill_saws=1`, `task_rank=premium` | 0.542 | [0.473, 0.610] | 19.9 (17.8) |
| `saw_target` 2 / 3 / 4 | 0.490 / 0.458 / 0.432 | upper bound 0.502 at 4 | 18.3 / 16.2 / 14.8 |
| `max_sawyers=2` (+ any `saw_target`) | 0.33-0.36 | upper bounds < 0.5 (worse) | 9.6-11.7 (about 18) |
| `pick_hw_task_bonus` 2 or 4 (identical) | 0.505 | [0.436, 0.574] | 18.8 (18.1) |
| `task_rank` premium or premium_piece (identical) | 0.520 | [0.451, 0.588] | 18.8 (17.7) |
| winter bonus always hardwood | 0.438 | [0.371, 0.507] | 16.8 (18.0) |
| `early_task=1` (weights 7, 9, 11 identical; not investigated) | 0.393 | [0.327, 0.462], worse | 16.3 (18.6) |
| `early_task=1`, `early_task_prob=0.3` | 0.530 | [0.461, 0.598] | 19.7 (17.8) |

Readings: a second sawyer costs about $4 a game and extra saws $1 each for no extra sawn discs; the
pick bias lifts hardwood cut only from 1.08 to about 1.16 a game (the cutting areas offer little
hardwood); both premium definitions rank the same cards through the take gate; both v1 and v2 took the
winter bonus every time (120 of 120 offers in 30 games) and always chose softwood, and the conditional
rule `bonus_kind: hardwood_if_task` fires in about 2 of 120 offers because the bot rarely holds a task
in winter; the early-task rule doubles completions (0.305) but takes 1.17 cards a game and completes
them in rounds 7-8 (r7 0.18, r8 0.235), so most of its cards lock wood and fail. The early-task code was
removed (uncommitted experiment, reverted). The CMA-ES sweep (d) was skipped: all variants are within
the noise of 200 games.

Exit check, held-out seeds 104-106 (100 games each, v4 = `mill_saws=1`, `task_rank: premium`,
`bonus_kind: hardwood_if_task`): **v4 0.503, CI [0.447, 0.560]; v2 0.497. Not met.**

| Bot | wood | tasks | joinery | office | craft | winter | loans | other | total |
|---|---|---|---|---|---|---|---|---|---|
| v4 | 25.1 | 2.1 | 2.9 | 0.1 | 8.4 | -3.9 | -2.9 | -11.8 (start 5 + joiner 7.1 + other 4.8 - spending 28.7) | 19.9 |
| v2 | 26.2 | 1.5 | 2.7 | 0.1 | 8.2 | -4.4 | -2.9 | -12.4 | 19.0 |

Penalties per game (v4 / v2): winter feed shortfall -2.18 / -2.01, heat shortfall -1.73 / -2.38, forced
loans 0.74 / 0.74 ($3.0), forced sales 0.59 / 0.52 ($0.7), forgiven dollars 0.84 / 1.07. Spending:
bearers 9.1 / 9.2, woodcutters 5.4 / 5.3, food 9.9 / 10.0, saws 2.1 / 2.0, planned work 1.1 / 1.0.
Tasks per game (v4 / v2): taken 0.32 / 0.29, completed 0.14 / 0.10, mean round 7.3 / 7.2
(v4 rounds 3, 5, 6, 7, 8: 0.003, 0.007, 0.007, 0.047, 0.080). Wood per game (all wood, v4 / v2): cut
9.7 / 9.7, sawn 4.3 / 4.1, sold 8.3 / 8.3, on tasks 0.30 / 0.21, in joinery 0.52 / 0.51, heated 12.2 /
11.9, unsold 4.9 / 5.2; hardwood cut 1.08 / 1.13. ms/move: 0.19 / 0.18 (p90 0.29 both).

Conclusion: hand-tuned bot policy is at its ceiling at about $19-20 a game; the gap to a human's $60+ is
planned work, buildings, joinery and transport efficiency (rafts, wagons, huts), which need a learned
policy. Open items for later: the feasibility gate of v3 (0.47 incomplete tasks per game), the
`tasks_early` weight having no effect, and a complete human game for a funnel comparison.

## Phase 7 unit 3b

`heuristic-v5` (v4 with the fitted value for wood_sales, joinery, craftwork, winter and rest;
`lignum/bots/fitted.py`) against `heuristic-v4`. Result: **negative, v5 not adopted** (it stays
registered).

2-player joinery win_loss head-to-head, held-out seeds 107-109, 200 games (68/66/66):
`uv run python -m tools.tournament --players 2 --games N --seed S --bots heuristic-v5,heuristic-v4 --mode head-to-head --side joinery --returns win_loss --no-time-cap`

**v5 win 0.398, CI [0.332, 0.467]; v4 0.603, CI [0.533, 0.668].** Mean dollars 14.4 vs 20.4.

| Mean $ by component | wood | tasks | joinery | office | craft | winter | loans | other |
|---|---|---|---|---|---|---|---|---|
| v5 | 24.2 | 1.4 | 1.4 | 0.1 | 8.4 | -7.6 | -3.3 | -10.2 |
| v4 | 25.4 | 2.8 | 2.8 | 0.1 | 8.3 | -3.7 | -2.9 | -12.7 |

Tasks completed per game 0.095 / 0.19. Winter feed missed 1.86 vs 0.62 units per game; forced sales
1.4-2.2 vs 0.3-0.4. ms/move 0.21 / 0.22.

Interpretation: forecast accuracy (held-out total RMSE 11.6 vs 34.4) did not translate to play. The
hand-set value's explicit winter provisioning terms were doing work that a smooth fit replaces, and
there is a train/play distribution shift (the fit was trained on v4 games).

Next ideas (not run): a hybrid with `fitted_components` [wood_sales, craftwork] only; a second
collection round with fitted bots.

## Phase 7 unit 5b: `heuristic-v6` (v4 + own-turn solver) vs `heuristic-v4` (2026-11-12)

Solver: `lignum/bots/solver.py`, beam 8, node cap 150, depth 8, leaf = v4 hand-set `value()`, run in W1-W4 and W6 (`solver.phases`); W5/W7 keep the v4 task and drying pipeline; the pipeline's sell filter applies at every W6 search node.
2p, joinery side, `win_loss`, head-to-head, seat rotation, `--no-time-cap`:
`uv run python -m tools.tournament --players 2 --games N --seed S --bots heuristic-v6,heuristic-v4 --mode head-to-head --side joinery --returns win_loss --no-time-cap`

| Run | Seeds (games) | v6 win rate [95% Wilson CI] | Mean $ v6 / v4 |
|---|---|---|---|
| first version (solver in W5/W7, W6 unfiltered) | 110-112 (200) | 0.505 [0.436, 0.574] | 21.2 / 20.7 |
| final version | 113-115 (200) | 0.570 [0.501, 0.637] | 22.8 / 20.4 |

First version: joinery placed 0.00 per game (the W6 solver sold the pieces the pipeline reserves) and tasks taken halved; fixed by the sell filter and by keeping W5/W7 on v4's pipeline.
Final version, mean $ by component (v6 / v4): wood 28.8 / 25.5, joinery 2.4 / 2.7, tasks 2.5 / 1.9, craft 8.4 / 8.5, winter -3.8 / -4.1, spending -29.4 / -28.0. Tasks completed 0.17 / 0.135 per game, joinery placed 0.47 / 0.475, winter feed missed 0.69 / 0.75. ms/move 0.82 / 0.15 (about 5x).
Reading: the gain comes from wood sales (+3.3 $). The lower bound is only just above 0.5 and the final version was tried once after an earlier tie, so treat it as promising, not proven; a further held-out run is needed before adopting v6 as the control. The solver sees one turn only: it cannot value drying progress, task timing or planned-work timing.

## Phase 7 unit 5-plan: `heuristic-v7` (v6 + task planner `lignum/bots/plan.py`) (2026-11-12)

Planner: pure function of public state; per held task: requirements, pieces available by area/drying stage, earliest eligible round, `finishable`, slack, `next_step`; `task_take_ok`; unfinishable tasks valued ~0 in the value and solver leaf; area picks, sell filter and placement follow `next_step`; credit knobs for moving a needed piece one step (`take_slack` 2, stock 0.6, sawing 0.4, woodpile 0.2, river 0.1, progress 0.3, untuned first guesses). Gate check over 20 games: every task taken was finishable at take time; precision 0.57, recall 1.0 (the plan assumes the bot's logistics succeed). First version took 28 tasks and completed 0 (older bots never carry hardwood from the woodpile).
2p, joinery, win_loss, head-to-head, `--no-time-cap`, 200 games each:

| Matchup | Seeds | v7 win rate [95% Wilson CI] | Mean $ v7 / opp | ms/move v7 / opp |
|---|---|---|---|---|
| v7 vs v6 | 116-118 | 0.470 [0.402, 0.539] | 19.9 / 20.8 | 1.49 / 1.03 |
| v7 vs v4 | 119-121 | 0.378 [0.313, 0.446] | 17.4 / 21.9 | 1.52 / 0.20 |

Mean $ by component (v7 / v6): wood 22.6 / 28.4, tasks 8.3 / 1.7, joinery 2.6 / 2.4, craft 8.4 / 7.9, winter -6.3 / -3.8, loans -4.4 / -2.8. Versus v4: wood 21.5 / 27.4, tasks 7.4 / 1.2, joinery 2.2 / 3.0, winter -6.5 / -3.3.
Funnel per game (v7 / v6; v7 / v4): tasks taken 1.04 / 0.23; 1.04 / 0.30; completed 0.48 / 0.11; 0.43 / 0.09; pieces on tasks 1.50 / 0.24; 1.36 / 0.17; mean completion round 7.33 / 7.53. Winter feed missed 0.85 / 0.75 (v6), 1.18 / 0.56 (v4); heat missed 1.85 / 0.84; forced sales 0.76 / 0.55.
Reading: the planner does what it was built for (tasks +$6 to +$7 a game, completions 4-5x) but pays more elsewhere: wood sales -$6, winter -$2.5 to -$3. Net: tie with v6 (not adopted), loses to v4 (0.378, upper bound < 0.5). Tasks are still only half completed (0.5 of 1.0 taken).

## Phase 7 unit 5c: `mcts-solver` (MCTS with the v6 solver) vs `mcts-fast` at the same sim cap (2026-11-12)

`mcts-solver:SIMS`: rollouts play `heuristic-v6` with a cheap solver (beam 3, node cap 40); the tree prior is v6 at full solver settings (in W1-W4/W6 the first action of the solver's best sequence); value function unchanged. `mcts-fast` and `mcts` are byte-identical with the knobs off.
2p, joinery, win_loss, head-to-head, seat rotation, `--no-time-cap`, 20 sims each, held-out seeds 122-127, 200 games (6 processes on 12 cores, so ms/move is contended):
`uv run python -m tools.tournament --players 2 --games N --seed S --bots mcts-solver:20,mcts-fast:20 --mode head-to-head --side joinery --returns win_loss --no-time-cap`

| | mcts-solver:20 | mcts-fast:20 |
|---|---|---|
| Win rate [95% Wilson] | 0.902 [0.853, 0.936] | 0.098 |
| Mean $ | 18.1 | -3.8 |
| wood / joinery / tasks | 19.9 / 2.0 / 1.3 | 15.4 / 0.0 / 0.0 |
| winter | -3.0 | -14.6 |
| heat units missed per game | 1.26 | 11.49 |
| joinery placed per game | 0.41 | 0.00 |
| ms/move | 222 | 334 |

Reading: a large win, but `mcts-fast` at 20 sims is a weak baseline (negative dollars, most winter heat missed); the heuristic rollouts account for much of the gap. Not yet compared: `mcts-solver` vs `mcts-fast` at 60 sims, and `mcts-solver` vs `heuristic-v6` (does MCTS add anything over the plain heuristic?). Unit 6. Mean $ of v6 in its own matchups is 21-23 (vs v4), so MCTS at 20 sims (18.1) may be below the plain heuristic; not measured head to head.
Code review (2026-11-12): no must-fix; fixed missing-solver-section error, exhaustive flag, dropped frontier at the node cap, `mcts-*:0` rejected, plan cache keyed on tables.
