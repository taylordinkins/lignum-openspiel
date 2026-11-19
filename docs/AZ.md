# AZ bot (`lignum/bots/az/`, `tools/az_train.py`)

An AlphaZero-style bot built on the strategist: a policy-value net primed by imitation of the
strategist, a PUCT search guided by that net, and self-play iterations that retrain the net on the
search's own games. One-off work outside the PLAN.md phases (user request 2026-11-12). 2 players,
joinery side, the strategist's benchmark setting.

OpenSpiel's own AlphaZero (`open_spiel.python.algorithms.alpha_zero`) assumes a zero-sum,
perfect-information game with a fixed observation tensor and runs its C++/TF search; Lignum is a
Python game, general-sum (we maximise our own dollars), has hidden cutting-area picks and about 550
decisions a game. So the pieces are written here, in numpy (runtime) and torch (training only).

## Pieces

- **Features** (`features.py`): the engine's single-seat observer tensor (only our own hidden pick,
  R-029) with every seat-indexed field rotated so the acting seat is first, plus strategist
  planning quantities per seat (food and heat shortfall, hardwood and softwood supply, open task
  slots, reserved pieces) and the strategist's value of each laid-out task. 809 numbers.
- **Net** (`net.py`): normalised input, 512-wide stem, 3 pre-norm residual MLP blocks, a policy head
  (440 decision logits, masked to the candidates) and a value head (each seat's final dollars,
  acting seat first). Inference is plain numpy (about 0.3 ms per state), so self-play workers do
  not load torch.
- **Search** (`search.py`): PUCT. Every seat maximises its own predicted dollars (a value vector,
  not zero-sum). Each simulation resamples the other seats' unrevealed picks (R-038) and samples
  chance outcomes; a child is keyed by the move plus the chance outcomes and forced moves after it.
  - *Macro tree*: nodes only at strategic decisions (setup and round picks, the supply path:
    travel, hires, purchases, tasks, plans, buildings, huts; Overtime; the winter bonus). The
    strategist plays the wood-work and winter micro-decisions, inside the tree and at the table.
  - *Leaf evaluation*: after a new leaf the strategist plays on for `leaf_steps` decisions (both
    seats) and the net values the state reached.
  - *Priors*: the net's policy blended with the strategist's move (`prior_mix`).
  - *Confidence skip*: no search when the blended prior's top move has at least `skip_conf`.
- **Bot** (`bot.py`): `AZBot(model, SearchConfig(...))`.

## Training pipeline

1. Priming (behaviour cloning): 6000 strategist games (self-play and vs `heuristic-v6`), half the
   decisions kept: policy target the strategist's move, value target the final dollars.
2. Counterfactual value data: strategist games where a strategic decision is replaced, with
   probability 4-6 %, by an alternative drawn from the current net's prior (temperature 2). The
   policy target stays the strategist's move; the value target is the outcome after the deviation.
   This taught the value net what alternatives are worth, which the search needs.
3. AZ iterations: games played by the search (vs `heuristic-v6` and vs `strategist`, Dirichlet
   noise at searched roots), recorded with visit-count policy targets and outcome values; the net
   is fine-tuned on these plus the earlier data.

Commands are in the `tools/az_train.py` docstring.

## Results

All vs `heuristic-v6`, 2 players, AZ seat rotated, eval seeds 9000+ (never used in training). The
strategist scores $58.5 vs v6 (3000 games) and $59.9 on these seeds. sd per game is about $10-17,
so 100 games give se about $1, 50 games about $2.5.

| Setting (model, search) | Games | AZ $ |
|---|---|---|
| bc0, net policy only, no search | 100 | 49.3 |
| bc0, strategist prior only (sanity: = strategist) | 100 | 59.9 |
| bc0, search every decision, 64 sims, leaf 0 | 48 | 48.3 |
| bc0, macro, 32 sims, leaf 0 / 40 / 150 | 50 | 47.8 / 60.4 / 66.1 |
| bc1 (+ counterfactual data), macro 32 sims, leaf 0 / 40 | 50 | 54.5 / 61.5 |
| bc2 (more counterfactual data), macro 32 sims, leaf 0 / 40 / 150 | 50 | 56.6 / 63.0 / 66.6 |
| bc2, macro 64 sims, leaf 150, skip 0.97 | 100 | 69.4 |
| bc2, macro 128 sims, leaf 150, skip 0.97 | 50 | 71.6 |
| bc2, macro 64 sims, leaf 300, skip 0.97 | 50 | 69.3 |
| **it1, macro 64 sims, leaf 150, skip 0.97 (AZ alone)** | 100 | **69.4** |
| it1, same with prior_mix 0.25 | 100 | 69.8 |
| it1, same searching every decision (`--micro`) | 100 | 70.7 |
| it1, key decisions always searched at 2x sims | 100 | 70.5 |

All runs use prior_mix 0.5 unless noted. "leaf N" = strategist decisions played past a new leaf
before the net's value.

Money by component, same 48 seeds (it1 macro vs the strategist):

| Component | AZ | Strategist |
|---|---|---|
| Wood sales | 45.9 | 45.2 |
| Tasks | 47.7 | 38.8 |
| Joinery | 6.5 | 5.9 |
| Joiner income | 11.4 | 11.2 |
| Craftwork | 1.6 | 1.2 |
| Winter | -1.3 | -2.9 |
| Loans (proceeds - repayment) | -3.6 | -4.0 |
| Spending | -47.0 | -44.4 |
| Start + other income | 8.8 | 8.8 |
| **Total** | **70.1** | **59.9** |

Tasks completed 2.38 vs 1.96 (incomplete 0.04 vs 0.12): almost all of the gain is tasks, and the
AZ bot is still conservative about taking more. Iteration-1 search games: $68.7 vs v6 with
exploration noise, and $55.1 vs the strategist (the strategist's $28.8 there vs $31 in self-play).

Findings:
- A value net trained only on the strategist's own choices cannot rank alternatives: searching
  every decision with it lost $12. Counterfactual data (rare plausible deviations) fixed most of
  that cheaply; strategist playouts past the leaf fixed the rest.
- Searching only the strategic decisions keeps leaf states in the training distribution.
- One AZ iteration (1000 search games, ~250k samples) did not move the score (bc2 = it1 = 69.4):
  the search still assumes the strategist plays the rest of the game, which caps the improvement.
- Training so far is small: about 6 GPU-minutes in all, 26k cheap strategist games and 1000
  search games (about an hour on 12 cores).

## Plan-level search (`lignum/bots/plan_search.py`)

At this seat's first supply-side decision of each round, `PlanSearchBot` builds candidate
`RoundPlan`s (strategist hook in `lignum/bots/strategist.py`): the strategist's own choice, the
2 best cutting areas (when the pick is still ahead) crossed with own task choice, "no task" and
the 3 best laid-out tasks. Each plan is scored by strategist playouts to the end of the game with
common random numbers (4 for every plan, 4 more for the 3 leaders and the default; the default
gets $0.5 benefit of the doubt). The winning plan is set on the executor's strategist: the plain
strategist, or the AZ search (whose priors and default policy are that strategist). Other seats'
hidden picks are resampled from the strategist's pick model.

100 games vs `heuristic-v6`, seeds 9000+ (same seeds as above):

| Bot | $ | Tasks done | Incomplete |
|---|---|---|---|
| strategist | 59.9 | 1.96 | 0.12 |
| plan + strategist, 8 playouts | 62.1 (se 1.5) | 2.43 | 0.51 |
| plan + strategist, 16 playouts | 63.2 (se 1.2) | 2.41 | 0.44 |
| AZ (it1) | 69.4 (se 1.0) | 2.38 | 0.04 |
| **plan + AZ, 8 playouts** | **72.5 (se 1.1)** | **2.71** | 0.30 |

Plan + AZ by component: wood 39.4, tasks 52.6, joinery 5.7, joiner income 11.2, craftwork 1.9,
winter -0.7, loans -2.6, spending -44.0, start and other 9.0. Plans take more tasks (about 3 a
game); the AZ search finishes more of them than the plain strategist does, at some cost in wood
sales. A confirmation on fresh seeds (9100+) was started and stopped early at the user's request;
it is still to do.

### Two-round plans (step 1 of the multi-round search, 2026-11-13)

`PlanConfig.ahead` (`--plan-ahead N`) adds candidates "this round's task (own choice, none or a
top task), then no task or one of the N best laid-out tasks for the next seasonal round"
(`RoundPlan.then`); unclaimed tasks stay face up (R-036), and a follow-up task taken by another
seat falls back to own choice. The plan is still searched again every round. `commit_bonus`
(`--plan-commit $`) favours the scheduled task when re-planning. The strategist does not yet
reserve wood for a scheduled task it does not hold (step 2).

100 games vs `heuristic-v6`, seeds 9000+ (same seeds as above):

| Bot | $ | Tasks done | Incomplete |
|---|---|---|---|
| plan + strategist, one-round (above) | 62.1 (se 1.5) | 2.43 | 0.51 |
| plan + strategist, ahead 2 | 66.7 (se 1.3) | 2.60 | 0.41 |
| plan + AZ, one-round (above) | 72.5 (se 1.1) | 2.71 | 0.30 |
| **plan + AZ, ahead 2** | **74.3 (se 1.0)** | **2.83** | **0.15** |
| plan + AZ, ahead 2, commit $1 | 73.7 (se 1.0) | 2.78 | 0.19 |

Plan + AZ ahead 2 by component: wood 40.4, tasks 54.5, joinery 6.0, joiner income 11.4,
craftwork 1.5, winter -0.8, loans -2.7, spending -45.0, start and other 9.0. The gain is tasks
(+1.9) with half the unfinished ones; it is not just more compute (16 one-round playouts gave the
strategist only +1.1 over 8). The commit bonus did not help. Cost: about 14 min per 100 games on 12
cores.

Fresh-seed confirmation, 200 games vs `heuristic-v6`, seeds 9100+ (2026-11-13):

| Bot | $ | Tasks done | Incomplete |
|---|---|---|---|
| plan + AZ, one-round (the `az` seat) | 70.4 (se 0.8) | 2.67 | 0.28 |
| plan + AZ, ahead 2 | 71.1 (se 0.8) | 2.71 | 0.20 |

These seeds are about $2 harder than 9000+ for both. The ahead-2 gain shrinks from +1.8 to +0.7
(within noise); over all 300 games it is about +1.1. Fewer unfinished tasks holds up. The `az`
seat stays one-round for now.

### Wood for scheduled tasks (step 2, 2026-11-13)

`PlanConfig.reserve` (`--plan-reserve`; `StrategistBot.reserve_planned`): the laid-out tasks a
plan schedules for this seat and not held yet (`Ctx.planned`) join the slot plan after every held
slot: they reserve spare logs, add needs (cutting, sawing, hardwood, area value) and count for
drying-1 entries. A task's own value leaves its planned wood out (the first version counted it
against itself and took fewer tasks: $65.3 / $73.6).

100 games vs `heuristic-v6`, seeds 9000+, all with ahead 2:

| Executor | no reserve | reserve |
|---|---|---|
| plan + strategist | 66.7 (se 1.3) | 65.4 (se 1.6) |
| plan + AZ | 74.3 (se 1.0) | 73.2 (se 1.1) |

No gain (about -$1 on both, within noise). With reserve the AZ bot sells more wood (41.2 vs
40.4), earns less from tasks (53.1 vs 54.5) and leaves more unfinished (0.27 vs 0.15). A likely reading (not checked game by game): holding
spare logs for a task that may never be taken (re-planned, or taken by the other seat) costs
sales without finishing more tasks. Kept off.

## The `az` seat

`server/bots.py` registers `az` (`lignum/bots/az/seat.py`, `AZSeat`): plan + AZ, 8 plan
playouts, with the it1 model in `data/bots/az/current.npz` (float16) and the AZ settings above.
2 players on the joinery side only; other games and a missing model fall back to the strategist.
About 100 s of thinking per game (p95 1.9 s, max about 4 s per decision).
Override the model with `LIGNUM_AZ_MODEL`.

## Next ideas (logged 2026-11-12)

The goal is $75 vs `heuristic-v6`; best so far is plan + AZ at $72.5.

1. **Plan-level search (built, first version above)**: plans are one round deep (area, task).
   **Next: plans that look further ahead (logged 2026-11-13, not started).** The most likely
   path to $75. Today a plan only says which area to pick and which task to take this round; the
   strategist decides the rest round by round, so it never commits to a combination of tasks.
   Opus game 0 ($80) won by doing exactly that: tasks 14 and 12 shared one softwood disk sawn to
   3 logs. A multi-round plan would fix:
   - **A task portfolio**: the 2-3 tasks to complete over the rest of the game, chosen so their
     wood needs overlap (one disk sawn into logs for several slots; hardwood already coming),
     and the round in which each is taken.
   - **Area picks per round** for the wood that portfolio needs (softwood for overlapping slots,
     hardwood for every task), not just the best area this round.
   - **Drying timing**: which logs enter drying when, so each reaches its stage by the tasks
     phase it is needed (the strategist's slot plan already models stages; the plan would
     reserve logs for future tasks, not only held ones).
   - **Support**: buildings (Small Storage Area, Storeroom), huts (drying tokens to make up
     late stages, a worker hut for the round-8 hardwood) and planned work (Overtime for
     hardwood, Heating Supply) chosen for the portfolio.

   How: generate portfolios from the laid-out tasks (and a placeholder for tasks still to come),
   rank them by a cheap feasibility check (wood overlap, stage timing against the rounds left),
   carry out the top 10-20 with the strategist following the plan for every round, and score
   them with playouts on common random numbers. Re-plan each round, keeping the current plan
   unless another beats it by a margin (stability). Cheaper scoring: cut playouts at the end of
   the next round and use the value net, after checking its bias on plan-driven positions (and a
   cheap value refresh on plan-driven strategist games if needed). Risk seen in the first
   version: forced tasks that cannot be finished (0.3-0.5 incomplete a game), so the portfolio
   check and the playouts must price unfinished tasks.
2. **PPO / policy-gradient fine-tuning of the net (logged, not started).** Start from the
   strategist-copy net and optimise final dollars directly with reinforcement learning, using the
   value head as the baseline. Learn only at the ~136 strategic decisions per seat (most of them
   near-certain), with the strategist playing the rest. A net-only game costs about 0.15 s against
   about 50 s with search, so this can use tens of thousands of games an hour instead of 1000.
   Risk: noisy credit assignment over a long game ($15 sd per game). If it works, the improved
   policy also replaces the strategist in the search's playouts, which lifts the cap above.
3. Opponent model from observed play: the playouts assume a strategist-strength opponent;
   shifting that model toward the opponent's actual picks and routes this game (no knowledge of
   its code) should make contested task and area choices less timid against weak opponents.
4. Hybrid with an LLM at the 10-15 key decisions a game, as a probe of the ceiling (Opus game 0
   scored $80); its decisions can be distilled into the net.
5. Search tweaks: opponent moves in the tree played by the default policy (`--opp-default`,
   implemented, untested), common random numbers across siblings, adaptive sims. Probably $1-3.

