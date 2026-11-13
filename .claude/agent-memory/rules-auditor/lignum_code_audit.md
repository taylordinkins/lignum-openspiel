---
name: lignum-code-audit
description: Recurring defect classes and probe recipes for Lignum Phase 2+ engine/test audits (first seen unit 3 setup spot audit, 2026-11-05)
metadata:
  type: project
---

First seen in the Phase 2 unit 3 (setup) spot audit, 2026-11-05.

- **Decision phases skip legality in `_apply_action`.** Unit 3 validated chance outcomes in SC but
  SP accepted a 2-firewood area, a duplicate pick, even MOVE_TO(1) decoded as an area. Same class
  as kingisdead unit 7 (see [[audit-patterns]]). Each unit, probe every new phase with off-mask
  actions on a clone. tools/replay checks legality, but the server or bots may not.
- **Slash-ordered per-player lists read backwards.** ACTIONS and R-013 write "4/3/2", "3/2/1",
  "8/7/6" in 4p/3p/2p order. Unit 3 read ACTIONS 2 "AREAS3: k = 4/3/2 by players" as k = 6 − players
  (the 2-firewood subset) and the test accepted either. Outcomes are the same, but the ID meaning freezes at
  Phase 2 close. Check each slash list against the 4p-first convention, and check that tests pin the
  encoding.
- **0-based area indices in strings.** ACTIONS defines a = printed − 1; observer strings and
  action names show "areas3 0,4,5" / "PICK_AREA(4)" (= printed 5) while scenarios use 1..6. A display
  issue only (NOTE), but watch for it in logs, replay output and the UI.
- Probe recipe: scratch script run as `PYTHONPATH=/home/xdink/code/lignum uv run python <script>`
  (no PIL needed). `state.high_areas()`, `state.picks` and `state.draws` are handy internals for
  probes. Run each spec example end to end by forcing the chance ID (R-015 3p example = AREAS3(10)
  under the unit-3 encoding).

Unit 6 (supply path, 2026-11-05): engine matched the spec (0 problems over 6,000 travel steps of
an independent money ledger + visit-option oracle + off-mask probe). Recurring classes:
- **Prices/limits hard-coded although setup.yaml has them** (`location_prices`, `sawyer_prices`,
  `loans.amount_each/max_per_seat`, `max_saws_per_seat`): `-1`, `>= 1`, MAX_SAWS=4, LOAN_AMOUNT.
  Later buildings (Field fodder $0) need data-driven prices. constants.py claims "tests check vs
  yaml" but test_constants pins literals. Grep `_bump(..., -1)` and `>= 1` each money unit.
- **User decisions relayed only by the orchestrator** ("multi-unit visits end only on DONE",
  "Market/PW/Buildings illegal until Phase 4") were not in PLAN §9 or ACTIONS; ACTIONS 1.4
  (auto-end) and PLAN Phase-2 scope (Market buying in Phase 2) contradicted them. Ask for the
  record when a caller cites a decision you can't find.
- **Equivalent mutants from forward-only movement**: once-per-round flags (task_taken,
  fodder_bought, hired_s==0) are redundant because a foreman visits each location once; free
  sawyers = players, so "paid sawyer without a free one" is unreachable. Don't report as gaps.
- Mutation plugin recipe works here too (`PYTHONPATH=<scratch> uv run pytest -p mutplug`);
  rules.py functions are looked up by module global, so patching `lignum.rules.X` takes.

**Why:** encoding and validation choices made in Phase 2 freeze with the action IDs.
**How to apply:** on every Phase 2+ unit audit, probe illegal actions per phase and pin chance encodings.

Unit 8 (W4..W7 sawing/tasks/selling/drying, 2026-11-05): engine matched the spec (0 problems over
~145k steps with an independent price/advance/capacity/W5-mask oracle). Recurring classes:
- **Pending markers left on implemented rules** because the harness snapshot (`dump_scenario`) only
  works at decision nodes: a test whose DONE ends the round lands on a chance node (S-NOTDECISION)
  and xfails. Run `pytest --runxfail -k <rule>` and read *why* each pending test fails.
- **Vacuous passing tests for unbuilt features**: "slots without a joiner are equivalent" passes
  because no final sale exists yet. Flag negative/equivalence tests whose feature is still a stub.
- **Dual-purpose turn flags** (`w_dirty` = window closed AND forced drying advance applied): any
  later window action that sets it would silently skip a forced move. Note as forward risk.
- **Lossy observer tensors** (task_filled as bit_count) alias distinct states; strings were exact.
- Probe policy: uniform random play sells everything in W6, so drying 3 and joinery are never
  reached. Bias W6 to DONE (~85%) and other phases to non-DONE (~90%) to get coverage.

Unit 10 (winter NB/N1..N4, automatic N5/N6, SF shortfall, 2026-11-05): settlement money matched an
independent oracle over ~53k steps (both winters, 2-4p, joinery on/off). Recurring classes:
- **Gated step leaks past its gate.** R-073 step 3 (selling, incl. optional extra sales) applies
  only "if it still has less than due" after loans; sf_actions offered SELL whenever money >= due,
  so a seat covered by loans could sell firewood-storage/sawing wood. ACTIONS copied the leak. For
  every multi-step "if still short, then..." rule, probe the state where an earlier step already
  satisfied the condition.
- **Negative tests vacuous by fixture**: "loan stops once covered, no selling" used a seat with
  nothing sellable, and the reference model's DONE-first policy never explores the extra branch.
  Check each "X not offered" test's fixture actually has an X candidate.
- **Scenario dump at forbidden resting phases**: dump_scenario accepted SF (SCENARIOS forbids N5,
  N6, SF as resting phases) and dropped sf_due. Check new automatic/mid-turn phases against
  SCENARIOS' resting-phase list.
- Probe policy for winter: never pick TAKE_LOAN outside SF (else every seat has 2 loans by round
  4 and SF never offers loans), and DONE in N1 ~60% so the mill worker reaches N2/N3.

Unit 11 (final sale FS, final dollars, returns, 2026-11-05): one blocker, found only by the probe.
- **Automatic sweep after a choice node re-processes the chooser.** `_advance_final_sale` ran "sell
  the single river kind" for every seat after the FS choices, so a seat that chose softwood also
  had its firewood sold (both kinds paid). Every FS game was wrong; the suite passed because no test
  reaches FS. Whenever a decision node sits inside an automatic step, check that the automatic
  remainder skips what the decision already settled (or excludes the deciding seats).
- **Natural play can't reach the money paths** (year-2 winter bankrupts every seat: no sale/drying
  wood, no completed tasks, no 0/1-loan seats, no clip). Recipe that worked: monkeypatch the entry
  function (`LignumState._begin_final_sale`) to fuzz the pre-step fields (money, loans, zones,
  joinery, river, held_tasks, filled) and snapshot them, then compare `state.final`/returns to a
  yaml-only oracle. Script kept as a pattern, not a file: ~3000 games run in seconds.
- **State an ordering needs is cleared before the phase that uses it**: `_end_winter` clears `wint`
  (fall clearing order) before FS, so FS runs in seat order and dump_scenario at FS crashes (strict
  zip on the path, clearing_order None) while SCENARIOS requires clearing_order in FS. Also check
  each new phase against SCENARIOS' "state before X" definitions (FS = before the final sale; the
  engine sells step 1 and joinery before FS).
- Harness fallbacks `legal[0]` pick TAKE_LOAN (ID 1) first at any node where it is legal; flag
  default policies that would take loans at FS/other nodes if reached.

Phase 3 unit 2 (server adapter view, 2026-11-06): view() itself clean (pk-swap probe, 18.7k
comparisons, 0 leaks). Recurring classes for server units:
- **The leak is in the shell, not the adapter.** sessions.history_entries labels every action via
  action_meta (no viewer arg) and ships raw `id`s in GameView.history to every seat; /export ships
  raw history. PICK_AREA labels/ids leak hidden picks. Check every path that serialises
  history/ids/labels, not just view(); the adapter comment "never rendered" was false.
- **"Views differ" reveal tests pass with picks removed**: after reveal, food distribution makes
  views differ anyway. Mutant (drop `picks`) survived. Demand value assertions (`picks == [...]`).
- **Adapter/shell key contract drift**: app.render reads v["is_terminal"], v["legal_actions"]; the
  ported adapter emitted "terminal" and no legal_actions -> KeyError on every render. Smoke a real
  create_game through TestClient with the real adapter.
- Probe recipes: pk-swap on clone (`c.pk = tuple(...)`) comparing other seats' JSON views; view
  mutants via a pytest plugin wrapping `LignumAdapter.view` (`-p mutplug_view`, env MUT=...).

Phase 2 close full audit (2026-11-06): PASS, no blockers. Settled, don't re-investigate:
- **sim_stats "final dollars ~ -16, 2 loans each, 83-89% ties" is expected, not a bug.** Every
  random seat enters FS with $0 (1350/1350): the year-1 winter forces both loans even under a
  no-voluntary-loan policy, the year-2 dues (~$36 vs ~$1.4 held) end in D9 forgiveness, so final =
  -16 + river/covered joinery/tasks. No Market food in Phase 2 makes winters $3 per food. Ties follow
  from D8. Random sims therefore never test scoring; rely on fuzz-entry oracles.
- **D9 masks winter fixtures.** A winter test whose seat ends bankrupt passes whatever the due was:
  `test_R071_each_joiner_adds_one_food_due` (asserts `<=`), the surplus-food discard and the
  cheapest-first heating order were all untested (mutants survived tests/rules; heating order
  survived even the goldens). For every payment test, check the seat is solvent and that the
  fixture holds the distinguishing items (mixed log kinds, surplus food).
- **ACTIONS.md self-contradicts after user decisions**: auto-insert of ASSIGN_WORKER (§4 notes, §5.2)
  vs "always exposed" (A4, §5.8). At ID freeze, grep each user decision's subject across all sections.
- Sim reports print "invariant violations: 0" whether or not `--invariants` ran; ask which.
- Probe scripts that worked (0 mismatches): per-decision money ledger with rulebook-typed prices
  (skip N4/SF/round-boundary steps, add R-079 income at RS); winter settle oracle wrapping
  `_settle`/`_end_winter` that replays the recorded SF actions; hidden-pick leak by swapping
  `st.pk[0]` on a clone and comparing other seats' 4 views. Mutant set of 20 in ~2 min with xargs -P 5.

Phase 3 winners spot audit (2026-11-06): adapter winners/returns correct (36 random games + oracle,
0 mismatches). Recurring classes:
- **Winner/tie set re-derived in several places** (engine returns() inline top/k, adapter view,
  tools/sim_stats). All read `state.final`, so dollars aren't duplicated, but R-084 is. Suggest one
  engine `winners()`; check each new consumer (UI, reports) for a fourth copy.
- **Server full-game tests can't check winners**: random play ends all-tied at -16 (see above), so
  shape asserts (`winners` non-empty, in range) survive min-picking/everyone/[0] mutants. Demand a
  fuzzed or scripted terminal with a sole winner AND a partial tie, with distinct loan counts so
  money-vs-final ordering differs. Also flag `abs(sum(returns))<1e-9` asserted in margin mode.
- The view's `money` at terminal is pre-repayment; final dollars are not exposed. Watch the UI.

Phase 3 close (server + web, 2026-11-06): view/history masking clean (session-layer pk-swap over
960 comparisons, 0 leaks), but hidden picks leaked by side channels. Recurring classes:
- **Seeded deterministic bots + public seed = hidden-pick oracle.** bot_rng(seed, len(history))
  and the chance RNG are keyed on the session seed, which GameView ships to every seat (and the
  web top bar prints). A later seat computes a random bot's masked pick from seed + masked entry
  index; /import of the visible prefix with that seed makes the server compute it (20/20). Same
  seed also predicts future chance draws. Probe both on every server/bot change.
- **Undo that crosses a reveal.** Back after the reveal truncates to before the human's own pick;
  the deterministic bot re-picks identically, so the human re-picks knowing it (10/10). Check every
  undo/rewind path against "pick is final" and reveal barriers.
- **View completeness vs R-028.** Leak tests check only what must be hidden; the view omitted
  public items (visible winter halves, fodder slots, task card contents, PW cards, building
  supply). Diff the adapter view keys against the observer string_from parts and the R-028 list.
- **UI labels guessed from abbreviated keys** (path sf/sp shown as "Sawmill food/pay" for free/paid
  sawyers; sf_due as "Sawmill food due"). Trace each displayed key to the engine field comment.
- UI view-seat fallback to the server default seat (= current player) pins the UI to a bot's seat
  after a reload during a bot turn, showing the bot's private pick. Check fallbacks pick a human.

Phase 3 fix re-check (2026-11-06): seed hidden + secret salt (fixed; import re-salts, 20/120 = chance),
reveal barrier on Back (fixed, holds in chains and in imported sessions), winter cards in view (fixed).
Recurring classes found on re-check:
- **Barriers on undo must cover chance runs too, not only hidden picks.** Chance RNG keyed on
  (seed, salt, len(history)) re-deals identical round-start (RS) draws after Back + same-length
  redo (15/15), and a length-changing redo re-rolls them. Any undo past a chance node = peek or
  re-roll. Probe every undo path across RS, not just across PK.
- **Import accepts any legal history, so an edited export bypasses every Back barrier** (splice own
  new pick + bot's revealed pick: 10/10). Not fixable by Back logic; it's a trust question
  (signed exports?) for the user.
- Explicit seed => salt "" => the typer has a full bot/chance oracle (20/20); no API path sends it.
- **Barrier implemented as refuse, not clamp.** RS-chance barrier fix (2026-11-06) verified: 0
  mismatches vs an independent oracle over ~3k Back attempts (2-4p, joinery on/off), 15/15 RS
  re-deals now 409, import verdicts identical. But a human run that *straddles* a reveal (last PK
  picker who is also first in TR) is refused outright, so own post-reveal TR moves can't be undone.
  For every undo barrier, probe a run that starts before the barrier and continues after it.
- Probe hygiene: run scratchpad scripts with PYTHONPATH=<repo>; /report writes into
  <repo>/playtest/reports by default, so pass create_app(reports_dir=<scratchpad>) or delete after.

Phase 4 unit 3 (planned work core, 2026-11-06): engine matched the spec (0 problems over ~16k TR
steps, 2.3k plans, independent yaml-only oracle for entry/options/cost/records). Recurring classes:
- **"Any option" activation masks money gating in tests.** PW entry = any legal card affordable
  with loans; fixtures always had a free card laid out, so mutants ignore-money / no-loan-room /
  one-loan-room all survived the suite. For every "can enter if it can pay (loans counted)" test,
  demand a fixture where EVERY option costs more than money (needs loan) and one where even
  money + all loans fall short. Same shape as Market (food always $1).
- **Base price in setup.yaml still ignored**: `location_prices.planned_work_per_token` and
  `per_seat.planned_work_tokens` unused (cost = count, PW_PAIRS=3). Keep grepping each new price.
- game.py imports rules functions by name (`plan_cost`), so a mutant must patch both
  `lignum.rules.X` and `lignum.game.X`. Probe recipe: random play preferring PW (70%) reaches
  needs-a-loan entries (~12/150 games) and money-blocked entries (~280).
- Equivalent mutant again: "one plan per round" check (forward-only movement, visit ends turn).

Phase 4 unit 6 (PW Hut Construction R-095, PW Drying R-096, 2026-11-06): engine matched the spec
(PW-build legality oracle over 300 games, 78 PW builds; tightened drying oracle over 550 games, 0
violations). Recurring classes:
- **Invariant exemptions wider than the rule that needs them.** The drying-capacity check was
  skipped for any seat that ever planned Drying (future targets included) and dropped the disk/log
  mix check that R-096 keeps; `hut_built` (global) already skips every seat once anyone builds.
  For each new exemption ask: gated on round/seat? does it drop sub-checks the rule never relaxes?
  is there still an upper bound (2x cap)? A tightened oracle in the probe proves it's affordable.
- **Boundary test named for one thing, body checks another.** "not_doubled_in_the_round_after_the_
  target" only checked the forced advance; mutant "doubling persists after target" survived the
  whole fast suite. Read each boundary test body against its name and mutate the gate (`==` round
  -> `<=` round) via a plugin patching the module-global import (`lignum.woodwork.plan_active`).
- **Pending marker reused for a fixture limit** on an implemented rule ("pending implementation of
  R-096" while the fixture just goes bankrupt in winter). See the unit-8 note above.

Phase 4 unit 7 (PW Overtime R-097, Log Driving R-098, Cutting R-099, 2026-11-06): engine matched
an independent oracle (~325k steps, 860 games, 2-4p; off-mask probe on 880 new nodes, 0 accepted).
27 mutants, 2 survivors. Recurring classes:
- **User rulings land in engine + ACTIONS but not in SCENARIOS/spec.** Round-4 Overtime ruling:
  SCENARIOS still says `WS` round 8 only; ACTIONS WS row and 5.9's first sentence still say round 8
  (ruling appended after the old text). For each ruling, grep its subject in SCENARIOS.md,
  ACTIONS.md (rows + prose) and the locked spec (propose an amendment).
- **New decision node exempted from dump S-MIDTURN while its twin refuses.** dump_scenario accepts
  RS/WS after TAKE_OVERTIME (before DONE) but refuses NB after TAKE_BONUS; a reload per SCENARIOS
  ("first undecided holder") re-offers the take. Probe dump on every new mid-node action.
- **Order mutants survive when the ordered decisions don't interact** (winter Overtime by fall
  clearing order instead of starting track). Outcome-equivalent, so minor; still ask for a
  2-holder winter test since the observer sees earlier choices.
- **Over-broad flag mutants** (cut_lost = every area) survive when the negative test's fixture has
  no outside take at all. Demand the near-miss fixture (outside take from a *different* area).
- **Tests written lenient for an open structure question stay lenient after the ruling** (settle()
  plays DONE "if still asked"); the ruled behaviour (TAKE doesn't close the node) is pinned only by
  accident. Re-read helper docstrings that say "not fixed" once a ruling lands.
- Phase 4 unit 8 (winter hut workers, wcut per seat, 2026-11-06): PASS, 6 mutants all killed. But
  **per-round counters reset in cleanup (wcut) are killed only by goldens**: no rule test reaches the
  year-2 winter, so "counter never resets" is guarded only by the replay hashes. Ask for a round-8
  first-action test for each new per-round counter. Mutation recipe without plugins: `cp -r lignum
  tests data tools pyproject.toml` into scratch (NOT docs/: the spec-lock hook blocks any command
  naming RULES_SPEC), run `PYTHONPATH=<copy> uv run --project <repo> pytest tests/rules
  tests/test_playthroughs.py`; ignore test_constants/test_data_crossrefs (need docs/).
- Phase 4 unit 10 (buildings A: Waterchannel/Marketstand/Storeroom/Small Workshop, 2026-11-07):
  PASS. Fuzz oracle (12k games, feeding wrapped via `G.LignumState._pay_feeding`) and off-mask probe
  clean. Survivors repeat known classes: **turn-flag reset (`w_wc` never reset) survived tests AND
  goldens** (goldens never take buildings, so no golden guards any building effect); "hardwood never
  to sale" negative test had no hardwood in the fixture; "no WC on bearer/wagon" fixture always had
  rafts. Building yaml params unused again (`immediate_pieces_per_transport_phase`,
  `reed_as_shingle_max`). Fuzz bias that reached buildings: weight CHOOSE_BUILDING 50, BUILD_HUT 20,
  WC_MOVE 30, USE_PW_LOGDRIVING 20, TAKE_LOAN 0.05 (~7 s / 500 games).
- Round-gate `==` -> `<=`/`>=` mutants per card were all killed (patch plan_active in rules,
  woodwork, game, huts). Recipe: mutplug with per-pw_id comparison override.
- Phase 4 unit 11 (buildings B: Drying Area Upgrade/Small Joinery/Inn, 2026-11-07): PASS. Fuzz
  (400 games, buildings white-box assigned at the first decision node, W7 DRY_ENTER-set oracle,
  PLAN cost oracle, FS joinery oracle with fuzzed joiners/joinery_wood/owner) 0 problems. Classes:
  **"replaces X" effects tested only where X is small**: Inn ($0) vs a "$1 discount" mutant survived,
  since no Inn holder ever faced 2+ tokens. For each override, demand a fixture where the base
  value is >= 2 steps away. **Invariant branches for buildings are dead in the suite** (sims never
  hold buildings): loosening the upgrade cap in invariants.py survived. Copy-recipe baseline: 1
  failure (test_R075_action_space_sizes_match_actions_doc, needs docs/) — subtract it.
- Phase 4 unit 12 (buildings C: Small Storage/Field/Office, 2026-11-07): rules PASS (fuzz 200
  games 2-4p with buildings white-box given to every seat, 0 problems; 20 mutants, 1 survivor).
  Classes: **Engine bent so the tests' snapshot helper works mid-turn.** STORE_PIECE and PLACE_TASK
  src 2 skipped `w_dirty` so `dump_scenario` (harness snapshot) succeeds after them; 9 tests depend
  on it (setting w_dirty fails exactly those). But the action still sets `win_closed`, so the dump
  claims a boundary with an open hut window that is closed (SCENARIOS 1.3). For every new action
  that skips w_dirty, set it in a mutant copy and see which tests fail. Field: "$0 and loan room"
  fixture masked a "Field still needs $1-or-loan to enter" mutant (needs $0 AND max loans; same
  class as PW "any option"). `capacity: 1` yaml param unused (single slot hard-wired).
  Fuzz note: `bld_supply` is a derived property (no setter); phase names via `game.PHASE_NAMES`,
  since `H.phase_of` dumps and raises S-MIDTURN mid-turn.
- Phase 4 close (2026-11-07): engine PASS (1800-game white-box fuzz: inject buildings/craft/huts/
  plans/equip at the first SP node, oracle for Market legal set + entry, Buildings entry, hut-window
  set, sale/food/yield deltas; 0 problems, ~4 s per 100 games). 20 mutants, 4 survivors, all the
  **"modifier tested only on the case it changes most"** class: PW Heating Supply applied to
  softwood/hardwood, PW Craftwork 4-set ($11) never sold, food hut excluding the seat's OWN area,
  winter food hut using stale `picks` (fixture food never sat in another seat's last area). For
  every "X instead of Y for kind/size Z" effect, ask for a test on the kinds/sizes it must NOT
  change and on the largest size. Trade-only Market entry was killed only by a golden.
  Equivalent mutant: Buildings "supply non-empty" check (supply empties only when all own 2).
  Copy recipe now works with docs/ copied too (`cp -r docs` is not blocked); baseline 0 failures.
  `picks` persist through winter in state (cleanup doesn't clear them) - view labels them round 4/8.

Phase 5 unit 7 (terminal `score` breakdown in the adapter, 2026-11-07): components matched a
yaml-only oracle (1200 fuzzed games, 2-4p, both returns, joinery on/off, ~400 river choices,
~1000 negative finals, 0 mismatches). Recurring classes:
- **Remainder-balanced breakdowns make "parts sum to total" tests tautological.** `money` =
  final - other parts, so any wrong component is silently absorbed. Demand an independent value for
  the remainder (engine-recorded parts or a fuzz oracle), and value asserts on fuzzed terminals;
  random-play terminals are all-zero parts, all tied at -16 (see Phase 2 close note).
- **Replay-based recomputation reads the state *before the triggering action*, not the state the
  engine used.** The adapter rebuilds "pre-final-sale" as the clone before the action entering
  FS/END; correct only because N5/N6/cleanup touch no sale zones. Any future automatic step inside
  that action lands in `money`. Suggest engine-side recording of the parts.
- Probe recipe for replaying consumers: fuzz inside an engine method that runs in an EARLIER action
  (wrap `_next_winter_turn`, fuzz on N3->N4 in round 8, rng keyed on str(history)) so the
  consumer's replay reproduces it; snapshot at `_begin_final_sale` entry for the oracle. Fuzzing
  inside `_begin_final_sale` itself is invisible to the replayed `pre` and gives false mismatches.

Phase 5 close (board UI, 2026-11-09): view clean (pk-swap over every new field, 1050 comparisons,
0 diffs; history entries carry no params). Recurring classes for UI audits:
- **UI-only relabels leave server-built strings in the old terms.** The Log(unmilled)/Milled
  relabel changed web labels only; adapter action labels ("Sell firewood log" = milled), task
  requirement text and SAW labels still use spec disk/log, and they render in popovers right over
  pad items labelled the opposite way. On any terminology change, grep the adapter `_ACTION_FMT`,
  `_req_text`, `_PIECES` and every web consumer of `label`/`text`. (Fixed in 5f0b24d. Re-check
  recipe: sprite ids `piece-<k>-disk|log` and view keys `sale_logs` keep spec terms by design, so
  filter them out; check that `_PIECES` order still matches `2*kind+milled` (constants.py); look at
  the meaning of SAW's `n` (logs to firewood storage); test fixtures may keep the old strings.)
- **Two-sided card sprites shown whole.** Winter cards render both halves (sprite + viewer text
  from yaml) with the active half only in aria/title; the viewer's `describe` drops the view's
  `detail`. For any card where only part applies, check the UI marks the active part.
- **Data-derived "effect text" from params is partial** (Storeroom, Small Storage, Drying Upgrade
  lose half their rule). Not wrong, but not "full text"; flag minor.
- Generated art bakes data at build time; the byte-identical regeneration test catches yaml drift
  only for values the generator reads. Grep generator string literals for prices ("$1 per token").

Phase 6 unit 3 (bot value function `lignum/bots/value.py`, 2026-11-09): data sources clean (all
prices/rewards via SetupTables/yaml, no picks read). Recurring classes for bot/value audits:
- **Value mirrors of a multi-step sale forget sub-steps already done.** At FS a chooser's unsold
  river kind stayed valued after its choice (same class as unit 11's sweep bug), so every
  non-last chooser was indifferent between kinds (probe: 1 fw vs 5 sw, both 8.2; true gap $17).
  Probe: wrap `_begin_final_sale` to set river (1,5,0) for all seats, compare value per choice.
- **Horizon flags keyed on round, not on remaining phases.** "last winter => upstream wood $0"
  ignored round-8 sledge (R-067) and sawing (R-068) into the sale area; river is final already
  after round 7's W2 (no log driving in winter). Check each "can't be sold any more" cutoff
  against the remaining phase list.
- Leftover items worth $0 at the end (craft, buildings, plans, partial tasks) keep heuristic value
  through round 8: harmless constant offsets, minor. Terminal tests on random play are vacuous
  (all tied, see Phase 2 close note).

Phase 6 unit 5 (hidden-pick resampler `lignum/bots/resample.py`, 2026-11-10): sound (0 info-state
string/tensor mismatches over ~1,150 states x all seats, 2-4p; `pk` is () outside PHASE_PK, so
round 1, winter and Overtime nodes are identity). Probe facts worth reusing:
- `LignumState.clone()` rebinds the pyspiel base, so a clone's `history()` is **empty**: no leak
  through history, but anything reading `history()` on a clone/sample (invariants.py error text,
  replay tools) sees []. Python ISMCTS never reads history.
- No per-state caches in `__dict__` (only the game-level `_full_observer`), so info-state equality
  tests on clones are not vacuous by shared memo. Re-check if a string cache is ever added.
- Leak test recipe: build `alt` with hidden picks shifted, same rng => identical samples. Catches
  "truth + noise" draws that pass a uniformity check. Support check (`in range(6)`, >=3 distinct)
  does not catch a draw that never yields area 6 (`randrange(5)`).

Phase 6 close (bots, 2026-11-10): no leaks of real hidden info (pk-swap probe, 30 games 2-4p, 300
PK nodes: info-state string/tensor, observation, value, and heuristic/ISMCTS/determinized
`choose(st, Random(5))` vs `choose(alt, Random(5))` all identical). Recurring classes:
- **Custom search keyed by action path brings hidden picks back inside the tree.** lignum/bots/
  mcts.py keys nodes by the path from the root, so an in-tree seat picking after another sees the
  earlier seat's unrevealed PK action (R-038 says order has no strategic meaning). OpenSpiel's
  Python ISMCTSBot (D22) keys by `information_state_string()` (ismcts.py get_state_key). Check any
  hand-rolled search for what its node key contains; the D27 info-state may go unused.
- **Stop-cost / budget tables that skip some priced locations.** heuristic `_stop_cost` returned
  $0 for planned work ($1/token, R-041) and `_location_key` didn't check it, so the bot walks into
  PW unaffordable and is forced into a loan (4/72 seats). D29-legal, but "prices from data" was
  only partly true. Grep each bot cost table against the R-041 location list.
- Expected sim fact: heuristic seats take both loans in round-4 SF in ~every game (mean final
  ~-13.5, all 2 loans), so heuristic sims don't exercise scoring either.
- Probe: classify every bot TAKE_LOAN as sole/SF/enables-new-action (clone + apply, diff legal);
  anything else violates D29.

Phase 7 own-turn-solver claim check (2026-11-11): "a W/N turn has no chance and no other seat"
HOLDS by construction. Chance only when phase SC, or RS with `rd` set (`_begin_round`, reached only
from the last W7 DONE or `_end_winter`); W/N current seat = clearing/wint[w_turn], and w_turn moves
only in `_next_turn` (DONE, or the W2 last-river-piece auto-end) and `_settle`. `pk` is () outside
PK, so in-turn true state == info state. Recurring class for solvers/turn-segment tests:
- **The same seat can act in two consecutive turns with nothing between them**: W1 last seat ->
  W2 when only it has river wood (`_skip_empty_rivers`); W2 sole river seat clearing[0] -> W3;
  N4 last DONE -> its own SF; FEED SF -> its HEAT SF after automatic payers; WS Overtime -> NB.
  W2 has no DONE (auto-end). Turn end must be keyed on (phase, w_turn) change or DONE, never
  on current_player change; check any turn-scoped search/test for this.

Phase 7 close (bot task planners plan.py/tasks.py, 2026-11-12): engine/spec/data untouched (diff
only lignum/bots, tools, server registry). No blockers; planner misreadings, all bot quality:
- **Planner clock keyed on phase, not on whether the evaluated seat already acted in it.**
  `_clock` uses `phase <= W4` etc., so after a seat's own W4 DONE (non-last seat, phase still W4)
  its unsawn disk still counts as ready this round (probe: round 5 W4, task 17 hw+2 stays
  finishable after DONE, dead in truth). Solver leaves in W1-W4 and MCTS opponent values inherit
  it; W7 `w_dirty` is the *current* seat's flag, wrong for other seats. Check every bot horizon
  against "has THIS seat's turn in the phase passed" (clearing/wint index vs w_turn).
- **Winter resource limits ignored by planners**: one mill worker per winter round (C6) means
  sledge+saw (woodpile -> milled) is impossible in round 8 without hut workers, and only one disk
  is sawn; "saw by money" ignores that saws come from path locations (no path in winter, none
  after TR). Probe with `tests/bots/test_plan.board(8, PHASE_N1, woodpile=..., held_tasks=...)`.
- **Building-provided sources missing from planners + "dead task" action filters**: Small Storage
  piece (R-114, any stage, round 8 N4) not in planner stock, so the task looks dead and
  `_wood_work` drops PLACE_TASK(slot,2) -> all pipeline profiles play DONE instead of completing
  the card (board(8, PHASE_N4, small_storage=(2,-1), wint=(0,1), held_tasks=((17,),()))).
  For any filter "only actions for live tasks", check the action that would make it live.
- Hard-coded board values reappear in bot code (fodder 3/2, drying disk cap 1) even when
  SetupTables has the field (`dry_cap_disks`); grep each new bot module for small literals.
