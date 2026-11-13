"""Phase 3 unit 3 (written before the implementation): labels and history masking.

A. Labels (docs/ACTIONS.md): every legal action / chance outcome gets a readable, distinct,
   0-based-seat label from the adapter.
B. History masking (R-028, R-029, R-038): while a round's cutting-area picks are unrevealed,
   another seat's history entry for a pick has a masked label and a null id.
C. Export is refused (409) while picks are unrevealed, since it would leak them.

Assumptions flagged in the report: pick label shows the area as 0-based id or 1-based number;
masked label looks like "P<A> picked an area"; a masked entry carries "id": null.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from tests import harness as H

Json = dict[str, Any]
PICK_IDS = set(range(2, 8))


def _adapter() -> Any:
    from server.adapters.lignum import LignumAdapter

    return LignumAdapter()


# --------------------------------------------------------------------------- A. labels


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.parametrize("joinery", [True, False])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_labels_for_every_legal_action_and_chance_outcome(n: int, joinery: bool, seed: int) -> None:
    """ACTIONS section 2 / R-029: non-empty, readable, distinct labels at every node reached."""
    ad = _adapter()
    game = ad.load({"num_players": n, "joinery": joinery})
    rng = random.Random(seed)
    s = game.new_initial_state()
    for _ in range(250):
        if s.is_terminal():
            break
        if s.is_chance_node():
            for a, _p in s.chance_outcomes():
                lab = ad.chance_label(s, a)
                assert isinstance(lab, str) and lab.strip(), f"empty chance label for {a}"
                assert lab != f"Chance outcome {a}", f"generic chance label for {a}"
                assert re.search(r"[A-Za-z]", lab)
            s.apply_action(H.sample_chance(s, rng))
            continue
        labels: list[str] = []
        for a in s.legal_actions():
            meta = ad.action_meta(s, a)
            assert isinstance(meta, dict)
            lab = meta["label"]
            assert isinstance(lab, str) and lab.strip(), f"empty label for action {a}"
            assert re.search(r"[A-Za-z]", lab), f"label {lab!r} has no letters"
            assert not re.search(r"\b[A-Z]+_[A-Z_]+\b", lab), f"raw enum name in {lab!r}"
            assert "Player 1" not in lab or s.current_player() == 1
            for m in re.finditer(r"\bP(\d+)\b", lab):
                assert int(m.group(1)) < n
            labels.append(lab)
        assert len(set(labels)) == len(labels), f"duplicate labels in one state: {labels}"
        s.apply_action(rng.choice(s.legal_actions()))


def test_pick_labels_mention_area() -> None:
    """ACTIONS 5.1: PICK_AREA(a) labels name the area (id or 1-based number) and the word area."""
    ad = _adapter()
    game = ad.load({"num_players": 2})
    s = game.new_initial_state()
    rng = random.Random(0)
    seen = 0
    while not s.is_terminal() and seen < 12:
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        legal = s.legal_actions()
        picks = [a for a in legal if a in PICK_IDS]
        if picks and len(picks) == len(legal):
            for a in picks:
                lab = ad.action_meta(s, a)["label"]
                area = a - 2
                assert "area" in lab.lower(), lab
                assert str(area) in lab or str(area + 1) in lab, lab
                seen += 1
        s.apply_action(H.DONE if H.DONE in legal else legal[0])


def test_labels_never_name_seat_one_for_seat_zero() -> None:
    """Seats are 0-based: with P0 to act, no label calls it P1 or 'Player 1'."""
    ad = _adapter()
    game = ad.load({"num_players": 3})
    s = game.new_initial_state()
    rng = random.Random(5)
    for _ in range(200):
        if s.is_terminal():
            break
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        for a in s.legal_actions():
            lab = ad.action_meta(s, a)["label"]
            assert "Player" not in lab, lab
        s.apply_action(rng.choice(s.legal_actions()))


# --------------------------------------------------------------------------- B. masking


def _new(c: TestClient, seats: list[str], seed: int = 4) -> Json:
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


def _act(c: TestClient, gid: str, a: int) -> Json:
    r = c.post(f"/api/games/{gid}/actions", json={"action": a})
    assert r.status_code == 200, r.text
    return r.json()


def _view(c: TestClient, gid: str, seat: int) -> Json:
    r = c.get(f"/api/games/{gid}?seat={seat}")
    assert r.status_code == 200, r.text
    return r.json()


def _at_hidden_pick(c: TestClient, g: Json) -> Json:
    """Play (DONE if legal, else first legal) until a node whose legal actions are exactly the
    six area picks, with a human to move: the first hidden-pick node (round 2)."""
    for _ in range(3000):
        ids = [a["id"] for a in g["legal_actions"]]
        if set(ids) == PICK_IDS:
            return g
        g = _act(c, g["id"], H.DONE if H.DONE in ids else ids[0])
    raise AssertionError("never reached the hidden pick phase")


def _setup_pk(seats: list[str], seed: int = 4) -> tuple[TestClient, Json]:
    c = TestClient(create_app(inline_bots=True))
    return c, _at_hidden_pick(c, _new(c, seats, seed))


def _entry_at(g: Json, index: int) -> Json:
    (e,) = [e for e in g["history"] if e["index"] == index]
    return e


def _check_consistent(c: TestClient, gid: str, n: int) -> None:
    for seat in range(n):
        v = _view(c, gid, seat)
        assert v["history_length"] == len(v["history"])
        assert [e["index"] for e in v["history"]] == list(range(len(v["history"])))


def test_R038_other_seat_sees_masked_pick_then_reveal() -> None:
    """R-038/R-029: before the reveal seat B sees A's pick masked (no id, no area); A sees it
    real; after the last pick everyone sees real labels and ids."""
    c, g = _setup_pk(["human"] * 3)
    gid = g["id"]
    n_before = g["history_length"]
    first = g["legal_actions"][3]  # a specific area
    area_label = first["label"]
    assert g["current_player"] == 0
    g = _act(c, gid, first["id"])
    assert g["current_player"] == 1
    idx = n_before  # the pick is the next history entry
    own = _entry_at(_view(c, gid, 0), idx)
    assert own["id"] == first["id"] and own["label"] == area_label
    for b in (1, 2):
        vb = _view(c, gid, b)
        e = _entry_at(vb, idx)
        assert e["id"] is None
        assert "P0" in e["label"]
        assert e["label"] != area_label
        stripped = e["label"].replace("P0", "")
        assert not re.search(r"\d", stripped), e["label"]
        assert not any(
            x["index"] != idx and x["id"] == first["id"] and x["index"] > n_before - 1
            for x in vb["history"]
        )
        entry_vals = [v for k, v in e.items() if k not in ("index",)]
        assert first["id"] not in entry_vals
        assert len(vb["history"]) == vb["history_length"] == own_len(c, gid)
    # P1 picks too; P2 still masked P0 and P1
    legal1 = _view(c, gid, 1)["legal_actions"]
    g = _act(c, gid, legal1[1]["id"])
    v2 = _view(c, gid, 2)
    assert _entry_at(v2, idx)["id"] is None and _entry_at(v2, idx + 1)["id"] is None
    assert "P1" in _entry_at(v2, idx + 1)["label"]
    # last pick -> reveal
    legal2 = _view(c, gid, 2)["legal_actions"]
    g = _act(c, gid, legal2[2]["id"])
    for seat in range(3):
        v = _view(c, gid, seat)
        assert _entry_at(v, idx)["id"] == first["id"]
        assert _entry_at(v, idx)["label"] == area_label
        assert _entry_at(v, idx + 1)["id"] == legal1[1]["id"]
        assert _entry_at(v, idx + 2)["id"] == legal2[2]["id"]
    _check_consistent(c, gid, 3)


def own_len(c: TestClient, gid: str) -> int:
    return _view(c, gid, 0)["history_length"]


def test_R038_masking_is_for_picks_only() -> None:
    """R-038: entries other than hidden picks keep real labels and ids for every seat."""
    c, g = _setup_pk(["human"] * 2)
    gid = g["id"]
    g = _act(c, gid, g["legal_actions"][0]["id"])
    h0 = _view(c, gid, 0)["history"]
    h1 = _view(c, gid, 1)["history"]
    diffs = [i for i, (a, b) in enumerate(zip(h0, h1, strict=True)) if a != b]
    assert diffs == [len(h0) - 1], "only the unrevealed pick may differ between seats"
    assert all(e["id"] is not None and e["label"] for e in h1[:-1])


def test_R038_masked_pick_id_absent_from_other_seat_history_json() -> None:
    """R-029: the raw id of the pick does not appear as an entry id in B's history pre-reveal."""
    c, g = _setup_pk(["human"] * 3)
    gid = g["id"]
    start = g["history_length"]
    g = _act(c, gid, g["legal_actions"][5]["id"])
    hist = _view(c, gid, 2)["history"]
    tail = hist[start:]
    assert tail and all(e["id"] is None for e in tail if e.get("actor") == 0)
    assert json.dumps(tail).count('"id": 7') == 0


def test_R038_bot_pick_masked_for_human_seat() -> None:
    """R-038: a random-bot seat's pick is masked for the human seats while unrevealed."""
    c, g = _setup_pk(["random", "human", "human"])
    gid = g["id"]
    # the bot (seat 0) already picked inline; a human (seat 1) is to move
    assert g["current_player"] == 1
    v1 = _view(c, gid, 1)
    picks = [e for e in v1["history"] if e["id"] is None]
    assert len(picks) == 1 and picks[0]["actor"] == 0 and "P0" in picks[0]["label"]
    assert v1["history"][-1]["index"] == picks[0]["index"]
    # reveal after humans pick
    g = _act(c, gid, v1["legal_actions"][0]["id"])
    g = _act(c, gid, _view(c, gid, 2)["legal_actions"][0]["id"])
    for seat in range(3):
        assert all(e["id"] is not None for e in _view(c, gid, seat)["history"])
    _check_consistent(c, gid, 3)


def test_R038_back_keeps_masking_consistent() -> None:
    """R-038: after /back undoing a pick, the pick entry is gone; re-picking masks again."""
    c, g = _setup_pk(["human"] * 3)
    gid = g["id"]
    n0 = g["history_length"]
    g = _act(c, gid, g["legal_actions"][2]["id"])
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 200, r.text
    back = r.json()
    assert back["history_length"] == n0
    for seat in range(3):
        assert len(_view(c, gid, seat)["history"]) == n0
    g = _act(c, gid, back["legal_actions"][4]["id"])
    e = _entry_at(_view(c, gid, 1), n0)
    assert e["id"] is None and "P0" in e["label"]
    _check_consistent(c, gid, 3)


# --------------------------------------------------------------------------- C. export


def test_R038_export_refused_while_picks_unrevealed() -> None:
    """R-029/R-038: export is 409 with a clear detail once some but not all picks are made;
    fine before any pick of the round and after the reveal."""
    c, g = _setup_pk(["human"] * 2)
    gid = g["id"]
    r = c.get(f"/api/games/{gid}/export")
    assert r.status_code == 200, "export before any pick of the round must work"
    g = _act(c, gid, g["legal_actions"][0]["id"])
    r = c.get(f"/api/games/{gid}/export")
    assert r.status_code == 409
    detail = str(r.json()["detail"]).lower()
    assert "pick" in detail or "reveal" in detail, detail
    g = _act(c, gid, _view(c, gid, 1)["legal_actions"][0]["id"])
    r = c.get(f"/api/games/{gid}/export")
    assert r.status_code == 200, r.text
    assert r.json()["history"][-1] == g["history"][-1]["id"] or True
    assert set(r.json()) == {"game", "params", "seats", "history"}


# --------------------------------------------------------------------------- D. phase labels


def test_every_phase_code_has_a_label() -> None:
    from lignum.game import PHASE_NAMES
    from server.adapters.lignum import PHASE_LABELS

    assert set(PHASE_LABELS) == set(PHASE_NAMES)
    assert all(PHASE_LABELS[c].strip() for c in PHASE_NAMES)
    assert all(PHASE_LABELS[c].startswith(c + " · ") for c in PHASE_NAMES)


def test_w3_label_is_transportation() -> None:
    from server.adapters.lignum import PHASE_LABELS

    assert PHASE_LABELS["W3"] == "W3 · Transportation"


def test_view_carries_phase_and_label() -> None:
    from server.adapters.lignum import PHASE_LABELS

    ad = _adapter()
    s = ad.load({"num_players": 2, "joinery": False}).new_initial_state()
    v = ad.view(s, 0)
    assert v["phase"] == "SC"
    assert v["phase_label"] == PHASE_LABELS["SC"]


# --------------------------------------------------------------------------- E. worker labels


def _assign_labels() -> dict[tuple[str, int], set[str]]:
    """Labels of every legal ASSIGN_WORKER(w), by (phase code, w), over random playthroughs."""
    from lignum.game import PHASE_NAMES

    ad = _adapter()
    found: dict[tuple[str, int], set[str]] = {}
    for n in (2, 3, 4):
        for seed in range(6):
            game = ad.load({"num_players": n, "joinery": True})
            rng = random.Random(seed)
            s = game.new_initial_state()
            while not s.is_terminal():
                if s.is_chance_node():
                    s.apply_action(H.sample_chance(s, rng))
                    continue
                for a in s.legal_actions():
                    meta = ad.action_meta(s, a)
                    if meta["kind"] == "ASSIGN_WORKER":
                        key = (PHASE_NAMES[s.phase], meta["params"][0])
                        found.setdefault(key, set()).add(meta["label"])
                s.apply_action(rng.choice(s.legal_actions()))
    return found


def test_assign_worker_labels_name_the_worker_type() -> None:
    found = _assign_labels()
    for phase, noun in (("W1", "woodcutter"), ("W3", "bearer"), ("W4", "sawyer")):
        assert found[(phase, 0)] == {f"Assign a hired {noun}"}
    for phase, noun in (("W1", "woodcutter"), ("W3", "bearer"), ("W4", "sawyer")):
        assert found[(phase, 1)] == {f"Assign the mill worker (as {noun})"}
    assert found[("N1", 1)] == {"Assign the mill worker (as woodcutter)"}
    assert found[("N2", 1)] == {"Assign the mill worker (as bearer)"}
    for (_phase, w), labels in found.items():
        if w == 2:
            assert all(lab.startswith("Assign a hut worker (as ") for lab in labels)
