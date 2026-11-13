# Lignum — Action Catalogue

**Status:** DRAFT (Phase 1 unit 9). Companion to `docs/RULES_SPEC.md` (R-IDs refer to it). If this file and the spec disagree, the spec wins and this file is fixed. **Action IDs freeze when Phase 2 closes** (PLAN D19; replays and playtest reports depend on them). Counts come from `data/components/*.yaml`; nothing here restates card values.

Design (PLAN D19, §5.4): atomic typed sub-decisions, one small vocabulary reused across phases, legal-action masks do the work. Joinery, Buildings, planned work, huts, Market and craftwork IDs are defined now and are simply **never legal until Phase 4** (PLAN Phase 2), except joinery wood placement (`PLACE_JOINERY`), which is legal in Phase 2 with `joinery=true`.

## 1. Conventions

1. **Seats** are numbered from 0. An action never names the acting seat: the acting seat is `current_player()`. Chance nodes use the chance player.
2. **Two ID spaces.** Decision IDs `0..439` and chance outcome IDs `0..102` are separate spaces (OPENSPIEL_NOTES: chance ids only need to be `< max_chance_outcomes`). The node type says which space an `apply_action` value is in; a replay file is a flat list and is decoded by replaying with the state. `num_distinct_actions` = **440**, `max_chance_outcomes` = **103**.
3. **Keep acting until DONE.** The acting seat keeps acting until it plays `DONE` (ends its current turn: a supply-path visit, or its turn in a wood-work or winter phase) or the turn ends automatically (below). `DONE` is legal only when nothing in the turn is still compulsory.
4. **Auto-ending turns.** A supply-path visit at a single-acquisition location ends automatically after its one acquisition (Fodder, Tasks, Planned work, Buildings, Joiner, token spots, clearing). Multi-unit locations (Bearer, Woodcutter, Sawyer) end only on an explicit `DONE`, even when nothing more can be acquired there (user decision 2026-11-05). A log-driving turn (R-049) ends when the river is empty. A trip (§5) ends automatically when its maximum is reached or no further piece/raft/food can be used. All other turns end only with `DONE`. Nodes where `DONE` is the only legal action are *not* removed from the vocabulary (whether the engine skips them is AMBIGUITY A2).
5. **Index conventions.**
   | Symbol | Range | Meaning |
   |---|---|---|
   | area *a* | 0..5 | cutting areas 1..6 (area *a* = printed number − 1) |
   | kind *k* | 0..2 | 0 firewood, 1 softwood, 2 hardwood |
   | piece *p* = 2*k* + *m* | 0..5 | *m* = 0 unmilled disk, 1 milled log: 0 FW disk, 1 FW log, 2 SW disk, 3 SW log, 4 HW disk, 5 HW log |
   | dest *d* | 0..1 | 0 sawing area, 1 sale area |
   | zone *z* | 0..5 | 0 sale area, 1 drying 1, 2 drying 2, 3 drying 3, 4 sawing area, 5 firewood storage. Only 0..3 are legal outside the winter shortfall sale (R-073) |
   | loc *l* | 1..22 | printed location number on the chosen side (R-032); 23 = forest clearing. On the base side (20 locations) 21, 22 are never legal; IDs are by printed number so side-specific meaning is resolved from `path.yaml` |
   | worker src *w* | 0..2 | 0 hired worker (bearer / woodcutter / sawyer as the phase needs; not in winter), 1 mill worker, 2 hut worker token |
   | task *t* | 0..18 | index in `cards.yaml` `tasks` order |
   | task slot *s* | 0..47 | flat index of requirement slots over all tasks in `cards.yaml` order (19 cards, 48 slots; 1–4 per card) |
   | building *b* | 0..9 | order in `buildings.yaml` |
   | PW card *c* | 0..9 | order in `planned_work.yaml` |
   | pair *n* | 0..2 | pair number 1, 2, 3 (target round = current + *n*+1, R-088) |
   | craftwork type *x* | 0..4 | 0 board, 1 shingle, 2 stake, 3 reed bundle, 4 joker (order of `setup.yaml` `craftwork_by_type`) |
   | hut area *h* | 0..2 | 0 drying, 1 food, 2 worker (R-100) |
   | equipment *e* | 0..2 | 0 raft, 1 sledge, 2 wagon (the three Trade-sellable types, R-090) |
6. **Canonicalisation (equal outcomes have one action sequence; exception: `HUT_TOKEN` picks are order-free, user ruling 2026-11-06).**
   - Identical pieces, tokens, workers and food are interchangeable, so no action names an individual item; actions name only kind/milledness/zone/slot.
   - Repetition (hire several bearers, move several pieces, sell several pieces) is repeated single-unit actions; the order of identical units is irrelevant by construction. Where two *different* actions could be interleaved to the same end state within one atomic purpose, the later must have a not-smaller ID than the earlier: this is the **non-decreasing rule**, applied to the hut build's `HUT_AREA` (§5.7); `HUT_TOKEN` picks are order-free (user ruling 2026-11-06).
   - Two identical requirements on one task card (same kind, milledness, drying) are filled lowest slot index first (`PLACE_TASK`).
   - Craftwork sets are named by (real type, size, jokers), so a set has one name (§5.6).
   - Sawing names the disk kind and the number of logs sent to the firewood storage (the rest go to the sale area): logs are identical, so there is no per-log ordering (R-054).
   - Chance outcomes that build an unordered set (laid-out tasks, PW cards, buildings, placement cards) are drawn one at a time; the resulting state depends on the set, not the draw order. Spot-by-spot path tokens are ordered (spots are distinguishable).
7. **Windows (C5).** *Loans*: `TAKE_LOAN` is legal at any decision node of the acting seat except SP and PK, while loans < 2 (§3), including at the final sale (FS; user answer 2026-11-04). *Hut/PW "start" actions* (`BUILD_HUT`, `HUT_*`, `TAKE_OVERTIME`-style round-start options) are legal in the **window**: from the start of each of the seat's supply-path visits and each wood-work / winter phase turn until the seat plays its first non-window, non-loan action of that turn. The window closes at the turn's first non-window, non-loan action, including in W6/W7 (user answer 2026-11-04, A1; §8).
8. **Legality always includes** affordability of the paid action counting nothing not yet taken: an action that needs $ is legal only if the seat has the $ (a loan must be taken first by an explicit `TAKE_LOAN`). `MOVE_TO` is the exception: its legality counts loans (R-040 item 4).

## 2. Chance outcomes (`max_chance_outcomes` = 103)

Probabilities depend on the state (remaining deck counts); zero-probability outcomes are omitted. IDs are unique across node types, so an outcome ID alone identifies its meaning.

| IDs | Name | Params | Node | Distribution | Rules |
|---|---|---|---|---|---|
| 0–19 | `AREAS3(r)` | *r* = lexicographic rank of the set of the cutting areas that start with 3 firewood, a *k*-subset of {0..5} with k = players = 2/3/4 (user answer 2026-11-05; the other areas start with 2); at most C(6,3) = 20 ranks | 1, setup | uniform over subsets | R-013, R-015, R-026(1) |
| 20–27 | `WINTER(c, h)` = 20 + 2*c* + *h* | card *c* ∈ 0..3 of the year's deck, visible half *h* ∈ 0..1 (0 = top, 1 = bottom in `cards.yaml`) | 2 (year 1), 3 (year 2), setup | uniform over unused *c*; *h* uniform if `easy_winter=false`, otherwise only the easier half is offered (R-117) | R-014, R-026(3), R-027, R-117 |
| 28–46 | `TASK_DRAW(t)` = 28 + *t* | task *t* | setup layout (players draws); each round refill (R-036) | uniform over undrawn task cards; no node when the deck is empty | R-014, R-036, R-062 |
| 47–56 | `PW_DRAW(c)` = 47 + *c* | PW card *c* | setup (players + 2 draws) | uniform over undrawn | R-014, R-026(2) |
| 57–75 | `PLACEMENT_DRAW(q)` = 57 + *q* | placement card *q* (order in `cards.yaml` `placement`) | each seasonal round 2.. (3/2/1 draws) | uniform over undrawn; discarded after use | R-037, R-062 |
| 76–85 | `BUILDING_DRAW(b)` = 76 + *b* | building *b* | setup, joinery=true only (8/7/6 draws) | uniform over undrawn | R-019, R-026(4) |
| 86–90 | `CRAFT_DRAW(x)` = 86 + *x* (*x* ∈ 0..4) | craftwork type drawn from the 18-token pile | 3 nodes per path fill (rounds 1, 2, 3, 5, 6, 7; round 1 in setup) | proportional to remaining pile counts (4/4/4/4/2 initially) | R-014, R-017, R-035, R-062 |
| 91–102 | `SPOT_TOKEN(y)` = 91 + *y* | *y* = 0 wagon, 1 raft, 2 saw, 3 sledge, 4 dollar, 5 food, 6 X-marker, 7 board, 8 shingle, 9 stake, 10 reed, 11 joker | 13 nodes per path fill, one per token spot in spot order 1..13 (after the 3 `CRAFT_DRAW` nodes) | proportional to the remaining multiset of the 13 tokens (10 equipment per `setup.yaml` + the 3 drawn craftwork) | R-017, R-023, R-035, R-062 |

**Order of chance nodes in setup** (R-012, R-026): `AREAS3`; `WINTER` year 1; `WINTER` year 2; `TASK_DRAW` × players; `PW_DRAW` × (players + 2); `BUILDING_DRAW` × (8/7/6, joinery only); `CRAFT_DRAW` × 3; `SPOT_TOKEN` × 13; then decisions `PICK_AREA` × players (§5.1). Setup chance nodes ≤ 1 + 2 + 4 + 6 + 8 + 3 + 13 = 37. Per seasonal round from round 2: `TASK_DRAW` (≤ 4), `CRAFT_DRAW` × 3, `SPOT_TOKEN` × 13, `PLACEMENT_DRAW` (1–3); all resolved at round start before any decision depends on them. Upper bound for `max_chance_nodes_in_history`: 37 + 5 × (4 + 16 + 3) = 152.

Not chance (no node): starting player (seat 0, R-016); foremen start (R-016); area food and wood effects of placement cards; the extra firewood (R-037(2)); player order for the next round (R-060).

## 3. Decision IDs (`num_distinct_actions` = 440)

Parameters decode as shown. "Phases" use the codes of §4.

| IDs | Name | Params | Meaning | Phases | Rules |
|---|---|---|---|---|---|
| 0 | `DONE` | – | end the current turn / decline an optional round-start option | see the §4 matrix (never in SP, PK, W2, FS) | R-045, R-040, R-064 |
| 1 | `TAKE_LOAN` | – | take the next loan: first $4 (card 4/7), second flips the card, +$4 (loans < 2) | any decision node of the acting seat except PK, SP | R-075, R-076, R-073 |
| 2–7 | `PICK_AREA(a)` = 2 + *a* | *a* | choose cutting area: setup token placement (public, must be a 3-firewood area with no token) and the hidden round pick | SP, PK | R-015, R-038 |
| 8–30 | `MOVE_TO(l)` = 7 + *l* | *l* 1..23 | move the foreman forward to location *l* (23 = clearing) | TR | R-040, R-044 |
| 31 | `HIRE_BEARER` | – | hire one bearer, $1 | TR at Bearers | R-041, R-043 |
| 32 | `HIRE_WOODCUTTER` | – | hire one woodcutter, $1 (cap: wood in the selected area, +2 with PW Cutting) | TR at Woodcutters | R-041, R-099 |
| 33 | `HIRE_SAWYER` | – | hire one sawyer: free if the seat has none this round, else the $1 sawyer (only once per round for all seats) | TR at Sawyers | R-025, R-041 |
| 34 | `BUY_FODDER` | – | buy one fodder, $1 ($0 with Field) onto the value-3 slot | TR at Fodder | R-041, R-043, R-115 |
| 35 | `BUY_SAW` | – | buy one saw, $1 (max 4 owned) | TR at Market | R-041, R-104 |
| 36 | `BUY_FOOD` | – | buy one food, $1 | TR at Market | R-041, R-104 |
| 37 | `SELL_FOOD` | – | sell one food, $1 (Marketstand) | TR at Market | R-108 |
| 38–56 | `TAKE_TASK(t)` = 38 + *t* | *t* | take face-up task *t*, $1 | TR at Tasks | R-041, R-043 |
| 57–66 | `CHOOSE_BUILDING(b)` = 57 + *b* | *b* | take building *b* from the supply (free) | TR at Buildings | R-106 |
| 67–96 | `PLAN_WORK(c, n)` = 67 + 3*c* + *n* | *c*, *n* | plan card *c* with pair *n*+1 (pays $1 per token on the card; $0 with Inn) | TR at PW | R-087, R-088 |
| 97–129 | `SELL_SET(x, s, j)` | see §5.6 | sell one craftwork set at the Market | TR at Market | R-104, R-105, R-091 |
| 130–132 | `SELL_EQUIP(e)` = 130 + *e* | *e* | sell one raft/sledge/wagon token, $2 (PW Trade target round) | TR at Market | R-090 |
| 133 | `TAKE_OVERTIME` | – | take 1 hardwood disk into the woodpile (PW Overtime target round) | RS, WS | R-097 |
| 134–135 | `BUILD_HUT(v)` = 134 + *v* | *v* 0 = 3 tokens, 1 = PW Hut Construction 2 tokens | start a hut build | window | R-100, R-095 |
| 136–140 | `HUT_TOKEN(x)` = 136 + *x* | *x* craftwork type | choose a craftwork token to flip, in any order (§5.7; user ruling 2026-11-06) | build in progress | R-100, R-095, R-110 |
| 141–143 | `HUT_AREA(h)` = 141 + *h* | *h* | assign a flipped token to hut area *h*, in non-decreasing *h* | build in progress | R-100 |
| 144–149 | `HUT_FOOD(a)` = 144 + *a* | *a* | spend a food hut token to take all food of free area *a* | window | R-102 |
| 150–167 | `HUT_DRY(z, p)` = 150 + 6*z* + *p* | *z* ∈ 0..2 (sale, drying 1, drying 2), *p* | spend a drying hut token: move one piece of type *p* from zone *z* one area right | window | R-101 |
| 168–173 | `MOVE_CUT_TOKEN(a)` = 168 + *a* | *a* | pay $1 and move own cutting token to token-free area *a* | W1, before the first wood action of the turn (also after `ASSIGN_WORKER`, not once wood is taken or the token moved); only for a seat sharing its area with an earlier seat, or whose area lost wood to another seat's PW Cutting outside take this round (user ruling 2026-11-06) | R-048, R-099 |
| 174–176 | `ASSIGN_WORKER(w)` = 174 + *w* | *w* | commit a worker of source *w* to the next action (§5.2) | W1, W3, W4, N1, N2, N3 | R-045, R-047, R-051, R-054, R-103 |
| 177–194 | `TAKE_WOOD(a, k)` = 177 + 3*a* + *k* | *a*, *k* | the assigned worker takes 1 piece of kind *k* from area *a* into the woodpile (own area; other area only with PW Cutting) | W1 | R-047, R-099 |
| 195–200 | `MOVE_WOOD(k, d)` = 195 + 2*k* + *d* | *k*, *d* | move 1 unmilled piece of kind *k* into area *d*: from the river (W2), or from the woodpile (W3, N2) | W2, W3, N2 | R-046, R-049, R-050..R-052, R-067 |
| 201–203 | `RIVER_MOVE(k)` = 201 + *k* | *k* | place 1 unmilled piece from the woodpile on the river (raft, or PW Log Driving) | W3 | R-053, R-098 |
| 204–209 | `WC_MOVE(k, d)` = 204 + 2*k* + *d* | *k*, *d* | Waterchannel: the placed river piece arrives at once into area *d* (once per transport phase) | W3 | R-107 |
| 210 | `USE_WAGON` | – | after `ASSIGN_WORKER`: spend a wagon and the fodder (value-2 slot first); trip of 1..3 or 1..2 pieces | W3 | R-052 |
| 211 | `USE_SLEDGE` | – | after `ASSIGN_WORKER`: spend a sledge; trip of up to 2 (+ up to 3 with food) pieces | N2 | R-067 |
| 212 | `USE_PW_LOGDRIVING` | – | start the PW Log Driving trip (no worker, no raft, up to 3 pieces) | W3 | R-098 |
| 213 | `END_TRIP` | – | end the current trip early (after at least 1 piece) | W3, N2 | R-050..R-053, R-067 |
| 214–226 | `SAW(k, n)` | *k*, *n*; see §5.3 | mill one disk of kind *k*; *n* logs to the firewood storage, the rest to the sale area; spends a saw (not for the PW Sawing second disk) | W4, N3 | R-054, R-068, R-092, R-094 |
| 227 | `WINTER_CUT` | – | after `ASSIGN_WORKER`: take winter firewood (2 for the first winter woodcutting action, 1 for each further) | N1 | R-066, R-103 |
| 228–230 | `TAKE_BONUS(k)` = 228 + *k* | *k* | take 1 unmilled disk of kind *k* from the supply (winter bonus); `DONE` declines | NB | R-065 |
| 231–374 | `PLACE_TASK(s, r)` = 231 + 3*s* + *r* | *s* task slot, *r* source | lock one piece onto requirement slot *s* (§5.4) | W5, N4 (year 2 only) | R-055..R-056, R-069, R-114 |
| 375–383 | `PLACE_JOINERY(k, q)` = 375 + 3*k* + *q* | *k* kind, *q* joinery slot 0..2 | place 1 milled piece of kind *k* from drying 2 into joinery slot *q* | W5, N4 (year 2 only) | R-057, R-069 |
| 384–395 | `STORE_PIECE(k, z)` = 384 + 4*k* + *z* | *k* kind, *z* ∈ 0..3 (sale, drying 1..3) | Small Storage Area: commit 1 milled piece | W5, N4 (round 8 only) | R-114 |
| 396–431 | `SELL(z, p)` = 396 + 6*z* + *p* | *z*, *p* | sell one piece of type *p* from zone *z* | W6, SF (winter shortfall) | R-058, R-073 |
| 432–437 | `DRY_ENTER(p)` = 432 + *p* | *p* | move one piece of type *p* from the sale area into drying 1 | W7 | R-059 |
| 438–439 | `RIVER_SALE(k)` = 438 + *k* | *k* ∈ 0..1 (firewood, softwood) | final sale: choose the river kind to sell | FS | R-081 |

IDs that are always illegal but kept for uniform indexing: pieces *p* = 4 (unmilled hardwood) in `SELL`, `DRY_ENTER`, `HUT_DRY` (unmilled hardwood never reaches sale or drying areas, R-046, R-058); `MOVE_WOOD(2, 1)`, `WC_MOVE(2, 1)` (unmilled hardwood to the sale area); `SELL(z, 4)`. Also `MOVE_TO(21)`, `MOVE_TO(22)` on the base side, and `TAKE_WOOD`/`MOVE_*`/`RIVER_MOVE` for kinds absent from the woodpile.

## 4. Phase machine and legality matrix

Phase codes:

| Code | Name | Rules |
|---|---|---|
| SC | setup chance run | R-012, R-026 |
| SP | setup `PICK_AREA`, public, in seat order | R-015 |
| RS | round start: income and fills (automatic or chance), then PW Overtime option (target-round seats only, §5.9) | R-034, R-035, R-079, R-097 |
| PK | hidden `PICK_AREA`, seat order, rounds 2.. | R-038 |
| TR | supply-path travel (one visit per turn) | R-040..R-044 |
| W1..W7 | woodcutting, log driving, transportation, sawing, tasks, selling, drying | R-045..R-059 |
| WS | winter start: PW Overtime option (rounds 4 and 8, before the bonus) | R-097 |
| NB | winter bonus | R-065 |
| N1..N6 | winter woodcutting, sledge transport, sawing, tasks, feeding, heating (N6 has no decision of its own: payment is automatic, shortfall via SF) | R-066..R-072 |
| SF | winter shortfall payment (inside N5 and N6) | R-073 |
| FS | final sale river choice | R-081 |

Note: there are no hut windows in N5 and N6 (feeding and heating are automatic). Hut actions of those turns are outcome-equivalent to the same actions in N4 or at the seat's last earlier window, so none is offered (Phase 1 close backlog F7).

Seat order: TR uses the starting-player order (R-040); W1..W7 use clearing order A, B, C, D (R-045); NB and N1..N6 use the preceding fall's clearing order (R-064); PK and SP use seat order 0..n−1 (SP: R-016); RS/WS option nodes use the starting-player (current turn) order (user answer 2026-11-04, A3). Phases W1..W7 and N1..N6 have one turn per seat.

Matrix (· = never legal, ● = legal, ○ = legal under condition in the "Notes" row).

| ID group | SP | PK | TR | W1 | W2 | W3 | W4 | W5 | W6 | W7 | RS/WS | NB | N1 | N2 | N3 | N4 | SF | FS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `DONE` | · | · | ○ | ● | · | ● | ● | ● | ○ | ● | ● | ● | ● | ● | ● | ● | ○ | · |
| `TAKE_LOAN` | · | · | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ○ | ● |
| `PICK_AREA` | ● | ● | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `MOVE_TO` | · | · | ● | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| hire / buy / take / choose / plan / sell-set / sell-equip / sell-food | · | · | ● | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `BUILD_HUT`, `HUT_*` (window) | · | · | ● | ● | ● | ● | ● | ● | ● | ● | · | · | ● | ● | ● | ● | · | · |
| `TAKE_OVERTIME` | · | · | · | · | · | · | · | · | · | · | ● | · | · | · | · | · | · | · |
| `MOVE_CUT_TOKEN` | · | · | · | ● | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `ASSIGN_WORKER` | · | · | · | ● | · | ● | ● | · | · | · | · | · | ● | ● | ● | · | · | · |
| `TAKE_WOOD` | · | · | · | ● | · | · | · | · | · | · | · | · | · | · | · | · | · | · |
| `MOVE_WOOD` | · | · | · | · | ● | ● | · | · | · | · | · | · | · | ● | · | · | · | · |
| `RIVER_MOVE`, `WC_MOVE`, `USE_WAGON`, `USE_PW_LOGDRIVING` | · | · | · | · | · | ● | · | · | · | · | · | · | · | · | · | · | · | · |
| `USE_SLEDGE` | · | · | · | · | · | · | · | · | · | · | · | · | · | ● | · | · | · | · |
| `END_TRIP` | · | · | · | · | · | ● | · | · | · | · | · | · | · | ● | · | · | · | · |
| `SAW` | · | · | · | · | · | · | ● | · | · | · | · | · | · | · | ● | · | · | · |
| `WINTER_CUT` | · | · | · | · | · | · | · | · | · | · | · | · | ● | · | · | · | · | · |
| `TAKE_BONUS` | · | · | · | · | · | · | · | · | · | · | · | ● | · | · | · | · | · | · |
| `PLACE_TASK`, `PLACE_JOINERY` | · | · | · | · | · | · | · | ● | · | · | · | · | · | · | · | ○ | · | · |
| `STORE_PIECE` | · | · | · | · | · | · | · | ● | · | · | · | · | · | · | · | ○ | · | · |
| `SELL` | · | · | · | · | · | · | · | · | ● | · | · | · | · | · | · | · | ● | · |
| `DRY_ENTER` | · | · | · | · | · | · | · | · | · | ● | · | · | · | · | · | · | · | · |
| `RIVER_SALE` | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ● |

Notes (conditions on ○ and gating):
- `DONE` in TR: only after at least one acquisition in the visit (R-040 item 4). In W6: only when drying 3 is empty (R-058). In SF: only when money ≥ due or no sellable piece remains (a seat covered by loans alone has `DONE` only, no `SELL`).
- `TAKE_LOAN` in SF: the only legal action while money < due and loans < 2 ("loans first", R-073). Not legal in SP or PK (no meaningful turn; AMBIGUITY A5). Never legal at chance nodes or at another seat's node.
- `TAKE_LOAN` in other phases is legal whenever loans < 2.
- `PLACE_TASK`/`PLACE_JOINERY`/`STORE_PIECE` in N4 only in round 8; `STORE_PIECE` is legal only while the building is empty and has never moved a piece (one piece per game, user answer 2026-11-04; R-114); in round 8 N4 a seat may commit a piece and move it to a task in that same phase, once and never in round 4; `PLACE_TASK` source 2 (stored piece) only in round 8 N4 (R-114).
- `ASSIGN_WORKER` is always exposed, even when only one worker source is legal (A4, user decision 2026-11-05); the mask contains only legal sources.
- "Window" actions (`BUILD_HUT`, `HUT_FOOD`, `HUT_DRY`) are legal only before the seat's first non-window, non-loan action of the turn; they are mutually repeatable inside the window. Which hut effects are legal also depends on tokens held (Phase 4).
- `HUT_DRY` is also legal in W6, W7 and in winter turns ("drying huts still work in winter", R-074). `HUT_FOOD` has no phase restriction beyond the window.
- `SELL` in SF uses zones 0..5 with the R-073 order constraint (zones 4, 5 only when zones 0..3 hold no sellable piece). It is legal only once step 3 has started: money < due with both loans taken, or a sale already made in this shortfall (optional extra sales then continue after the bill is covered). A seat covered by loans alone has only `DONE`.

### Phase machine sketch

```
SC ─► SP ─► [RS ─► PK ─► TR ─► W1 ─► W2 ─► W3 ─► W4 ─► W5 ─► W6 ─► W7]   rounds 1(no PK, no placement),2,3,5,6,7
                                                     └─ determine order, cleanup (automatic, R-060/R-061)
fall ─► WS ─► NB ─► N1 ─► N2 ─► N3 ─► N4 ─► N5 (feeding, SF) ─► N6 (heating, SF)   rounds 4, 8
round 8 ─► FS ─► TERMINAL (final sale, scoring, returns automatic)
```
Round 1 starts at TR (R-020). W2 is empty for a seat with an empty river. Automatic steps inside each transition: income (R-079), fills, food distribution (R-039), clearing order, cleanup, scoring.

## 5. Sub-step structures

### 5.1 Cutting-area picks (R-015, R-038)
`PICK_AREA(a)`. SP: public, seat order 0..n−1, only areas that start with 3 firewood and carry no token; a forced single choice is still recorded as an action (R-015 example). PK: hidden, seat order, any area including repeats; the observer hides other seats' PK actions until all have chosen; the reveal and R-039 food are automatic.

### 5.2 Worker assignment
`ASSIGN_WORKER(w)` commits one worker for the next action(s) of the phase: *w*=0 a hired worker of the phase's type (woodcutter in W1, bearer in W3, sawyer in W4; **never legal in N1/N2/N3**, source 0 does not exist in winter, R-064), 1 the mill worker (once per round across all phases, R-045, C6), 2 a hut worker token (spent when used, any phase including N1/N2/N3, R-103). Legal when the source has one available **and** the next action it would feed is possible (equipment present, wood available). The action is always exposed, even when only one source is legal (AMBIGUITY A4, implemented). The mask after `ASSIGN_WORKER` is the set of "first actions" of the phase:
- W1: `TAKE_WOOD(a, k)` (one piece; the worker is then used). PW Cutting lets *a* ≠ own area (R-099): at most 2 workers (hired woodcutters, mill worker, hut workers) take wood outside the own area, all from one other area; the first `TAKE_WOOD` outside the own area fixes that area for the turn.
- W3: bearer carry `MOVE_WOOD(k, d)` (ends the trip), `USE_WAGON`, or `RIVER_MOVE(k)` (raft trip).
- W4: `SAW(k, n)`.
- N1: `WINTER_CUT` (2 firewood if it is the seat's first winter woodcutting action, else 1, whoever performs it; order decides, R-066). N2: `USE_SLEDGE`. N3: `SAW(k, n)`.

### 5.3 Sawing (R-054, R-068, R-092, R-094)
`SAW(k, n)`: ID = 214 + `off`, `off` = *n* for *k*=0 (*n* 0..6; 0..4 normally, 5–6 only with PW Heating), 7 + *n* for *k*=1 (*n* 0..3), 11 + *n* for *k*=2 (*n* 0..1). A disk of kind *k* in the sawing area is replaced by 4 (6 with Heating) / 3 / 1 logs: *n* go to the firewood storage, the rest to the sale area. The saw is spent on the first disk of the worker; with PW Sawing the worker may mill a second disk with the same saw: immediately after a `SAW`, a `SAW` is legal without a new `ASSIGN_WORKER`, then the pair is closed (the mask offers `SAW` or the next `ASSIGN_WORKER` or `DONE`).

### 5.4 Task placement (R-055, R-056, R-114)
`PLACE_TASK(s, r)` for slot *s* of a held task. Source *r*: 0 = the area the requirement's drying stage names (stage 0: sale area; +1: drying 2; +2: drying 3); 1 = drying 1 (legal only for a stage-0 requirement); 2 = the Small Storage Area piece (round 8 only, milled kind equal to the requirement's kind, any stage). Exact kind, milledness and stage must match; the slot must be free; of two identical free requirements on one card the lower slot index must be filled first.

### 5.5 Joinery (R-057, R-069)
`PLACE_JOINERY(k, q)`: milled kind *k* from drying 2 into joinery slot *q* (0..2); legal if the joinery holds no piece of kind *k* and slot *q* is empty. The slot choice is the seat's (R-057, R-082).

### 5.6 Craftwork sets (R-105, R-091)
`SELL_SET(x, s, j)`: real type *x* ∈ 0..3, total size *s* ∈ 2..4, *j* jokers (0..2, at most the 2 jokers that exist), *s* − *j* ≥ 1 real tokens of type *x*. ID = 97 + 8*x* + `i`, `i` indexing `(s, j)` in the order (2,0), (2,1), (3,0), (3,1), (3,2), (4,0), (4,1), (4,2). ID 129 = `SELL_SET_JOKERS`: a set of exactly 2 jokers. Price by size *s* only ($2/$4/$6; $5/$8/$11 with PW Craftwork). Sold tokens leave the game.

### 5.7 Hut construction (R-100, R-095, R-110)
`BUILD_HUT(0)` (3 tokens) or `BUILD_HUT(1)` (PW, 2 tokens, only in a Hut Construction target round) opens a build. Then `HUT_TOKEN(x)` is played 3 (or 2) times in any order (the order of picks does not matter, user ruling 2026-11-06; only the final set must be valid), each a token the seat holds and that keeps a valid completion (stake, board, shingle once each with jokers as substitutes; reed only as the shingle with Small Workshop; the PW build takes any 2 of stake/board/shingle/joker, at most one reed as a shingle with the Workshop). Then `HUT_AREA(h)` the same number of times with non-decreasing *h*. The tokens are flipped when the last `HUT_AREA` is played; nothing is irrevocable earlier but no other action is legal during a build except `TAKE_LOAN`.

### 5.8 Transport trips (R-050..R-053, R-067, R-098, R-107)
`DONE` is legal at a W3 turn start and after `ASSIGN_WORKER` while no piece has moved (a seat need not transport any wood, or all of it), but never while a trip is open (at least one piece moved and the trip not ended); the only early exit is `END_TRIP` (user decision 2026-11-05). A trip start (`USE_WAGON`, `RIVER_MOVE`) is offered only when the woodpile is non-empty, so a seat is never left with a spent wagon or open trip and nothing movable (user decision 2026-11-05). `ASSIGN_WORKER` is always exposed (never auto-selected). In W1, `MOVE_CUT_TOKEN` stays legal after `ASSIGN_WORKER` until wood is taken or the token moved, and only a seat with an earlier seat in clearing order on the same area, or whose area lost wood this round to another seat's PW Cutting outside take (user ruling 2026-11-06), has it.
A **trip** starts with `ASSIGN_WORKER` followed by one of:
- `MOVE_WOOD(k, d)`: bearer trip, one piece; ends automatically.
- `USE_WAGON`: wagon + fodder; then `MOVE_WOOD(k, d)` × (1..cap, cap = 3 if fodder on slot 3 else 2; the slot-2 fodder is used first, R-052), then `END_TRIP` (automatic at cap). The fodder wears down regardless of pieces moved (O-U2-9).
- `RIVER_MOVE(k)` × m (each spends a raft, m ≥ 1), optionally one `WC_MOVE(k, d)` instead of one `RIVER_MOVE` when the seat has the Waterchannel and has not used it this phase, then `END_TRIP`.
- `USE_SLEDGE` (winter): `MOVE_WOOD(k, d)` × (1..5); pieces 3..5 each need 1 food (spent automatically); `END_TRIP` (automatic at 5).
`USE_PW_LOGDRIVING` starts a worker-free trip: `RIVER_MOVE(k)` × 1..3 (no raft spent), optionally the Waterchannel `WC_MOVE`, then `END_TRIP`. Hardwood disks are never moved with *d* = 1. Raft tokens, wagon tokens, fodder, sledge tokens and food are spent automatically; PW Food Supply income is automatic on each river placement (R-093).

### 5.9 Round-start options (R-097)
PW Overtime (step 3a of R-034): at RS (and WS for rounds 4 and 8, before the bonus), a seat whose Overtime target round it is gets one decision node: `TAKE_OVERTIME` or `DONE`. Order (user answer 2026-11-04, A3): the automatic start-of-round steps run first (joiner income R-079, fills and chance nodes), then the Overtime holders decide in starting-player (current turn) order, then the hidden picks. In RS/WS an Overtime holder's node is the only decision before the picks. `TAKE_OVERTIME` does not close the node by itself: `DONE` follows (as in A2). A PW Overtime planned for round 4 (winter year 1) is offered at WS like round 8, before the winter phases (user ruling 2026-11-06).

### 5.10 Winter payments (R-071..R-073)
- **Feeding (N5):** no choice when food suffices; the payment, the discard of surplus food (Storeroom keeps it in year 1) and the shortfall computation are automatic. If food is short, SF starts for *due* = $3 × missing.
- **Heating (N6):** fully automatic, no seat decision (user answer 2026-11-04, A8): the requirement is paid from the firewood storage in the fixed order cheapest milled kind first (firewood, then softwood, then hardwood), one piece each. The shortfall in pieces, if any, then starts SF.
- **SF (shortfall):** while money < due and loans < 2: only `TAKE_LOAN`. Then, if still short: `SELL(z, p)` (zones 0..3 first, zones 4..5 only when zones 0..3 have no sellable piece, R-073), `DONE` once money ≥ due or nothing is sellable (extra sales beyond *due* allowed; `DONE` also legal then). On `DONE` the seat pays min(money, due); any remainder is forgiven (D9).

### 5.11 Final sale (R-081)
Automatic: sale and drying areas, joinery (R-082), tasks, Office, loan repayment, returns. The only decision is `RIVER_SALE(k)`: offered to a seat only when its river holds both firewood and softwood; if it holds one sellable kind, that kind is sold automatically; hardwood has no value. `DONE` is not offered (user answer 2026-11-04, A6: the final sale is automatic). Order (user decision 2026-11-05): the sale/drying areas and covered joinery are sold first, then `RIVER_SALE` is offered, seat by seat in the year-2 fall clearing order (the `wint` order of round 8); a seat that chose sells only that kind.

## 6. Rule to action mapping

Rules whose decisions are actions:

| Rule | Action IDs |
|---|---|
| R-015 | `PICK_AREA` (2–7) |
| R-038 | `PICK_AREA` (2–7) |
| R-040 | `MOVE_TO` (8–30), `DONE` (0), `TAKE_LOAN` (1) |
| R-041 | `HIRE_BEARER` (31), `HIRE_WOODCUTTER` (32), `HIRE_SAWYER` (33), `BUY_FODDER` (34), `BUY_SAW` (35), `BUY_FOOD` (36), `TAKE_TASK` (38–56) |
| R-042 | `MOVE_TO` onto a token spot (acquisition is automatic) |
| R-044 | `MOVE_TO(23)` |
| R-045, R-103 | `ASSIGN_WORKER` (174–176) |
| R-047 | `TAKE_WOOD` (177–194) |
| R-048 | `MOVE_CUT_TOKEN` (168–173), `TAKE_LOAN` |
| R-049 | `MOVE_WOOD` (195–200) in W2 |
| R-050, R-051 | `MOVE_WOOD` in W3 |
| R-052 | `USE_WAGON` (210), `MOVE_WOOD`, `END_TRIP` (213) |
| R-053 | `RIVER_MOVE` (201–203), `END_TRIP` |
| R-054 | `SAW` (214–226) |
| R-055 | `PLACE_TASK` (231–374) |
| R-057 | `PLACE_JOINERY` (375–383) |
| R-058 | `SELL` (396–431), `DONE` |
| R-059 | `DRY_ENTER` (432–437), `DONE` |
| R-065 | `TAKE_BONUS` (228–230), `DONE` |
| R-066 | `ASSIGN_WORKER`, `WINTER_CUT` (227) |
| R-067 | `ASSIGN_WORKER`, `USE_SLEDGE` (211), `MOVE_WOOD`, `END_TRIP` |
| R-068 | `ASSIGN_WORKER`, `SAW` |
| R-069 | `PLACE_TASK`, `PLACE_JOINERY` in round 8 |
| R-073 | `TAKE_LOAN`, `SELL`, `DONE` |
| R-075, R-076 | `TAKE_LOAN` (1) |
| R-078 | `MOVE_TO` the Joiner location (acquisition automatic) |
| R-081 | `RIVER_SALE` (438–439) |
| R-087, R-088 | `PLAN_WORK` (67–96) |
| R-090 | `SELL_EQUIP` (130–132) |
| R-091, R-105 | `SELL_SET` (97–129) |
| R-092 | `SAW` (second disk without new saw) |
| R-094 | `SAW` firewood *n* up to 6 |
| R-095, R-100, R-110 | `BUILD_HUT` (134–135), `HUT_TOKEN` (136–140), `HUT_AREA` (141–143) |
| R-097 | `TAKE_OVERTIME` (133; step 3a of R-034) |
| R-098 | `USE_PW_LOGDRIVING` (212), `RIVER_MOVE`, `END_TRIP` |
| R-099 | `HIRE_WOODCUTTER` (+2 cap), `ASSIGN_WORKER` + `TAKE_WOOD` in one other area (at most 2 workers) |
| R-101 | `HUT_DRY` (150–167) |
| R-102 | `HUT_FOOD` (144–149) |
| R-104 | `BUY_SAW`, `BUY_FOOD`, `SELL_SET`, `SELL_EQUIP`, `SELL_FOOD` |
| R-106 | `CHOOSE_BUILDING` (57–66) |
| R-107 | `WC_MOVE` (204–209) |
| R-108 | `SELL_FOOD` (37); with it, `BUY_FOOD` and `SELL_FOOD` are mutually exclusive within one Market visit (once either is played, the other is illegal until the visit ends; user decision 2026-11-07). Rationale: with the Marketstand both prices are $1, so buy/sell could alternate forever in one visit; one canonical action sequence per outcome. |
| R-114 | `STORE_PIECE` (384–395; W5 and round 8 N4), `PLACE_TASK` source 2 |
| R-115 | `BUY_FODDER` price $0 (mask/price only, same ID) |
| Chance (R-014, R-017, R-019, R-026, R-027, R-035, R-036, R-037, R-062, R-117) | chance IDs 0–102 (§2) |

Rules with **no action** (pure automatic, structural or scoring), for unit 12's mapping test:
R-001 through R-014 (parameters, components, setup quantities; R-014 is covered by chance), R-016, R-018, R-020, R-021 through R-025, R-027, R-028 through R-032, R-033, R-034, R-035 (chance only), R-036 (chance only), R-037 (chance + automatic extra firewood), R-039, R-043, R-046, R-056, R-060, R-061, R-062 (chance), R-063, R-064, R-070, R-071 (feeding automatic; shortfall: R-073), R-072 (heating payment automatic in fixed order; shortfall: R-073), R-074, R-077, R-079, R-080, R-082 through R-086, R-089 (loss of an unusable plan is automatic), R-093 (income automatic), R-096 (capacity effect only), R-109, R-111, R-112, R-113, R-116, R-117 (chance), R-007/R-009 (supply limits are masks). R-089 and R-093 are enforced by the masks of the actions they refer to.

## 7. Totals and exclusions

| Space | Count |
|---|---|
| Decision IDs | **440** (0–439) |
| Chance outcomes | **103** (0–102) |

Range summary (decision IDs): 0–1 control and loan; 2–7 area picks; 8–30 moves; 31–37 hire/buy/sell singles; 38–66 task and building choices; 67–96 planned-work plans; 97–133 Market/PW sales and Overtime; 134–167 huts; 168–213 woodcutting and transport; 214–230 sawing and winter cut/bonus; 231–395 task, joinery and storage placement; 396–437 selling and drying; 438–439 final river sale.

Deliberately excluded from the vocabulary (no action): cutting-area food (automatic, R-039); path token take at token spots (automatic on entry); feeding and discards (automatic); player order, cleanup, scoring (automatic); the choice of which individual piece or token (identical items are indistinguishable); fodder slot choice (value-2 first is forced, R-052); early loan repayment (does not exist, R-077). The tactical variant (Phase 8) adds no actions here.

Phase-4 content (planned work, huts, the entire Market location including `BUY_SAW`/`BUY_FOOD`, Market sets and equipment sales, craftwork, Buildings, `STORE_PIECE`, `TAKE_OVERTIME`, `WC_MOVE`, `USE_PW_LOGDRIVING`) is defined above and is legal only from Phase 4. The planned-work, Buildings and Market locations are never legal `MOVE_TO` destinations in Phase 2 (user decision 2026-11-05); Buildings is legal from Phase 4 unit 9 (R-106: joinery=true, fewer than 2 owned, supply non-empty; `CHOOSE_BUILDING` free, visit auto-ends); joiner hire (Joiner location) and joiner income are Phase 2 (R-078, R-079), joinery wood placement in W5 (`PLACE_JOINERY`, R-057, R-082) is Phase 2 when `joinery=true` (user decision 2026-11-05), and only joiner-related parts that depend on Phase-4 content wait; with `joinery=false` no joiner, building, joinery or `CHOOSE_BUILDING` action is ever legal (R-002).

## 8. AMBIGUITIES

These are places where the spec does not fix the decision structure. A1, A3, A6, A8 are resolved by user answers of 2026-11-04 (recorded in PLAN §9). A2, A4, A5, A7, A9–A12 stay open but are structure-only: they affect how decisions are presented or skipped, not any game outcome or the ID space, and unit 10/12 may proceed on the stated assumption. Nothing was guessed.

- **A1 — Hut/PW window edges (R-100, C5). RESOLVED 2026-11-04.** The window closes at the turn's first non-window, non-loan action (as drafted), also in W6/W7 (after the first `SELL` or `DRY_ENTER`) and not between the parts of a trip.
- **A2 — Nodes with a single legal action.** (open, structure-only) R-045 says a seat may do nothing but still takes a turn. The spec does not say whether a seat with no legal action but `DONE` is skipped by the engine or must play `DONE`. R-015's example records a forced pick as an action, suggesting nothing is skipped; both are consistent with this vocabulary.
- **A2 (winter, decided 2026-11-05, unit 10).** Every winter phase NB and N1..N4 gives every seat an explicit node that ends in `DONE`, even when the seat has nothing it can do (no auto-skip); `TAKE_BONUS`, `WINTER_CUT` and a finished sledge trip do not end the turn by themselves. Round 8 joinery placement in N4 takes its source from R-057 (drying area 2 only) and round 8 task placement follows R-055. Feeding and heating (N5, N6) are automatic; SF is entered only when the seat's money is below the amount due, and a seat in SF with no loan left and nothing sellable still gets its `DONE` node.
- **A3 — Seat order of round-start options (R-097, R-034). RESOLVED 2026-11-04.** PW Overtime holders decide in starting-player (current turn) order, after the automatic start-of-round steps (joiner income, fills, chance nodes) and before the hidden picks (as drafted).
- **A4 — Worker source (R-045, C6, R-103).** (open, structure-only) The spec lets the seat use the mill worker, hired workers or hut tokens but does not say the seat chooses among them; automatic priority (hired, then mill, then hut) is dominated-choice-free in most cases but not proved. The vocabulary exposes the choice (`ASSIGN_WORKER`) and the engine may auto-select when only one source is legal. **Implemented (user decision 2026-11-05):** `ASSIGN_WORKER` is always exposed and the seat picks; index 0 (hired worker, the sawyer in W4) comes before index 1 (mill worker) when both are available.
- **A5 — Loans in hidden/setup picks (R-076).** (open, structure-only) "Any moment of its own turn": the spec does not say whether the setup placement and the hidden cutting-area pick count as turns in which a loan may be taken. Here a loan is not legal in SP/PK; no money matters there.
- **A6 — Final-sale choices (R-081, R-082). RESOLVED 2026-11-04.** The final sale is automatic; a choice (`RIVER_SALE`) only when both firewood and softwood are on the river; no decline action (as drafted).
- **A7 — Drying: timing of the forced advance versus `DRY_ENTER` (R-059).** (open, structure-only) The forced advance of drying areas 1 and 2 (right to left) must precede sale-area entries into drying 1, but the spec does not say whether it happens at the start of the seat's drying turn (after any window hut moves) or at `DONE`. The vocabulary assumes it applies when the window closes, before the first `DRY_ENTER` is offered. **Implemented (user decision 2026-11-05):** the advance is applied at the seat's first `DRY_ENTER` or at `DONE`, whichever comes first; until then the turn-boundary state still shows the pre-advance areas, and `DRY_ENTER` legality is computed as if drying 1 were already empty. Drying 3 entry beyond capacity by huts is described in R-059.
- **A8 — Heating payment choice (R-072). RESOLVED 2026-11-04.** CHANGED from the draft: heating is paid in a fixed automatic order with no seat decision, cheapest milled kind first (firewood, then softwood, then hardwood). `PAY_HEAT` was removed from the vocabulary and the decision IDs renumbered.
- **A9 — Hut build choices (R-100, R-095).** (open, structure-only) The spec does not say whether, when the seat holds more tokens than needed (e.g. a joker and a real shingle), it chooses which to flip. It is modelled as a choice (`HUT_TOKEN`, order-free by user ruling 2026-11-06; every held type that keeps a valid completion is offered), with the three areas also chosen (R-100).
- **A10 — Wagon trip piece count (R-052).** (open, structure-only) "Between 1 and the fodder's maximum pieces": the trip ends with `END_TRIP` or automatically at the maximum; the engine must not end a trip with zero pieces, which `USE_WAGON` followed by `END_TRIP` with no piece would otherwise be. `END_TRIP` is therefore illegal until at least one piece has moved.
- **A11 — PW Cutting extra woodcutter hires (R-099).** (open, structure-only) The spec does not state whether the +2 hires are mandatory-used or whether unmoved workers may be hired for nothing; the vocabulary hires one at a time within the cap and does not require the seat to use them.
- **A12 — Setup `WINTER` node under `easy_winter` (R-117).** (open, structure-only) The card draw is still chance (4 outcomes per deck) but the spec does not say whether the card choice stays chance when `easy_winter=true`; the vocabulary keeps it chance with the half forced.
