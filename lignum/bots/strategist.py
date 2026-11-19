"""Strategist: a fast, plan-driven scripted policy (no search, no Opus in the loop).

Distilled from the rules (base + Joinery and Buildings) and Opus game 0's play. The policy is
generic over cards: it reads the laid-out tasks, planned-work cards, buildings and winter cards from
the state and values them through one weight table ``W`` (tunable by self-play, see
``tools/tune_strategist.py``).

Strategy in brief:
- Tasks are the engine. Every task needs milled hardwood, so hardwood supply (area wood, winter
  bonus, PW Overtime) bounds how many tasks to take. Tasks are taken when the hardwood and the
  drying-stage timing make them finishable.
- Logs are reserved for open task slots by drying stage (stage s ready s+1 drying steps after the
  sale area); reserved logs are never sold and enter drying first.
- Winter food and heat are covered ahead of time (firewood sawn to the storage, food bought at $1
  against the $3 shortfall), loans only when a task or a forced payment needs them.
- Supply path: each round a budgeted plan fixes the workers, saws, food, task, joiner, building
  and planned work wanted; the route is chosen by the value of the stops, discounted by the risk
  of losing contested stops to the opponents.

Seat-local information only: picks of other seats are read only once revealed (TR onwards).
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pyspiel

from lignum import actions as A
from lignum.bots.base import bot_candidates
from lignum.constants import CLEARING_LOC, NUM_AREAS
from lignum.game import (
    PHASE_FS,
    PHASE_N1,
    PHASE_N2,
    PHASE_N3,
    PHASE_N4,
    PHASE_NB,
    PHASE_PK,
    PHASE_RS,
    PHASE_SF,
    PHASE_SP,
    PHASE_TR,
    PHASE_W1,
    PHASE_W2,
    PHASE_W3,
    PHASE_W4,
    PHASE_W5,
    PHASE_W6,
    PHASE_W7,
    PHASE_WS,
    LignumState,
)
from lignum.rules import (
    SPOT_NAMES,
    SetupTables,
    fodder_cost,
    has_building,
    plan_active,
    plan_options,
)

FW, SW, HW = 0, 1, 2
OPPS = (1, 2, 3, 5, 6, 7, 8)  # rounds with a tasks phase (round 8: winter N4)
SEASONAL = (1, 2, 3, 5, 6, 7)
LAST_OPP = len(OPPS) - 1
BOARD, SHINGLE, STAKE, REED, JOKER = range(5)
H_DRY, H_FOOD, H_WORK = 0, 1, 2

# Tunable weights (dollars unless noted). Self-play tuning perturbs these.
DEFAULT_WEIGHTS: dict[str, float] = {
    "hw_value": 8.0,  # a hardwood disk when a task needs it
    "hw_spare": 3.0,  # a hardwood disk otherwise (milled sells $5)
    "sw_value": 3.5,
    "fw_value": 3.0,
    "fw_heat": 3.0,  # a firewood disk while heat is short
    "food_short": 2.6,  # a food unit while the next winter is short
    "food_spare": 0.3,
    "token_dollar": 1.0,
    "token_saw": 1.0,
    "token_saw_spare": 0.4,
    "token_wagon": 0.6,
    "token_raft": 0.4,
    "token_sledge": 1.2,
    "token_craft": 1.0,
    "joiner_base": 1.5,
    "task_min_value": 4.0,
    "task_piece_cost": 1.5,
    "task_max_open": 2.0,
    "hw_board_rate": 0.2,  # hardwood expected from placement cards per remaining seasonal round
    "sw_board_rate": 0.45,  # softwood disks I can expect per remaining seasonal round
    "r8_hw": 0.8,  # round-8 winter bonus hardwood (times the chance the kit is ready)
    "overtime_value": 8.0,
    "heating_value": 2.0,
    "loan_task_value": 9.0,  # take a loan to fund a task worth at least this
    "keep_token": 0.85,
    "keep_joiner": 0.8,
    "keep_task": 0.92,
    "keep_building": 0.95,
    "contest_clearing": 0.75,
    "contest_weight": 0.3,
    "area_contest": 0.6,
    "pick_tau": 0.8,
    "first_bonus": 0.25,  # shared-area value when first in travel order (can cut first)
    "food_early": 0.0,  # share of the next winter's food kept two rounds before it
    "sw_mill_bonus": 2.0,  # milling softwood for the drying pipeline (> 0 enables it)
    "sw_need_bonus": 4.0,  # softwood disk while task slots still need softwood logs
    "storeroom": 3.0,
    "small_storage": 3.5,
    "office": 3.0,
    "small_joinery": 1.5,
    "drying_upgrade": 1.5,
    "inn": 2.0,
    "field": 0.8,
    "waterchannel": 0.8,
    "marketstand": 0.4,
    "small_workshop": 0.5,
}


def _round_opp(rnd: int) -> int:
    """Index in OPPS of the first tasks phase at or after round ``rnd``."""
    for i, r in enumerate(OPPS):
        if r >= rnd:
            return i
    return len(OPPS)


@dataclass
class Slot:
    slot: int
    task: int
    kind: int
    milled: int
    stage: int
    reward: int


@dataclass(frozen=True)
class RoundPlan:
    """A plan for one seat's round, set by a plan-level search (``lignum.bots.plan_search``).

    ``task``: None = the strategist's own choice, -1 = take no task this round, else the task to
    take (valued at least ``PLAN_TASK_VALUE`` so the route and money reserve go for it).
    ``area``: the cutting area to pick this round (None = own choice).
    ``then``: plans for later rounds (multi-round plan search), followed when their round comes.
    """

    round: int
    task: int | None = None
    area: int | None = None
    then: tuple[RoundPlan, ...] = ()

    def for_round(self, rnd: int) -> RoundPlan | None:
        if self.round == rnd:
            return self
        return next((q for q in self.then if q.round == rnd), None)


PLAN_TASK_VALUE = 10.0


@dataclass
class SlotPlan:
    """Reservation of current pieces for open task slots, and the logs still to be made."""

    # (zone, piece) -> count of current pieces reserved for slots
    reserved: dict[tuple[int, int], int] = field(default_factory=lambda: {})
    # logs still to make: (kind, stage, latest tasks-phase index, task); stage -1 = a disk
    needs: list[tuple[int, int, int, int]] = field(default_factory=lambda: [])
    dead: set[int] = field(default_factory=lambda: set[int]())  # tasks that cannot be finished
    storage_slot: Slot | None = None
    slot_src: dict[int, tuple[int, int]] = field(default_factory=lambda: {})  # slot -> (zone, p)

    def res(self, zone: int, piece: int) -> int:
        return self.reserved.get((zone, piece), 0)

    def need_logs(self, kind: int, latest_min: int = 0) -> int:
        return sum(1 for k, _, la, _ in self.needs if k == kind and la >= latest_min)


class Ctx:
    """Per-decision view of the acting seat (cheap; built once per ``choose``)."""

    def __init__(self, state: LignumState, seat: int, w: Mapping[str, float]) -> None:
        self.s = state
        self.me = seat
        self.w = w
        self.t: SetupTables = state._tables()  # pyright: ignore[reportPrivateUsage]
        self.rnd = state.round
        self.phase = state.phase
        self._slots: list[Slot] | None = None
        self._plan: SlotPlan | None = None
        # Tasks a plan schedules for this seat that it does not hold yet (set by the strategist
        # when ``reserve_planned``): their slots get wood in the slot plan, after held tasks.
        self.planned: tuple[int, ...] = ()

    # ---- holdings
    @property
    def money(self) -> int:
        return self.s.money[self.me]

    def bld(self, bid: str) -> bool:
        return has_building(self.t, self.s.held_buildings, self.me, bid)

    def saws(self) -> int:
        return self.s.equip[self.me][0]

    def wagons(self) -> int:
        return self.s.equip[self.me][1]

    def rafts(self) -> int:
        return self.s.equip[self.me][2]

    def sledges(self) -> int:
        return self.s.equip[self.me][3]

    def huts(self) -> tuple[int, int, int]:
        return self.s.huts[self.me]

    def zone_logs(self, zone: int) -> tuple[int, int, int]:
        if zone == 0:
            return self.s.sale_logs[self.me]
        d = self.s.dry[self.me][zone - 1]
        return (d[3], d[4], d[5])

    def zone_disks(self, zone: int) -> tuple[int, int, int]:
        if zone == 0:
            return self.s.sale[self.me]
        d = self.s.dry[self.me][zone - 1]
        return (d[0], d[1], d[2])

    def zone_count(self, zone: int, piece: int) -> int:
        k, m = piece // 2, piece % 2
        return (self.zone_logs(zone) if m else self.zone_disks(zone))[k]

    # ---- time
    def cur_opp(self) -> int:
        """Index of the next tasks phase (this round's if it is still ahead)."""
        if self.rnd in SEASONAL and self.phase > PHASE_W5 and self.phase <= PHASE_W7:
            return _round_opp(self.rnd + 1)
        if self.rnd == 8 and self.phase not in (
            PHASE_WS,
            PHASE_NB,
            PHASE_N1,
            PHASE_N2,
            PHASE_N3,
            PHASE_N4,
        ):
            return len(OPPS)
        return _round_opp(self.rnd)

    def seasonal_left(self, include_current: bool = True) -> int:
        return sum(1 for r in SEASONAL if r > self.rnd or (include_current and r == self.rnd))

    # ---- winter
    def winter_req(self, year: int) -> tuple[int, int]:
        wv = self.s.draws.winter[year]
        return self.t.winter_req[year][wv // 2][wv % 2]

    def winters_left(self) -> list[int]:
        """Years (0, 1) whose feeding is still ahead."""
        out: list[int] = []
        for y, r in enumerate(self.t.winter_rounds):
            if self.rnd < r or (
                self.rnd == r
                and self.phase in (PHASE_WS, PHASE_NB, PHASE_N1, PHASE_N2, PHASE_N3, PHASE_N4)
            ):
                out.append(y)
        return out

    def food_due(self, year: int) -> int:
        f = self.winter_req(year)[0] + self.s.joiners[self.me]
        if self.bld("storeroom"):
            f -= 1
        return max(0, f)

    def food_short(self) -> int:
        """Food still missing for the next winter."""
        ws = self.winters_left()
        if not ws:
            return 0
        return max(0, self.food_due(ws[0]) - self.s.food[self.me])

    def heat_short(self, next_only: bool = False) -> int:
        """Milled pieces still missing in the firewood storage for the remaining winters."""
        ws = self.winters_left()
        if not ws:
            return 0
        if next_only:
            ws = ws[:1]
        need = sum(self.winter_req(y)[1] for y in ws)
        return max(0, need - sum(self.s.store[self.me]))

    # ---- tasks
    def open_slots(self) -> list[Slot]:
        if self._slots is None:
            out: list[Slot] = []
            held = self.s.held_tasks[self.me]
            comp = self.t
            for i, (task, req, kind, milled, stage) in enumerate(comp.task_slots):
                if task in held and not (self.s.filled[task] >> req & 1):
                    out.append(Slot(i, task, kind, milled, stage, _reward(task)))
            self._slots = out
        return self._slots

    def planned_slots(self) -> list[Slot]:
        """Slots of ``planned`` tasks (not held yet, so none is filled)."""
        if not self.planned:
            return []
        return [
            Slot(i, task, kind, milled, stage, _reward(task))
            for i, (task, _req, kind, milled, stage) in enumerate(self.t.task_slots)
            if task in self.planned
        ]

    def plan_slots(self) -> list[Slot]:
        """Open slots of held tasks, then the slots of planned ones."""
        return self.open_slots() + self.planned_slots()

    def slot_plan(self) -> SlotPlan:
        if self._plan is None:
            self._plan = make_slot_plan(self)
        return self._plan


_REWARDS: dict[int, int] = {}
_TASK_REQS: dict[int, list[tuple[int, int, int]]] = {}


def _load_tasks() -> None:
    from lignum.components import load_components

    for i, task in enumerate(load_components().tasks):
        _REWARDS[i] = task.reward
        _TASK_REQS[i] = [
            (("firewood", "softwood", "hardwood").index(r.kind), int(r.milled), r.drying)
            for r in task.requirements
        ]


def _reward(task: int) -> int:
    if not _REWARDS:
        _load_tasks()
    return _REWARDS[task]


def _reqs(task: int) -> list[tuple[int, int, int]]:
    if not _TASK_REQS:
        _load_tasks()
    return _TASK_REQS[task]


def make_slot_plan(c: Ctx) -> SlotPlan:
    """Reserve current logs (by zone) for open slots, hardest stage first; list missing logs.

    Slots of planned tasks (``Ctx.planned``) come after every held slot, so they only take wood
    the held tasks do not need.

    A log in zone z (0 sale, 1..3 drying) at the next tasks phase index i reaches zone z+k at
    index i+k. Stage s >= 1 needs zone s+1; stage 0 takes the sale area or drying 1. Drying hut
    tokens can make up missing steps; the Small Storage piece fills any stage of its kind.
    """
    plan = SlotPlan()
    i = c.cur_opp()
    after_tasks = c.rnd in SEASONAL and c.phase in (PHASE_W6, PHASE_W7)
    avail: dict[tuple[int, int], int] = {}
    for z in range(4):
        for k in range(3):
            n = c.zone_logs(z)[k]
            if n:
                # After this round's tasks the drying areas advance (drying 3 is sold).
                zz = z + 1 if (after_tasks and z >= 1) else z
                if zz <= 3:
                    avail[(z, k)] = n
            d = c.zone_disks(z)[k]
            if d and z == 0:
                avail[(z, 10 + k)] = d  # unmilled disks in the sale area
    hut_steps = c.huts()[H_DRY]
    storage = c.s.small_storage[c.me]
    storage_kind = storage if 0 <= storage < 3 else -1

    def eff_zone(z: int) -> int:
        return z + 1 if (after_tasks and z >= 1) else z

    slots = sorted(c.open_slots(), key=lambda s: (-s.stage, -s.reward))
    slots += sorted(c.planned_slots(), key=lambda s: (-s.stage, -s.reward))
    for sl in slots:
        if not sl.milled:
            key = (0, 10 + sl.kind)
            if avail.get(key, 0) > 0:
                avail[key] -= 1
                plan.reserved[(0, 2 * sl.kind)] = plan.reserved.get((0, 2 * sl.kind), 0) + 1
                plan.slot_src[sl.slot] = (0, 2 * sl.kind)
            else:
                plan.needs.append((sl.kind, -1, LAST_OPP, sl.task))  # -1: an unmilled disk
            continue
        target = sl.stage + 1 if sl.stage >= 1 else 0
        best: tuple[int, int] | None = None
        for z in (3, 2, 1, 0):
            if avail.get((z, sl.kind), 0) <= 0:
                continue
            ez = eff_zone(z)
            if sl.stage == 0:
                ok = ez <= 1
                steps = 0
            else:
                steps = target - ez
                ok = steps >= 0 and i + steps <= LAST_OPP
                if steps >= 0 and i + steps > LAST_OPP and steps - (i + steps - LAST_OPP) >= 0:
                    ok = hut_steps >= i + steps - LAST_OPP
            if ok:
                best = (z, steps)
                break
        if best is not None:
            z, _ = best
            avail[(z, sl.kind)] -= 1
            plan.reserved[(z, 2 * sl.kind + 1)] = plan.reserved.get((z, 2 * sl.kind + 1), 0) + 1
            plan.slot_src[sl.slot] = (z, 2 * sl.kind + 1)
            continue
        if storage_kind == sl.kind and plan.storage_slot is None:
            plan.storage_slot = sl
            continue
        latest = LAST_OPP if sl.stage == 0 else LAST_OPP - (sl.stage + 1) + min(hut_steps, 2)
        if latest < i and not (c.bld("small_storage_area") and storage == -1):
            plan.dead.add(sl.task)
        plan.needs.append((sl.kind, sl.stage, latest, sl.task))
    if plan.dead:
        plan.needs = [n for n in plan.needs if n[3] not in plan.dead]
        for s_, (z, p) in list(plan.slot_src.items()):
            sl2 = next(x for x in slots if x.slot == s_)
            if sl2.task in plan.dead:
                plan.reserved[(z, p)] -= 1
                del plan.slot_src[s_]
    return plan


# ---------------------------------------------------------------- hardwood and task valuation


def hw_certain(c: Ctx) -> int:
    """Hardwood already mine (unreserved logs and disks) plus Overtime plans still to come."""
    me, s = c.me, c.s
    plan = c.slot_plan()
    n = 0
    for z in range(4):
        n += c.zone_logs(z)[HW] - plan.res(z, 5)
    n += s.woodpile[me][HW] + s.sawing[me][HW] + s.river[me][HW]
    for seat, card, _pair, target in s.plans:
        if seat == me and c.t.pw_ids[card] == "pw_overtime" and c.rnd < target <= 7:
            n += 1
    return n


def hw_supply(c: Ctx) -> float:
    """Hardwood (disks or unreserved logs) expected to reach me before the last tasks phase."""
    me, s = c.me, c.s
    plan = c.slot_plan()
    n = 0.0
    for z in range(4):
        n += c.zone_logs(z)[HW] - plan.res(z, 5)
    n += s.woodpile[me][HW] + s.sawing[me][HW] + s.river[me][HW]
    if c.phase == PHASE_TR or (c.phase in range(PHASE_W1, PHASE_W1 + 1)):
        n += 0.8 * s.wood[s.picks[me]][HW] if s.picks else 0
    for seat, card, _pair, target in s.plans:
        if seat == me and c.t.pw_ids[card] == "pw_overtime" and c.rnd < target <= 7:
            n += 1
    if c.rnd < 4 or (c.rnd == 4 and c.phase in (PHASE_WS, PHASE_NB)):
        n += 1  # winter bonus year 1
    n += c.w["r8_hw"] * r8_kit(c)  # winter bonus year 2 (stage-0 slot only)
    # future Overtime plans
    if any(c.t.pw_ids[card] == "pw_overtime" for card in s.pw_cards):
        mine = [p for p in s.plans if p[0] == me]
        pairs_left = c.t.pw_pairs - len(mine)
        rounds_left = sum(1 for r in SEASONAL if r > c.rnd and r <= 6)
        if c.phase == PHASE_TR and not any(p[3] - p[2] == c.rnd for p in mine):
            rounds_left += 1 if c.rnd <= 6 else 0
        n += 0.7 * min(pairs_left, rounds_left)
    n += c.w["hw_board_rate"] * sum(1 for r in SEASONAL if r > c.rnd)
    return n


def sw_supply_logs(c: Ctx) -> float:
    """Softwood logs expected: unreserved logs, 3 per owned disk, area and board softwood."""
    me, s = c.me, c.s
    plan = c.slot_plan()
    n = 0.0
    for z in range(4):
        n += c.zone_logs(z)[SW] - plan.res(z, 3)
    disks = s.woodpile[me][SW] + s.sawing[me][SW] + s.river[me][SW] + s.sale[me][SW]
    n += 3 * disks
    if c.phase == PHASE_TR and s.picks:
        n += 3 * 0.8 * s.wood[s.picks[me]][SW]
    elif c.rnd in SEASONAL and c.rnd < 7:
        n += 3 * 0.35 * min(2, sum(s.wood[a][SW] for a in range(NUM_AREAS)))
    n += 3 * c.w["sw_board_rate"] * sum(1 for r in SEASONAL if r > c.rnd and r <= 6)
    return n


def r8_kit(c: Ctx) -> float:
    """Chance the round-8 winter bonus hardwood can be sledged, sawn and placed: needs a sledge,
    a saw and a hut worker (the mill worker sledges, the hut worker saws)."""
    if c.rnd > 8 or (c.rnd == 8 and c.phase not in (PHASE_WS, PHASE_NB)):
        return 0.0
    has_hut = c.huts()[H_WORK] >= 1
    has_sledge = c.sledges() >= 1
    if has_hut and has_sledge:
        return 0.9
    if c.rnd >= 7:
        return 0.5 if has_hut else 0.1
    return 0.5 if has_hut else 0.3


def spare_huts(c: Ctx) -> int:
    """Hut workers free to spend now: from round 6 one is kept for the round-8 hardwood while
    a task is open."""
    n = c.huts()[H_WORK]
    if 6 <= c.rnd <= 7 and n and c.open_slots():
        n -= 1
    return n


def hw_committed(c: Ctx) -> int:
    return c.slot_plan().need_logs(HW, latest_min=-1)


def task_value(c: Ctx, task: int) -> float:
    """Expected net dollars of taking face-up ``task`` now."""
    if task in c.planned:  # its own planned wood must not count against it
        own = c
        c = Ctx(own.s, own.me, own.w)
        c.planned = tuple(t for t in own.planned if t != task)
    reqs = _reqs(task)
    reward = _reward(task)
    i = c.cur_opp()
    # The task would be held from this round's tasks phase on.
    storage_free = c.bld("small_storage_area") and c.s.small_storage[c.me] == -1
    can_get_storage = storage_free or (
        len(c.s.held_buildings[c.me]) < 2
        and c.t.building_ids.index("small_storage_area") in c.s.bld_supply
    )
    plan = c.slot_plan()
    hut = c.huts()[H_DRY]
    late = 0
    for _kind, _milled, stage in reqs:
        if stage == 0:
            continue
        latest = LAST_OPP - (stage + 1)
        if latest < i:
            late += 1
    if late > (1 if (storage_free or can_get_storage) else 0) + min(hut, 1):
        return -99.0
    hw_need = sum(1 for k, _, _ in reqs if k == HW)
    free_hw = hw_supply(c) - hw_committed(c)
    if free_hw >= hw_need + 0.5:
        p = 0.92
    elif free_hw >= hw_need:
        p = 0.75
    elif free_hw >= hw_need - 0.5:
        p = 0.45
    else:
        p = 0.12
    sw_need = sum(1 for k, _m, _ in reqs if k == SW)
    if sw_need:
        free_sw = sw_supply_logs(c) - c.slot_plan().need_logs(SW, latest_min=-1)
        if free_sw < sw_need:
            p *= 0.35 if free_sw < sw_need - 1 else 0.65
    if late:
        p *= 0.7
    open_tasks = len({sl.task for sl in c.open_slots()} - plan.dead)
    if open_tasks >= c.w["task_max_open"]:
        p *= 0.4 ** (open_tasks - c.w["task_max_open"] + 1)
    # Late in the game: pieces must be in hand.
    if i >= 5:
        have = 0
        for kind, milled, stage in reqs:
            if milled and any(c.zone_logs(z)[kind] for z in range(2)):
                have += 1
            elif kind == HW and stage == 0 and r8_kit(c) >= 0.5:
                have += r8_kit(c)
            elif not milled and c.zone_disks(0)[kind]:
                have += 1
        p *= 0.3 + 0.7 * have / len(reqs)
    cost = c.w["task_piece_cost"] * len(reqs) + c.t.price_location
    return reward * p - cost


# ---------------------------------------------------------------- the bot


class StrategistBot:
    """Scripted plan-driven policy. ``weights`` overrides entries of DEFAULT_WEIGHTS."""

    def __init__(self, weights: Mapping[str, float] | None = None, trace: bool = False) -> None:
        self.w: dict[str, float] = dict(DEFAULT_WEIGHTS)
        if weights:
            self.w.update(weights)
        self.trace = trace
        self.log: list[str] = []
        self._rng: random.Random | None = None
        # Per-seat round plans (plan-level search); empty = plain strategist.
        self.plans: dict[int, RoundPlan] = {}
        # Plan wood for tasks the round plan schedules but this seat does not hold yet.
        self.reserve_planned = False

    def _plan(self, c: Ctx) -> RoundPlan | None:
        p = self.plans.get(c.me)
        return p.for_round(c.rnd) if p is not None else None

    def _planned_tasks(self, c: Ctx) -> tuple[int, ...]:
        """Laid-out tasks the plan schedules for this seat: this round's (until it takes a task)
        and later rounds'."""
        p = self.plans.get(c.me)
        if p is None:
            return ()
        held = c.s.held_tasks[c.me]
        out: list[int] = []
        for q in (p, *p.then):
            if q.round < c.rnd or q.task is None or q.task < 0:
                continue
            if q.round == c.rnd and c.s.task_taken[c.me]:
                continue
            if q.task in c.s.task_row and q.task not in held and q.task not in out:
                out.append(q.task)
        return tuple(out)

    # ------------------------------------------------------------ entry
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        legal = list(state.legal_actions())
        if len(legal) == 1:
            return legal[0]
        seat = state.current_player()
        c = Ctx(state, seat, self.w)
        if self.reserve_planned:
            c.planned = self._planned_tasks(c)
        self._rng = rng
        try:
            a = self._dispatch(c, legal)
        except Exception:  # pragma: no cover - defensive: never crash a game
            if self.trace:
                raise
            a = None
        if a is None or a not in legal:
            a = self._fallback(state, legal, rng)
        return a

    def _fallback(self, state: LignumState, legal: list[int], rng: random.Random) -> int:
        for x in (A.DONE, A.END_TRIP):
            if x in legal:
                return x
        cands = [a for a in bot_candidates(state) if a != A.TAKE_LOAN] or legal
        return cands[0]

    def _dispatch(self, c: Ctx, legal: list[int]) -> int | None:
        ph = c.phase
        if ph == PHASE_SP:
            p = self._plan(c)
            if p is not None and p.area is not None and A.encode("PICK_AREA", p.area) in legal:
                return A.encode("PICK_AREA", p.area)
            return legal[0]
        if ph == PHASE_PK:
            return self._pick_area(c, legal, self._rng)
        if ph in (PHASE_RS, PHASE_WS):
            return A.TAKE_OVERTIME if A.TAKE_OVERTIME in legal else A.DONE
        if ph == PHASE_SF:
            return self._shortfall(c, legal)
        if ph == PHASE_FS:
            return self._final_sale(c, legal)
        # Hut build in progress
        if c.s.hb_open:
            return self._hut_build_step(c, legal)
        # Window actions (start of a turn): build huts, food huts, drying huts.
        w = self._window(c, legal)
        if w is not None:
            return w
        if ph == PHASE_TR:
            return self._travel(c, legal)
        fn = {
            PHASE_W1: self._w1,
            PHASE_W2: self._w2,
            PHASE_W3: self._w3,
            PHASE_W4: self._w4,
            PHASE_W5: self._w5,
            PHASE_W6: self._w6,
            PHASE_W7: self._w7,
            PHASE_NB: self._nb,
            PHASE_N1: self._n1,
            PHASE_N2: self._n2,
            PHASE_N3: self._w4,
            PHASE_N4: self._w5,
        }.get(ph)
        return fn(c, legal) if fn else None

    # ------------------------------------------------------------ area pick
    def area_value(self, c: Ctx, area: int, for_me: bool = True) -> float:
        fw, sw, hw = c.s.wood[area]
        food = c.s.area_food[area]
        w = self.w
        plan = c.slot_plan()
        hw_v = w["hw_value"] if (not for_me or plan.need_logs(HW) > 0) else w["hw_spare"] + 1
        fw_v = w["fw_heat"] if (for_me and c.heat_short() > 0) else w["fw_value"]
        sw_short = plan.need_logs(SW) - 3 * (
            c.s.woodpile[c.me][SW] + c.s.sawing[c.me][SW] + c.s.river[c.me][SW]
        )
        sw_v = w["sw_value"] + (w["sw_need_bonus"] if for_me and sw_short > 0 else 0)
        sw_list = [sw_v] + [w["sw_value"]] * max(0, sw - 1) if sw else []
        if for_me and sw_short > 3 and sw >= 2:
            sw_list[1] = sw_v
        pieces = sorted([hw_v] * hw + sw_list + [fw_v] * fw, reverse=True)
        cap = max(2, min(5, c.money // 2 + 2)) if for_me else 4
        return sum(pieces[:cap]) + 1.1 * food

    def _pick_area(self, c: Ctx, legal: list[int], rng: random.Random | None = None) -> int:
        """Area with the best expected value against a model of the opponents' picks: a blend
        of a generic wood model and a model of each opponent's own needs (public state)."""
        import math

        areas = [A.decode(act).params[0] for act in legal]
        p = self._plan(c)
        if p is not None and p.area in areas:
            return A.encode("PICK_AREA", p.area)
        vals = {a: self.area_value(c, a) for a in areas}
        tau = self.w["pick_tau"]
        q = [0.0] * NUM_AREAS  # chance that some opponent picks each area
        for e in range(c.s.n):
            if e == c.me:
                continue
            oc = Ctx(c.s, e, self.w)
            for model, wt in ((False, 0.5), (True, 0.5)):
                ov = [self.area_value(oc, a, for_me=model) for a in range(NUM_AREAS)]
                m = max(ov)
                ex = [math.exp((v - m) / tau) for v in ov]
                z = sum(ex)
                for a in range(NUM_AREAS):
                    q[a] = min(1.0, q[a] + wt * ex[a] / z)
        # Shared area: whoever reaches the clearing first cuts first; the seat first in travel
        # order can always get there first.
        first = c.s.turn_order[0] == c.me
        share = self.w["area_contest"] + (self.w["first_bonus"] if first else 0.0)
        share = min(share, 1.0)
        best_a = max(areas, key=lambda a: (vals[a] * (1 - (1 - share) * q[a]), -a))
        return A.encode("PICK_AREA", best_a)

    # ------------------------------------------------------------ round plan (travel)
    def _round_plan(self, c: Ctx) -> dict[str, Any]:
        """What this round's wood work needs, budgeted by money (recomputed every decision,
        counting workers already hired)."""
        s, me, w = c.s, c.me, self.w
        plan = c.slot_plan()
        area = s.picks[me]
        fw, sw, hw = s.wood[area]
        rivals = [e for e in range(s.n) if e != me and s.picks[e] == area]
        opp_first = [e for e in rivals if e in s.clearing]
        avail = [fw, sw, hw]
        for e in opp_first:  # an earlier seat in my area cuts the best pieces first
            take = s.hired_w[e] + 1
            for k in (HW, SW, FW):
                d = min(take, avail[k])
                avail[k] -= d
                take -= d
        heat_short = c.heat_short()
        hw_need = plan.need_logs(HW) > 0
        sw_logs_needed = plan.need_logs(SW)

        def disk_v(k: int, heat_left: int) -> float:
            if k == HW:
                return w["hw_value"] if hw_need else w["hw_spare"] + 2
            if k == SW:
                return w["sw_value"] + (w["sw_need_bonus"] if sw_logs_needed else 0)
            if heat_left > 0 and (c.rnd >= 5 or c.heat_short(next_only=True) > 0):
                return max(w["fw_value"], w["fw_heat"] * min(4, heat_left) / 2)
            return w["fw_heat"] if heat_left > 0 else w["fw_value"]

        heat_left = heat_short - 4 * (s.sawing[me][FW] + s.river[me][FW])
        pieces: list[tuple[float, int, bool]] = []  # (value, kind, needs a cutter)
        pile = s.woodpile[me]
        for k in (HW, SW, FW):
            for _ in range(pile[k]):
                pieces.append((disk_v(k, heat_left) + 0.3, k, False))
                if k == FW:
                    heat_left -= 4
            for _ in range(avail[k]):
                pieces.append((disk_v(k, heat_left), k, True))
                if k == FW:
                    heat_left -= 4
        pieces.sort(key=lambda x: -x[0])
        # Sawing this round: hardwood always; softwood for task logs; firewood for heat.
        to_saw = [0, 0, 0]
        arriving = [s.sawing[me][k] + s.river[me][k] for k in range(3)]
        # Reserve money for the stop purchases that come first in value.
        reserve = 0
        if not s.task_taken[me] and s.task_row:
            _t, tv = self._best_task(c)
            if tv >= w["task_min_value"]:
                reserve += 1
        hw_disks = s.sawing[me][HW] + s.river[me][HW] + s.woodpile[me][HW] + avail[HW]
        reserve += max(0, min(hw_disks, 2) - c.saws())
        reserve += self._essential(c)
        free = (0 if s.mill_used[me] else 1) + spare_huts(c)
        cutters = s.hired_w[me]
        bearers = s.hired_b[me]
        wagon_cap = 0
        if c.wagons() and (
            s.fodder3[me] or s.fodder2[me] or (s.path_fodder > 0 and not s.fodder_bought[me])
        ):
            wagon_cap = 3 if (s.fodder3[me] or not s.fodder2[me]) else 2
        budget = c.money - reserve
        hire_c = hire_b = 0
        wagon_used = 0
        chosen: list[int] = []
        for v, k, needs_cut in pieces:
            cost = 0
            use_c = use_b = ""
            if needs_cut:
                if cutters > 0:
                    use_c = "have"
                elif free > 0:
                    use_c = "free"
                else:
                    use_c = "pay"
                    cost += 1
            if wagon_cap and 0 < wagon_used < wagon_cap:
                use_b = "wagon"
            elif bearers > 0:
                use_b = "have"
            elif free - (1 if use_c == "free" else 0) > 0:
                use_b = "free"
            else:
                use_b = "pay"
                cost += 1
            spendable = budget + (reserve if v >= 5 else 0)
            if v - cost < 0.6 or spendable < cost:
                continue
            budget -= cost
            if use_c == "have":
                cutters -= 1
            elif use_c == "free":
                free -= 1
            elif use_c == "pay":
                hire_c += 1
            if use_b == "wagon":
                wagon_used += 1
            elif use_b == "have":
                bearers -= 1
                if wagon_cap and wagon_used == 0:
                    wagon_used = 1
            elif use_b == "free":
                free -= 1
                if wagon_cap and wagon_used == 0:
                    wagon_used = 1
            else:
                hire_b += 1
                if wagon_cap and wagon_used == 0:
                    wagon_used = 1
            chosen.append(k)
        bought = {"food": 0, "task": 1 if reserve else 0}
        moved = [arriving[k] + chosen.count(k) for k in range(3)]
        pot = self._saw_targets(c, arriving=True, potential=True)
        to_saw = [min(moved[k], pot[k]) for k in range(3)]
        n_saw = sum(to_saw)
        keep_saw = 1 if (c.rnd == 7 and c.huts()[H_WORK] >= 1) else 0
        saws_needed = max(0, min(n_saw + keep_saw, c.t.max_saws) - c.saws())
        sawyer_free = 1 if (s.hired_s[me] == 0 and s.path_sf > 0) else 0
        sawers_have = s.hired_s[me] + sawyer_free + max(0, free)
        paid_sawyer = 1 if (n_saw > sawers_have and s.path_sp > 0 and s.hired_s[me] <= 1) else 0
        uses_wagon = wagon_used >= 2
        return {
            "cutters": hire_c,
            "bearers": hire_b,
            "cut": chosen,
            "n_saw": n_saw,
            "to_saw": to_saw,
            "paid_sawyer": paid_sawyer,
            "saws_needed": saws_needed,
            "budget_left": budget,
            "food_buy": bought["food"],
            "task_ok": bought["task"] > 0,
            "heat_short": heat_short,
            "contest": bool(rivals) and not opp_first,
            "contest_value": w["contest_weight"]
            * sum(sorted((v for v, _k, nc in pieces if nc), reverse=True)[:2])
            if rivals
            else 0.0,
            "wagon": uses_wagon,
        }

    # ------------------------------------------------------------ travel
    def loc_kind(self, c: Ctx, number: int) -> str:
        for num, kind, _cap in c.t.locations:
            if num == number:
                return kind
        return "clearing"

    def _token_value(self, c: Ctx, y: int, rp: dict[str, Any]) -> float:
        name = SPOT_NAMES[y]
        w = self.w
        if name == "dollar":
            return w["token_dollar"]
        if name == "food":
            return w["food_short"] if c.food_short() > 0 else w["food_spare"] + 0.4
        if name == "saw":
            if c.saws() >= c.t.max_saws:
                return -1.0
            return w["token_saw"] if rp["saws_needed"] > 0 else w["token_saw_spare"]
        if name == "wagon":
            return w["token_wagon"]
        if name == "raft":
            return w["token_raft"] + (0.6 if c.rnd == 7 else 0)
        if name == "sledge":
            winters = c.winters_left()
            return w["token_sledge"] if winters and c.sledges() < len(winters) else 0.2
        if name == "x_marker":
            return -1.0
        # craftwork
        x = y - SPOT_NAMES.index("board")
        held = c.s.held_craft[c.me]
        v = w["token_craft"]
        if c.rnd >= 7:
            v *= 0.6
        if x == REED and not c.bld("small_workshop"):
            v = 0.5 if held[REED] >= 1 else 0.3
        elif x in (BOARD, SHINGLE, STAKE) and held[x] == 0:
            v += 0.4
        elif x == JOKER:
            v += 0.5
        return v

    def _best_building(self, c: Ctx) -> tuple[int, float]:
        best, best_v = -1, 0.0
        n_tasks = len(c.s.held_tasks[c.me])
        for b in c.s.bld_supply:
            bid = c.t.building_ids[b]
            v = self.w.get(bid, 0.5)
            if bid == "drying_area_upgrade":
                v = self.w["drying_upgrade"]
            if bid == "office":
                v = (
                    self.w["office"]
                    * (0.6 + 0.4 * min(n_tasks, 3) / 2)
                    * (1 if c.rnd <= 6 else 0.8)
                )
            if bid == "storeroom":
                v = self.w["storeroom"] * len(c.winters_left()) / 2
            if bid == "small_storage_area":
                v = self.w["small_storage"] * (1.0 if c.rnd <= 6 else 0.4)
            if bid == "small_joinery":
                v = self.w["small_joinery"] * (1 + c.s.joiners[c.me]) / 2
            if bid == "inn":
                mine = [p for p in c.s.plans if p[0] == c.me]
                v = self.w["inn"] * (c.t.pw_pairs - len(mine)) / 2
            if v > best_v:
                best, best_v = b, v
        return best, best_v

    def _plan_value(self, c: Ctx, card: int, pair: int) -> float:
        pid = c.t.pw_ids[card]
        target = c.rnd + pair
        w = self.w
        if pid == "pw_overtime":
            if target in (2, 3, 5, 6, 7):
                return w["overtime_value"] - 0.2 * pair
            if target == 4:
                return w["overtime_value"] - 1.5
            return 0.5
        if pid == "pw_heating_supply":
            need = c.heat_short()
            if need <= 0:
                return 0.2
            v = w["heating_value"] * min(2, (need + 3) // 4)
            if target in (4, 8):
                v *= 0.5
            if target in (2, 6) or (target == 5 and c.heat_short(next_only=True) == 0):
                v += 0.5
            return v
        if pid == "pw_cutting":
            return 2.0 if target in SEASONAL else 0.0
        if pid == "pw_sawing":
            return 1.5 if target in SEASONAL else 0.8
        if pid == "pw_log_driving":
            return 2.5 if target == 7 else 1.5
        if pid == "pw_drying":
            return 1.5 if target <= 6 else 0.3
        if pid == "pw_food_supply":
            return 0.8 + 1.0 * min(c.rafts(), 2)
        if pid == "pw_trade":
            return 0.4 + 2.0 * min(2, c.rafts() + c.wagons() + max(0, c.sledges() - 1)) / 2
        if pid == "pw_craftwork":
            return 1.0
        if pid == "pw_hut_construction":
            return 0.8
        return 0.0

    def _best_plan(self, c: Ctx, money: int) -> tuple[tuple[int, int] | None, float]:
        best, best_v = None, 0.0
        for card, pair, cost in plan_options(c.t, c.s, c.me):
            if cost > money:
                continue
            v = self._plan_value(c, card, pair) - cost
            if v > best_v:
                best, best_v = (card, pair), v
        return best, best_v

    def _joiner_value(self, c: Ctx) -> float:
        if c.s.path_joiner <= 0 or c.s.joiners[c.me] >= c.t.joiner_spaces:
            return 0.0
        incomes = sum(1 for r in SEASONAL if r > c.rnd)
        winters = len(c.winters_left())
        v = incomes - winters * 1.0 + self.w["joiner_base"]
        if c.rnd >= 6:
            v -= 1.0
        return v

    def _essential(self, c: Ctx) -> int:
        """Money to keep for the coming winter: food still missing (bought at $1), spread over
        the seasonal rounds left before it."""
        ws = c.winters_left()
        if not ws:
            return 0
        nxt = c.t.winter_rounds[ws[0]]
        left = sum(1 for r in SEASONAL if c.rnd <= r < nxt)
        fs = c.food_short()
        if left <= 1:
            return fs
        if left == 2:
            return int(fs * self.w["food_early"])
        return 0

    def _free_money(self, c: Ctx) -> int:
        return c.money - self._essential(c)

    def _best_task(self, c: Ctx) -> tuple[int, float]:
        p = self._plan(c)
        if p is not None and p.task is not None:
            if p.task < 0:
                return -1, -1e9
            if p.task in c.s.task_row:  # else taken by another seat: own choice
                return p.task, max(task_value(c, p.task), PLAN_TASK_VALUE)
        best, best_v = -1, -1e9
        for task in c.s.task_row:
            v = task_value(c, task)
            if v > best_v:
                best, best_v = task, v
        return best, best_v

    def _market_value(self, c: Ctx, rp: dict[str, Any]) -> float:
        v = 0.0
        if rp["saws_needed"] > 0 and c.saws() < c.t.max_saws and c.money >= 1:
            v += 3.0 * min(rp["saws_needed"], 2, c.money)
        fs = c.food_short()
        ess = self._essential(c)
        if fs > 0 and ess > 0:
            v += 2.0 * min(ess, c.money)
        elif fs > 0 and c.money >= 4:
            v += 1.0 * min(fs, c.money - 3)
        if self._sets_to_sell(c):
            v += 2.0
        return v

    def _stop_values(self, c: Ctx, rp: dict[str, Any]) -> dict[int, tuple[float, float]]:
        """For each reachable location: (value, keep probability if visited later)."""
        s, me = c.s, c.me
        here = s.foreman[me]
        out: dict[int, tuple[float, float]] = {}
        opp_behind = [s.foreman[e] for e in range(s.n) if e != me and s.foreman[e] != CLEARING_LOC]
        for number, kind, cap in c.t.locations:
            if number <= here:
                continue
            if sum(1 for f in s.foreman if f == number) >= cap:
                continue
            threat = any(f < number for f in opp_behind)
            v = 0.0
            keep = 1.0
            if kind == "token_spot":
                y = s.path_tokens[c.t.token_spots.index(number)]
                if y < 0:
                    continue
                v = self._token_value(c, y, rp)
                keep = self.w["keep_token"] if threat else 1.0
            elif kind == "bearers":
                v = 3.0 * rp["bearers"] if s.path_b > 0 and c.money >= 1 else 0
            elif kind == "woodcutters":
                v = 3.0 * rp["cutters"] if s.path_w > 0 and c.money >= 1 else 0
            elif kind == "sawyers":
                if s.hired_s[me] == 0 and s.path_sf > 0 and rp["n_saw"] >= 1:
                    v = 2.0 + 1.5 * min(rp["n_saw"] - 1, 2) + (1.0 if rp["paid_sawyer"] else 0)
            elif kind == "fodder":
                if (
                    c.wagons()
                    and not s.fodder3[me]
                    and not s.fodder_bought[me]
                    and s.path_fodder > 0
                    and len(s.woodpile[me])
                    and sum(s.woodpile[me]) + len(rp["cut"]) >= 3
                ):
                    v = 1.5 if fodder_cost(c.t, s, me) <= c.money else 0
            elif kind == "planned_work":
                best, bv = self._best_plan(c, max(0, self._free_money(c)))
                v = bv if best and bv >= 1.0 else 0
            elif kind == "buildings":
                if len(s.held_buildings[me]) < c.t.building_spaces:
                    _, v = self._best_building(c)
                    keep = self.w["keep_building"] if threat else 1.0
            elif kind == "tasks":
                if not s.task_taken[me] and s.task_row:
                    _task, tv = self._best_task(c)
                    afford = c.money >= 1 or (s.loans[me] == 0 and tv >= self.w["loan_task_value"])
                    if tv >= self.w["task_min_value"] and afford:
                        v = tv
                        keep = self.w["keep_task"] if threat else 1.0
            elif kind == "joiner":
                v = self._joiner_value(c)
                keep = self.w["keep_joiner"] if threat else 1.0
            elif kind == "market":
                v = self._market_value(c, rp)
                if c.money < 1 and not self._sets_to_sell(c):
                    v = 0
            if v > 0.05:
                out[number] = (v, keep)
        return out

    def _travel(self, c: Ctx, legal: list[int]) -> int | None:
        s = c.s
        if s.visit_loc:
            return self._visit(c, legal)
        rp = self._round_plan(c)
        stops = self._stop_values(c, rp)
        moves = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "MOVE_TO"}
        clearing_v = rp["contest_value"] if rp["contest"] else 0.0
        cl_keep = self.w["contest_clearing"]
        order = sorted(stops)
        # DP over routes: best[j][k] = best value of the rest of a route that just stopped at
        # order[j] after k earlier stops; each stop's value is discounted by keep**k.
        n_st = len(order)
        memo: dict[tuple[int, int], float] = {}

        def rest(j: int, k: int) -> float:
            key = (j, k)
            if key in memo:
                return memo[key]
            v = clearing_v * cl_keep**k
            for jj in range(j + 1, n_st):
                val, keep = stops[order[jj]]
                v = max(v, val * keep**k + rest(jj, k + 1))
            memo[key] = v
            return v

        best_n, best_v = CLEARING_LOC, clearing_v
        for j, n in enumerate(order):
            if n not in moves:
                continue
            v = stops[n][0] + rest(j, 1)
            if v > best_v:
                best_n, best_v = n, v
        if best_n not in moves:
            best_n = CLEARING_LOC
        return moves.get(best_n)

    def _visit(self, c: Ctx, legal: list[int]) -> int | None:
        s = c.s
        kind = self.loc_kind(c, s.visit_loc)
        rp = self._round_plan(c)
        done = A.DONE if A.DONE in legal else None
        if kind == "bearers":
            # rp is recomputed with money already spent: hire while the plan still wants more.
            want = rp["bearers"]
            if A.HIRE_BEARER in legal and want > 0:
                return A.HIRE_BEARER
            return done if done is not None else (A.HIRE_BEARER if A.HIRE_BEARER in legal else None)
        if kind == "woodcutters":
            if A.HIRE_WOODCUTTER in legal and rp["cutters"] > 0:
                return A.HIRE_WOODCUTTER
            return (
                done
                if done is not None
                else (A.HIRE_WOODCUTTER if A.HIRE_WOODCUTTER in legal else None)
            )
        if kind == "sawyers":
            if s.visit_n == 0 and A.HIRE_SAWYER in legal:
                return A.HIRE_SAWYER
            if A.HIRE_SAWYER in legal and rp["paid_sawyer"] and c.money >= 2:
                return A.HIRE_SAWYER
            return done
        if kind == "fodder":
            return A.encode("BUY_FODDER") if A.BUY_FODDER in legal else None
        if kind == "tasks":
            task, tv = self._best_task(c)
            act = A.encode("TAKE_TASK", task) if task >= 0 else None
            if act in legal:
                return act
            if A.TAKE_LOAN in legal and c.money < 1 and tv >= self.w["loan_task_value"]:
                return A.TAKE_LOAN
            return None
        if kind == "buildings":
            b, _ = self._best_building(c)
            act = A.encode("CHOOSE_BUILDING", b)
            return act if act in legal else None
        if kind == "planned_work":
            best, _ = self._best_plan(c, max(0, self._free_money(c)))
            if best:
                act = A.encode("PLAN_WORK", best[0], best[1] - 1)
                if act in legal:
                    return act
            return None
        if kind == "market":
            return self._market(c, legal, rp)
        return done

    def _sets_to_sell(self, c: Ctx) -> list[int]:
        held = c.s.held_craft[c.me]
        late = c.rnd >= 7
        legal_like: list[int] = []
        for x in range(4):
            n = held[x]
            if n >= 2:
                spare = n - (0 if x == REED or late else 1)
                if x == REED and not c.bld("small_workshop"):
                    spare = n
                if spare >= 2:
                    legal_like.append(A.encode("SELL_SET", x, min(spare, 4), 0))
        if late and held[JOKER] >= 1:
            for x in range(4):
                if held[x] >= 1:
                    legal_like.append(A.encode("SELL_SET", x, min(held[x] + 1, 4), 1))
        if late and held[JOKER] >= 2:
            legal_like.append(A.SELL_SET_JOKERS)
        return legal_like

    def _market(self, c: Ctx, legal: list[int], rp: dict[str, Any]) -> int | None:
        for a in self._sets_to_sell(c):
            if a in legal:
                return a
        me = c.me
        if A.BUY_SAW in legal and rp["saws_needed"] > 0:
            return A.BUY_SAW
        fs = c.food_short()
        if (
            A.BUY_FOOD in legal
            and fs > 0
            and (c.rnd in (3, 7) or self._essential(c) > 0 or c.money >= 4)
        ):
            return A.BUY_FOOD
        for e, slot in ((0, 2), (2, 1), (1, 3)):  # PW Trade: spare rafts, wagons, sledges
            a = A.encode("SELL_EQUIP", e)
            if a in legal:
                keep = len(c.winters_left()) if slot == 3 else 0
                if c.s.equip[me][slot] > keep:
                    return a
        return A.DONE if A.DONE in legal else None

    # ------------------------------------------------------------ huts
    def _window(self, c: Ctx, legal: list[int]) -> int | None:
        s = c.s
        names = {A.decode(a).name for a in legal}
        if "BUILD_HUT" in names:
            if A.encode("BUILD_HUT", 0) in legal:
                return A.encode("BUILD_HUT", 0)
            if A.encode("BUILD_HUT", 1) in legal:
                return A.encode("BUILD_HUT", 1)
        if "HUT_FOOD" in names:
            best, best_f = None, 0
            for a in legal:
                d = A.decode(a)
                if d.name == "HUT_FOOD":
                    f = s.area_food[d.params[0]]
                    if f > best_f:
                        best, best_f = a, f
            urgent = c.phase in (PHASE_N1, PHASE_N2, PHASE_N3, PHASE_N4, PHASE_NB)
            if best is not None and (best_f >= 2 or (urgent and best_f >= 1 and c.food_short())):
                return best
        if "HUT_DRY" in names:
            a = self._hut_dry(c, legal)
            if a is not None:
                return a
        return None

    def _hut_dry(self, c: Ctx, legal: list[int]) -> int | None:
        s = c.s
        final = c.rnd == 8 and c.phase == PHASE_N4
        plan = c.slot_plan()
        # Advance a reserved log that would miss its slot otherwise, or (round 8) gain value.
        for sl in sorted(c.open_slots(), key=lambda x: -x.reward):
            src = plan.slot_src.get(sl.slot)
            if src is None or not sl.milled or sl.stage == 0:
                continue
            z, p = src
            target = sl.stage + 1
            if z >= target:
                continue
            i = c.cur_opp()
            steps = target - z
            if final or i + steps > LAST_OPP or (c.rnd == 7 and c.phase >= PHASE_W5):
                a = A.encode("HUT_DRY", z, p)
                if a in legal:
                    return a
        if final:
            # Spend remaining tokens for +$1 each: drying 2 -> 3 and 1 -> 2 (unreserved pieces).
            for z, gain in ((2, 1), (1, 1)):
                for p in (5, 3, 1, 4, 2, 0):
                    a = A.encode("HUT_DRY", z, p)
                    if a in legal and gain > 0:
                        return a
        _ = s
        return None

    def _hut_build_step(self, c: Ctx, legal: list[int]) -> int | None:
        tok = [a for a in legal if A.decode(a).name == "HUT_TOKEN"]
        if tok:
            pref = (STAKE, BOARD, SHINGLE, REED, JOKER)
            for x in pref:
                a = A.encode("HUT_TOKEN", x)
                if a in legal:
                    return a
        areas = [a for a in legal if A.decode(a).name == "HUT_AREA"]
        if areas:
            want = self._hut_areas(c)
            done = len(c.s.hb_area)
            target = want[done] if done < len(want) else H_WORK
            a = A.encode("HUT_AREA", target)
            if a in legal:
                return a
            return areas[-1]
        return None

    def _hut_areas(self, c: Ctx) -> list[int]:
        size = len(c.s.hb_tok) if c.s.hb_tok else 3
        size = max(size, 2)
        plan = c.slot_plan()
        staged = sum(1 for sl in c.open_slots() if sl.milled and sl.stage >= 1)
        risky = sum(1 for n in plan.needs if n[1] >= 1)
        dry = min(2, risky + (1 if staged else 0))
        food = 0
        if c.food_short() >= 2 or (len(c.winters_left()) >= 1 and c.rnd >= 5):
            food = 1
        areas = [H_DRY] * dry + [H_FOOD] * food
        while len(areas) < size:
            areas.append(H_WORK)
        areas = sorted(areas[:size])
        return areas

    # ------------------------------------------------------------ wood work
    def _later_worker_need(self, c: Ctx, after_phase: int) -> int:
        """Workers the seat still needs after ``after_phase`` this round beyond hired ones."""
        s, me = c.s, c.me
        need = 0
        if after_phase < PHASE_W3:
            pile = sum(s.woodpile[me])
            cap_wagon = 0
            if c.wagons() and (s.fodder3[me] or s.fodder2[me]):
                cap_wagon = 3 if s.fodder3[me] else 2
            carriers = s.hired_b[me] - s.bear_used[me]
            movable = pile + (self._cut_plan_count(c) if after_phase < PHASE_W1 + 1 else 0)
            if cap_wagon and carriers >= 1:
                movable -= cap_wagon - 1
            need += max(0, movable - carriers)
        if after_phase < PHASE_W4:
            disks = sum(self._saw_targets(c))
            sawyers = s.hired_s[me] - s.saw_used[me]
            need += max(0, min(disks, c.saws()) - sawyers)
        return need

    def _cut_plan_count(self, c: Ctx) -> int:
        return 0

    def _w1(self, c: Ctx, legal: list[int]) -> int | None:
        s, me = c.s, c.me
        area = s.picks[me]
        moves = [a for a in legal if A.decode(a).name == "MOVE_CUT_TOKEN"]
        if moves:
            here = self.area_value(c, area) - 1.1 * s.area_food[area]
            best, bv = None, here + 1.5
            for a in moves:
                ar = A.decode(a).params[0]
                v = self.area_value(c, ar) - 1.1 * s.area_food[ar] - 1
                if v > bv:
                    best, bv = a, v
            if best is not None and (c.money >= 2 or bv > here + 3):
                return best
        takes = [a for a in legal if A.decode(a).name == "TAKE_WOOD"]
        if takes:
            # Prefer own area hardwood > softwood > firewood; outside area (PW Cutting) likewise.
            def tv(a: int) -> tuple[int, int]:
                ar, k = A.decode(a).params
                return ({HW: 3, SW: 2, FW: 1}[k], 1 if ar != area else 0)

            return max(takes, key=tv)
        assigns = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "ASSIGN_WORKER"}
        if not assigns:
            return A.DONE
        if 0 in assigns:
            return assigns[0]
        wood = s.wood[area]
        if not sum(wood):
            return A.DONE
        if 1 in assigns and not self._mill_needed_later(c, extra_pile=1):
            return assigns[1]
        if 2 in assigns and (wood[HW] or wood[SW]) and spare_huts(c) > 0:
            return assigns[2]
        return A.DONE

    def _mill_needed_later(self, c: Ctx, extra_pile: int = 0) -> bool:
        """Whether the mill worker should be kept for carrying or sawing later this round
        (``extra_pile``: pieces it would add to the woodpile by cutting now)."""
        s, me = c.s, c.me
        pile = list(s.woodpile[me])
        targets = self._saw_targets(c, arriving=True)
        to_saw = sum(targets)
        sawyers = s.hired_s[me] - s.saw_used[me] + spare_huts(c)
        if to_saw > sawyers:
            return True
        carriers = s.hired_b[me] - s.bear_used[me]
        if c.wagons() and (s.fodder3[me] or s.fodder2[me]) and carriers >= 1:
            carriers += 2 if s.fodder3[me] else 1
        return sum(pile) + extra_pile > carriers

    def _heating_next(self, c: Ctx) -> bool:
        return any(
            p[0] == c.me and c.t.pw_ids[p[1]] == "pw_heating_supply" and p[3] == c.rnd + 1
            for p in c.s.plans
        )

    def _dest(self, c: Ctx, kind: int) -> int:
        """0 sawing area, 1 sale area for a disk of ``kind`` arriving now."""
        if kind == HW:
            return 0
        s, me = c.s, c.me
        targets = self._saw_targets(c, arriving=True)
        in_saw = s.sawing[me][kind]
        if targets[kind] > in_saw:
            return 0
        return 1

    def _heat_disks_now(self, c: Ctx) -> int:
        """Firewood disks to mill for heat this round: the next winter's shortfall spread over
        the seasonal rounds left before it; in year 1 spare capacity also serves year 2."""
        ws = c.winters_left()
        if not ws:
            return 0
        nxt = c.t.winter_rounds[ws[0]]
        rounds_left = sum(1 for r in SEASONAL if c.rnd <= r < nxt)
        if c.rnd in (4, 8):
            return (c.heat_short(next_only=True) + 3) // 4
        short_next = c.heat_short(next_only=True)
        disks = (short_next + 3) // 4
        if rounds_left <= 0:
            return disks
        return -(-disks // rounds_left)

    def _saw_targets(self, c: Ctx, arriving: bool = False, potential: bool = False) -> list[int]:
        """Disks per kind to mill this round, within the sawing capacity (workers and saws).

        Counts disks in the sawing area plus, with ``arriving``, the woodpile and river disks
        that could still be brought there this round. ``potential`` (travel) assumes the free
        sawyer will be hired and saws bought.
        """
        s, me = c.s, c.me
        plan = c.slot_plan()
        workers = (s.hired_s[me] - s.saw_used[me]) + (0 if s.mill_used[me] else 1)
        workers += spare_huts(c)
        saws = c.saws()
        if potential:
            workers = max(s.hired_s[me], 1 if s.path_sf > 0 else 0) + 1 + spare_huts(c)
            saws = c.t.max_saws
        if c.rnd in (4, 8):
            workers = (0 if s.mill_used[me] else 1) + c.huts()[H_WORK]
        cap = min(workers, saws)
        if plan_active(c.t, s, me, "pw_sawing"):
            cap = min(workers * 2, saws * 2)
        if c.phase > PHASE_W4 and c.rnd not in (4, 8):
            return [0, 0, 0]
        have = [
            s.sawing[me][k] + ((s.woodpile[me][k] + s.river[me][k]) if arriving else 0)
            for k in range(3)
        ]
        if potential:
            area = s.picks[me]
            have = [have[k] + s.wood[area][k] for k in range(3)]
        out = [0, 0, 0]
        out[HW] = min(cap, have[HW])
        cap -= out[HW]
        fw_logs = plan.need_logs(FW)
        fw_need = max(self._heat_disks_now(c), (fw_logs + 3) // 4)
        sw_need = (plan.need_logs(SW) + 2) // 3
        urgent_heat = c.rnd in (3, 7, 4, 8)
        if plan_active(c.t, s, me, "pw_heating_supply"):
            fw_need = max(fw_need, -(-c.heat_short() // 6))
            urgent_heat = True
        if urgent_heat:
            out[FW] = min(cap, fw_need, have[FW])
            cap -= out[FW]
        out[SW] = min(cap, sw_need, have[SW])
        cap -= out[SW]
        if not urgent_heat:
            out[FW] = min(cap, fw_need, have[FW])
            cap -= out[FW]
        # Spare capacity: softwood for the drying pipeline, firewood for later heat.
        d_free = c.rnd in (1, 2, 3, 5) and sum(c.zone_logs(1)) == 0
        if cap > 0 and d_free and have[SW] > out[SW] and self.w["sw_mill_bonus"] > 0:
            out[SW] += 1
            cap -= 1
        if cap > 0 and c.heat_short() > 4 * out[FW] and have[FW] > out[FW] and c.rnd >= 2:
            out[FW] += 1
            cap -= 1
        return out

    def _w2(self, c: Ctx, legal: list[int]) -> int | None:
        r = c.s.river[c.me]
        for k in (HW, SW, FW):
            if r[k]:
                a = A.encode("MOVE_WOOD", k, self._dest(c, k))
                if a in legal:
                    return a
                a = A.encode("MOVE_WOOD", k, 0)
                if a in legal:
                    return a
        return None

    def _w3(self, c: Ctx, legal: list[int]) -> int | None:
        s, me = c.s, c.me
        pile = s.woodpile[me]
        names = {A.decode(a).name for a in legal}
        if s.trip_kind != 0:  # inside a trip
            if s.trip_kind in (2, 4):  # raft / PW log driving
                for k in (SW, FW):
                    a = A.encode("RIVER_MOVE", k)
                    if pile[k] and a in legal and (c.rnd == 7 or self._dest(c, k) == 1):
                        return a
                return A.END_TRIP if A.END_TRIP in legal else None
            for k in (HW, SW, FW):
                if pile[k]:
                    a = A.encode("MOVE_WOOD", k, self._dest(c, k))
                    if a in legal:
                        return a
            return A.END_TRIP if A.END_TRIP in legal else None
        if not sum(pile):
            return A.DONE
        if "USE_PW_LOGDRIVING" in names and not s.w_ld:
            # Use it for sale pieces (never hardwood), saving bearers.
            sale_pieces = sum(pile[k] for k in (SW, FW) if c.rnd == 7 or self._dest(c, k) == 1)
            extra = sum(pile) - (s.hired_b[me] - s.bear_used[me])
            if sale_pieces and (extra > 0 or c.rnd == 7):
                return A.USE_PW_LOGDRIVING
        if s.w_worker >= 0:
            # Worker committed: wagon if worthwhile, raft for surplus, else carry one.
            carriers = s.hired_b[me] - s.bear_used[me]
            others = carriers + (0 if s.mill_used[me] else 1) + spare_huts(c)
            if A.USE_WAGON in legal and sum(pile) >= 2:
                return A.USE_WAGON
            if pile[HW] and others <= pile[HW]:
                a = A.encode("MOVE_WOOD", HW, 0)
                if a in legal:
                    return a
            if c.rafts() and sum(pile) > carriers + 1 and c.rnd in (1, 2, 3, 5, 6, 7):
                for k in (SW, FW):
                    a = A.encode("RIVER_MOVE", k)
                    if pile[k] and a in legal and self._dest(c, k) == 1:
                        return a
            for k in (HW, SW, FW):
                if pile[k]:
                    a = A.encode("MOVE_WOOD", k, self._dest(c, k))
                    if a in legal:
                        return a
            return None
        assigns = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "ASSIGN_WORKER"}
        if 0 in assigns:
            return assigns[0]
        # Mill worker if not needed for sawing.
        saw_need = min(sum(self._saw_targets(c)), c.saws())
        sawing_now = sum(s.sawing[me]) + (pile[HW])
        sawyers = s.hired_s[me]
        needs_mill_for_saw = min(saw_need, sawing_now) > sawyers
        if (
            1 in assigns
            and (not needs_mill_for_saw or sum(pile) >= 3)
            and self._pile_value(c) >= 2.5
        ):
            return assigns[1]
        if 2 in assigns and self._pile_value(c) >= 3.5 and spare_huts(c) > 0:
            return assigns[2]
        return A.DONE

    def _pile_value(self, c: Ctx) -> float:
        pile = c.s.woodpile[c.me]
        if pile[HW]:
            return 6.0
        if pile[SW]:
            return 4.0
        if pile[FW]:
            return 3.0
        return 0.0

    def _w4(self, c: Ctx, legal: list[int]) -> int | None:
        s, me = c.s, c.me
        saws = [a for a in legal if A.decode(a).name == "SAW"]
        disks = s.sawing[me]
        if saws:
            plan = c.slot_plan()
            heat = c.heat_short()
            kinds = [k for k in (HW, SW, FW) if disks[k]]
            if not kinds:
                return A.DONE if A.DONE in legal else None
            sw_need = plan.need_logs(SW) > 0
            fw_need = plan.need_logs(FW) > 0 or heat > 0
            if HW in kinds:
                k = HW
            elif SW in kinds and (sw_need or FW not in kinds or not fw_need):
                k = SW
            else:
                k = FW
            ys = [A.decode(a).params[1] for a in saws if A.decode(a).params[0] == k]
            if not ys:
                return A.DONE if A.DONE in legal else None
            y = max(ys)
            n_store = 0
            if k == FW:
                task_logs = 1 if plan.need_logs(FW) else 0
                n_store = max(0, min(y - task_logs, heat))
            elif c.rnd in (4, 8) and c.heat_short(next_only=True) > 0 and not disks[FW]:
                if k == SW or plan.need_logs(HW) == 0:
                    n_store = min(y, c.heat_short(next_only=True))
            a = A.encode("SAW", k, n_store)
            return a if a in legal else None
        assigns = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "ASSIGN_WORKER"}
        if not assigns:
            return A.DONE
        targets = self._saw_targets(c)
        want = 0
        for k in range(3):
            if k == HW:
                want += disks[HW]
            else:
                want += min(disks[k], targets[k])
        if c.rnd == 8 and c.phase == PHASE_N3:
            want = sum(disks)  # sawing-area disks are worth nothing at the final sale
        if want <= 0:
            return A.DONE
        if 0 in assigns:
            return assigns[0]
        if 1 in assigns:
            return assigns[1]
        # A hut worker saves a $1 hire; spend it on hardwood or needed logs.
        if (
            2 in assigns
            and (spare_huts(c) > 0 or c.rnd in (4, 8))
            and (disks[HW] or c.slot_plan().needs or c.heat_short(next_only=True) > 0 or c.rnd == 8)
        ):
            return assigns[2]
        return A.DONE

    def _w5(self, c: Ctx, legal: list[int]) -> int | None:
        s, me = c.s, c.me
        plan = c.slot_plan()
        places = [a for a in legal if A.decode(a).name == "PLACE_TASK"]
        if places:
            slots = {sl.slot: sl for sl in c.open_slots()}
            best, best_key = None, None
            for a in places:
                slot, src = A.decode(a).params
                sl = slots.get(slot)
                if sl is None or sl.task in plan.dead and c.rnd < 8:
                    continue
                if src == 1:
                    # Taking from drying 1 must not steal a log reserved for a later stage.
                    p = 2 * sl.kind + 1
                    reserved_hi = sum(
                        1
                        for s2, (z, pp) in plan.slot_src.items()
                        if z == 1 and pp == p and slots.get(s2) is not None and slots[s2].stage >= 1
                    )
                    if c.zone_count(1, p) <= reserved_hi:
                        continue
                if src == 0 and sl.stage == 0 and sl.milled:
                    p = 2 * sl.kind + 1
                    reserved_hi = sum(
                        1
                        for s2, (z, pp) in plan.slot_src.items()
                        if z == 0 and pp == p and slots.get(s2) is not None and slots[s2].stage >= 1
                    )
                    if c.zone_count(0, p) <= reserved_hi and c.rnd < 8:
                        continue
                if src == 2 and c.rnd == 8:
                    # The stored piece goes to the highest-stage slot it fits.
                    key = (2, sl.stage, sl.reward)
                else:
                    key = (1, sl.stage, sl.reward)
                if best_key is None or key > best_key:
                    best, best_key = a, key
            if best is not None:
                return best
        stores = [a for a in legal if A.decode(a).name == "STORE_PIECE"]
        if stores:
            a = self._store_choice(c, stores)
            if a is not None:
                return a
        joins = [a for a in legal if A.decode(a).name == "PLACE_JOINERY"]
        if joins:
            j = s.joiners[me]
            for k in (HW, SW, FW):
                if c.zone_count(2, 2 * k + 1) - plan.res(2, 2 * k + 1) <= 0:
                    continue
                for q in range(min(j, 3)):
                    a = A.encode("PLACE_JOINERY", k, q)
                    if a in legal:
                        return a
        return A.DONE

    def _store_choice(self, c: Ctx, stores: list[int]) -> int | None:
        plan = c.slot_plan()
        uncovered = [n for n in plan.needs if n[1] >= 0]
        if not uncovered:
            return None
        # Prefer a slot whose drying cannot be done in time (or round 7+): hardest stage first.
        uncovered.sort(key=lambda n: (-n[1], n[2]))
        late = c.rnd >= 6
        for kind, stage, _latest, _task in uncovered:
            if stage == 0 and not late:
                continue
            for z in (3, 2, 1, 0):
                p = 2 * kind + 1
                if c.zone_count(z, p) - plan.res(z, p) > 0:
                    a = A.encode("STORE_PIECE", kind, z)
                    if a in stores:
                        return a
        return None

    def _keep_money(self, c: Ctx) -> int:
        """Money to keep for the coming winter's shortfall (penalties)."""
        if c.rnd not in (3, 7):
            return 0
        fs = c.food_short()
        hs = c.heat_short(next_only=True)
        return 3 * (fs + hs)

    def _w6(self, c: Ctx, legal: list[int]) -> int | None:
        plan = c.slot_plan()
        sells = {A.decode(a).params: a for a in legal if A.decode(a).name == "SELL"}
        # Drying 3 must be sold (reserved pieces were placed in W5 already).
        for p in range(6):
            if (3, p) in sells:
                return sells[(3, p)]
        if c.rnd == 7:
            need = self._keep_money(c) - c.money
            if need > 0:
                return self._sell_cheapest(c, sells, plan)
            return A.DONE
        # Sale area: disks not reserved are sold; logs beyond what enters drying are sold.
        for k in (FW, SW):
            p = 2 * k
            if c.zone_count(0, p) - plan.res(0, p) > 0 and (0, p) in sells:
                return sells[(0, p)]
        keep = self._dry_choice(c, plan)
        for p in (1, 3, 5):
            spare = c.zone_count(0, p) - plan.res(0, p) - keep.get(p, 0)
            if spare > 0 and (0, p) in sells:
                return sells[(0, p)]
        need = self._keep_money(c) - c.money
        if need > 0 or (c.money < 2 and c.rnd <= 6):
            a = self._sell_cheapest(c, sells, plan, zones=(1, 2))
            if a is not None and (need > 0 or c.money < 1):
                return a
        return A.DONE

    def _sell_cheapest(
        self,
        c: Ctx,
        sells: dict[tuple[int, ...], int],
        plan: SlotPlan,
        zones: tuple[int, ...] = (0, 1, 2),
    ) -> int | None:
        best, bv = None, 1e9
        for (z, p), a in sells.items():
            if z not in zones:
                continue
            if c.zone_count(z, p) - plan.res(z, p) <= 0:
                continue
            price = c.t.wood_price[p // 2][p % 2] + c.t.dry_bonus[z]
            if price < bv:
                best, bv = a, price
        return best if best is not None else A.DONE

    def _dry_choice(self, c: Ctx, plan: SlotPlan) -> dict[int, int]:
        """Sale-area logs (by piece) that should enter drying 1 this round, at most 2."""
        if c.rnd == 7:
            return {}
        out: dict[int, int] = {}
        room = 2
        if c.bld("drying_area_upgrade"):
            room = 2
        if plan_active(c.t, c.s, c.me, "pw_drying"):
            room *= 2
        for p in (5, 3, 1):
            r = plan.res(0, p)
            # Only reserved logs that need drying (stage >= 1) go first.
            hi = sum(
                1 for sl in c.plan_slots() if plan.slot_src.get(sl.slot) == (0, p) and sl.stage >= 1
            )
            n = min(room, hi)
            if n:
                out[p] = out.get(p, 0) + n
                room -= n
            _ = r
        for p in (5, 3, 1):
            spare = c.zone_count(0, p) - plan.res(0, p)
            n = min(room, max(0, spare))
            if n:
                out[p] = out.get(p, 0) + n
                room -= n
        return out

    def _w7(self, c: Ctx, legal: list[int]) -> int | None:
        plan = c.slot_plan()
        enters = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "DRY_ENTER"}
        if not enters:
            return A.DONE
        want = self._dry_choice(c, plan)
        for p in (5, 3, 1):
            if want.get(p, 0) > 0 and p in enters:
                return enters[p]
        return A.DONE

    # ------------------------------------------------------------ winter
    def _nb(self, c: Ctx, legal: list[int]) -> int | None:
        if c.s.w_dirty:
            return A.DONE
        plan = c.slot_plan()
        if c.rnd == 4:
            hw_gap = plan.need_logs(HW) - hw_certain(c)
            sw_gap = plan.need_logs(SW) - sw_supply_logs(c)
            if sw_gap > 0 and hw_gap < 0:
                return A.encode("TAKE_BONUS", SW)
            return A.encode("TAKE_BONUS", HW)
        # Round 8: hardwood only if a stage-0 hardwood slot is open and a second worker and
        # saw and sledge exist; else softwood to sledge to the sale area ($4).
        hw_slot = any(n[0] == HW and n[1] == 0 for n in plan.needs)
        if hw_slot and c.huts()[H_WORK] >= 1 and c.saws() and c.sledges():
            return A.encode("TAKE_BONUS", HW)
        if c.heat_short(next_only=True) >= 2 and c.saws() and c.huts()[H_WORK] >= 1:
            return A.encode("TAKE_BONUS", FW)
        return A.encode("TAKE_BONUS", SW)

    def _mill_job(self, c: Ctx) -> str:
        """Best use of the winter mill worker: 'saw', 'sledge' or 'cut'."""
        s, me = c.s, c.me
        heat = c.heat_short(next_only=True)
        disks = s.sawing[me]
        saw_v = 0.0
        if c.saws() and sum(disks):
            if disks[FW] and heat > 0:
                saw_v = 3.0 * min(heat, 4)
            elif c.rnd == 8:
                saw_v = 4.0 if disks[SW] or disks[FW] else 5.0 if disks[HW] else 0
                if disks[HW] and any(n[0] == HW and n[1] == 0 for n in c.slot_plan().needs):
                    saw_v = 12.0
            elif disks[HW]:
                saw_v = 1.0
        sledge_v = 0.0
        pile = s.woodpile[me]
        if c.sledges() and sum(pile):
            if c.rnd == 8:
                sledge_v = 4.0 * min(pile[SW], 2) + 3.0 * min(pile[FW], max(0, 2 - pile[SW]))
                hw0 = any(n[0] == HW and n[1] == 0 for n in c.slot_plan().needs)
                if pile[HW] and hw0 and c.huts()[H_WORK] and c.saws():
                    sledge_v = 15.0
            else:
                sledge_v = 1.0 * min(sum(pile), 2)
        cut_v = 5.0 if c.rnd == 4 else 0.0
        best = max((saw_v, "saw"), (sledge_v, "sledge"), (cut_v, "cut"))
        return best[1] if best[0] > 0 else "none"

    def _n1(self, c: Ctx, legal: list[int]) -> int | None:
        if A.WINTER_CUT in legal:
            return A.WINTER_CUT
        assigns = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "ASSIGN_WORKER"}
        job = self._mill_job(c)
        if job == "cut" and 1 in assigns:
            return assigns[1]
        # Spare hut workers in round 4 cut too (1 firewood each after the first).
        return A.DONE

    def _n2(self, c: Ctx, legal: list[int]) -> int | None:
        s, me = c.s, c.me
        pile = s.woodpile[me]
        if s.trip_kind == 3:
            surplus_food = s.food[me] - (c.food_due(len(c.winters_left()) and c.winters_left()[0]))
            if s.trip_n >= c.t.sledge_free and surplus_food <= 0:
                return A.END_TRIP if A.END_TRIP in legal else None
            for k in (SW, FW, HW):
                if pile[k]:
                    d = 1 if c.rnd == 8 and k != HW else self._dest(c, k)
                    if (
                        c.rnd == 8
                        and k != HW
                        and s.sawing[me][k] == 0
                        and c.huts()[H_WORK]
                        and c.saws()
                        and s.mill_used[me]
                    ):
                        d = 1
                    a = A.encode("MOVE_WOOD", k, d)
                    if a in legal:
                        return a
            return A.END_TRIP if A.END_TRIP in legal else None
        if A.USE_SLEDGE in legal:
            return A.USE_SLEDGE
        assigns = {A.decode(a).params[0]: a for a in legal if A.decode(a).name == "ASSIGN_WORKER"}
        job = self._mill_job(c)
        if 1 in assigns and job == "sledge":
            return assigns[1]
        if 2 in assigns and c.rnd == 8 and sum(pile):
            return assigns[2]
        return A.DONE

    def _shortfall(self, c: Ctx, legal: list[int]) -> int | None:
        if A.TAKE_LOAN in legal and len(legal) == 1:
            return A.TAKE_LOAN
        if c.money >= c.s.sf_due and A.DONE in legal:
            return A.DONE
        sells = {A.decode(a).params: a for a in legal if A.decode(a).name == "SELL"}
        if not sells:
            return A.DONE if A.DONE in legal else None
        plan = c.slot_plan()
        best, bv = None, (9, 99)
        for (z, p), a in sells.items():
            reserved = z < 4 and c.zone_count(z, p) - plan.res(z, p) <= 0
            price = c.t.wood_price[p // 2][p % 2]
            key = (1 if reserved else 0, -price)
            if key < bv:
                best, bv = a, key
        return best

    def _final_sale(self, c: Ctx, legal: list[int]) -> int | None:
        r = c.s.river[c.me]
        fw_v = r[FW] * c.t.wood_price[FW][0]
        sw_v = r[SW] * c.t.wood_price[SW][0]
        a = A.encode("RIVER_SALE", 0 if fw_v >= sw_v else 1)
        return a if a in legal else None
