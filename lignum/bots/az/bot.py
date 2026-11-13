"""The AZ seat: PUCT search over a policy-value net primed on the strategist."""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import pyspiel

from lignum.bots.az.features import Encoder
from lignum.bots.az.net import NumpyNet
from lignum.bots.az.search import SearchConfig, Searcher, is_key, is_strategic
from lignum.bots.base import bot_candidates
from lignum.bots.strategist import StrategistBot
from lignum.game import LignumState

DEFAULT_MODEL = Path(os.environ.get("LIGNUM_AZ_MODEL", "data/bots/az/current.npz"))


class AZBot:
    """``choose`` searches ``cfg.sims`` simulations and plays the most visited candidate.

    With ``sims=0`` it plays the net's policy greedily (no search). ``temperature`` > 0 samples
    the move from visits ** (1 / temperature) instead (self-play exploration).
    """

    def __init__(
        self,
        model: str | Path = DEFAULT_MODEL,
        cfg: SearchConfig | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.net = NumpyNet(model)
        self.cfg = cfg or SearchConfig()
        self.temperature = temperature
        self._enc: dict[int, Encoder] = {}
        self._strat = StrategistBot()
        self._hook_rng = random.Random(0)
        self.last: tuple[list[int], np.ndarray] | None = None  # (cands, visit policy)

    @property
    def strategist(self) -> StrategistBot:
        """The strategist used as prior and default policy (a plan search sets its plans)."""
        return self._strat

    def _prior_hook(self, state: LignumState, cands: list[int]) -> int | None:
        try:
            return self._strat.choose(state, self._hook_rng)
        except Exception:  # noqa: BLE001
            return None

    def searcher(self, state: LignumState) -> Searcher:
        enc = self._enc.get(state.n)
        if enc is None:
            enc = self._enc[state.n] = Encoder(state.get_game())
        return Searcher(self.net, enc, self.cfg, self._prior_hook, self._default)

    def _default(self, state: LignumState, rng: random.Random) -> int:
        return self._strat.choose(state, rng)

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        cands = bot_candidates(state)
        if len(cands) == 1:
            self.last = None
            return cands[0]
        if self.cfg.macro and not is_strategic(state):
            self.last = None
            return self._strat.choose(state, rng)
        s = self.searcher(state)
        if self.cfg.sims <= 0:
            prior, _ = s.evaluate(state, cands)
            self.last = (cands, prior)
            return cands[int(np.argmax(prior))]
        key = is_key(cands)
        if self.cfg.skip_conf <= 1.0 and not key:
            prior, _ = s.evaluate(state, cands)
            if prior.max() >= self.cfg.skip_conf:
                self.last = (cands, prior)
                return cands[int(np.argmax(prior))]
        sims = int(self.cfg.sims * (self.cfg.key_mult if key else 1.0))
        cands, visits, q, _root = s.run(state, rng, sims)
        pol = visits / visits.sum()
        self.last = (cands, pol)
        if self.temperature > 0:
            w = visits ** (1.0 / self.temperature)
            return rng.choices(cands, list(w))[0]
        best = visits.max()
        idx = [i for i in range(len(cands)) if visits[i] == best]
        return cands[max(idx, key=lambda i: q[i])]
