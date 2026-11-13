# Lignum — Scenario Format

**Status:** DRAFT (Phase 1 unit 10). Companion to `docs/RULES_SPEC.md` (R-IDs) and `docs/ACTIONS.md` (action and chance IDs). If this file disagrees with the spec, the spec wins and this file is fixed. Card and path values are not restated as rules here: ids and counts come from `data/components/*.yaml`. Numbers quoted in the worked examples (§9) are checked by the example tests, not by this file.

A **scenario** is a JSON document that describes a position in one game of Lignum, plus optionally the action ids to play from it. It serves three users with one format:

1. **Rule tests** load a scenario as the start state of a small fixture (PLAN §6 "rule tests on small scenario fixtures"; files in `tests/scenarios/*.json`, loader `lignum/scenario`).
2. **The setup editor** (Phase 5) produces and consumes scenarios. Per PLAN D18, an editor-built game is persisted as **the scenario JSON plus the action history after it**; the server never accepts a `serialize()` string from a client. The server validates a scenario with the same loader as the tests.
3. **Mirroring a physical table**: a scenario transcribes what is on a real table at a turn boundary (§1.3), so a human game can be continued or analysed in the engine.

A scenario is **a position, not a history**. It need not be reachable by legal play; the loader checks only the invariants of §7. This keeps fixtures small. Seats are numbered from **0** everywhere (`seats[0]` is P0). Files are JSON (`.json`, UTF-8); the loader also accepts YAML with an identical schema.

## 1. Concepts

### 1.1 Resolved versus shorthand
A scenario may omit almost everything. The loader turns a **shorthand** scenario into a **resolved** one by applying, in order: the defaults of §6, the sampling of unspecified chance-dependent fields (§6.3), and derivations (§4 "derived"). A **resolved** scenario states every field explicitly. `dump_scenario(state)` always emits a resolved scenario (§8).

### 1.2 Conventions
- **Piece keys** (wood). A *piece map* is an object from piece key to count; absent key = 0; unknown key = error. A piece map may also be written as a list of piece keys (repeats allowed), e.g. `["firewood_disk","firewood_disk"]` for `{"firewood_disk": 2}`.

  | Piece key | `p` (ACTIONS §1.5) | Meaning |
  |---|---|---|
  | `firewood_disk` | 0 | unmilled firewood |
  | `firewood_log` | 1 | milled firewood |
  | `softwood_disk` | 2 | unmilled softwood |
  | `softwood_log` | 3 | milled softwood |
  | `hardwood_disk` | 4 | unmilled hardwood |
  | `hardwood_log` | 5 | milled hardwood |

- **Kinds**: `"firewood"`, `"softwood"`, `"hardwood"`. **Craftwork types**: `board`, `shingle`, `stake`, `reed`, `joker` (order of `setup.yaml` `craftwork_by_type`). **Equipment types**: `saw`, `wagon`, `raft`, `sledge`.
- **Ids**: tasks `task_01`..`task_19`, placement cards `placement_01`..`placement_19`, winter cards `winter_1_1`..`winter_2_4`, planned work `pw_*`, buildings `waterchannel`..`office` (the `id` fields of `cards.yaml`, `planned_work.yaml`, `buildings.yaml`).
- **Cutting areas** are numbered 1..6 (printed numbers). **Path locations** are printed numbers on the chosen side (R-032); `0` = start; the forest clearing slots are `"A"`..`"D"` (R-024).
- **Rounds** 1..8 as R-033 (1 spring y1, 2 summer, 3 fall, 4 winter y1, 5 spring y2, 6, 7, 8 winter y2).
- Unknown top-level or nested keys are an error (`S-SCHEMA`).

### 1.3 Turn boundaries only
A scenario can be placed only at a **turn boundary**: the acting seat is about to take the first action of a turn (a supply-path visit, a wood-work or winter phase turn, a pick, a round-start option) and has taken no action in it, except possibly loans. Mid-turn state (a visit with some acquisitions made, a trip in progress, an open hut build, a worker assigned, a partly resolved shortfall, hidden picks apart from the seat prefix of §4.4) is **not representable**. Fixtures that need mid-turn states reach them with `history` (§5). `dump_scenario` on a mid-turn state raises `ScenarioError("S-MIDTURN")`.
Consequently these per-turn facts are not stored: the hut/PW window is open at a boundary (ACTIONS §1.7); the Waterchannel and trip counters are zero; "seat has played this phase" is derived from `current_player` and the phase's order.

## 2. Top-level fields

`Vis`: **pub** = public information (R-028); **priv** = hidden information (R-029; one field only); **meta** = not game state (never part of an observation).

| Field | Type | Req | Default | Vis | Meaning |
|---|---|---|---|---|---|
| `format` | `1` | yes | – | meta | format version |
| `kind` | `"setup"` \| `"state"` | no | `"state"` | meta | `setup` restricts the scenario to a fresh game (§6.4) |
| `description` | string | no | `""` | meta | free text |
| `parameters` | object | no | R-001 defaults | pub | `players` 2..4 (2), `joinery` bool (true), `returns` `"win_loss"`\|`"margin"` (`"win_loss"`), `easy_winter` bool (false) |
| `round` | int 1..8 | no | 1 | pub | R-033 |
| `phase` | code | no | first decision phase of the round (§3) | pub | phase code of ACTIONS §4, restricted to §3 |
| `current_player` | seat | no | first seat the phase would call (§3) | pub | the seat to act (never a chance node: scenarios sit at decision nodes) |
| `turn_order` | list of seats | no | `[0..n-1]` | pub | starting-player track, position 1 first (R-016, R-060); in winter and after a fall round it is the order set at the end of fall (R-060) |
| `clearing_order` | list of seats \| null | cond. | `null` | pub | clearing slots A, B, C, D in order. Required in W1..W7, WS, NB, N1..N4, FS. During TR it is derived from the foremen's slots. `null` in SP, RS, PK |
| `seats` | list (or map `"0"`..) of seat objects | no | all defaults | see §4 | one entry per seat; missing entries are defaults |
| `cutting_areas` | list of 6 area objects (or map `"1"`..`"6"`) | no | R-015 layout (§6.2) | pub | §4.2 |
| `path` | object \| null | cond. | R-017 fill (§6.2) | pub | supply path, §4.3. Must be `null` in winter phases and FS |
| `planned_work` | object | no | `{laid_out: sampled, plans: []}` | pub | §4.5 |
| `supply` | object | no | sampled/derived | pub | decks, building supply, winter cards, craftwork bookkeeping, §4.6 |
| `seed` | int | no | 0 | meta | PRNG seed for sampling (§6.3) |
| `chance` | list of chance ids | no | `[]` | meta | explicit chance outcomes consumed by the sampler (§6.3) |
| `history` | list of ints | no | `[]` | meta | action ids applied after the scenario (§5) |
| `expect` | object | no | none | meta | assertions after `history` (§5.2) |

## 3. Phases

`phase` uses the codes of ACTIONS §4. A scenario may rest only where the engine has a decision node, so the allowed phases and their constraints are:

| Phase | Round | Meaning at load | `current_player` default |
|---|---|---|---|
| `SP` | 1 | setup token placement, public, seat order (R-015); seats before `current_player` have their `cutting_area` set, the rest `null` | first seat without a token |
| `RS` | 2,3,5,6,7 | round-start fills, income and chance are done; Overtime holders decide (R-097). Valid only if some seat has a plan on `pw_overtime` with target = `round` | first undecided holder in `turn_order` |
| `PK` | 2,3,5,6,7 | hidden picks, seat order. Seats before `current_player` have `pick` set; all `cutting_area` are `null` | first seat without a pick |
| `TR` | 1,2,3,5,6,7 | supply-path travel (R-040). All `cutting_area` set (revealed) | per cycle; **explicit** `current_player` is always required |
| `W1`..`W7` | 1,2,3,5,6,7 | wood-work phase `n` (R-045); foremen in the clearing | first seat in `clearing_order` |
| `WS` | 4, 8 | Overtime holders of round 4 or 8, before the bonus (R-097); the same rule as `RS` | first undecided holder |
| `NB` | 4,8 | winter bonus (R-065) | first seat in `clearing_order` |
| `N1`..`N4` | 4,8 | winter woodcutting, sledge, sawing, tasks (R-066..R-069) | first seat in `clearing_order` |
| `FS` | 8 | final sale river choice (R-081); the state **after** R-081 steps 1 and 3 (sale/drying areas and covered joinery already sold, user decision 2026-11-05; §10 Q1) | first seat whose river holds both firewood and softwood |

Not allowed as resting phases (automatic or mid-turn): `SC`, `N5`, `N6`, `SF`. A fixture for feeding, heating or the shortfall sale rests at `N4` with the last seat to act and uses `history` (§9.2). A round-8 game that has no seat with both river kinds goes straight from heating to terminal, so `FS` is valid only when some seat has a choice.

Order of the seats for the "seats before/after `current_player`" tests: `turn_order` for `SP`, `PK`, `TR`, `RS`, `WS` (seat order 0..n-1 for `SP`, `PK`: R-016, R-038); `clearing_order` for the rest (R-045, R-064).

Round and phase compatibility: `PK`/`RS` not in round 1 or winter; `SP` only in round 1; `N*`, `NB`, `WS`, `FS` only in rounds 4, 8 (`FS` round 8 only); `TR`/`W*` only in seasonal rounds.

## 4. Seat, board and supply objects

### 4.1 Seat object (`seats[i]`)
All fields optional. Defaults are the R-018 starting holdings.

| Field | Type | Default | Vis | Meaning / rule |
|---|---|---|---|---|
| `money` | int ≥ 0 | 5 | pub | R-018 |
| `loans` | 0..2 | 0 | pub | R-011, R-075 (the card side follows from the count) |
| `hired` | `{woodcutters, bearers, sawyers}` ints | all 0 | pub | hired workers in the worker area this round (R-043); 0 outside TR..W7 |
| `mill_worker_used` | bool | false | pub | the mill worker has been used this round (R-045; C6) |
| `task_taken` | bool | false | pub | took a task at the Tasks location this round (R-041) |
| `fodder_bought` | bool | false | pub | bought fodder at the Fodder location this round (R-041) |
| `foreman` | 0..N \| `"A"`..`"D"` | 0 (TR); slot of `clearing_order` (W/N phases: derived and must not be given) | pub | N = last location number of the side (20 or 22). In winter the foreman is 0 (R-061) |
| `cutting_area` | 1..6 \| null | `null`; default in TR..W7 = the seat's setup area (§6.2) | pub | the area of the seat's cutting token, revealed |
| `pick` | 1..6 \| null | `null` | **priv** | hidden pick, only in `PK`, seats before `current_player` (R-029). Must be `null` in every other phase |
| `joiners` | 0..3 | 0 | pub | R-078; must be 0 if `joinery` is false |
| `buildings` | list of ≤ 2 building ids | `[]` | pub | R-106; empty if `joinery` is false |
| `small_storage` | milled piece key \| null | `null` | pub | the piece in the Small Storage Area (R-114; one piece per game); requires the building |
| `small_storage_spent` | bool | `false` | pub | `true` once the stored piece has been moved to a task; the building then cannot be refilled (R-114: one piece per game). Must be `false` while `small_storage` holds a piece |
| `equipment` | `{saw, wagon, raft, sledge}` ints ≥ 0 | 0 | pub | `saw` ≤ 4 (R-042) |
| `craftwork` | `{board, shingle, stake, reed, joker}` ints ≥ 0 | 0 | pub | R-042, R-028 |
| `huts` | `{drying, food, worker}` ints ≥ 0 | 0 | pub | unspent hut tokens on each hut-effect area (R-100..R-103); at most 3 per area |
| `food` | int ≥ 0 | 0 | pub | food storage |
| `fodder` | `{slot3: bool, slot2: bool}` | both false | pub | fodder on the value-3 / value-2 slot (R-043) |
| `woodpile` | piece map | `{}` | pub | unmilled pieces only |
| `sawing` | piece map | `{}` | pub | unmilled pieces only (R-046) |
| `sale` | piece map | `{}` | pub | no `hardwood_disk` (R-046, R-058) |
| `drying` | list of 3 piece maps | `[{},{},{}]` | pub | drying areas 1..3; no `hardwood_disk`; capacities are warnings only (§7, S-DRY) |
| `river` | piece map | `{}` | pub | unmilled pieces only (R-053) |
| `firewood_storage` | piece map | `{}` | pub | milled pieces only (R-046, R-072) |
| `joinery` | list of 3 (kind \| null) | `[null,null,null]` | pub | milled piece kind in joinery slot 1..3 (R-057); requires `joinery`; each kind at most once |
| `tasks` | list of `{id, filled}` | `[]` | pub | held task cards; `filled` = list of requirement indices (0-based, order of `cards.yaml`) already locked (R-055, R-056). A locked piece is exactly the requirement shown, so nothing else is stored |

`woodpile`, `sawing`, `sale`, `drying`, `river`, `firewood_storage` accept the list shorthand of §1.2.
A seat has exactly one mill worker (R-018); it is always present, so only its used flag is stored.
Hired workers are not stored per location: the worker area holds `hired` (R-043).

### 4.2 Cutting areas (`cutting_areas`)
A list of six objects (index 0 = area 1), or a map keyed `"1"`..`"6"`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `wood` | `{firewood, softwood, hardwood}` ints | per §6.2 | unmilled pieces in the area (R-015, R-037) |
| `food` | int ≥ 0 | 0 | food cubes in the area (R-037, R-039) |

Cutting tokens are **not** stored here: they are `seats[i].cutting_area` (revealed) or `seats[i].pick` (hidden). Seats sharing an area is a state where two seats have the same `cutting_area`.

### 4.3 Supply path (`path`)
`null` in winter phases and `FS` (the path is cleared at the end of fall and rebuilt at the start of round 5, R-061, R-035). Otherwise:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `bearers` | int ≥ 0 | R-013 count minus `hired.bearers` of all seats | bearers on the Bearers location |
| `woodcutters` | int ≥ 0 | likewise | on the Woodcutters location |
| `sawyers_free` | int ≥ 0 | R-013 price-0 count minus free sawyers taken | sawyers at $0 |
| `sawyers_paid` | 0..1 | 1 | the $1 sawyer |
| `fodder` | int ≥ 0 | R-013 count | fodder on the Fodder location |
| `joiner` | 0..1 | 1 if `joinery` and the joiner supply is not empty (R-035), else 0 | joiner on the Joiner location |
| `tokens` | map printed number → token \| null | sampled (§6.3) | the 13 token spots (R-023). Keys are exactly the `token_spot` locations of the chosen side (R-032); `null` = taken. Token values: `wagon`, `raft`, `saw`, `sledge`, `dollar`, `food`, `x` (X-marker, 2 players), `board`, `shingle`, `stake`, `reed`, `joker` |

Sawyers hired by seats: the seat holds `hired.sawyers`; a seat with 1 holds the free one, with 2 also the $1 one. `sawyers_free + sawyers_paid + Σ hired.sawyers` must equal the R-013 total (S-WORKERS). The building supply is not on the path; it is in `supply.buildings`.

### 4.4 Hidden picks
Only `PK` has hidden data: `seats[i].pick` for the seats before `current_player`. An observer sees its own seat's pick only (R-030). A scenario is the perfect-information view; the server's persistence layer may store it, but must never send another seat's `pick` to a client.

### 4.5 Planned work (`planned_work`)
| Field | Type | Default | Meaning |
|---|---|---|---|
| `laid_out` | list of PW ids | sampled, `players + 2` cards (R-014) | the cards beside the PW location; fixed all game (R-087) |
| `plans` | list of `{seat, card, pair, target}` | `[]` | `pair` 1..3 (R-087); `target` = round 1..8 = (round planned) + `pair` (R-088) |

Tokens on a card (for costs) and tokens on the planning area are **derived** from `plans`: two tokens per plan. A plan whose `target` is earlier than `round` is allowed (its tokens still count for costs, R-088).

### 4.6 Supply (`supply`)
| Field | Type | Default | Vis | Meaning |
|---|---|---|---|---|
| `tasks_laid_out` | list of task ids | sampled (`players` cards, R-014) from tasks not held | pub | face-up task row (R-036); fewer than `players` only if the deck is empty |
| `placement_discarded` | list of placement ids | sampled, count per §7 S-PLACE | pub | placement cards already used (R-037); the rest are the deck |
| `winter` | `{year1: W, year2: W}`, `W = {card, half}` | sampled (R-014, R-027) | pub | the two winter cards in effect; `half` is `"top"` or `"bottom"` as in `cards.yaml`, the half in effect (R-027) |
| `buildings` | list of building ids | sampled (R-019) when `joinery`, else `[]` | pub | the building supply on the table (R-106) |
| `craftwork_removed` | `{board, shingle, stake, reed, joker}` ints | `{}` | pub | craftwork tokens out of the game: sold, flipped into huts, or removed leftovers (R-017, R-061, R-105) |

**Derived, never written** (and an error if given): the task deck (`task_NN` not laid out and not held), the placement deck (all placement ids minus `placement_discarded`), the craftwork pile (per type: total minus path, held, `craftwork_removed`), the joiner supply (`supply.joiners` in `setup.yaml`, currently 6, minus path minus held), loan cards in the supply, tokens on PW cards and planning area, `clearing_order` in `TR`, foremen slots in W/N phases, and the cutting-area tokens on the board.
Undrawn deck order is not state (R-029): decks are drawn lazily and uniformly (ACTIONS §2); only membership is stored.

## 5. History and expectations

### 5.1 `history`
A flat list of ints exactly as in a replay file (`tools/replay.py`): decision ids and chance outcome ids in one list, decoded by replaying with the state. After the scenario is loaded the loader applies each entry in turn, checking that decision ids are legal at a decision node and that chance ids have non-zero probability at a chance node (the same check as `tools/replay.py`). A violation is `ScenarioError("S-HISTORY", index)`. After the list the state is wherever play stopped; if that is a chance node the test applies outcomes itself (the loader never samples during `history`).
`State.history()` of a loaded state returns **only** the `history` entries (not the prefix that produced the scenario, which does not exist); OpenSpiel `serialize`/`deserialize` of such a state is not replayable from `new_initial_state` and must not be used for persistence (PLAN D18). The persisted form of an editor-built game is `{"game", "params", "scenario": {…}, "history": […]}`, the replay file plus a `scenario`; `tools/replay.py` gains support for the `scenario` key when the loader lands (Phase 2).

### 5.2 `expect` (optional)
Documents what a fixture proves. Only keys listed are checked.
```json
"expect": {
  "phase": "TR",
  "current_player": 0,
  "legal_after": {"0": [1, 2], "2": [0]},
  "scenario_subset": {"seats": [{"money": 8}]},
  "terminal": false,
  "final_dollars": [39, 30],
  "returns": [1.0, -1.0]
}
```
- `legal_after`: prefix length (string) → exact sorted decision-id list after that many `history` entries (`"0"` = right after loading).
- `scenario_subset`: matched against `dump_scenario` of the state after all of `history`: objects match recursively, lists index-wise (use `{}` to skip an element), scalars by equality.
- `phase`, `current_player`, `terminal`, `final_dollars` (R-083 values, terminal only), `returns` (R-085/R-086) refer to the state after all of `history`.

## 6. Defaults, shorthand and sampling

### 6.1 Minimal scenario
`{"format": 1}` is valid: 2 players, joinery, round 1, phase `SP`, default seats, sampled setup. Everything omitted follows 6.2 and 6.3. A fixture lists only what its test depends on; hidden dependencies on sampled data are a test bug (use the resolved dump in a review to see them).

### 6.2 Defaults filled from the setup rules
- **Seats**: R-018 (money 5, no wood/food/fodder/equipment/craftwork/joiners/buildings/loans, foreman 0, mill worker unused).
- **Turn order**: identity (R-016). **Clearing order**: none until required (§2).
- **Path** (R-013, R-017, `setup.yaml`): full counts less `hired` of the seats (hired workers come off the path); `sawyers_paid` 1; fodder full; joiner per R-035; 13 tokens sampled with the 2-player X-marker mix; all tokens present.
- **Cutting areas**: the R-015 layout: `parameters`-dependent number of areas with 3 firewood (sampled uniformly, §6.3, node `AREAS3`) and the others with 2 firewood, no softwood or hardwood, no food. The same default applies to every round (it does not simulate the placement cards of earlier rounds: a fixture whose test depends on area contents says so).
- **Seat cutting area** when required (TR..W7) and omitted: seat `i` gets the `i`-th lowest-numbered area that holds 3 firewood in the *resolved* `cutting_areas`.
- **Decks/layout**: laid-out tasks (`players`), PW cards (`players + 2`), building supply (R-019 count less buildings held by seats) are sampled uniformly without replacement from the cards not already placed elsewhere.
- **Winter cards**: one card per year, uniformly; with `easy_winter=true` the easier half (lower food+heating, R-117), otherwise a uniform half (R-027).
- `current_player`, `phase`: §3.

### 6.3 Sampling and the `chance` script
Unspecified fields that correspond to a setup chance node (ACTIONS §2) are resolved in the **canonical order of ACTIONS §2** (`AREAS3`; `WINTER` year 1; `WINTER` year 2; `TASK_DRAW` ×; `PW_DRAW` ×; `BUILDING_DRAW` ×; `CRAFT_DRAW` ×3; `SPOT_TOKEN` ×13). For each node, if `chance` has an unconsumed entry it is used (it must be a valid outcome for that node type and not conflict with already-resolved cards, else `S-CHANCE`), otherwise the node is sampled uniformly (probability by the ACTIONS §2 distribution) from `random.Random(seed)`, indexing the sorted candidate list with `rng.randrange(len)` (stable across Python versions). Specified fields skip their nodes and consume nothing. `chance` is therefore the "explicit deck order" of a fixture: e.g. `[28, 29]` lays out `task_01`, `task_02`. Leftover `chance` entries are an error (`S-CHANCE`). The same seed and scenario always give the same resolved scenario (R-031).
A fully resolved `kind: "setup"` scenario is equivalent to the setup chance sequence of ACTIONS §2 followed by the `PICK_AREA` decisions of the seats before `current_player`; the loader may start from the scenario directly. (That equivalence is to be checked by a Phase 2 test on `setup_basic` and random setups.)

### 6.4 `kind: "setup"`
Allowed only: `format`, `kind`, `description`, `parameters`, `cutting_areas`, `seats[].cutting_area` (phase `SP` or `TR` only), `path`, `planned_work.laid_out`, `supply.tasks_laid_out`, `supply.winter`, `supply.buildings`, `seed`, `chance`, `history`, `expect`. Round 1, phase `SP` or `TR`, default seat holdings, `turn_order` identity, `plans` empty, `placement_discarded` empty. In `TR` every `cutting_area` is set to a distinct area holding 3 firewood (R-015). This is the editor's "new game" form.

## 7. Invariants the loader must check

Each failure is `ScenarioError(code, path, message)`. **E** = error, **W** = warning (error under `strict=True`; tests use the default, CI fixtures under `tests/scenarios/` are loaded `strict=True`).

| Code | Sev | Check | Rule |
|---|---|---|---|
| S-SCHEMA | E | field types, enums, ranges of §2–§4; unknown keys; ids exist in the data files; seat indices < `players`; `joinery=false` forbids joiners, buildings, joinery, small storage, `joiner` on the path and the Joiner/Buildings locations | R-001, R-002 |
| S-PHASE | E | `phase` allowed (§3); round/phase compatible; `current_player` in the right order; `RS`/`WS` only with a due Overtime holder; `FS` only with a river choice; `clearing_order` presence per §2 | R-033, R-045 |
| S-ORDER | E | `turn_order` and `clearing_order` are permutations of the seats (`clearing_order` may hold fewer entries only in TR, as the arrival prefix) | R-016, R-024, R-060 |
| S-FOREMAN | E | in TR: foremen on locations that exist on the side (and not on X-marker spots); per-location count ≤ capacity from `path.yaml`; clearing slots filled A, B, … without gaps, one seat each; `current_player` is not in the clearing. In W/N phases: all foremen in the clearing (W) or on 0 (winter); `current_player` in `clearing_order` | R-040, R-044, R-061 |
| S-WORKERS | E | per worker type: path + Σ `hired` = the R-013 count (sawyers: free + paid + hired = price-0 count + 1); hired = 0 outside TR..W7 (and at RS/PK/SP); sawyers hired ≤ 2 per seat | R-013, R-035, R-041, R-061 |
| S-JOINERS | E | `path.joiner` + Σ `joiners` ≤ `supply.joiners` (setup.yaml, currently 6); each seat ≤ 3; at RS/PK, `path.joiner` = 1 iff Σ `joiners` < `supply.joiners` | R-035, R-078 |
| S-BUILDINGS | E | a building appears at most once among supply and seats; `len(supply.buildings)` + Σ held = R-019 draw count (6/7/8); each seat ≤ 2 | R-019, R-106 |
| S-TOKENS | E | `path.tokens`: 13 keys = the token spots; per-type counts ≤ the R-017 recipe (equipment) and craftwork counts on the path + held + removed ≤ totals; exactly 2 `x` for 2 players, none otherwise (X spots never `null`) | R-017, R-023 |
| S-CRAFT | E | per craftwork type: path + Σ held + `craftwork_removed` ≤ total in `setup.yaml`; the pile is the remainder (≥ 0); `craftwork_removed` total ≥ Σ unspent hut tokens (required when any seat has hut tokens) | R-006, R-100 |
| S-LIMITS | E | saws ≤ 4; loans ≤ 2; hut tokens ≤ 3 per area; money ≥ 0 | R-011, R-042, R-100 |
| S-DECKS | E | no task id twice across laid out and held; all laid out / held ids unique across seats; `tasks_laid_out` = `players` cards at SP/RS/PK unless the deck is empty; PW `laid_out` has `players + 2` distinct cards; `filled` indices valid and unique; winter cards are one per year deck and `half` ∈ {top, bottom}; with `easy_winter=true` each half is the easier one | R-005, R-014, R-036, R-117 |
| S-PLACE | W | `placement_discarded` size = placements per round × number of seasonal rounds 2..`round` already past the placement step (rounds 2,3,5,6,7; applies from PK on) | R-037 |
| S-PW | E | each plan: `pair` 1..3 unused by that seat; `target` = made round + `pair` with made round 1..`round`, `target` ≤ 8; `target` season printed on the card; no seat plans the same card for the same target twice; at most one plan per seat per made round | R-087, R-088 |
| S-CUT | E | `cutting_area` set exactly in TR..W7 (and SP for seats before `current_player`), otherwise `null`; `pick` set exactly in PK for seats before `current_player`, otherwise `null`; in SP the placed areas are distinct and hold 3 firewood in `cutting_areas`  | R-015, R-038 |
| S-WOOD | E | zone typing of §4.1 (woodpile/sawing/river unmilled only; firewood storage milled only; no unmilled hardwood in sale/drying); joinery kinds distinct; `small_storage` milled; wood in winter phases only in zones R-046 permits | R-046, R-057, R-114 |
| S-DRY | W | per drying area capacity: 1 disk or ≤ 2 logs, never a disk with logs; 2 pieces any mix with Drying Area Upgrade; PW Drying in its target round doubles area 1. Over-capacity is a warning because huts and PW Drying can leave it | R-059, R-096, R-101, R-111 |
| S-STATE | E | winter phases: `hired` all 0, all foremen 0, `path` null, `task_taken`/`fodder_bought` false; RS/PK/SP: `hired` all 0, foremen 0; no wood on any river in round 1 | R-049, R-061, R-064 |
| S-PICKS | E | PK: `pick` area valid; SP: see S-CUT | R-029 |
| S-FS | E | `FS`: round 8, `clearing_order` present, ≥ 1 seat with both `firewood_disk` and `softwood_disk` on the river and `current_player` is the first such seat | R-081 |
| S-HISTORY | E | each `history` entry legal or valid (§5.1) | – |
| S-CHANCE | E | `chance` entries valid for their node type, consistent with already fixed cards, none left over | R-026 |
| S-MIDTURN | E | (dump only) the state is not at a turn boundary | §1.3 |

Not checked, because the state does not record it: who moved last in TR (the cycle position is the explicit `current_player`), which tokens were taken, whether an Overtime holder has already decided beyond the order rule, drying over-capacity causes. Equipment, wood, food, fodder and money are not conserved (R-009).

## 8. Round trip

1. **Fixpoint**: `dump(load(S))` for a shorthand `S` is the *resolved* scenario `R` (key order fixed, lists canonical: card id lists sorted, zero counts dropped, derived fields absent). `dump(load(R)) == R` byte for byte.
2. **State round trip**: for every state `s` of a play-through at a turn boundary, `load(dump(s))` has equal: perfect-information string (`State.__str__`), every seat's observation string and tensor, `legal_actions()`, `current_player()`, `is_terminal()`, `returns()`, and, after applying any one legal action sequence, the same results as `s`. A Phase 2 test checks this on every boundary state of random games for every parameter combination, and on all shipped scenarios.
3. `dump` omits `seed`, `chance`, `history`, `expect` (meta), and writes `seats[i].pick` only in PK.
4. The hidden picks of §4.4 follow the observer: `dump(state)` is perfect-information; a seat-restricted dump (for a client) blanks other seats' `pick`, and such a dump is **not** loadable (S-CUT).
5. Mirroring a table: a human fills a scenario from the table (all zones are visible), loads it, and continues from the engine.

## 9. Worked examples

All use data ids from `data/components`. Counts that come from the data (winter requirements, prices, rewards) are the values at the time of writing; the example tests re-check them. Action ids are from ACTIONS.md §3.

### 9.1 Minimal round-2 fixture (hidden picks, then travel)
Two players, base side. Everything not listed is default. The test needs only that after both picks the phase is TR with P0 to move.
```json
{
  "format": 1,
  "description": "R-038/R-039: P0 and P1 pick areas 1 and 4; picks reveal, travel starts with P0.",
  "parameters": {"players": 2, "joinery": false},
  "round": 2,
  "phase": "PK",
  "seed": 7,
  "history": [2, 5],
  "expect": {"phase": "TR", "current_player": 0,
             "scenario_subset": {"seats": [{"cutting_area": 1}, {"cutting_area": 4}]}}
}
```
`PICK_AREA(0)` = 2 and `PICK_AREA(3)` = 5. At load, `current_player` = 0, no picks, path and areas sampled with seed 7. Resolved, the scenario also shows the 13 spot tokens, the laid-out cards, both winter cards and `placement_discarded` (one card, 2-player count, R-013).

### 9.2 Winter fixture (shortfall, loans first)
Round 4, year-1 winter, two players, clearing order P0, P1. P1 finishes the tasks phase; P0 is fed automatically; P1 is two food short and cannot pay $6 with $2.
```json
{
  "format": 1,
  "description": "R-071/R-073: shortfall with too little money; only TAKE_LOAN is legal.",
  "parameters": {"players": 2, "joinery": false, "easy_winter": false},
  "round": 4,
  "phase": "N4",
  "current_player": 1,
  "turn_order": [1, 0],
  "clearing_order": [0, 1],
  "path": null,
  "seats": [
    {"food": 7, "firewood_storage": {"firewood_log": 6}},
    {"money": 2, "food": 5, "firewood_storage": {"firewood_log": 6}}
  ],
  "supply": {"winter": {"year1": {"card": "winter_1_1", "half": "top"}}},
  "history": [0],
  "expect": {"phase": "SF", "current_player": 1, "legal_after": {"1": [1]},
             "scenario_subset": {"seats": [{"food": 0}, {}]}}
}
```
`DONE` (0) ends P1's N4 turn; feeding (N5) runs for P0 (pays the card's food, leaving 0) then reaches P1 with 2 food missing, due $6 > $2: SF, only `TAKE_LOAN` (1) legal (ACTIONS §5.10). The year-2 winter card is sampled.

### 9.3 Drying and selling fixture
Round 3 (fall year 1), selling phase W6, clearing order P1, P0. P1 holds a piece in each stage; drying 3 is non-empty, so it must sell.
```json
{
  "format": 1,
  "description": "R-058/R-059: wood in drying 3 forces a sale; DONE illegal until it is sold.",
  "parameters": {"players": 2, "joinery": false},
  "round": 3,
  "phase": "W6",
  "current_player": 1,
  "turn_order": [0, 1],
  "clearing_order": [1, 0],
  "seats": [
    {},
    {"sale": ["softwood_disk"],
     "drying": [{"firewood_log": 2}, {"softwood_log": 1}, {"firewood_log": 1}]}
  ],
  "history": [415],
  "expect": {"legal_after": {"0": [1, 398, 403, 411, 415], "1": [0, 1, 398, 403, 411]},
             "scenario_subset": {"seats": [{}, {"money": 8, "drying": [{}, {}, {}]}]}}
}
```
Legal at load: `SELL(z, p)` = 396 + 6z + p for the four non-empty zones, plus `TAKE_LOAN` (1); no `DONE`. `SELL(3, firewood_log)` = 415 pays the log's base price plus the third-area bonus (data), $3, so money 5 → 8, drying 3 empty and `DONE` becomes legal.

### 9.4 Joinery end-game fixture
Round 8 final sale, two players, joinery. The `FS` fixture is the state after R-081 steps 1 and 3 (the sale area and covered joinery below are credited on load; final dollars are the same). P0 has one joiner, so only joinery slot 1 sells (R-082); its river holds both firewood and softwood, so the river sale is a decision (R-081, A6).
```json
{
  "format": 1,
  "description": "R-081/R-082/R-083/R-085: covered joinery slot, river choice, one loan.",
  "parameters": {"players": 2, "joinery": true, "returns": "win_loss"},
  "round": 8,
  "phase": "FS",
  "current_player": 0,
  "turn_order": [0, 1],
  "clearing_order": [0, 1],
  "path": null,
  "seats": [
    {"money": 20, "loans": 1, "joiners": 1,
     "joinery": ["hardwood", "firewood", null],
     "sale": ["softwood_log"],
     "river": ["firewood_disk", "softwood_disk"],
     "tasks": [{"id": "task_01", "filled": [0, 1]}]},
    {"money": 30}
  ],
  "history": [439],
  "expect": {"terminal": true, "final_dollars": [39, 30], "returns": [1.0, -1.0],
             "legal_after": {"0": [1, 438, 439]}}
}
```
P0 holds 1 loan, so `TAKE_LOAN` (1, loans < 2) is also legal at the final sale (user answer 2026-11-04). P0: 20 + softwood log in the sale area (2) + hardwood in the covered joinery slot (5 + 3) + river softwood (4, chosen with `RIVER_SALE(1)` = 439) + task reward (12) − loan repayment (7) = 39. The firewood in the uncovered slot earns nothing. P1 ends with 30.

## 10. Open points (structure only; no rule guessed)

- **Q1 — RESOLVED 2026-11-05.** `FS` is the state after R-081 steps 1 and 3 (sale/drying areas and covered joinery sold, money already credited); only the river choices, tasks and loan repayment remain. Final dollars are unchanged. `dump` at `FS` shows that state (clearing_order = the year-2 fall order, `path` null). Choices are made in clearing order.
- **Q2 — Default cutting-area layout in later rounds** (§6.2) is a loader convention, not a rule: it reuses the setup layout in every round. If the user prefers "a plausible mid-game layout", it needs a decision.
- **Q3 — Task rewards and winter requirements in examples** are quoted from the data; if `cards.yaml` is re-transcribed the examples change.
- **Q4 — Drying over-capacity** is a warning (S-DRY) because the state does not record whether a hut or PW Drying caused it (R-059, R-096, R-101); an `over_capacity` flag would make it an error, at the cost of one more field.
- **Q5 — `tools/replay.py`** must accept a `scenario` key (§5.1) before scenario-based playtest reports can be replayed. Not a rule question.
- **Q6 — Mid-turn scenarios** (open huts window mid-turn, SF in progress) are deliberately unsupported (§1.3); persistence of such states is by `history` alone.
