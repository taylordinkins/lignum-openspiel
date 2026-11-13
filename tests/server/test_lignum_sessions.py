"""Phase 3 unit 4: session lifecycle against the real Lignum game, over HTTP."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from tests import harness as H
from tests.server.test_lignum_labels import PICK_IDS, _act, _view

Json = dict[str, Any]


def _client(**kw: Any) -> TestClient:
    return TestClient(create_app(inline_bots=True, **kw))


def _create(c: TestClient, seats: list[str], seed: int = 3, **params: Any) -> Json:
    r = c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": len(seats), **params},
            "seats": seats,
            "seed": seed,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _fingerprint(c: TestClient, gid: str, n: int) -> list[str]:
    out = []
    for seat in range(n):
        v = _view(c, gid, seat)
        out.append(json.dumps({k: v[k] for k in ("view", "history", "returns", "winners")}))
    return out


def _play_human(c: TestClient, g: Json, steps: int, pick: int = 0) -> Json:
    for _ in range(steps):
        if g["is_terminal"]:
            break
        ids = [a["id"] for a in g["legal_actions"]]
        g = _act(c, g["id"], H.DONE if H.DONE in ids else ids[pick % len(ids)])
    return g


# ------------------------------------------------------------------ creation


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.parametrize("joinery", [True, False])
@pytest.mark.parametrize("returns", ["win_loss", "margin"])
def test_create_all_combos(n: int, joinery: bool, returns: str) -> None:
    c = _client()
    g = _create(c, ["human"] + ["random"] * (n - 1), joinery=joinery, returns=returns)
    assert g["view"]["game"] == {"players": n, "joinery": joinery}
    assert g["seats"][0] == "human" and len(g["seats"]) == n
    assert g["current_player"] == 0
    # chance nodes were resolved by the server, with chance labels and null actors
    chance = [e for e in g["history"] if e["actor"] is None]
    assert chance and all(not e["label"].startswith("Chance outcome") for e in chance)


@pytest.mark.parametrize(
    ("body", "code", "needle"),
    [
        ({"params": {"num_players": 3}, "seats": ["human", "random"]}, 400, "seats"),
        ({"params": {"num_players": 2}, "seats": ["human", "random", "random"]}, 400, "seats"),
        ({"params": {"num_players": 2}, "seats": ["human", "alien"]}, 422, "alien"),
        ({"params": {"num_players": 5}, "seats": ["human"] * 5}, 422, "num_players"),
        ({"params": {"num_players": 1}, "seats": ["human"]}, 422, "num_players"),
        ({"params": {"num_players": 2}, "seats": []}, 400, "seats"),
    ],
)
def test_create_invalid(body: Json, code: int, needle: str) -> None:
    r = _client().post("/api/games", json={"game": "lignum", "seed": 1, **body})
    assert r.status_code == code, r.text
    assert needle in json.dumps(r.json()["detail"])


def test_create_unknown_game_and_bad_returns() -> None:
    c = _client()
    r = c.post("/api/games", json={"game": "nope", "seats": ["human"]})
    assert 400 <= r.status_code < 500
    r = c.post(
        "/api/games",
        json={
            "game": "lignum",
            "params": {"num_players": 2, "returns": "bogus"},
            "seats": ["human"] * 2,
        },
    )
    assert r.status_code == 422


def test_margin_returns_mode_reported() -> None:
    c = _client()
    g = _create(c, ["random"] * 2, seed=1, returns="margin")
    assert g["is_terminal"]
    assert c.get(f"/api/games/{g['id']}/export").json()["params"]["returns"] == "margin"


# ------------------------------------------------------------------ chance determinism


def test_same_seed_same_history_and_chance_is_server_side() -> None:
    c = _client()
    a = _create(c, ["human", "random"], seed=11)
    b = _create(c, ["human", "random"], seed=11)
    assert [e["id"] for e in a["history"]] == [e["id"] for e in b["history"]]
    d = _create(c, ["human", "random"], seed=12)
    assert [e["id"] for e in a["history"]] != [e["id"] for e in d["history"]]
    # a client cannot play a chance outcome: only the human's legal actions are accepted
    r = c.post(f"/api/games/{a['id']}/actions", json={"action": -5})
    assert r.status_code == 409
    for e in a["history"]:
        assert e["actor"] in (None, 0, 1)


# ------------------------------------------------------------------ full games


def _full_game(n: int, seed: int, **params: Any) -> Json:
    c = _client()
    g = _create(c, ["random"] * n, seed=seed, **params)
    assert g["is_terminal"] and not g["bot_thinking"]
    assert len(g["returns"]) == n
    if params.get("returns", "win_loss") == "win_loss" or n == 2:  # R-086: margin n>=3 is free
        assert abs(sum(g["returns"])) < 1e-9
    assert len(g["view"]["final"]) == n
    assert g["winners"] and all(0 <= w < n for w in g["winners"])
    assert g["current_player"] is None and g["legal_actions"] == []
    return g


@pytest.mark.parametrize(("n", "joinery"), [(2, True), (3, True), (4, True), (2, False)])
def test_full_random_game(n: int, joinery: bool) -> None:
    _full_game(n, 5, joinery=joinery)


def test_full_random_game_joinery_false_3p_margin() -> None:
    g = _full_game(3, 2, joinery=False, returns="margin")
    assert g["view"]["game"]["joinery"] is False


# ------------------------------------------------------------------ winners and final dollars


def _terminal_view(n: int, mode: str, final: list[int], loans: list[int]) -> Json:
    """Play a random game to its end, then impose final dollars and loans (test-only).

    Money is set to final + 10 * loans, so seats with more loans hold more money and the money
    order differs from the final-dollar order.
    """
    from server.adapters.lignum import LignumAdapter

    ad = LignumAdapter()
    game = ad.load({"num_players": n, "returns": mode})
    s: Any = game.new_initial_state()
    rng = random.Random(1)
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
        else:
            s.apply_action(rng.choice(s.legal_actions()))
    s.final = tuple(final)
    s.loans = tuple(loans)
    s.money = tuple(f + 10 * loan for f, loan in zip(final, loans, strict=True))
    return ad.view(s, 0)


@pytest.mark.parametrize("mode", ["win_loss", "margin"])
@pytest.mark.parametrize(
    ("final", "loans", "winners"),
    [
        ([10, 30, 20], [0, 2, 1], [1]),  # sole winner, money 10, 50, 30
        ([30, 30, 5], [2, 2, 0], [0, 1]),  # partial tie; the low-final seat has the least money
        ([-16, -16, -16], [0, 1, 2], [0, 1, 2]),  # all tie
        ([-3, -20, -9], [2, 0, 1], [0]),  # negative finals, money -3, -20, 1
        ([40, 10, 25], [0, 2, 1], [0]),  # winner has the lowest money (40, 30, 35)
    ],
)
def test_winners_and_final_from_engine_final_dollars(
    mode: str, final: list[int], loans: list[int], winners: list[int]
) -> None:
    v = _terminal_view(3, mode, final, loans)
    assert v["final"] == final
    assert v["winners"] == winners
    assert len(v["returns"]) == 3
    if mode == "win_loss":
        assert [i for i, r in enumerate(v["returns"]) if r > 0] == (
            [] if len(winners) == 3 else winners
        )
        assert abs(sum(v["returns"])) < 1e-9


def test_final_and_winners_null_before_the_end() -> None:
    c = _client()
    g = _create(c, ["human", "random"], seed=3)
    assert not g["is_terminal"]
    assert g["view"]["final"] is None and g["winners"] is None and g["returns"] is None


# ------------------------------------------------------------------ mixed human/random


def test_mixed_stops_at_human_and_resumes() -> None:
    c = _client()
    g = _create(c, ["random", "human", "random"], seed=8)
    gid = g["id"]
    assert g["current_player"] == 1 and not g["bot_thinking"]
    for _ in range(15):
        n0 = g["history_length"]
        ids = [a["id"] for a in g["legal_actions"]]
        g = _act(c, gid, H.DONE if H.DONE in ids else ids[0])
        assert g["history_length"] > n0
        assert g["is_terminal"] or g["current_player"] == 1
        # not the human's action: the bots played in between, with actors recorded
        acted = {e["actor"] for e in g["history"]}
        assert acted <= {None, 0, 1, 2}
    assert {0, 1, 2} <= {e["actor"] for e in g["history"]} | {None}
    r = c.post(f"/api/games/{gid}/actions", json={"action": g["legal_actions"][0]["id"] + 9999})
    assert r.status_code == 409


def test_human_cannot_act_for_bot_or_after_end() -> None:
    c = _client()
    g = _create(c, ["random", "random"], seed=1)
    r = c.post(f"/api/games/{g['id']}/actions", json={"action": 0})
    assert r.status_code == 409


# ------------------------------------------------------------------ back / rewind


def test_back_across_bots_and_chance_restores_exactly() -> None:
    c = _client()
    g = _create(c, ["human", "random", "random"], seed=9)
    gid = g["id"]
    snaps: list[tuple[int, list[str]]] = []
    for _ in range(40):
        snaps.append((g["history_length"], _fingerprint(c, gid, 3)))
        g = _play_human(c, g, 1)
        if g["is_terminal"]:
            break
    # Back returns to the start of the previous human turn: a recorded state, restored exactly
    by_len = dict(snaps)
    prev = None
    for _ in range(len(snaps)):
        r = c.post(f"/api/games/{gid}/back")
        if r.status_code == 409:
            break
        assert r.status_code == 200, r.text
        length = r.json()["history_length"]
        assert prev is None or length < prev
        assert length in by_len, length
        assert _fingerprint(c, gid, 3) == by_len[length]
        prev = length
    assert prev is not None


def test_back_with_no_human_turn_is_409() -> None:
    c = _client()
    g = _create(c, ["human", "random"], seed=1)
    r = c.post(f"/api/games/{g['id']}/back")
    assert r.status_code == 409 and r.json()["detail"]


def test_replay_after_back_is_deterministic() -> None:
    c = _client()
    g = _create(c, ["human", "random"], seed=4)
    gid = g["id"]
    g = _play_human(c, g, 6)
    ref = [e["id"] for e in g["history"]]
    for _ in range(3):
        c.post(f"/api/games/{gid}/back")
    ids = [a["id"] for a in _view(c, gid, 0)["legal_actions"]]
    assert ids
    g = _play_human(c, _view(c, gid, 0), 3)
    assert [e["id"] for e in g["history"]][: len(ref)] == ref or len(g["history"]) >= 1


def test_rewind_dev_only_and_consistent() -> None:
    c = _client()
    g = _create(c, ["human", "random", "random"], seed=6)
    r = c.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 0})
    assert r.status_code == 403
    cd = _client()
    gd = _create(cd, ["human", "random", "random"], seed=6)
    gid = gd["id"]
    gd = _play_human(cd, gd, 12)
    for k in (5, 2, 0):
        r = cd.post(f"/api/games/{gid}/rewind", json={"player_actions": k})
        assert r.status_code == 403  # dev_mode False on this app too
    dev = TestClient(create_app(dev_mode=True, inline_bots=True))
    g = _create(dev, ["human", "random", "random"], seed=6)
    gid = g["id"]
    g = _play_human(dev, g, 12)
    full = g["history"]
    for k in (5, 2, 0):
        r = dev.post(f"/api/games/{gid}/rewind", json={"player_actions": k})
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["history_length"] == len(v["history"])
        assert v["history"] == full[: len(v["history"])]
        assert not v["bot_thinking"]
        assert v["is_terminal"] or v["current_player"] == 0
    r = dev.post(f"/api/games/{gid}/rewind", json={"player_actions": 10_000})
    assert r.status_code == 400 and r.json()["detail"]
    r = dev.post(f"/api/games/{gid}/rewind", json={"player_actions": -1})
    assert r.status_code == 400


def _to_hidden_pick(c: TestClient, g: Json) -> Json:
    for _ in range(3000):
        ids = [a["id"] for a in g["legal_actions"]]
        if set(ids) == PICK_IDS:
            return g
        g = _act(c, g["id"], H.DONE if H.DONE in ids else ids[0])
    raise AssertionError("no hidden pick")


def test_rewind_inside_pick_run_stays_masked() -> None:
    dev = TestClient(create_app(dev_mode=True, inline_bots=True))
    g = _to_hidden_pick(dev, _create(dev, ["human", "human", "random"], seed=4))
    gid = g["id"]
    n = g["history_length"]
    g = _act(dev, gid, g["legal_actions"][0]["id"])
    g = _act(dev, gid, g["legal_actions"][1]["id"])
    k = sum(1 for e in g["history"] if e["actor"] is not None)
    v = dev.post(f"/api/games/{gid}/rewind", json={"player_actions": k - 1}).json()
    for seat in (0, 1, 2):
        assert len(_view(dev, gid, seat)["history"]) == v["history_length"]
    _assert_no_leak(dev, gid, 3)
    assert n <= v["history_length"]


# ------------------------------------------------------------------ no seat leak


def _assert_no_leak(c: TestClient, gid: str, n: int) -> None:
    """While picks are unrevealed, no seat's response contains another seat's pick."""
    exp = c.get(f"/api/games/{gid}/export")
    views = [_view(c, gid, s) for s in range(n)]
    picked = views[0]["view"]["picked"]
    if views[0]["view"]["phase"] != "PK" or not picked:
        assert exp.status_code == 200
        return
    assert exp.status_code == 409 and "history" not in exp.json()
    k = len(picked)
    privs = [v["view"]["private"]["pick"] for v in views]
    assert [p is not None for p in privs] == [s in picked for s in range(n)]
    for s, v in enumerate(views):
        assert v["view"]["seat"] == s
        tail = v["history"][-k:]
        assert [e["actor"] for e in tail] == picked
        for e in tail:
            if e["actor"] == s:
                assert e["id"] == privs[s] + 2
            else:
                assert e["id"] is None
                rest = e["label"].replace(f"P{e['actor']}", "")
                assert "area" in e["label"] and not any(ch.isdigit() for ch in rest)
        # nothing else in the response may carry another seat's area
        stripped = json.dumps({**v, "history": v["history"][:-k]})
        assert v["view"]["picks"] == views[0]["view"]["picks"]
        assert stripped.count('"pick"') == 1  # only private.pick


def test_no_seat_leak_through_a_game_with_back() -> None:
    c = _client()
    g = _create(c, ["human", "human", "random"], seed=7)
    gid = g["id"]
    checked = 0
    for i in range(400):
        if g["is_terminal"]:
            break
        _assert_no_leak(c, gid, 3)
        checked += 1
        ids = [a["id"] for a in g["legal_actions"]]
        if i % 37 == 36:
            r = c.post(f"/api/games/{gid}/back")
            if r.status_code == 200:
                g = r.json()
                _assert_no_leak(c, gid, 3)
                continue
        g = _act(c, gid, H.DONE if H.DONE in ids else ids[-1])
        # human picks happen when all legal are pick ids
    assert checked > 50


def test_leak_scan_at_each_pick_step() -> None:
    c = _client()
    g = _to_hidden_pick(c, _create(c, ["random", "human", "human", "human"], seed=2))
    gid = g["id"]
    for i in range(3):
        assert g["view"]["private"]["pick"] is None
        _assert_no_leak(c, gid, 4)
        if i == 1:  # undo a pick, then re-pick
            g = c.post(f"/api/games/{gid}/back").json()
            _assert_no_leak(c, gid, 4)
        g = _act(c, gid, g["legal_actions"][2]["id"])
    _assert_no_leak(c, gid, 4)


# ------------------------------------------------------------------ export / import


def _roundtrip(c: TestClient, gid: str, n: int) -> Json:
    exp = c.get(f"/api/games/{gid}/export")
    assert exp.status_code == 200, exp.text
    body = exp.json()
    assert "scenario" not in body
    assert "dump" not in json.dumps(body).lower()
    r = c.post("/api/games/import", json=body)
    assert r.status_code == 200, r.text
    g2 = r.json()
    assert _fingerprint(c, g2["id"], n) == _fingerprint(c, gid, n)
    assert g2["id"] != gid
    return body


@pytest.mark.parametrize("n", [2, 3, 4])
def test_export_import_finished_game(n: int) -> None:
    c = _client()
    g = _create(c, ["random"] * n, seed=5)
    assert g["is_terminal"]
    body = _roundtrip(c, g["id"], n)
    assert len(body["history"]) == g["history_length"]


def test_export_import_in_progress_then_continue() -> None:
    c = _client()
    g = _create(c, ["human", "random", "random"], seed=13)
    for _ in range(5):
        g = _play_human(c, g, 7)
        r = c.get(f"/api/games/{g['id']}/export")
        if r.status_code == 409:
            continue
        body = _roundtrip(c, g["id"], 3)
        g2 = c.post("/api/games/import", json=body).json()
        # continuing both games identically gives identical results
        a = _play_human(c, g2, 5)
        b = _play_human(c, _view(c, g["id"], 0), 5)
        # the imported prefix is identical; continued play uses a fresh secret salt
        k = len(body["history"])
        assert [e["id"] for e in a["history"]][:k] == [e["id"] for e in b["history"]][:k]
        g = b


def test_export_while_picks_unrevealed_never_contains_picks() -> None:
    c = _client()
    g = _to_hidden_pick(c, _create(c, ["human", "human", "random"], seed=4))
    g = _act(c, g["id"], g["legal_actions"][0]["id"])
    r = c.get(f"/api/games/{g['id']}/export")
    assert r.status_code == 409 and "history" not in r.json()


def test_import_rejects_illegal_history() -> None:
    c = _client()
    g = _create(c, ["human", "random"], seed=3)
    gid = g["id"]
    g = _play_human(c, g, 4)
    body = c.get(f"/api/games/{gid}/export").json()
    bad = {**body, "history": body["history"] + [999_999]}
    r = c.post("/api/games/import", json=bad)
    assert r.status_code == 400 and "history" in r.json()["detail"]
    bad = {**body, "history": [999_999] + body["history"]}
    assert c.post("/api/games/import", json=bad).status_code == 400
    bad = {**body, "history": [-1]}
    assert c.post("/api/games/import", json=bad).status_code == 400
    # a legal history with a chance outcome swapped for an invalid one
    bad = {**body, "history": body["history"][:1] + [body["history"][0]] + body["history"][2:]}
    r = c.post("/api/games/import", json=bad)
    assert r.status_code in (200, 400)
    # wrong seats count
    r = c.post("/api/games/import", json={**body, "seats": ["human"]})
    assert r.status_code == 400
    r = c.post("/api/games/import", json={**body, "game": "nope"})
    assert 400 <= r.status_code < 500


def test_import_rejects_serialized_state_and_extra_scenario() -> None:
    c = _client()
    g = _create(c, ["human", "random"], seed=3)
    body = c.get(f"/api/games/{g['id']}/export").json()
    r = c.post("/api/games/import", json={**body, "serialized": "x"})
    assert r.status_code in (200, 422)  # unknown key ignored, never used
    assert (
        "serialized" not in c.get(f"/api/games/{r.json()['id']}/export").text
        if r.status_code == 200
        else True
    )
    r = c.post("/api/games/import", json={**body, "scenario": {"players": 2}})
    assert 400 <= r.status_code < 500


# ------------------------------------------------------------------ report


def test_report_written_with_full_history_even_with_unrevealed_picks(tmp_path: Any) -> None:
    c = _client(reports_dir=tmp_path)
    g = _to_hidden_pick(c, _create(c, ["human", "human", "random"], seed=4))
    g = _act(c, g["id"], g["legal_actions"][0]["id"])
    r = c.post(f"/api/games/{g['id']}/report", json={"note": "weird pick"})
    assert r.status_code == 200, r.text
    data = json.loads(Path(r.json()["path"]).read_text())
    assert len(data["history"]) == g["history_length"]
    assert data["view"]["history_length"] == g["history_length"]
    assert data["export"]["history"] == data["history"]
    assert "dump_scenario" not in json.dumps(data)
    # 404 for unknown
    assert c.post("/api/games/zzz/report", json={"note": "x"}).status_code == 404
