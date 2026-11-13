# Lignum — OpenSpiel Implementation Plan

**Status:** v1 · 2026-11-04 (interview complete; §4 defaults confirmed except the winter-half draw in C2)
**Repository:** `taylordinkins/lignum` (private; default branch `master`)
**Rules sources, in priority order:** (1) *Lignum* second edition rulebook and *Joinery and Buildings Expansion* rulebook (Alexander Huemer, Capstone Games 2017); (2) answers marked **Official** in the FAQ at [ludex.dev/lignum/faq](https://www.ludex.dev/lignum/faq/); (3) the player aid (John Priebe, v05.15.18); (4) decisions in §3–§4 of this file.
**Component data and art:** [ludex.dev/lignum/cards](https://www.ludex.dev/lignum/cards/) (card contents and images), plus your photos of the Joinery board side and player-board extension.
**Target framework:** OpenSpiel `open-spiel==2.0.2`, Python 3.12 (same pin as `kingisdead`)
**Prior art:** `taylordinkins/kingisdead` — agents, hooks, skills, server and web shell are ported (D13)

### Progress
- [x] Phase 0 — Scaffold, agent setup ported from kingisdead, OpenSpiel spike for hidden picks, asset fetch ([report](docs/phase-reports/phase-0.md))
- [x] Phase 1 — Rules spec (base + Joinery) and component data ✋ *you review spec and card tables* ([report](docs/phase-reports/phase-1.md))
- [x] Phase 2 — Engine A: full round loop, both board sides, winter, loans, joiners, final sale
- [x] Phase 3 — Server + web shell (ported) ✋ *playtest #1 via action list + text board* ([report](docs/phase-reports/phase-3.md))
- [x] Phase 4 — Engine B: planned work, huts, craftwork market, buildings ✋ *playtest #2* ([report](docs/phase-reports/phase-4.md))
- [x] Phase 5 — Board UI with official art, generic theme, setup editor ✋ *playtest #3* ([report](docs/phase-reports/phase-5.md))
- [x] Phase 6 — Bots (random, heuristic, MCTS family) ✋ *playtest #4*
- [x] Phase 7 (closed 2026-11-12 by user decision, D42; trained agents not started, interview next) — Better bots first (fitted value, tuning, own-turn solver), then trained policies ✋ *playtest #5*
- [ ] Phase 8 — Tactical variant (swapped with trained policies, user decision 2026-11-10: the variant waits for better policies)

---

## 1. Goal

A faithful, well-tested implementation of *Lignum* with the *Joinery and Buildings* expansion as a **Python OpenSpiel game**, playable by humans in a **browser** against other humans and bots, and usable unchanged by OpenSpiel algorithms for RL work.

**Done for v1 (end of Phase 6) means:**
1. `pyspiel.load_game("python_lignum", {"players": n})` works for n = 2, 3, 4, with `joinery` on (default) and off, and passes `random_sim_test` with serialization.
2. Every rule in `docs/RULES_SPEC.md` has at least one test citing its rule ID, and every card in `data/components/` matches its source image (data-check tests plus your review).
3. You can play a full game in the browser with the official art, against any mix of humans and bots, and report a problem with one click.
4. One setting switches the UI to the generic theme, and one documented command removes all third-party material from the repo history (D11).

## 2. Scope

| In v1 | Later phases | Out of scope |
|---|---|---|
| Base game and Joinery expansion (parameter), 2–4 players | Tactical variant (Phase 8) | Solo play (the game has none) |
| Hotseat with hidden-pick handoff; random, heuristic, MCTS seats | Trained-policy opponents (Phase 7) | Networked multiplayer, accounts |
| Official art + generic theme | | Mobile-optimised UI |
| Playtest report button, replay export/import | | First-edition rules, C++ port (revisit in Phase 7 only if needed) |

## 3. Decisions log

| # | Topic | Decision | Notes |
|---|---|---|---|
| D1 | Language | Python game registered via `pyspiel.register_game` | Same as kingisdead |
| D2 | Framework | Pin `open-spiel==2.0.2`, Python 3.12 | Proven in kingisdead; its `docs/OPENSPIEL_NOTES.md` is copied in Phase 0 |
| D3 | Player counts | 2, 3 and 4 from Phase 2 | Counts differ only in setup (§4 C2); bots and training start at 2 |
| D4 | Expansion | Joinery is in the spec and engine from the start, as parameter `joinery` (default `true`). `joinery=false` gives the base game on the 20-location side | One registered game; information type doesn't change |
| D5 | Information model | `dynamics=SEQUENTIAL`, `information=IMPERFECT_INFORMATION`. The secret cutting-area pick is a run of decisions in seat order, each hidden from the others until all are made, then revealed | "Turn-based simultaneous" encoding; Phase 0 spike checks which bots accept it |
| D6 | Wood-work turn order | Strictly sequential in forest-clearing order (A, B, C, D) in every phase | Rulebook permits simultaneous play except Woodcutting; sequential is equivalent elsewhere and is the rulebook's own first-game advice |
| D7 | Returns | Parameter `returns`: `win_loss` (default) — sole winner +1, others −1/(n−1), a k-way tie gives each winner (n−k)/(k·(n−1)); `margin` — own dollars minus the mean of the others, divided by 50 and clipped to [−1, 1]. `win_loss` is zero-sum; `margin` is GENERAL_SUM (the clip makes it not exactly zero-sum for n ≥ 3; user 2026-11-04) | Policies may train on `margin` but are always evaluated on `win_loss` |
| D8 | Ties | No tiebreak; tied players share the win | FAQ (Official) and player aid |
| D9 | Unpayable winter | If a player still can't cover food/heating after 2 loans and selling every sellable piece, money stays at 0 and the shortfall is forgiven | FAQ house-rule option 1 |
| D10 | Setup | Rulebook setup, not the player aid's. Which cutting areas get 3 wood is a chance outcome; each player, in starting-player order, places a cutting token on a different 3-wood area (a decision). Seat 0 starts; the lobby chooses who sits there | Setup editor (Phase 5) can mirror a physical table |
| D11 | Third-party material | Official art, rulebook PDFs, player aid and photos are **committed** while the repo is private, all under one directory, `third_party/`. Before going public: `git filter-repo --path third_party --invert-paths`, then confirm the generic theme runs | Art and pictures are © Capstone Games; ludex.dev states no reuse licence. Keeping everything under one path makes the scrub one command, and lets cloud agent sessions read the rulebooks |
| D12 | Component data | Card contents in `data/components/*.yaml`, transcribed from ludex.dev and your photos, never hand-typed into code | Covers 19 task, 19 placement, 8 winter, 10 planned work, 10 buildings, both path layouts |
| D13 | Server and web | Copy kingisdead's game-agnostic `server/` and `web/src/shell/` into this repo in Phase 3, with its backlog fixes applied | Extracting a shared package stays an option |
| D14 | Per-seat views | The server filters every view by seat from day one | Needed for hidden picks; kingisdead deferred this |
| D15 | Model use | Sonnet workhorses, Haiku search and sims, Opus audits at phase close and spot checks (§8) | Main session defaults to Sonnet |
| D16 | Spec lock | `docs/RULES_SPEC.md` Status DRAFT → APPROVED → AMENDING; a hook blocks edits while APPROVED; only you change the Status line | As kingisdead D15 |
| D17 | Tests ahead of code | `@pytest.mark.pending("R-0xx")` (non-strict xfail); `spec-test-writer` can't read `lignum/` source (hook) | As kingisdead D16–D17 |
| D18 | Persistence | Persist action histories (plus scenario JSON for editor-built states); never accept `serialize()` strings from clients | As kingisdead D18 and its Phase 2 backlog item |
| D19 | Action encoding | Atomic typed sub-decisions with an explicit DONE; the acting player keeps acting until DONE. Fixed action table in `docs/ACTIONS.md`, frozen when Phase 2 closes | "Any time on your turn" actions are offered at defined windows (§4 C5) |
| D20 | §4 confirmations (2026-11-04) | Buildings location holds 2; jokers are wild for sets and market sales; planned work wraps into year 2 and can't land after the final winter; path-location activation (C3), $1 switch to an empty area (C4), unused workers return (C6), right-to-left drying (C10) | User confirmed C1, C3, C4, C6, C10, C13, C14 |
| D21 | Third-party guard (2026-11-04) | The CI check for images, PDFs and fonts outside `third_party/` and `assets/generic/` is advisory (warns, doesn't fail); `--strict` makes it fail | User: be more lenient than kingisdead, since the official art is wanted. D11's single-directory rule and scrub command stand |
| D22 | MCTS-family bot (2026-11-04) | Python IS-MCTS (`open_spiel.python.algorithms.ismcts.ISMCTSBot`) with a resampler that redraws other seats' unrevealed cutting-area picks; determinized Python MCTS kept as fallback/opponent. Never the C++ `MCTSBot`/`ISMCTSBot` on `python_lignum` | Phase 0 spike: the C++ bots segfault on any Python game in 2.0.2; IS-MCTS beat random 0.96 and determinized MCTS +0.28 (`docs/OPENSPIEL_NOTES.md`). Settles §5.7 |
| D23 | Equipment and fodder unlimited (2026-11-04; supersedes the earlier shortage house rule) | Equipment tokens, fodder, wood, food and money are never short (amount tokens substitute; FAQ Official). No random-draw refill fallback. Spent and sold equipment returns to the supply; craftwork sold or used for huts is removed from the game | User; C13's 'used or sold tokens leave the game' over-generalised a craftwork-only FAQ answer |
| D24 | Action vocabulary (2026-11-04) | `docs/ACTIONS.md` fixes 440 decision ids and 103 chance ids; worker-free trips are sequences of sub-actions ending in `END_TRIP`; feeding and heating are automatic (no N5/N6 hut windows) | Frozen once Phase 2 closes; ids feed replays and reports | Phase 1 unit 9, user answers A1/A3/A6/A8 |
| D25 | Base printed numbers live in data (2026-11-04) | Prices, sawing yield, drying capacity, loan repayment, winter numbers and similar base values are in `data/components/setup.yaml`, not in code | CLAUDE.md: card values only in data; the unit-11 audit (F1) found ~20 of them only as prose | Phase 1 unit 11 |
| D26 | Scenario format (2026-11-04) | Scenarios are written as in `docs/SCENARIOS.md` (JSON fields, derived state never written, S-* validation rules) | One format for tests, the setup editor and replays | Phase 1 unit 10 |
| D27 | Information state deferred (2026-11-06) | `information_state_string` equals `observation_string` in Phase 2 (`perfect_recall` unused); Phase 6 adds the per-round log of revealed picks before IS-MCTS keys on it | Public state is nearly Markov; avoids unused code now | Phase 2 close, `docs/OPENSPIEL_NOTES.md` |
| D28 | Server hidden-information policy (2026-11-06) | The seed and a per-session salt stay server-side: `GameView` and exports carry no seed, bot picks and chance draws are keyed on seed + salt, imports get a fresh salt (an explicit seed in a create request means an empty salt, deterministic, opt-in). Back is refused across a revealed pick and across a round-start chance run; dev-mode Rewind is unrestricted. `/import` is a trusted load-any-position tool (exports are not signed) | Phase 3 close audit; R-029, R-038 |
| D29 | Random-bot loans (2026-11-06) | Server random bots take `TAKE_LOAN` only when it is the only legal action, the winter shortfall (SF) forces it, or taking it newly enables an action (a purchase it could not afford). Bot policy only: R-076 and human legality are unchanged | Playtest report 20261106T213551-e2d38f; `server/bots.py` `bot_candidates` |
| D30 | Market food exclusion (2026-11-07) | `BUY_FOOD` and `SELL_FOOD` are mutually exclusive within one Market visit (per-visit flag), removing a no-op loop under the Marketstand ($1 buy, $1 sell). Spec amended 2026-11-07 (user-approved): R-064/R-097 Overtime/WS also apply in round 4 (ruling 2026-11-06) | Phase 4 close, code-reviewer blocker; user decision |
| D31 | UI wood terms (2026-11-09) | UI-only relabel applied to every user-facing string including server adapter labels: unmilled wood = "Log", milled wood = "Milled". Spec terms (R-007 disk = unmilled, log = milled), data and action IDs unchanged. Unit 9 ticked on the strength of 9a–9i | Phase 5 close, rules-auditor must-fix; user decision |
| D32 | Heuristic bot (2026-11-09) | Supply-path location choices follow a fixed ranking of marginal value per stop (from a community strategy post: joker/set-completing craftwork, planned work, task cards, cutters/bearers by wood kind, sawyers, $1 and food/saws at $1, then market, wheat+wagons, raft, sledge, the wheat craftwork); every other decision uses the expected-dollars value function with one-step lookahead. Weights live in `data/bots/heuristic.yaml`, prices come from the component data. Optional simple firewood/food-for-heating rule if cheap | Bot policy only, no rules content; user decision at `/start-phase 6` | `lignum/bots/heuristic.py` |
| D33 | MCTS design (2026-11-10) | MCTS rollouts follow the heuristic policy to depth 40, leaves scored by the expected-dollars value (random rollouts and extra sims made search worse). `clone()` is an exact C++-backed copy; bots use `search_clone()` (no history, ~175× faster). Search nodes are keyed by action path, not information state (departure from D22; see Backlog) | `mcts-fast` beats heuristic 76.5% and random 100% (`docs/bot-tournament.md`) | Phase 6 close, `docs/phase-reports/phase-6.md` |
| D34 | Phase order swap (2026-11-10) | Trained policies are now Phase 7 and the tactical variant Phase 8: the variant waits until the policies are better. Its rules are not in the spec, PLAN or player aid (rulebook PDFs have no text layer), so its mini-interview must first fix the rules source | Roadmap only; user decision at `/start-phase 7` | |
| D35 | Phase 7 scope (2026-11-11) | Phase 7 starts as bot-policy work, no rules changes: fitted value function (regression on logged games, `heuristic-v1` frozen as baseline), CMA-ES weight tuning, own-turn solver for wood-work turns used by the heuristic and MCTS; search keeps picks, tasks, buildings, plans, market tokens. Eval: 2p, joinery, win_loss, sim-count caps (no time caps), held-out seeds, 95% Wilson CI. Trained agents follow in the same phase only after these units. Optional `bots` dependency group (numpy, scikit-learn, cma); runtime bots load YAML only. Budget 6 cores, hours per run. C++ port only if measured need | Heuristic scores about -6 and best bot about +3 vs human $60+ (`docs/bot-tournament.md`) | User decision at `/start-phase 7` | |
| D36 | Phase 7 reorder (2026-11-11) | Before collecting data: cheap baselines only (mcts-fast baseline skipped), a ledger/funnel diagnostic, and a new unit 1d `heuristic-v2` (winter provisioning, task pipeline, joiner discipline). Data collection, fit, tuning, solver and MCTS comparisons use v2; `heuristic-v1` stays as the historical baseline. Reason: v1 earns $0 from tasks and joinery and pays about -$36 in winter, so a fit on its games would learn nothing about those payoffs | `heuristic-v1` 4-20 game breakdowns (`docs/bot-tournament.md`); user decision after the unit 1b report | |
| D37 | Throughput unit (2026-11-12) | Add unit 1e (transport and sawing policy) before the joiner step of 1d: with the task pipeline in, `heuristic-v2` completes ~0.05 tasks/game because ~12 of ~10+ cut pieces per game stay unmoved in woodpiles; data collection (unit 2) should run on a v2 that moves wood | v2 task funnel and woodpile counts (unit 1d step 2 report); user decision | |
| D38 | Task-first unit (2026-11-12) | Add unit 1f before data collection: the human reference is 2-3 tasks completed per game against v2's 0.16, task thresholds were swept before the bearer fix (unit 1e), and a fit on games with ~0 task payoffs would learn nothing about them. New profile `heuristic-v3`; v2 stays frozen. Units 2-6 compare against v3 if its exit passes | v2 task funnel; user decision | |
| D39 | Throughput unit (2026-11-12) | 1f failed (v3 at parity with v2, fewer tasks completed). Task value was misjudged: net of the $1 card a task's premium over selling its pieces is $4-15 from the sale area at base price (median $9, mean $9.6), $2-12 at the drying stage the task requires (median $8), $1-9 after drying every piece to +2 (median $4, the source of the wrong "$4-6"). All 19 task cards need milled hardwood, so tasks are gated by hardwood cutting and sawing capacity. Add unit 1g (profile `heuristic-v4`): wood-flow funnel first, then a direct sawing A/B, hardwood / task targeting, a CMA-ES sweep, new code only for a funnel-shown bottleneck. Units 2-6 compare against v4 if its exit passes | 1f held-out result; user decision | |
| D40 | Control heuristic closed (2026-11-12) | 1g failed its exit (v4 0.503, lower bound 0.447). Sawing capacity, transport, hardwood pick bias, task ranking, winter bonus and an early-task rule were each A/B tested on seeds 21-22 against v2: none beat v2; always-hardwood bonus and unconditional early_task lost (0.438, 0.393). The heuristic is at its ceiling for hand tuning (about $19-20 a game against a human $60+); the remaining gap is planned work, buildings, joinery and wood-flow efficiency, which need a learned policy. Unit 2 collects data from `heuristic-v4` (user decision 2026-11-12; statistically equal to v2, more task payoffs) with `heuristic-v2` and some `mcts-fast` games in the mix; units 3-6 compare against v2 as the frozen reference | 1g held-out result; user decision | |
| D41 | Phase 7 results (2026-11-12) | Fitted value (v5) lost to v4 (0.398 [0.332, 0.467]): forecast accuracy (held-out RMSE 11.6 vs 34.4 dollars) did not give better play, the hand-set winter terms did work the smooth fit removed. Unit 4 (CMA-ES) skipped. Own-turn solver `heuristic-v6` (v4 + solver in W1-W4/W6) beat v4 0.570 [0.501, 0.637] on seeds 113-115 after the W6 sell-filter fix (first version tied 0.505); the user adopts v6 as the best heuristic on the dollar numbers although the lower bound is marginal. Task planner `heuristic-v7` completes 4-5x more tasks but loses elsewhere (ties v6 0.470, loses to v4 0.378): set aside | `docs/bot-tournament.md` units 3b, 5b, 5-plan | User decisions 2026-11-12 | |
| D42 | Phase 7 close with unit 6 deferred (2026-11-12) | `mcts-solver` (v6 solver in MCTS rollouts and prior) beat `mcts-fast` at 20 sims 0.902 [0.853, 0.936] at lower ms/move, a weak baseline. Not measured: vs `mcts-fast:60`, vs `heuristic-v6`; `mcts-solver` is not a server seat, no 3p/4p legality smoke test of the new seats, no sim-count choice (unit 6 deferred). Phase exit as written (fitted-value heuristic beats v1; server seats for the new bots) is not met | User asked to close the phase | User decision at phase close | |

## 4. Rules clarifications

Gaps and ambiguities, resolved. Each becomes a numbered entry in `docs/RULES_SPEC.md`. ⚑ = my default where no source rules on it; veto any during Phase 1 review.

**C1 — Supply path.** Forest clearing A–D follows the last location.

| | Base side (20) | Joinery side (22) |
|---|---|---|
| Bearers | 4 | 4 |
| Fodder | 6 | 6 |
| Planned work | 8 | 8 |
| Woodcutters | 10 | 10 |
| Buildings | — | 12 |
| Tasks | 13 | 14 |
| Joiner | — | 16 |
| Sawyers | 16 | 18 |
| Market | 19 | 21 |
| Equipment-token spots (13) | 1, 2, 3, 5, 7, 9, 11, 12, 14, 15, 17, 18, 20 | 1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22 |

Capacity: bearers, planned work, woodcutters, tasks, sawyers and market hold 4 foremen; fodder holds 2; Joiner holds 1; every token spot holds 1; Buildings holds 2 (confirmed 2026-11-04). Joinery-side numbering is read from your board photo.

**C2 — Player-count setup** (rulebook p.17 and board)

| | 4 players | 3 players | 2 players |
|---|---|---|---|
| Bearers / woodcutters | 10 / 16 | 8 / 12 | 6 / 8 |
| Fodder | 2 | 2 | 1 |
| Sawyers: price 0 / price 1 | 4 / 1 | 3 / 1 | 2 / 1 |
| Path tokens (+3 craftwork) | 2 wagon, 2 raft, 2 saw, 1 sledge, 1 coin, 2 food | as 4p | 1 wagon, 2 raft, 1 saw, 1 sledge, 1 coin, 2 food, 2 X (spot blocked) |
| Placement cards per round | 3 | 2 | 1 |
| Initial cutting-area firewood | 3 on four areas, 2 on two | 3 on three, 2 on three | 3 on two, 2 on four |
| Task cards / PW cards laid out | 4 / 6 | 3 / 5 | 2 / 4 |
| Buildings (Joinery) | 8 | 7 | 6 |

Shuffles, path-token placement, placement-card draws, winter-card draws and which half shows, and building draws are all chance nodes, drawn lazily so the action history stays the single source of truth. ⚑ The visible winter half is random unless `easy_winter=true`, which shows the easier half on both cards.

**C3 — Supply path movement.** Foremen move in starting-player order, cycling, until all reach the clearing (FAQ). Forward only, must move, within capacity, and only onto a location whose action you carry out. "Carry out" (confirmed 2026-11-04) means at least one acquisition there that you can afford, counting loans you take in the same window. Bearers, woodcutters and fodder cost $1 each; first sawyer free, one extra for $1 (one player per round); tasks $1, one per player per round; fodder at most 1 per player per round; woodcutters capped by the wood in your selected cutting area; one joiner per round, free, max 3 per player; one building per visit, free, max 2 per player.

**C4 — Cutting-area pick, food, woodcutting.** From round 2, before travel: hidden picks (D5), reveal, then food — alone in an area takes all of it; sharing splits evenly, the remainder stays (and stays across rounds and winters, FAQ). In Woodcutting, in clearing order, each woodcutter (or the mill worker) takes 1 wood of the player's choice. A later player sharing an area either cuts what is left or pays $1 to move to an area with no other player's cutting token. That area may hold zero wood (confirmed 2026-11-04).

**C5 — "Any time on your turn".** Loans may be taken on your own turn whenever you want, in any season, including mid-turn (FAQ Official, rulebook Loan Cards section; user-confirmed 2026-11-04, amends the earlier window reading), never during another player's turn. Hut construction and hut effects keep the windows: the start of each of your supply-path moves and of each wood-work and winter phase turn.

**C6 — Workers.** The mill worker replaces one worker of any type once per round, winter included. Hut "mill worker" tokens are single-use extra workers, also in winter. Unused hired workers return to the path at round end (FAQ, unofficial; confirmed 2026-11-04).

**C7 — Transport.** Bearer 1:1. Wagon: 1 bearer + fodder + wagon token; fodder at 3 then 2; spend value 2 first; never two fodder of equal value; can't buy fodder while holding a 3; several wagons per season allowed (FAQ). Log driving: 1 bearer + rafts, 1 wood per raft, arrives at next round's Log Driving phase; none in winter. Sledge (winter only): a worker + sledge token moves 2 wood, +1 per extra food spent, up to 3 food per sledge; each worker needs its own sledge. Wood is placed in the sawing or sale area on arrival and never moves again; hardwood must go to sawing.

**C8 — Sawing.** One worker + one saw (returned) per disc: hardwood → 1, softwood → 3, firewood → 4 milled; output goes immediately to firewood storage or sale area. Max 4 saws owned; no limit on other equipment (FAQ).

**C9 — Tasks and joinery placement.** Task pieces come only from the sale area or drying areas and must match the requirement exactly: no bonus = sale area or +0; +1 needs +1; over-dried doesn't count (FAQ). Placed pieces are locked; completed tasks pay at game end only. Joinery: milled wood from the +1 drying area, all pieces of different kinds, max 3, placeable without a joiner, sellable at the final sale only with a joiner (+3 each).

**C10 — Selling and drying.** Selling: only sale and drying areas; the +2 area must be sold; no selling in winter except to cover a shortfall (FAQ). Drying: all wood in each drying area moves right together every season and can't pause; pieces in the sale area may move into the first drying area (FAQ). A drying area holds 1 unmilled or up to 2 milled. If a hut or planned work left an area over capacity, all its wood must move (player aid). Resolve right-to-left so moves can't chain (confirmed 2026-11-04).

**C11 — Winter.** Bonus: 1 wood of any kind to the woodpile, no worker. Woodcutting: the first winter woodcutting action gives 2 firewood, each further action (hut workers) 1 (FAQ). Then sledge, sawing, tasks (second winter only, after sawing), feeding (winter card + 1 per joiner), heating. Missing food or heat: $3 each, then loans, then forced sales (D9). Excess food is discarded; firewood storage is kept. No joiner income in winter.

**C12 — Loans.** $4 now; repay $7 for one, $16 for two (card flipped), at game end only. Max 2. On your turn in any season.

**C13 — Market.** Buy saws and food at $1; sell sets of identical craftwork, 2/3/4 → $2/4/6 ($5/8/11 with the Craftwork PW). Jokers are wild: a joker can complete any set and can be sold at the market as any craftwork type (confirmed 2026-11-04). Trade PW: sell rafts, sledges, wagons for $2 each. Marketstand building: sell food for $1 each. Used equipment returns to the supply and sold equipment too (Trade PW, Base p.18); sold or hut-used craftwork leaves the game (FAQ Official; D23).

**C14 — Planned work.** One PW per round per player; cost $1 per token already on the card, no cap (FAQ); the pair's number (1/2/3) sets how many seasons ahead, winter counts as a season, and planning wraps from year 1 into year 2 (FAQ, unofficial; confirmed 2026-11-04). A plan that would land after the second winter is illegal (confirmed 2026-11-04). Executable only in the planned season and only if the card allows that season (data); unmet requirements forfeit it.

**C15 — Huts.** Stake + board + shingle (joker substitutes; reed bundle replaces shingle only with Small Workshop) → 3 hut tokens on the 3 hut areas, locked once placed; several sets allowed (FAQ). Each token is single-use: drying moves a piece one area right ignoring limits (several huts may move one piece several areas); food takes the whole food supply of a cutting area with no other player's cutting token; worker is an extra worker of any type.

**C16 — Joiners.** $1 income per joiner at the start of each spring, summer and fall round, starting the round after hiring; 1 extra food per joiner in winter.

**C17 — Game end.** After the second winter: final sale (sale and drying areas; river wood of one kind only; joinery wood with a joiner at +3, +4 with Small Joinery), completed tasks pay, Office pays $1 per task card held, loans repaid. Most dollars wins (D7, D8).

**C18 — Supply limits.** Wood, food, fodder, equipment and money are unlimited (FAQ Official, D23). Workers, joiners, buildings and craftwork tokens are limited to component counts.

## 5. Architecture

### 5.1 Repository layout

```
lignum/                       # repository root
├─ PLAN.md · CLAUDE.md
├─ .claude/                   # settings.json, agents/, skills/, hooks/, rules/ (ported from kingisdead)
├─ .github/workflows/ci.yml
├─ third_party/               # © material; removed by one command before going public (D11)
│  ├─ rules/                  # rulebook PDFs, player aid, board and extension photos
│  └─ art/                    # official art fetched from ludex.dev + manifest.json
├─ assets/generic/            # original placeholder theme + manifest.json
├─ data/components/           # cards.yaml, path.yaml, setup.yaml, buildings.yaml (D12)
├─ docs/  (RULES_SPEC.md, ACTIONS.md, OPENSPIEL_NOTES.md, SCENARIOS.md, phase-reports/)
├─ lignum/                    # engine: components, constants, rules, actions, game, observer, scenario, bots/
├─ server/                    # ported FastAPI app + lignum adapter
├─ web/                       # ported React/TS shell + games/lignum/
├─ tests/  (rules/, data/, scenarios/, regressions/, playthroughs/)
├─ tools/  (play_text, replay, sim_stats, tournament, fetch_assets)
└─ playtest/reports/
```

### 5.2 OpenSpiel game definition

`short_name="python_lignum"`, `dynamics=SEQUENTIAL`, `chance_mode=EXPLICIT_STOCHASTIC`, `information=IMPERFECT_INFORMATION`, `utility=ZERO_SUM` for `returns=win_loss` and `GENERAL_SUM` for `returns=margin`, `reward_model=TERMINAL`, players 2–4. Parameters: `players` (2), `joinery` (true), `returns` ("win_loss"), `easy_winter` (false); `tactical` arrives in Phase 8. Observations through `make_py_observer` with public and private parts, so each seat's information-state tensor excludes other players' unrevealed picks. Craftwork types are public: they are taken face up, so with perfect recall hiding them adds nothing.

### 5.3 Round machine

```
SETUP (chance + token placement) ─► ROUND r = 1..8
  spring/summer/fall: joiner income ─► fill path (chance) ─► [r≥2] placement cards (chance) ─► hidden picks ─► reveal + food
                      ─► supply path (cycling starting-player order until all reach the clearing)
                      ─► wood work 1..7 in clearing order ─► new starting-player order ─► cleanup
  winter:             bonus wood ─► woodcutting ─► sledge ─► sawing ─► [year 2] tasks ─► feeding ─► heating
after r = 8: final sale ─► TERMINAL
```

### 5.4 Actions

Defined in Phase 1 (`docs/ACTIONS.md`): one small vocabulary of typed IDs (DONE, MOVE_TO loc, PICK_AREA a, TAKE/BUY item, PLACE_WOOD (kind, milled, from, to), ASSIGN_WORKER, LOAN, BUILD_HUT, USE_HUT, PLAN_WORK (card, season), CHOOSE_BUILDING, …) reused across phases, with legal-action masks doing the work. Duplicate orderings are canonicalised as in kingisdead. Target: a few hundred IDs.

### 5.5 Server and web

Ported from kingisdead (D13): the action history is the source of truth; `GameAdapter.view(state, seat)` filtered per seat (D14); a handoff curtain before each hidden pick in hotseat; Back, Rewind, Report, replay export/import; the action-list fallback keeps the game playable before the board exists.

### 5.6 Board UI and art

The board is layered sprites placed from `<theme>/manifest.json` (board, sawmill pads, extensions, cards, tokens, pawns, wood). Themes: `official` (from `third_party/art/`) and `generic` (from `assets/generic/`). A missing official sprite falls back to the generic one, so a scrubbed clone still runs. `tools/fetch_assets.py` downloads ludex.dev images into `third_party/art/` and records each source URL in the manifest. The Joinery board side and player-board extension aren't on ludex.dev; Phase 5 uses your photos (perspective-corrected), or better scans if you supply them.

### 5.7 Bots

Random; heuristic (supply-path location ranking plus expected-dollars value function, D32); Python IS-MCTS with a hidden-pick resampler (D22, chosen by the Phase 0 spike), with determinized MCTS as a fallback.

## 6. Verification strategy

Cheapest first, as kingisdead §6:

1. **Rule tests** named `test_R###_…`, written from the spec before the code, on small scenario fixtures.
2. **Invariants after every action** in random simulations: conservation of workers, fodder, joiners, buildings, equipment and craftwork; money ≥ 0; drying capacity (except hut/PW cases); locked task and joinery wood; ≤ 2 loans; ≤ 4 saws; ≤ 3 joiners; ≤ 2 buildings; non-terminal states have a legal action; returns sum to 0.
3. **OpenSpiel conformance**: `random_sim_test` with serialization over thousands of games, every parameter combination.
4. **Component data checks**: counts and schema tests, plus a rendered table of every card next to its image for your review.
5. **Golden playthroughs**: fixed-seed files; any diff explained in the commit.
6. **Independent audits**: `rules-auditor` checks the spec against the rulebooks and FAQ, and the code against the spec.
7. **Your playtests** at each ✋, using the Report button.

The Stop hook runs lint and the fast suite whenever Python changed; CI runs everything, slow simulations included, on every push. **Report → fix loop:** reproduce from the replay → failing regression test → fix → green → mark resolved.

## 7. Phases

Each phase starts with `/start-phase` (task list for your approval) and ends with `/close-phase` (evidence report, PR). ✋ = stop for you.

**Phase 0 — Scaffold & spike**
- `uv` project, pins, ruff, pytest, pyright, CI, `CLAUDE.md`; port `.claude/` agents, skills, hooks and rules from kingisdead with these fixes from its backlog: `protect_spec.py` false positives on Bash, the missing `tools/replay.py`, player numbering from 0 everywhere, `State.__str__` via the observer.
- `third_party/` populated (rulebooks, player aid, photos); `tools/fetch_assets.py` run once.
- Spike: a toy Python game with hidden sequential picks and chance — public/private observer, `random_sim_test`, IS-MCTS or determinized MCTS. Findings in `docs/OPENSPIEL_NOTES.md`.
- *Exit:* green suite; spike notes committed.

**Phase 1 — Rules spec and component data ✋**
- `RULES_SPEC.md` (base + Joinery, numbered from the rulebooks, Official FAQ answers and §4), `ACTIONS.md`, scenario format, `data/components/*.yaml`.
- `rules-auditor` checks the spec against the rulebooks and FAQ, and the data against the ludex.dev images and your photos.
- *Exit:* you approve the spec and the card tables. After that, behaviour changes need a spec amendment you sign off.

*Task list (approved 2026-11-04; branch `phase-1/rules-spec`):*
- [x] 1. Spec skeleton, components, setup, path sides — `implementer`
- [x] 2. Round structure, hidden cutting pick, seven wood-work phases, drying, sawmill — `implementer`
- [x] 3. Winter, loans, joiners, final sale, scoring, ties, `returns` — `implementer`
- [x] 4. Planned work, huts, craftwork, buildings, `easy_winter` (D20 applied) — `implementer`
- [x] 5. Spec audit vs rulebooks and FAQ — `rules-auditor`, then `implementer` fixes
- [x] 6. `cards.yaml`: 19 task, 19 placement, 8 winter (confirm easier halves) — `implementer` (+ `Explore`)
- [x] 7. `buildings.yaml` and planned-work cards — `implementer`
- [x] 8. `path.yaml` and `setup.yaml` (both sides, pads, extension) — `implementer`
- [x] 9. `docs/ACTIONS.md` — `implementer`
- [x] 10. `docs/SCENARIOS.md` — `implementer`
- [x] 11. Data audit vs ludex.dev images and photos — `rules-auditor`
- [x] 12. `tests/data/` counts, schema, action-to-rule mapping — `spec-test-writer` + `implementer`
- [x] 13. ✋ User review; user sets spec Status to APPROVED

**Phase 2 — Engine A**
- Setup, both path sides, hidden picks, all seven wood-work phases, winter, loans, joiners (hire, income, feeding, joinery wood), final sale, scoring, both `returns` modes, 2–4 players. Planned work, huts, craftwork selling, buildings and the whole Market (including saw and food buying) are absent from legal actions until Phase 4; Phase 2 sims get saws only from path tokens.
- Invariant checker, `tools/play_text.py`, golden playthroughs for 3 seeds.
- *Exit:* rule tests green; `random_sim_test` passes for every parameter combination; 10,000 random games with zero invariant violations; `sim_stats` report (dollar spread, game length, loans taken).

*Task list (approved 2026-11-05; branch `phase-2/engine-a`):*
- [x] 1. Components, data loader, constants, action IDs (R-001..R-011, R-075) — `spec-test-writer`, `implementer`
- [x] 2. Game shell, state skeleton, observer, parameters (R-001..R-003, R-028..R-032) — `spec-test-writer`, `implementer`
- [x] 3. Setup (R-012..R-020, R-026, R-027, R-031) — tests, impl, `rules-auditor` spot check
- [x] 4. Round start (R-033..R-037, R-062, R-063, R-078..R-080, R-020) — tests, impl (38 tests stay pending until units 6-10; temporary stub loop and minimal PK phase in game.py)
- [x] 5. Hidden pick and reveal (R-038, R-039) — tests, impl
- [x] 6. Supply path (R-021..R-025, R-040..R-044, R-076) — tests, impl, `rules-auditor` spot check (money)
- [x] 7. Wood work I: woodcutting, log driving, transportation (R-045..R-053) — tests, impl
- [x] 8. Wood work II: sawing, tasks, selling, drying, joinery wood (R-054..R-059, R-063, R-082) — tests, impl, `rules-auditor` spot check (drying) (5 R-059 tests and 1 R-082 test stay pending: need chance-node snapshot reads, and unit 11 final sale)
- [x] 9. End of round (R-060, R-061, R-063) — tests, impl (10 cases stay pending until winter, unit 10)
- [x] 10. Winter, loans, shortfall (R-064..R-074, R-076, R-077, R-117 data side) — tests, impl, `rules-auditor` spot check
- [x] 11. Final sale, scoring, ties, returns (R-081..R-086) — tests, impl, `rules-auditor` spot check
- [x] 12. Invariant checker, `random_sim_test`, `tools/play_text.py` — `implementer`, `sim-runner`
- [x] 13. Golden playthroughs (3 seeds), `tools/sim_stats.py` — `implementer`, `sim-runner`
- [x] 14. Exit gate: 10,000 random games, `sim_stats` report, full `rules-auditor` + `code-reviewer` pass — `sim-runner`, Opus reviewers, `implementer` fixes

**Phase 3 — Server + web shell ✋ playtest #1**
- Port server and shell; lignum adapter with per-seat views and chance labels; text board; handoff curtain; human and random seats; Playwright smoke test that finishes a game.
- *Exit:* you play one hotseat game and one against random, and file reports.

Task list (approved 2026-11-06; branch `phase-3/server-shell`):
- [x] 1. Server port from kingisdead (app, sessions, bots, reports, schemas, adapter base), backlog fixes, deps — `implementer`, `sim-runner`
- [x] 2. Lignum adapter and per-seat view (no hidden-pick leak, no `dump_scenario`) — tests, impl, Opus spot audit
- [x] 3. Labels: `action_meta` and `chance_label` for all decision/chance ids, P0-based seats — tests, impl — MUST mask other seats' unrevealed pick entries (label and id) in history (unit-2 audit blocker, server/sessions.py history_entries)
- [x] 4. Sessions, history, Back/Rewind/report, replay export/import, 2-4 player create — `implementer`, `sim-runner` — decide /export during unrevealed picks (audit should-fix); seat-B no-leak test over history, /back, bot picks
- [x] 5. Random seat and bot loop (chance auto-play, hidden-pick runs) — `implementer`
- [x] 6. Web port 1: scaffold, `api/`, generated types, `useGame` with stale-poll fixes — `implementer`
- [x] 7. Web port 2: Lobby, GameScreen, ActionList, ActionLog, YourMove, Report/Import, registry entry — `implementer`
- [x] 8. Text board plugin and handoff curtain — `implementer`
- [x] 9. Playwright smoke test that finishes a game, dev scripts, CI jobs — `implementer`, `sim-runner`
- [x] 10. Exit gate: full suite + slow, `rules-auditor` + `code-reviewer`, fixes, hand over for playtest #1 — `sim-runner`, Opus reviewers, `implementer`

**Phase 4 — Engine B ✋ playtest #2**
- Planned work (all 10 cards, seasons, costs, wrap), huts (build, three effects), craftwork and Trade selling, all 10 buildings, `easy_winter`.
- *Exit:* as Phase 2 for the new rules; you play a full Joinery game through the shell.

Task list (approved 2026-11-06; ★ = Opus spot audit):
- [x] 1. Market location: `BUY_SAW`, `BUY_FOOD`, craftwork pile draws (R-104, R-041, R-042, R-017, R-026/R-062)
- [x] 2. Craftwork selling: sets, jokers, equipment (R-105, R-058)
- [x] 3. ★ Planned work core: deck, `PLAN_WORK`, cost, season, wrap, execute/lose (R-087–R-089, R-014, R-026, R-062)
- [x] 4. PW effects: Trade, Craftwork, Sawing, Food Supply, Heating Supply (R-090–R-094)
- [x] 5. Huts: build and three effects (R-100–R-103)
- [x] 6. ★ PW Hut Construction and Drying (R-095, R-096, R-111)
- [x] 7. ★ PW Overtime, Log Driving, Cutting; `PHASE_WS` (R-097–R-099)
- [x] 8. ★ Winter hut workers; fix `_use_worker`; reconcile ACTIONS §5.2 (R-066, R-103, R-102, R-074)
- [x] 9. Buildings acquisition (R-106, R-010, R-019, R-063)
- [x] 10. Buildings A: Waterchannel, Marketstand, Storeroom, Small Workshop (R-107–R-110)
- [x] 11. Buildings B: Drying Area Upgrade, Small Joinery, Inn (R-111–R-113)
- [x] 12. Buildings C: Small Storage Area, Field, Office (R-114–R-116)
- [x] 13. `easy_winter` (R-117, R-027, R-070)
- [x] 14. View and adapter: public R-028 items, Phase 3 label fixes
- [x] 15. Sims, goldens, stale pending notes
- [x] 16. Exit gate: full suite + slow, `rules-auditor` + `code-reviewer`, fixes, hand over for playtest #2

**Phase 5 — Board UI ✋ playtest #3**
- Sprite board and sawmill pads with click-to-act, card displays, scoring breakdown, theme switch, setup editor.
- *Exit:* you play a game through with official art from the Lobby's rulebook setup (physical-table mirroring descoped 2026-11-07, optional later); the generic theme as a standalone option is optional later (it remains the per-sprite fallback).

Task list (approved 2026-11-07; setup editor covers the rulebook setup only, not mirroring a physical table or mid-game positions; photo corners picked by eye, user checks):
- [x] 1. Theme and manifest loader (official/generic lookup, fallback chain)
- [x] 2. Generic theme assets (`assets/generic/`, manifest covers every official id)
- [x] 3. Joinery art prep (`tools/prep_photos.py`: perspective-correct board side and player-board extension)
- [x] 4. Board layout engine (layered `Board.tsx`, both sides, both themes)
- [x] 5. Click-to-act for the board (legal-action hotspots, hover link)
- [x] 6. Sawmill pads and player boards (adds public R-028 view fields)
- [x] 7. Cards and scoring breakdown (rename `winter.sf_due` per spec)
- [x] 8. Setup editor and server — DESCOPED 2026-11-07 (user decision): rulebook setup only, which the Lobby already provides (players, joinery, returns, seed). No scenario loader or editor UI. Physical-table mirroring is optional later work (see §9 Backlog)
- [x] 9. Polish and e2e full official-theme game — e2e DONE (web/e2e/official_game.spec.ts); visual polish covered by 9a–9i (ticked at close 2026-11-09, user decision) (user decision 2026-11-07: official theme is the focus; generic stays as the per-sprite fallback only; theme switch UI and generic-only game are optional later, see §9 Backlog)
- [x] 9a. Layout and sizing (user playtest feedback 2026-11-07; target viewports 1366x768 and 1440x900, everything fits without page scroll): shrink overall board, sawmill and joinery boards; remake the joinery board at a usable size; drop the A-K section labels on sawmill boards
- [x] 9b. Board art: edit the official board photo (glare between cutting areas 4 and 6, table showing at upper right; ludex board as reference; derived art stays under third_party/)
- [x] 9c. Trackers and cards: season + planned-work tracker on the right, phase tracker along the top; winter, task, planned-work cards and building supply shown near their board locations (planned work may sit above the board)
- [x] 9d. Workers and joinery: default mill worker shown in each Worker Area; worker colours (bearer green, woodcutter brown, sawyer white, joiner yellow, joiner on the joinery board); building icon over the slot on the joinery board when taken
- [x] 9e. Interaction: hiring opens next to its section; selling and other actions clickable on the board; side panel folded into sections; hut token areas assignable independently in the UI (engine already allows any multiset via non-decreasing HUT_AREA; verify with a test, raise a rules item only if the engine blocks a valid split)
- [x] 9f. Generic theme polish (user request 2026-11-07): rebuild `assets/generic/` as clean flat vector art (SVG, warm wood/forest palette, crisp icons and type, light and dark variants) whose sprites sit in the same positions as the official theme (same manifest ids and anchors, both board sides); theme switch in the UI (no new generic-theme e2e game); card viewer (click/hover enlarges any card with full text and values from `data/components/*.yaml`; browse hand, discards, supply); worker tracking with no ambiguity (per-seat roster by colour/type and location, mill worker distinct from hired workers); planned-work and season tracker matching the official one, current round highlighted; event log with last-action highlight on the board. Viewer, roster, tracker and log are shared components, so they work in both themes. Needs a run-and-look session
- [x] 9g. Generic theme follow-ups (user playtest feedback 2026-11-07): remove the hover-enlarge on card clusters (the click/"+" zoom viewer replaces it; hover is flaky in the generic theme); remove the stray "Small Storage Area" label on the joinery section's building area; standardize box sizes, especially on the sawmill player boards (consistent slot/box dimensions, spacing and alignment, keeping the general layout and flow; need not match official sizes; clean, polished, functional)
- [x] 9h. Generic theme polish round 2 (user playtest feedback 2026-11-07): realign the current-round yellow box on the planned-work tracker; make planned-work tokens (1, 2, 3) clearly visible; craftwork tokens get a light-pink background distinct from equipment tokens; print wood sale prices on the sawmill sale area and the drying "+" modifier under the matching drying areas (values from data/spec, never hard-coded); fix overlap of "Year 1", "Year 2", "Final sale" on the main board's planned-work tracker; fix "Reward" overlapping requirements on task cards; add a Woodpile area above the sawmill board showing the player's held wood (sawmill and joinery boards resized jointly). User does the visual check
- [x] 9i. Generic theme round 3 (user playtest feedback 2026-11-07): money visible on the Board tab; wood sale price text no longer overlaps wood-type labels; building effect text shown on the Joinery board once a building is placed (no overlap); new "Task Cards" tab, separate from Cards, showing each seat's task cards (hidden information respected); sawmill firewood piece naming and icons in the generic theme: unmilled wood is "Log" (icon of a log), milled wood is "Milled" (disk icon); the old Disk/Log labels and icons were reversed. User does the visual check — item 5 done as UI-only relabel (user decision 2026-11-07; spec terms unchanged: R-007 disk = unmilled, log = milled)
- [x] 10. Exit gate: full suite + slow, `rules-auditor` + `code-reviewer`, fixes, phase report, hand over for playtest #3

**Phase 6 — Bots ✋ playtest #4**
- Heuristic and MCTS-family seats; `tools/tournament.py`. Task list (approved 2026-11-09, heuristic per D32):
  - [x] 1. Engine speed for search: shallow `__deepcopy__`/`clone`, cached `_tables()`, fast apply mode (`lignum/game.py`); clone ≥5× faster, goldens unchanged — `implementer`, `sim-runner`
  - [x] 2. Information state (D27): per-round log of revealed picks in `information_state_string` (`lignum/observer.py`, `game.py`); key stable across resamples, differs when revealed picks differ — `implementer`
  - [x] 3. Bot package + value function: `lignum/bots/{base,value}.py`, move `Bot`/`RandomBot` from `server/bots.py`; seat-relative expected-dollars value (money, loans, held/sale wood, task and PW payouts, data-driven prices) with unit tests — `implementer`
  - [x] 4. Heuristic bot (D32): supply-path location ranking in `data/bots/heuristic.yaml` + `lignum/bots/heuristic.py`; value function with one-step lookahead elsewhere; D29 loan policy; optional simple firewood/food-for-heating rule; beats random over 100 2p games (slow test), no illegal moves in 2–4p sims — `implementer`, `sim-runner`
  - [x] 5. Hidden-pick resampler (`lignum/bots/resample.py`): sample key equals root key, no leak, 2–4 players — `implementer`, `rules-auditor` spot check
  - [x] 6. IS-MCTS + determinized MCTS (`lignum/bots/mcts.py`), ported from `spike/bots.py`, heuristic/biased rollouts; beats random at modest sims within a time budget — `implementer`
  - [x] 7. Server + lobby: register `heuristic`, `mcts`, `mcts-fast`; per-move time cap; inline-mode `IllegalAction` backlog fix; OpenAPI types (`npm run check:api`); lobby options; bot-vs-bot game finishes via API — `implementer`
  - [x] 8. `tools/tournament.py`: head-to-head/round-robin, seat rotation, fixed seeds, win rate with CI, small slow test — `implementer`
  - [x] 9. Cleanup: delete `spike/` and `tests/spike/`, move the C++-bot crash canary into `tests/` — `implementer`
  - [x] 10. Tournament run and tuning: a few hundred 2p games MCTS vs random and vs heuristic; tune sims; record results in a doc — `sim-runner`
  - [x] 11. Exit gate: full + slow suites, `rules-auditor` + `code-reviewer`, fixes, phase report, hand over for playtest #4 — `/close-phase`
- *Exit:* MCTS clearly beats random and heuristic over a few hundred 2-player games; you play against each.

**Phase 7 — Better bots, then trained policies, optional ✋ playtest #5** *(interview done 2026-11-11, D35; branch `phase-7/bot-value-fit`)*
- Bot policy only; `docs/RULES_SPEC.md` stays locked. Task list (approved 2026-11-11):
  - [x] 1a. Freeze `heuristic-v1` (`data/bots/heuristic_v1.yaml`, loadable seat); move every hard-coded `value.py` weight to YAML — `implementer`
  - [x] 5a. (runs right after 1a; gates 5b–5c; if it fails, stop and tell the user before 1b) Test that each seat's wood-work turns contain no chance nodes and no other seat's decisions; `rules-auditor` checks the claim against the spec — `spec-test-writer`, `rules-auditor` — CLAIM HOLDS (240-game test + rules-auditor code audit 2026-11-11). Solver notes for 5b: turn end = DONE, W2 auto-end on last river piece, or change of (phase, w_turn), never a current_player() change alone (same seat can start back-to-back turns); a W7 DONE by the last seat in a seasonal round leads to the RS chance node, so treat it as a leaf; the test flags a mid-turn chance node only if the same seat acts next (tighten if cheap)
  - [x] 1b. `tools/tournament.py`: per-seat final-dollar breakdown by component (wood sales, tasks, joinery, Office, craftwork, winter penalties, loan repayment; same definitions as `value.py`), sim-count caps — `implementer`, `sim-runner`
  - [x] 1c. Cheap baselines only (reordered 2026-11-11, D36): `heuristic-v1` vs random and self-play in `docs/bot-tournament.md`; the `mcts-fast` baseline is skipped (Phase 6 already has 76.5%). `code-reviewer` spot audit of unit 1 (1a+1b) runs in parallel — `sim-runner`, `code-reviewer`
  - [x] 1c'. Diagnostic: ledger splits winter into feed/heat shortfall dollars, forced loans and forced sales, and splits spending by what it bought; task funnel per seat (taken, wood pieces placed on tasks, completed); joinery funnel (joiners hired, pieces placed, pieces sold); run the ledger over the human playtest replays in `playtest/` as a target breakdown — `implementer`, `sim-runner`
  - [x] 1d. (all three steps done, held-out exit passed 2026-11-12: seeds 101-103, 0.948 CI [0.917, 0.968]; seeds 104-199 stay reserved) `heuristic-v2` (bot policy only; a rules question stops the work and goes to the user): winter provisioning (stock food and firewood ahead of each winter when cheaper than the $3 charge, 1 food per joiner; check whether the D32 firewood/food rule exists), task pipeline (take only plausible tasks, route wood to the exact drying stage each needs, place it), joiners (hire only with a plan to place joinery wood). Exit: v2 beats `heuristic-v1` on held-out seeds (Wilson lower bound > 0.5), tasks completed > 0, winter shortfall down; report both funnels. `heuristic-v1` stays the historical baseline; units 2–6 compare against v2 — `implementer`, `sim-runner`
  - [x] 1e. Transport and sawing policy for `heuristic-v2` (added 2026-11-12, D37): the task pipeline showed the bot cuts ~10 pieces a game but moves ~4 to the sawmill and saws ~3, leaving ~12 pieces unmoved; improve transport (wagon/raft/sledge/bearers), sawing (saws, sawyers, mill worker) and the order of wood-work actions so more wood reaches sale, drying and tasks; measure on seeds 21-22 vs `heuristic-v1` and vs the committed v2; bot policy only — `implementer`, `sim-runner`
  - [x] 1f. (closed 2026-11-12 with a negative result, v3 not adopted: held-out seeds 101-103, v3 0.502 CI [0.445, 0.558] vs v2, tasks completed 0.08 vs 0.14 per game, 0.55 taken, 0.47 left incomplete; see docs/bot-tournament.md; `heuristic-v3` stays registered for the record; backlog: its feasibility gate evidently does not gate, revisit after 1g) Task-first policy, new profile `heuristic-v3` (copy of `heuristic-v2`, which stays frozen as the comparison; D38): place every eligible piece on a held task in the first task phase it qualifies (check drying/C10 eligibility window against the spec); never sell a piece a committed task needs; drying capacity (1 unmilled or 2 milled per area) in take/commit; held-task wood needs in the hidden-pick area weights; take only if a schedule fits the remaining task phases (count the year-2 winter task phase, no drying in winter); replace TASK_PARTIAL_WEIGHT with a small feasibility scheduler (finishable task valued near full reward, unfinishable 0) used for take, commit and value. Human reference: 2-3 tasks completed is normal. Exit: v3 beats v2 on held-out seeds with Wilson lower bound > 0.5; report completions per game, round each task completed, full ledger breakdown (completions are reported, not the target). A rules doubt about drying or task eligibility stops the work and goes to the user — `implementer`, `sim-runner`
  - [x] 1g. (closed 2026-11-12 with a negative result: held-out seeds 104-106, v4 0.503 CI [0.447, 0.560] vs v2, tasks completed 0.14 vs 0.10 per game; no sawing, targeting, bonus or early-task variant separated from v2; see docs/bot-tournament.md. `heuristic-v4` is the control heuristic: v2 plus `mill_saws`, `task_rank: premium`, conditional winter bonus, all within noise of v2. Sweep (d) skipped: every variant sits inside the +-7 point noise of 200 games, so there is no gradient.) Throughput, profile `heuristic-v4` (copy of `heuristic-v2`; D39), in this order: (a) wood-flow funnel in the ledger, per game and per round, hardwood separate: cut, transported (bearer / wagon / raft), arrived in the sawing area, sawn, then sold / dried / placed on tasks / placed in joinery / used for heating, plus pieces available at each drying stage; run for v2 and over the human replays in `playtest/`, report the stage where the human count pulls ahead. (b) direct sawing A/B vs v2 on seeds 21-22 before any sweep: `max_sawyers` 2 (R-025), `saw_target` 2, 3, 4 (max 4 saws owned; restock at the Market or from path saw tokens), mill worker saws when not needed elsewhere; report sawn discs per round (hardwood separate), discs reaching the sawing area, saws bought, ledger breakdown, win rate; if discs do not reach the sawing area, say so (transport is then the bottleneck). (c) hardwood and task targeting: bias the cutting-area pick to hardwood when holding or planning tasks; rank task cards by premium per piece over base sale price, computed from the component data, never hard-coded. (d) CMA-ES sweep (unit 4's tuner pulled forward) from the best (b) setting vs v2 on seeds 21-22; bounds: `max_sawyers` {1, 2}, `saw_target` {1..4}, `woodcutter_cap`, `bearer_cap`, and the sawyer, saw, market, wagon and fodder location weights. (e) new heuristic code only for a bottleneck the funnel shows that (a)-(d) do not fix. Exit: v4 beats v2 on held-out seeds (104-106; 101-103 were spent on the v2 and v3 exit checks) with Wilson lower bound > 0.5; report the funnel, ledger breakdown, task completions per game and their rounds, ms/move. Bot policy only, spec untouched; a rules doubt stops the work and goes to the user. `code-reviewer` spot-audits the ledger and heuristic changes — `implementer`, `sim-runner`, `code-reviewer`
  - [x] 2. (landed 2026-11-12; schema v1 in docs/BOT_DATA.md, output data/bot_games/ ignored) `tools/collect_games.py` (data from `heuristic-v4`, v2 and some `mcts-fast` games, D36/D39/D40; user chose v4 on 2026-11-12 although 1g's exit was not met, since v4 is statistically equal to v2 and shows more task payoffs): parallel seeded bot games, per-decision feature rows plus realised per-component dollars, untracked output dir, format in `docs/BOT_DATA.md`; mix in `mcts-fast` games as far as budget allows, mix recorded in the fit YAML — `implementer`, `sim-runner`
  - [x] 3a. (landed 2026-11-12; 400 games seeds 200-599, ridge per component, held-out total RMSE 11.6 vs hand-set 34.4; data/bots/value_fit.yaml) `tools/fit_value.py` (regression per component, `data/bots/value_fit.yaml` with data seed, game count and mix; held-out error vs hand-set value); `bots` dependency group — `implementer`, `sim-runner`
  - [x] 3b. Fitted value in the runtime (no numpy); `code-reviewer` spot audit of unit 3 — `implementer`, `code-reviewer`. Closed, negative: `heuristic-v5` (fitted wood_sales, joinery, craftwork, winter, rest) loses to v4 head-to-head (0.398 vs 0.603, 200 games); registered, not adopted. See docs/bot-tournament.md.
  - [x] 4. (SKIPPED 2026-11-12, user decision: no gradient expected, long-term planning for tasks and planned work is the lever; v4 stays the control) `tools/tune_weights.py`: CMA-ES on supply-path weights and plan/building preferences vs `heuristic-v1`, fixed seed sets with seat rotation, separate held-out set — `implementer`, `sim-runner`
  - [x] 5b. (landed 2026-11-12: `heuristic-v6` beats v4 0.570 CI [0.501, 0.637] on seeds 113-115, marginal; first version tied 0.505; see docs/bot-tournament.md; v4 stays the control until confirmed) Own-turn solver `lignum/bots/solver.py` (exhaustive when small, beam otherwise, scored by the fitted value), used in the heuristic — `implementer`
  - [x] 5p. (added 2026-11-12, user decision; landed, result: v7 task planner ties v6 0.470 [0.402, 0.539], loses to v4 0.378; tasks +$6-7 but wood -$6 and winter -$3; see docs/bot-tournament.md) Smallest long-term task planner `lignum/bots/plan.py`, `heuristic-v7`
  - [x] 5c. (landed 2026-11-12: mcts-solver:20 beats mcts-fast:20 0.902 [0.853, 0.936]; weak baseline, strength vs mcts-fast:60 and vs heuristic-v6 still to measure in unit 6) Solver in MCTS tree policy and rollouts; `code-reviewer` spot audit of unit 5 — `implementer`, `code-reviewer`
  - [x] 6. (DEFERRED 2026-11-12, user decision at phase close, D42: the `mcts-solver` server seat, 3p/4p legality smoke test, sim-count choice and the mcts-solver vs mcts-fast:60 and vs heuristic-v6 comparisons; heuristic-v1..v7 are already registered seats) Server seats for the new bots; legality smoke test (a few 3p and 4p games per new seat, no illegal moves or stalls); measure `mcts-fast` ms/move once, pick the MCTS+solver sim count with equal or lower ms/move, compare both on sim-count caps, record timings and the dollar-gain breakdown in `docs/bot-tournament.md` — `implementer`, `sim-runner`
  - [x] 7. Close: `/close-phase`, then stop for playtest #5 — `/close-phase`
- *Exit (2p, joinery, win_loss, sim-count caps, held-out seeds, 95% Wilson CI):* tuned heuristic with fitted value beats `heuristic-v1` (lower bound > 0.5); MCTS+solver beats `mcts-fast` at equal or lower ms/move (lower bound > 0.5); breakdown shows where the gain comes from; server seats exist.
- Trained agents (algorithm, budget, C++ port) stay in this phase after the units above; interview them then.
**Phase 8 — Tactical variant** *(mini-interview first: the variant's exact rules and rules source, pick order display, placement-card preview UI. Swapped with trained policies on 2026-11-10: it waits until the policies are better. The rules are not yet in the spec or PLAN.)*

## 8. Working agreement for agent sessions

### Who does what (D15)

| Role | Agent | Model | Used for |
|---|---|---|---|
| Orchestrator | main session | Sonnet (project default) | Runs the skills, delegates, talks to you; doesn't write large changes |
| Workhorse | `implementer` | Sonnet | One task-list unit: engine, server, web, tools, review fixes |
| Workhorse | `spec-test-writer` | Sonnet | Tests from the spec before code; regression tests for reports |
| Cheap | `Explore` (overrides built-in) | Haiku | Codebase search |
| Cheap | `sim-runner` | Haiku | Full suite, slow sims, tools; returns a short summary |
| QA | `rules-auditor` | Opus, high effort, project memory | Spec vs rulebooks/FAQ; data vs card images; code and tests vs spec |
| QA | `code-reviewer` | Opus, high effort | Correctness review of the phase diff |

Opus runs at phase close, and as spot audits in `/next-task` only for units that touch money, scoring, winter, loans, drying or planned-work timing.

### The loop

1. **`/start-phase N`** — branch `phase-N/<slug>`; units of one rule group or component (≲ 300 changed lines); you approve the list.
2. **`/next-task`** — `spec-test-writer` writes pending tests → `implementer` makes them pass → `sim-runner` runs the suite → spot audit if applicable → commit, tick the box.
3. **`/close-phase`** — full run including slow sims; `rules-auditor` and `code-reviewer` in parallel; one fix round (only blocker/must-fix findings block; the rest go to §9 Backlog); `docs/phase-reports/phase-N.md`; PR to `master`. ✋ phases stop for you; you merge.
4. **`/triage-report <file>`** — reproduce, classify (engine bug / spec gap / UI bug / not a bug), regression test, fix or ask you.

### Rules for every session

- No rule behaviour without a spec entry. An ambiguity means stop, add it to §9, ask — never guess.
- Card values live only in `data/components/`; code never hard-codes them.
- Tests cite rule IDs; nobody edits a test to make it pass; golden files are regenerated only with a reason in the commit.
- Commit at each green step on the phase branch; `master` changes only by PR.
- Keep this file current: tick boxes, append dated decisions to §3.

### What's enforced mechanically

| Guard | Mechanism |
|---|---|
| Don't finish with failing lint/tests | `check.py` on Stop and on SubagentStop for `implementer` and `spec-test-writer` |
| Don't change an approved spec | `protect_spec.py` on PreToolUse |
| Tests stay independent of the code | `block_engine_reads.py` in `spec-test-writer`'s frontmatter |
| Consistent formatting | `format_py.py` (`ruff format`) after each Python edit |
| No pushes to `master`, no force pushes | `permissions.deny` in `.claude/settings.json` |
| Third-party material stays in one place | Advisory CI check (warns) for images, PDFs or fonts tracked outside `third_party/` and `assets/generic/` (D21) |

## 9. Open questions (deferred)

- Phase 1 task 5, resolved with user answers 2026-11-04: hut wood put in area 3 after selling is overtaken by area 2's wood over capacity and all area 3 wood is sold in the next selling phase (R-059, R-101); the winter shortfall sale may sell more than is due (overrides O-U3-3's "only what is due", R-073); PW Cutting's "up to 2 moved workers" may be any combination of woodcutters, the mill worker and hut workers (R-099); `returns=margin` declares GENERAL_SUM (R-086, D7, §5.2). User answers recorded here may override a rulebook where the spec cites them.
- Phase 1 task 5, resolved 2026-11-04: O-U5-1 the sale-and-drying-first order also binds the optional extra winter-shortfall sales (R-073).
- Phase 1 unit 4, resolved with user answers 2026-11-04: O-U4-1 easier winter half = lower food+heating sum (R-117); O-U4-2 two plans on one season allowed (R-087); O-U4-3 Food Supply works in its target round like every other PW (R-093; supersedes the earlier whole-year reading); O-U4-4 Hut Construction PW takes any 2 of stake/board/shingle/joker, repeatable, no reeds (R-095); O-U4-5 doubled Drying stack forced on over capacity, Drying Area Upgrade + PW Drying = 4 in area 1 (R-096, R-111); O-U4-6 drying hut may move sale-area wood (R-101); O-U4-7 hut worker spent on use in its C5 window (R-103); O-U4-8 (part) Waterchannel one piece per transport phase (R-107); O-U4-9 Small Storage Area one milled piece from the sale/drying areas at task times, moved to a task in the final task assignment (winter year 2) at any dryness (R-114); O-U4-3 PW Log Driving and Waterchannel pieces count for Food Supply; O-U4-8 PW Log Driving counts as raft transport for Waterchannel; O-U4-10 a seat cannot plan the same card for the same season twice (overrides the earlier stacking answer); O-U4-11 at most one reed may stand for a shingle in PW Hut Construction with the Small Workshop; O-U4-12 stored piece fills milled requirements only.
- Phase 1 unit 9, resolved with user answers 2026-11-04: A1 hut/PW window closes at the turn's first non-window, non-loan action (R-100); A3 PW Overtime holders decide in starting-player (current turn) order after the automatic start-of-round steps (joiner income, fills/chance) and before the hidden picks (R-097); A6 the final sale is automatic, a choice only when both firewood and softwood are on the river (R-081); A8 winter heating is paid automatically in a fixed order, cheapest milled kind first (firewood, softwood, hardwood), no seat decision, so `PAY_HEAT` is removed and decision IDs renumbered to 440 (R-072; `docs/ACTIONS.md`). A2, A4, A5, A7, A9–A12 stay open (structure-only).
- Phase 1 close, resolved with user answers 2026-11-04: Small Storage Area may be filled in round 8's Tasks phase and its piece moved to a task in that same phase (R-114; STORE_PIECE legal in N4 of round 8; one piece per game: once moved to a task the building cannot be refilled, STORE_PIECE legal only while empty and never used); PW Cutting's up to 2 moved workers all go into one other cutting area (R-099); in winter every cutting area is free for the food hut (R-102); `TAKE_LOAN` is legal at the final sale while loans < 2 (ACTIONS §1.7, SCENARIOS 9.4). Spec wording fixes: R-096 example, R-097 order (new step 3a of R-034), R-053/R-098 river wood sold automatically at the final sale, R-012 step order (SP follows the path fill).
- Phase 2 unit 10, user decisions 2026-11-05: every winter phase NB and N1..N4 gives every seat an explicit node ending in `DONE` (no auto-skip of empty phases); round-8 joinery placement sources follow R-057 (drying area 2 only) and round-8 task placement follows R-055 (R-064, R-069; `docs/ACTIONS.md` A2); a seat in SF with both loans taken and nothing sellable still gets a DONE-only node (explicit, not auto-skipped).
- Phase 2 unit 11, user decisions 2026-11-05: `FS` comes after R-081 steps 1 and 3 (sale/drying areas and covered joinery sold first; final dollars unchanged, `docs/SCENARIOS.md` §3, §9.4, Q1); river choices at FS are made in the year-2 fall clearing order (R-081; `docs/ACTIONS.md` 5.11).
- Phase 1 unit 6, confirmed by user 2026-11-04: task-card wood colours (light = firewood, red-brown = softwood, black = hardwood), 1 food to each of the two food areas on a placement card, and drying labels attach to the adjacent piece on task cards with same-kind pieces (`cards.yaml`).
- Phase 2 unit 6, resolved with user decisions 2026-11-05: food on placement cards is 1 per card, stacking across cards (R-037); chance node order at round start is TASK, CRAFT_DRAW, SPOT_TOKEN, PLACEMENT (R-034, R-062); joiner income is paid from the round after the hire (R-079); multi-unit supply-path visits (Bearer, Woodcutter, Sawyer) end only on explicit DONE, single-acquisition locations auto-end; planned work, Buildings and Market locations are never legal destinations in Phase 2; the Market (including saw and food buying) stays out until Phase 4.
- Phase 2 unit 7, resolved with user decisions 2026-11-05: DONE is not legal while a W3 transport trip is open (END_TRIP is the only early exit; transporting nothing or only part of the woodpile is allowed, DONE legal with zero pieces moved); ASSIGN_WORKER is always exposed (the engine never auto-selects); MOVE_CUT_TOKEN is legal only for a seat with an earlier seat in clearing order on the same area, and stays legal after ASSIGN_WORKER until wood is taken or the token moved (R-048, R-050..R-053; `docs/ACTIONS.md` 5.8); `USE_WAGON` and `RIVER_MOVE` are offered only with a non-empty woodpile, so a spent wagon or open trip always has a piece to move.
- Phase 2 unit 8, resolved with user decisions 2026-11-05: `PLACE_JOINERY` is legal in Phase 2 with `joinery=true` (R-057, R-082; ACTIONS wording fixed); A4 `ASSIGN_WORKER` stays always exposed, the seat picks, index 0 (sawyer) before the mill worker; A7 the forced drying advance applies at the first `DRY_ENTER` or at `DONE` (structure-only, implemented as assumed).
- Phase 7: bot units interviewed 2026-11-11 (D35); trained agents (algorithm, budget, C++ port) still to interview after unit 7.
- Phase 8: tactical variant rules and UI.

### Backlog
- Optional, later (user decision 2026-11-07): theme switch UI and a full e2e game on the generic theme alone. Generic assets stay in the repo and fill any gap in the official theme.
- Optional, later (user decision 2026-11-07): setup editor to mirror a physical table. Needs a `kind: "setup"` scenario loader (`load_setup_scenario` with S-* validation, built from the ACTIONS §2 chance sequence + PICK_AREA decisions; adapter `scenario_players`/`initial_state`; none exists today), a validate endpoint rejecting `kind: "state"`, and the editor UI. See docs/SCENARIOS.md §6.3–6.4.
Should-fix and minor findings, tagged with the phase that found them. `/close-phase` appends here.

- Phase 0: the player aid PDF isn't in `third_party/rules/` yet (only `player_aid.txt`); add it if Phase 1 needs its tables or icons.
- Phase 0: ludex.dev has no Buildings cards, Joinery board side or player-board extension; Phase 1 data for those comes from the expansion rulebook p.4, the player aid and the photos (as §5.6 and Appendix A already say).
- Phase 0: `protect_spec.py` now blocks `git merge/pull/rebase/cherry-pick/revert/am/apply` whenever the spec is APPROVED, even when the spec isn't touched; the user runs those (or flips to AMENDING). A Python script that writes the spec without naming it on the command line is caught only by the Stop-time backstop in `check.py`.
- Phase 0: `tests/test_hooks.py` is marked slow (as in kingisdead), so the Stop hook's fast run skips it; CI and `/close-phase` run it.
- Phase 0: delete `spike/` (and `tests/spike/`) once `lignum/` has its own observer, resampler and IS-MCTS seat (Phase 6 at the latest); keep the C++-bot crash canary by moving it to `tests/`.
- Phase 0: `tests/test_openspiel_api.py` and `tests/support/toy_chance_game.py` are ported from kingisdead to back the inherited half of `docs/OPENSPIEL_NOTES.md`.
- Phase 5 (UI): `third_party/art/boards/board.webp` is the base side (no Buildings or Joiner location); the joinery-side photo prints 2 foremen spots at Buildings, matching the rules. Handle the joinery side in the sprite board.
- Phase 1 close (backlog): `docs/ACTIONS.md` has no N5/N6 hut windows (outcome-equivalent, because feeding and heating are automatic; state this in §4).
- Phase 1 close (backlog): `data/setup.yaml` `supply.fodder` and `supply.mill_workers` sit in the pools block beside the unlimited marker; add a comment.
- Phase 1 close (backlog): `docs/SCENARIOS.md` hard-coded the joiner supply of 6 in places; point to `supply.joiners` (partly done in the close fixes).
- Phase 1 close (backlog): the `tests/data/test_data_crossrefs` docstring overstates its coverage.
- Phase 1 close (backlog): `setup.yaml` keys `sawmill_pads`, `player_board_extensions` and `joiners_on_path` are not checked by any test.
- Phase 2 close (backlog): `State.clone` costs ~144 µs (deepcopy over immutable tuples); add a shallow `__deepcopy__` and cache `_tables()` (`get_game()` called ~1,400 times per game) before Phase 6 MCTS.
- Phase 2 close (backlog): every `_apply_*` recomputes `_legal_actions` to validate; add a fast mode for bots.
- Phase 2 close (backlog): `_use_worker` (`game.py`) counts hired workers correctly only in W1/W3/W4; Phase 4 hut workers in winter (N3) need it fixed.
- Phase 2 close (backlog): `dump_scenario` exports other seats' hidden PK picks (full-information by design); the Phase 3 server must never send it, or PK `history()`/`action_to_string`, to another seat before the reveal.
- Phase 2 close (backlog): random sims never reach solvent winters, the final sale of sale/drying wood or task payouts (every seat ends at -16); add a biased-policy sim before trusting `sim_stats` dollar spread (Phase 6 bots).
- Phase 2 close (backlog): `tests/rules/test_round_start.py::test_R063_buildings_location_is_not_refilled` stays pending until Buildings land in Phase 4.
- Phase 3 unit 4 (rules-auditor, minor): the R-084 tie set is computed in three places (`LignumState.returns`, `server/adapters/lignum.py`, `tools/sim_stats.py`); add `LignumState.winners()` in the engine and reuse it. Unit 4 also noted: Back undoes a whole run of consecutive actions by one human seat; Rewind counts bot actions as player actions.
- Phase 3 close (should-fix): `web/src/shell/useGame.ts:68` `refresh()` returns early while busy without bumping `pollTick`; a repeated identical error can stop polling for good.
- Phase 3 close (should-fix): `server/app.py` action/back/retry/rewind validate `?seat=` inside `render()`, after the mutation is applied; an out-of-range seat returns 422 but the action stuck. Check the seat before mutating.
- Phase 3 close (should-fix): the lignum view omits public R-028 items: fodder slots, task-card requirements and rewards (labels say only "Take task 07"), PW cards laid out, building supply. Add before Phase 4 makes them playable.
- Phase 3 close (should-fix): `winter.sf_due` is shown as "Sawmill food due"; confirm its meaning (R-073 shortfall?) and rename to the spec's term. (The supply-path labels were fixed by triage of report 20261106T212822-ecfda0.)
- Phase 3 close (should-fix): in inline bot mode (tests/tools) a bot `IllegalAction` makes `post_action` return 409 as if the human's action failed; record it in `bot_error` as the async path does.
- Phase 3 close (minor): e2e hotseat test never reaches a round-2 hidden pick; drive to round-2 PK and check P1's log and board after the reveal. Retry/`autoFocus` on the Curtain button is lost when it mounts disabled (focus in an effect on enable). `useGame` doesn't sequence out-of-order GET responses (stale `current_player` can flash a wrong "Pass to P{n}").
- Phase 3 close (minor): `picks_round` in the adapter uses `phase > PHASE_PK` though TR < PK, so revealed picks are labelled with the wrong round in some phases; `BUILD_HUT` label hard-codes the hut token count (`3 - p[0]`, use `hut_effect_slots`); `test_view_winter_requirements_match_observer` restates the adapter lookup instead of comparing with `_winter_requirement()`; the Lobby "Seed (optional)" field should say a fixed seed makes bots and draws predictable.
- Phase 3 close (minor, rules-auditor): Back over-refuses at the reveal barrier: a human who is both the last PK picker and first in the TR turn order has pick + TR moves in one run, so Back is refused (409) instead of stopping just after the reveal and undoing only the TR moves (`server/sessions.py:296-314`). No leak; no test covers it.
- Phase 3 triage (report 20261106T230931-ad7881, minor): `docs/ACTIONS.md` §5.2 says ASSIGN_WORKER(0) is a hired bearer in N2 and a hired sawyer in N3, but `n2_actions` offers only the mill worker, and `_use_worker` counts a hired worker in N3 under `bear_used` (only W1/W4 are special-cased); reconcile the doc and engine (and fix the N3 counter) in Phase 4 when winter hut workers land.
- Phase 3 close (minor): `npm ci` reports 6 vulnerabilities (1 high, 2 critical); triage with `npm audit`. `useGame.test.tsx` prints React `act(...)` warnings.
- Phase 4 unit 5, resolved with user decision 2026-11-06: `HUT_FOOD(a)` is legal only for a free cutting area that currently holds food (R-102 is silent on empty areas; an empty-area action would be a no-op that wastes a token). Structure-only.
- Phase 4 unit 6, resolved with user ruling 2026-11-06: the order of `HUT_TOKEN` picks is free (only the final set must be valid); `HUT_AREA` stays non-decreasing; `docs/ACTIONS.md` §5.7 and A9 amended. Structure-only.
- Phase 4 unit 7, resolved with user ruling 2026-11-06 (a): PW Overtime planned for round 4 (the card is printed for winter) behaves like round 8: the holder gets the `TAKE_OVERTIME` / `DONE` node at the winter-round start (WS), in starting-player order, before the winter wood-work phases; the winter bonus (R-065) comes after, only if the round has one. `TAKE_OVERTIME` does not close the node by itself; `DONE` follows (as in A2).
- Phase 4 unit 7, resolved with user ruling 2026-11-06 (b): PW Cutting affected seat. A seat whose cutting area lost wood to another seat's PW Cutting outside take this round may pay $1 and move its cutting token to a token-free area (as R-048 item 2) even if no other seat's token shares its area. Legal only when wood was actually taken out of its area by an outside take (area-lost-wood flag per round), or under the existing R-048 sharing condition. `docs/ACTIONS.md` amended.
- Phase 4 unit 7 (RESOLVED 2026-11-07: spec amended with user approval at Phase 4 close): R-064/R-097 described Overtime/WS for round 8 only; ruling (a) extends to round 4 — propose spec amendment at phase close (spec is locked once APPROVED).
- Phase 5 close (should-fix, rules-auditor): winter cards are drawn whole with both halves visible; the half in effect (R-027/R-070) shows only in the tooltip. Crop/mark the active half on the Board and Cards tabs and in the viewer.
- Phase 5 close (minor, rules-auditor): fodder slot values 2 and 3 hard-coded in `board/Sawmill.tsx:213`; the view already sends `fodder_values`. The generated PW card prints "$1 per token" literally (`tools/make_generic_theme.py:533`; use `location_prices.planned_work_per_token`); TextBoard "Sawyers ($0)/($1)" hard-codes `sawyer_prices`.
- Phase 5 close (minor, rules-auditor): `board/Trackers.tsx:25` always puts the SF marker on N6; a feeding shortfall is in N5 (use `winter.pay`). Building effect text built from yaml params only (Storeroom, Small Storage Area, Drying Area Upgrade) is terse vs PLAN 9f "full text". ScoringPanel column "Money held" is money before the final sale; rename. `test_lignum_board_view.py` hidden-pick test checks only a few fields (an audit probe found 0 leaks; extend to the new fields).
- Phase 5 close (minor, code-reviewer): `Board.tsx:86` keeps last round's revealed picks through RS/PK so a pawn can show on two areas; hide or label them. `_score` replays history on every terminal view (~0.12 s on a 536-action 4p game); cache per session and history length. Board/Sawmill `open` popover key is not reset when `history_length` changes. `Board.tsx:55` falls back to the base board image if `board-joinery` is missing from both themes.
- Phase 5 close (bookkeeping): `winter.sf_due` key was not renamed (label "Shortfall money due" already correct; the spec has no other term); unit 7's rename claim and the Phase 3 backlog line stand as label-only. `npm ci` reports 6 vulnerabilities; triage with `npm audit`.
- Phase 4 unit 8, resolved with user ruling 2026-11-06: the first winter woodcutting action gives 2 firewood whoever performs it, each later one 1, by order not by worker type (R-066). Structure-only. Counted per seat.
- Backlog (unit 7): scenario dump accepts RS/WS after TAKE_OVERTIME before DONE (lossy; a reload would duplicate the disk) — treat as mid-turn once a scenario loader exists.
- Phase 4 close, resolved with user decision 2026-11-07: with the Marketstand (R-108) `BUY_FOOD` and `SELL_FOOD` are mutually exclusive within one Market visit (per-visit flag `visit_food`), because both cost/pay $1 and could cycle forever; `docs/ACTIONS.md` §6 amended. Spec text unchanged (locked).
- Phase 4 unit 6: the R-096 spec-example test was fixed and unmarked at Phase 4 close.
- Phase 4 close (should-fix/minor): `make_playthroughs` cannot reproduce `p2_joinery_win_loss_std` and `p4_joinery_margin_std` histories (digests were rehashed, not regenerated); `disks_per_saw` and Small Storage `capacity` are guarded rather than generalised; scenario dump accepts a closed PW Sawing pair as a turn start (latent, no loader); invariant drying check is skipped game-wide once any hut is built; own-area hut food same-turn case untested; stale line above (R-063 pending) is resolved.

- Phase 6 (should-fix, rules-auditor): `lignum/bots/mcts.py` keys tree nodes by action path, so in-tree seats picking after the root see hidden picks (breaks R-038/D5 inside the search; real hidden info does not leak, probe 0 diffs). Re-key by `(current_player, information_state_string)` or mask unrevealed picks; amend D22 (we use a custom search, not OpenSpiel's `ISMCTSBot`). May change MCTS strength; re-run the tournament. The determinized fallback has the same in-tree knowledge by design.
- Phase 6 (should-fix, rules-auditor): no test that the heuristic only takes loans that are the only legal action, a winter shortfall, or unlock a new action (D29); behaviour conforms today (69-game probe, 0 voluntary loans).
- Phase 6 (should-fix, code-reviewer): time caps make tournament results depend on CPU load, and `tools/tournament.py` docstring says runs are deterministic. With 4 players `mcts` (1000 sims, 10 s cap) gets ~60 sims/move (~150-180 ms/sim). Add a tournament option to drop caps or report sims/move, correct the docstring, retune the server `mcts` settings (full-strength `mcts` 11/20 vs heuristic, no better than `mcts-fast`).
- Phase 6 (minor): route planner treats Planned Work as $0 and ignores affordability (4/72 seats forced into a loan; `plan_cost` unused) and sawyer cost is a literal $0 (`heuristic.py:184-200`); Storeroom carry-over food under-valued for winter 2 (`value.py:205`); value-function weights are hard-coded in `value.py` though a docstring says they moved to `data/bots/heuristic.yaml` (D32); leftover craftwork/buildings keep value after round 7 (R-081, `value.py:227`).
- Phase 6 (minor): `test_random_vs_random_deterministic_and_rotated` never asserts seat rotation (use two distinct stub bots); IS-MCTS pools stats across hidden-pick worlds (see above); `_GAMES`/`_TABLES` registries are "last constructed wins" (`game.py` ~219-245).
- Phase 6 (observation): heuristic-vs-heuristic and random sims end near -$13 to -$16 (loans, unpaid winter), so they do not exercise final scoring; `web/src/shell/useGame.test.tsx` "drops a stale poll response" failed once under heavy CPU load (fixed `sleep(5)`), passed on rerun.
- Phase 6: `.claude/hooks/check.py` `WATCHED_DIRS` still lists `spike/`, and `docs/OPENSPIEL_NOTES.md` history section names `spike/` paths; clean up with the matching `tests/test_hooks.py` change.
- Backlog (Phase 7 close, rules-auditor should-fix, bot play only): (1) R-114/R-069 the planners never count the Small Storage piece in round 8 N4, so v4/v6/v7 give up a card it would complete; (2) R-054/R-050 `tasks.py` `_clock` and `plan.py` `_arrivals` ignore whether the seat already had its turn in the phase (solver scores W1-W4 end states optimistically; W7 `w_dirty` skews opponent leaf values in MCTS); (3) C6/R-064/R-104 winter planning counts woodpile to milled by N4 and counts an affordable saw as owned (overstates finishability); minor: `dry_cap_disks` hard-coded 1 in `plan.py:189`, wagon trip sizes 3/2 hard-coded in `heuristic.py:648`, W2 river timing pessimistic, winter heat credit ignores the one mill-worker sawing and saw ownership.
- Backlog (Phase 7 close, code-reviewer should-fix): `_plan` planner cache race across threads (`heuristic.py:226`, build local then assign once or key a dict by `_tkey`); `ISMCTSBot(profile="heuristic-v7")` drops the plan section from value weights (`mcts.py:186`, use `h.vw`); `fit_value` does not check games share `value_profile` and `every` (`fit_value.py:97`); `breakdown_history.py` exit-code/docstring mismatch and uncaught AssertionError; `tests/bots/test_plan.py` uses seeds 100-102 which overlap the held-out range.
- Backlog (Phase 7, plan): v7 task planner needs winter protection and wood trade-offs before it can beat v6; unit 6 (mcts-solver seat, 3p/4p smoke, sim count, vs `mcts-fast:60` and vs `heuristic-v6`) deferred; trained agents still to interview.

## 10. Risks

| Risk | Mitigation |
|---|---|
| A much larger ruleset than kingisdead invites misreads | Engine split A/B, spec review ✋, rule-ID tests, audits, playtest after Engine A |
| Card transcription errors | Data lives in YAML only; side-by-side image review; data tests |
| Long games (hundreds of decisions) make Python MCTS slow | Canonical orderings, auto-advance on forced actions, 2-player bots first; C++ only if Phase 7 needs it |
| Imperfect-information bots on Python games in 2.0.2 | Phase 0 spike before engine work |
| Third-party art reaching a public repo | One `third_party/` path, CI check, scrub command in D11, generic theme always runnable |
| Official answers in a fan-maintained FAQ change or disappear | Phase 1 copies the cited rulings into the spec with their source |

## Appendix A — Component data sources

| Item | Count | Source |
|---|---|---|
| Task cards | 19 | ludex.dev (wood, drying bonus, dollars) |
| Placement cards | 19 | ludex.dev (wood and food per area). The rulebook FAQ's "15" is treated as an error |
| Winter cards | 8 (4 per year, two halves each) | ludex.dev; easier half = lower food+heating sum, settled by R-117 |
| Planned work cards | 10 | rulebook p.18 text + ludex.dev seasons |
| Buildings | 10 | expansion rulebook p.4 + player aid; photo of all 10 tiles (`third_party/rules/photos/buildings.jpg`) |
| Supply path, both sides | 20 / 22 + clearing | rulebook p.2 image; your Joinery-side photo |
| Sawmill pad and extension | 4 + 4 | ludex.dev image; your extension photo |
