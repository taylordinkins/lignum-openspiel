"""Strategist with rollouts at strategic decisions (one-step policy improvement).

At a few decision types (area pick, task choice, planned work, building, winter bonus, joiner
and task stops), each candidate action is evaluated by ``n`` playouts of the strategist for
every seat to the end of the game; the action with the best mean final dollars of the acting
seat wins. Other decisions are the plain strategist's. The opponents' hidden cutting-area pick
(round 2+) is resampled from the strategist's pick model, so no hidden information is read.
Playouts share seeds across candidates (common random numbers).
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

import pyspiel

from lignum import actions as A
from lignum.bots.strategist import Ctx, StrategistBot
from lignum.constants import NUM_AREAS
from lignum.game import PHASE_NB, PHASE_PK, PHASE_TR, LignumState

_VISIT_KINDS = {"tasks": "TAKE_TASK", "planned_work": "PLAN_WORK", "buildings": "CHOOSE_BUILDING"}


class RolloutStrategist:
    def __init__(
        self,
        n: int = 12,
        k: int = 4,
        weights: Mapping[str, float] | None = None,
        moves: bool = True,
        objective: str = "own",
    ) -> None:
        self.base = StrategistBot(weights=weights)
        self.policy = StrategistBot(weights=weights)
        self.n = n
        self.k = k
        self.moves = moves
        self.objective = objective

    # -------------------------------------------------------------- candidates
    def _candidates(self, state: LignumState, legal: list[int], default: int) -> list[int]:
        ph = state.phase
        if ph == PHASE_PK:
            return [a for a in legal if A.decode(a).name == "PICK_AREA"]
        if ph == PHASE_NB and not state.w_dirty:
            return [a for a in legal if A.decode(a).name == "TAKE_BONUS"]
        if ph == PHASE_TR and state.visit_loc:
            kind = self.base.loc_kind(
                Ctx(state, state.current_player(), self.base.w), state.visit_loc
            )
            name = _VISIT_KINDS.get(kind)
            if name:
                opts = [a for a in legal if A.decode(a).name == name]
                return opts[:8]
            return []
        if ph == PHASE_TR and self.moves and not state.hb_open:
            moves = [a for a in legal if A.decode(a).name == "MOVE_TO"]
            # Only at a fork that involves a strategic stop (tasks, joiner, PW, buildings).
            c = Ctx(state, state.current_player(), self.base.w)
            strategic: list[int] = []
            for a in moves:
                loc = A.decode(a).params[0]
                if self.base.loc_kind(c, loc) in ("tasks", "joiner", "planned_work", "buildings"):
                    strategic.append(a)
            if not strategic:
                return []
            nxt = min(strategic, key=lambda x: A.decode(x).params[0])
            cands = {default, nxt}
            # the first non-strategic stop before it (skip vs take the strategic stop)
            return sorted(cands)
        return []

    # -------------------------------------------------------------- rollouts
    def _playout(self, state: LignumState, action: int, seat: int, seed: int) -> float:
        st = state.search_clone()
        st.fast_apply = False
        rng = random.Random(seed)
        if st.phase == PHASE_PK:
            self._resample_picks(st, seat, rng)
        st.apply_action(action)
        pol = self.policy
        steps = 0
        while not st.is_terminal() and steps < 4000:
            if st.is_chance_node():
                outs = st.chance_outcomes()
                a = rng.choices([x for x, _ in outs], [p for _, p in outs])[0]
            else:
                a = pol.choose(st, rng)
            st.apply_action(a)
            steps += 1
        mine = st.final[seat]
        if self.objective == "margin":
            others = [st.final[e] for e in range(st.n) if e != seat]
            return mine - 0.5 * sum(others) / len(others)
        return float(mine)

    def _resample_picks(self, st: LignumState, seat: int, rng: random.Random) -> None:
        """Replace earlier seats' hidden picks of this round by samples of the pick model."""
        if not st.pk:
            return
        new: list[int] = []
        for e, _hidden in enumerate(st.pk):
            oc = Ctx(st, e, self.base.w)
            vals = [self.base.area_value(oc, a) for a in range(NUM_AREAS)]
            m = max(vals)
            ws = [math.exp((v - m) / max(0.3, self.base.w["pick_tau"])) for v in vals]
            new.append(rng.choices(range(NUM_AREAS), ws)[0])
        st.pk = tuple(new)

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        legal = list(state.legal_actions())
        default = self.base.choose(state, rng)
        if len(legal) <= 1 or state.round >= 8:
            return default
        cands = self._candidates(state, legal, default)
        if default not in cands:
            cands = [default, *cands]
        if len(cands) <= 1:
            return default
        seat = state.current_player()
        base_seed = rng.randrange(1 << 30)
        best, best_v = default, -math.inf
        for a in cands:
            v = sum(self._playout(state, a, seat, base_seed + i) for i in range(self.n)) / self.n
            if a == default:
                v += 0.25  # ties and noise favour the base policy
            if v > best_v:
                best, best_v = a, v
        return best
