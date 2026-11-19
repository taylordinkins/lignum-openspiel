"""PPO policy on top of the strategist (docs/PPO.md).

At strategic decisions (``is_strategic``: area picks, the supply path, the winter bonus) with more
than one candidate, the move is drawn from

    pi(a | s) = softmax_a( logits(s)[a] + bonus * [a == strategist(s)] )   over the candidates,

where ``logits`` is the AZ-architecture net (``lignum.bots.az.net``) and ``bonus`` a fixed logit
added to the strategist's move. Starting from the strategist-primed AZ net, this policy is the
strategist plus plausible deviations; PPO (``tools/ppo_train.py``) then moves the net's logits.
Every other decision is the strategist's. ``greedy`` plays the argmax (evaluation and the seat).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyspiel

from lignum.bots.az.features import Encoder
from lignum.bots.az.net import NumpyNet
from lignum.bots.az.search import is_strategic
from lignum.bots.base import bot_candidates
from lignum.bots.strategist import StrategistBot
from lignum.game import LignumState

DEFAULT_BONUS = 3.0


@dataclass
class Step:
    """One recorded decision (the training sample for PPO)."""

    seat: int
    x: np.ndarray  # features (float16)
    cands: list[int]
    sidx: int  # index of the strategist's move in ``cands``
    aidx: int  # index of the move played
    logp: float  # log pi(played) under the acting policy
    value: float  # the net's value of this state for ``seat`` (dollars)


class PPOBot:
    def __init__(
        self,
        model: str | Path,
        bonus: float = DEFAULT_BONUS,
        greedy: bool = True,
        temperature: float = 1.0,
    ) -> None:
        self.net = NumpyNet(model)
        self.bonus = bonus
        self.greedy = greedy
        self.temperature = temperature
        self.strat = StrategistBot()
        self._enc: dict[int, Encoder] = {}
        self.record: list[Step] | None = None  # set to a list to record decisions

    def _encoder(self, state: LignumState) -> Encoder:
        enc = self._enc.get(state.n)
        if enc is None:
            enc = self._enc[state.n] = Encoder(state.get_game())
        return enc

    def policy(
        self, state: LignumState, cands: list[int], a_s: int
    ) -> tuple[np.ndarray, float, np.ndarray]:
        """(probabilities over ``cands``, own value in dollars, features)."""
        seat = state.current_player()
        x = self._encoder(state).encode(state, seat)
        logits, v = self.net.forward(x[None, :])
        lg = logits[0, cands].astype(np.float64)
        lg[cands.index(a_s)] += self.bonus
        lg = lg / self.temperature
        lg -= lg.max()
        p = np.exp(lg)
        p /= p.sum()
        return p, float(v[0, 0]), x

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        a_s = self.strat.choose(state, rng)
        if not is_strategic(state):
            return a_s
        cands = bot_candidates(state)
        if len(cands) <= 1 or a_s not in cands:
            return a_s
        p, v, x = self.policy(state, cands, a_s)
        i = int(np.argmax(p)) if self.greedy else rng.choices(range(len(cands)), list(p))[0]
        if self.record is not None:
            self.record.append(
                Step(
                    seat=state.current_player(),
                    x=x.astype(np.float16),
                    cands=cands,
                    sidx=cands.index(a_s),
                    aidx=i,
                    logp=float(np.log(max(p[i], 1e-12))),
                    value=v,
                )
            )
        return cands[i]
