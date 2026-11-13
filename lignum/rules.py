"""Pure setup rules (R-012..R-020, R-026, R-027, R-031). No pyspiel, no I/O, no randomness.

Chance IDs are never built here as integers: this module speaks in (family, params) pairs of
ACTIONS 2 and ``game.py`` maps them to IDs through ``lignum.actions``.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol

from lignum.components import Components, WinterCard
from lignum.constants import (
    CLEARING_LOC,
    KIND_FIREWOOD,
    KIND_HARDWOOD,
    KIND_SOFTWOOD,
    NUM_AREAS,
)

# ACTIONS 2: SPOT_TOKEN index order (y = 0..11) and CRAFT_DRAW / craftwork type order (x = 0..4).
KIND_NAMES = ("firewood", "softwood", "hardwood")  # kind index 0, 1, 2 (R-007)
EQUIPMENT_ORDER = ("wagon", "raft", "saw", "sledge", "dollar", "food", "x_marker")
SELL_SET_SHAPES = ((2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 0), (4, 1), (4, 2))  # ACTIONS 5.6
CRAFT_ORDER = ("board", "shingle", "stake", "reed", "joker")
SPOT_NAMES = EQUIPMENT_ORDER + CRAFT_ORDER


@dataclass(frozen=True)
class SetupTables:
    """Static per-game setup constants derived from the component data (kept on the game)."""

    players: int
    joinery: bool
    easy_winter: bool
    # AREAS3 rank -> the areas that start with 3 firewood: the lexicographic rank of that
    # k-subset, k = players (user decision 2026-11-05); the other areas start with 2 (R-013, R-015).
    high_area_subsets: tuple[tuple[int, ...], ...]
    firewood_high: int
    firewood_low: int
    # Per winter year (index 0, 1): offered (card, half) outcomes encoded as 2*card + half.
    winter_offers: tuple[tuple[int, ...], tuple[int, ...]]
    deck_sizes: tuple[int, int, int]  # tasks, planned work, buildings
    sequence: tuple[str, ...]  # chance families in order (R-026)
    equipment: tuple[int, ...]  # counts in EQUIPMENT_ORDER
    craft_totals: tuple[int, ...]  # counts in CRAFT_ORDER
    token_spots: tuple[int, ...]  # printed numbers of the 13 token spots, ascending (R-023)
    # Round start (R-035..R-037, R-078, R-079).
    task_cap: int  # task cards laid out (R-013, R-036)
    placement_per_round: int  # placement cards drawn per seasonal round >= 2 (R-013, R-037)
    placement_wood: tuple[tuple[tuple[int, int, int], ...], ...]  # [card][area] -> (fw, sw, hw)
    placement_food: tuple[tuple[int, ...], ...]  # [card][area] -> food added (repeats stack)
    joiner_supply: int  # joiners in the general supply (joinery only, else 0)
    placement_cards: int  # size of the placement deck (R-005)
    joiner_loc: int  # printed number of the Joiner location, 0 without joinery
    # Supply path (R-013, R-021, R-022, R-035, R-040).
    path_bearers: int
    path_woodcutters: int
    path_sawyers_free: int  # price-$0 sawyers (R-025)
    path_sawyers_paid: int  # the $1 sawyer
    path_fodder: int
    locations: tuple[tuple[int, str, int], ...]  # (printed number, kind, capacity) in path order
    # Prices and limits from setup.yaml (R-025, R-041, R-042, R-075, R-076).
    price_location: int  # bearer / woodcutter / fodder / task, each the same price
    price_saw: int  # Market (R-104)
    price_food: int  # Market (R-104)
    craft_set_prices: tuple[int, int, int]  # sale of 2, 3, 4 identical craftwork tokens (R-105)
    price_sawyer_extra: int  # the second sawyer of a visit
    loan_amount: int
    max_loans: int
    max_saws: int
    # Sawing, selling, drying, tasks (R-054..R-059), indexed by kind 0 firewood, 1 softwood,
    # 2 hardwood.
    sawing_yield: tuple[int, int, int]  # logs per milled disk
    wood_price: tuple[tuple[int, int], ...]  # per kind: (unmilled, milled); -1 = cannot be sold
    dry_bonus: tuple[int, int, int, int]  # sale area, drying 1, 2, 3
    dry_cap_disks: int  # unmilled disks per drying area (never together with logs)
    dry_cap_logs: int  # milled logs per drying area
    # Flat requirement slots (ACTIONS 1.5): (task index, requirement index, kind, milled, stage).
    task_slots: tuple[tuple[int, int, int, int, int], ...]
    # Winter requirements (R-070): [year 0/1][card][half 0 top / 1 bottom] -> (food, heating).
    winter_req: tuple[tuple[tuple[tuple[int, int], tuple[int, int]], ...], ...]
    winter_rounds: tuple[int, int]  # R-033: the rounds of the two winters
    winter_cut_further: int  # firewood from each later winter woodcutting action (R-066)
    winter_cut_first: int  # firewood from the first winter woodcutting action (R-066)
    sledge_free: int  # pieces a sledge moves without food (R-067)
    sledge_food: int  # most food a sledge can turn into extra pieces (R-067)
    shortfall_unit: int  # dollars per missing food or heating unit (R-073)
    joiner_income: int  # dollars per joiner at round start (R-079)
    joiner_spaces: int  # joiners one seat can hold (R-010, R-078)
    building_spaces: int  # buildings one seat can own (R-010, R-106)
    building_ids: tuple[str, ...]  # data ids in YAML order (index = ACTIONS building b)
    building_params: tuple[Mapping[str, Any], ...]  # per building: the numbers in its data entry
    pw_seasons: tuple[tuple[int, ...], ...]  # per PW card: printed season indices (R-088)
    pw_ids: tuple[str, ...]  # per PW card: its data id (effects look cards up by id, R-089..R-094)
    pw_params: tuple[Mapping[str, Any], ...]  # per PW card: the numbers named in its data entry
    pw_pairs: int  # pairs per seat (R-087): planned_work_tokens // 2 (a plan uses 2 tokens)
    pw_token_price: int  # dollars per token on the card (R-088)
    token_move_price: int  # dollars to move the cutting-area token (R-048)
    joiner_food: int  # extra food due per joiner at feeding (R-071)
    joinery_bonus: int  # final-sale bonus of a covered joinery piece (R-082)
    loan_repay: tuple[int, ...]  # game-end repayment by number of loans held (R-077)


def easier_half(card: WinterCard) -> int:
    """Implements R-027/R-117: 0 = top, 1 = bottom, the lower food+heating half; a tie raises."""
    halves = card.halves
    top = halves["top"].food + halves["top"].heating
    bottom = halves["bottom"].food + halves["bottom"].heating
    if top == bottom:
        raise ValueError(f"winter card {card.id}: halves tie on food+heating, no easier half")
    return 0 if top < bottom else 1


def _subsets(size: int, k: int) -> tuple[tuple[int, ...], ...]:
    """All k-subsets of range(size) in lexicographic order (the AREAS3 rank order)."""
    out: list[tuple[int, ...]] = []
    for c in itertools.combinations(range(size), k):
        out.append(tuple(c))
    return tuple(out)


def _single_price(comp: Components) -> int:
    """Implements R-041: bearer, woodcutter, fodder and task share one price (setup.yaml)."""
    lp = comp.setup.location_prices
    prices = {lp.bearer, lp.woodcutter, lp.fodder, lp.task}
    if len(prices) != 1:
        raise ValueError(f"path location prices differ: {sorted(prices)}")
    return prices.pop()


def build_tables(comp: Components, players: int, joinery: bool, easy_winter: bool) -> SetupTables:
    """Implements R-013, R-014, R-017, R-026, R-027."""
    q = comp.setup.by_players[players]
    n_high = q.cutting_areas_with_3_firewood
    subsets = _subsets(NUM_AREAS, n_high)
    offers: list[tuple[int, ...]] = []
    for year in (1, 2):
        cards = [w for w in comp.winter if w.year == year]
        offers.append(
            tuple(
                2 * c + h
                for c, w in enumerate(cards)
                for h in ((easier_half(w),) if easy_winter else (0, 1))
            )
        )
    seq = ["AREAS3", "WINTER", "WINTER"]
    seq += ["TASK_DRAW"] * q.task_cards_laid_out
    seq += ["PW_DRAW"] * q.pw_cards_laid_out
    if joinery:
        seq += ["BUILDING_DRAW"] * q.buildings_drawn
    seq += ["CRAFT_DRAW"] * comp.setup.path_craftwork_tokens
    seq += ["SPOT_TOKEN"] * comp.path.token_spot_count
    equip = q.path_equipment_tokens
    side = comp.path.sides["joinery" if joinery else "base"]
    spots = tuple(loc.number for loc in side if loc.kind == "token_spot")
    kind_index = {"firewood": KIND_FIREWOOD, "softwood": KIND_SOFTWOOD, "hardwood": KIND_HARDWOOD}
    p_wood: list[tuple[tuple[int, int, int], ...]] = []
    p_food: list[tuple[int, ...]] = []
    for card in comp.placement:
        wood = [[0, 0, 0] for _ in range(NUM_AREAS)]
        for area, kinds in card.areas.items():
            for k in kinds:
                wood[int(area) - 1][kind_index[k]] += 1
        food = [0] * NUM_AREAS
        for area in card.food_areas:
            food[int(area) - 1] += 1
        p_wood.append(tuple((w[0], w[1], w[2]) for w in wood))
        p_food.append(tuple(food))
    joiner_loc = next((loc.number for loc in side if loc.kind == "joiner"), 0)
    winter_req = tuple(
        tuple(
            (
                (w.halves["top"].food, w.halves["top"].heating),
                (w.halves["bottom"].food, w.halves["bottom"].heating),
            )
            for w in comp.winter
            if w.year == year
        )
        for year in (1, 2)
    )
    return SetupTables(
        winter_req=winter_req,
        winter_rounds=WINTER_ROUNDS,
        winter_cut_further=comp.setup.winter.woodcutting_each_further,
        winter_cut_first=comp.setup.winter.woodcutting_first,
        sledge_free=comp.setup.winter.sledge_base_pieces,
        sledge_food=comp.setup.winter.sledge_max_food,
        shortfall_unit=comp.setup.winter.shortfall_per_unit,
        joiner_income=comp.setup.joiner.income_per_round,
        joiner_spaces=comp.setup.player_board_extension.joiner_spaces,
        building_spaces=comp.setup.player_board_extension.building_spaces,
        building_ids=tuple(b.id for b in comp.buildings),
        building_params=tuple(b.params for b in comp.buildings),
        pw_seasons=tuple(
            tuple(SEASON_NAMES.index(x) for x in c.seasons) for c in comp.planned_work
        ),
        pw_ids=tuple(c.id for c in comp.planned_work),
        pw_params=tuple(c.params for c in comp.planned_work),
        pw_pairs=comp.setup.per_seat.planned_work_tokens // 2,
        pw_token_price=comp.setup.location_prices.planned_work_per_token,
        token_move_price=comp.setup.location_prices.cutting_area_move,
        joiner_food=comp.setup.joiner.food_per_winter,
        joinery_bonus=comp.setup.joinery_bonus,
        loan_repay=(0, *(comp.setup.loans.repayment[k] for k in (1, 2))),
        players=players,
        joinery=joinery,
        easy_winter=easy_winter,
        high_area_subsets=subsets,
        firewood_high=comp.setup.cutting_area_firewood.with_3,
        firewood_low=comp.setup.cutting_area_firewood.with_2,
        winter_offers=(offers[0], offers[1]),
        deck_sizes=(len(comp.tasks), len(comp.planned_work), len(comp.buildings)),
        sequence=tuple(seq),
        equipment=tuple(equip.get(name, 0) for name in EQUIPMENT_ORDER),
        craft_totals=tuple(comp.setup.supply.craftwork_by_type[name] for name in CRAFT_ORDER),
        token_spots=spots,
        task_cap=q.task_cards_laid_out,
        placement_per_round=q.placement_cards_per_round,
        placement_wood=tuple(p_wood),
        placement_food=tuple(p_food),
        joiner_supply=comp.setup.supply.joiners if joinery else 0,
        placement_cards=len(comp.placement),
        joiner_loc=joiner_loc,
        path_bearers=q.bearers_on_path,
        path_woodcutters=q.woodcutters_on_path,
        path_sawyers_free=q.sawyers_price_0,
        path_sawyers_paid=q.sawyers_price_1,
        path_fodder=q.fodder_on_path,
        locations=tuple((loc.number, loc.kind, loc.capacity) for loc in side),
        price_location=_single_price(comp),
        price_saw=comp.setup.location_prices.market_saw,
        price_food=comp.setup.location_prices.market_food,
        craft_set_prices=(
            comp.setup.craftwork_set_prices[2],
            comp.setup.craftwork_set_prices[3],
            comp.setup.craftwork_set_prices[4],
        ),
        price_sawyer_extra=comp.setup.sawyer_prices.extra,
        loan_amount=comp.setup.loans.amount_each,
        max_loans=comp.setup.loans.max_per_seat,
        max_saws=comp.setup.supply.max_saws_per_seat,
        sawing_yield=(
            comp.setup.sawing_yield.firewood,
            comp.setup.sawing_yield.softwood,
            comp.setup.sawing_yield.hardwood,
        ),
        wood_price=tuple(
            (
                -1
                if comp.setup.wood_prices[name].unmilled is None
                else comp.setup.wood_prices[name].unmilled,
                comp.setup.wood_prices[name].milled,
            )
            for name in KIND_NAMES
        ),
        dry_bonus=(
            comp.setup.drying_bonuses.sale_area,
            comp.setup.drying_bonuses.drying_1,
            comp.setup.drying_bonuses.drying_2,
            comp.setup.drying_bonuses.drying_3,
        ),
        dry_cap_disks=comp.setup.drying_area_capacity.disks,
        dry_cap_logs=comp.setup.drying_area_capacity.logs,
        task_slots=tuple(
            (ti, ri, KIND_NAMES.index(req.kind), int(req.milled), req.drying)
            for ti, task in enumerate(comp.tasks)
            for ri, req in enumerate(task.requirements)
        ),
    )


@dataclass(frozen=True)
class SetupDraws:
    """The chance results of setup so far (all public). Decks are stored as sorted tuples (the
    state depends on the set, ACTIONS 1.6); craftwork and spot tokens keep their draw order."""

    step: int = 0
    areas_rank: int = -1
    winter: tuple[int, ...] = ()  # 2*card + half per year drawn
    tasks: tuple[int, ...] = ()
    pw: tuple[int, ...] = ()
    buildings: tuple[int, ...] = ()
    craft: tuple[int, ...] = ()  # craftwork type per CRAFT_DRAW
    spots: tuple[int, ...] = ()  # SPOT_TOKEN y per spot, in spot order

    def done(self, t: SetupTables) -> bool:
        return self.step >= len(t.sequence)

    def family(self, t: SetupTables) -> str:
        return t.sequence[self.step]

    def high_areas(self, t: SetupTables) -> tuple[int, ...]:
        """Implements R-015: areas starting with 3 firewood (empty before AREAS3)."""
        if self.areas_rank < 0:
            return ()
        return t.high_area_subsets[self.areas_rank]

    def firewood(self, t: SetupTables) -> tuple[int, ...]:
        """Firewood per area (R-015); zeros before AREAS3."""
        if self.areas_rank < 0:
            return (0,) * NUM_AREAS
        high = self.high_areas(t)
        return tuple(t.firewood_high if a in high else t.firewood_low for a in range(NUM_AREAS))

    def _spot_pool(self, t: SetupTables) -> list[int]:
        pool = list(t.equipment) + [0] * len(CRAFT_ORDER)
        for x in self.craft:
            pool[len(EQUIPMENT_ORDER) + x] += 1
        for y in self.spots:
            pool[y] -= 1
        return pool

    def outcomes(self, t: SetupTables) -> list[tuple[str, tuple[int, ...], float]]:
        """Implements R-014, R-017, R-026, R-027: (family, params, probability) at this node,
        uniform over remaining items (proportional to remaining counts for tokens)."""
        fam = self.family(t)
        if fam == "AREAS3":
            n = len(t.high_area_subsets)
            return [(fam, (r,), 1.0 / n) for r in range(n)]
        if fam == "WINTER":
            offers = t.winter_offers[len(self.winter)]
            return [(fam, (o // 2, o % 2), 1.0 / len(offers)) for o in offers]
        if fam in ("TASK_DRAW", "PW_DRAW", "BUILDING_DRAW"):
            idx = ("TASK_DRAW", "PW_DRAW", "BUILDING_DRAW").index(fam)
            drawn = (self.tasks, self.pw, self.buildings)[idx]
            left = [i for i in range(t.deck_sizes[idx]) if i not in drawn]
            return [(fam, (i,), 1.0 / len(left)) for i in left]
        if fam == "CRAFT_DRAW":
            left_c = [t.craft_totals[x] - self.craft.count(x) for x in range(len(CRAFT_ORDER))]
            total = sum(left_c)
            return [(fam, (x,), c / total) for x, c in enumerate(left_c) if c > 0]
        pool = self._spot_pool(t)
        total = sum(pool)
        return [(fam, (y,), c / total) for y, c in enumerate(pool) if c > 0]

    def apply(self, t: SetupTables, fam: str, params: tuple[int, ...]) -> SetupDraws:
        """Implements R-026: record one chance outcome (caller has checked it is legal)."""
        nxt = self.step + 1
        if fam == "AREAS3":
            return replace(self, step=nxt, areas_rank=params[0])
        if fam == "WINTER":
            return replace(self, step=nxt, winter=self.winter + (2 * params[0] + params[1],))
        if fam == "TASK_DRAW":
            return replace(self, step=nxt, tasks=tuple(sorted(self.tasks + params)))
        if fam == "PW_DRAW":
            return replace(self, step=nxt, pw=tuple(sorted(self.pw + params)))
        if fam == "BUILDING_DRAW":
            return replace(self, step=nxt, buildings=tuple(sorted(self.buildings + params)))
        if fam == "CRAFT_DRAW":
            return replace(self, step=nxt, craft=self.craft + params)
        return replace(self, step=nxt, spots=self.spots + params)


@dataclass(frozen=True)
class RoundDraws:
    """The chance run of one seasonal round start from round 2 (R-035..R-037, R-062).

    Order (ACTIONS 2, user decision 2026-11-05): TASK_DRAW (missing cards), CRAFT_DRAW x3,
    SPOT_TOKEN x13, PLACEMENT_DRAW x per-round count. Everything drawn here is public.
    """

    seq: tuple[str, ...]
    tasks_seen: tuple[int, ...]  # task cards drawn before this run (laid out or held)
    pile: tuple[int, ...]  # craftwork pile counts (CRAFT_ORDER) before this run
    placement_seen: tuple[int, ...]  # placement cards already discarded
    pos: int = 0
    new_tasks: tuple[int, ...] = ()
    craft: tuple[int, ...] = ()
    spots: tuple[int, ...] = ()
    cards: tuple[int, ...] = ()

    def done(self) -> bool:
        return self.pos >= len(self.seq)

    def outcomes(self, t: SetupTables) -> list[tuple[str, tuple[int, ...], float]]:
        """Implements R-062: (family, params, probability) at this node."""
        fam = self.seq[self.pos]
        if fam == "TASK_DRAW":
            seen = self.tasks_seen + self.new_tasks
            left = [i for i in range(t.deck_sizes[0]) if i not in seen]
            return [(fam, (i,), 1.0 / len(left)) for i in left]
        if fam == "PLACEMENT_DRAW":
            seen = self.placement_seen + self.cards
            left = [i for i in range(len(t.placement_wood)) if i not in seen]
            return [(fam, (i,), 1.0 / len(left)) for i in left]
        if fam == "CRAFT_DRAW":
            rest = [self.pile[x] - self.craft.count(x) for x in range(len(CRAFT_ORDER))]
            total = sum(rest)
            return [(fam, (x,), c / total) for x, c in enumerate(rest) if c > 0]
        pool = list(t.equipment) + [0] * len(CRAFT_ORDER)
        for x in self.craft:
            pool[len(EQUIPMENT_ORDER) + x] += 1
        for y in self.spots:
            pool[y] -= 1
        total = sum(pool)
        return [(fam, (y,), c / total) for y, c in enumerate(pool) if c > 0]

    def apply(self, fam: str, params: tuple[int, ...]) -> RoundDraws:
        """Implements R-062: record one chance outcome (caller has checked it is legal)."""
        nxt = self.pos + 1
        if fam == "TASK_DRAW":
            return replace(self, pos=nxt, new_tasks=self.new_tasks + params)
        if fam == "PLACEMENT_DRAW":
            return replace(self, pos=nxt, cards=self.cards + params)
        if fam == "CRAFT_DRAW":
            return replace(self, pos=nxt, craft=self.craft + params)
        return replace(self, pos=nxt, spots=self.spots + params)


def start_round_draws(
    t: SetupTables,
    row_size: int,
    tasks_seen: tuple[int, ...],
    pile: tuple[int, ...],
    placement_seen: tuple[int, ...],
) -> RoundDraws:
    """Implements R-035, R-036, R-037, R-062: the chance run of a seasonal round >= 2.

    The task row is refilled to the laid-out count while the deck lasts (R-036)."""
    missing = max(0, min(t.task_cap - row_size, t.deck_sizes[0] - len(tasks_seen)))
    seq = ["TASK_DRAW"] * missing
    seq += ["CRAFT_DRAW"] * 3 + ["SPOT_TOKEN"] * len(t.token_spots)
    seq += ["PLACEMENT_DRAW"] * t.placement_per_round
    return RoundDraws(tuple(seq), tasks_seen, pile, placement_seen)


def apply_placement(
    t: SetupTables,
    wood: tuple[tuple[int, int, int], ...],
    food: tuple[int, ...],
    cards: tuple[int, ...],
) -> tuple[tuple[tuple[int, int, int], ...], tuple[int, ...]]:
    """Implements R-037: add each drawn card's wood and food, then 1 firewood to every area that
    holds no wood (food does not count)."""
    w = [list(a) for a in wood]
    f = list(food)
    for q in cards:
        for a in range(NUM_AREAS):
            for k in range(3):
                w[a][k] += t.placement_wood[q][a][k]
            f[a] += t.placement_food[q][a]
    for a in range(NUM_AREAS):
        if sum(w[a]) == 0:
            w[a][KIND_FIREWOOD] = 1
    return tuple((a[0], a[1], a[2]) for a in w), tuple(f)


def distribute_food(
    picks: tuple[int, ...], food: tuple[int, ...]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Implements R-039: a seat alone in its area takes all of its food; seats sharing divide it
    evenly, the indivisible rest stays. Returns (food gained per seat, area food left)."""
    gain = [0] * len(picks)
    left = list(food)
    for a in range(NUM_AREAS):
        seats = [s for s, p in enumerate(picks) if p == a]
        if not seats:
            continue
        share = left[a] // len(seats)
        for s in seats:
            gain[s] += share
        left[a] -= share * len(seats)
    return tuple(gain), tuple(left)


# --------------------------------------------------------------------------- supply path (unit 6)

MULTI_UNIT_KINDS = frozenset({"bearers", "woodcutters", "sawyers", "market"})  # end only on DONE
SPOT_X = SPOT_NAMES.index("x_marker")
SPOT_SAW = SPOT_NAMES.index("saw")
FIRST_CRAFT_SPOT = len(SPOT_NAMES) - len(CRAFT_ORDER)  # SPOT_TOKEN y >= this is craftwork
WINTER_ROUNDS = (4, 8)  # R-033
SEASON_NAMES = ("spring", "summer", "fall", "winter")  # season index order
LAST_ROUND = 8
EQUIP_SLOTS = ("saw", "wagon", "raft", "sledge")  # index order of the per-seat equipment tuple


class TravelState(Protocol):
    """The slice of the game state the travel rules read (structural; see ``LignumState``)."""

    picks: tuple[int, ...]
    wood: tuple[tuple[int, int, int], ...]
    money: tuple[int, ...]
    loans: tuple[int, ...]
    joiners: tuple[int, ...]
    foreman: tuple[int, ...]
    hired_w: tuple[int, ...]
    hired_s: tuple[int, ...]
    path_b: int
    path_w: int
    path_sf: int
    path_sp: int
    path_fodder: int
    path_joiner: int
    fodder3: tuple[int, ...]
    fodder_bought: tuple[int, ...]
    task_taken: tuple[int, ...]
    task_row: tuple[int, ...]
    path_tokens: tuple[int, ...]
    equip: tuple[tuple[int, int, int, int], ...]
    held_craft: tuple[tuple[int, ...], ...]
    visit_n: int
    visit_food: int
    round: int
    plans: tuple[tuple[int, int, int, int], ...]  # (seat, card, pair, target round) in order made
    held_buildings: tuple[tuple[int, ...], ...]  # building indices owned per seat (R-106)
    food: tuple[int, ...]

    @property
    def pw_cards(self) -> tuple[int, ...]: ...

    @property
    def bld_supply(self) -> tuple[int, ...]: ...


def can_pay_one(t: SetupTables, ts: TravelState, seat: int) -> bool:
    """Implements R-040(4), R-076: $1 is payable if held or a loan could still be taken."""
    return ts.money[seat] >= t.price_location or ts.loans[seat] < t.max_loans


def woodcutter_room(t: SetupTables, ts: TravelState, seat: int) -> int:
    """Implements R-041, R-099: wood pieces in the seat's cutting area (plus 2 with PW Cutting in
    its target round) minus woodcutters already hired."""
    extra = (
        plan_param(t, "pw_cutting", "extra_woodcutters")
        if plan_active(t, ts, seat, "pw_cutting")
        else 0
    )
    return sum(ts.wood[ts.picks[seat]]) + extra - ts.hired_w[seat]


def craft_sales(held: tuple[int, ...]) -> list[tuple[str, tuple[int, ...]]]:
    """Implements R-105: the sets sellable from a craftwork holding (CRAFT_ORDER, joker last), as
    (name, params). A set is 2-4 tokens, at least one real token of one type plus jokers, or two
    jokers; a single token is never sellable."""
    jokers = held[len(CRAFT_ORDER) - 1]
    out: list[tuple[str, tuple[int, ...]]] = []
    for x in range(len(CRAFT_ORDER) - 1):
        for s, j in SELL_SET_SHAPES:
            if 1 <= s - j <= held[x] and j <= jokers:
                out.append(("SELL_SET", (x, s, j)))
    if jokers >= 2:
        out.append(("SELL_SET_JOKERS", ()))
    return out


def craft_price(t: SetupTables, ts: _Planned, seat: int, size: int) -> int:
    """Implements R-105, R-091: dollars for a set of ``size`` tokens (PW Craftwork in its target
    round pays the card's prices)."""
    if plan_active(t, ts, seat, "pw_craftwork"):
        return plan_param(t, "pw_craftwork", "set_prices")[size]
    return t.craft_set_prices[size - 2]


def equip_sales(t: SetupTables, ts: TravelState, seat: int) -> list[tuple[str, tuple[int, ...]]]:
    """Implements R-090: SELL_EQUIP(e) for the raft/sledge/wagon types held (e 0 raft, 1 sledge,
    2 wagon), only with PW Trade in its target round."""
    if not plan_active(t, ts, seat, "pw_trade"):
        return []
    return [
        ("SELL_EQUIP", (e,))
        for e, slot in enumerate(("raft", "sledge", "wagon"))
        if ts.equip[seat][EQUIP_SLOTS.index(slot)] > 0
    ]


def round_season(rnd: int) -> int:
    """Implements R-033, R-088: season index of a round (winter rounds 4 and 8 are winter)."""
    if rnd in WINTER_ROUNDS:
        return len(SEASON_NAMES) - 1
    return (rnd - 1) % (WINTER_ROUNDS[0])


class _Planned(Protocol):
    round: int
    plans: tuple[tuple[int, int, int, int], ...]


def has_building(t: SetupTables, held: tuple[tuple[int, ...], ...], seat: int, bid: str) -> bool:
    """Implements R-106: whether ``seat`` owns the building with data id ``bid`` (R-107..R-110)."""
    return bid in t.building_ids and t.building_ids.index(bid) in held[seat]


def building_param(t: SetupTables, bid: str, key: str) -> Any:
    """The number ``key`` of building ``bid`` from the component data (R-107..R-110)."""
    return t.building_params[t.building_ids.index(bid)][key]


def plan_param(t: SetupTables, pw_id: str, key: str) -> Any:
    """The number ``key`` of PW card ``pw_id`` from the component data."""
    return t.pw_params[t.pw_ids.index(pw_id)][key]


def plan_active(t: SetupTables, s: _Planned, seat: int, pw_id: str) -> bool:
    """Implements R-089: the seat holds a plan for card ``pw_id`` whose target is this round."""
    return any(p[0] == seat and t.pw_ids[p[1]] == pw_id and p[3] == s.round for p in s.plans)


def plan_cost(t: SetupTables, ts: TravelState, card: int, seat: int) -> int:
    """Implements R-088(4): $1 per token on the card, whoever's; the new plan's tokens are not
    counted (one token of each plan lies on the card)."""
    if has_building(t, ts.held_buildings, seat, "inn"):  # R-113: the Inn sets the cost
        return building_param(t, "inn", "planned_work_cost")
    return t.pw_token_price * sum(1 for p in ts.plans if p[1] == card)


def plan_options(t: SetupTables, ts: TravelState, seat: int) -> list[tuple[int, int, int]]:
    """Implements R-087, R-088, R-040(4): (card, pair, cost) the seat could plan now apart from
    money: not yet planned this round, unused pair, laid-out card printed for the target season,
    target round <= 8, no same card for the same target twice."""
    mine = [p for p in ts.plans if p[0] == seat]
    if any(p[3] - p[2] == ts.round for p in mine):
        return []
    used = {p[2] for p in mine}
    out: list[tuple[int, int, int]] = []
    for pair in range(1, t.pw_pairs + 1):
        target = ts.round + pair
        if pair in used or target > LAST_ROUND:
            continue
        season = round_season(target)
        for card in ts.pw_cards:
            if season in t.pw_seasons[card] and not any(
                p[1] == card and p[3] == target for p in mine
            ):
                out.append((card, pair, plan_cost(t, ts, card, seat)))
    return out


def destination_ok(t: SetupTables, ts: TravelState, seat: int, number: int, kind: str) -> bool:
    """Implements R-040(4), R-041, R-042, R-078: the foreman would make an acquisition there."""
    if kind == "token_spot":
        y = ts.path_tokens[t.token_spots.index(number)]
        return y >= 0 and y != SPOT_X and not (y == SPOT_SAW and ts.equip[seat][0] >= t.max_saws)
    if kind == "buildings":  # R-106: fewer than 2 owned and a tile left in the supply
        return len(ts.held_buildings[seat]) < t.building_spaces and bool(ts.bld_supply)
    if kind == "joiner":
        return ts.path_joiner > 0 and ts.joiners[seat] < t.joiner_spaces
    if kind == "sawyers":
        return ts.path_sf > 0 and ts.hired_s[seat] == 0
    if kind == "planned_work":  # R-088: a plan is affordable, a same-turn loan counted
        room = (t.max_loans - ts.loans[seat]) * t.loan_amount
        return any(ts.money[seat] + room >= c for _, _, c in plan_options(t, ts, seat))
    if kind == "market":
        # R-104: food is always buyable, so affording one suffices; a sellable set (R-105) also
        # counts; extend with equipment and food sales (R-090, R-108) here.
        return (
            ts.money[seat] >= t.price_food
            or ts.loans[seat] < t.max_loans
            or bool(craft_sales(ts.held_craft[seat]))
            or bool(equip_sales(t, ts, seat))
            or (bool(ts.food[seat]) and has_building(t, ts.held_buildings, seat, "marketstand"))
        )
    if kind == "fodder":  # R-115: a free fodder needs no payment
        return (
            ts.path_fodder > 0
            and not ts.fodder3[seat]
            and not ts.fodder_bought[seat]
            and (ts.money[seat] >= fodder_cost(t, ts, seat) or ts.loans[seat] < t.max_loans)
        )
    if not can_pay_one(t, ts, seat):
        return False
    if kind == "bearers":
        return ts.path_b > 0
    if kind == "woodcutters":
        return ts.path_w > 0 and woodcutter_room(t, ts, seat) > 0
    if kind == "tasks":
        return len(ts.task_row) > 0 and not ts.task_taken[seat]
    raise ValueError(f"unknown location kind {kind}")


def fodder_cost(t: SetupTables, ts: TravelState, seat: int) -> int:
    """Implements R-041, R-115: the Field makes fodder cost its building parameter."""
    if has_building(t, ts.held_buildings, seat, "field"):
        return int(building_param(t, "field", "fodder_cost"))
    return t.price_location


def legal_destinations(t: SetupTables, ts: TravelState, seat: int) -> list[int]:
    """Implements R-040, R-044: printed numbers the seat may move to (clearing always last)."""
    here = ts.foreman[seat]
    out: list[int] = []
    for number, kind, capacity in t.locations:
        if number <= here:
            continue
        if sum(1 for f in ts.foreman if f == number) >= capacity:
            continue
        if destination_ok(t, ts, seat, number, kind):
            out.append(number)
    out.append(CLEARING_LOC)
    return out


def visit_options(
    t: SetupTables, ts: TravelState, seat: int, kind: str
) -> list[tuple[str, tuple[int, ...]]]:
    """Implements R-025, R-041: acquisitions open inside an entered visit, as (name, params).
    TAKE_LOAN and DONE are added by the caller."""
    paid = ts.money[seat] >= t.price_location
    if kind == "bearers":
        return [("HIRE_BEARER", ())] if ts.path_b > 0 and paid else []
    if kind == "woodcutters":
        ok = ts.path_w > 0 and woodcutter_room(t, ts, seat) > 0 and paid
        return [("HIRE_WOODCUTTER", ())] if ok else []
    if kind == "sawyers":
        if ts.visit_n == 0:
            return [("HIRE_SAWYER", ())] if ts.path_sf > 0 else []
        if ts.visit_n == 1:
            extra = ts.money[seat] >= t.price_sawyer_extra
            return [("HIRE_SAWYER", ())] if ts.path_sp > 0 and extra else []
        return []
    if kind == "planned_work":  # R-088: a loan is taken beforehand (TAKE_LOAN)
        return [
            ("PLAN_WORK", (card, pair - 1))
            for card, pair, cost in plan_options(t, ts, seat)
            if ts.money[seat] >= cost
        ]
    if kind == "market":  # R-104; sale options (R-105, R-090, R-108) join here
        # Per-visit exclusion (2026-11-07): buying and selling food never mix in one visit.
        buy = ts.money[seat] >= t.price_food and ts.visit_food != 2
        out = [("BUY_FOOD", ())] if buy else []
        if ts.money[seat] >= t.price_saw and ts.equip[seat][0] < t.max_saws:
            out.append(("BUY_SAW", ()))
        out += craft_sales(ts.held_craft[seat]) + equip_sales(t, ts, seat)
        if (
            ts.food[seat]
            and ts.visit_food != 1
            and has_building(t, ts.held_buildings, seat, "marketstand")
        ):
            out.append(("SELL_FOOD", ()))  # R-108
        return out
    if kind == "buildings":  # R-106: free, one tile from the supply
        return [("CHOOSE_BUILDING", (b,)) for b in ts.bld_supply]
    if kind == "fodder":
        ok = ts.money[seat] >= fodder_cost(t, ts, seat) and ts.path_fodder > 0
        return [("BUY_FODDER", ())] if ok else []
    if kind == "tasks":
        return [("TAKE_TASK", (c,)) for c in ts.task_row] if paid else []
    return []
