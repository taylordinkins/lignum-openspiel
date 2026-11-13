# Opus game 0 vs heuristic-v6: divergence analysis (2026-11-12)

Opus (P0, seed 400) won $80-$44; the v6 mirror on the same seed ended $22-$25. For each of Opus's
263 decisions, `heuristic-v6` was asked what it would play in the same state (script in the
session scratchpad; per-step output in `data/llm_games/opus1/g00/diverge.json`). One game, so
these are hypotheses, not findings.

Agreement 185/263 (70%). By type: DONE 0.84, ASSIGN_WORKER 0.93, MOVE_TO 0.55, MOVE_WOOD 0.60,
PLACE_TASK 0.50, BUILD_HUT 0/2, CHOOSE_BUILDING 0/2, PLAN_WORK 0/1, BUY_SAW 0/4. Routine wood
handling (hire, assign, sell, saw) agrees; the gap is in strategic choices.

Where Opus differs (with its notes):
1. **Winter first.** Round-1 free plan of Heating Supply for round 2 (v6: Cutting), then sawing
   firewood disks into 12 logs covered both winters' heat. It also took nearly every free food
   token on the path (MOVE_TO a food spot where v6 goes elsewhere) and chose Storeroom.
2. **Tasks chosen by overlap.** Took tasks 14 and 12 that share one softwood disk sawn to 3 logs
   (one stage-0 slot, two dried-2 slots), plus task 4 for the hardwood already coming. v6 picked a
   different task at the first take (s148) and held a log back less often (PLACE_TASK 0.50).
3. **Huts.** Built two hut sets (board+shingle+stake, etc.): drying huts to bring logs to dried 2/3
   in time for tasks, food huts for the year-2 winter, a worker hut as a free sawyer. It collected
   craftwork tokens (MOVE_TO the shingle spot, free wagon) to complete the sets. v6 never built one.
4. **Buildings.** Storeroom and Small Storage Area (park a milled log for a dried slot) versus v6's
   Small Workshop / Small Joinery choices.
5. **Contested wood.** Went to the forest clearing first to cut the area the opponent also picked, and
   picked cutting areas for the wood a task needs (softwood for task 14) rather than most wood.
6. Mistake it reports: joinery left empty with 2 joiners (v6 would have placed pieces).

Candidate v8 pieces, cheapest first: (a) prefer free food tokens and Heating Supply in round 1;
(b) task choice and drying by shared-requirement overlap (extends `lignum/bots/plan.py`; v7 got
tasks to +$6-7 but lost wood and winter money, so couple it with the winter-first rule);
(c) hut building (needs a craftwork-set plan); (d) building preference Storeroom / Small Storage.
