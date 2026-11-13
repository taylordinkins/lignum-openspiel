"""Phase 6 unit 6: IS-MCTS and determinized MCTS bots (R-029, R-038)."""

from __future__ import annotations

import random
import time

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots import Bot, RandomBot
from lignum.bots.mcts import DeterminizedMCTSBot, ISMCTSBot


def play(bots: list[Bot], seed: int, max_moves: int | None = None) -> pyspiel.State:
    """Play (at most max_moves decisions of) one game; every move must be legal."""
    game = pyspiel.load_game(f"python_lignum(players={len(bots)},returns=margin)")
    state = game.new_initial_state()
    chance = random.Random(seed)
    rngs = [random.Random(f"{seed}:{i}") for i in range(len(bots))]
    moves = 0
    while not state.is_terminal() and (max_moves is None or moves < max_moves):
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(acts, probs)[0])
            continue
        p = state.current_player()
        a = bots[p].choose(state, rngs[p])
        assert a in state.legal_actions(), (p, a)
        state.apply_action(a)
        moves += 1
    return state


def small(kind: str) -> Bot:
    if kind == "is":
        return ISMCTSBot(simulations=6, rollout_depth=4)
    return DeterminizedMCTSBot(determinizations=2, simulations=6, rollout_depth=4)


@pytest.mark.parametrize("kind", ["is", "det"])
@pytest.mark.parametrize("players", [2, 3, 4])
def test_moves_are_legal(kind: str, players: int) -> None:
    play([small(kind) for _ in range(players)], seed=players, max_moves=60)


@pytest.mark.parametrize("kind", ["is", "det"])
def test_deterministic_with_seed(kind: str) -> None:
    def trace(seed: int) -> list[int]:
        game = pyspiel.load_game("python_lignum(players=3)")
        state = game.new_initial_state()
        chance = random.Random(seed)
        rng = random.Random(seed)
        bot = small(kind)
        out: list[int] = []
        while len(out) < 25 and not state.is_terminal():
            if state.is_chance_node():
                acts, probs = zip(*state.chance_outcomes(), strict=True)
                state.apply_action(chance.choices(acts, probs)[0])
                continue
            a = bot.choose(state, rng)
            out.append(a)
            state.apply_action(a)
        return out

    assert trace(5) == trace(5)


@pytest.mark.parametrize("kind", ["is", "det"])
def test_time_cap_is_honoured(kind: str) -> None:
    bot: Bot
    if kind == "is":
        bot = ISMCTSBot(simulations=10**6, time_budget=0.05, rollout_depth=4)
    else:
        bot = DeterminizedMCTSBot(
            determinizations=4, simulations=10**6, time_budget=0.05, rollout_depth=4
        )
    game = pyspiel.load_game("python_lignum(players=2)")
    state = game.new_initial_state()
    chance = random.Random(0)
    rng = random.Random(0)
    worst = 0.0
    decisions = 0
    while decisions < 30 and not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance.choices(acts, probs)[0])
            continue
        t = time.perf_counter()
        a = bot.choose(state, rng)
        worst = max(worst, time.perf_counter() - t)
        assert a in state.legal_actions()
        state.apply_action(a)
        decisions += 1
    assert worst < 0.5


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["is", "det"])
def test_search_bot_beats_random(kind: str) -> None:
    """Seats rotated; a win counts 1, a tie 0.5 (random play often ends level)."""
    games, score = 24, 0.0
    for i in range(games):
        seat = i % 2
        bots: list[Bot] = [RandomBot(), RandomBot()]
        bots[seat] = (
            ISMCTSBot(simulations=30, time_budget=0.2, rollout_depth=10)
            if kind == "is"
            else DeterminizedMCTSBot(
                determinizations=3, simulations=30, time_budget=0.2, rollout_depth=10
            )
        )
        ret = play(bots, seed=i).returns()[seat]
        score += 1.0 if ret > 0 else 0.5 if ret == 0 else 0.0
    assert score / games > 0.7
