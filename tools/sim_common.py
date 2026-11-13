"""Shared simulation helpers: the 24-combination parameter grid and a seeded random playout."""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Callable
from typing import Any

import numpy as np
import pyspiel

import lignum.game as _game  # registers the game with pyspiel
from lignum.actions import decode

_REGISTERED = _game

Combo = tuple[int, bool, str, bool]  # players, joinery (path side), returns mode, easy winter

PLAYERS = (2, 3, 4)
JOINERY = (True, False)  # selects the path side (joinery side vs base side)
RETURNS = ("win_loss", "margin")
EASY = (False, True)
COMBOS: list[Combo] = list(itertools.product(PLAYERS, JOINERY, RETURNS, EASY))


def combo_id(c: Combo) -> str:
    return f"p{c[0]}-{'joinery' if c[1] else 'base'}-{c[2]}-{'easy' if c[3] else 'std'}"


def combo_params(c: Combo) -> dict[str, Any]:
    return {"players": c[0], "joinery": c[1], "returns": c[2], "easy_winter": c[3]}


def load(c: Combo) -> pyspiel.Game:
    return pyspiel.load_game("python_lignum", combo_params(c))


def random_playout(
    game: pyspiel.Game, seed: int, on_step: Callable[[pyspiel.State], None] | None = None
) -> pyspiel.State:
    """Play one uniformly random game; ``on_step`` is called after every applied action."""
    rng = np.random.RandomState(seed)
    state = game.new_initial_state()
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(int(rng.choice(actions, p=probs)))
        else:
            state.apply_action(int(rng.choice(state.legal_actions())))
        if on_step is not None:
            on_step(state)
    return state


# Phase 4 actions (planned work, huts, craftwork market, buildings) that random play should reach.
PHASE4_ACTIONS = (
    "BUY_SAW",
    "BUY_FOOD",
    "CHOOSE_BUILDING",
    "PLAN_WORK",
    "SELL_SET",
    "SELL_EQUIP",
    "BUILD_HUT",
    "HUT_TOKEN",
    "HUT_AREA",
    "HUT_FOOD",
    "HUT_DRY",
    "USE_PW_LOGDRIVING",
    "TAKE_OVERTIME",
)


def action_counts(state: pyspiel.State) -> Counter[str]:
    """Count decision actions by name over the state's history (chance outcomes excluded)."""
    return Counter(decode(pa.action).name for pa in state.full_history() if pa.player >= 0)
