"""Heuristic bot (Phase 6, D32).

Supply-path stops follow a fixed ranking of marginal value per stop (``data/bots/heuristic.yaml``).
Everything else is chosen by one-step lookahead on the expected-dollars value function
(``lignum.bots.value``): clone, apply the candidate, compare ``value`` for the seat. Loans follow
D29 (``bot_candidates``). The bot reads only public state and its own seat's holdings; the cutting
area it picks is its own, and opponents' hidden picks are never read.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from typing import Any

import pyspiel

from lignum import actions as A
from lignum.bots.base import bot_candidates
from lignum.bots.plan import candidate_plan, task_plan, task_take_ok
from lignum.bots.solver import WOOD_WORK_PHASES, solve_turn
from lignum.bots.tasks import Assessment, TaskPlanner, held_assessments, task_premium
from lignum.bots.value import value
from lignum.bots.weights import HEURISTIC_YAML, load_profile, load_weights
from lignum.components import load_components
from lignum.game import (
    PHASE_N1,
    PHASE_N2,
    PHASE_N4,
    PHASE_PK,
    PHASE_SP,
    PHASE_TR,
    PHASE_W1,
    PHASE_W2,
    PHASE_W3,
    PHASE_W4,
    PHASE_W5,
    PHASE_W6,
    PHASE_W7,
    LignumState,
)
from lignum.rules import (
    CLEARING_LOC,
    CRAFT_ORDER,
    SPOT_NAMES,
    building_param,
    craft_sales,
    has_building,
    plan_cost,
)
from lignum.woodwork import IDX_WAGON, SRC_MILL

__all__ = ["HEURISTIC_YAML", "HeuristicBot", "load_weights"]

# Actions that only set up a following action in the same turn: scored by their best follow-up.
_SETUP_ACTIONS = frozenset(
    A.encode(n, *p) for n, p in (("ASSIGN_WORKER", (w,)) for w in range(3))
) | {A.USE_WAGON, A.USE_SLEDGE, A.USE_PW_LOGDRIVING}
_W_PHASES = {
    "W1": PHASE_W1,
    "W2": PHASE_W2,
    "W3": PHASE_W3,
    "W4": PHASE_W4,
    "W6": PHASE_W6,
    "W5": PHASE_W5,
    "W7": PHASE_W7,
}
_HUT_NAMES = frozenset({"BUILD_HUT", "HUT_TOKEN", "HUT_AREA", "HUT_FOOD", "HUT_DRY"})
_KINDS = ("fw", "sw", "hw")
_MILL_RESERVE_PHASES = frozenset({PHASE_W1, PHASE_W2, PHASE_W3, PHASE_N1, PHASE_N2})


def _best_kind(state: LignumState, seat: int) -> str:
    wood = state.wood[state.picks[seat]]
    for k in (2, 1, 0):
        if wood[k]:
            return _KINDS[k]
    return "fw"


class HeuristicBot:
    def __init__(
        self, weights: Mapping[str, Any] | None = None, profile: str = "heuristic"
    ) -> None:
        """``weights`` (a loaded profile dict) wins over ``profile`` (a name under data/bots/)."""
        self.w = weights if weights is not None else load_profile(profile)
        self.vw: Mapping[str, Any] = self.w["value"]
        self.pw: Mapping[str, Any] = self.w.get("plan") or {}  # v7 long-term planner knobs
        self._plan_on = bool(self.pw.get("enabled", 0))
        if self._plan_on:  # the value function reads the plan knobs too (value._task_value)
            self.vw = {**self.vw, "plan": self.pw}
        if "value_fit" in self.vw:  # fail at construction, not mid-game
            from lignum.bots.fitted import load_fit

            load_fit(self.vw["value_fit"], tuple(self.vw["fitted_components"]))
        comps = load_components()
        self._pw_ids = [p.id for p in comps.planned_work]
        self._bld_ids = [b.id for b in comps.buildings]
        self._tasks = comps.tasks
        self._planner: TaskPlanner | None = None
        self._planner_key: tuple[int, bool, bool] | None = None

    # ------------------------------------------------------------------ entry point
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        legal = bot_candidates(state)
        if len(legal) == 1:
            return legal[0]
        assert isinstance(state, LignumState)
        seat = state.current_player()
        bonus = self._bonus_pick(state, legal)
        if bonus is not None:
            return bonus
        if state.phase in (PHASE_SP, PHASE_PK):
            return self._pick_area(state, legal, rng)
        if state.phase == PHASE_TR:
            if state.hb_open:
                return self._lookahead(state, legal, seat, rng)
            if state.visit_loc == 0:
                return self._move(state, legal, seat, rng)
            return self._visit(state, legal, seat, rng)
        if self.w.get("mill_saws", 0) and state.phase in _MILL_RESERVE_PHASES:
            legal = self._keep_mill_for_saw(state, legal, seat)
        sv = self.w.get("solver")
        if (
            sv
            and sv["enabled"]
            and state.phase in self._solver_phases(sv)
            and not (state.phase == PHASE_W6 and self.w.get("task_pipeline", 0))
        ):  # with the task pipeline, W6 is solved inside _wood_work (reserved pieces stay unsold)
            move = self._solve(state, legal, seat, sv)
            if move is not None:
                return move
        if self.w.get("task_pipeline", 0) and (
            state.phase in (PHASE_W5, PHASE_W6, PHASE_W7)
            or (state.phase == PHASE_N4 and state.round == state._tables().winter_rounds[1])  # pyright: ignore[reportPrivateUsage]
        ):
            return self._wood_work(state, legal, seat, rng)
        return self._lookahead(state, legal, seat, rng)

    def _bonus_pick(self, state: LignumState, legal: list[int]) -> int | None:
        """v4 (profile key ``bonus_kind``: firewood, softwood, hardwood or hardwood_if_task): take
        the winter bonus disk (R-065) of that kind whenever it is offered. ``hardwood_if_task``
        takes hardwood only while held tasks still need more hardwood than the seat has (winter
        has no path, so no card can be taken before the next spring), else the lookahead chooses
        as in v1-v3 (it always took softwood)."""
        kind = self.w.get("bonus_kind")
        if kind is None:
            return None
        if kind == "hardwood_if_task":
            if not self._hw_target(state, anticipate=False):
                return None
            kind = "hardwood"
        want = ("firewood", "softwood", "hardwood").index(str(kind))
        for a in legal:
            d = A.decode(a)
            if d.name == "TAKE_BONUS" and d.params[0] == want:
                return a
        return None

    def _keep_mill_for_saw(self, state: LignumState, legal: list[int], seat: int) -> list[int]:
        """v4 (profile key ``mill_saws``): before sawing, do not spend the mill worker on cutting
        or carrying while discs wait in the sawing area, a saw is in hand and no hired sawer is
        left to saw them (R-054: one worker and one saw per disc)."""
        if (
            state.mill_used[seat]
            or not state.equip[seat][0]
            or not sum(state.sawing[seat])
            or state.hired_s[seat] - state.saw_used[seat] > 0
        ):
            return legal
        keep = [
            a
            for a in legal
            if not (A.decode(a).name == "ASSIGN_WORKER" and A.decode(a).params[0] == SRC_MILL)
        ]
        return keep or legal

    # ------------------------------------------------------------------ own-turn solver (v6)
    @staticmethod
    def _solver_phases(sv: Mapping[str, Any]) -> frozenset[int]:
        """Phases the solver plays: profile ``solver.phases`` (names W1..W7), default all."""
        names = sv.get("phases")
        if names is None:
            return WOOD_WORK_PHASES
        return frozenset(_W_PHASES[str(n)] for n in names)

    def _solve(
        self,
        state: LignumState,
        legal: list[int],
        seat: int,
        sv: Mapping[str, Any],
        narrow: Callable[[LignumState, list[int]], list[int]] | None = None,
    ) -> int | None:
        """First action of the best own-turn sequence (lignum.bots.solver); the mill-saw filter
        and the hut/loan exclusions apply at every step of the search, as at the root."""

        def expand(s: LignumState) -> list[int]:
            acts = bot_candidates(s)
            if self.w.get("mill_saws", 0) and s.phase in _MILL_RESERVE_PHASES:
                acts = self._keep_mill_for_saw(s, acts, seat)
            if narrow is not None:
                acts = narrow(s, acts) or acts
            return sorted(a for a in acts if A.decode(a).name not in _HUT_NAMES) or sorted(acts)

        root = sorted(a for a in legal if A.decode(a).name not in _HUT_NAMES) or sorted(legal)
        plan = solve_turn(
            state,
            seat,
            lambda s: root if s is state else expand(s),
            lambda s: value(s, seat, self.vw),
            int(sv["beam"]),
            int(sv["node_cap"]),
            int(sv["max_depth"]),
        )
        return plan.actions[0] if plan else None

    # ------------------------------------------------------------------ task pipeline (v2)
    def _plan(self, state: LignumState) -> TaskPlanner:
        key = state._tkey  # pyright: ignore[reportPrivateUsage]
        if self._planner is None or self._planner_key != key:
            self._planner = TaskPlanner(state._tables(), self.vw)  # pyright: ignore[reportPrivateUsage]
            self._planner_key = key
        return self._planner

    def _held_assessments(self, state: LignumState, seat: int) -> dict[int, Assessment]:
        if self._plan_on:  # v7: the long-term plan decides which held tasks are live
            return {
                tp.task: Assessment(
                    1.0 if tp.finishable else 0.0,
                    0.0,
                    list(tp.stock_pieces) if tp.finishable else [],
                    tp.finishable and all(s.zone >= 0 for s in tp.missing),
                    tp.finishable,
                )
                for tp in task_plan(state, seat).tasks
            }
        return held_assessments(self._plan(state), state, seat, self._tasks)

    def _active_tasks(self, ass: dict[int, Assessment]) -> set[int]:
        if self.w.get("task_first", 0) or self._plan_on:  # a task is live while a schedule fits
            return {h for h, a in ass.items() if a.feasible}
        floor = self.w.get("task_place_prob", 0.2)
        return {h for h, a in ass.items() if a.prob >= floor}

    def _wood_work(
        self, state: LignumState, legal: list[int], seat: int, rng: random.Random
    ) -> int:
        """W5-W7 with held tasks: place wood on live tasks first, keep the pieces a live task
        still needs out of the sale, and send them into drying first."""
        ass = self._held_assessments(state, seat)
        active = self._active_tasks(ass)
        first = bool(self.w.get("task_first", 0)) or self._plan_on
        commit = (
            set(active)
            if first
            else {
                h
                for h in active
                if ass[h].sure or ass[h].prob >= self.w.get("task_commit_prob", 0.0)
            }
        )
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        reserved: dict[tuple[int, int], int] = {}
        for h in active:
            for key in ass[h].reserved:
                reserved[key] = reserved.get(key, 0) + 1
        if first and state.phase in (PHASE_W6, PHASE_W7):
            for key in self._anticipated(state, seat, ass):
                reserved[key] = reserved.get(key, 0) + 1
        jres = self._joinery_reserve(state, seat, reserved) if self.w.get("joinery_plan") else {}
        if state.phase in (PHASE_W5, PHASE_N4):
            best: tuple[tuple[float, int, int], int] | None = None
            for a in legal:
                d = A.decode(a)
                if d.name != "PLACE_TASK":
                    continue
                task = t.task_slots[d.params[0]][0]
                if task not in commit:
                    continue
                if first and not self._keeps_schedule(state, a, seat, task):
                    continue
                done = bin(state.filled[task]).count("1") + 1
                key = (done / len(self._tasks[task].requirements), d.params[1], -d.params[0])
                if best is None or key > best[0]:
                    best = (key, a)
            if best is not None:
                return best[1]
            slot = min(
                (x for x in range(3) if not 0 <= state.joinery_wood[seat][x] <= 2), default=3
            )
            for a in legal:  # planned joinery pieces next (a piece the tasks do not need)
                d = A.decode(a)
                if (
                    d.name == "PLACE_JOINERY"
                    and jres.get((2, 2 * d.params[0] + 1), 0)
                    and d.params[1] == slot
                ):
                    return a
            keep: list[int] = []
            for a in legal:
                d = A.decode(a)
                if d.name == "PLACE_TASK" and t.task_slots[d.params[0]][0] not in commit:
                    continue
                if d.name == "PLACE_JOINERY":
                    k = d.params[0]
                    n = state.dry[seat][1][3 + k]
                    if reserved.get((2, 2 * k + 1), 0) >= n:
                        continue
                keep.append(a)
            return self._lookahead(state, keep or legal, seat, rng)
        for key, n in jres.items():
            reserved[key] = reserved.get(key, 0) + n
        if state.phase == PHASE_W6:

            def sellable(s: LignumState, acts: list[int]) -> list[int]:
                out: list[int] = []
                for a in acts:
                    d = A.decode(a)
                    if d.name == "SELL":
                        z, p = d.params
                        have = (
                            (s.sale_logs if p % 2 else s.sale)[seat][p // 2]
                            if z == 0
                            else s.dry[seat][z - 1][p // 2 + 3 * (p % 2)]
                        )
                        if have <= reserved.get((z, p), 0):
                            continue
                    out.append(a)
                return out

            keep = sellable(state, legal)
            sv = self.w.get("solver")
            if sv and sv["enabled"] and state.phase in self._solver_phases(sv):
                move = self._solve(state, keep or legal, seat, sv, sellable)
                if move is not None:
                    return move
            return self._lookahead(state, keep or legal, seat, rng)
        # W7: reserved sale pieces enter drying first
        enter = [
            a
            for a in legal
            if A.decode(a).name == "DRY_ENTER" and reserved.get((0, A.decode(a).params[0]), 0)
        ]
        if enter:
            return enter[0]
        return self._lookahead(state, legal, seat, rng)

    def _anticipated(
        self, state: LignumState, seat: int, ass: dict[int, Assessment]
    ) -> list[tuple[int, int]]:
        """v3: pieces to keep out of the sale for a card on the task row that they would finish
        (wood first, card next round at the Tasks stop), if the seat has room for another card."""
        if len(state.held_tasks[seat]) >= self.w["max_held_tasks"] or state.task_taken[seat]:
            return []
        if self._plan_on:
            slack = int(self.pw.get("take_slack", 1))
            pbest: tuple[int, list[tuple[int, int]]] | None = None
            for ti in state.task_row:
                if ti in state.held_tasks[seat]:
                    continue
                tp = candidate_plan(state, seat, ti)
                if (
                    tp.finishable
                    and tp.slack >= slack
                    and tp.stock_pieces
                    and (pbest is None or tp.reward > pbest[0])
                ):
                    pbest = (tp.reward, list(tp.stock_pieces))
            return pbest[1] if pbest else []
        planner = self._plan(state)
        held = list(ass)
        floor = self.w.get("task_take_prob", 0.3)
        best: tuple[float, list[tuple[int, int]]] | None = None
        for ti in state.task_row:
            if ti in state.held_tasks[seat]:
                continue
            a = planner.assess(state, seat, held, ti)[ti]
            if not (a.feasible and a.prob >= floor and a.reserved):
                continue
            net = planner.worth(a, self._tasks[ti].reward)
            if best is None or net > best[0]:
                best = (net, a.reserved)
        return best[1] if best else []

    def _keeps_schedule(self, state: LignumState, action: int, seat: int, task: int) -> bool:
        """v3: placing this piece must leave the task finishable (a piece may be wanted for a
        deeper-dried slot of the same card)."""
        after = state.search_clone()
        after.fast_apply = True
        after.apply_action(action)
        if after.filled[task] == (1 << len(self._tasks[task].requirements)) - 1:
            return True
        if self._plan_on:
            tp = task_plan(after, seat).get(task)
            return tp is not None and tp.finishable
        return self._plan(state).assess(after, seat, [task])[task].feasible

    def _joinery_reserve(
        self, state: LignumState, seat: int, task_res: dict[tuple[int, int], int]
    ) -> dict[tuple[int, int], int]:
        """Milled logs to keep for the joinery (v2, profile key ``joinery_plan``): one per kind not
        yet in the joinery, only while a joiner covers a free slot (R-082), only pieces that can
        stand in drying area 2 at some later W5 or N4 (R-057 places from drying 2 only, so a piece
        in drying 3 is lost to it), hardwood first. Pieces a held task needs are left to it."""
        if not state.joinery:
            return {}
        free = state.joiners[seat] - sum(1 for k in state.joinery_wood[seat] if 0 <= k < 3)
        if free <= 0:
            return {}
        planner = self._plan(state)
        clock = planner._clock(state)  # pyright: ignore[reportPrivateUsage]
        stock = planner._stock(state, seat)  # pyright: ignore[reportPrivateUsage]
        placed = {k for k in state.joinery_wood[seat] if 0 <= k < 3}
        out: dict[tuple[int, int], int] = {}
        for kind in (2, 1, 0):
            if kind in placed or free <= 0:
                continue
            p = 2 * kind + 1
            best: tuple[int, int] | None = None
            best_at = 99
            for (z, q), n in stock.items():
                if q != p or n - task_res.get((z, q), 0) - out.get((z, q), 0) <= 0:
                    continue
                at = planner._ready(z, 1, clock)  # pyright: ignore[reportPrivateUsage]
                if at is not None and at < best_at:
                    best, best_at = (z, q), at
            if best is not None:
                out[best] = out.get(best, 0) + 1
                free -= 1
        return out

    def _best_task(
        self, state: LignumState, seat: int, offered: list[int]
    ) -> tuple[int, float] | None:
        """(task, net) of the best offered task worth its card price, None if none is."""
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        if self._plan_on:  # v7: take only a card the plan can finish with slack to spare
            slack = int(self.pw.get("take_slack", 1))
            rank = self.w.get("task_rank", "base")
            pick: tuple[int, float] | None = None
            for ti in offered:
                if not task_take_ok(state, seat, ti, slack):
                    continue
                net = task_premium(t, self._tasks[ti], rank == "premium_piece")
                if net - t.price_location < self.pw.get("take_margin", 0.0):
                    continue
                if pick is None or net > pick[1]:
                    pick = (ti, net)
            return pick
        planner = self._plan(state)
        held = list(self._held_assessments(state, seat))
        floor = self.w.get("task_take_prob", 0.3)
        margin = self.w.get("task_take_margin", 2.0)
        rank = self.w.get("task_rank", "base")
        best: tuple[int, float] | None = None
        for ti in offered:
            a = planner.assess(state, seat, held, ti)[ti]
            if self.w.get("task_first", 0):
                net = planner.worth(a, self._tasks[ti].reward) - t.price_location
                ok = a.feasible and a.prob >= floor and net >= margin
            else:
                net = a.net - t.price_location
                ok = a.prob >= floor and net >= margin
            if ok and rank != "base":  # v4 task_rank: among the cards that pass, best premium
                net = task_premium(t, self._tasks[ti], rank == "premium_piece")
            if ok and (best is None or net > best[1]):
                best = (ti, net)
        return best

    # ------------------------------------------------------------------ lookahead
    def _lookahead(
        self, state: LignumState, legal: list[int], seat: int, rng: random.Random
    ) -> int:
        cands = [a for a in legal if A.decode(a).name not in _HUT_NAMES] or legal
        best: list[int] = []
        best_key: tuple[float, int] | None = None
        for a in cands:
            key = (self._score(state, a, seat), 0 if a == A.DONE else 1)
            if best_key is None or key > best_key:
                best, best_key = [a], key
            elif key == best_key:
                best.append(a)
        return rng.choice(best)

    def _score(self, state: LignumState, action: int, seat: int) -> float:
        after = state.search_clone()
        after.fast_apply = True
        after.apply_action(action)
        if (
            action in _SETUP_ACTIONS
            and not after.is_terminal()
            and not after.is_chance_node()
            and after.current_player() == seat
        ):
            follow = [a for a in bot_candidates(after) if a != A.TAKE_LOAN]
            if follow:
                return max(self._score_leaf(after, a, seat) for a in follow)
        return value(after, seat, self.vw)

    def _score_leaf(self, state: LignumState, action: int, seat: int) -> float:
        after = state.search_clone()
        after.fast_apply = True
        after.apply_action(action)
        return value(after, seat, self.vw)

    # ------------------------------------------------------------------ cutting-area picks
    def _pick_area(self, state: LignumState, legal: list[int], rng: random.Random) -> int:
        weight = self.w["area_wood_weight"]
        need = self._wood_needs(state) if self.w.get("task_first", 0) else (0, 0, 0)
        bonus = self.w.get("task_pick_bonus", 0.0)
        if self._plan_on:  # v7: wood the plan still has to cut for finishable held tasks
            need = self._plan_needs(state)
            bonus = self.pw.get("pick_bonus", 0.0)
        hw_bonus = self.w.get("pick_hw_task_bonus", 0.0)
        hw_need = self._hw_target(state) if hw_bonus else 0

        def score(a: int) -> float:
            area = A.decode(a).params[0]
            if not state.wood:
                return 0.0
            got = state.wood[area]
            return (
                sum(n * w for n, w in zip(got, weight, strict=True))
                + bonus * sum(min(got[k], need[k]) for k in range(3))
                + hw_bonus * min(got[2], hw_need)
            )

        top = max(score(a) for a in legal)
        return rng.choice([a for a in legal if score(a) == top])

    def _hw_target(self, state: LignumState, anticipate: bool = True) -> int:
        """v4 (``pick_hw_task_bonus``): hardwood pieces still wanted for tasks, from the seat's own
        holdings and the public task row. Unfilled hardwood slots of held tasks, plus, if the seat
        has room for another card, can pay for it and the row offers one, the fewest hardwood slots
        on any offered card; less the hardwood already in the seat's sale, drying, sawing and
        woodpile areas."""
        seat = state.current_player()
        need = 0
        for h in state.held_tasks[seat]:
            for r, req in enumerate(self._tasks[h].requirements):
                if req.kind == "hardwood" and not state.filled[h] >> r & 1:
                    need += 1
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        if (
            anticipate
            and len(state.held_tasks[seat]) < self.w["max_held_tasks"]
            and not state.task_taken[seat]
            and state.task_row
            and state.money[seat] >= t.price_location
        ):
            need += min(
                sum(r.kind == "hardwood" for r in self._tasks[ti].requirements)
                for ti in state.task_row
            )
        if not need:
            return 0
        have = int(state.sawing[seat][2]) + int(state.woodpile[seat][2])
        for (_, p), n in self._plan(state)._stock(state, seat).items():  # pyright: ignore[reportPrivateUsage]
            if p // 2 == 2:
                have += n
        return max(0, need - have)

    def _plan_needs(self, state: LignumState) -> tuple[int, int, int]:
        """v7: pieces per kind that finishable held tasks can only get by cutting new wood."""
        need = [0, 0, 0]
        for tp in task_plan(state, state.current_player()).tasks:
            if tp.finishable:
                for s in tp.missing:
                    if s.source == "cut":
                        need[s.piece.kind] += 1
        return (need[0], need[1], need[2])

    def _wood_needs(self, state: LignumState) -> tuple[int, int, int]:
        """v3: pieces of each kind that unfinished held tasks still need beyond the wood the
        seat already has in its sale / drying / sawing / woodpile areas (hidden-pick weights)."""
        seat = state.current_player()
        have = [0, 0, 0]
        for (_, p), n in self._plan(state)._stock(state, seat).items():  # pyright: ignore[reportPrivateUsage]
            have[p // 2] += n
        for k in range(3):
            have[k] += int(state.sawing[seat][k]) + int(state.woodpile[seat][k])
        need = [0, 0, 0]
        for h in state.held_tasks[seat]:
            for r, req in enumerate(self._tasks[h].requirements):
                if not state.filled[h] >> r & 1:
                    need[("firewood", "softwood", "hardwood").index(req.kind)] += 1
        return (
            max(0, need[0] - have[0]),
            max(0, need[1] - have[1]),
            max(0, need[2] - have[2]),
        )

    # ------------------------------------------------------------------ supply path
    def _provision(self, state: LignumState, seat: int) -> tuple[int, int]:
        """(saws, food) still to acquire for the next winter, (0, 0) unless the profile provisions
        (v2). Heating needs milled wood in the firewood storage and a firewood disk milled with one
        saw makes 4 pieces, so saws short = ceil(missing heat / 4) - saws held. Food missing counts
        only in the last seasonal round before the winter (area food and path tokens still come
        before). A $1 saw or food at the Market is far below the $3 shortfall per unit."""
        if not self.w.get("provision", 0):
            return 0, 0
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        draws = state.draws.winter
        for year, wr in enumerate(t.winter_rounds):
            if wr > state.round and year < len(draws):
                break
        else:
            return 0, 0
        w = draws[year]
        req_food, req_heat = t.winter_req[year][w // 2][w % 2]
        gap = max(0, req_heat - sum(state.store[seat]))
        per_saw = t.sawing_yield[0]
        saws = -(-gap // per_saw) - state.equip[seat][0] if per_saw else 0
        saws = max(0, min(saws, t.max_saws - state.equip[seat][0]))
        food = 0
        if wr - state.round <= 2:
            due = req_food + state.joiners[seat] * t.joiner_food
            if has_building(t, state.held_buildings, seat, "storeroom"):
                due = max(0, due - building_param(t, "storeroom", "winter_food_reduction"))
            food = max(0, due - state.food[seat])
        return saws, food

    def _hire_joiner(self, state: LignumState, seat: int) -> bool:
        """Joiner discipline (v2, profile keys ``joiner_max`` and ``joiner_last_round``, absent in
        v1: always hire). A joiner pays $1 at the start of each later seasonal round and costs 1
        food per winter (R-079, R-071), so a late hire is a net loss."""
        cap = self.w.get("joiner_max")
        if cap is not None and state.joiners[seat] >= cap:
            return False
        last = self.w.get("joiner_last_round")
        return last is None or state.round <= last

    def _bearer_need(self, state: LignumState, seat: int) -> int:
        """Bearers worth hiring this round (v2 flow policy, profile key ``flow``): one per woodpile
        piece or piece about to be cut (``flow_cut_share`` of the planned cuts), minus the mill
        worker's free carry and the extra pieces of a wagon trip already in hand, at most
        ``flow_max_bearers``. 0 when the profile has no ``flow``. Carrying a piece is worth its $1
        hire (unmilled sale or sawing), but the bot is short of cash, so more bearers lose money."""
        if not self.w.get("flow", 0):
            return 0
        pile = sum(state.woodpile[seat])
        area = sum(state.wood[state.picks[seat]]) if state.wood else 0
        plan_cut = min(self.w["woodcutter_cap"][_best_kind(state, seat)], area)
        cuts = max(state.hired_w[seat], plan_cut)
        cuts = int(cuts * self.w.get("flow_cut_share", 1.0))
        need = pile + cuts - (0 if state.mill_used[seat] else 1)
        if state.equip[seat][IDX_WAGON] and (state.fodder3[seat] or state.fodder2[seat]):
            need -= 2 if state.fodder2[seat] and not state.fodder3[seat] else 3
            need += 1
        return max(0, min(need, self.w.get("flow_max_bearers", 4)))

    def _bearer_cap(self, state: LignumState, seat: int) -> int:
        cap = self.w["bearer_cap"][_best_kind(state, seat)]
        return max(cap, self._bearer_need(state, seat))

    def _location_key(self, state: LignumState, seat: int, number: int) -> str | None:
        """Ranking key of a destination, None when it is not worth a stop for this seat."""
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        if number == CLEARING_LOC:
            return "clearing"
        kind = state._loc_kind(number)  # pyright: ignore[reportPrivateUsage]
        money = state.money[seat]
        best = _best_kind(state, seat)
        if kind == "token_spot":
            y = state.path_tokens[t.token_spots.index(number)]
            if y < 0:
                return None
            name = SPOT_NAMES[y]
            if name == "x_marker":
                return None
            if name in CRAFT_ORDER:
                if name == "joker":
                    return "joker"
                held = state.held_craft[seat]
                return "craft_set" if held[CRAFT_ORDER.index(name)] or held[-1] else "craft_other"
            if name == "saw" and self._provision(state, seat)[0] > 0:
                return "saw_need"
            return name
        if kind in ("woodcutters", "bearers"):
            if money < t.price_location:
                return None
            if kind == "woodcutters":
                cap = self.w["woodcutter_cap"][best]
                if state.path_w <= 0 or state.hired_w[seat] >= cap:
                    return None
            else:
                if state.path_b <= 0 or state.hired_b[seat] >= self._bearer_cap(state, seat):
                    return None
                backlog = self._bearer_need(state, seat) > state.hired_b[seat]
                if backlog and "bearers_backlog" in self.w["location_weights"]:
                    return "bearers_backlog"
            return f"{kind}_{best}"
        if kind == "sawyers":
            ok = state.path_sf > 0 and state.hired_s[seat] < self.w["max_sawyers"]
            return "sawyers" if ok else None
        if kind == "tasks":
            ok = (
                money >= t.price_location and len(state.held_tasks[seat]) < self.w["max_held_tasks"]
            )
            if ok and self.w.get("task_pipeline", 0):
                ok = self._best_task(state, seat, list(state.task_row)) is not None
            return "tasks" if ok and state.task_row and not state.task_taken[seat] else None
        if kind == "market":
            need_saws, need_food = self._provision(state, seat)
            if (need_saws or need_food) and money >= t.price_saw:
                return "market_need"
            if craft_sales(state.held_craft[seat]):
                return "market_sell"
            return "market" if money >= t.price_food else None
        if kind == "fodder":
            ok = state.equip[seat][1] and money >= t.price_location
            return "fodder" if ok else None
        if kind == "planned_work":
            return "planned_work"
        if kind == "joiner" and not self._hire_joiner(state, seat):
            return None
        return kind

    def _stop_cost(self, state: LignumState, seat: int, key: str) -> int:
        """Dollars a stop is expected to spend (prices from the component data)."""
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        best = _best_kind(state, seat)
        if key.startswith("woodcutters"):
            return t.price_location * (self.w["woodcutter_cap"][best] - state.hired_w[seat])
        if key.startswith("bearers"):
            return t.price_location * (self._bearer_cap(state, seat) - state.hired_b[seat])
        if key in ("tasks", "fodder"):
            return t.price_location
        if key == "market":
            return t.price_food
        if key == "market_need":
            saws, food = self._provision(state, seat)
            return min(state.money[seat], saws * t.price_saw + food * t.price_food)
        return 0

    def _move(self, state: LignumState, legal: list[int], seat: int, rng: random.Random) -> int:
        """Pick the stops worth their cost greedily by weight within the money in hand, then go to
        the nearest of them (the foreman only moves forward, so the path order decides)."""
        moves = [a for a in legal if A.decode(a).name == "MOVE_TO"]
        if not moves:
            return self._lookahead(state, legal, seat, rng)
        weights = self.w["location_weights"]
        stops: list[tuple[float, int, int, int]] = []  # (weight, number, cost, action)
        for a in moves:
            number = A.decode(a).params[0]
            key = self._location_key(state, seat, number)
            if key is None or key not in weights or number == CLEARING_LOC:
                continue
            stops.append((weights[key], number, self._stop_cost(state, seat, key), a))
        budget = state.money[seat]
        chosen: list[tuple[int, int]] = []
        for _, number, cost, a in sorted(stops, key=lambda x: (-x[0], x[1])):
            if cost <= budget:
                budget -= cost
                chosen.append((number, a))
        return min(chosen)[1] if chosen else moves[-1]  # clearing is always legal and last

    def _visit(self, state: LignumState, legal: list[int], seat: int, rng: random.Random) -> int:
        """Choices inside an open supply-path visit."""
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        kind = state._loc_kind(state.visit_loc)  # pyright: ignore[reportPrivateUsage]
        acts = [a for a in legal if a != A.TAKE_LOAN]
        if not acts:
            return legal[0]
        names = {a: A.decode(a) for a in acts}
        best = _best_kind(state, seat)

        def done_or(default: int) -> int:
            return A.DONE if A.DONE in acts else default

        if kind == "woodcutters":
            hire = [a for a in acts if names[a].name == "HIRE_WOODCUTTER"]
            if hire and state.hired_w[seat] < self.w["woodcutter_cap"][best]:
                return hire[0]
            return done_or(acts[0])
        if kind == "bearers":
            hire = [a for a in acts if names[a].name == "HIRE_BEARER"]
            if hire and state.hired_b[seat] < self._bearer_cap(state, seat):
                return hire[0]
            return done_or(acts[0])
        if kind == "sawyers":
            hire = [a for a in acts if names[a].name == "HIRE_SAWYER"]
            if hire and state.hired_s[seat] < self.w["max_sawyers"]:
                return hire[0]
            return done_or(acts[0])
        if kind == "tasks":
            tasks = load_components().tasks
            if self.w.get("task_pipeline", 0):
                pick = self._best_task(state, seat, [names[a].params[0] for a in acts])
                if pick is not None:
                    return next(a for a in acts if names[a].params[0] == pick[0])

            task_rank = self.w.get("task_rank", "base")

            def task_score(a: int) -> float:
                task = tasks[names[a].params[0]]
                if task_rank != "base":
                    return task_premium(t, task, task_rank == "premium_piece")
                return task.reward / len(task.requirements)

            return max(acts, key=lambda a: (task_score(a), -a))
        if kind == "planned_work":
            weights = self.w["plan_weights"]
            return max(
                acts,
                key=lambda a: (
                    weights.get(self._pw_ids[names[a].params[0]], 0.0)
                    - plan_cost(t, state, names[a].params[0], seat),
                    -names[a].params[1],
                ),
            )
        if kind == "buildings":
            order = self.w["building_order"]

            def rank(a: int) -> int:
                bid = self._bld_ids[names[a].params[0]]
                return order.index(bid) if bid in order else len(order)

            return min(acts, key=rank)
        if kind == "market":
            return self._market(state, acts, names, seat, rng)
        return self._lookahead(state, acts, seat, rng)

    def _market(
        self,
        state: LignumState,
        acts: list[int],
        names: dict[int, Any],
        seat: int,
        rng: random.Random,
    ) -> int:
        base = value(state, seat, self.vw)
        sells = [
            a
            for a in acts
            if names[a].name in ("SELL_SET", "SELL_EQUIP", "SELL_FOOD", "SELL_SET_JOKERS")
        ]
        gains = [(self._score(state, a, seat) - base, a) for a in sells]
        gains = [g for g in gains if g[0] > 0]
        if gains:
            return max(gains)[1]
        t = state._tables()  # pyright: ignore[reportPrivateUsage]
        need_saws, need_food = self._provision(state, seat)
        if need_saws and A.BUY_SAW in acts and state.money[seat] >= t.price_saw:
            return A.BUY_SAW
        if need_food and A.BUY_FOOD in acts and state.money[seat] >= t.price_food:
            return A.BUY_FOOD
        spare = state.money[seat] - self.w["reserve_money"]
        saws = state.equip[seat][0]
        if A.BUY_SAW in acts and saws < self.w["saw_target"] and spare >= t.price_saw:
            return A.BUY_SAW
        if (
            A.BUY_FOOD in acts
            and spare >= t.price_food
            and self._score(state, A.BUY_FOOD, seat) > base
        ):
            return A.BUY_FOOD
        if A.DONE in acts:
            return A.DONE
        for a in (A.BUY_FOOD, A.BUY_SAW):  # a visit needs one purchase
            if a in acts:
                return a
        return acts[0]
