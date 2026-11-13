"""IS-MCTS and determinized MCTS bots (Phase 6 unit 6; R-029, R-038).

Both search from the acting seat's point of view. Each simulation draws a world with the
hidden-pick resampler (``lignum.bots.resample``), walks a UCT tree, expands one node, then scores a
leaf: a (possibly depth-limited) rollout whose end state is valued by ``value_diff`` (expected
dollars over the other seats' mean, squashed by tanh to a reward in (-1, 1); exact at game end).
Nodes are keyed by the action path from the root, so chance outcomes simply branch the tree.
Candidates are ``bot_candidates`` (D29 loan policy), hence only legal moves are ever returned.
OpenSpiel's C++ bots crash on Python games and its Python search is slower, so the search is
written here on shallow clones with ``fast_apply``.

``ISMCTSBot`` shares one tree across worlds; ``DeterminizedMCTSBot`` builds one tree per world
and plays the action with the most summed root visits (cheaper, but strategy fusion).
"""

from __future__ import annotations

import math
import random
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import pyspiel

from lignum import actions as A
from lignum.bots.base import bot_candidates
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.resample import resample
from lignum.bots.value import value
from lignum.bots.weights import DEFAULT_PROFILE, load_profile, thaw, value_weights
from lignum.game import PHASE_SF, LignumState

RolloutPolicy = Literal["random", "heuristic"]
REWARD_SCALE = 25.0  # dollars per tanh unit


@dataclass
class _Node:
    n: int = 0
    prior: int | None = None
    edges: dict[int, list[float]] = field(
        default_factory=dict[int, list[float]]
    )  # action -> [visits, total]


def _sample_chance(state: pyspiel.State, rng: random.Random) -> None:
    actions, probs = zip(*state.chance_outcomes(), strict=True)
    state.apply_action(rng.choices(actions, probs)[0])


class _Search:
    def __init__(
        self,
        policy: RolloutPolicy,
        depth: int | None,
        uct_c: float,
        heuristic: HeuristicBot | None,
        prior: HeuristicBot | None = None,
        widen: float = 1.0,
        prior_weight: float = 1.0,
        vw: Mapping[str, Any] | None = None,
    ) -> None:
        self.vw = vw
        self.widen = widen
        self.prior_weight = prior_weight
        self.prior = prior
        self.policy = policy
        self.depth = depth
        self.uct_c = uct_c
        self.heuristic = heuristic

    def rewards(self, state: LignumState) -> list[float]:
        vals = [value(state, s, self.vw) for s in range(state.n)]
        total = sum(vals)
        n = state.n
        return [math.tanh((v - (total - v) / (n - 1)) / REWARD_SCALE) for v in vals]

    def rollout(self, state: LignumState, rng: random.Random) -> None:
        steps = 0
        while not state.is_terminal() and (self.depth is None or steps < self.depth):
            if state.is_chance_node():
                _sample_chance(state, rng)
                continue
            if self.policy == "heuristic" and self.heuristic is not None:
                state.apply_action(self.heuristic.choose(state, rng))
            else:
                legal = state.legal_actions()
                if len(legal) > 1 and state.phase != PHASE_SF:
                    legal = [a for a in legal if a != A.TAKE_LOAN] or legal
                state.apply_action(rng.choice(legal))
            steps += 1

    def simulate(
        self,
        tree: dict[tuple[int, ...], _Node],
        world: LignumState,
        rng: random.Random,
    ) -> None:
        state = world.search_clone()
        state.fast_apply = True
        path: tuple[int, ...] = ()
        trail: list[tuple[_Node, int, int]] = []  # (node, action, acting seat)
        expanded = False
        while not state.is_terminal():
            if state.is_chance_node():
                a = rng.choices(*zip(*state.chance_outcomes(), strict=True))[0]
                state.apply_action(a)
                path += (a,)
                continue
            cands = bot_candidates(state)
            node = tree.get(path)
            if node is None:
                if expanded:
                    break
                node = tree[path] = _Node()
                expanded = True
            if node.prior is None and self.prior is not None:
                node.prior = self.prior.choose(state, rng)
            tried = [c for c in cands if c in node.edges]
            fresh = [c for c in cands if c not in node.edges]
            stop_after = False
            if fresh and (not tried or len(node.edges) < 1 + int(self.widen * node.n**0.5)):
                a = node.prior if node.prior in fresh else rng.choice(fresh)
                node.edges[a] = [0.0, 0.0]
                stop_after = True
            else:
                logn = math.log(max(node.n, 1))
                best, best_u = tried[0], -math.inf
                for c in tried:
                    v, w = node.edges[c]
                    u = w / v + self.uct_c * math.sqrt(logn / v)
                    if c == node.prior:
                        u += self.prior_weight / (1.0 + v)
                    if u > best_u:
                        best, best_u = c, u
                a = best
            trail.append((node, a, state.current_player()))
            state.apply_action(a)
            path += (a,)
            if stop_after:
                expanded = True
                break
        self.rollout(state, rng)
        rew = self.rewards(state)
        for node, a, seat in trail:
            node.n += 1
            e = node.edges[a]
            e[0] += 1
            e[1] += rew[seat]


class _MCTSBase:
    def __init__(
        self,
        simulations: int = 200,
        time_budget: float | None = None,
        rollout: RolloutPolicy = "random",
        rollout_depth: int | None = 15,
        uct_c: float = 0.7,
        heuristic_prior: bool = True,
        profile: str = DEFAULT_PROFILE,
        policy_profile: str | None = None,
        solver_rollout: bool = False,
        solver_tree: bool = False,
        rollout_solver: Mapping[str, Any] | None = None,
    ) -> None:
        """Unit 5c knobs (all off = the Phase 6 bot, byte-identical): ``policy_profile`` names the
        heuristic profile (with the own-turn solver) used where a switch below is on; the value
        function stays that of ``profile``. ``solver_rollout``: rollouts play that policy, with
        ``rollout_solver`` (e.g. ``{"beam": 3, "node_cap": 40}``) overriding its solver settings
        (a cheaper search). ``solver_tree``: the node prior (first expansion) is that policy's move
        at full solver settings, so in W1-W4/W6 it is the first action of the solver's best
        sequence. The solver reads only the acting seat's resampled world, as the heuristic does."""
        self.profile = profile
        self.policy_profile = policy_profile
        self.solver_rollout = solver_rollout
        self.solver_tree = solver_tree
        self.rollout_solver = dict(rollout_solver or {})
        self.simulations = simulations
        self.time_budget = time_budget
        self.rollout = rollout
        self.rollout_depth = rollout_depth
        self.uct_c = uct_c
        self.vw = value_weights(profile)
        h = HeuristicBot(profile=profile)
        self._fallback = h
        pol = policy_profile or profile
        roll_bot = h
        prior_bot = h
        if solver_rollout or solver_tree:
            sv = load_profile(pol).get("solver")
            if not sv or not sv.get("enabled"):
                raise ValueError(f"profile {pol!r} has no enabled solver: section")
        if solver_rollout:
            w = thaw(load_profile(pol))
            w["solver"] = {**w["solver"], **self.rollout_solver}
            roll_bot = HeuristicBot(weights=w)
        if solver_tree:
            prior_bot = HeuristicBot(profile=pol)
        self._search = _Search(
            rollout,
            rollout_depth,
            uct_c,
            roll_bot if rollout == "heuristic" else None,
            prior_bot if heuristic_prior else None,
            vw=self.vw,
        )

    def _visits(
        self, state: LignumState, rng: random.Random, deadline: float | None
    ) -> Counter[int]:
        raise NotImplementedError

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        cands = bot_candidates(state)
        if len(cands) == 1:
            return cands[0]
        deadline = None if self.time_budget is None else time.perf_counter() + self.time_budget
        visits = self._visits(state, rng, deadline)
        if not any(visits[a] for a in cands):  # time cap hit before any simulation finished
            return self._fallback.choose(state, rng)
        best = max(visits[a] for a in cands)
        return rng.choice([a for a in cands if visits[a] == best])


class ISMCTSBot(_MCTSBase):
    """Single-tree IS-MCTS: a fresh resampled world per simulation (R-029)."""

    def _visits(
        self, state: LignumState, rng: random.Random, deadline: float | None
    ) -> Counter[int]:
        seat = state.current_player()
        tree: dict[tuple[int, ...], _Node] = {}
        for _ in range(self.simulations):
            if deadline is not None and time.perf_counter() >= deadline:
                break
            self._search.simulate(tree, resample(state, seat, rng), rng)
        root = tree.get(())
        return Counter({a: int(e[0]) for a, e in root.edges.items()} if root else {})


class DeterminizedMCTSBot(_MCTSBase):
    """D worlds, one tree each; plays the action with the most summed root visits."""

    def __init__(self, determinizations: int = 4, **kw: float | int | str | None) -> None:
        super().__init__(**kw)  # type: ignore[arg-type]
        self.determinizations = determinizations

    def _visits(
        self, state: LignumState, rng: random.Random, deadline: float | None
    ) -> Counter[int]:
        seat = state.current_player()
        per_world = max(1, self.simulations // self.determinizations)
        visits: Counter[int] = Counter()
        for d in range(self.determinizations):
            world = resample(state, seat, rng)
            tree: dict[tuple[int, ...], _Node] = {}
            sub = None
            if deadline is not None:
                now = time.perf_counter()
                sub = now + (deadline - now) / (self.determinizations - d)
            for _ in range(per_world):
                if sub is not None and time.perf_counter() >= sub:
                    break
                self._search.simulate(tree, world, rng)
            root = tree.get(())
            if root:
                for a, e in root.edges.items():
                    visits[a] += int(e[0])
        return visits
