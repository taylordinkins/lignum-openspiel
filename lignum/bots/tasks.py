"""Task pipeline planner for heuristic-v2 (Phase 7 unit 1d, D36). Bot policy only.

Reads public state and the seat's own holdings. For the task cards a seat holds (and one it might
take) it allocates the wood the seat has or can get to the unfilled requirement slots, hardest
stage first, and estimates a completion probability, an expected profit and the pieces that must
not be sold. Timing follows the engine (R-055, R-058, R-059):

* a piece placed from the sale area or drying 1 fills a stage-0 slot, from drying 2 a stage-1 slot,
  from drying 3 a stage-2 slot, in W5 (before the W6 sale, so drying-3 wood can still be placed);
* drying advances every round (W7), so a log that enters drying 1 at the end of round index i is
  placeable at stage s in W5 of index i + 1 + s; rounds are indexed 1..7 without the first winter,
  and the last placement is the round 8 N4 phase (index 7);
* only 2 logs fit in drying 1, which the planner ignores (it only makes some plans a round late).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache

from lignum.components import Components, Task, load_components
from lignum.game import (
    PHASE_N3,
    PHASE_N4,
    PHASE_W1,
    PHASE_W3,
    PHASE_W4,
    PHASE_W5,
    PHASE_W7,
    LignumState,
)
from lignum.rules import SetupTables
from lignum.woodwork import piece_idx

Weights = Mapping[str, float]

# Probability weights for wood that is not yet in the sale / drying areas.
# Chance that upstream wood reaches the sale area in time: the worker it needs is hired and the
# phase is still ahead (sure), or it depends on later rounds (unsure).
_P_SAWING = (0.9, 0.5)  # disk in the sawing area: a saw and a sawyer / the mill worker in W4
_P_WOODPILE = (0.8, 0.3)  # disk in the woodpile: also a bearer in W3
_P_FUTURE_BASE = 0.3  # not yet cut: base plus a step per piece of the kind in the seat's area
_P_FUTURE_STEP = 0.1
_P_FUTURE_MAX = 0.7


@cache
def _components() -> Components:
    return load_components()


@dataclass(frozen=True)
class Clock:
    first: int  # index of the next W5 at which wood can be placed
    early: bool  # this round's W5 is over: a sale piece entering drying 1 is in area 1 at ``first``
    shift: bool  # drying wood still moves one area on before ``first``
    arrive: int  # index of the W5 at which wood now upstream (sawing area, woodpile) can be there
    cut: int  # same for wood not yet cut (woodcutting W1 of that round)


@dataclass
class Assessment:
    """One task card against the seat's wood. ``prob`` is the product of the slot probabilities."""

    prob: float
    net: float  # reward x prob minus the sale value of the pieces it takes
    reserved: list[tuple[int, int]] = field(default_factory=lambda: [])  # (zone, piece) in hand
    sure: bool = False  # every free slot is covered by wood already in the sale / drying areas
    feasible: bool = False  # task_first: a schedule fits (``prob`` at least task_feasible_prob)
    cost: float = 0.0  # sale value of the free slots' pieces and their drying bonus


def task_premium(t: SetupTables, task: Task, per_piece: bool = False) -> float:
    """Reward minus the sale value of the task's pieces at the drying stage each requires (v4
    ``task_rank: premium``), per piece with ``per_piece`` (``premium_piece``). Prices and bonuses
    come from the setup tables."""
    sale = 0
    for req in task.requirements:
        kind = ("firewood", "softwood", "hardwood").index(req.kind)
        sale += max(0, t.wood_price[kind][int(req.milled)]) + (
            t.dry_bonus[req.drying + 1] if req.drying else 0
        )
    return (task.reward - sale) / (len(task.requirements) if per_piece else 1)


def seq_index(t: SetupTables, rnd: int) -> int:
    """Round number without the first winter: rounds 1,2,3,5,6,7,8 -> 1..7."""
    return rnd - 1 if rnd > t.winter_rounds[0] else rnd


class TaskPlanner:
    def __init__(self, t: SetupTables, w: Weights) -> None:
        self.t = t
        self.w = w
        self.last = seq_index(t, t.winter_rounds[1])

    # ------------------------------------------------------------------ timing
    def _clock(self, state: LignumState) -> Clock:
        t = self.t
        rnd, phase = state.round, state.phase
        if rnd == t.winter_rounds[0]:  # no placement and no drying in the first winter
            nxt = seq_index(t, rnd + 1)
            return Clock(nxt, False, False, nxt, nxt)
        cur = seq_index(t, rnd)
        if rnd == t.winter_rounds[1]:
            if phase > PHASE_N4:
                return Clock(cur + 1, False, False, cur + 1, cur + 1)
            return Clock(cur, False, False, cur if phase <= PHASE_N3 else cur + 1, cur + 1)
        if phase <= PHASE_W5:
            return Clock(
                cur,
                False,
                False,
                cur if phase <= PHASE_W4 else cur + 1,
                cur if phase <= PHASE_W1 else cur + 1,
            )
        # W6 / W7: the advance of the W7 turn is applied once the seat has acted in it (A7)
        advanced = phase == PHASE_W7 and bool(state.w_dirty)
        return Clock(cur + 1, True, not advanced, cur + 1, cur + 1)

    def _stock(self, state: LignumState, seat: int) -> dict[tuple[int, int], int]:
        """Pieces in the sale area (zone 0) and drying areas (1..3) by (zone, piece type)."""
        out: dict[tuple[int, int], int] = {}
        for k in range(3):
            if state.sale[seat][k]:
                out[(0, 2 * k)] = state.sale[seat][k]
            if state.sale_logs[seat][k]:
                out[(0, 2 * k + 1)] = state.sale_logs[seat][k]
        for z in range(1, 4):
            row = state.dry[seat][z - 1]
            for p in range(6):
                if row[piece_idx(p)]:
                    out[(z, p)] = row[piece_idx(p)]
        return out

    def _ready(self, zone: int, stage: int, c: Clock) -> int | None:
        """Index of the W5 at which a piece now in ``zone`` fills a slot of ``stage``, None when it
        is over-dried or comes too late."""
        if zone == 0:
            at = c.first if stage == 0 else c.first + stage + (0 if c.early else 1)
        else:
            z = zone + 1 if c.shift else zone  # area it stands in at W5 ``first``
            if z > 3 or z - 1 > stage:
                return None
            at = c.first + stage - (z - 1)
        return at if at <= self.last else None

    def _fresh_ready(
        self, stage: int, arrive: int, cohort: dict[int, int] | None = None
    ) -> int | None:
        at = arrive if stage == 0 else arrive + 1 + stage
        if cohort is not None and stage:  # drying 1 holds 2 logs: later round when it is full
            while cohort.get(at - stage, 0) >= self.t.dry_cap_logs and at <= self.last:
                at += 1
        return at if at <= self.last else None

    # ------------------------------------------------------------------ allocation
    def assess(
        self,
        state: LignumState,
        seat: int,
        tasks: list[int],
        candidate: int | None = None,
    ) -> dict[int, Assessment]:
        """Allocate wood to the free slots of ``tasks`` (in order) and then ``candidate``."""
        t, w = self.t, self.w
        comps = _components().tasks
        clock = self._clock(state)
        arrive = clock.arrive
        stock = self._stock(state, seat)
        sawing = [float(x) for x in state.sawing[seat]]
        pile = [float(x) for x in state.woodpile[seat]]
        area = (
            state.wood[state.picks[seat]]
            if state.wood and seat < len(state.picks) and 0 <= state.picks[seat] < len(state.wood)
            else (0, 0, 0)
        )
        future = [float(area[k]) for k in range(3)]
        saws = state.equip[seat][0]
        # Workers in hand make this round's chain likely; the mill worker saws once a round.
        sawyer = state.hired_s[seat] - state.saw_used[seat] > 0 or not state.mill_used[seat]
        p_saw = _P_SAWING[0 if sawyer and state.phase <= PHASE_W4 else 1]
        p_pile = _P_WOODPILE[0 if state.hired_b[seat] and state.phase <= PHASE_W3 else 1]
        tf = bool(w.get("task_first", 0))
        cohort: dict[int, int] | None = {} if tf else None  # logs entering drying 1, by round
        floor = w.get("task_feasible_prob", 0.3)
        out: dict[int, Assessment] = {}
        order = [*tasks, *([candidate] if candidate is not None else [])]
        for ti in order:
            task = comps[ti]
            filled = state.filled[ti] if ti in state.held_tasks[seat] else 0
            slots = [(r, req) for r, req in enumerate(task.requirements) if not filled >> r & 1]
            slots.sort(key=lambda x: -x[1].drying)
            prob, cost, sure = 1.0, 0.0, True
            res: list[tuple[int, int]] = []
            for _, req in slots:
                kind = ("firewood", "softwood", "hardwood").index(req.kind)
                p = 2 * kind + int(req.milled)
                stage = req.drying
                price = t.wood_price[kind][int(req.milled)]
                cost += max(0, price) + (t.dry_bonus[stage + 1] if stage else 0)
                got = self._take_stock(stock, p, stage, clock, res, cohort)
                if got:
                    continue
                sure = False
                at = self._fresh_ready(stage, arrive, cohort)
                if req.milled:
                    if saws and sawing[kind] > 1e-9 and at:
                        sawing[kind] -= 1.0 / max(1, t.sawing_yield[kind])
                        prob *= p_saw
                        self._enter(cohort, stage, at)
                        continue
                    if saws and pile[kind] > 1e-9 and at:
                        pile[kind] -= 1.0 / max(1, t.sawing_yield[kind])
                        prob *= p_pile
                        self._enter(cohort, stage, at)
                        continue
                elif pile[kind] > 1e-9 and at:
                    pile[kind] -= 1.0
                    prob *= p_pile
                    continue
                ready = self._fresh_ready(stage, clock.cut, cohort)
                if ready is None:
                    prob = 0.0
                    break
                self._enter(cohort, stage, ready)
                # chance per round of cutting (and milling) one such piece, over the rounds left
                q = min(
                    w.get("task_future_max", _P_FUTURE_MAX),
                    w.get("task_future_base", _P_FUTURE_BASE)
                    + w.get("task_future_step", _P_FUTURE_STEP) * future[kind],
                )
                prob *= 1.0 - (1.0 - q) ** min(3, self.last - ready + 1)
                future[kind] = max(0.0, future[kind] - 1.0)
            if not prob:
                res = []
            net = task.reward * prob - cost * w.get("task_cost_weight", 1.0)
            out[ti] = Assessment(
                prob, net, res, sure and bool(prob), tf and prob >= max(floor, 1e-9), cost
            )
        return out

    def worth(self, a: Assessment, reward: int) -> float:
        """task_first: a finishable task is worth near its full reward less the sale value of the
        wood it still needs; an unfinishable one nothing (R-056)."""
        if not a.feasible:
            return 0.0
        w = self.w
        return reward * w.get("task_finish_value", 0.85) - a.cost * w.get("task_cost_weight", 0.3)

    def _take_stock(
        self,
        stock: dict[tuple[int, int], int],
        p: int,
        stage: int,
        clock: Clock,
        res: list[tuple[int, int]],
        cohort: dict[int, int] | None = None,
    ) -> bool:
        best: tuple[int, int] | None = None
        best_at = 0
        for (z, q), n in stock.items():
            if q != p or n <= 0:
                continue
            at = self._ready(z, stage, clock)
            if at is None:
                continue
            if cohort is not None and z == 0 and stage:  # waits for room in drying 1
                while cohort.get(at - stage, 0) >= self.t.dry_cap_logs and at <= self.last:
                    at += 1
                if at > self.last:
                    continue
            if best is None or at < best_at:
                best, best_at = (z, q), at
        if best is None:
            return False
        stock[best] -= 1
        res.append(best)
        if best[0] or stage:
            self._enter(cohort, stage, best_at)
        return True

    @staticmethod
    def _enter(cohort: dict[int, int] | None, stage: int, at: int) -> None:
        """Count a log that stands in drying 1 at W5 ``at - stage`` (task_first capacity)."""
        if cohort is not None and stage:
            cohort[at - stage] = cohort.get(at - stage, 0) + 1


def held_assessments(
    planner: TaskPlanner, state: LignumState, seat: int, tasks: Sequence[Task]
) -> dict[int, Assessment]:
    """Unfinished held tasks against the seat's wood, nearest to done first (they claim the wood
    first). ``tasks`` is the component task list."""
    held = [
        h
        for h in state.held_tasks[seat]
        if state.filled[h] != (1 << len(tasks[h].requirements)) - 1
    ]
    held.sort(
        key=lambda h: (
            len(tasks[h].requirements) - bin(state.filled[h]).count("1"),
            -tasks[h].reward,
        )
    )
    return planner.assess(state, seat, held)
