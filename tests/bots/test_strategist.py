"""Strategist bot (lignum.bots.strategist): legal, crash-free, fast play and the server seat."""

from __future__ import annotations

import random
import statistics
import time

import pyspiel
import pytest

import lignum.game  # noqa: F401
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.strategist import DEFAULT_WEIGHTS, StrategistBot
from server.bots import BOTS, is_valid_seat_type


def _play(players: int, seed: int, bots: list, joinery: bool = True) -> pyspiel.State:
    game = pyspiel.load_game("python_lignum", {"players": players, "joinery": joinery})
    rng = random.Random(seed)
    st = game.new_initial_state()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            a = rng.choices([x for x, _ in outs], [p for _, p in outs])[0]
        else:
            a = bots[st.current_player()].choose(st, rng)
            assert a in st.legal_actions()
        st.apply_action(a)
    return st


@pytest.mark.parametrize(("players", "joinery"), [(2, True), (3, True), (4, True), (2, False)])
def test_plays_legal_games_without_errors(players: int, joinery: bool) -> None:
    # trace=True re-raises internal errors instead of falling back to a safe action.
    bots = [StrategistBot(trace=True) for _ in range(players)]
    for seed in range(3):
        st = _play(players, 100 + seed, bots, joinery)
        assert len(st.final) == players


def test_deterministic_given_seed() -> None:
    a = _play(2, 7, [StrategistBot(), StrategistBot()]).final
    b = _play(2, 7, [StrategistBot(), StrategistBot()]).final
    assert a == b


def test_fast_inference() -> None:
    t = time.perf_counter()
    _play(2, 11, [StrategistBot(), StrategistBot()])
    assert time.perf_counter() - t < 5.0  # ~0.05 s on a desktop


def test_weight_overrides() -> None:
    bot = StrategistBot(weights={"hw_value": 1.0})
    assert bot.w["hw_value"] == 1.0
    assert set(bot.w) == set(DEFAULT_WEIGHTS)


def test_registered_seat() -> None:
    assert is_valid_seat_type("strategist")
    assert isinstance(BOTS["strategist"], StrategistBot)


@pytest.mark.slow
def test_beats_heuristic_v6() -> None:
    mine, theirs = [], []
    for g in range(20):
        s, v6 = StrategistBot(), HeuristicBot(profile="heuristic-v6")
        seat = g % 2
        bots = [s, v6] if seat == 0 else [v6, s]
        st = _play(2, 2000 + g, bots)
        mine.append(st.final[seat])
        theirs.append(st.final[1 - seat])
    assert statistics.mean(mine) > statistics.mean(theirs) + 15
