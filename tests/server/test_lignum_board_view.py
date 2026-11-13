"""Phase 5 unit 6A: board/panel fields of the lignum view (R-028) and privacy (R-029)."""

from __future__ import annotations

import json
import random
from typing import Any

from lignum.components import load_components
from lignum.game import PHASE_PK
from tests import harness as H


def _adapter() -> Any:
    from server.adapters.lignum import LignumAdapter

    return LignumAdapter()


def _states(n: int, seed: int, every: int = 60, cap: int = 3000):
    ad = _adapter()
    game = ad.load({"num_players": n, "joinery": True})
    rng = random.Random(seed)
    s = game.new_initial_state()
    for i in range(cap):
        if s.is_terminal():
            return
        if i % every == 0:
            yield ad, s
        s.apply_action(
            H.sample_chance(s, rng) if s.is_chance_node() else rng.choice(s.legal_actions())
        )


def test_seat_labels_zero_based() -> None:
    ad, s = next(_states(3, 1))
    assert [x["label"] for x in ad.view(s, 0)["seats"]] == ["P0", "P1", "P2"]


def test_path_locations_match_engine() -> None:
    side = load_components().path.sides["joinery"]
    seen = 0
    for ad, s in _states(3, 2):
        v: Any = ad.view(s, 1)
        locs = v["path"]["locations"]
        assert [x["number"] for x in locs] == [loc.number for loc in side]
        assert [x["kind"] for x in locs] == [loc.kind for loc in side]
        by_kind = {x["kind"]: x for x in locs if x["kind"] != "token_spot"}
        assert by_kind["bearers"]["pool"] == s.path_b
        assert by_kind["woodcutters"]["pool"] == s.path_w
        assert by_kind["fodder"]["pool"] == s.path_fodder
        assert by_kind["joiner"]["pool"] == s.path_joiner
        assert by_kind["sawyers"]["pool"] == {"free": s.path_sf, "paid": s.path_sp}
        for x in locs:
            assert x["foremen"] == [q for q in range(s.n) if s.foreman[q] == x["number"]]
            assert len(x["foremen"]) <= x["capacity"]
        toks = [x["token"] for x in locs if x["token"]]
        assert (
            toks
            == [
                {"spot": t["spot"], "kind": t["kind"], "taken": t["taken"]}
                for t in v["path"]["tokens"]
            ]
            or not s.path_tokens
        )
        slots = v["path"]["clearing_slots"]
        assert len(slots) == 4 and [q for q in slots if q is not None] == list(s.clearing)
        seen += 1
    assert seen > 5


def test_seat_boards_match_engine() -> None:
    for ad, s in _states(2, 3):
        v: Any = ad.view(s, 0)
        for i, sv in enumerate(v["seats"]):
            assert sv["woodpile"] == list(s.woodpile[i])
            assert sv["river"] == list(s.river[i])
            assert sv["sawing"] == list(s.sawing[i])
            assert sv["sale"] == list(s.sale[i])
            assert sv["dry"] == [list(d) for d in s.dry[i]]
            assert sv["store"] == list(s.store[i])
            assert sv["joinery_wood"] == list(s.joinery_wood[i])
            assert sv["held_craft"] == list(s.held_craft[i])
            assert sv["held_tasks"] == list(s.held_tasks[i])
            assert sv["fodder"] == [s.fodder3[i], s.fodder2[i]]
            assert sv["hired"] == {"b": s.hired_b[i], "w": s.hired_w[i], "s": s.hired_s[i]}
            assert sv["loans"] == s.loans[i] and sv["joiners"] == s.joiners[i]
            assert sv["buildings"] == list(s.held_buildings[i])
        held = {k for h in s.held_tasks for k in h}
        assert {c["index"] for c in v["tasks"]["cards"]} == held | set(s.task_row)
        assert v["buildings"]["supply"] == list(s.bld_supply)
        assert v["pw"]["row"] == list(s.draws.pw)
        assert v["craft"]["pile"] == list(s.craft_pile)
        assert v["placement"]["discarded"] == list(s.placement_discarded)


def test_views_identical_across_seats_except_private() -> None:
    for ad, s in _states(3, 4):
        views = [json.loads(json.dumps(ad.view(s, q))) for q in range(3)]
        for v in views:
            v.pop("seat")
            v.pop("private")
            v.pop("legal_actions")
        assert views[0] == views[1] == views[2]


def test_hidden_pick_never_in_other_seat_view() -> None:
    """R-029: P0's unrevealed pick appears only in P0's private; never in P1's view."""
    ad = _adapter()
    game = ad.load({"num_players": 2, "joinery": True})
    rng = random.Random(5)
    s: Any = game.new_initial_state()
    checked = 0
    for _ in range(3000):
        if s.is_terminal():
            break
        if s.phase == PHASE_PK and len(s.pk) == 1 and not s.is_chance_node():
            hidden = s.pk[0]
            other = ad.view(s, 1)
            assert other["private"]["pick"] is None
            assert other["picked"] == [0]
            assert other["picks"] == list(s.picks)  # revealed picks only
            assert other["log"][0]["picks"] == list(s.picks)
            assert ad.view(s, 0)["private"]["pick"] == hidden
            checked += 1
        s.apply_action(
            H.sample_chance(s, rng) if s.is_chance_node() else rng.choice(s.legal_actions())
        )
    assert checked >= 1
