"""Review must-fix findings: seed not an oracle, Back never crosses a reveal, public winter."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from server.adapters import default_adapters
from server.app import create_app
from server.sessions import SessionStore
from tests import harness as H
from tests.server.test_lignum_labels import _act, _at_hidden_pick, _view

Json = dict[str, Any]


def _create(c: TestClient, seats: list[str], seed: int | None = None) -> Json:
    body: Json = {"game": "lignum", "params": {"num_players": len(seats)}, "seats": seats}
    if seed is not None:
        body["seed"] = seed
    r = c.post("/api/games", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _keys(x: Any) -> set[str]:
    if isinstance(x, dict):
        return set(x) | {k for v in x.values() for k in _keys(v)}
    if isinstance(x, list):
        return {k for v in x for k in _keys(v)}
    return set()


# ------------------------------------------------------------------ A: seed is not an oracle


def test_seed_and_salt_never_in_client_responses() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _create(c, ["human", "random"], seed=424242)
    gid = g["id"]
    bodies = [json.dumps(g)]
    for seat in (0, 1):
        bodies.append(json.dumps(_view(c, gid, seat)))
    g = _at_hidden_pick(c, g)
    g = _act(c, gid, g["legal_actions"][0]["id"])  # reveal (bot picks right after)
    for _ in range(3):
        ids = [a["id"] for a in g["legal_actions"]]
        if g["is_terminal"]:
            break
        g = _act(c, gid, H.DONE if H.DONE in ids else ids[0])
    exp = c.get(f"/api/games/{gid}/export")
    assert exp.status_code == 200, exp.text
    bodies.append(exp.text)
    for seat in (0, 1):
        bodies.append(json.dumps(_view(c, gid, seat)))
    for b in bodies:
        assert "seed" not in _keys(json.loads(b)) and "salt" not in _keys(json.loads(b))
        assert "424242" not in b


def test_export_import_replays_without_seed_and_old_exports_import() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _create(c, ["human", "random"])
    gid = g["id"]
    exp = c.get(f"/api/games/{gid}/export").json()
    assert "seed" not in exp
    r = c.post("/api/games/import", json=exp)
    assert r.status_code == 200, r.text
    assert r.json()["history"] == _view(c, gid, 0)["history"]
    r = c.post("/api/games/import", json={**exp, "seed": 7})  # old export format
    assert r.status_code == 200, r.text


def test_salt_changes_bot_and_chance_streams() -> None:
    store = SessionStore(default_adapters())
    a = store.create("lignum", {"num_players": 2}, ["random", "random"], 5, salt="aaa")
    b = store.create("lignum", {"num_players": 2}, ["random", "random"], 5, salt="bbb")
    d = store.create("lignum", {"num_players": 2}, ["random", "random"], 5, salt="aaa")
    assert a.history != b.history  # same seed, other salt: not reproducible from the seed
    assert a.history == d.history


def test_default_games_are_not_seed_reproducible() -> None:
    c = TestClient(create_app(inline_bots=True))
    a = _create(c, ["random", "random"])
    b = _create(c, ["random", "random"])
    assert [e["label"] for e in a["history"]] != [e["label"] for e in b["history"]]


# ------------------------------------------------------------------ B: Back is stopped by a reveal


def test_back_refused_after_reveal() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _at_hidden_pick(c, _create(c, ["human", "random"], seed=4))
    gid = g["id"]
    g = _act(c, gid, g["legal_actions"][0]["id"])
    before = _view(c, gid, 0)["history_length"]
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 409 and r.json()["detail"]
    assert _view(c, gid, 0)["history_length"] == before


def test_back_before_reveal_still_works() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _at_hidden_pick(c, _create(c, ["human", "human", "random"], seed=4))
    gid = g["id"]
    n = g["history_length"]
    g = _act(c, gid, g["legal_actions"][0]["id"])
    assert g["current_player"] == 1
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 200, r.text
    assert r.json()["history_length"] == n


def test_rewind_in_dev_mode_unrestricted_across_reveal() -> None:
    c = TestClient(create_app(dev_mode=True, inline_bots=True))
    g = _at_hidden_pick(c, _create(c, ["human", "random"], seed=4))
    gid = g["id"]
    g = _act(c, gid, g["legal_actions"][0]["id"])
    r = c.post(f"/api/games/{gid}/rewind", json={"player_actions": 0})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ D: public winter cards


def test_view_winter_requirements_match_observer() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _create(c, ["human", "random"], seed=2)
    from server.adapters.lignum import LignumAdapter
    from server.sessions import Session

    s: Session = SessionStore(default_adapters()).create(
        "lignum", {"num_players": 2}, ["human", "random"], 2
    )
    st: Any = s.state
    t = st._tables()
    expect = []
    for y, rnd in enumerate(t.winter_rounds):
        probe = st.clone()
        probe.round = rnd  # the engine's own lookup of the visible half for that winter
        food, heating = probe._winter_requirement()
        expect.append({"year": y + 1, "food": food, "heating": heating})
    assert len(expect) == 2
    assert LignumAdapter().view(st, 1)["winter"]["cards"] == expect
    assert g["view"]["winter"]["cards"] == expect
    assert _view(c, g["id"], 1)["view"]["winter"]["cards"] == expect


# ------------------------------------------------------------------ C: mutations honour ?seat=


def test_mutation_responses_render_the_requested_seat() -> None:
    c = TestClient(create_app(dev_mode=True, inline_bots=True))
    g = _create(c, ["human", "human"], seed=3)
    gid = g["id"]
    a = g["legal_actions"][0]["id"]
    r = c.post(f"/api/games/{gid}/actions?seat=0", json={"action": a})
    assert r.status_code == 200 and r.json()["seat"] == 0
    r = c.post(f"/api/games/{gid}/back?seat=1")
    assert r.status_code == 200 and r.json()["seat"] == 1
    r = c.post(f"/api/games/{gid}/rewind?seat=1", json={"player_actions": 0})
    assert r.status_code == 200 and r.json()["seat"] == 1


# ------------------------------------------------------------- Back stops at round-start chance


def _run_to_round2(c: TestClient, seats: list[str]) -> Json:
    g = _create(c, seats, seed=4)
    for _ in range(3000):
        if g["current_player"] == 0 and _view(c, g["id"], 0)["history_length"] > 0:
            hist = _view(c, g["id"], 0)["history"]
            first_human = (
                next(e for e in hist if e["actor"] == 0)
                if any(e["actor"] == 0 for e in hist)
                else None
            )
            last_chance = max((e["index"] for e in hist if e["actor"] is None), default=-1)
            if first_human and last_chance > first_human["index"]:
                return g
        ids = [a["id"] for a in g["legal_actions"]]
        g = _act(c, g["id"], H.DONE if H.DONE in ids else ids[0])
    raise AssertionError("never reached round 2")


def test_back_refused_across_round_start_chance_human_random() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _run_to_round2(c, ["human", "random"])
    n = _view(c, g["id"], 0)["history_length"]
    r = c.post(f"/api/games/{g['id']}/back")
    assert r.status_code == 409 and r.json()["detail"]
    assert _view(c, g["id"], 0)["history_length"] == n


def test_back_refused_across_round_start_chance_human_human() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _run_to_round2(c, ["human", "human"])
    r = c.post(f"/api/games/{g['id']}/back")
    assert r.status_code == 409 and r.json()["detail"]


def test_back_within_round_still_works_after_round_start() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _run_to_round2(c, ["human", "human"])
    gid = g["id"]
    n = g["history_length"]
    g = _act(c, gid, g["legal_actions"][0]["id"])
    assert g["current_player"] == 1
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 200, r.text
    assert r.json()["history_length"] == n


def test_rewind_dev_mode_across_round_start_chance() -> None:
    c = TestClient(create_app(dev_mode=True, inline_bots=True))
    g = _run_to_round2(c, ["human", "random"])
    r = c.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 0})
    assert r.status_code == 200, r.text


def test_first_back_in_round_one_unaffected_by_setup_chance() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _create(c, ["human", "random"], seed=4)
    gid = g["id"]
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 409  # nothing to go back to
    g = _act(c, gid, g["legal_actions"][0]["id"])
    if g["current_player"] == 0:
        r = c.post(f"/api/games/{gid}/back")
        assert r.status_code == 200, r.text
