"""Phase 3 unit 2: Lignum adapter and per-seat view (written before the implementation).

Hidden information (R-029, R-030, R-038): the only secret is a seat's cutting-area pick between
choosing and the reveal. The view for a seat must never leak another seat's unrevealed pick.
Tests avoid assuming the view's keys: they compare views of states that differ only in a hidden
pick (the "two-state trick").

Assumptions flagged in the report: view(state, A) differs when A's own pick differs (the seat can
see its own pick); a view contains no top-level history/scenario dump keys.
"""

from __future__ import annotations

import json
import random
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R


def _adapter() -> Any:
    from server.adapters.lignum import LignumAdapter

    return LignumAdapter()


def _pk_state(n: int, joinery: bool = False, seed: int = 1, rnd: int = 2) -> Any:
    run = R.drive(
        {"players": n, "joinery": joinery},
        seed=seed,
        stop=lambda c: c.round == rnd and c.phase == "PK",
    )
    assert run.stopped
    return run.state


def _after(state: Any, picks: list[int]) -> Any:
    s = state.clone()
    for a in picks:
        assert H.PICK_AREA(a) in s.legal_actions()
        s.apply_action(H.PICK_AREA(a))
    return s


def _j(v: Any) -> str:
    return json.dumps(v, sort_keys=True)


def test_R029_registry_has_lignum() -> None:
    """Registry: default_adapters() includes 'lignum'; get_adapter returns a LignumAdapter."""
    from server.adapters import default_adapters, get_adapter
    from server.adapters.base import GameAdapter
    from server.adapters.lignum import LignumAdapter

    assert "lignum" in default_adapters()
    a = get_adapter("lignum")
    assert isinstance(a, LignumAdapter) and isinstance(a, GameAdapter)
    assert a.name == "lignum"


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.parametrize("joinery", [True, False])
def test_R029_load_maps_params(n: int, joinery: bool) -> None:
    """load() maps num_players/joinery/returns onto the engine game."""
    g = _adapter().load({"num_players": n, "joinery": joinery, "returns": "margin"})
    assert g.num_players() == n
    g2 = _adapter().load({"num_players": n})
    assert g2.num_players() == n


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.parametrize("joinery", [True, False])
def test_R029_view_json_serialisable_along_playthrough(n: int, joinery: bool) -> None:
    """R-029: view is JSON-serialisable for every seat at every state of random playthroughs."""
    ad = _adapter()
    game = ad.load({"num_players": n, "joinery": joinery})
    for seed in (1, 2):
        rng = random.Random(seed)
        s = game.new_initial_state()
        for step in range(150):
            if s.is_terminal():
                break
            for seat in range(n):
                v = ad.view(s, seat)
                assert isinstance(v, dict)
                json.dumps(v)
            if s.is_chance_node():
                s.apply_action(H.sample_chance(s, rng))
            else:
                acts = s.legal_actions()
                a = rng.choice(acts)
                if s.current_player() == 0 and step % 17 == 0:
                    meta = ad.action_meta(s, a)
                    assert isinstance(meta["label"], str) and meta["label"]
                s.apply_action(a)
        for seat in range(n):
            json.dumps(ad.view(s, seat))


def test_R029_action_meta_labels_nonempty_and_zero_based() -> None:
    """action_meta gives a non-empty str label for each legal action; seat 0 is never 'Player 1'."""
    ad = _adapter()
    s = _pk_state(2)
    for a in s.legal_actions():
        label = ad.action_meta(s, a)["label"]
        assert isinstance(label, str) and label
        assert "Player 1" not in label or s.current_player() == 1  # no off-by-one names


def test_R029_view_has_no_player_one_for_seat_zero() -> None:
    """Seats are numbered from 0: no 'Player <n+1>' style names in the view."""
    ad = _adapter()
    s = _pk_state(2)
    for seat in range(2):
        text = _j(ad.view(s, seat))
        assert "Player 2" not in text
        assert "Player 1" not in text


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.parametrize("joinery", [True, False])
def test_R029_other_seats_cannot_see_unrevealed_pick(n: int, joinery: bool) -> None:
    """R-029/R-038: states differing only in P0's hidden pick give every other seat equal views."""
    ad = _adapter()
    base = _pk_state(n, joinery)
    s_a = _after(base, [0])
    s_b = _after(base, [5])
    assert not s_a.is_chance_node() and s_a.current_player() == 1
    for other in range(1, n):
        assert _j(ad.view(s_a, other)) == _j(ad.view(s_b, other)), f"seat {other} leaks P0 pick"


def test_R029_picker_sees_own_pick() -> None:
    """R-029: a seat's own pick is visible to itself (view differs when its own pick differs)."""
    ad = _adapter()
    base = _pk_state(3)
    s_a = _after(base, [0])
    s_b = _after(base, [5])
    assert _j(ad.view(s_a, 0)) != _j(ad.view(s_b, 0))
    assert ad.view(s_a, 0)["private"]["pick"] == 0
    assert ad.view(s_b, 0)["private"]["pick"] == 5


def test_R029_later_pickers_hidden_from_earlier_and_each_other() -> None:
    """R-029: with P0 and P1 both picked, others cannot see either pick."""
    ad = _adapter()
    base = _pk_state(4)
    x = _after(base, [0, 1])
    y = _after(base, [3, 1])  # differ only in P0's pick
    z = _after(base, [0, 4])  # differ only in P1's pick
    for seat in (1, 2, 3):
        assert _j(ad.view(x, seat)) == _j(ad.view(y, seat))
    for seat in (0, 2, 3):
        assert _j(ad.view(x, seat)) == _j(ad.view(z, seat))


def test_R029_pick_id_not_present_in_other_seat_view_after_pick() -> None:
    """R-029: the view for B is the same as before A picked in everything about A's pick."""
    ad = _adapter()
    base = _pk_state(2)
    s = _after(base, [2])
    for forbidden in ("history", "scenario", "dump_scenario", "action_history"):
        assert forbidden not in ad.view(s, 1)
    v = ad.view(s, 1)
    assert v["private"]["pick"] is None
    assert v["picks"] == list(base.picks)  # no pending pick enters the public picks
    assert v["picked"] == [0]
    assert v["log"][0]["picks"] == list(base.picks)


def test_R029_reveal_makes_picks_public() -> None:
    """R-038/R-028: after the last pick all picks are public: every seat's view reflects them."""
    ad = _adapter()
    base = _pk_state(3)
    x = _after(base, [0, 1, 2])
    y = _after(base, [3, 1, 2])  # P0's pick changed, revealed
    assert x.current_player() >= 0 or x.is_chance_node()
    for seat in range(3):
        assert _j(ad.view(x, seat)) != _j(ad.view(y, seat)), f"seat {seat} cannot see revealed pick"
        vx, vy = ad.view(x, seat), ad.view(y, seat)
        assert vx["picks"] == [0, 1, 2]
        assert vy["picks"] == [3, 1, 2]
        assert vx["private"]["pick"] is None and vx["picked"] == []
        assert vy["private"]["pick"] is None and vy["picked"] == []


def test_R029_public_part_agrees_between_seats_pre_reveal() -> None:
    """R-028: views for different seats are built on the same public data (same JSON keys)."""
    ad = _adapter()
    s = _after(_pk_state(3), [4])
    keys = {frozenset(ad.view(s, seat)) for seat in range(3)}
    assert len(keys) == 1
    # seats that have not picked (P1, P2) see identical views apart from any seat identity context
    v1, v2 = ad.view(s, 1), ad.view(s, 2)
    diff = {k for k in v1 if v1[k] != v2[k]}
    assert diff <= {"seat", "me", "viewer", "you", "private"}, diff


def test_R029_view_before_any_pick_equal_for_non_viewers() -> None:
    """R-028: with no pick made yet, views are equal across seats apart from identity keys."""
    ad = _adapter()
    s = _pk_state(2)
    v0, v1 = ad.view(s, 0), ad.view(s, 1)
    diff = {k for k in v0 if v0[k] != v1[k]}
    assert diff <= {"seat", "me", "viewer", "you", "private"}, diff


# Report 20261106T212915-8912cc: the token list must say which token is on which spot.
_TOKEN_HISTORY = [
    6, 27, 27, 28, 35, 34, 45, 52, 47, 48, 55, 50, 54, 85, 84, 77, 76, 83, 78, 79,
    82, 89, 89, 87, 96, 96, 92, 99, 95, 92, 91, 93, 91, 101, 101, 94, 93,
]  # fmt: skip
_OBSERVER_TO_LABEL = {"dollar": "$1", "x_marker": "X marker"}


def _observer_tokens(state: Any) -> list[str]:
    field = next(f for f in str(state).split(" | ") if f.startswith("tokens "))
    return [_OBSERVER_TO_LABEL.get(t, t) for t in field.removeprefix("tokens ").split(",")]


def test_path_tokens_list_spot_location_and_kind() -> None:
    state = H.replay({"players": 4, "joinery": True}, _TOKEN_HISTORY)
    toks = _adapter().view(state, 0)["path"]["tokens"]
    assert [t["spot"] for t in toks] == list(range(1, 14))
    assert [t["kind"] for t in toks] == _observer_tokens(state)
    assert [t["location"] for t in toks] == [1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22]
    assert all(t["taken"] is False for t in toks)
    for seat in range(4):
        assert _adapter().view(state, seat)["path"]["tokens"] == toks


def test_path_tokens_taken_spot_has_no_kind() -> None:
    rng = random.Random(3)
    state = H.load_game(players=3).new_initial_state()
    while not state.is_terminal() and all(y >= 0 for y in state.path_tokens or (0,)):
        if state.is_chance_node():
            state.apply_action(H.sample_chance(state, rng))
        else:
            state.apply_action(rng.choice(state.legal_actions()))
    assert any(y < 0 for y in state.path_tokens)
    toks = _adapter().view(state, 0)["path"]["tokens"]
    assert len(toks) == 13
    for t, y in zip(toks, state.path_tokens, strict=True):
        assert t["taken"] is (y < 0)
        assert (t["kind"] is None) is (y < 0)


def test_view_exposes_slot_name_orders() -> None:
    """Per-seat tuples are labelled from the engine's own orders (equipment, wood kinds, craft)."""
    from lignum.rules import CRAFT_ORDER, EQUIP_SLOTS, KIND_NAMES

    v = _adapter().view(_pk_state(2), 0)
    assert v["equip_slots"] == list(EQUIP_SLOTS)
    assert v["kind_names"] == list(KIND_NAMES)
    assert v["craft_order"] == list(CRAFT_ORDER)
    assert len(v["seats"][0]["equip"]) == len(v["equip_slots"])
    assert len(v["seats"][0]["woodpile"]) == len(v["kind_names"])
    assert len(v["seats"][0]["held_craft"]) == len(v["craft_order"])


_E08E86_HISTORY = [
    6,
    27,
    27,
    28,
    35,
    34,
    45,
    52,
    47,
    48,
    55,
    50,
    54,
    85,
    84,
    77,
    76,
    83,
    78,
    79,
    82,
    89,
    89,
    87,
    96,
    96,
    92,
    99,
    95,
    92,
    91,
    93,
    91,
    101,
    101,
    94,
    93,
    2,
    4,
    5,
    6,
    8,
    25,
    33,
    33,
    1,
    0,
    18,
    22,
    9,
    29,
    26,
    23,
    10,
    30,
    1,
    1,
    30,
    24,
    11,
    31,
    31,
    0,
    25,
    33,
    1,
    1,
    0,
    12,
    30,
    13,
    34,
    14,
    16,
    17,
    32,
    32,
    0,
    20,
    21,
]


def test_R036_task_row_ids_match_take_task_labels() -> None:
    """Playtest 20261106T213346-e08e86: row shows card ids, same as 'Take task NN' labels."""
    a = _adapter()
    g = a.load({"num_players": 4, "joinery": True, "returns": "win_loss"})
    s = H.replay(g, _E08E86_HISTORY)
    v = a.view(s, 0)
    assert v["tasks"]["row"] == [0, 6, 7, 17]
    assert v["tasks"]["row_ids"] == ["task 01", "task 07", "task 08", "task 18"]
    labels = {a.action_meta(s, x)["label"] for x in s.legal_actions()}
    for tid in v["tasks"]["row_ids"]:
        assert f"Take {tid}" in labels
    assert len(v["tasks"]["filled_ids"]) == sum(v["tasks"]["filled"])
    for seat in v["seats"]:
        assert len(seat["held_task_ids"]) == len(seat["held_tasks"])


def test_mill_used_is_public_and_not_pick_dependent() -> None:
    """Unit 9d: mill_used (mill worker away from its worker area) is a public per-seat flag."""
    st = _pk_state(2)
    a = _adapter()
    v0, v1 = a.view(st, 0), a.view(st, 1)
    assert [s["mill_used"] for s in v0["seats"]] == [s["mill_used"] for s in v1["seats"]]
    assert all(isinstance(s["mill_used"], bool) for s in v0["seats"])
