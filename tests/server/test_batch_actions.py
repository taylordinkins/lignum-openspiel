"""Batch action endpoint: all-or-nothing, history gets the plain frozen ids."""

from __future__ import annotations

import random
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

Json = dict[str, Any]
ASSIGN_HIRED = 174


def take(area: int, kind: int) -> int:
    return 177 + 3 * area + kind


def _w1_game(c: TestClient, seed: int) -> Json | None:
    """Play seat 0 (random, preferring hires) until it can cut in W1 with >= 2 woodcutters."""
    g: Json = c.post(
        "/api/games",
        json={"params": {"num_players": 2}, "seats": ["human", "random"], "seed": seed},
    ).json()
    rng = random.Random(seed)
    for _ in range(400):
        v = g["view"]
        if v["is_terminal"]:
            return None
        ids = [a["id"] for a in g["legal_actions"]]
        me = v["seats"][0]
        if (
            v["phase"] == "W1"
            and ASSIGN_HIRED in ids
            and me["hired"]["w"] - me["cut_used"] >= 2
            and sum(v["area_wood"][v["picks"][0]]) >= 2
        ):
            return g
        a = 32 if (32 in ids and v["phase"] == "TR") else rng.choice(ids)
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": a})
        assert r.status_code == 200, r.text
        g = r.json()
    return None


@pytest.fixture
def w1() -> tuple[TestClient, Json, list[int]]:
    for seed in range(60):
        c = TestClient(create_app(inline_bots=True))
        g = _w1_game(c, seed)
        if g is not None:
            area = g["view"]["picks"][0]
            wood = g["view"]["area_wood"][area]
            kinds = [k for k in range(3) for _ in range(wood[k])][:2]
            ids = [x for k in kinds for x in (ASSIGN_HIRED, take(area, k))]
            return c, g, ids
    pytest.skip("no seed reached a W1 cutting turn with two woodcutters")


def test_batch_equals_single_actions(w1: tuple[TestClient, Json, list[int]]) -> None:
    c, g, ids = w1
    n0 = g["history_length"]
    r = c.post(f"/api/games/{g['id']}/actions/batch?seat=0", json={"action_ids": ids})
    assert r.status_code == 200, r.text
    batched = r.json()
    assert [h["id"] for h in batched["history"][n0 : n0 + len(ids)]] == ids

    exp = c.get(f"/api/games/{g['id']}/export").json()
    assert exp["history"][n0 : n0 + len(ids)] == ids


def test_single_back_undoes_batch(w1: tuple[TestClient, Json, list[int]]) -> None:
    c, g, ids = w1
    c.post(f"/api/games/{g['id']}/actions/batch?seat=0", json={"action_ids": ids})
    r = c.post(f"/api/games/{g['id']}/back?seat=0")
    assert r.status_code == 200, r.text
    assert r.json()["history_length"] == g["history_length"]
    assert r.json()["view"]["area_wood"] == g["view"]["area_wood"]


def test_illegal_middle_step_is_atomic(w1: tuple[TestClient, Json, list[int]]) -> None:
    c, g, ids = w1
    bad = [ids[0], ids[1], 999, ids[2]]
    r = c.post(f"/api/games/{g['id']}/actions/batch", json={"action_ids": bad})
    assert r.status_code == 409
    after = c.get(f"/api/games/{g['id']}?seat=0").json()
    assert after["history_length"] == g["history_length"]
    assert after["view"]["area_wood"] == g["view"]["area_wood"]


def test_wrong_seat_is_409(w1: tuple[TestClient, Json, list[int]]) -> None:
    c, g, ids = w1
    r = c.post(f"/api/games/{g['id']}/actions/batch?seat=1", json={"action_ids": ids})
    assert r.status_code == 409
    assert c.get(f"/api/games/{g['id']}").json()["history_length"] == g["history_length"]


def test_batch_after_back_works(w1: tuple[TestClient, Json, list[int]]) -> None:
    c, g, ids = w1
    c.post(f"/api/games/{g['id']}/actions/batch?seat=0", json={"action_ids": ids})
    c.post(f"/api/games/{g['id']}/back?seat=0")
    r = c.post(f"/api/games/{g['id']}/actions/batch?seat=0", json={"action_ids": ids})
    assert r.status_code == 200, r.text


def test_batch_limits() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = c.post("/api/games", json={"seats": ["human", "random"], "seed": 1}).json()
    assert c.post(f"/api/games/{g['id']}/actions/batch", json={"action_ids": []}).status_code == 422
    r = c.post(f"/api/games/{g['id']}/actions/batch", json={"action_ids": [0] * 33})
    assert r.status_code == 422
