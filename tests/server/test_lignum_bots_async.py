"""Phase 3 unit 5: the background-thread bot loop (inline bots OFF) against the real Lignum."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

import server.bots as bots_mod
from server.app import create_app
from tests import harness as H
from tests.server.test_lignum_labels import PICK_IDS, _act, _view

Json = dict[str, Any]
TIMEOUT = 20.0


def _client(inline: bool = False) -> TestClient:
    return TestClient(create_app(inline_bots=inline))


def _create(c: TestClient, seats: list[str], seed: int = 4) -> Json:
    r = c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": len(seats)},
            "seats": seats,
            "seed": seed,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _get(c: TestClient, gid: str, seat: int | None = None) -> Json:
    url = f"/api/games/{gid}" + (f"?seat={seat}" if seat is not None else "")
    return c.get(url).json()


def _wait(c: TestClient, gid: str, pred: Callable[[Json], bool]) -> Json:
    deadline = time.monotonic() + TIMEOUT
    while True:
        g = _get(c, gid)
        if pred(g):
            return g
        assert time.monotonic() < deadline, "timed out waiting for the bot loop"
        time.sleep(0.005)


def _settled(g: Json) -> bool:
    return g["is_terminal"] or not g["bot_thinking"]


@pytest.mark.parametrize(
    "seats",
    [
        ["human", "random"],
        ["random", "human"],
        ["random", "human", "random"],
        ["human", "random", "random"],
        ["random", "random", "human", "random"],
        ["human", "random", "random", "random"],
    ],
)
def test_mixed_seats_reach_human_turn(seats: list[str]) -> None:
    c = _client()
    g = _wait(c, _create(c, seats)["id"], _settled)
    assert not g["is_terminal"]
    assert seats[g["current_player"]] == "human"
    assert not g["bot_thinking"] and g["bot_error"] is None
    # play a few human moves; the loop always settles on a human turn again
    for _ in range(6):
        ids = [a["id"] for a in g["legal_actions"]]
        r = c.post(
            f"/api/games/{g['id']}/actions", json={"action": H.DONE if H.DONE in ids else ids[0]}
        )
        assert r.status_code == 200, r.text
        g = _wait(c, g["id"], _settled)
        assert g["is_terminal"] or seats[g["current_player"]] == "human"
        assert g["bot_error"] is None


@pytest.mark.parametrize("n", [2, 3, 4])
def test_all_random_terminal_and_matches_inline(n: int) -> None:
    seats = ["random"] * n
    c = _client()
    g = _wait(c, _create(c, seats, 7)["id"], lambda x: x["is_terminal"])
    assert not g["bot_thinking"] and g["bot_error"] is None
    h = _create(_client(True), seats, 7)
    assert h["is_terminal"]
    assert [e["id"] for e in g["history"]] == [e["id"] for e in h["history"]]
    assert g["returns"] == h["returns"]


def test_async_bot_pick_masked_for_other_seats() -> None:
    c = _client()
    seats = ["random", "human", "human"]
    gid = _create(c, seats)["id"]
    g = _wait(c, gid, _settled)
    for _ in range(3000):
        ids = [a["id"] for a in g["legal_actions"]]
        if set(ids) == PICK_IDS and g["current_player"] == 1:
            break
        g = _act(c, gid, H.DONE if H.DONE in ids else ids[0])
        g = _wait(c, gid, _settled)
    else:
        raise AssertionError("never reached the hidden pick phase")
    v1 = _view(c, gid, 1)
    picks = [e for e in v1["history"] if e["id"] is None]
    assert len(picks) == 1 and picks[0]["actor"] == 0 and "P0" in picks[0]["label"]
    assert v1["history"][-1]["index"] == picks[0]["index"]
    # the bot's real pick id is not exposed anywhere in the other seats' history
    real = _view(c, gid, 0)["history"][picks[0]["index"]]
    assert real["id"] in PICK_IDS and real["label"] != picks[0]["label"]
    for seat in (1, 2):
        tail = json.dumps(_view(c, gid, seat)["history"][picks[0]["index"] :])
        assert real["label"] not in tail
        assert f'"id": {real["id"]}' not in tail


class SlowFirst:
    """Random bot whose first call is slow, so a test can act while the worker thinks."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.calls = 0

    def choose(self, state: Any, rng: Any) -> int:
        self.calls += 1
        if self.calls == 1:
            time.sleep(self.delay)
        return rng.choice(state.legal_actions())


def test_back_while_bot_thinking_discards_stale_move(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bots_mod.BOTS, "random", SlowFirst(0.8))
    c = _client()
    g = _create(c, ["human", "random"])
    gid = g["id"]
    # the bot's first call is the slow one; get a human action in before it moves
    g = _wait(c, gid, lambda x: x["is_terminal"] or x["current_player"] == 0 or x["bot_thinking"])
    if g["current_player"] == 0 and not g["bot_thinking"]:
        for _ in range(500):
            ids = [a["id"] for a in g["legal_actions"]]
            r = c.post(
                f"/api/games/{gid}/actions",
                json={"action": H.DONE if H.DONE in ids else ids[0]},
            )
            assert r.status_code == 200, r.text
            g = r.json()
            if g["bot_thinking"]:
                break
    assert g["bot_thinking"]
    time.sleep(0.1)  # worker is inside choose()
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 200, r.text
    back = r.json()
    assert back["history_length"] < g["history_length"]
    assert not back["bot_thinking"] and back["current_player"] == 0
    time.sleep(1.0)  # the stale computation finishes and must be discarded
    now = _get(c, gid)
    assert now["history"] == back["history"]
    assert now["current_player"] == 0 and not now["bot_thinking"] and now["bot_error"] is None
    for seat in range(2):
        v = _view(c, gid, seat)
        assert v["history_length"] == len(v["history"])
        assert [e["index"] for e in v["history"]] == list(range(len(v["history"])))


def test_flags_clear_at_end() -> None:
    c = _client()
    gid = _create(c, ["random", "random", "random"], 2)["id"]
    g = _wait(c, gid, lambda x: x["is_terminal"])
    assert g["bot_thinking"] is False and g["bot_error"] is None
