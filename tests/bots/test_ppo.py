"""PPO policy on top of the strategist (lignum/bots/ppo.py, tools/ppo_train.py)."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import numpy as np
import pyspiel
import pytest

import lignum.game  # noqa: F401  # pyright: ignore[reportUnusedImport]
from lignum.bots.az.features import Encoder
from lignum.bots.az.net import random_params
from lignum.bots.ppo import PPOBot
from lignum.bots.strategist import StrategistBot
from lignum.game import LignumState
from tools.ppo_train import batch_arrays


@pytest.fixture
def model(tmp_path: Path) -> Path:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    p: dict[str, Any] = random_params(Encoder(game).size)
    p["pi.weight"] *= 0.0  # flat logits: the bonus alone decides
    path = tmp_path / "net.npz"
    np.savez(path, **p)
    return path


def _play(bots: list[object], seed: int) -> LignumState:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    st = game.new_initial_state()
    assert isinstance(st, LignumState)
    rng = random.Random(seed)
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
        else:
            st.apply_action(bots[st.current_player()].choose(st, rng))  # type: ignore[attr-defined]
    return st


def test_greedy_with_flat_logits_plays_like_the_strategist(model: Path) -> None:
    a = _play([PPOBot(model, greedy=True), StrategistBot()], 5)
    b = _play([StrategistBot(), StrategistBot()], 5)
    assert a.final == b.final


def test_sampling_records_steps_and_gae_targets(model: Path) -> None:
    bot = PPOBot(model, bonus=0.5, greedy=False)
    bot.record = []
    st = _play([bot, StrategistBot()], 7)
    steps = bot.record
    assert steps and all(s.seat == 0 for s in steps)
    assert any(s.aidx != s.sidx for s in steps)  # low bonus: some deviations
    assert all(s.logp <= 0 for s in steps)
    data = batch_arrays([{"final": list(st.final), "steps": steps}], lam=1.0)
    # lambda = 1: the return target is the final dollars (scaled) at every step
    assert np.allclose(data["ret"], st.final[0] / 100.0, atol=1e-5)
    assert data["cands"].shape[0] == len(steps)


def test_azpp_seat_plays_and_falls_back() -> None:
    from server.bots import BOTS, is_valid_seat_type

    assert is_valid_seat_type("azpp")
    seat = BOTS["azpp"]
    bot = StrategistBot()
    for players in (2, 3):
        game = pyspiel.load_game("python_lignum", {"players": players})
        st = game.new_initial_state()
        rng = random.Random(9)
        steps = 0
        while steps < 60 or st.is_chance_node():
            if st.is_chance_node():
                outs = st.chance_outcomes()
                st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            else:
                st.apply_action(bot.choose(st, rng))
                steps += 1
        assert seat.choose(st.clone(), rng) in st.legal_actions()
