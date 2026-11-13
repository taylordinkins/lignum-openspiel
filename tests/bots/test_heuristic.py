"""Phase 6 unit 4: the heuristic bot (D32): legality, determinism, YAML ranking, strength."""

from __future__ import annotations

import random
from typing import Any

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots import Bot, HeuristicBot, RandomBot
from lignum.bots.heuristic import HEURISTIC_YAML, load_weights


def play(bots: list[Bot], seed: int, margin: bool = True) -> list[float]:
    """Play one game; every bot move must be legal (apply_action re-checks legality)."""
    mode = "margin" if margin else "win_loss"
    game = pyspiel.load_game(f"python_lignum(players={len(bots)},returns={mode})")
    state = game.new_initial_state()
    chance = random.Random(seed)
    rngs = [random.Random(f"{seed}:{i}") for i in range(len(bots))]
    while not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(acts, probs)[0])
            continue
        p = state.current_player()
        a = bots[p].choose(state, rngs[p])
        assert a in state.legal_actions(), (p, a)
        state.apply_action(a)
    return list(state.returns())


def test_weights_load_from_yaml() -> None:
    assert HEURISTIC_YAML.exists()
    w = load_weights()
    ranking = w["location_weights"]
    assert ranking["joker"] > ranking["planned_work"] > ranking["tasks"] > ranking["sawyers"]
    assert ranking["sawyers"] > ranking["dollar"] > ranking["market"] > ranking["sledge"]
    assert ranking["clearing"] == min(ranking.values())
    assert HeuristicBot().w is w


def test_weights_can_be_overridden() -> None:
    w: dict[str, Any] = dict(load_weights())
    assert HeuristicBot(w).w is w


@pytest.mark.parametrize("players", [2, 3, 4])
def test_heuristic_games_are_legal_and_finish(players: int) -> None:
    for seed in range(2):
        returns = play([HeuristicBot() for _ in range(players)], seed)
        assert len(returns) == players


def test_mixed_table_is_legal() -> None:
    play([HeuristicBot(), RandomBot(), HeuristicBot()], 5)


def test_deterministic_with_seed() -> None:
    a = play([HeuristicBot(), RandomBot()], 11)
    b = play([HeuristicBot(), RandomBot()], 11)
    assert a == b


@pytest.mark.slow
def test_heuristic_beats_random_over_100_games() -> None:
    wins = games = 0
    for g in range(100):
        seat = g % 2  # rotate the heuristic's seat
        bots: list[Bot] = [RandomBot(), RandomBot()]
        bots[seat] = HeuristicBot()
        returns = play(bots, 1000 + g, margin=False)
        wins += returns[seat] > 0
        games += 1
    print(f"heuristic win rate vs random: {wins}/{games}")
    assert wins / games >= 0.8
