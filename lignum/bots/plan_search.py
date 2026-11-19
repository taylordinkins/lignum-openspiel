"""Plan-level search: choose each round's plan (cutting area, task to take) by playouts.

At this seat's first decision of a round on the supply side (setup pick, round pick or travel),
candidate ``RoundPlan``s are built: the strategist's own choice, the best few cutting areas (when
the pick is still ahead) crossed with "no task" and the best few laid-out tasks. Each plan is
scored by playouts of the strategist (or another ``sim`` policy built on it) for every seat to the
end of the game, with this seat following the plan for the round; all plans share the same seeds
(common random numbers), and a two-stage race spends the second half of the playouts on the leaders
only. The best plan is set on the executor's strategist (the executor plays every decision: the
strategist itself, or the AZ search whose priors and default policy are that strategist). Other
seats' unrevealed picks are resampled from the strategist's pick model, so no hidden information is
read (R-029, R-038).

With ``ahead`` > 0 the candidates also include two-round plans (this round's task, then the task
for the next seasonal round), so this round's choice is judged with a committed follow-up; the
plan is still searched again every round, optionally favouring the scheduled task
(``commit_bonus``).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

import pyspiel

from lignum import actions as A
from lignum.bots.strategist import Ctx, RoundPlan, StrategistBot, task_value
from lignum.constants import NUM_AREAS
from lignum.game import PHASE_PK, PHASE_SP, PHASE_TR, LignumState

SEASONAL = (1, 2, 3, 5, 6, 7)


@dataclass
class PlanConfig:
    playouts: int = 8  # per plan for the leaders (half of them for every plan)
    areas: int = 2  # area candidates besides the strategist's own pick
    tasks: int = 3  # task candidates besides "own choice" and "no task"
    keep: int = 3  # plans kept for the second stage (plus the strategist's own plan)
    default_bonus: float = 0.5  # dollars of benefit of the doubt for the strategist's own plan
    # Two-round plans: "task t now (own choice, none or a top task), then task y next seasonal
    # round" for y in "no task" and the ``ahead`` best laid-out tasks other than t (0 = off).
    ahead: int = 0
    # Dollars of bonus, when re-planning, for plans that take the task the previous round's plan
    # scheduled for this round (stability; 0 = none).
    commit_bonus: float = 0.0
    # The strategists (executor and playouts) plan wood for scheduled tasks not held yet.
    reserve: bool = False


class PlanSearchBot:
    """``executor``: a ``StrategistBot`` or an ``AZBot`` (its ``strategist`` gets the plan)."""

    def __init__(
        self, executor: Any = None, cfg: PlanConfig | None = None, sim: Any = None
    ) -> None:
        """``sim``: the playout policy for every seat (default a fresh strategist); a bot with a
        ``strat`` attribute (e.g. a greedy ``PPOBot``) gets the plan on that strategist."""
        self.executor = executor if executor is not None else StrategistBot()
        self.strat: StrategistBot = (
            self.executor if isinstance(self.executor, StrategistBot) else self.executor.strategist
        )
        self.cfg = cfg or PlanConfig()
        self.sim_bot: Any = sim if sim is not None else StrategistBot()
        self.sim: StrategistBot = (
            self.sim_bot if isinstance(self.sim_bot, StrategistBot) else self.sim_bot.strat
        )
        self.strat.reserve_planned = self.sim.reserve_planned = self.cfg.reserve
        self._planned: tuple[int, int, int] | None = None
        self._chosen: dict[int, RoundPlan] = {}  # seat -> last plan chosen (for commit_bonus)
        self.last_scores: dict[RoundPlan, float] = {}

    # ------------------------------------------------------------------ entry
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        seat = state.current_player()
        if state.phase in (PHASE_SP, PHASE_PK, PHASE_TR):
            key = (id(state.draws), seat, state.round)
            if key != self._planned and len(state.legal_actions()) > 1:
                self._planned = key
                plan = self.search(state, rng)
                self._chosen[seat] = plan
                self.strat.plans[seat] = plan
        plan = self.strat.plans.get(seat)
        if (
            state.phase in (PHASE_SP, PHASE_PK)
            and plan is not None
            and plan.round == state.round
            and plan.area is not None
        ):
            a = A.encode("PICK_AREA", plan.area)
            if a in state.legal_actions():
                return a
        return self.executor.choose(state, rng)

    # ------------------------------------------------------------------ candidates
    def candidates(self, state: LignumState) -> list[RoundPlan]:
        seat, rnd, cfg = state.current_player(), state.round, self.cfg
        c = Ctx(state, seat, self.strat.w)
        areas: list[int | None] = [None]
        if state.phase in (PHASE_SP, PHASE_PK):
            legal = [A.decode(a).params[0] for a in state.legal_actions()]
            ranked = sorted(legal, key=lambda a: -self.strat.area_value(c, a))
            areas += ranked[: cfg.areas]
        tasks: list[int | None] = [None]
        ranked_t: list[int] = []
        if rnd in SEASONAL and not state.task_taken[seat] and state.task_row:
            vals = {t: task_value(c, t) for t in state.task_row}
            ranked_t = sorted((t for t in vals if vals[t] > -50), key=lambda t: -vals[t])
            tasks += [-1, *ranked_t[: cfg.tasks]]
            due = self._due_task(seat, rnd)
            if due is not None and due in state.task_row and due not in tasks:
                tasks.append(due)
        plans = [RoundPlan(rnd, task=t, area=a) for a in areas for t in tasks]
        nxt = next((r for r in SEASONAL if r > rnd), None)
        if cfg.ahead > 0 and nxt is not None and len(tasks) > 1:
            for t in tasks:
                follow = [-1, *[y for y in ranked_t if y != t][: cfg.ahead]]
                plans += [RoundPlan(rnd, task=t, then=(RoundPlan(nxt, task=y),)) for y in follow]
        return plans

    def _due_task(self, seat: int, rnd: int) -> int | None:
        """The task the previous plan scheduled for round ``rnd`` (None = none or own choice)."""
        prev = self._chosen.get(seat)
        q = prev.for_round(rnd) if prev is not None and prev.round != rnd else None
        return q.task if q is not None and q.task is not None and q.task >= 0 else None

    # ------------------------------------------------------------------ search
    def search(self, state: LignumState, rng: random.Random) -> RoundPlan:
        seat, cfg = state.current_player(), self.cfg
        plans = self.candidates(state)
        default = plans[0]
        self.last_scores = {}
        if len(plans) == 1:
            return default
        seeds = [rng.randrange(1 << 30) for _ in range(cfg.playouts)]
        half = max(1, cfg.playouts // 2)
        sums = {p: sum(self.playout(state, p, seat, sd) for sd in seeds[:half]) for p in plans}
        ranked = sorted(plans, key=lambda p: -sums[p])
        leaders = list(dict.fromkeys([default, *ranked[: cfg.keep]]))
        means: dict[RoundPlan, float] = {}
        for p in leaders:
            rest = sum(self.playout(state, p, seat, sd) for sd in seeds[half:])
            means[p] = (sums[p] + rest) / len(seeds)
        means[default] += cfg.default_bonus
        due = self._due_task(seat, state.round)
        if cfg.commit_bonus and due is not None:
            for p in leaders:
                if p.task == due:
                    means[p] += cfg.commit_bonus
        self.last_scores = means
        return max(leaders, key=lambda p: means[p])

    def playout(self, state: LignumState, plan: RoundPlan, seat: int, seed: int) -> float:
        st = state.search_clone()
        st.fast_apply = False
        rng = random.Random(seed)
        self._resample_picks(st, seat, rng)
        sim = self.sim
        sim.plans = {seat: plan}
        while not st.is_terminal():
            if st.is_chance_node():
                outs = st.chance_outcomes()
                st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            else:
                st.apply_action(self.sim_bot.choose(st, rng))
        sim.plans = {}
        return float(st.final[seat])

    def _resample_picks(self, st: LignumState, seat: int, rng: random.Random) -> None:
        """Other seats' hidden picks of this round, redrawn from the strategist's pick model."""
        if not st.pk or all(e == seat for e in range(len(st.pk))):
            return
        new: list[int] = []
        for e, own in enumerate(st.pk):
            if e == seat:
                new.append(own)
                continue
            oc = Ctx(st, e, self.sim.w)
            vals = [self.sim.area_value(oc, a) for a in range(NUM_AREAS)]
            m = max(vals)
            ws = [math.exp((v - m) / max(0.3, self.sim.w["pick_tau"])) for v in vals]
            new.append(rng.choices(range(NUM_AREAS), ws)[0])
        st.pk = tuple(new)
