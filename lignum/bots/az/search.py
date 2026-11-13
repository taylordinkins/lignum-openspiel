"""PUCT search for the AZ bot (AlphaZero-style, general-sum, imperfect information).

Each simulation draws a world in which the other seats' unrevealed picks are resampled
(``lignum.bots.resample``, R-029/R-038), walks the tree by PUCT, expands one leaf with the net
(priors over the candidates, a value per seat), and backs up. Every seat maximises its own
predicted final dollars (optionally minus ``margin`` times the other seats' mean), so the value is
a vector, not a zero-sum scalar. Chance outcomes are sampled; a child is keyed by the decision plus
the chance outcomes that followed it. Loans are filtered as in ``bot_candidates`` (D29) at the
root, and as in the MCTS rollouts inside the tree.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from lignum import actions as A
from lignum.bots.az.features import Encoder
from lignum.bots.az.net import NumpyNet
from lignum.bots.base import bot_candidates
from lignum.bots.resample import resample
from lignum.game import PHASE_NB, PHASE_PK, PHASE_SF, PHASE_SP, PHASE_TR, PHASE_WS, LignumState

PriorHook = Callable[[LignumState, list[int]], int | None]
DefaultPolicy = Callable[[LignumState, random.Random], int]
STRATEGIC_PHASES = frozenset((PHASE_SP, PHASE_PK, PHASE_TR, PHASE_WS, PHASE_NB))


KEY_FAMILIES = frozenset(("TAKE_TASK", "PLAN_WORK", "CHOOSE_BUILDING", "PICK_AREA", "TAKE_BONUS"))


def is_key(cands: list[int]) -> bool:
    """Tasks, planned work, buildings, area picks and the winter bonus: always searched."""
    return any(A.decode(a).name in KEY_FAMILIES for a in cands)


def is_strategic(state: LignumState) -> bool:
    """Area picks, the supply path (travel, purchases, tasks, plans, buildings), winter bonus."""
    return state.phase in STRATEGIC_PHASES


@dataclass
class SearchConfig:
    sims: int = 64
    c_puct: float = 1.5
    q_scale: float = 10.0  # dollars per unit of Q in the PUCT score
    fpu: float = 2.0  # dollars below the node's value for unvisited children
    margin: float = 0.0
    dirichlet: float = 0.0  # root noise weight (self-play only)
    dirichlet_alpha: float = 0.3
    prior_mix: float = 0.0  # weight of the strategist's move in the priors (priming)
    macro: bool = True  # tree nodes only at strategic decisions; the default policy plays the rest
    leaf_steps: int = 0  # default-policy decisions played past a new leaf before its value
    skip_conf: float = 1.1  # no search when the root prior's top candidate has at least this
    opp_default: bool = False  # other seats' decisions in the tree are played by the default policy
    key_mult: float = 1.0  # sims multiplier at key decisions (never skipped)


class Node:
    __slots__ = ("player", "actions", "prior", "n", "w", "children", "value", "total")

    def __init__(self, player: int, actions: list[int], prior: np.ndarray, value: np.ndarray):
        self.player = player
        self.actions = actions
        self.prior = prior
        self.n = np.zeros(len(actions), np.float64)
        self.w = np.zeros(len(actions), np.float64)
        self.children: dict[tuple[int, tuple[int, ...]], Node] = {}
        self.value = value  # absolute-seat dollars predicted at expansion
        self.total = 0


def tree_candidates(state: LignumState) -> list[int]:
    legal = state.legal_actions()
    if len(legal) > 1 and state.phase != PHASE_SF and A.TAKE_LOAN in legal:
        return [a for a in legal if a != A.TAKE_LOAN]
    return legal


class Searcher:
    def __init__(
        self,
        net: NumpyNet,
        encoder: Encoder,
        cfg: SearchConfig,
        prior_hook: PriorHook | None = None,
        default: DefaultPolicy | None = None,
    ) -> None:
        self.default = default
        self.net = net
        self.enc = encoder
        self.cfg = cfg
        self.prior_hook = prior_hook
        self.n = encoder.n

    # ------------------------------------------------------------------ net
    def evaluate(self, state: LignumState, cands: list[int]) -> tuple[np.ndarray, np.ndarray]:
        """Priors over ``cands`` and the absolute-seat value vector (dollars)."""
        seat = state.current_player()
        x = self.enc.encode(state, seat)[None, :]
        logits, v = self.net.forward(x)
        lg = logits[0, cands]
        lg = lg - lg.max()
        p = np.exp(lg)
        p /= p.sum()
        if self.cfg.prior_mix > 0 and self.prior_hook is not None and len(cands) > 1:
            a = self.prior_hook(state, cands)
            if a is not None and a in cands:
                p = p * (1 - self.cfg.prior_mix)
                p[cands.index(a)] += self.cfg.prior_mix
        vals = np.empty(self.n)
        for k in range(self.n):
            vals[(seat + k) % self.n] = v[0, k]
        return p, vals

    def _leaf_value(self, state: LignumState, rng: random.Random, vals: np.ndarray) -> np.ndarray:
        assert self.default is not None
        st = state.search_clone()
        steps = 0
        while not st.is_terminal() and steps < self.cfg.leaf_steps:
            if st.is_chance_node():
                o, p = zip(*st.chance_outcomes(), strict=True)
                st.apply_action(rng.choices(o, p)[0])
                continue
            st.apply_action(self.default(st, rng))
            steps += 1
        if st.is_terminal():
            return np.array(st.final, np.float64)
        if st.is_chance_node():
            return vals
        return self.evaluate(st, tree_candidates(st))[1]

    def _objective(self, vals: np.ndarray, seat: int) -> float:
        if self.cfg.margin == 0 or self.n == 1:
            return float(vals[seat])
        others = (vals.sum() - vals[seat]) / (self.n - 1)
        return float(vals[seat] - self.cfg.margin * others)

    # ------------------------------------------------------------------ search
    def run(
        self, state: LignumState, rng: random.Random, sims: int | None = None
    ) -> tuple[list[int], np.ndarray, np.ndarray, Node]:
        """Search from ``state`` (acting seat's view). Returns (cands, visits, q, root)."""
        cfg = self.cfg
        seat = state.current_player()
        cands = bot_candidates(state)
        prior, vals = self.evaluate(state, cands)
        if cfg.dirichlet > 0 and len(cands) > 1:
            noise = np.random.default_rng(rng.randrange(1 << 31)).dirichlet(
                [cfg.dirichlet_alpha] * len(cands)
            )
            prior = (1 - cfg.dirichlet) * prior + cfg.dirichlet * noise
        root = Node(seat, cands, prior, vals)
        # Only other seats' unrevealed picks are resampled; without them every world is the same
        # and stored actions stay legal.
        hidden = any(s != seat for s in range(len(state.pk)))
        for _ in range(sims if sims is not None else cfg.sims):
            world = resample(state, seat, rng) if hidden else state.search_clone()
            world.fast_apply = True
            self._simulate(root, world, rng, hidden)
        q = np.where(root.n > 0, root.w / np.maximum(root.n, 1), -1e9)
        return cands, root.n.copy(), q, root

    def _select(self, node: Node, legal: set[int] | None) -> int:
        cfg = self.cfg
        sq = math.sqrt(node.total + 1)
        base = self._objective(node.value, node.player) - cfg.fpu
        best_i, best = -1, -math.inf
        for i, a in enumerate(node.actions):
            if legal is not None and a not in legal:
                continue
            ni = node.n[i]
            q = node.w[i] / ni if ni else base
            u = q / cfg.q_scale + cfg.c_puct * node.prior[i] * sq / (1 + ni)
            if u > best:
                best_i, best = i, u
        return best_i

    def _simulate(self, root: Node, state: LignumState, rng: random.Random, hidden: bool) -> None:
        node = root
        trail: list[tuple[Node, int]] = []
        first = True
        while True:
            legal = None if (first or not hidden) else set(tree_candidates(state))
            first = False
            i = self._select(node, legal)
            if i < 0:  # determinization made every stored action illegal
                vals = node.value
                break
            a = node.actions[i]
            trail.append((node, i))
            state.apply_action(a)
            outs: list[int] = []
            cands: list[int] = []
            while not state.is_terminal():  # chance outcomes and forced moves are not nodes
                if state.is_chance_node():
                    o, p = zip(*state.chance_outcomes(), strict=True)
                    c = rng.choices(o, p)[0]
                    state.apply_action(c)
                    outs.append(c)
                    continue
                cands = tree_candidates(state)
                if len(cands) != 1:
                    if self.default is not None and (
                        (self.cfg.macro and not is_strategic(state))
                        or (self.cfg.opp_default and state.current_player() != root.player)
                    ):
                        d = self.default(state, rng)
                        state.apply_action(d)
                        outs.append(1000 + d)
                        continue
                    break
                state.apply_action(cands[0])
                outs.append(1000 + cands[0])
            if state.is_terminal():
                vals = np.array(state.final, np.float64)
                break
            key = (a, tuple(outs))
            child = node.children.get(key)
            if child is None:
                pr, vals = self.evaluate(state, cands)
                node.children[key] = Node(state.current_player(), cands, pr, vals)
                if self.cfg.leaf_steps > 0 and self.default is not None:
                    vals = self._leaf_value(state, rng, vals)
                break
            node = child
        for nd, i in trail:
            nd.n[i] += 1
            nd.w[i] += self._objective(vals, nd.player)
            nd.total += 1
