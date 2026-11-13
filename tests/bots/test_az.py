"""AZ bot (lignum.bots.az): encoder perspective, search legality, full games with a random net."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pyspiel
import pytest

import lignum.game  # noqa: F401
from lignum.bots.az.bot import AZBot
from lignum.bots.az.features import Encoder
from lignum.bots.az.net import NumpyNet, random_params
from lignum.bots.az.search import SearchConfig, Searcher, is_strategic
from lignum.bots.strategist import StrategistBot
from lignum.game import LignumState


def _advance(st: pyspiel.State, rng: random.Random, steps: int) -> pyspiel.State:
    bot = StrategistBot()
    for _ in range(steps):
        if st.is_terminal():
            break
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
        else:
            st.apply_action(bot.choose(st, rng))
    return st


@pytest.fixture
def model(tmp_path: Path) -> Path:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    d = Encoder(game).size
    path = tmp_path / "net.npz"
    np.savez(path, **random_params(d))
    return path


def test_encoder_rotates_seats() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    enc = Encoder(game)
    st = _advance(game.new_initial_state(), random.Random(3), 200)
    assert isinstance(st, LignumState)
    x0, x1 = enc.encode(st, 0), enc.encode(st, 1)
    assert x0.shape == (enc.size,)
    money = enc.obs.dict["money"]  # last encoded seat (1) first
    assert list(money) == [st.money[1], st.money[0]]
    assert not np.array_equal(x0, x1) or st.money[0] == st.money[1]


def test_encoder_hides_other_seat_pick() -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    enc = Encoder(game)
    rng = random.Random(5)
    st = game.new_initial_state()
    bot = StrategistBot()
    while not (isinstance(st, LignumState) and st.pk and len(st.pk) == 1):
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
        else:
            st.apply_action(bot.choose(st, rng))
    seen = enc.encode(st, st.current_player())
    alt = st.search_clone()
    alt.pk = ((alt.pk[0] + 1) % 6,)
    assert np.array_equal(seen, enc.encode(alt, st.current_player()))


def test_search_returns_candidates(model: Path) -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    enc = Encoder(game)
    rng = random.Random(1)
    st = game.new_initial_state()
    while not (isinstance(st, LignumState) and is_strategic(st) and len(st.legal_actions()) > 2):
        st = _advance(st, rng, 1)
    assert isinstance(st, LignumState)
    s = Searcher(NumpyNet(model), enc, SearchConfig(sims=16), default=StrategistBot().choose)
    cands, visits, _q, root = s.run(st, rng)
    assert visits.sum() == 16 and root.total == 16
    assert set(cands) <= set(st.legal_actions())


@pytest.mark.parametrize("leaf", [0, 20])
def test_full_game_legal(model: Path, leaf: int) -> None:
    game = pyspiel.load_game("python_lignum", {"players": 2})
    bots = [AZBot(model, SearchConfig(sims=4, leaf_steps=leaf, skip_conf=0.9)), StrategistBot()]
    rng = random.Random(2)
    st = game.new_initial_state()
    while not st.is_terminal():
        if st.is_chance_node():
            outs = st.chance_outcomes()
            st.apply_action(rng.choices([x for x, _ in outs], [p for _, p in outs])[0])
            continue
        a = bots[st.current_player()].choose(st, rng)
        assert a in st.legal_actions()
        st.apply_action(a)
    assert isinstance(st, LignumState) and len(st.final) == 2


def test_numpy_matches_torch(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from tools.az_train import build_model

    d = 50
    m = build_model(d, 32, 2, 2)
    state = {k: v.detach() for k, v in m.state_dict().items()}
    arrays = {k: v.numpy() for k, v in state.items()}
    arrays["norm_mean"] = np.zeros(d, np.float32)
    arrays["norm_inv"] = np.ones(d, np.float32)
    arrays["meta_blocks"] = np.array([2])
    np.savez(tmp_path / "m.npz", **arrays)
    x = np.random.default_rng(0).standard_normal((3, d)).astype(np.float32)
    lg, v = NumpyNet(tmp_path / "m.npz").forward(x)
    with torch.no_grad():
        tl, tv = m(torch.tensor(np.clip(x, -5, 5)))
    assert np.allclose(lg, tl.numpy(), atol=1e-4)
    assert np.allclose(v, tv.numpy() * 100.0, atol=1e-2)


def test_registered_seat_plays_and_falls_back() -> None:
    from server.bots import BOTS, is_valid_seat_type
    from server.schemas import GameParams  # noqa: F401  (pattern import stays valid)

    assert is_valid_seat_type("az")
    seat = BOTS["az"]
    for players in (2, 3):
        game = pyspiel.load_game("python_lignum", {"players": players})
        rng = random.Random(9)
        st = _advance(game.new_initial_state(), rng, 60)
        while st.is_chance_node():
            st = _advance(st, rng, 1)
        assert seat.choose(st.clone(), rng) in st.legal_actions()
