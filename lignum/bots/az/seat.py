"""The ``az`` server seat (lazy: numpy and the model load on first use, not at server import)."""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

import pyspiel

from lignum.bots.strategist import StrategistBot
from lignum.game import LignumState

DEFAULT_MODEL = Path(os.environ.get("LIGNUM_AZ_MODEL", "data/bots/az/current.npz"))


class AZSeat:
    """Plan-level search over ``AZBot`` with the best measured settings (docs/AZ.md): each round's
    plan (area, task) chosen by 8 strategist playouts per plan, then the AZ search (macro tree, 64
    sims, strategist playouts of 150 decisions per leaf, no search where the blended prior is
    >= 0.97 sure, prior half strategist) plays the moves. About $72.5 a game vs heuristic-v6.

    The net was trained for 2 players on the joinery side; other games (and a missing model file)
    fall back to the strategist, so the seat is always playable.
    """

    def __init__(self, model: str | Path = DEFAULT_MODEL) -> None:
        self.model = Path(model)
        self._bot: Any = None
        self._fallback = StrategistBot()

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        if state.n != 2 or not state.joinery or not self.model.exists():
            return self._fallback.choose(state, rng)
        if self._bot is None:
            from lignum.bots.az.bot import AZBot
            from lignum.bots.az.search import SearchConfig
            from lignum.bots.plan_search import PlanConfig, PlanSearchBot

            cfg = SearchConfig(sims=64, prior_mix=0.5, leaf_steps=150, skip_conf=0.97)
            self._bot = PlanSearchBot(AZBot(self.model, cfg), PlanConfig(playouts=8))
        return int(self._bot.choose(state, rng))


PPO_MODEL = Path(os.environ.get("LIGNUM_AZPP_POLICY", "data/bots/ppo/current.npz"))


class AZPPSeat(AZSeat):
    """``az`` with the learned policy (docs/PPO.md: the AZ net's logits plus a bonus on the
    strategist's move, trained by paired-rollout advantage regression) in place of the strategist
    as the default player: plan-search playouts, AZ leaf playouts, the prior's extra-weighted move
    and the unsearched decisions. The AZ net (priors, values) is the same as ``az``'s. Falls back
    to the strategist like ``az`` (also when the policy file is missing)."""

    def __init__(self, model: str | Path = DEFAULT_MODEL, policy: str | Path = PPO_MODEL) -> None:
        super().__init__(model)
        self.policy = Path(policy)

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        assert isinstance(state, LignumState)
        if state.n != 2 or not state.joinery or not self.model.exists() or not self.policy.exists():
            return self._fallback.choose(state, rng)
        if self._bot is None:
            from lignum.bots.az.bot import AZBot
            from lignum.bots.az.search import SearchConfig
            from lignum.bots.plan_search import PlanConfig, PlanSearchBot
            from lignum.bots.ppo import PPOBot

            cfg = SearchConfig(sims=64, prior_mix=0.5, leaf_steps=150, skip_conf=0.97)
            play = PPOBot(self.policy, greedy=True)
            sim = PPOBot(self.policy, greedy=True)
            self._bot = PlanSearchBot(
                AZBot(self.model, cfg, default_bot=play), PlanConfig(playouts=8), sim=sim
            )
        return int(self._bot.choose(state, rng))
