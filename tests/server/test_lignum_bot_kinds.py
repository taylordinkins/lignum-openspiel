"""Phase 6 unit 7: heuristic/mcts bot kinds, time cap, inline IllegalAction handling."""

from __future__ import annotations

import random
import time
from typing import Any

import pyspiel
import pytest
from fastapi.testclient import TestClient

import lignum.game  # noqa: F401
import server.bots as bots_mod
from lignum.bots.mcts import ISMCTSBot
from server.app import create_app
from server.bots import BOTS

Json = dict[str, Any]


def _create(c: TestClient, seats: list[str], seed: int = 3) -> Any:
    return c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": len(seats)},
            "seats": seats,
            "seed": seed,
        },
    )


def test_registered_kinds() -> None:
    assert {"random", "heuristic", "mcts", "mcts-fast"} <= set(BOTS)
    for k in ("heuristic", "mcts", "mcts-fast"):
        assert bots_mod.is_valid_seat_type(k)


def test_unknown_kind_rejected() -> None:
    c = TestClient(create_app(inline_bots=True))
    assert _create(c, ["human", "nope"]).status_code == 422


def test_mcts_time_cap_falls_back() -> None:
    bot = ISMCTSBot(simulations=10**6, time_budget=0.0)
    state = pyspiel.load_game("python_lignum(players=2)").new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    t = time.perf_counter()
    assert bot.choose(state, random.Random(0)) in state.legal_actions()
    assert time.perf_counter() - t < 5


def test_inline_bot_illegal_action_goes_to_bot_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Bad:
        def choose(self, state: Any, rng: Any) -> int:
            return 10**6

    monkeypatch.setitem(BOTS, "random", Bad())
    c = TestClient(create_app(inline_bots=True))
    r = _create(c, ["human", "random"])
    assert r.status_code == 200, r.text
    g = r.json()
    if g["seat_types"][g["seat"]] == "human":
        a = g["view"]["legal_actions"][0]["id"]
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": a})
        assert r.status_code == 200, r.text
        g = r.json()
    assert g["bot_error"] and "IllegalAction" in g["bot_error"]


@pytest.mark.slow
def test_bot_vs_bot_finishes() -> None:
    c = TestClient(create_app(inline_bots=False))
    g = _create(c, ["heuristic", "mcts-fast"], seed=5).json()
    deadline = time.monotonic() + 540
    while not g["view"]["is_terminal"]:
        assert time.monotonic() < deadline, "bot game did not finish"
        assert g["bot_error"] is None
        time.sleep(0.2)
        g = c.get(f"/api/games/{g['id']}").json()
