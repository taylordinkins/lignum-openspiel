"""Playback frames: GET /api/games/{id}?at=N renders the state after the first N history entries."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from server.app import create_app
from tests import harness as H
from tests.server.test_lignum_labels import _act, _new, _view

Json = dict[str, Any]


def _frame(c: TestClient, gid: str, at: int, seat: int | None = None, ok: bool = True) -> Json:
    q = f"?at={at}" + ("" if seat is None else f"&seat={seat}")
    r = c.get(f"/api/games/{gid}{q}")
    if ok:
        assert r.status_code == 200, r.text
    return r.json()


def _play(c: TestClient, g: Json, steps: int) -> Json:
    for _ in range(steps):
        if g["is_terminal"]:
            break
        ids = [a["id"] for a in g["legal_actions"]]
        g = _act(c, g["id"], H.DONE if H.DONE in ids else ids[0])
    return g


def _same(a: Json, b: Json) -> None:
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_frame_at_zero() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _play(c, _new(c, ["human", "human"], 4), 12)
    f = _frame(c, g["id"], 0, seat=0)
    assert f["history_length"] == 0 and f["history"] == []
    assert f["id"] == g["id"] and f["seat"] == 0
    assert g["history_length"] > 0


def test_frame_middle_and_live() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _play(c, _new(c, ["human", "human"], 4), 15)
    n = g["history_length"]
    mid = n // 2
    f = _frame(c, g["id"], mid, seat=0)
    assert f["history_length"] == mid
    assert [e["index"] for e in f["history"]] == list(range(mid))
    live = _view(c, g["id"], 0)
    assert f["history"] == live["history"][:mid]
    # N = len is the live view, identical to omitting `at`.
    _same(_frame(c, g["id"], n, seat=0), live)
    # default seat follows the frame's player to move
    assert _frame(c, g["id"], mid)["seat"] == max(f["current_player"] or 0, 0)


def test_frame_out_of_range_409() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _play(c, _new(c, ["human", "human"], 4), 3)
    n = g["history_length"]
    for at in (n + 1, -1):
        r = c.get(f"/api/games/{g['id']}?at={at}")
        assert r.status_code == 409, r.text


def test_frame_does_not_mutate_live_session() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _play(c, _new(c, ["human", "human"], 4), 10)
    before = _view(c, g["id"], 1)
    _frame(c, g["id"], 1, seat=1)
    _same(_view(c, g["id"], 1), before)


def test_frame_bot_thinking() -> None:
    c = TestClient(create_app(inline_bots=True))
    g = _play(c, _new(c, ["human", "random"], 5), 20)
    n = g["history_length"]
    frames = [_frame(c, g["id"], k, seat=0) for k in range(n)]
    assert any(f["bot_thinking"] for f in frames)
    for f in frames:
        assert f["bot_error"] is None
        if f["bot_thinking"]:
            assert f["current_player"] == 1


def test_frames_equal_what_each_seat_saw_live_no_pick_leak() -> None:
    """A frame for seat s equals the live view s had at that history length, hidden picks
    included: nothing the live view masked appears in a frame, whatever is revealed since."""
    c = TestClient(create_app(inline_bots=True))
    g = _new(c, ["human", "human"], 4)
    gid = g["id"]
    seen: dict[tuple[int, int], Json] = {}
    saw_masked = False
    extra = 0
    for _ in range(3000):
        for seat in (0, 1):
            v = _view(c, gid, seat)
            seen[(seat, v["history_length"])] = v
            saw_masked = saw_masked or any(e["id"] is None for e in v["history"])
        if g["is_terminal"] or extra > 40:
            break
        extra += saw_masked
        ids = [a["id"] for a in g["legal_actions"]]
        g = _act(c, gid, H.DONE if H.DONE in ids else ids[0])
    assert saw_masked, "never produced a masked pick"
    for (seat, n), v in seen.items():
        f = _frame(c, gid, n, seat=seat)
        assert f["history"] == v["history"]
        _same(f["view"], v["view"])
        assert f["legal_actions"] == v["legal_actions"]
        assert f["history_length"] == v["history_length"]
    # explicit: a frame taken while a pick was unrevealed shows it masked for the other seat
    n, seat = next(
        (n, s) for (s, n), v in sorted(seen.items()) if any(e["id"] is None for e in v["history"])
    )
    f = _frame(c, gid, n, seat=seat)
    hidden = [e for e in f["history"] if e["id"] is None]
    assert hidden and all(e["actor"] != seat for e in hidden)
    assert all(e["label"] == f"P{e['actor']} picked an area" for e in hidden)
    other = _frame(c, gid, n, seat=hidden[0]["actor"])
    assert other["history"][hidden[0]["index"]]["id"] is not None
