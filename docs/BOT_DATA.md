# Bot game data (Phase 7 unit 2)

Format of the files written by `tools/collect_games.py`, the input of the value fit
(`tools/fit_value.py`, unit 3a). Schema version: **1** (bump it on any field change).

## Regenerate

```
uv run python -m tools.collect_games --workers 6 --matchups \
    "heuristic-v4,heuristic-v4:300" "heuristic-v4,heuristic-v2:100" "heuristic-v4,mcts-fast:20"
```

- `--matchups "SEAT0,SEAT1:COUNT" ...`: seat strings as `tools/tournament.py` accepts (profile
  overrides `heuristic-v4:max_sawyers=2;saw_target=3`, `mcts:SIMS`...). The trailing `:COUNT` is
  required. 2 players, joinery side, `win_loss` returns, standard winter (same as the tournament).
- Games take consecutive seeds from `--seed-start` (default 200) across the matchups in the order
  given. Seats are swapped on odd seeds (seat 0 plays `SEAT0` on even seeds). Seeds 101-199 are
  reserved for held-out evaluation; a schedule touching them is refused (exit 2).
- `--every N` records every Nth decision (default 1). `--games N` caps games per matchup (smoke
  runs). `--dry-run` lists the schedule. `--no-time-cap` drops MCTS wall-clock caps (without it
  `mcts-fast` moves depend on CPU load, so those games are not exactly repeatable).
- `--value-profile` (default `heuristic-v4`): the `value:` weights used for the hand-set parts `v`.
- Resumable: a seed whose `<seed>.jsonl.gz` exists is skipped. Delete the file (or use another
  `--out`) to replay it. Changing matchups or `--every` under the same `--out` mixes schemas of
  rows silently; use a fresh directory. Files are written atomically (tmp + rename).
- Output: `data/bot_games/` (git-ignored). Games are deterministic: seed string `str(seed)` through
  `tools.tournament.play_game_record`, so a collected game has the same history and final dollars
  as the tournament path for the same seed and seats (tested). The collector only reads the state.

## Layout

```
data/bot_games/manifest.json        written at the end of each run
data/bot_games/<seed>.jsonl.gz      one game: header line, row lines, footer line (JSON Lines)
```

`manifest.json`: `schema`, `git_sha`, `matchups`, `seed_start`, `games_cap`, `every`,
`value_profile`, `time_cap`, `bot_yaml_sha256` (first 16 hex of each used `data/bots/*.yaml`),
`games_scheduled/new/skipped`, `seconds`, and `games`: for each game played in this run `seed`,
`matchup` (index), `seats`, `file`, `bytes`, `rows`, `decisions`, `seconds`, `observer_seconds`
(time spent building rows), `final`. A resumed run lists only its new games.

## Records

Every line is a JSON object with a `type`.

**header** (line 1): `schema`, `seed`, `matchup`, `seats` (bot spec per seat 0, 1), `every`,
`value_profile`, and the name lists that give meaning to the row arrays: `feature_names`,
`part_names`, `components`.

**row** (one per recorded decision). A decision is a non-chance node with at least 2 legal actions
for any seat (forced single-action nodes and chance nodes are skipped and not counted). Fields:

| field | meaning |
|---|---|
| `d` | decision index (0-based, counts all decisions; with `--every N` rows have `d % N == 0`) |
| `step` | index into the full action history (chance outcomes included) at which the action is applied |
| `round`, `phase` | game round (1..8) and phase code (`lignum.game.PHASE_*`) |
| `p` | acting seat |
| `f` | per seat (index 0, 1): raw features, ordered as `feature_names` |
| `v` | per seat: the hand-set value function split into parts, ordered as `part_names`, dollars |
| `acc` | per seat: dollars accrued so far per ledger component, ordered as `components` |

`feature_names` (counts unless noted; kinds f/s/h = wood kinds 0/1/2 (fw/sw/hw, hardwood last) as
in the engine tables): `money`, `loan_level`, `loan_repay` ($ owed at the end), `joiners`, `food`,
`store` (milled wood in storage, all kinds); `sale_unmilled_*`, `sale_logs_*` (sale area);
`dry_unmilled_*`, `dry_logs_*` (drying areas, summed over the 3 areas); `woodpile_*`, `sawing_*`,
`river_*` (upstream, unmilled); `joinery_covered` / `joinery_uncovered` (pieces in joinery slots
with / without a joiner); `tasks_held`, `tasks_complete`, `task_reward_held`,
`task_reward_complete`, `task_reward_progress` ($, reward x filled/required summed);
`office` (0/1); `craft_tokens`, `craft_jokers`; `plans_live` (planned work not yet executed);
`buildings`; `winters_ahead`; `rounds_to_winter` (to the next winter, 0 if none); `winter_shortfall`
($, unweighted food/heat shortfall still ahead per `value.py`, `winter_min_weight` forced to 1).

`part_names` (sum = `value()` of `lignum/bots/value.py`, up to rounding): `money`, `loan`
(minus the owed repayment), `wood` (sale, drying and upstream wood, discounted), `joinery`,
`tasks` (without Office), `office`, `craft`, `plans`, `buildings`, `income` (future joiner
income), `winter` (minus the weighted shortfall). Source: `lignum.bots.value.value_parts`.

`components` are the ledger components of `tools/ledger.py` (the same as the tournament breakdown):
`start`, `wood_sales`, `joinery`, `tasks`, `office`, `craftwork`, `winter`, `loan_proceeds`,
`loan_repayment`, `joiner_income`, `spending`, `other_income`, `unattributed`.

**footer** (last line): `seed`, `decisions`, `rows`, `actions` (history length), `returns`,
`final` (final dollars per seat, R-083), `winner` (seats with the top return; both on a tie),
`breakdown`: per seat, the realised final dollars per component (ordered as `components`; sums to
`final`, `unattributed` is 0, `loan_repayment` = minus the repayment owed at the end).

## Rows and footers (targets)

Targets are the footer's whole-game totals. For a decision, the realised **future** dollars of a
component are `footer.breakdown[seat][c] - row.acc[seat][c]` (`acc` has `loan_repayment` 0 until
the end, so its future is the whole repayment). The hand-set parts map onto components roughly as:
`wood` -> `wood_sales`; `joinery` -> `joinery`; `tasks` -> `tasks`; `office` -> `office`; `craft` ->
`craftwork`; `winter` -> `winter` (negative); `loan` -> `loan_repayment`; `money` and `income` ->
the rest. `plans` and `buildings` have no ledger counterpart (their payoff is spread over other
components). Predict `future` from `f`, compare against `v`.

## Caution: perfect information

Features are computed from the full engine state, not from the acting player's observation. They
read only each seat's public board (the same fields `value()` reads), never the hidden cutting-area
picks, so a model trained on them can be used by a bot without leaking hidden information. Both
seats' features are in every row, whoever acts; the opponent's board is public (R-028).

## Size and speed (measured, 10 heuristic-v4 vs heuristic-v2 games, 1 worker)

- ~460 decision rows per game (~590 actions); ~7.6 KB gzip per game (~183 KB raw), ~16 B gzip /
  400 B raw per row. 10,000 games would be ~76 MB gzip.
- Row building costs ~0.13 ms per recorded row (~0.06 s per game, ~25% over a plain heuristic
  game of ~0.25 s). `--every 5` cuts size and the row cost ~5x. `mcts-fast` games take minutes
  each (the sim cost dominates; row cost is the same); budget them separately.

## Fitted value at runtime (unit 3b, `heuristic-v5`)

Features are computed by `lignum/bots/features.py` (the collector imports it, so training and
runtime agree). `lignum/bots/fitted.py` evaluates `data/bots/value_fit.yaml` in pure Python
(no numpy). Value of a seat = `money_now` + sum over the fit components of one term each: the
fit's predicted future dollars (`intercept + sum(coef * feature)`, opponent money / owed repayment
and round as extra features) for the components in the profile's `value.fitted_components`, the
hand-set term from `lignum/bots/value.py` for the others. `money` is exact and never predicted;
the targets are final minus accrued dollars, so `final = money_now + sum(future)`. `rest` is
everything not in the other components (plans, buildings, joiner income, spending, loan
proceeds). `heuristic-v5` fits wood_sales, joinery, craftwork, winter, rest and keeps tasks,
office and loan_repayment hand-set (lower held-out MAE, unit 3a). Keys in `value:`: `value_fit`
(path), `fitted_components` (list; empty = the hand-set value). Terminal states use the exact
final dollars.

`heuristic-v5` is 2-player only: the fit records its game parameters (`game_params`: players 2,
joinery on, easy winter off, the settings `tools/collect_games.py` plays) and at any other
parameters the runtime falls back to the hand-set value. The features are computed with the value
weights the fit was trained with (`data.value_profile`), so profile overrides of the heat-credit
keys do not change their scale. The profile's fit file is loaded when the bot is built (a missing
or malformed file fails there), and the collect manifest records its hash under
`<profile>:value_fit` in `bot_yaml_sha256`.
