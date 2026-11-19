# LLM play protocol (Opus vs heuristic-v6)

Run `opus1`: 25 games in order, game g = seed 400+g, LLM seat g%2, opponent `heuristic-v6`.
Tool: `tools/llm_play.py` (see its docstring). Data: `data/llm_games/opus1/` (git-ignored).

## Brief for the playing agent (one agent per game, or per segment of a game)

You are playing Lignum (2nd ed. + Joinery) to win against a heuristic bot. Goal: most dollars at the end.
Allowed reading: `docs/RULES_SPEC.md` (the rules), `docs/ACTIONS.md` (action vocabulary),
`third_party/rules/player_aid.txt`, and `data/llm_games/opus1/playbook.md` + this run's `g<NN>/notes.md`.
Forbidden: `lignum/bots/`, `server/bots.py`, `tools/` sources, other files under `data/`, git history.
Do not look at the engine to predict hidden information.

1. Read the playbook (it is your accumulated knowledge from earlier games), skim the rules spec.
2. `uv run python -m tools.llm_play start --run opus1 --game N` (or `show` when resuming).
3. Loop: choose, then `act --run opus1 --game N ID [ID ...] --note "<one line: why>"`. Several ids
   can be queued when you are sure they stay legal (e.g. repeated DONE-free sub-steps); play stops
   when the turn passes. Always give a note: it is saved with the trajectory.
4. Keep `data/llm_games/opus1/g<NN>/notes.md` current every ~40 decisions: round, money, plan,
   open commitments (tasks, planned work, drying wood, loans). If your context is getting long,
   stop, make sure notes.md lets a fresh agent continue, and reply `CONTINUE`.
5. When the game ends (`RESULT` line) write the post-game review: edit `playbook.md` (keep it
   under ~150 lines; merge, don't just append): what worked, what lost money, concrete
   rules of thumb with numbers, mistakes to avoid. Compare with what the heuristic did when useful.
   Reply with the RESULT line and a 3-line summary.

## Segment-script mode (run `opus2`, from game 1 on)

Plan ahead, don't decide step by step. `act --plan "MOVE_TO(14) # why; TAKE_TASK(11); ..."` plays a
whole script of action names (or ids) and stops itself at the first illegal action, when the turn
passes to the opponent, or when a new round starts (new chance draws). A new round's tasks, craftwork,
path tokens and placement cards are only visible then, so write one script per segment, about three per
round: (1) your pick and supply-path visit, (2) the wood-work phases W1-W7 (these depend almost only on
your own state, so script the whole round: saw, move, dry, sell, place pieces), (3) winter. Re-plan only
when a script stops. Fall back to single actions when the position is unclear. Trajectory rows are still
written for every action; put the intent of the segment in the first item's `#` note.

## Baselines against the strong bots (runs `opus_strat`, `opus_az`, 2026-11-13)

Game 0's setup (seed 400, Opus P0, empty playbook, step by step, Opus 5.5 medium effort, the brief
above with "a bot" for "a heuristic bot"), opponent set by `start --opponent`. Chance in
`llm_play` is keyed by history index, so only the setup draws are shared between games on a seed;
later rounds' draws differ once the move counts differ.

| Run | Opponent | Opus $ | Bot $ | Opus tasks | Opus decisions |
|---|---|---|---|---|---|
| opus1 g00 | heuristic-v6 | 80 | 44 | 3 | 263 |
| opus_strat g00 | strategist | 52 | 33 | 2 | 281 |
| opus_az g00 | az (plan + AZ) | 64 | 64 (tie) | 3 | 264 |

Bots on the same setup (seed 400, P0 first, one game each): strategist 72-(-16) v6, 50-43
strategist; api1_it6 (docs/PPO.md) 66-4 v6, 58-43 strategist; az 60-18 v6, 54-(-5) strategist,
49-74 az.
