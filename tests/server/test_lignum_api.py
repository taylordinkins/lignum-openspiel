"""Phase 3 unit 2: a real Lignum game created and played through the HTTP API."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

Json = dict[str, Any]


@pytest.mark.parametrize("n", [2, 3])
def test_lignum_game_through_api(n: int) -> None:
    c = TestClient(create_app(inline_bots=True))
    r = c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": n},
            "seats": ["human"] + ["random"] * (n - 1),
            "seed": 5,
        },
    )
    assert r.status_code == 200, r.text
    g: Json = r.json()
    for _ in range(8):
        for seat in range(n):
            v = c.get(f"/api/games/{g['id']}?seat={seat}").json()
            assert v["seat"] == seat
            assert v["view"]["seat"] == seat
            assert v["view"]["game"]["players"] == n
        view = g["view"]
        assert view["is_terminal"] is False
        assert view["current_player"] == 0  # bots are played inline; the human is to move
        legal = view["legal_actions"]
        assert legal and all(isinstance(a["label"], str) and a["label"] for a in legal)
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": legal[0]["id"]})
        assert r.status_code == 200, r.text
        g = r.json()
    assert g["history_length"] >= 8


def test_legal_actions_expose_kind_and_params() -> None:
    from lignum import actions as A

    c = TestClient(create_app(inline_bots=True))
    r = c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": 2},
            "seats": ["human", "random"],
            "seed": 5,
        },
    )
    assert r.status_code == 200, r.text
    for a in r.json()["view"]["legal_actions"]:
        d = A.decode(a["id"])
        assert a["kind"] == d.name
        assert a["params"] == list(d.params)
