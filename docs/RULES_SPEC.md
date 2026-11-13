# Lignum — Rules Specification

**Status:** APPROVED

Contract between the rulebooks and the engine. Every rule behaviour in `lignum/` must trace to an entry here (CLAUDE.md). Only the user changes the Status line (D16).

This file is built in units. Unit 1 covers R-001 to R-032: parameters, components, setup, supply-path layout and the information boundary. Unit 2 covers R-033 to R-063: the spring/summer/fall round structure, the supply-path phase, the seven wood-work phases and end-of-round cleanup. Unit 3 covers R-064 to R-086: winter, loans, joiners, the final sale, scoring and returns. Unit 4 covers R-087 to R-117: planned work, huts, the Market and craftwork selling, the ten buildings and `easy_winter`. Its questions O-U4-1 to O-U4-12 are all resolved (see "Resolved questions").

## Sources and priority

1. *Lignum* second edition rulebook (`third_party/rules/lignum_rulebook.pdf`, "Base p.N") and the *Joinery and Buildings Expansion* rulebook (`joinery_expansion_rulebook.pdf`, "Exp p.N"). Capstone Games 2017.
2. Answers marked **Official** in the ludex.dev FAQ ("FAQ"), as captured in PLAN.md §3–§4.
3. The player aid, John Priebe v05.15.18 (`third_party/rules/player_aid.txt`, "Aid").
4. Photos in `third_party/rules/photos/` ("Photo"), and decisions D1–D23 and clarifications C1–C18 in PLAN.md.

Where a rulebook and PLAN.md differ, the rulebook wins unless a decision (D-number) or a user answer recorded in PLAN.md §9 or in this file's "Resolved questions" explicitly overrides it; each such case is cited in the entry.

## Conventions

- **Rule IDs** are `R-001` style, sequential, permanent. A retired rule keeps its ID and is marked RETIRED.
- Each entry gives: statement, source, parameters it depends on, and an example where setup is subtle.
- **Seats** are numbered from 0 everywhere (engine, tests, logs, examples) and labelled `P0`…`P3`. Never "Player 1" for seat 0.
- **Parameters:** `players` (2–4), `joinery` (true/false), `returns` (`win_loss` | `margin`), `easy_winter` (true/false). See R-001.
- **Card and path values** (task requirements, placement-card wood/food, winter requirements, planned work cards, building tiles, location numbers, capacities, token spots) live only in `data/components/*.yaml` (D12). This spec refers to them by name and gives numbers only where they are rulebook counts needed to state a rule. Where this spec and the data disagree, that is a bug to report.
- "Wood" means a disk or log; kinds are firewood, softwood, hardwood, each unmilled (disk) or milled (log). "$" is dollars.

---

## 1. Parameters

### R-001 — Game parameters
The game takes: `players` ∈ {2,3,4} (default 2); `joinery` ∈ {true,false} (default true); `returns` ∈ {`win_loss`,`margin`} (default `win_loss`); `easy_winter` ∈ {true,false} (default false). `returns` affects only the returns vector at game end; `easy_winter` affects only which half of each winter card is visible (R-027). Neither changes legal actions.
Source: D3, D4, D7, §5.2, C2.

### R-002 — joinery=false versus joinery=true
| | `joinery=false` (base game) | `joinery=true` |
|---|---|---|
| Board side | 20 locations + forest clearing | 22 locations + forest clearing (R-021, R-022) |
| Player-board extension | not used | one per player (R-010) |
| Joiners (6 yellow) | not used; location absent | used; one placed on the Joiner location each round |
| Buildings (10 tiles) | not used; location absent | used (R-019) |
| Tasks | placing wood on task cards only | task cards, plus joinery placement (R-057) |
| Setup differences | none beyond the above | R-019 |

All other rules, counts and setup are identical in both modes. When `joinery=false`, no action, location, component or scoring item belonging to Joinery or Buildings exists. The Joinery-only items include joiner income and feeding, the joinery final-sale bonus and building effects.
Source: D4; Base p.2–5; Exp p.1.

### R-003 — Player counts
2, 3 and 4 players are supported. Counts differ only in setup quantities (R-013) and the per-round quantities set out in R-013 that recur every round (path refill, placement cards drawn). All other rules are identical.
Source: D3, C2; Base p.17.

---

## 2. Components

### R-004 — Game board and phase markers
One game board with two sides: the 20-location side (`joinery=false`) and the 22-location side (`joinery=true`). It has six forest cutting areas numbered 1–6, a supply path ending in the forest clearing (slots A–D), a starting-player order track (positions 1–4), a phase track, an annual-course/planned-work planning area for year 1 and year 2 (one slot per season, winter included), two winter-card positions (year 1, year 2), and a hut-construction information strip. Two beige octagon markers (phase marker, season marker) are used.
Source: Base p.2–3; Photo `board_joinery_side.jpg`.

### R-005 — Cards
| Card | Count | Notes |
|---|---|---|
| Task | 19 | values in `data/components/` |
| Placement | 19 | Only some are used per game: 4p draws 3 per placement season, 3p draws 2, 2p draws 1 (R-013). The FAQ's "15" is the 4-player draw count (5 seasons × 3); user-confirmed 2026-11-04 |
| Winter | 8 | 4 per year (year 1 deck, year 2 deck); two printed halves each |
| Planned work (PW) | 10 | one each: Trade, Craftwork, Sawing, Food Supply, Heating Supply, Hut Construction, Drying, Overtime, Log Driving, Cutting |
| Loan | 4 | one per player; faces "4/7" and "16" (R-011, R-075) |
| Building (joinery=true only) | 10 | Waterchannel, Marketstand, Storeroom, Small Workshop, Drying Area Upgrade, Small Joinery, Inn, Field, Small Storage Area, Office |

Card contents are data (D12), not spec. Winter cards: the used half is the half left visible (R-027); a hidden half has no effect.
Source: Base p.3, p.18; Exp p.1, p.4; D12; Appendix A.

### R-006 — Tokens
- **Equipment tokens, 59:** 18 saw, 10 wagon, 12 raft, 6 sledge, 2 food, 1 dollar-coin, 2 X-marker (used only in a 2-player game), 8 amount marker (the 3/5 markers; may stand in for wood, food, fodder or equipment if a physical pile runs out, see R-009).
- **Craftwork tokens, 18** (counted in the rulebook's "77 equipment tokens"): 4 board, 4 shingle, 4 stake, 4 reed bundle, 2 joker.
- **Cutting-area tokens, 24:** 6 per player colour, numbered 1–6 on the reverse. The numbers are not used in the base game (Base p.4, step 6).
- **Planned-work tokens, 24:** 6 per player colour, two each of 1, 2, 3 (a "pair" is the two tokens with the same number).
- **Hut tokens:** three per constructed hut (R-100); no separate component count beyond the craftwork tokens that become huts.
Source: Base p.3.

### R-007 — Pawns and raw materials
- **Pawns:** 16 woodcutters, 10 bearers, 5 sawyers, 4 mill workers (one per player colour), 4 foremen (one per player colour), 4 player turn-order disks, 6 yellow joiners (joinery=true only).
- **Fodder:** 8 yellow wheat pieces.
- **Wood (disks = unmilled, logs = milled):** firewood 28 disks / 45 logs; softwood 12 disks / 25 logs; hardwood 10 disks / 10 logs. Wood and food are effectively unlimited (R-009).
- **Food:** 40 food cubes.
- **Money:** 80 coins totalling $275.
Source: Base p.3; C18.

### R-008 — Player components
Each player seat receives, in their colour: one sawmill board, one mill worker (in the worker area), one woodpile tile, six planned-work tokens, six cutting-area tokens, one foreman pawn, one turn-order disk, and $5 (loan cards come from the supply deck, R-075). With `joinery=true`, also one player-board extension (R-010).
The sawmill board has: fodder storage (capacity values by data), worker area, hut-effect area (three slots), food storage, river, equipment and craftwork areas, firewood storage (for heating), sawing area, sale area, and three drying areas (first, second, third; the third is the last drying area).
Source: Base p.3–4; Aid "Setup".

### R-009 — Supply limits
Wood, food, fodder and equipment tokens are unlimited: if the physical pieces run out (in practice only the 10 wagon tokens could), amount markers or substitutes stand in (FAQ Official; user decision). Workers (woodcutters, bearers, sawyers, mill workers), joiners, buildings and craftwork tokens are limited to the counts above. The limit of 4 saws owned per seat (R-041) is a holding limit, not a supply limit. Money is limited to the counts above at the table; this spec treats the bank as unlimited (see O-4).
Source: Base p.20 FAQ; FAQ (Official); C18.

### R-010 — Player-board extension (joinery=true)
One per player. It has three joiner spaces (filled left to right, permanent, maximum 3 joiners per player), three joinery wood slots (one under each joiner space; used for final-sale bonus wood, R-082) and two building spaces (maximum 2 buildings per player, permanent). It is not used when `joinery=false`.
Source: Exp p.1–2, p.4; Photo `player_board_extension.jpg`.

### R-011 — Loan cards
There are 4 loan cards in total, a deck in the general supply, "4/7 side" up; seats start with none (R-018) and take one when they take a first loan (R-075). The count of loans a player can hold is capped at 2.
Source: Base p.4 step 3, p.17.

---

## 3. Setup

### R-012 — Setup order
1. Each seat takes its components (R-008) and starts with $5.
2. Place the phase marker on position 1 (cutting) of the phase track and the season marker on year 1, spring.
3. Prepare supplies and decks (R-014).
4. Set the starting player and order (R-016).
5. Fill the supply path (R-017).
6. Place wood in the cutting areas and each player places a cutting-area token (R-015). The token placement (phase SP) is a decision sequence in starting-player order, so it follows the starting order (step 4) and the chance fill of the path (step 5); the order of steps 4 to 6 is a spec ordering and no rule outcome depends on it besides this (user answer 2026-11-04: SP follows the path fill).
7. Round 1 (spring, year 1) then begins at the supply-path phase; the "mark wood to be cut" and "select cutting area" steps are skipped in round 1 because setup handles them.

Setup draws are chance nodes (R-026).
Source: Base p.4–5; Aid "Setup" (rulebook order used; D10).

### R-013 — Setup quantities by player count
| | 4 players | 3 players | 2 players |
|---|---|---|---|
| Bearers on path | 10 | 8 | 6 |
| Woodcutters on path | 16 | 12 | 8 |
| Fodder on path | 2 | 2 | 1 |
| Sawyers at price $0 | 4 | 3 | 2 |
| Sawyers at price $1 | 1 | 1 | 1 |
| Equipment tokens on path | 10 | 10 | 10 |
| Craftwork tokens on path | 3 | 3 | 3 |
| X-markers among the 13 path tokens | 0 | 0 | 2 (the 2p mix has 1 wagon and 1 saw instead of 2 each, plus 2 X; see R-017) |
| Placement cards drawn each round from round 2 | 3 | 2 | 1 |
| Cutting areas with 3 firewood at setup | 4 | 3 | 2 |
| Cutting areas with 2 firewood at setup | 2 | 3 | 4 |
| Task cards laid out | 4 | 3 | 2 |
| PW cards laid out | 6 | 5 | 4 |
| Buildings drawn (joinery=true) | 8 | 7 | 6 |

The path quantities refill every round (R-017). The task, PW and building quantities are the opening layout; per-round refills are R-035 and R-036.
Source: Base p.4–5, p.17; Exp p.1; C2.

### R-014 — Supplies and decks
- The raw materials, food, fodder, coins, equipment tokens (face up by type) and the four loan cards (4/7 side up, as a deck) are placed in the general supply.
- The 18 craftwork tokens are shuffled face down into a pile.
- Task deck, PW deck and placement deck are each shuffled face down (separately by type).
- Winter cards are separated into year 1 and year 2 decks and shuffled. One card is drawn from each deck and pushed under the board marking so that exactly one half is visible (R-027). The other cards of those decks return to the box.
- Task cards equal to the number of players are drawn and laid out beside the Tasks location. PW cards equal to players + 2 are drawn and laid out beside the PW location, the rest return to the box.
- With `joinery=true`: buildings (R-019).
Which cards are drawn, in which order, and which winter half shows are chance outcomes (R-026).
Source: Base p.4 steps 3–5; Aid "Setup"; C2.

### R-015 — Initial cutting-area wood and cutting tokens (D10)
- The number of cutting areas that start with 3 firewood and those that start with 2 follows R-013. Which areas get 3 is a chance outcome (uniform over the possible subsets); the remaining areas get 2.
- Per R-013, 4p has four 3-firewood areas, 3p three, 2p two (the 4p and 3p counts equal the number of players; the 2p count also equals it, so every seat can take a distinct 3-wood area). The rulebook says players choose "any" areas to hold 3; D10 makes the choice a chance outcome instead.
- In starting-player order (R-016), each seat places one of its cutting-area tokens on a 3-firewood area that no token yet occupies. The choice is a decision (a public one: each seat sees earlier placements). So each player starts with a different 3-wood area, giving 3 wood to cut in round 1.
- Cutting-area token numbers play no role.
Source: Base p.4 step 6, p.17; Aid "Setup" is overridden (the aid puts 2 firewood in each area and places tokens randomly); D10.

Example (3 players): chance picks areas 1, 5, 6 for 3 firewood; areas 2, 3, 4 get 2. P0 chooses area 5, P1 chooses area 1, P2 is left with area 6 (a forced choice, still recorded).

### R-016 — Starting player and order
Seat 0 is the starting player (the rulebook's "player who last visited a forest"; D10 replaces this with a fixed seat, the lobby decides who sits there). Turn order is seat 0, 1, …, n−1. The turn-order disks go on starting-player positions 1…n in that order. Each foreman starts on location 0.
Source: Base p.5 step 6; Aid "Setup"; D10.

### R-017 — Initial supply-path fill
The supply path is filled as follows on the chosen side and refilled each round by the same recipe (round refill: R-035).
- Bearers (all of the R-013 count) on the Bearers location.
- Fodder (R-013) on the Fodder location.
- Woodcutters (R-013) on the Woodcutters location.
- Sawyers on the Sawyers location: R-013 at price $0, one at price $1.
- 10 equipment tokens + 3 craftwork tokens drawn from the supply form 13 tokens, which are mixed and placed face up, one per token spot (R-024). The 10 equipment tokens at 3 and 4 players: 2 wagon, 2 raft, 2 saw, 1 sledge, 1 dollar-coin, 2 food. At 2 players: 1 wagon, 2 raft, 1 saw, 1 sledge, 1 dollar-coin, 2 food, 2 X-marker; the X-marker spots cannot be used.
- Task cards: refilled to the laid-out count (R-013) at the beginning of each round.
- With `joinery=true`: 1 joiner on the Joiner location; the Buildings location holds the building supply (R-019).
The 3-player token mix is the same as for 4 players (the rulebook p.17 lists no change; user-confirmed 2026-11-04). Only 2 players change the mix, by the two X-markers above.

**Equipment is unlimited (R-009).** Equipment tokens used in play return to the general supply (Base p.11–12); equipment sold under the Trade planned work goes back to the supply (Base p.18). Craftwork tokens that are sold, or used to build huts, are removed from the game (FAQ Official). Because equipment is unlimited a refill never lacks a token, and the earlier random-draw fallback is not a rule (D23 in PLAN.md now says equipment is unlimited).
Source: Base p.5 step 1, p.17; C1, C2; Exp p.1.

Example (2 players): the 10 equipment tokens are 1 wagon, 2 rafts, 1 saw, 1 sledge, 1 coin, 2 food and 2 X, plus 3 craftwork; the 13 are shuffled and laid on the 13 token spots. Which two spots end up holding X-markers is random; a location marked X cannot be used (Base p.17; movement rules: R-040).

### R-018 — Starting holdings
Each seat starts with $5, an empty woodpile, no wood, no food, no fodder, no workers except the mill worker in its worker area, no equipment, no joiners, no buildings, no loans. Its foreman is on location 0 (R-016).
Source: Base p.4; Aid "Setup".

### R-019 — Joinery and Buildings setup (joinery=true)
- Use the 22-location side.
- Each player takes a player-board extension (R-010).
- All 6 yellow joiners are placed in the general supply; 1 joiner is placed on the Joiner location (R-017).
- Draw buildings at random from the 10 tiles: 2 players 6, 3 players 7, 4 players 8; they sit face up next to the board as the building supply. The undrawn tiles return to the box.
Source: Exp p.1; Aid "Setup"; C2.

### R-020 — Round 1 specifics
In round 1 there is no placement-card draw and no cutting-area selection step; each seat's cutting area is the one set in R-015. Task refill and path refill have been done by setup. The first action of the game is P0's supply-path move (movement rules: R-040).
Source: Base p.4–5; Aid "Setup".

---

## 4. The supply path

### R-021 — Base side (joinery=false): 20 locations
Locations in order, with the action at each. Numbers and capacities are data (`path.yaml`); this table fixes which acquisitions exist.
| Location | Acquisition | Capacity (foremen) |
|---|---|---|
| 4 | Bearers | 4 |
| 6 | Fodder | 2 |
| 8 | Planned work | 4 |
| 10 | Woodcutters | 4 |
| 13 | Tasks | 4 |
| 16 | Sawyers | 4 |
| 19 | Market | 4 |
| 1, 2, 3, 5, 7, 9, 11, 12, 14, 15, 17, 18, 20 | one equipment/craftwork token each | 1 |
The path ends at the forest clearing (A–D) after location 20.
Source: C1; Base p.2 image; Base p.5 step 1. The base side is the Joinery side without the Buildings and Joiner locations, with indexes shifted accordingly (user-confirmed 2026-11-04).

### R-022 — Joinery side (joinery=true): 22 locations
| Location | Acquisition | Capacity |
|---|---|---|
| 4 | Bearers | 4 |
| 6 | Fodder | 2 |
| 8 | Planned work | 4 |
| 10 | Woodcutters | 4 |
| 12 | Buildings | 2 |
| 14 | Tasks | 4 |
| 16 | Joiner | 1 |
| 18 | Sawyers | 4 |
| 21 | Market | 4 |
| 1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22 | one equipment/craftwork token each | 1 |
The path ends at the forest clearing after location 22.
Source: C1; Exp p.1; Photo `board_joinery_side.jpg`; Buildings capacity 2 from D20 (the expansion rulebook leaves it open).

### R-023 — Token spots
There are exactly 13 token spots on either side. At setup and each refill every spot holds exactly one token face up (R-017). A token spot has capacity 1.
Source: Base p.5 step 1; C1.

### R-024 — Forest clearing
After the last location comes the forest clearing with four ordered slots A, B, C, D (one per player at most; slot letters sort players into wood-work order). A foreman that reaches the clearing ends its supply-path moves for the round. Clearing order is set when a foreman arrives (A first). Details of arrival, cycling and player-order reset: R-040, R-044, R-060.
Source: Base p.2 (item c), p.5; C3.

### R-025 — Sawyer prices
The first sawyer taken by a player in a round is the free one ("price $0"); the sawyers priced $1 are taken as the optional extra (at most one player). At setup the counts are per R-013. Acquisition rules: R-041.
Source: Base p.17; Aid "Supply Path"; C3.

---

## 5. Chance and information

### R-026 — Chance nodes in setup
The following are chance events, drawn lazily as explicit chance nodes so the action history is the single source of truth (C2):
1. Which cutting areas receive 3 firewood (R-015).
2. The order of the task, PW and placement decks and which cards are laid out (R-014).
3. The year-1 and year-2 winter cards and which half of each is visible (R-027).
4. Which buildings are drawn (R-019).
5. The face-down shuffle of craftwork tokens and the placement of the 13 path tokens (R-017).
Each chance node is resolved before any decision depends on it. Per-round chance (refills, placement draws) is R-062.
Source: C2, D10, D5.

### R-027 — Winter card halves and `easy_winter`
Each winter card shows a harder and an easier half; the half pushed under the board is not in effect. With `easy_winter=false` the visible half of each card is a chance outcome (uniform). With `easy_winter=true` the easier half is visible on both cards. The easier half is the half with the lower food+heating sum (R-117).
Source: Base p.4 step 4, p.20 ("easier winter conditions" for a first game); C2 (house default: random).

### R-028 — Public information
These are public to all seats at all times: every seat's money, loans, workers, foreman locations, joiners and buildings, equipment and craftwork tokens held (craftwork is taken face up), the contents of each seat's woodpile, sawing, sale, drying, river, food and firewood storage, planned-work placements, tasks held and wood placed on them, huts, the visible winter half of both winter cards, task and PW cards laid out, the building supply, the contents of every cutting area, the path contents, turn order, clearing order, and all cutting-area picks once revealed (and every pick made in setup).
Source: D5, §5.2 ("Craftwork types are public"); Base: all of these are open on the table.

### R-029 — Private (hidden) information
The only hidden information is the seat's cutting-area pick between the moment it is chosen and the reveal that follows when all seats have chosen (round 2 onward). During the picking run each seat's choice is visible only to that seat; after all picks, all become public. Unrevealed deck order and the undrawn winter halves are not state: they are resolved by chance only when needed (R-026), so nothing hidden is stored.
Source: D5, D14; §5.2.

### R-030 — Observer contract
A seat's observation must not reveal another seat's unrevealed pick (R-029) in its string or tensor. The perfect-information view used for `State.__str__` includes all picks.
Source: D5, D14; `.claude/rules/engine.md`.

### R-031 — Determinism of setup
Given the parameters and the chance-node outcomes (R-026) and the recorded decisions (token placements, R-015), setup yields one unique initial state. Seat 0 is always the starting player (R-016).
Source: D10.

### R-032 — Terminology for locations
"Location N" means the supply-path location with that printed number on the chosen board side. The same name may denote different actions on the two sides (e.g. location 13 is the Tasks location on the base side and a token spot on the joinery side), so location numbers are always qualified by side in tests and logs; the spec and data name locations by purpose (Bearers, Fodder, …) where the side is unspecified.
Source: C1; Exp p.1.

---

## 6. Round structure (spring, summer, fall)

### R-033 — Calendar, rounds and markers
The game has 8 rounds: round 1 = spring year 1, 2 = summer year 1, 3 = fall year 1, 4 = winter year 1, 5 = spring year 2, 6 = summer year 2, 7 = fall year 2, 8 = winter year 2. Rounds 1–3 and 5–7 are **seasonal rounds** (spring, summer, fall) and follow R-034 to R-061. Rounds 4 and 8 are winter rounds, which are a different structure with their own phases (R-064 to R-074); they use neither the supply path nor placement cards. The season marker shows the current round on the annual-course area; the phase marker shows the current phase (R-045). After round 8 the game ends with the final sale (R-081).
Source: Base p.2 (Overview), p.5, p.15, p.16.

Example: after round 3 (fall, year 1) finishes its cleanup (R-061) the next round is the year-1 winter, not a spring. Round 5 is the first seasonal round of year 2, so it draws placement cards (R-037) and has hidden picks (R-038) like round 2.

### R-034 — Seasonal round sequence
Every seasonal round runs these steps in order. Steps marked † are skipped in round 1 because setup has done them (R-012, R-020).
1. **Joiner income** (joinery=true only; R-079, Exp p.3). Listed here only to fix its place: it happens at the start of the round, before the path is filled.
2. **Fill the supply path** (R-035) and **refill tasks** (R-036). Round 1 is filled by setup.
3. **Placement cards and extra firewood** (R-037). †
3a. **PW Overtime** (R-097): each seat holding Overtime for this round decides, in starting-player order.
4. **Cutting-area picks**, then reveal and food distribution (R-038, R-039). †
5. **Supply-path travel** (R-040 to R-044).
6. **Wood work**: seven phases in order (R-045 to R-059).
7. **Determine player order** (R-060).
8. **Cleanup** (R-061).
The step order places the placement draw (3) before the picks (4) so every seat sees the wood and food on offer in every area before choosing.
Source: Base p.5 ("Order of play in each season"), p.6, p.14; Aid "Board & Supply Path"; Exp p.3 (income timing).

### R-035 — Round-start supply-path fill
At the start of every seasonal round from round 2 (round 1 by setup, R-017) the path is brought to the R-017/R-013 recipe for the player count:
- **Workers.** All bearers, woodcutters and sawyers are back on the path after the last cleanup (R-061), so each location again holds the full R-013 count: bearers, woodcutters, sawyers (R-013 at price $0 plus one at $1).
- **Joiner** (joinery=true): the Joiner location holds exactly 1 joiner if the general supply still has one (only 1 joiner is available per round); otherwise it is empty.
- **Fodder:** the Fodder location is topped up to the R-013 count from the general supply (fodder is unlimited, R-009; fodder held by seats is not on the path).
- **Tokens.** The old path tokens were cleared in R-061. Ten equipment tokens and three craftwork tokens are drawn from the supply per R-017 (including the 2-player mix with X-markers), mixed, and placed face up one per token spot. The draw order and spot assignment are chance (R-062).
Craftwork tokens: the supply pile of 18 serves exactly 6 fills (rounds 1, 2, 3, 5, 6, 7 at 3 tokens each); leftover craftwork tokens on the path are removed from the game in cleanup, so the pile does not refill.
Source: Base p.5 step 1, p.14–15 ("Before the next round"); Aid "Board & Supply Path"; Exp p.1 (joiner); R-017.

Example (4 players, round 3, base side): at the end of round 2, P1 hired 3 bearers, 2 woodcutters and 1 sawyer, and P3 hired the free sawyer and the $1 sawyer; all of them go back to the path in cleanup. At round 3 start Bearers holds 10, Woodcutters 16 and Sawyers holds 5 (4 at $0, 1 at $1), regardless of who hired what.

### R-036 — Task refill
At the same step as R-035 the face-up task cards are refilled by drawing from the task deck until the laid-out count of R-013 (4/3/2 players) is reached. Cards that stay unclaimed remain face up. A task card, once taken, belongs to that seat (R-041) and is never discarded: completed tasks stay with their seat until the end-game scoring. If the task deck runs out, the row is not replenished and its slots stay empty.
Source: Base p.5 ("Draw task cards to refill the cards that were taken in the previous round"), p.4 step 5; Aid ("Refill: ... Tasks").

Example (4 players): at round 2 start two of the four face-up tasks were taken in round 1; the top two cards of the deck are turned face up, restoring four.

### R-037 — Placement cards and extra firewood
From round 2 on (every seasonal round except round 1), before the picks:
1. Draw placement cards from the shuffled placement deck: 4 players 3 cards, 3 players 2, 2 players 1 (R-013). Each card names, per cutting area, wood (kind and count) and food to add. Add exactly those pieces to those areas. The draws are chance nodes and the cards are discarded after use (never reshuffled; the 19-card deck is never exhausted, R-005).
2. After all drawn cards are applied, every cutting area that holds no wood receives 1 firewood (this follows the card draws, so an area given wood by a card gets no extra firewood). Food does not count as wood here.
Cutting-area contents are public (R-028). Wood and food in areas carry over between rounds (including through winter); only what players cut (R-047) or take (R-039) leaves them.
Source: Base p.5 step 2, p.17; Aid "Board & Forest"; C2.

Example (3 players, round 2): the two cards give area 1 one softwood plus one food, and area 6 two food. Before the draw, areas 3 and 6 had been cut empty in round 1. After the cards, areas 3 and 6 still hold no wood (area 6 holds only food), so each gets 1 firewood. Area 1 does not.

### R-038 — Secret cutting-area pick
From round 2 on, after R-037 and before travel, each seat chooses one of the six cutting areas (1–6) with its cutting-area tokens. D5 encodes this as a run of sequential decisions in seat order (P0, then P1, …, n−1), each hidden from the other seats until all have chosen (R-029, R-030). Any area may be chosen, including one chosen in an earlier round, an area with no wood, and an area another seat picks (several seats may share an area). The pick is final once made. When all seats have chosen, all picks are revealed together and each token is placed in its area; from then on picks are public. Because the picks are hidden, the order of the decisions has no strategic meaning (D5).
In round 1 there is no pick: each seat's area is the one placed in setup (R-015, R-020).
Source: Base p.6 step 3; Aid "Board & Forest"; D5, D10; §5.2.

Example (3 players, round 2): P0 picks area 4, P1 picks area 4, P2 picks area 2. P1's observation shows only P1's own choice until P2 has chosen; then all three are revealed: P0 and P1 share area 4, P2 is alone in area 2.

### R-039 — Reveal and food distribution
Immediately after the reveal (R-038), for every cutting area that holds at least one token:
- A seat that is **alone** in its area takes the area's entire food supply into its food storage. The rulebook says the seat "may immediately" take it; the spec makes this automatic and mandatory (a deliberate simplification; no seat would decline free food). The hut effect that takes a free area's food (R-102) is separate.
- Seats that **share** an area divide the food evenly (equal whole shares); pieces that cannot be divided remain in the area. If food < number of sharing seats, nobody receives any. Remaining food stays in the area across rounds, and may be taken in later rounds (C4; Base p.6 "Remaining supplies stay in the cutting area").
Food taken goes to the food storage on the sawmill board and is public (R-028). Food is only distributed at this step in the seasonal round, not later in the woodcutting phase.
Source: Base p.6 step 3, p.9; C4.

Example: area 2 holds 3 food; P0 and P1 share it. Each takes 1; the third food stays. If area 2 held only 1 food, neither would take it and it would stay. Area 5 holds 4 food and only P2 is there: P2 takes all 4.

---

## 7. The supply-path phase

### R-040 — Foreman movement
At the start of travel every foreman is on location 0. Turn order is the starting-player track (position 1 first; round 1: P0, P1, …). The foremen take turns cycling through that order; a foreman that has reached the forest clearing (R-044) is skipped. On its turn a foreman makes exactly one move, which must obey all of:
1. **Forward only.** The destination has a higher number than the foreman's current location, or is the forest clearing. A foreman never moves backwards, never stays, never passes: it must move.
2. **Skipping is allowed.** Any location ahead, however far, may be chosen.
3. **Capacity.** The destination has room: the number of foremen currently standing on it is below its capacity (R-021/R-022 and data; one foreman per token spot and Joiner, two at Fodder and Buildings, four elsewhere). A foreman occupies only the location it currently stands on; moving on frees the space.
4. **Activation.** The destination must be one where the foreman carries out at least one acquisition (R-041, R-042): taking a token, hiring a worker, buying and so on, within that location's limits and what the seat can pay for. "Can pay for" counts a loan the seat takes on the same turn (C3, C5, D20; loans: R-075, R-076). A location showing nothing available to this seat, or an X-marked location (2 players, R-017), cannot be entered. The move includes taking at least one acquisition; it cannot be an empty visit.
5. The clearing is the exception to 4 (R-044) and is always enterable.
After a move the turn passes to the next foreman in the cycle. Travel ends when every foreman is in the clearing. Because the clearing is always reachable, a foreman always has a legal move.
Source: Base p.6 step 4 and "IMPORTANT" box, p.5; Aid "Supply Path"; C3, D20.

Example (3 players, base side, round 2, starting-player track P2, P0, P1): P2 moves 0→4 and hires 2 bearers; P0 moves 0→4 (four foremen fit there) and hires 1; P1 moves 0→6 and buys fodder. The cycle continues with P2 again: P2 may go to any location above 4 with room (7, 8, 10, …) but not 5 if its token has already been taken, since nothing could be acquired there. P0, standing on 4, cannot move back or stay; P0 may enter 6 (capacity 2, P1 is there) only if a second fodder remains and P0 can pay $1 for it (R-041).

### R-041 — Acquisitions and costs at the path locations
Prices are paid to the bank. "Per visit" means per foreman move to that location.
| Location | Acquisition | Cost | Limits |
|---|---|---|---|
| Bearers | bearers | $1 each | any number up to those remaining on the location |
| Fodder | one fodder | $1 | at most 1 per seat per round; only if the seat's value-3 fodder slot is empty (R-043) |
| Woodcutters | woodcutters | $1 each | at most as many as the wood pieces now in the seat's selected cutting area (R-038); the mill worker is not counted |
| Sawyers | the free sawyer, then optionally the $1 sawyer | $0, then $1 | each seat may take one price-$0 sawyer per round; the $1 sawyer is taken in addition, only once per round by any seat; once it is hired nobody else may hire it. The $1 sawyer may only be taken in addition to the free sawyer in the same visit; a seat takes at most one free and one paid sawyer per round |
| Tasks | one face-up task card | $1 | one card per seat per round; it is placed next to the seat's sawmill board |
| Market | saws and food (buying) | $1 each | any number; a seat may own at most 4 saws (equipment area), counting any saw bought |
| Joiner (joinery) | one joiner | free | R-078 |
| Planned work | one plan on a laid-out card | $1 per token on the card | R-088 |
| Buildings (joinery) | one building | free | R-106 |
| Token spot | the token on the spot | free | R-042 |
Market selling (craftwork sets, Trade tokens, Marketstand food) is R-104/R-105; it counts as an acquisition for the activation test in R-040. Worker counts on a location run down as they are hired; a location with none left, or a fodder location with no fodder, cannot be activated by hiring.
Source: Base p.6–7 (Bearers, Fodder, Woodcutters, Sawyers, Market, Tasks), p.8 (placement of acquisitions); Aid "Supply Path"; C3, C7.

Example: P0 with $3 and a woodcutter area holding 3 wood visits Woodcutters: it may hire 1, 2 or 3 woodcutters (3 would use all its money); with $3 and an area holding 2 wood it may hire at most 2. P1 visits Sawyers with $0: it takes the free sawyer only. P2 visits Sawyers with $4: takes the free one and pays $1 for the second; P3, arriving later, takes only the free one.

### R-042 — Token spots
A token spot (13 per side, R-023) holds one face-up token; the foreman that enters takes it. Free of charge. The token goes to the seat's sawmill board:
- **Equipment tokens** (saw, wagon, raft, sledge) go to the equipment area and stay with the seat for later rounds. A seat holds at most 4 saws, so a spot holding a saw cannot be entered by a seat that already owns 4. There is no limit on other equipment.
- **Dollar coin token:** exchanged for one dollar from the bank; the token returns to the supply (R-017).
- **Food token:** exchanged for 1 food; the token returns to the supply.
- **Craftwork token:** goes to the craftwork area. The rulebook places it face down and allows hiding (Base p.8; Aid "may hide"); the spec overrides this and treats its type as public (it was face up on the path), per PLAN §5.2 ("Craftwork types are public") and R-028. Craftwork use (huts, selling) is R-100, R-105.
Once taken, the spot is empty and cannot be entered for the rest of the round.
Source: Base p.5 step 1, p.7, p.8; Aid "Supply Path"; C3, C13, C18.

Example: P1 moves onto a spot holding a saw while owning 4 saws: illegal. P1 moves onto a spot holding a sledge: legal, the sledge goes to P1's equipment area.

### R-043 — Where acquisitions go (sawmill board)
- **Hired workers** (bearers, woodcutters, sawyers) go to the worker area. They are usable in this round's wood work (R-045 on); unused ones return to the path in cleanup (R-061; C6).
- **Fodder** goes to the fodder storage on the slot valued 3. The storage has two slots, valued 3 and 2. A seat cannot buy fodder while its value-3 slot is occupied. It may buy while only the value-2 slot is occupied. It never holds two fodder of the same value. Fodder wears down by use (R-052).
- **Food** goes to the food storage.
- **Tasks** go next to the sawmill board, face up; the seat is the only one who may place wood on them (R-055).
- **Money** goes to the seat's supply.
Source: Base p.8 ("Where do you place your new acquisitions"), p.11; C7.

### R-044 — Forest clearing and end of travel
The forest clearing is the last "location" (after the last numbered one; slots A–D, R-024). It is enterable from any location including 0, regardless of what is on the path. It has no acquisition and no cost. The foreman that enters first stands on slot A, the second on B, the third on C, the fourth on D (with fewer than 4 players only the first n slots exist). Once there the foreman takes no more moves. When every foreman is in the clearing, travel is over and the wood-work phases begin; the clearing order A, B, C, D is the turn order in every wood-work phase (D6, R-045) and is also what sets the next round's starting-player order (R-060). Entering first therefore gives the first turn in each wood-work phase and the last turn in the next round's travel.
Source: Base p.9 ("End of supply of path"), p.14; C3, D6.

Example: P3 enters the clearing first (slot A), P1 second (B), P0 third (C), P2 fourth (D). Wood work runs P3, P1, P0, P2 in every phase.

---

## 8. Wood work

### R-045 — Wood-work framework
Wood work has seven phases, always in this order (the phase track):
1. Woodcutting (R-047, R-048)
2. Log driving, wood arrival (R-049)
3. Transportation (R-050 to R-053)
4. Sawing (R-054)
5. Tasks (R-055 to R-057)
6. Selling (R-058)
7. Drying (R-059)
The phase marker starts at 1 and moves to the next position only when every seat has finished the phase. In each phase each seat takes one turn in clearing order A, B, C, D (D6; the rulebook allows simultaneous play except for woodcutting, but this game is always sequential). A turn is a series of actions of that phase's type ending with the seat declaring itself done; a seat may do nothing, except that forced moves still apply (wood on the third drying area must be sold, R-058, and drying-area wood must advance, R-059). A seat's turn in a phase is finished before the next seat acts.
The **mill worker**: each seat's own mill worker may stand in for one worker of any kind (woodcutter, bearer, sawyer) — once per round (C6). Using it in one phase uses it up for the round; it does not replace the need for the matching equipment (a saw for sawing, a raft or wagon for transport). Loans may be taken at any moment of the seat's own turn, mid-turn included, in any season, never during another seat's turn (C5 as amended). Hut construction and hut effects keep the C5 windows (start of each of the seat's moves or wood-work turns; R-100 to R-103).
Source: Base p.9 (phase track, "VERY IMPORTANT"), p.10, p.12–14, p.20 ("first game" advice); D6, C5, C6.

### R-046 — Wood zones and legal moves
Wood is always in exactly one place. Wood of every kind is unmilled (disk) or milled (log) (R-007); only the sawing step changes this. All zones except drying areas are unlimited in size.
| From | To | When | Notes |
|---|---|---|---|
| cutting area | woodpile | woodcutting (R-047) | the only way into the woodpile in seasonal rounds |
| woodpile | sawing area or sale area | transportation (R-050) | the choice is made when the piece arrives and is final |
| woodpile | river | transportation, raft (R-053) | arrives next round's log driving |
| river | sawing area or sale area | log-driving phase (R-049) | same choice, final |
| sawing area (unmilled) | firewood storage or sale area (milled) | sawing (R-054) | the disk is replaced by logs |
| sale area | first drying area | drying (R-059) | |
| drying area n | drying area n+1 | drying (R-059) | |
| sale or drying area | task card | tasks (R-055) | locked |
| milled wood in drying area 2 | joinery | tasks, joinery=true (R-057) | locked |
| sale or drying area | bank (sold) | selling (R-058) | wood returns to supply |
| sale area or drying area n | next area to the right | hut drying effect (R-101) | ignores capacity |
| sale or drying area | Small Storage Area (one milled piece) | tasks, building (R-114) | locked; moved to a task in winter year 2 |
In seasonal rounds, wood in the **sawing area** cannot be sold, dried or placed on a task or in the joinery before it is milled and moved out (the only exception, the winter shortfall sale, is R-073); wood in the **sale area** can no longer be milled. Unmilled hardwood can only go to the sawing area, because it cannot be sold, dried or placed on a task unmilled (sale value none, R-058). In seasonal rounds, milled wood in the firewood storage is only for winter heating and cannot be sold or moved. Winter shortfall selling of wood "from the mill" (sawing area, firewood storage; Base p.16) and the final sale are R-073 and R-081. Planned-work effects (e.g. Overtime adding a hardwood to the woodpile, R-097) can add wood outside the table's transitions, and the Small Storage Area building (R-114) adds a zone. Wood on a task card or in the joinery is permanent.
Source: Base p.10 ("Please note" and "IMPORTANT"), p.12–14; Aid; C7, C8, C9.

### R-047 — Phase 1: Woodcutting
The woodcutters hired this round (R-041) and optionally the seat's mill worker (R-045) go into the cutting area where the seat's token stands. Each worker placed may take 1 wood piece from that area (of any kind the player chooses from what is there) into the woodpile. One worker takes at most one piece. Wood goes to the woodpile, not directly to the sawmill, and not into the food storage; food in the area is not taken in this phase. Workers beyond the number of wood pieces available take nothing and stay in the worker area (they return to the path in R-061). The woodpile is unlimited and wood in it stays indefinitely.
Seats act in clearing order; only shared areas make the order matter (R-048).
Source: Base p.9; Aid "Wood Work"; C4.

Example: P0 (slot A) has area 5 with firewood ×2 and softwood ×1, and brings 2 woodcutters and the mill worker. It may take up to 3 pieces, say 1 softwood and 2 firewood. The woodpile now holds those three disks and area 5 is empty.

### R-048 — Woodcutting in a shared cutting area
When two or more seats picked the same area, the seat earliest in clearing order cuts first, as in R-047. Each later seat (that has another seat's cutting token in its area when its turn comes) then chooses one of:
1. cut with its workers whatever wood remains in the area (R-047); or
2. pay $1 to the bank, move its own cutting token to a different area in which no other seat's cutting token stands, and cut there. The new area may hold no wood (C4, D20).
The first seat in clearing order cannot be displaced and has no move option because no earlier seat's token shares its area. The area a seat ended up in is the area it holds for the rest of the round (food in it is not taken). Any later sharing seat may pay and move regardless of how much wood remains or how many workers it has. The $1 is paid from money on hand; a seat short of $1 may take a loan (R-076) mid-turn, on its own turn to pay it (O-U2-10).
Source: Base p.9 (box "What happens, when 2 or more players..."); Aid "Wood Work"; C4, D20.

Example (clearing order P1, P0, P2): P0, P1 and P2 all picked area 4, holding 2 firewood. P1 cuts first, taking both with 2 woodcutters. P0 (next) finds area 4 empty of wood: it may cut nothing there, or pay $1 and move its token to area 3 (no tokens there) and cut what area 3 holds. P2 then has the same choice (P1's token is still in area 4); if it pays, area 3 is no longer free (it holds P0's token), so it must move to an area with no token, such as area 1.

### R-049 — Phase 2: Log driving, wood arrival
Each seat in clearing order receives all wood on its river that was placed there during an earlier round's transportation (R-053). Each arriving piece is placed in the sawing area or the sale area at the seat's choice (the choice is final), except that hardwood disks can only go to the sawing area. No worker or equipment is needed. In round 1 there is no wood on any river. Wood placed in the fall of year 1 stays on the river through winter, which has no log driving, and arrives in round 5; wood placed in the fall of year 2 never arrives.
Source: Base p.10, p.11 ("Please note"); C7.

Example: P0's river has 3 firewood disks and 1 hardwood disk from round 2. In round 3's log-driving phase P0 puts the hardwood in the sawing area, 2 firewood disks into the sale area and 1 into the sawing area.

### R-050 — Phase 3: Transportation (general)
Wood moves from the woodpile to the sawmill by three methods in seasonal rounds: bearer (R-051), wagon (R-052) and log driving by raft (R-053). (Sledge is winter-only, R-067.) A seat may combine methods and repeat them within its turn, as long as each use has the worker and equipment it needs; a worker or token is used at most once. For every piece moved by bearer or wagon, the seat decides at once: sawing area or sale area (hardwood disks only to the sawing area); the choice is final (R-046).
Wood that is not transported stays in the woodpile and may be carried in a later round.
Source: Base p.10; Aid "Wood Work"; C7.

### R-051 — Transport by bearer
A seat places one bearer (or the mill worker, R-045) on its woodpile and moves 1 wood piece from the woodpile to the sawing or sale area. Each bearer moves exactly one piece.
Source: Base p.10; C7.

Example: P2 has 5 woodpile pieces and 2 bearers: it moves up to 2 pieces this way, say one softwood to the sale area (for sale) and one hardwood to the sawing area. Three pieces remain.

### R-052 — Transport by wagon (with fodder)
Needs, together: one bearer (or the mill worker), one fodder in the seat's fodder storage, one wagon token. The bearer is placed on the woodpile, the wagon token is spent and returns to the supply, and the fodder moves wood: 3 pieces if the fodder is on slot 3, 2 pieces if on slot 2. After a trip with fodder valued 3 the fodder shifts to slot 2; after a trip with fodder valued 2 it is used up and returns to the supply. If the seat holds fodder in both slots, it must use the one valued 2 first (C7). A seat may use several wagons in a round, one bearer, one fodder and one wagon each. A trip moves between 1 and the fodder's maximum (3 or 2) pieces (at least 1); the fodder wears down the same way regardless of how many pieces move (O-U2-9). The moved pieces go to the sawing or sale area as in R-050.
Source: Base p.11 (wagon, "IMPORTANT"); Aid "Wood Work"; C7.

Example: P3 holds fodder on slot 3 and 1 wagon, 1 bearer. Wagon trip 1 moves 3 pieces; the fodder drops to slot 2. In round 3 a second wagon trip (new wagon token) moves only 2 pieces and the fodder is used up.

### R-053 — Log driving (raft) placement
A seat places one bearer (or the mill worker) on its woodpile and spends any number of raft tokens it holds; each raft moves 1 wood piece from the woodpile to the river area of its sawmill board. Spent raft tokens return to the general supply (R-017) at once. River wood stays there; it arrives at the next log-driving phase (R-049), exactly one round later when there is one, and cannot be sold, milled or moved before that. Only one bearer is needed regardless of how many rafts are used in the same action. There is no log driving in winter. The Waterchannel building (R-107) is an exception to the delay for one piece per transport phase. River wood left at the end of year 2's fall never arrives; one kind of it (the seat's choice if both firewood and softwood are present) is sold automatically at the final sale (R-081; Base p.11, p.17).
Source: Base p.11 ("Log Driving — wood placement"), p.10; C7.

Example: P0 uses 1 bearer and 4 rafts: 4 pieces move from the woodpile to the river; in the next round's phase 2 P0 distributes the 4 between sawing and sale. The rafts are gone.

### R-054 — Phase 4: Sawing
For every unmilled disk in a seat's sawing area that it wants to mill, the seat uses one sawyer (or the mill worker) and one saw token (the saw is spent and returns to the supply, R-017). The disk is replaced by logs of the same kind: hardwood 1, softwood 3, firewood 4. The logs must be placed at once, individually, in the firewood storage or in the sale area (any split, final). Disks not sawed this round stay in the sawing area. A seat can saw as many disks as it has both sawyers and saws for. A sawyer or saw is used for one disk only.
Source: Base p.12; Aid "Wood Work"; C8.

Example: P0 has 1 sawyer and 2 saws, and a softwood and a firewood disk in the sawing area. It saws the softwood: 1 sawyer + 1 saw spent; the 3 softwood logs go 1 to firewood storage and 2 to the sale area. The firewood disk stays; the second saw remains in its equipment area (no second sawyer).

### R-055 — Phase 5: Tasks
A seat may place wood from its **sale area** or **drying areas** on task cards it holds (R-043). Each task card shows required pieces (kind, milled or unmilled, and a drying bonus stage; values in data) and a reward. A piece fits a requirement only if it is exactly what is shown:
- kind and milledness match exactly;
- **drying stage matches exactly.** A requirement with no drying bonus accepts wood from the sale area or from the first drying area (stage 0). A requirement with +1 accepts wood only from the second drying area, and with +2 only from the third. Wood that is drier than required (over-dried) does not fit.
Pieces may be placed one by one over several rounds (partial completion is fine). A placed piece is locked on the card: never sold, moved or taken back (exception: the Small Storage Area piece in round 8, R-114). Wood in the sawing area, the woodpile and the firewood storage cannot be used. The seat may place on its own cards only. In the winter of year 1 no wood may be placed on tasks; the winter of year 2 allows it after sawing (R-069).
Source: Base p.12–13; Aid "Wood Work"; C9.

Example (illustrative card; real values are data): a held card requires 1 milled softwood at +1 and 1 milled firewood with no bonus. P0 moves 1 milled softwood from its second drying area onto the first slot. A milled softwood from the sale area would not fit, nor one from the third drying area. P0 moves 1 milled firewood from the sale area onto the second slot. The card is now full.

### R-056 — Task completion and reward
A task is **completed** when every requirement on the card is filled by a locked piece. A completed task pays its printed reward at the game end (final scoring: R-081, R-083; C9, C17). An unfinished task pays nothing, with no penalty, and its pieces are lost. A task card taken from the path is held by its seat until the game end whether completed or not (the Office building counts cards held, R-116).
Source: Base p.12–13 ("IMPORTANT You do not get the money for completed tasks until the end of the game"); Aid "END GAME"; C9, C17.

Example: a card requires two pieces and pays $17. P1 fills one piece in round 3 and the other in round 5. No money moves yet. At the game end P1 receives $17. A card with one of two pieces placed pays $0.

### R-057 — Joinery wood placement (joinery=true)
During phase 5 (Tasks), in addition to task cards, a seat may place milled wood on its joinery (player-board extension, R-010):
- the piece must be **milled** and must come from the **second drying area** (the "+1" area);
- the piece's kind must differ from every piece already in the joinery: at most one firewood, one softwood and one hardwood, so at most 3 pieces in total;
- several pieces may be placed in one turn if their kinds differ;
- the placing seat chooses which of the three joinery slots (R-010) each piece goes into (user decision); a placed piece is locked in its slot and never leaves the joinery;
- no joiner is needed to place.
At the final sale (R-082) a joinery piece may be sold only if its slot has a joiner (with the +3 bonus); a piece in a slot without a joiner may NOT be sold and earns nothing (Exp p.3: "if you have wood in the joinery without a joiner, you are not allowed to sell it!"). Winter year 2 placement: R-069.
Source: Exp p.3 ("Final Sale", rules a–e), Exp p.2; Aid "Wood Work"; C9, C16.

Example: P0 has milled firewood and milled hardwood in drying area 2. It may place both in one turn (different kinds). A second milled firewood in drying area 2 could not be added afterwards (the kind is already there).

### R-058 — Phase 6: Selling
In clearing order each seat may sell any or all wood in its **sale area** and its **three drying areas**, and only that wood. A piece is paid its base price plus the drying bonus of the area it stands in; the money goes to the seat and the wood returns to the supply. All wood on the **third** drying area must be sold now (it cannot dry further).
Base prices (board; also data): milled hardwood $5 (unmilled hardwood cannot be sold); unmilled softwood $4, milled softwood $2; unmilled firewood $3, milled firewood $1.
Bonuses: sale area +0, first drying area +0, second +1, third +2.
Source: Base p.13, p.14 (areas' labels); Aid "Wood Work".

Example: P0 sells 1 unmilled firewood from the sale area ($3) and 1 milled softwood from the second drying area ($2 + $1 = $3) and 2 milled firewood from the third drying area ($1 + $2 each = $6): total $12. (Any wood on the third drying area had to be sold, so it is part of the sale.)

### R-059 — Phase 7: Drying
Each seat's wood advances one area right: sale area → first drying area → second → third.
- Drying areas hold either **1 unmilled disk** or **up to 2 milled logs** (any kinds, mixed allowed), never a disk together with logs. The sale area is unlimited.
- All wood in a drying area moves to the next drying area together; it cannot be left behind (C10). By the end of phase 6 the third area is empty (R-058), so drying areas 1 and 2 always advance, and moves are resolved from right to left (the second area first, then the first, then the sale area) so wood does not chain (D20, C10).
- Wood in the sale area may enter the first drying area (the seat chooses which pieces, as many as fit under the capacity rule); the rest stays in the sale area.
- If a drying area is over capacity (through a hut, R-101, or planned work, R-096) all its wood must move. A drying hut used after the selling phase may put wood into the third area before this step; the second area's wood still advances into the third area over capacity (user answer 2026-11-04), and everything in the third area is sold in the next selling phase (R-058).
Source: Base p.14; Aid "Wood Work"; C10, D20; user answer 2026-11-04 (hut wood in area 3).

Example: before drying P0 has: sale area: 1 milled firewood, 1 milled softwood; area 1: 2 milled firewood; area 2: 1 unmilled softwood; area 3 empty. After drying: area 3 holds the unmilled softwood, area 2 the 2 milled firewood, and area 1 may take the milled firewood and the milled softwood (both fit; 2 logs). Had the sale area held a third log, only two could enter area 1 and the third would stay in the sale area.

---

## 9. End of round

### R-060 — Determine player order
After phase 7, the starting-player order for the next round is the **reverse** of the clearing order: the seat on the last clearing slot (D if 4 players) takes starting-player position 1, the second-to-last takes 2, and so on; the seat on A takes the last position. The turn-order disks move accordingly. This order is the turn order of the next seasonal round's travel. After a fall round (rounds 3, 7) the order is determined the same way. Winter has no supply path, so no new clearing order is formed: the **fall clearing order is retained as the turn order of the winter phases** (Base p.16; Aid; details R-064), and the starting order determined after fall is unchanged through winter and is the starting order of the next spring (user answer O-U2-7).
Source: Base p.14 step 6, p.16; Aid ("Reset Turn Order").

Example (4 players): clearing slots A=P2, B=P0, C=P3, D=P1. Next round's order: P1, P3, P0, P2.

### R-061 — Cleanup
After determine player order, and before the next round (also after fall, before winter):
1. All hired workers (bearers, woodcutters, sawyers), used or not, return to their locations on the path.
2. Every seat's mill worker returns to its worker area. Cutting-area tokens return to their owners and foremen are placed on location 0.
3. Equipment tokens still on the path return to the supply (usable in later fills). Craftwork tokens still on the path are removed from the game.
4. The phase marker returns to position 1; the season marker advances.
5. If the next round is seasonal it starts with R-034 step 1 (joiner income, then R-035). After a fall round the next round is winter (R-064).
Tokens, workers, wood, money, food, fodder, tasks, plans and locked pieces held by seats are unchanged by cleanup. Wood and food left in the cutting areas stay.
Source: Base p.14–15 ("Before the next round"); Aid "Board & Forest" ("Reset Workers"; "New Tokens: Clear any leftovers"); C6.

Example: P1 hired 3 woodcutters but cut 2 wood. All 3 go back to the Woodcutters location. Of 13 path tokens, 9 were taken: the 4 left (3 equipment, 1 craftwork) are returned to the supply and removed from the game respectively.

### R-062 — Chance nodes per seasonal round
In addition to R-026, each seasonal round contains these chance nodes, resolved before any decision depends on them: the 13 path tokens (R-035, rounds 2, 3, 5, 6, 7); the task cards turned face up (R-036); and the placement cards drawn (R-037). Winter cards are fixed at setup (R-014, R-026).
Source: C2.

### R-063 — Joinery-side differences in the seasonal round (joinery=true)
- R-034 step 1 (joiner income, R-079) exists; with joinery=false it does not.
- R-035: the Joiner location holds 1 joiner, if available. The Buildings location is not refilled here (R-106).
- R-040/R-041: the path has 22 locations (R-022), Joiner (capacity 1) and Buildings (capacity 2) locations; the Joiner acquisition is R-078 and Buildings is R-106, and their capacity is part of R-040.
- R-057: joinery placement exists in the Tasks phase.
- Nothing else in this section differs: R-036 to R-039, R-045 to R-056, R-058 to R-061 are identical in both modes.
Source: Exp p.1–3; D4.

---

## Forward references (superseded)
Planned work, huts, craftwork selling and buildings, deferred here by units 1 to 3, are R-087 to R-117 (unit 4). Still deferred: the tactical variant (Phase 8 of PLAN). Where a rule below says "later unit" for these items, read the R-ID given in unit 4.

## 10. Winter

### R-064 — Winter round: structure and turn order
Winter (rounds 4 and 8, R-033) is a round with its own phase track. It has no supply path, no path refill, no task refill, no placement cards, no cutting-area picks, no food distribution, no log driving, no selling phase, no drying phase and no joiner income. Nobody hires workers: each seat has only its own mill worker (C6; hut workers: R-103).
At the start of a winter round (4 or 8) the seats holding PW Overtime decide first (R-097; Overtime may be planned for round 4, ruling 2026-11-06), then the bonus (R-065) is taken, if the round has one; after the bonus the winter phases run in order: 1 Woodcutting (R-066), 2 Transportation by sledge (R-067), 3 Sawing (R-068), 4 Tasks (R-069), 5 Feeding (R-071), 6 Heating (R-072). The phase marker moves one position when every seat has finished the phase. In each of the six phases (Base p.16 orders only the phases; applying the same order to the bonus step is a spec choice) and in the bonus the seats act sequentially in the **clearing order of the preceding fall round** (A, B, C, D; D6, R-060). That order stays recorded after the foremen return to location 0 in cleanup (R-061 step 2). With `joinery=false` all winter rules are the same without joiners.
Source: Base p.16; Aid "Winter: wood work only"; C11, D6, R-060.

Example (4 players): the fall clearing slots were A=P2, B=P0, C=P3, D=P1. The winter bonus and every winter phase run P2, P0, P3, P1, although the starting-player order for next spring (set after fall, R-060) is P1, P3, P0, P2.

### R-065 — Winter bonus wood
Before phase 1, each seat may take 1 wood piece of its choice (firewood, softwood or hardwood disk, unmilled) from the general supply into its woodpile. This uses no worker.
Source: Base p.16 ("Bonus"); Aid "Winter"; C11; FAQ answer in Base p.20 (hardwood for tasks in 2-player games).

Example: P0 takes a hardwood disk. In winter year 1 it later has no sledge, so the disk stays in the woodpile into spring year 2 and can be carried by a bearer in round 5.

### R-066 — Winter phase 1: Woodcutting
A seat may place its mill worker on its woodpile and take **2 firewood** (unmilled disks) from the general supply into the woodpile. Only firewood may be taken this way. The first woodcutting action of the winter gives 2 firewood whoever performs it, the mill worker or a hut worker; each further woodcutting action (by hut workers) gives 1 firewood (FAQ Official; C11; hut workers: R-103). This does not depend on who sawed or transported. The mill worker may be used once per round for any one of woodcutting, sledge transport or sawing (C6; Base p.16 "you need to choose"). Taking nothing is allowed.
Source: Base p.16; Aid "Winter"; C6, C11; FAQ (Official: "How much firewood does winter woodcutting give with hut workers?").

Example: P1 uses its mill worker for woodcutting: +2 firewood disks in its woodpile; its mill worker is now spent for the winter (no sledge or sawing action for P1 unless a hut worker is available).

### R-067 — Winter phase 2: Transportation by sledge
Sledge is the only transport in winter (no bearer, wagon or log driving). A worker (the mill worker) is placed on the woodpile and a sledge token is spent (it returns to the supply): the trip moves **up to 2** wood pieces from the woodpile to the sawmill. The seat may additionally hand in food from its food storage, to the general supply: each food piece allows 1 more piece to move (Base p.11: "1 additional wood piece per food piece"), **up to 3 food per sledge**, so at most 5 pieces per sledge. The trip may move fewer than the maximum, even a single piece; food is charged only for pieces actually moved beyond the first 2 (moving 4 pieces costs 2 food). Each worker needs its own sledge. Moved pieces go to the sawing area or the sale area, final, with hardwood disks only to the sawing area (R-050, R-046). Food spent here reduces what is available at feeding (R-071), and a resulting shortfall is handled by R-073. The mill worker's once-per-round limit applies (C6).
Source: Base p.11 (sledge), p.16; Aid "Winter"; C7.

Example: P0 has 5 disks in its woodpile, a sledge and the mill worker free. It spends 3 food: capacity 2 + 3 = 5, all 5 move. Food storage drops by 3 and its sledge token returns to the supply. Had P0 moved only 4 pieces, it would spend 2 food.

### R-068 — Winter phase 3: Sawing
A seat may use its mill worker (a hut worker, R-103) and a saw token to mill 1 disk from its sawing area per worker, exactly as in R-054 (output into the firewood storage or the sale area, final). Two sawing actions need two workers and two saws. The mill worker's once-per-round limit applies (C6).
Source: Base p.16 (Sawing), p.12; Aid "Winter"; C8.

### R-069 — Winter phase 4: Tasks
In the winter of year 1 (round 4) no wood may be placed on task cards and none on the joinery. In the winter of year 2 (round 8), after sawing, a seat may place wood on its task cards under R-055 and in its joinery under R-057 (wood must come from the sale area or the drying areas as there; no drying has occurred in winter). Wood placed on a task card cannot be sold.
Source: Base p.16 (Tasks), p.13 (box "Please note: Winter!"); Exp p.3 (box "Please note: Winter!"); C9.

### R-070 — Winter cards, requirements and `easy_winter`
Round 4 uses the year-1 winter card and round 8 the year-2 card (R-014). Each card shows two printed halves of requirements; only the half left visible applies (R-027; `easy_winter=true` shows the easier half, otherwise the visible half is a chance outcome). A half gives the seat a **food requirement** and a **heating requirement** (milled wood pieces); both values are data. The requirement does not scale by player count (every card half shows one food value and one heating value). The easier half is the half with the lower food+heating sum (R-117). The requirements are the same for every seat; joiners add food (R-071).
Source: Base p.16 ("The two winter cards display the supplies the players need"), p.4 step 4; C2; R-014, R-027.

Example (illustrative, from the rulebook): year-1 card requires 6 food and 3 milled wood for heating. A seat with 2 joiners must pay 8 food that winter and 3 milled pieces.

### R-071 — Winter phase 5: Feeding
Each seat in clearing order must pay food equal to the visible half's food requirement plus 1 per joiner it owns (joinery=true; Exp p.2). The food comes from its food storage and returns to the general supply. If the seat has less food than due, it pays **$3 for each missing food** (shortfall rules R-073). After feeding, all food left in the food storage is returned to the supply: excess food cannot be kept (Base p.16). The Storeroom building changes this (R-109). The cutting-area food, craftwork and equipment are unaffected.
Source: Base p.16; Exp p.2; Aid "Winter: Feeding"; C11, C16.

Example (2 players, joinery=true): requirement 6; P0 has 2 joiners, so 8 food are due; P0 holds 9 food: pays 8, the last 1 is discarded. P1 has 1 joiner (7 due) and 4 food: missing 3 → $9 (R-073).

### R-072 — Winter phase 6: Heating
Each seat in clearing order pays wood equal to the visible half's heating requirement from its **firewood storage**: any milled pieces count (firewood, softwood, hardwood logs, 1 piece each; Base p.16 heating remark). The seat makes no choice of which pieces: payment is automatic in a fixed order, **cheapest milled kind first**: milled firewood, then milled softwood, then milled hardwood, taking pieces from the firewood storage (user answer 2026-11-04). Paid pieces return to the supply. Missing pieces cost **$3 each** (R-073). Surplus wood in the firewood storage is kept for the next winter (Base p.16; unlike food). Only the firewood storage is used to pay; unmilled wood and wood elsewhere cannot.
Source: Base p.16; Aid "Winter: Heating"; C11; user answer 2026-11-04 (fixed order).

Example: requirement 3; P2's firewood storage has 2 milled firewood and 1 milled softwood: 3 pieces paid, storage empty. P3 has 5 pieces (2 firewood, 2 softwood, 1 hardwood): pays 2 firewood and 1 softwood, keeps 1 softwood and 1 hardwood for the year-2 winter (they can be sold in a year-2 shortfall, R-073).

### R-073 — Winter shortfall: loans first, then selling, then forgiveness (D9)
Applies to each money shortfall in feeding (R-071) and heating (R-072); it is resolved right when that seat pays for the phase. Let *due* be $3 × missing units.
1. The seat pays from its money if it has at least *due*.
2. Otherwise it must take a loan (R-075) — **before** selling any wood (FAQ Official, Base p.20) — and again a second loan, one at a time, each only while its money is still below *due*; it may not take more than 2 loans in total, counting loans taken earlier in the game.
3. If it still has less than *due*, it must sell wood from its mill until its money reaches *due*; it may sell more than is needed, so as to have money left for the next season (Base p.16; user answer 2026-11-04, which overrides O-U3-3's "only what is due"). The order of the pieces sold is: first pieces in the **sale area and the drying areas** (seat's choice of pieces), and only once those are exhausted, pieces in the **sawing area and the firewood storage** (the same order binds the optional extra sales too; user answer 2026-11-04). Prices are those of R-058 (Base p.13 table): drying areas carry their usual bonus, while the sale area, the sawing area and the firewood storage carry none; unmilled disks sell at the unmilled price (unmilled hardwood cannot be sold). The woodpile, the river, task cards, the joinery and the Small Storage Area cannot be sold (R-046, R-055, R-057, R-114).
4. If after 2 loans and selling every sellable piece it still cannot pay, it pays all the money it has, the money is 0, and the remaining shortfall is forgiven (D9).
Money from loans or from sold pieces that overshoots *due* stays with the seat. This is the exception to R-046's restriction on selling wood from the sawing area or firewood storage; it applies only here.
Source: Base p.16, p.20 (FAQ, Official); Aid "Winter"; C11, D9; user answer 2026-11-04 (optional extra sales).

Example: due $9 (3 food missing), P0 has $2. It takes loan 1: $6, still below 9; loan 2: $10 ≥ 9; pays 9, keeps $1, two loans held.
Example (extra sales): due $6, P2 already holds 2 loans (taken earlier) and has $2, and holds a milled softwood in drying area 2 ($3), another in the sale area ($2) and 2 milled firewood in the firewood storage ($1 each). It sells the drying-area softwood and the sale-area softwood ($5; money $7, due covered). If it wants more money for next season it must also sell nothing from the storage until the sale and drying areas are empty: here they now are, so it may sell the 2 storage firewood too (+$2). Had it sold only one softwood and kept the other, the storage firewood could not be sold.
Example (D9): due $15, P1 has $0, has already taken both loans earlier, and can sell wood worth $3 in total. It sells it, pays $3, ends with $0, and the remaining $12 is forgiven.

### R-074 — End of winter
After heating, the winter round ends: the mill workers return to their worker areas, the phase marker returns to position 1 and the season marker advances. Wood in drying areas does not dry in winter (R-059 does not run), although a seat's drying hut tokens (R-101) can still move wood in winter, subject to the C5 windows (FAQ Official). After round 4 the next round is spring year 2 (R-033; it starts with R-034 step 1 and R-035; its starting-player order is R-060). After round 8 the game ends (R-081). Food storages are empty after feeding (R-071) unless the Storeroom says otherwise (R-109).
Source: Base p.16–17; C11.

---

## 11. Loans

### R-075 — Loan cards and amounts
Four loan cards form a deck in the supply, "4/7" side up (R-011, R-014); one card serves one seat (with at most 4 seats there is always a card). A seat's **first loan**: take a card, place it by its sawmill board, receive **$4** from the bank. A seat's **second loan**: flip its own card to the "16" side and receive another **$4**. A seat holds at most 2 loans (R-011). Loan cash is public (R-028). (R-008 was adjusted to match: seats start with no loan card, R-018.)
Source: Base p.17 (Loan Cards); Aid "Setup"; C12.

Example: P0 takes its first loan ($4, card on its 4/7 side) and later a second ($4 more, card flipped to 16): +$8, owes $16 at the end.

### R-076 — Loan timing
A seat may take a loan at any moment of its own turn, in any season, including mid-turn: on its supply-path moves, in its wood-work and winter phase turns, and when a payment is due. It may never take a loan on another seat's turn (C5 as amended; FAQ Official). A loan is voluntary except where R-073 forces it. A loan taken to be able to enter a location counts for R-040.
Source: Base p.17 ("anytime during your turn"); C5 (amended), C12.

### R-077 — Loan repayment (game end only)
Loans are repaid only at the end of the game: $7 for a seat with one loan (card on the 4/7 side), $16 for two (card flipped). No interest otherwise. The repayment is deducted at the end of scoring (R-083). There is no early repayment during the game (Base p.17).
Source: Base p.17 ("must be paid back"), Aid "Setup" and "END GAME"; C12, C17.

---

## 12. Joiners (joinery=true)

### R-078 — Joiner hire
A seat entering the Joiner location takes the joiner there and places it on its leftmost empty joiner space (R-010). Free. At most 1 joiner is available per round (R-035) and a seat holds at most 3; a seat with 3 joiners cannot enter the location (R-040 activation test). Joiners are permanent.
Source: Exp p.1–2; Aid "Supply Path"; C3.

### R-079 — Joiner income
At the start of each seasonal round (step 1 of R-034) each seat receives $1 per joiner it owns from the bank. A joiner hired in a round yields nothing in that round: its first income comes at the start of the next seasonal round. Winter pays no income. A joiner hired in fall year 1 first pays at the start of round 5; one hired in fall year 2 never pays.
Source: Exp p.3 ("Income"); C16.

Example: P0 hires its first joiner in round 2 (summer). Round 2 income: none from it. Round 3: +$1. Round 4 (winter): no income. Round 5: +$1. If P0 also hires a second joiner in round 3, round 5 pays $2.

### R-080 — Joiner effects summary
Joiners cause: income (R-079); +1 food each in winter feeding (R-071); eligibility of joinery slots for the final sale (R-082). Joinery wood placement is R-057 (in R-069 for winter). Nothing else.
Source: Exp p.2–3; C16.

---

## 13. End of game and scoring

### R-081 — Game end and final sale
After the heating phase of round 8 (R-072) the game ends with the final sale, the same for all seats:
1. **Sale and drying areas.** All wood remaining in the sale area and the three drying areas is sold at its R-058 price with the drying bonus of its area; unmilled hardwood has no value.
2. **River.** Each seat sells all wood of **one kind** on its river (firewood or softwood; if it has both it chooses one kind). The sale is automatic: there is no option to decline, and a choice exists only when both kinds are on the river (user answer 2026-11-04). River wood is unmilled and sells at the unmilled price of its kind (firewood $3, softwood $4) with no drying bonus; unmilled hardwood on the river has no sale value.
3. **Joinery** (R-082).
4. **Tasks.** Each completed task pays its printed reward (R-056).
No other wood has value: the woodpile, sawing area, firewood storage, task cards (uncompleted) are worth $0. No leftover item scores except those named here and in R-083 (food, fodder, equipment, craftwork, planned-work tokens: worth $0). Building effects on the final sale: Office (R-116) and Small Joinery (R-112).
Source: Base p.17 ("Game End – Final Sale"); Aid "END GAME"; C17, D7.

Example (excluding loans): P0 holds $20, a milled softwood in the sale area (+$2), 2 milled firewood in drying area 1 (+$2), an unmilled firewood in drying area 2 (+$3 +$1 = $4), a milled hardwood in drying area 3 (+$5 +$2 = $7): wood total $15. A completed task pays $17. Money after steps 1 and 4: $20 + 15 + 17 = $52.

### R-082 — Joinery in the final sale (joinery=true)
Each piece in the joinery is sold for the milled price of its kind plus **$3**, but only if the slot it occupies is attached to a joiner: with *j* joiners, a seat's joiner spaces filled left to right correspond to the first *j* joinery slots (R-010). A piece in a slot without a joiner cannot be sold and is worth nothing (Exp p.3). Because the placing seat chooses the slot (R-057), it controls which pieces sell. No drying bonus applies. Small Joinery changes the bonus (R-112).
Source: Exp p.3 (Final Sale; example 5+3, 1+3); C9; R-057.

Example: P1 has 1 joiner and joinery pieces: milled hardwood in slot 1, milled firewood in slot 2. Only slot 1 is covered: it sells for $5 + $3 = $8; the firewood earns $0. Had P1 placed the firewood first into slot 1 and the hardwood into slot 2, it would sell the firewood for $1 + $3 = $4.

### R-083 — Final dollars
A seat's **final dollars** = money held after the final sale (R-081, R-082) − loan repayment (R-077: $7 with one loan, $16 with two, $0 with none). The repayment is the last step. Final dollars may be negative (no floor); the formulas in R-085 and R-086 use signed final dollars.
Source: Base p.17; Aid "END GAME"; C12, C17.

Example: P0 ends with $52 and one loan: final dollars $45. P1 ends with $10 and two loans: $10 − 16 = −6.

### R-084 — Winner and ties (D8)
The seat with the most final dollars wins. There is no tiebreak: seats tied for the most share the win.
Source: Base p.17 ("Winner"); Aid; D8.

### R-085 — Returns, `returns=win_loss`
Terminal returns for *n* players (zero-sum). Let *k* be the number of winners (R-084).
- Sole winner (k=1): +1; every other seat −1/(n−1).
- k-way tie among the winners (1 ≤ k < n): each winner gets (n−k)/(k·(n−1)); each non-winner gets −1/(n−1).
- All n seats tied (k=n): 0 for everyone.
Returns are 0 before the game ends. Sum of returns is 0.
Source: D7.

Examples:
- 2 players, final dollars 59 vs 41: P0 +1, P1 −1.
- 3 players, 60, 60, 20 (k=2): winners (3−2)/(2·2) = +0.25 each, P2 −1/2 = −0.5.
- 4 players, 50, 50, 20, 10 (k=2): winners (4−2)/(2·3) = +1/3 each; others −1/3.
- 4 players, 30, 30, 30, 10 (k=3): winners (4−3)/(3·3) = +1/9 each; P3 −1/3.
- 3 players, 40, 40, 40: 0, 0, 0.

### R-086 — Returns, `returns=margin`
Seat *i*'s return is clip((final dollars of *i* − mean of the other seats' final dollars) / 50, −1, 1). Returns are 0 before the game ends. The clip is kept at ±1. The game declares its utility as GENERAL_SUM when `returns=margin` and as ZERO_SUM when `returns=win_loss` (user answer 2026-11-04). The unclipped margin is exactly zero-sum, but with the clip the returns are not exactly zero-sum for n ≥ 3 when a margin exceeds 50 (documented, user decision); for n = 2 they stay zero-sum.
Source: D7.

Examples:
- 2 players, 59 and 41: P0 (59−41)/50 = +0.36; P1 −0.36.
- 3 players, 60, 40, 20: P0 (60−30)/50 = +0.6; P1 (40−40)/50 = 0; P2 (20−50)/50 = −0.6.
- 4 players, 80, 60, 40, 20: P0 (80−40)/50 = +0.8; P1 (60−46.67)/50 ≈ +0.267; P2 (40−53.33)/50 ≈ −0.267; P3 (20−60)/50 = −0.8.
- 4 players, 100, 0, 0, 0: P0 (100−0)/50 = 2 → clipped to +1; the others (0−33.3)/50 = −0.667, so the sum is −1 (not zero, as documented above).

---

## 14. Planned work

### R-087 — Planned work: cards, plans and tokens
Ten planned work (PW) cards exist (R-005); players + 2 are laid out beside the PW location at setup (R-014) and stay laid out all game (no refill). Each card's printed seasons (the seasons in which it may be executed; which of spring, summer, fall, winter) and each card's effect are data (`data/components/*.yaml`, D12); the effects are specified in R-090 to R-099.
A seat owns six planned-work tokens: three **pairs**, one pair each numbered 1, 2 and 3 (R-006). A **plan** is a (seat, card, target round) triple recorded by placing one token of a pair on the chosen card and the other token of the pair on the target season slot of the planning area (R-004). A pair is used once and its tokens are never removed or reused (Base p.7 "Please note"), so a seat makes at most 3 plans in the game, and at most one per pair number. Plans are public (R-028). Several seats may plan the same card, and a seat may plan the same card more than once (different pairs; Base p.7 "IMPORTANT"). One seat may hold two plans landing on the same target season only if they are different cards, each resolving where its card indicates; a seat cannot plan the same card for the same target season twice, even with different pairs (user answer 2026-11-04, which overrides an earlier answer that same-card plans stack). So effects never stack by repeating a card.
Source: Base p.7 (Planned Work, "IMPORTANT" box), p.8, p.18; Aid "Supply Path"; C14.

### R-088 — Making a plan: cost, target season and wrap-around
A seat that enters the PW location (capacity 4, R-021/R-022) makes exactly one plan on that visit, so at most one plan per seat per round (Base p.7: "Every player may only plan one PW per round"). The plan:
1. Chooses a laid-out card and an unused pair numbered *n* ∈ {1,2,3}.
2. **Target round** = current round + *n*. The rounds are counted in the order of R-033, winter included as one round, so *n* seasons ahead may cross a winter and wrap from year 1 into year 2 (C14, D20). Example: planned in round 3 (fall year 1), *n*=1 targets round 4 (winter year 1); *n*=2 targets round 5 (spring year 2). A target round beyond 8 (a plan that would land after the second winter) is illegal and cannot be chosen (D20).
3. The target season must be one of the card's printed seasons (data), and the seat must not already hold a plan on this card for the same target round (user answer 2026-11-04). A card that is not printed for that season cannot be planned for it (Base p.7 "Not all PW may be planned for the winter round").
4. **Cost.** The seat pays $1 to the bank for every token already lying on the chosen card, whichever seat's and whichever of its own tokens (a plan on a card nobody has planned is free; with 2 tokens already there it costs $2). The seat's own tokens placed by this plan do not count. The card's tokens are counted at the moment of the visit. FAQ (Official, Base p.20): "You must pay 1 dollar for every token that is lying on the planned work card, even if you placed it there yourself." The Inn building makes this free (R-113).
Both tokens are placed once the cost is paid and they stay to the end of the game. The money may come from a loan taken on the same turn (R-076).
For R-040's activation test, the PW location can be entered only if the seat has not yet planned this round, has an unused pair, a laid-out card that can legally be planned (items 2 and 3, including the same-card rule) and the money for it (loans on the same turn counted).
Source: Base p.7–8 (Planned Work, "How much does planning cost?"); Base p.20 FAQ (Official); Aid "Supply Path"; C14, D20.

Example (4 players): P0 in round 2 (summer year 1) with $2 enters PW and chooses Sawing, which has 2 tokens on it (P1 and P2's earlier plans). With its pair 2 it targets round 4 (winter year 1); the card must be printed for winter or this choice is illegal. If it is, P0 pays $2, places one token on Sawing and the other on the winter year 1 slot. Pair 1 and pair 3 remain unused.

### R-089 — Executing and losing a plan
A plan may be used only in its target round, in the phases that its card affects (R-090 to R-099). The seat uses the plan only if it has the required components (wood, workers, equipment, craftwork) when the phase comes; the rulebook says if the preparations are missing "the PW is lost" (Base p.7). All PW effects are optional for the seat except where stated; an effect not used, or unusable, is lost without refund and the tokens stay. Plans on a given round by different seats are independent. A seat's effects use only its own plan (not another seat's plan on the same card or season).
Source: Base p.7 ("A PW may only be executed during the season (round) it was planned for"), p.8; Aid "Planned Work".

### R-090 — PW Trade
In the target round, when the seat is at the Market location (R-104), it may sell any number of its raft, sledge and wagon equipment tokens at $2 each. Sold tokens return to the general supply (Base p.18; R-017). Saws and other equipment cannot be sold.
Source: Base p.18; Aid "Planned Work"; C13.

### R-091 — PW Craftwork
In the target round, the seat's craftwork sets sold at the Market location (R-105) pay $5 (2 identical), $8 (3 identical), $11 (4 identical), instead of $2/$4/$6.
Source: Base p.18; Aid "Planned Work"; C13.

### R-092 — PW Sawing
In the target round's sawing phase (R-054), each sawyer (or mill worker, hut worker) used with one saw token may mill **2** disks instead of 1; the saw is spent once. A seat with k sawyers each with a saw can therefore mill up to 2k disks (the rulebook's 4, 6, 8 for 2, 3, 4 sawyers). The disks must be in the sawing area. Output per disk is as R-054.
Source: Base p.18; Aid "Planned Work"; C8.

Example: P0 (PW Sawing this round) has 1 sawyer, 1 saw, and 2 softwood disks in the sawing area: it mills both with that one sawyer and saw (6 logs placed individually in the firewood storage or sale area, R-054).

### R-093 — PW Food Supply
Like every other PW (R-089) it applies in its **target round**, not in the round it is planned and not in the rest of the year: nothing is paid in the round it is planned. In the target round, immediately when the seat places a wood piece onto its river, it receives 2 food from the general supply into its food storage per piece. Pieces counted: those placed by raft log driving (R-053), those placed by PW Log Driving without a raft (R-098), and a piece that arrives at once through the Waterchannel, which counts as a raft transport (R-107; user answers 2026-11-04). Base p.18 words it "in the planned year"; the user settled that it works like every other PW, in the season it is planned for. If the target round is winter there is no log driving, so nothing is paid.
Source: Base p.18; Aid "Planned Work"; user answers 2026-11-04.

Example: P0 plans Food Supply in round 1 with pair 2 (target round 3, fall year 1, a printed season). In round 1 and round 2 it places pieces on the river: no food. In round 3 it places 3 pieces with rafts: 6 food.

### R-094 — PW Heating Supply
In the target round's sawing phase, milling a firewood disk yields 6 milled firewood instead of 4 (the milling rules of R-054 are otherwise unchanged, including the placement into the firewood storage or sale area). Softwood and hardwood are unchanged.
Source: Base p.18; Aid "Planned Work".

### R-095 — PW Hut Construction
In the target round the seat may construct a hut (R-100) from **2** craftwork tokens instead of 3: any two of stake, board, shingle and joker, which need not be different types (so two boards are valid); the two tokens are flipped and each assigned to a hut area as in R-100. Reed bundles are excluded, except that with the Small Workshop (R-110) at most one reed bundle may stand as a shingle, as in R-110 (user answer 2026-11-04). It may be done more than once in the round, each hut using 2 tokens and giving 2 hut tokens. It follows the C5 windows (R-100).
Source: Base p.18; Aid "Planned Work"; user answer 2026-11-04.

Example: P0 (PW Hut Construction this round) holds 2 boards, 1 stake and 1 reed. It flips the 2 boards (2 hut tokens: say drying and worker) and, later in the round, the stake plus a joker if it had one. The reed stays unused.

### R-096 — PW Drying
In the target round the seat's first drying area holds twice the normal amount: 2 unmilled disks or 4 milled logs (any kinds), still never a disk mixed with logs. The wood placed there continues to dry in later rounds: a stack above the normal capacity is forced on, all together, into the second and third areas over their normal capacity (the destination capacity is ignored), and the third area is sold in the next selling phase as usual (R-058, R-059). The doubling applies from the start of the target round's wood work (capacity is checked at the drying phase, R-059; hut moves ignore capacity, R-101).
Source: Base p.18; Aid "Planned Work" ("IF drying space over capacity from PW or HUT, must move all wood right"); user answer 2026-11-04.

Example: P0 plans Drying in round 1 with pair 1 (target round 2). In round 2's drying phase it puts 4 milled logs in area 1. Round 3's drying phase moves all 4 to area 2 (normal capacity 2, over by 2). Round 4 is winter (no selling, no drying), so they stay there. In round 5 the selling phase finds area 3 empty, then drying moves all 4 into area 3. They must all be sold in round 6's selling phase.

### R-097 — PW Overtime
In the target round, after the automatic start-of-round steps (seasonal rounds: joiner income, path and task fill, placement cards and extra firewood; winter rounds 4 and 8: none), each seat holding Overtime for this round, in starting-player-track order (R-060, also in winter rounds), may take 1 hardwood disk from the general supply into its woodpile (optional). This precedes the hidden picks (R-038) and, in a winter round, the winter bonus (R-065), if the round has one. Overtime may be planned for round 4 (the card is printed for winter): the holder then gets the decision at the start of round 4, before the winter wood-work phases (ruling 2026-11-06). The disk is ordinary unmilled hardwood (R-046). Timing: user answer 2026-11-04. It is step 3a of R-034.
Source: Base p.18; Aid "Planned Work"; FAQ (Base p.20, hardwood and Overtime); user answer 2026-11-04.

Example: P0 has Overtime planned for round 8 (winter year 2). At the start of round 8 it takes a hardwood disk into its woodpile, then takes its winter bonus (R-065), a softwood disk. Both go through R-067 in winter phase 2 if it has a sledge. If the card is planned for round 4 instead, the same decision comes at the start of round 4; the winter bonus follows only if the round has one.

### R-098 — PW Log Driving
In the target round's transportation phase (R-050), the seat may place up to 3 wood pieces from its woodpile onto its river without a bearer (or mill worker) and without raft tokens. The seat may also use ordinary raft log driving the same turn (R-053). The pieces arrive in the next round's phase 2 (R-049); wood placed in round 7 never arrives; one kind of it (the seat's choice if both firewood and softwood are present) is sold automatically at the final sale (R-081). The pieces are placed on the river like any raft placement; it counts as raft transport for the Waterchannel (R-107) and as river placement for PW Food Supply (R-093; user answers 2026-11-04).
Source: Base p.18; Aid "Planned Work".

### R-099 — PW Cutting
In the target round's woodcutting phase (R-047, R-048) the seat gains two options:
1. At the Woodcutters location (R-041), it may hire up to **2 more** woodcutters than the wood pieces now in its selected cutting area (so the cap becomes wood in the area + 2).
2. In its woodcutting turn it may move up to 2 workers, any combination of woodcutters, the mill worker and hut workers (R-103; user answers 2026-11-04), into **one other** cutting area (both into the same area, not two different areas) and take wood there: one piece per worker moved, from the wood in that area. At most 2 workers take wood outside the seat's own area. It cannot take food. The seat's cutting token stays; its remaining workers cut in its own area as in R-047. Because phases are in clearing order, this can take wood a later seat was counting on.
An affected seat (one whose area has been reduced before its turn) may, as in R-048, cut what remains or pay $1 to move its token to a free area, meaning an area with no other seat's token. The area the PW seat's workers moved into counts as free if it has no token.
Source: Base p.18 ("Cutting"); Aid "Planned Work"; D20; user answer 2026-11-04 (hut workers count).

Example (clearing order P0, P1): P0 has PW Cutting this round, picked area 2 (1 firewood) and has 3 woodcutters (1 + 2 extra, R-041) and the mill worker. P1 picked area 5 (2 softwood). P0 cuts the firewood with one woodcutter, then moves 2 workers into area 5 and takes both softwood (no food). P1, whose turn comes next, finds area 5 empty of wood: it cuts nothing, or pays $1 and moves its token to a free area (R-048).

## 15. Huts

### R-100 — Hut construction
A seat holding one craftwork token of each of the three types stake, board and shingle (R-006) may construct 3 huts: the three tokens are flipped to their hut side and each is placed on one of the three hut-effect areas of the sawmill board (R-008; drying, food from a free cutting area, mill worker). A joker is any of the three (D20, C13). A reed bundle is never used, except that with the Small Workshop (R-110) one reed bundle may replace the shingle. The three tokens may go all on one area, one on each, or two on one area and one on another; the choice is made at construction and then fixed: hut tokens cannot be moved afterwards. A seat may build several sets (FAQ). The construction uses no worker (hut workers: R-103; spent at any point of the turn in which they work). It follows the C5 windows (start of each of the seat's supply-path moves and of each wood-work or winter phase turn; the rulebook says anytime in the seat's own turn, user-amended in C5). A window closes at the turn's first action other than a hut action or a loan, including in the selling and drying phases (user answer 2026-11-04), in any season including winter (FAQ Official: hut construction in winter is allowed and usable at once). Used craftwork tokens that are flipped stay as hut tokens until used, then are removed from the game (FAQ Official; R-017). A hut uses no joiner and exists with `joinery=false` too.
Source: Base p.15 ("Special Action – Hut Construction"); FAQ (Official, Base p.20); Aid "HUTS"; C5, C15, D20.

Example: P0 holds stake, board and a joker. It flips all three and places 2 on the drying area and 1 on the worker area. P1 holds stake, board and reed and has the Small Workshop: it may build with the reed as the shingle.

### R-101 — Hut effect: drying
Each hut token on the drying area may be spent, in the seat's windows (R-100), to move 1 wood piece (milled or unmilled) one area to the right in the drying areas, ignoring the capacity limits (the destination may exceed its capacity). A piece may be moved several times in a window with several tokens, advancing by one area per token. The spent token is removed from the game. An area left over its capacity by this effect must have all its wood advance in the next drying phase (R-059; Aid). Any piece may be moved from any area to the one on its right: a piece in the sale area may be moved into the first drying area, in addition to drying-to-drying moves (user answer 2026-11-04). A piece in the third area has no area to its right and cannot be moved. A drying area may thereby hold milled and unmilled wood together (FAQ Official). (The sale area and the three drying areas are all areas from which wood may be sold, R-058.) Drying huts still work in winter although wood does not dry then (R-074).
Source: Base p.15; Aid "HUTS"; FAQ (Official, drying huts may mix milled and unmilled wood); user answer 2026-11-04.

Example: P0 has a drying hut token, a milled softwood in the first drying area, and 2 milled logs in the second area. It spends the token: the softwood moves to the second area, which now holds 3 logs. In the next drying phase all 3 must move on together (R-059).

### R-102 — Hut effect: food from a cutting area
Each hut token on the food area may be spent, in the seat's windows (R-100), to take the entire food supply of one **free** cutting area (a cutting area with no other seat's cutting-area token; the seat's own area is allowed) into the seat's food storage. Several tokens may take food from several areas, or from the same area in turn (it empties at the first). The spent token is removed from the game. In winter no cutting-area tokens are on the board (R-061), so every area is free; a food hut may take food from any area (user answer 2026-11-04).
Source: Base p.15 (a free cutting area has no cutting-area token of another player); Aid "HUTS"; C15.

Example: P0 stands in area 3 with its own token; P1's token is in area 5; area 2 and 6 have no tokens. P0 holds 2 food hut tokens. Area 3 (own area), 2 and 6 are free; area 5 is not. P0 spends one token to take area 2's 3 food, and the other for area 6's food.

### R-103 — Hut effect: worker
Each hut token on the worker area is a single-use additional worker, usable in place of one woodcutter, bearer or sawyer; it still needs the equipment of the work it does (a saw to saw, a raft or wagon to transport). Hut workers also work in winter (R-064, R-066, R-067, R-068): they allow extra woodcutting (the first winter woodcutting action gives 2 firewood whether done by the mill worker or a hut worker, each further one 1 firewood: FAQ Official, R-066), sledge transport and sawing, each needing its own sledge or saw. Unlike the mill worker it can be used in any phase of any round and is not limited to once per round (C6; each token is a separate worker). The spent token is removed from the game. The token is spent when it is used, that is when it replaces a worker in an action, and only inside the C5 window of the effect (the seat's turn in the phase that needs the worker; user answer 2026-11-04). An unused hut worker token stays on the area.
Source: Base p.15; Aid "HUTS"; FAQ (Official, winter woodcutting with hut workers); C5, C6, C15; user answer 2026-11-04.

Example: in its transportation turn P0 has 1 bearer and a worker hut token, 2 rafts and 1 wagon with fodder. It uses the bearer for rafts and spends the hut token as a second bearer for the wagon trip. The token is gone; had it not been needed it would have stayed.

## 16. Market and craftwork

### R-104 — Market location
The Market (R-021, R-022; capacity 4) is a location where a seat may in any order and any number, within one visit: **buy** saws ($1 each, at most 4 saws owned, R-041) and food ($1 each) from the supply; **sell** craftwork sets (R-105); and, if it has the plan or building, sell equipment (PW Trade, R-090) or food (Marketstand, R-108). Money from sales may be used for purchases in the same visit. For R-040's activation test the seat must be able to do at least one of these: afford a purchase (a loan on the same turn counts, R-076) that is allowed (saws only if the seat owns fewer than 4), or hold something it can sell (a set with the base prices, Trade tokens in the planned round, food with Marketstand). Money buys are paid to the bank and sale proceeds come from it. Wood is never sold at the Market.
Source: Base p.7 (Market), p.18; Aid "Supply Path"; C3, C13.

Example: P0 owns 4 saws, has $0, no craftwork and no food-buying loan wanted: its only purchase left is food, so it may enter only by taking a loan (R-076) to buy food. P1 owns 3 saws, $0 and holds 2 boards: it may enter, sell the pair for $2 and buy a saw with that money in the same visit.

### R-105 — Craftwork sets and jokers
Craftwork tokens (R-006) are held in the craftwork area, public (R-042, R-028). At the Market a seat may sell any number of sets; each set is 2, 3 or 4 **identical** craftwork tokens (board, shingle, stake or reed bundle), paying $2, $4 or $6 respectively (R-091 for $5/$8/$11). A single token cannot be sold, and a set has at most 4 tokens. A joker counts as any craftwork token the seat chooses, for a set (D20, C13; Base p.7 "Joker tokens can be used like any craftwork token"): a set may be made up of identical tokens and jokers, or of jokers only. The sold tokens are removed from the game (FAQ Official; R-017); they are not returned to the supply. The seat chooses which tokens to sell and which to keep for huts (R-100).
Source: Base p.7 (Market, selling), p.8; FAQ (Official: sold craftwork tokens are removed); Aid "Market"; C13, D20.

Example: P0 holds 3 shingles, 1 stake and 1 joker. It may sell 3 shingles for $4, or 3 shingles + the joker as a 4-set for $6, or 2 shingles for $2. It cannot sell the stake alone; stake + joker is a 2-set for $2.

## 17. Buildings (joinery=true)

### R-106 — Buildings: acquisition
The building supply (R-019: 8, 7 or 6 tiles by player count; one of each of the 10 buildings can be among them) is the set of tiles available next to the board; it is not refilled during the game (R-063). By entering the Buildings location (capacity 2, R-022), a seat takes **1** building from the supply that is available and places it on an empty one of the two building spaces of its player-board extension (R-010). It is free. A seat may own at most 2 buildings, permanently (never removed or moved) and a visit gives exactly one building, so at most 1 per round. A building's effect is immediate. For R-040 activation the Buildings location can be entered only if the seat owns fewer than 2 buildings and the supply holds at least one. A taken building leaves the supply for good; no other seat can take it. Buildings are public (R-028). Not used with `joinery=false` (R-002).
Source: Exp p.1, p.4 ("How to build a building?"); Aid "Supply Path", "BUILDINGS"; C3, D20.

### R-107 — Building: Waterchannel
When a seat transports wood by raft (R-053), it may choose one of the pieces being placed on the river and have it arrive at once at the sawmill, without delay, into the sale area or the sawing area (the choice is final, hardwood disks only to the sawing area, R-046). It gives one piece per transportation phase of the seat, regardless of how many rafts it uses (user answer 2026-11-04). Wood put on the river by PW Log Driving (R-098), without a raft, counts as raft transport for it, still giving only one Waterchannel piece per transport phase (user answer 2026-11-04). The piece that arrives at once counts as a river placement for PW Food Supply (R-093).
Source: Exp p.4; Aid "BUILDINGS"; user answer 2026-11-04.

Example: P0 (Waterchannel) places 4 pieces on its river with 4 rafts. One of them, its choice, arrives at once into the sale area; the other 3 arrive next round's log driving. Using more rafts in the same phase gives no second piece.

### R-108 — Building: Marketstand
At the Market (R-104) the seat may sell food from its food storage at $1 per piece, any number. The food returns to the supply.
Source: Exp p.4; Aid; C13.

### R-109 — Building: Storeroom
Each winter's feeding requirement (R-071) is reduced by 1 food (never below 0) for the seat. In addition, after feeding in the **first** winter (round 4) the seat keeps its surplus food in its food storage for the second winter instead of returning it to the supply (R-071, R-074). After the second winter surplus has no value (R-081).
Source: Exp p.4; Aid "BUILDINGS".

Example: the year-1 card half needs 5 food; P0 has the Storeroom and 1 joiner, so it owes 5 + 1 − 1 = 5. It holds 8 food: it pays 5 and keeps 3 for the second winter, where the card needs 7: with Storeroom 7 + 1 − 1 = 7. Without the Storeroom the 3 would be discarded.

### R-110 — Building: Small Workshop
For hut construction (R-100, R-095) the seat may use one reed bundle token as the shingle. Reed bundles are used for nothing else except selling (R-105).
Source: Exp p.4; Aid "BUILDINGS".

### R-111 — Building: Drying Area Upgrade
Each of the seat's three drying areas may hold either 2 milled logs, 2 unmilled disks, or 1 milled log and 1 unmilled disk (any mix of two pieces), instead of 1 disk or 2 logs. The capacity applies to every drying area of the seat. With PW Drying (R-096) in the target round the first area holds 4 pieces, any mix of milled and unmilled (user answer 2026-11-04).
Source: Exp p.4; Aid "BUILDINGS".

### R-112 — Building: Small Joinery
At the final sale (R-082) the bonus for each joinery piece (one with a joiner) is $4 instead of $3: the sale price of the kind (R-058) plus $4. Pieces in a slot without a joiner still cannot be sold.
Source: Exp p.4; Aid "BUILDINGS"; C17.

### R-113 — Building: Inn
Planned work is free for the seat: R-088's cost is $0 even when tokens lie on the card. The seat's tokens are still placed and still count toward other seats' costs.
Source: Exp p.4; Aid "BUILDINGS".

### R-114 — Building: Small Storage Area
The building holds exactly **one** piece of milled wood; any milled kind is valid, milled firewood included. It follows the task-card rules for assignment (user answer 2026-11-04): the piece comes only from the sale area, and the drying areas also count as sale areas (R-058; wood may be sold from any of them), so from the sale area or any drying area at any drying stage, and only in a Tasks phase in which wood may be placed on task cards (R-055; none in winter year 1, R-069; round 8's Tasks phase is included, so the piece may be committed there too and moved to a task in that same phase, user answer 2026-11-04). It cannot come from the firewood storage, woodpile, sawing area or river. The piece is committed there until the **final task assignment**, the Tasks phase of the second winter (round 8, after sawing, R-069), when it may be placed on a free requirement space of one of the seat's task cards that asks for milled wood of its kind, counting as any dryness stage (the printed stage is ignored). It cannot fill a requirement for unmilled wood. A piece moved there is locked and counts for the task (R-056). A piece never moved is worth $0 and is never sold: not in the winter shortfall sale (R-073) and not in the final sale (R-081, R-082), which takes place after that Tasks phase per the rulebook. Before the final task assignment the only use of the piece is that move. The building is **one piece per game** (user answer 2026-11-04): once the stored piece has been moved to a task, the building cannot be refilled, and a building that has never moved a piece can be filled only while empty.
Source: Exp p.4; Aid "BUILDINGS"; user answers 2026-11-04.

Example: P0 has the Small Storage Area and, in round 6's Tasks phase, commits a milled hardwood from drying area 2. In round 8, in the Tasks phase after sawing, a task card has a free space for milled hardwood at +2; the stored piece fills it regardless of stage. A card whose free space needs milled softwood would not accept it. In round 8's Tasks phase P0 could also commit a milled piece from the sale area and move it to a task in that same phase. If no card has such a space, the piece scores $0. Milled wood sitting in the firewood storage could never have been placed on the building.

### R-115 — Building: Field
A fodder acquired at the Fodder location (R-041) costs $0 instead of $1; the other limits (one per seat per round, value-3 slot empty) are unchanged.
Source: Exp p.4; Aid "BUILDINGS".

### R-116 — Building: Office
At the final sale (R-081) the seat receives $1 for every task card it holds, completed or not (R-056). Counted before loan repayment (R-083).
Source: Exp p.4; Aid "END GAME"; C17.

## 18. `easy_winter`

### R-117 — `easy_winter` option
`easy_winter=true` shows the easier printed half of both winter cards (R-027) instead of drawing it at random (R-026); the visible half then stays public (R-028). With false each card's visible half is a uniform chance outcome. Nothing else differs, and `easy_winter` is not a legal-action parameter (R-001). The **easier half** of a card is the half with the lower sum of its food and heating values (user answer 2026-11-04). On the 8 transcribed cards the sums never tie (data; the halves are (food/heating) Y1: 7/6 = 13 against 5/7 = 12 gives 5/7; 6/3 = 9 against 6/5 = 11 gives 6/3; 5/5 = 10 against 7/4 = 11 gives 5/5; 5/4 = 9 against 6/6 = 12 gives 5/4; Y2: 7/7 = 14 against 9/8 = 17 gives 7/7; 9/9 = 18 against 10/7 = 17 gives 10/7; 8/6 = 14 against 7/10 = 17 gives 8/6; 6/8 = 14 against 8/9 = 17 gives 6/8). The rulebook recommends the easier winters for a first 4-player game (Base p.20).
Source: Base p.4 step 4, p.20; PLAN §7 Phase 1 task 4 (D20 applied); C2; winter card images (`third_party/art/winter/`, data); user answer 2026-11-04.

Example: with `easy_winter=true` the year-1 card that shows food 5/heating 5 against food 7/heating 4 shows its 5/5 half: feeding 5 food, heating 5 pieces.

## Forward references (unit 3)
Superseded by unit 4 (R-087 to R-117).

## Resolved questions (user, 2026-11-04)

- O-1 Placement cards: 19 in the deck; use per player count as in R-005 and R-013. Winter has no placement.
- O-2 Three-player path tokens: no change from the 4-player mix; only the 2-player game adds two X-markers (R-017).
- O-3 Base-side numbers: Joinery side minus Buildings and Joiner, indexes shifted (R-021).
- O-4 Coins: money is unlimited.
- O-5 Equipment shortage: none; equipment is unlimited (D23 as amended, R-017).
- Winter is its own round structure with its own phases (R-064 to R-074); it is not a variant of the seasonal rounds.
- O-U2-1 Task cards are never discarded; completed tasks stay with players until end-game scoring. If the task deck runs out the row is not replenished (R-036).
- O-U2-2 One food per food token (R-042).
- O-U2-3 Fodder on the path is topped up to the R-013 count (R-035).
- O-U2-4 Used wagon, saw, raft (and other spent) tokens return to the supply, as in the rulebook; used equipment is never removed, and equipment is unlimited (FAQ Official, user decision; R-009). The earlier D23 random-draw fallback is superseded. Sold equipment goes back to the supply (Base p.18); craftwork sold or used for huts is removed (FAQ Official) (R-017, R-042, R-053, R-054).
- O-U2-5 Any later sharing seat may pay $1 and move, regardless of remaining wood or workers (R-048).
- O-U2-6 The $1 sawyer may only be taken in addition to a free sawyer; at most one free and one paid per seat per round (R-041).
- O-U2-7 The order set after fall carries through winter into the next spring (R-060).
- O-U2-8 Sold equipment goes back to the supply (Base p.18); craftwork sold or used for huts is removed (FAQ Official) (R-017).
- O-U2-9 A wagon trip may move 1 to the fodder's maximum pieces (at least 1); the fodder wears down regardless of how many move (R-052).
- C5 amended by the user: loans may be taken on the seat's own turn whenever it wants, in any season, including mid-turn, never during another seat's turn (FAQ Official and the rulebook Loan Cards); hut construction and effects keep the C5 windows. Applied in R-040, R-045, R-048.
- O-U2-10 Loans may be taken at any time on the seat's own turn, so a seat short of $1 may take a loan mid-turn to pay the $1 cutting-area move (R-048).
- O-U3-1 The winter requirement does not scale by player count; all 8 cards show one food and one heating value per half (R-070).
- O-U3-2 A sledge trip may move fewer than 2 pieces; food is charged only for pieces moved beyond the free 2, up to 3 food per sledge (Base p.11); a resulting feeding shortfall follows R-073 (R-067).
- O-U3-3 ("only what is due" overridden 2026-11-04: extra optional sales allowed, R-073) Winter shortfall sale: sellable zones are the sale area, drying areas, sawing area and firewood storage (not woodpile, river, task cards, joinery); prices per R-058 with no bonus in the sawing area or firewood storage; order is sale and drying areas first, then sawing area and firewood storage once those are exhausted (R-073).
- O-U3-4 Final dollars may be negative: money minus repayment, no floor (R-083).
- O-U3-5 River wood sells at the unmilled price with no bonus (R-081). O-U3-6 Leftover items are worth $0 (R-081).
- O-U3-7 The margin clip at ±1 stays; margin is documented as not exactly zero-sum for n ≥ 3, so `returns=margin` declares GENERAL_SUM (R-086).
- O-U3-8 No early loan repayment (Base p.17) (R-077).

- O-U4-1 "Easier" winter half is the half with the lower food+heating sum; no ties on the cards (R-117). O-U4-2 One seat may hold two plans on the same season; both resolve (R-087). O-U4-3 PW Food Supply works in its target round like every other PW (R-093; supersedes the earlier whole-year reading). O-U4-4 PW Hut Construction: any 2 of stake/board/shingle/joker, repeatable, reeds excluded (R-095). O-U4-5 A doubled Drying stack is forced on over capacity; Drying Area Upgrade + PW Drying gives 4 pieces in area 1 (R-096, R-111). O-U4-6 A drying hut may move sale-area wood into the first drying area (R-101). O-U4-7 A hut worker token is spent on use, within its C5 window (R-103). O-U4-8 (part) Waterchannel gives one piece per transport phase (R-107). O-U4-9 Small Storage Area holds one milled piece, taken only from the sale or drying areas at task-assignment times, moved to a task in winter year 2's Tasks phase at any dryness for its kind (R-114). O-U4-3 PW Log Driving and Waterchannel pieces count for Food Supply (R-093). O-U4-8 PW Log Driving counts as raft transport for Waterchannel (R-107). O-U4-10 A seat cannot plan the same card for the same season twice; different cards may share a season (R-087, R-088; overrides the earlier stacking answer). O-U4-11 With the Small Workshop at most one reed may stand for a shingle in PW Hut Construction (R-095, R-110). O-U4-12 The stored piece fills milled requirements only (R-114).

## Open questions (unit 2)

None outstanding.

## Open questions (unit 3)

None outstanding.

## Open questions (unit 4)

None outstanding.

## Open questions (task 5 audit)

None outstanding. Resolved: O-U5-1 the order in the winter shortfall sale (sale and drying areas first, then sawing area and firewood storage) also binds the optional extra sales (R-073).
