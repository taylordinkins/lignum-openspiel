# PPO policy on top of the strategist (`lignum/bots/ppo.py`, `tools/ppo_train.py`)

Idea 2 of docs/AZ.md (user request 2026-11-13): learn a policy that beats the strategist by
reinforcement learning on final dollars, cheaply enough to play hundreds of thousands of games,
so that it can later replace the strategist inside the AZ search and the plan search (both are
capped by the strategist's playouts today). 2 players, joinery side.

## Policy

At a strategic decision (`is_strategic`: area picks, the supply path, the winter bonus) with more
than one candidate:

    pi(a | s) = softmax over candidates of  logits(s)[a] + bonus * [a == strategist(s)]

`logits` is the AZ net (same architecture and 809 features, `lignum/bots/az/`), initialised from
the strategist-primed `it1`. The fixed `bonus` (default 3) keeps the strategist's move as the
starting point: the net alone plays at $49 vs `heuristic-v6`, this policy greedily at $59.5
(strategist $60.3, 100 games, seeds 9000+). Every other decision (wood work, winter micro) is the
strategist's. Greedy (argmax) for evaluation and play; sampling during training gives about 3.6
deviations from the strategist per seat-game at bonus 3.

## Training (`uv run python -m tools.ppo_train run ...`)

- Workers (12 processes, numpy net) play `--games` games an iteration (about 70 s for 960) over
  four lineups: vs `heuristic-v6`, vs `strategist`, vs `snap` (frozen greedy copy of the policy,
  refreshed every 10 iterations) and self-play (both seats learn).
- Reward: the seat's own final dollars, no discount. Advantages: GAE (lambda 0.95) over the seat's
  own recorded decisions with the net's value head (own head on the GAE return, other seats'
  heads on their final dollars). Advantages normalised per batch.
- PPO: clipped ratio 0.2, 3 epochs, minibatch 4096, Adam lr 1e-4, gradient clip 1, plus
  `kl * KL(pi || pi_initial)` (0.05) so the policy stays near the strategist where the data is
  thin.
- Every 10 iterations: greedy evaluation, 200 games each vs `heuristic-v6` and vs `strategist`,
  seeds 9000+ (never trained on). Log: `data/bots/ppo/<out>.out` and `<out>.log.jsonl`;
  checkpoints `<out>_itN.npz` (git-ignored).
- `uv run python -m tools.ppo_train eval --model <npz> --games 200 [--ledger]` evaluates a model
  (`--who strategist` for the baseline on the same seeds).

## Findings so far (2026-11-13)

- **Plain PPO (GAE) has too little signal.** Sampling at bonus 3 gives about 3.6 deviations per
  seat-game, each judged by a final score with $14 of noise the value head cannot explain
  (v$rmse 14.3). The KL to the initial policy levels off near 0.002 and no greedy move changes.
  (ppo1 and ppo2 also had a worker cache bug, fixed since: workers kept the initial net because
  the model path never changed. Their evals at it10 and it5 after the fix: $59.2 and $58.9 vs
  v6, $30.2 and $29.4 vs strategist, all within noise of the start.)
- **Paired rollouts.** At a sampled decision, the strategist's move and an alternative b are both
  played to the end from the same state, with chance keyed to the node index (common random
  numbers). The noise of one paired difference is about $10.7 per state (CRN barely helps:
  $13 unpaired; the rest is real dependence on future deals), while true effects vary by about
  $10 between states, so one sample has signal-to-noise of about 1. About a third of
  alternatives drawn from the policy at temperature 2 beat the strategist's move; the mean is
  -$1.7.
- **PPO on paired advantages** (ppo2) still did not move: the clipped ratio allows about +30 %
  probability a step and each batch is used once, while flipping a greedy move needs about +3
  logits.
- **Advantage regression (approximate policy iteration, `api`)** works: the net's logit gap
  logit(b) - logit(strategist) is regressed (Huber) on the paired dollar advantage, so greedy
  play deviates where the predicted gain exceeds bonus x $1. Pairs are kept in shards and reused
  over a window of iterations.

## Advantage regression (`uv run python -m tools.ppo_train api ...`)

Each iteration: 1440 games over `ppo,heuristic-v6`, `ppo,strategist`, `ppo,ppo` with the policy
sampling; 15 % of the learner's strategic decisions are paired (about 35k pairs, about 12 min on
12 cores with strategist continuations); the net is refit from `it1` on the last `--window`
shards (8 epochs, lr 3e-4, Huber delta $10, `reg` 0.1 holding the other candidates' logit gaps
near it1's); greedy eval, 200 games each vs v6 and strategist, seeds 9000+. Continuations in the
paired rollouts are the strategist's (`--rollout strategist`, cheap; the greedy policy deviates
only a few times a game) or the current policy (`--rollout policy`).

## Results

Baselines (greedy, 200 games, seeds 9000+): it1 + bonus 3 = $58.7 vs `heuristic-v6`, $28.6 vs
`strategist` (strategist $33.2).

| Model | Pairs | vs v6 $ | vs strategist $ (opp, win) |
|---|---|---|---|
| it1 + bonus 3 (start = strategist) | - | 58.7 | 28.6 (33.2, 0.43) |
| strategist itself | - | 59.5 | 30.6 (30.6, 0.50) |
| ppo1_it10 (GAE PPO, 14k games) | - | 59.2 | 30.2 (32.8, 0.47) |
| ppo2_it5 (PPO on paired advantages) | 18k | 58.9 | 29.4 (32.9, 0.44) |
| api1 it1 | 35k | 56.8 | 39.1 (31.4, 0.61) |
| api1 it2 | 70k | 58.4 | 42.6 (29.4, 0.65) |
| api1 it3 | 104k | 57.2 | 43.3 (27.7, 0.71) |
| api1 it4 | 138k | 56.8 | 42.1 (26.6, 0.74) |
| api1 it5 | 137k | 55.5 | 43.0 (29.6, 0.71) |
| **api1 it6** | 135k | **58.2** | **43.8 (28.4, 0.73)** |

Iterations 2-6 used strategist continuations and a 4-shard window (about 35k pairs each). The
validation fit peaked at it4 (corr 0.16, chosen deviations +$2.2) and fell after (0.12, +$0.4)
while play stayed level: the fit is noise-limited at this data size. Next: a longer window or
more pairs per iteration, and more `heuristic-v6` games in the mix (about 5 in 6 pairs come from
games against the strategist or itself).

api1 it1 by component (both opponents pooled; strategist in brackets): winter -2.8 (-6.9),
tasks 35.9 (34.0), joinery 5.6 (4.3), wood sales 37.6 (39.3), loans net -6.5 (-5.0).

## The `azpp` seat

`server/bots.py` registers `azpp` (`AZPPSeat` in `lignum/bots/az/seat.py`): the `az` seat (plan
search over the AZ search, docs/AZ.md) with the greedy api1 it6 policy (`data/bots/ppo/current.npz`,
float16; override with `LIGNUM_AZPP_POLICY`) in place of the strategist as the default player:
plan-search playouts, AZ leaf playouts, the prior's extra-weighted move and unsearched decisions.
The AZ net is unchanged. Same fallbacks as `az` (also when the policy file is missing).

First check, 48 games vs `strategist`, seeds 9000+: azpp $61.2 ± 1.4 (opp $28.4), az $59.7 ± 1.5
(opp $27.1); within noise. Unfinished tasks 0.0 vs 0.2, loans heavier (proceeds 5.8 vs 3.5).
