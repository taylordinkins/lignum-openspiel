"""Expected-dollars value function for Lignum bots (Phase 6, D32).

``value(state, seat)`` estimates the dollars ``seat`` will end with (R-083 final dollars) from any
non-terminal state; at a terminal state it IS the final dollars, so it agrees with ``returns``.
``value_diff`` is the seat's value minus the mean of the opponents' values (the zero-sum shape that
matches ``returns``), for lookahead.

Information: only public state and the seat's own holdings are read. Cutting-area picks (``picks``,
``pk``, ``pick_log``) are never touched, so the value is the same across the other seats'
unrevealed picks. Opponent values (``value_diff``) read only their public boards (money, wood
zones, tasks, plans), which every player sees (R-028).

Every price, reward and requirement comes from the engine's tables / component data; the module
holds only bot-tuning weights, read from the ``value:`` section of a bot profile
(``data/bots/<profile>.yaml``, see ``lignum.bots.weights``) and passed in as ``w``.

Components, all in dollars:
  money
  - loan repayment owed (R-077)
  + wood in the sale and drying areas at R-058 price + area bonus (x discount: not yet sold)
  + joinery pieces (R-082, covered slots full, uncovered at a discount)
  + unsold wood upstream (sawing area, woodpile, river) at the best of its unmilled / sawn value
    (x discount: needs workers, saws, transport); worth 0 in the last winter (cannot be sold)
  + held task cards: reward x progress (full reward when complete, x discount when partial)
  + Office building bonus per held task card (R-116)
  + planned work still to execute, buildings, joiner income to come, craftwork sets
  - winter shortfall ahead (R-071..R-073): $3 per missing food / heating unit, weighted by how
    close the winter is (far winters can still be provided for)
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any, cast

from lignum.bots.plan import task_worth
from lignum.bots.tasks import TaskPlanner, held_assessments
from lignum.bots.weights import value_weights
from lignum.components import Components, load_components
from lignum.game import (
    FEED,
    PHASE_END,
    PHASE_N2,
    PHASE_N3,
    PHASE_N5,
    PHASE_SF,
    PHASE_W2,
    LignumState,
)
from lignum.rules import CRAFT_ORDER, SetupTables, building_param, has_building

Weights = Mapping[str, float]


@cache
def _components() -> Components:
    return load_components()


def _best_unmilled_or_sawn(t: SetupTables, kind: int) -> float:
    """Value of one unmilled disk that can still be sawn: the better of selling it as is
    (unmilled price, -1 = unsellable) and sawing it into logs sold milled (R-054, R-058)."""
    unmilled = max(0, t.wood_price[kind][0])
    return float(max(unmilled, t.sawing_yield[kind] * t.wood_price[kind][1]))


def _wood_zone_value(state: LignumState, t: SetupTables, seat: int, w: Weights) -> float:
    """Wood on the board. Upstream zones (R-046) stop counting once nothing can move them to the
    sale area any more: round-8 woodpile wood after N2 (sledge, R-067), sawing-area wood after N3
    (winter sawing, R-068). River wood is final once log driving is over (R-049: after W2 of the
    round before the last winter), then it only sells under R-081 step 2."""
    sale_d, dry_d = w["sale_discount"], w["dry_discount"]
    up_d, river_d = w["upstream_discount"], w["river_discount"]
    total = 0.0
    sale, sale_logs, dry = state.sale[seat], state.sale_logs[seat], state.dry[seat]
    for kind in range(3):
        un, milled = t.wood_price[kind]
        if un >= 0:
            total += sale[kind] * (un + t.dry_bonus[0]) * sale_d
        total += sale_logs[kind] * (milled + t.dry_bonus[0]) * sale_d
        for area in range(3):
            disks, logs = dry[area][kind], dry[area][3 + kind]
            bonus = t.dry_bonus[area + 1]
            if un >= 0:
                total += disks * (un + bonus) * dry_d
            total += logs * (milled + bonus) * dry_d
    last = t.winter_rounds[1]
    final_round = state.round >= last
    river_final = final_round or (state.round == last - 1 and state.phase > PHASE_W2)
    for kind in range(3):
        sawn = _best_unmilled_or_sawn(t, kind)
        if not final_round or state.phase <= PHASE_N2:
            total += state.woodpile[seat][kind] * sawn * up_d
        if not final_round or state.phase <= PHASE_N3:
            total += state.sawing[seat][kind] * sawn * up_d
        if not river_final:
            total += state.river[seat][kind] * sawn * river_d
    if river_final:
        total += _river_final(state, t, seat)
    return total


def _river_final(state: LignumState, t: SetupTables, seat: int) -> float:
    """Final-sale river (R-081 step 2): the best single sellable kind at its unmilled price; $0
    once the seat has made its choice (the other kind can no longer be sold)."""
    if seat in state.choosers and seat not in state.fs_pending:
        return 0.0
    r = state.river[seat]
    return float(max(r[k] * max(0, t.wood_price[k][0]) for k in range(2)))


def _joinery_value(state: LignumState, t: SetupTables, seat: int, w: Weights) -> float:
    bonus = t.joinery_bonus
    if has_building(t, state.held_buildings, seat, "small_joinery"):
        bonus = building_param(t, "small_joinery", "joinery_bonus")
    total = 0.0
    for slot, kind in enumerate(state.joinery_wood[seat]):
        if 0 <= kind < 3:
            v = t.wood_price[kind][1] + bonus
            total += v if slot < state.joiners[seat] else v * w["joinery_uncovered"]
    return total


def _task_value(
    state: LignumState, t: SetupTables, seat: int, w: Weights, dead: bool = False
) -> float:
    tasks = _components().tasks
    total = 0.0
    plan_w = w.get("task_plan_weight", 0.0)
    chance: dict[int, float] = {}
    first = bool(w.get("task_first", 0))
    worth: dict[int, float] = {}
    pw = cast("Mapping[str, Any] | None", w.get("plan"))  # v7 section (a mapping, not a float)
    if pw and pw.get("enabled") and not dead:  # v7: the long-term plan values held tasks
        first = True
        worth = task_worth(state, seat, pw)
    elif first and not dead:  # v3: a finishable task is worth near its reward, others nothing
        planner = TaskPlanner(t, w)
        worth = {
            h: planner.worth(a, tasks[h].reward)
            for h, a in held_assessments(planner, state, seat, tasks).items()
        }
    elif plan_w and not dead:  # v2: completion chance from the wood the seat has or can get
        chance = {
            h: a.prob * plan_w
            for h, a in held_assessments(TaskPlanner(t, w), state, seat, tasks).items()
        }
    for held in state.held_tasks[seat]:
        task = tasks[held]
        need = len(task.requirements)
        done = bin(state.filled[held]).count("1")
        if done >= need:
            total += task.reward
        elif first:
            total += worth.get(held, 0.0)
        elif held in chance:
            total += task.reward * chance[held]
        elif not dead:  # R-056: an unfinished task pays nothing
            total += task.reward * done / need * w["task_partial_weight"]
    if has_building(t, state.held_buildings, seat, "office"):
        total += len(state.held_tasks[seat]) * building_param(t, "office", "money_per_task_card")
    return float(total)


def _craft_value(state: LignumState, t: SetupTables, seat: int, w: Weights) -> float:
    """Craftwork sets (R-105): 2-4 identical tokens sell at the set price; jokers join the
    largest group; a lone token is worth a share of half the smallest set price."""
    held = state.held_craft[seat]
    jokers = held[len(CRAFT_ORDER) - 1]
    groups = sorted((held[x] for x in range(len(CRAFT_ORDER) - 1) if held[x]), reverse=True)
    if groups:
        groups[0] += jokers
    elif jokers >= 2:
        groups = [jokers]
    total = 0.0
    for size in groups:
        if size >= 2:
            total += t.craft_set_prices[min(size, 4) - 2]
        else:
            total += t.craft_set_prices[0] / 2 * w["craft_single_discount"]
    return total * w["craft_discount"]


def _winter_weight(rounds_ahead: int, w: Weights) -> float:
    closeness = max(0.0, 1.0 - rounds_ahead / w["winter_horizon"])
    return w["winter_min_weight"] + (1.0 - w["winter_min_weight"]) * closeness


def _winter_cost(state: LignumState, t: SetupTables, seat: int, vw: Weights) -> float:
    """Dollars of feeding / heating shortfall still ahead (R-071..R-073)."""
    owed = 0.0
    now_feed = now_heat = False  # payments of the winter in progress that are still ahead
    if state.phase == PHASE_SF:
        pos, cur = state.wint.index(seat), state.w_turn
        now_feed = state.pay == FEED and pos > cur
        now_heat = pos > cur or state.pay == FEED
        owed = float(min(state.sf_due, state.money[seat])) if pos == cur else 0.0  # D9 forgiveness
    draws = state.draws.winter
    cost = owed
    first = True
    store = sum(state.store[seat])
    # Heat that unmilled wood still upstream can become (v2 provisioning; 0 credit = off).
    credit_saw = vw.get("heat_credit_sawing", 0.0)
    credit_pile = vw.get("heat_credit_woodpile", 0.0)
    saw_units = pile_units = 0.0
    if credit_saw or credit_pile:
        saw_units = float(sum(state.sawing[seat][k] * t.sawing_yield[k] for k in range(3)))
        pile_units = float(sum(state.woodpile[seat][k] * t.sawing_yield[k] for k in range(3)))
    for year, wr in enumerate(t.winter_rounds):
        if year >= len(draws):
            break
        current = wr == state.round and state.phase >= PHASE_N5
        if current:
            pending_feed, pending_heat = now_feed, now_heat
        elif wr > state.round or (wr == state.round):
            pending_feed = pending_heat = True
        else:
            continue
        w = draws[year]
        req_food, req_heat = t.winter_req[year][w // 2][w % 2]
        food_due = req_food + state.joiners[seat] * t.joiner_food
        if has_building(t, state.held_buildings, seat, "storeroom"):
            food_due = max(0, food_due - building_param(t, "storeroom", "winter_food_reduction"))
        weight = 1.0 if current else _winter_weight(max(0, wr - state.round), vw)
        missing = 0
        if pending_feed:
            missing += max(0, food_due - (state.food[seat] if first else 0))
        weight_food = weight
        if vw.get("heat_full_weight", 0):  # milled wood in the storage is kept: never wasted
            weight = 1.0
        heat_missing = 0.0
        if pending_heat:
            short: float = max(0, req_heat - store)
            store = max(0, store - req_heat)
            sawn = wr == state.round and state.phase >= PHASE_N3
            if short and not sawn:
                got = min(short, saw_units)
                saw_units -= got
                short -= got * credit_saw
                if wr > state.round:
                    more = min(short, pile_units)
                    pile_units -= more
                    short -= more * credit_pile
            heat_missing += short
        cost += (weight_food * missing + weight * heat_missing) * t.shortfall_unit
        first = False
    return cost


def _future_income(state: LignumState, t: SetupTables, seat: int, w: Weights) -> float:
    """R-079: $ per joiner at each later seasonal round start."""
    last = max(t.winter_rounds)
    starts = sum(1 for r in range(state.round + 1, last + 1) if r not in t.winter_rounds)
    return state.joiners[seat] * t.joiner_income * starts * w["joiner_income_discount"]


def value(state: LignumState, seat: int, w: Weights | None = None) -> float:
    """Expected final dollars of ``seat`` in ``state`` (exact at terminal states, R-083).
    ``w`` is a profile's ``value:`` weights; default is the working ``heuristic`` profile."""
    if state.phase == PHASE_END:
        return float(state.final[seat])
    if w is None:
        w = value_weights()
    if "value_fit" in w:  # v5: some components come from the fitted regression (lignum.bots.fitted)
        from lignum.bots.fitted import fitted_value

        return fitted_value(state, seat, w)
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    # From the SF phase of the last winter on, only R-081 items score (leftovers are worth $0).
    dead = state.round >= t.winter_rounds[1] and state.phase >= PHASE_SF
    v = float(state.money[seat]) - t.loan_repay[state.loans[seat]]
    v += _wood_zone_value(state, t, seat, w)
    v += _joinery_value(state, t, seat, w)
    v += _task_value(state, t, seat, w, dead)
    if not dead:
        v += _craft_value(state, t, seat, w)
        v += w["plan_value"] * sum(1 for p in state.plans if p[0] == seat and p[3] >= state.round)
        v += w["building_value"] * len(state.held_buildings[seat])
    v += _future_income(state, t, seat, w)
    v -= _winter_cost(state, t, seat, w)
    return v


def value_diff(state: LignumState, seat: int, w: Weights | None = None) -> float:
    """``value`` of ``seat`` minus the mean value of the other seats."""
    others = [value(state, o, w) for o in range(state.n) if o != seat]
    return value(state, seat, w) - sum(others) / len(others)


def value_parts(state: LignumState, seat: int, w: Weights | None = None) -> dict[str, float]:
    """The hand-set ``value`` split into its components (diagnostic, for tools/collect_games.py;
    bots use ``value``). Keys: money, loan, wood, joinery, tasks (without Office), office, craft,
    plans, buildings, income, winter. Their sum equals ``value`` up to float rounding."""
    if state.phase == PHASE_END:
        return {"money": float(state.final[seat])}
    if w is None:
        w = value_weights()
    t = state._tables()  # pyright: ignore[reportPrivateUsage]
    dead = state.round >= t.winter_rounds[1] and state.phase >= PHASE_SF
    office = 0.0
    if has_building(t, state.held_buildings, seat, "office"):
        office = len(state.held_tasks[seat]) * building_param(t, "office", "money_per_task_card")
    live = not dead
    return {
        "money": float(state.money[seat]),
        "loan": -float(t.loan_repay[state.loans[seat]]),
        "wood": _wood_zone_value(state, t, seat, w),
        "joinery": _joinery_value(state, t, seat, w),
        "tasks": _task_value(state, t, seat, w, dead) - office,
        "office": office,
        "craft": _craft_value(state, t, seat, w) if live else 0.0,
        "plans": w["plan_value"]
        * sum(1 for p in state.plans if p[0] == seat and p[3] >= state.round)
        if live
        else 0.0,
        "buildings": w["building_value"] * len(state.held_buildings[seat]) if live else 0.0,
        "income": _future_income(state, t, seat, w),
        "winter": -_winter_cost(state, t, seat, w),
    }
