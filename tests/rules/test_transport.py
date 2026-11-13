"""Phase 2 unit 7: log driving and transportation (R-049..R-053).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and
tests/support/{rounds,travel,woodwork}.py (public API only).

Rigs (all base side, seed 1 unless the seed is searched)
  * RAFTS: 3 players, P0 takes raft token(s) (free), hires 1 bearer and 3 woodcutters ($4) and
    cuts its 3-firewood area empty with the woodcutters, so at W3 P0 holds 3 firewood disks in
    the woodpile, one bearer and an unused mill worker.
  * WAGON: 3 players; P0 has wagon + fodder, P1 wagon but no fodder, P2 fodder but no wagon;
    each also has 1 bearer and 3 woodcutters and cuts 3 pieces.
Trip structure follows ACTIONS 5.8; `ASSIGN_WORKER` may be auto-inserted (A4), so the helpers
tolerate both presentations.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

FW_DISK = "firewood_disk"
HW_DISK = "hardwood_disk"


def _rafts(rafts: int, bearers: int = 1) -> W.Steps:
    steps = W.Steps()
    steps.add(
        1,
        "TR",
        0,
        *W.tr_plan(
            3,
            False,
            1,
            bearers=bearers,
            woodcutters=3,
            tokens=tuple(("raft", i) for i in range(rafts)),
        ),
    )
    steps.add(1, "W1", 0, *W.cut(3))
    return steps


def _rafts_w3(rafts: int, bearers: int = 1) -> Any:
    s = W.reach(3, False, 1, _rafts(rafts, bearers), (1, "W3", 0), key=("rafts", rafts, bearers))
    sn = W.snap(s)
    me = T.seat_of(sn, 0)
    assert sn["phase"] == "W3" and s.current_player() == 0
    assert me["equipment"]["raft"] == rafts and me["hired"]["bearers"] == bearers
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 3}
    assert me["mill_worker_used"] is False
    return s


def _wagon_w3(seat: int) -> Any:
    steps = W.Steps()
    plans = {
        0: dict(tokens=(("wagon", 0),), fodder=True),
        1: dict(tokens=(("wagon", 1),), fodder=False),
        2: dict(tokens=(), fodder=True),
    }
    for i, kw in plans.items():
        steps.add(1, "TR", i, *W.tr_plan(3, False, 1, bearers=1, woodcutters=3, **kw))
        steps.add(1, "W1", i, *W.cut(3))
    s = W.reach(3, False, 1, steps, (1, "W3", seat), key=("wagon", seat))
    sn = W.snap(s)
    me = T.seat_of(sn, seat)
    assert sn["phase"] == "W3" and W.zone(sn, seat, "woodpile") == {FW_DISK: 3}
    assert me["equipment"]["wagon"] == (1 if seat != 2 else 0)
    assert me["fodder"]["slot3"] is (seat != 1)
    return s


# --------------------------------------------------------------------------- R-049


@pytest.mark.parametrize("n", (2, 3, 4))
def test_R049_round_one_has_no_river_wood(n):
    """R-049: in round 1 there is no wood on any river, so no seat has a MOVE_WOOD choice in
    round 1's log-driving phase and every river is empty through round 1."""

    def rec(ctx: R.Ctx) -> int | None:
        if ctx.snap is not None and ctx.round == 1 and ctx.phase in ("W1", "W2", "W3"):
            assert all(not W.zone(ctx.snap, i, "river") for i in range(n))
            if ctx.phase == "W2":
                assert not W.ids(ctx.legal, W.MOVE_WOOD_IDS)
        return None

    R.drive({"players": n, "joinery": False}, seed=4, policy=rec, stop=lambda c: c.round == 2)


def test_R049_raft_wood_arrives_next_round_and_each_piece_chooses_sawing_or_sale():
    """R-049/R-053: two pieces placed on the river in round 1's transport arrive in round 2's
    log driving: legal moves are MOVE_WOOD(firewood, sawing) and MOVE_WOOD(firewood, sale) only
    (no DONE); the turn lasts until the river is empty; one piece goes to sawing, one to sale."""
    steps = _rafts(2)
    steps.add(
        1, "W3", 0, W.Opt(W.assign(0)), W.river_move(W.FW), W.river_move(W.FW), W.Opt(W.END_TRIP)
    )
    s = W.reach(3, False, 1, steps, (2, "W2", 0), key="arrival2")
    sn = W.snap(s)
    assert sn["round"] == 2 and sn["phase"] == "W2"
    assert W.zone(sn, 0, "river") == {FW_DISK: 2}
    legal = s.legal_actions()
    assert W.ids(legal, W.MOVE_WOOD_IDS) == [W.move_wood(W.FW, 0), W.move_wood(W.FW, 1)]
    assert H.DONE not in legal
    W.play(s, W.move_wood(W.FW, 0))
    assert s.current_player() == 0 and H.phase_of(s) == "W2"
    W.play(s, W.move_wood(W.FW, 1))
    after = W.snap(s)
    assert not W.zone(after, 0, "river")
    assert W.zone(after, 0, "sawing") == {FW_DISK: 1}
    assert W.zone(after, 0, "sale") == {FW_DISK: 1}


def test_R049_arriving_hardwood_disk_can_only_go_to_the_sawing_area():
    """R-049/R-046: a hardwood disk placed on the river in round 2 arrives in round 3 and may only
    be put in the sawing area."""
    seed, h = W.hardwood_round2_seed()
    steps = W.Steps().add(2, "PK", 0, H.PICK_AREA(h)).add(2, "PK", 1, W.pick_not(h))
    steps.add(1, "TR", 0, *W.tr_plan(2, False, seed, tokens=(("raft", 0),)))
    steps.add(
        2, "TR", 0, H.MOVE_TO(R.loc(False, "bearers")), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING
    )
    steps.add(2, "W1", 0, *W.cut(1, W.HW, src=1))
    steps.add(2, "W3", 0, W.Opt(W.assign(0)), W.river_move(W.HW), W.Opt(W.END_TRIP))
    s = W.reach(2, False, seed, steps, (3, "W2", 0))
    sn = W.snap(s)
    assert W.zone(sn, 0, "river") == {HW_DISK: 1}
    before = W.zone(sn, 0, "sawing")[HW_DISK]
    assert W.ids(s.legal_actions(), W.MOVE_WOOD_IDS) == [W.move_wood(W.HW, 0)]
    W.play(s, W.move_wood(W.HW, 0))
    after = W.snap(s)
    assert not W.zone(after, 0, "river")
    assert W.zone(after, 0, "sawing")[HW_DISK] == before + 1
    assert not W.zone(after, 0, "sale")


def test_R049_fall_year_one_river_wood_waits_through_winter_and_arrives_in_round_5():
    """R-049: wood placed on the river in round 3 (fall year 1) stays there through winter, which
    has no log driving, and arrives in round 5's log-driving phase."""
    steps = W.Steps().add(1, "TR", 0, *W.tr_plan(3, False, 1, tokens=(("raft", 0),)))
    steps.add(
        3, "TR", 0, H.MOVE_TO(R.loc(False, "bearers")), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING
    )
    steps.add(3, "W1", 0, *W.cut(1, W.FW, src=1))
    steps.add(3, "W3", 0, W.Opt(W.assign(0)), W.river_move(W.FW), W.Opt(W.END_TRIP))
    rivers: list[tuple[int, str, int]] = []

    def rec(ctx: R.Ctx) -> int | None:
        if ctx.snap is not None and ctx.round in (4, 5):
            rivers.append((ctx.round, ctx.phase, sum(W.zone(ctx.snap, 0, "river").values())))
        return None

    s = W.reach(3, False, 1, steps, (5, "W2", 0), extra=rec)
    assert W.zone(W.snap(s), 0, "river") == {FW_DISK: 1}
    assert rivers and all(c == 1 for _, _, c in rivers)
    assert any(r == 4 for r, _, _ in rivers)
    assert W.ids(s.legal_actions(), W.MOVE_WOOD_IDS) == [W.move_wood(W.FW, 0), W.move_wood(W.FW, 1)]


# --------------------------------------------------------------------------- R-050


def test_R050_wood_not_transported_stays_in_the_woodpile_into_the_next_round():
    """R-050/R-047: P0 cuts 3 pieces and moves none; they are still in the woodpile (unlimited,
    indefinite) at round 2's start."""
    steps = W.Steps().add(1, "TR", 0, *W.tr_plan(3, False, 1, woodcutters=3))
    steps.add(1, "W1", 0, *W.cut(3))
    s = W.reach(3, False, 1, steps, (2, "PK", 0))
    sn = W.snap(s)
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 3}
    assert not W.zone(sn, 0, "sawing") and not W.zone(sn, 0, "sale")


def test_R050_methods_combine_in_one_turn_and_each_worker_is_used_once():
    """R-050/R-053/R-051: P0 first sends one piece down the river with its bearer and a raft, then
    moves another to the sale area with the mill worker. The bearer cannot work twice; after
    the mill worker is used no worker remains. Result: river 1, sale 1, woodpile 1, raft spent."""
    s = _rafts_w3(1)
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW))
    if W.END_TRIP in s.legal_actions():
        W.play(s, W.END_TRIP)
    assert W.assign(0) not in s.legal_actions()
    W.assign_if_needed(s, 1)
    assert W.move_wood(W.FW, 1) in s.legal_actions()
    W.play(s, W.move_wood(W.FW, 1))
    legal = s.legal_actions()
    assert not W.ids(legal, W.MOVE_WOOD_IDS) and not W.ids(legal, W.RIVER_IDS)
    assert not W.ids(legal, W.ASSIGN_IDS)
    W.end_turn(s)
    sn = W.snap(s)
    assert W.zone(sn, 0, "river") == {FW_DISK: 1}
    assert W.zone(sn, 0, "sale") == {FW_DISK: 1}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 2 - 1}
    assert T.seat_of(sn, 0)["equipment"]["raft"] == 0
    assert T.seat_of(sn, 0)["mill_worker_used"] is True


def test_R050_destination_is_chosen_per_piece_and_is_final():
    """R-050/R-046: with 2 bearers and the mill worker P0 moves its 3 pieces one by one: sawing,
    sale, sawing. Each choice is made as the piece moves; result sawing 2, sale 1, woodpile 0."""
    steps = W.Steps()
    steps.add(1, "TR", 0, *W.tr_plan(3, False, 1, bearers=2, woodcutters=3))
    steps.add(1, "W1", 0, *W.cut(3))
    s = W.reach(3, False, 1, steps, (1, "W3", 0), key="two-bearers")
    seq = [(0, 0), (0, 1), (1, 0)]
    for src, dest in seq:
        W.assign_if_needed(s, src)
        legal = s.legal_actions()
        assert W.ids(legal, W.MOVE_WOOD_IDS) == [W.move_wood(W.FW, 0), W.move_wood(W.FW, 1)]
        W.play(s, W.move_wood(W.FW, dest))
    assert not W.ids(s.legal_actions(), W.MOVE_WOOD_IDS)
    W.end_turn(s)
    sn = W.snap(s)
    assert W.zone(sn, 0, "sawing") == {FW_DISK: 2}
    assert W.zone(sn, 0, "sale") == {FW_DISK: 1}
    assert not W.zone(sn, 0, "woodpile")


# --------------------------------------------------------------------------- R-051


def test_R051_each_bearer_moves_exactly_one_piece():
    """R-051: P0 has 1 bearer and 3 pieces in the woodpile, the mill worker already used in W1.
    The bearer moves one piece; no further MOVE_WOOD is legal although 2 pieces remain."""
    steps = W.Steps()
    steps.add(1, "TR", 0, *W.tr_plan(3, False, 1, bearers=1, woodcutters=2))
    steps.add(1, "W1", 0, *W.cut(2), *W.cut(1, W.FW, src=1))
    s = W.reach(3, False, 1, steps, (1, "W3", 0), key="one-bearer-mill-used")
    sn = W.snap(s)
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 3}
    assert T.seat_of(sn, 0)["mill_worker_used"] is True
    W.assign_if_needed(s, 0)
    assert W.move_wood(W.FW, 0) in s.legal_actions()
    W.play(s, W.move_wood(W.FW, 0))
    legal = s.legal_actions()
    assert not W.ids(legal, W.MOVE_WOOD_IDS) and not W.ids(legal, W.ASSIGN_IDS)
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 2}
    assert W.zone(after, 0, "sawing") == {FW_DISK: 1}


def test_R051_mill_worker_can_carry_one_piece_when_unused_and_then_nothing_more():
    """R-051/R-045: P0 has no bearer. With the mill worker unused (two woodcutters cut 2 pieces)
    it moves one piece to the sale area; afterwards nothing else may be moved this round."""
    steps = W.Steps()
    steps.add(1, "TR", 0, *W.tr_plan(3, False, 1, woodcutters=2))
    steps.add(1, "W1", 0, *W.cut(2))
    s = W.reach(3, False, 1, steps, (1, "W3", 0), key="mill-bearer")
    sn = W.snap(s)
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 2}
    assert T.seat_of(sn, 0)["mill_worker_used"] is False
    W.assign_if_needed(s, 1)
    assert W.ids(s.legal_actions(), W.MOVE_WOOD_IDS) == [W.move_wood(W.FW, 0), W.move_wood(W.FW, 1)]
    W.play(s, W.move_wood(W.FW, 1))
    assert not W.ids(s.legal_actions(), W.MOVE_WOOD_IDS)
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "sale") == {FW_DISK: 1}
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 1}
    assert T.seat_of(after, 0)["mill_worker_used"] is True


# --------------------------------------------------------------------------- R-052


def test_R052_wagon_trip_with_slot_3_fodder_moves_up_to_three_and_fodder_drops_to_slot_2():
    """R-052: P0 (wagon, fodder on slot 3, bearer) makes a wagon trip: no END_TRIP before the first
    piece; 3 pieces (2 to sawing, 1 to sale); the trip ends at the cap; the wagon token is
    spent and the fodder is now on slot 2."""
    s = _wagon_w3(0)
    W.assign_if_needed(s, 0)
    assert W.USE_WAGON in s.legal_actions()
    W.play(s, W.USE_WAGON)
    legal = s.legal_actions()
    assert W.ids(legal, W.MOVE_WOOD_IDS) == [W.move_wood(W.FW, 0), W.move_wood(W.FW, 1)]
    assert W.END_TRIP not in legal
    W.play(s, W.move_wood(W.FW, 0), W.move_wood(W.FW, 0))
    assert W.END_TRIP in s.legal_actions()
    W.play(s, W.move_wood(W.FW, 1))
    assert not W.ids(s.legal_actions(), W.MOVE_WOOD_IDS)
    W.end_turn(s)
    sn = W.snap(s)
    me = T.seat_of(sn, 0)
    assert me["equipment"]["wagon"] == 0
    assert me["fodder"] == {"slot3": False, "slot2": True}
    assert not W.zone(sn, 0, "woodpile")
    assert W.zone(sn, 0, "sawing") == {FW_DISK: 2} and W.zone(sn, 0, "sale") == {FW_DISK: 1}


def test_R052_trip_may_move_fewer_pieces_and_the_fodder_wears_down_all_the_same():
    """R-052 (O-U2-9): a trip of 1 piece ended with END_TRIP still spends the wagon and moves the
    fodder from slot 3 to slot 2; 2 pieces stay in the woodpile."""
    s = _wagon_w3(0)
    W.assign_if_needed(s, 0)
    W.play(s, W.USE_WAGON, W.move_wood(W.FW, 0))
    assert W.END_TRIP in s.legal_actions()
    W.play(s, W.END_TRIP)
    W.end_turn(s)
    sn = W.snap(s)
    me = T.seat_of(sn, 0)
    assert me["equipment"]["wagon"] == 0
    assert me["fodder"] == {"slot3": False, "slot2": True}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 2}
    assert W.zone(sn, 0, "sawing") == {FW_DISK: 1}


@pytest.mark.parametrize("seat", (1, 2))
def test_R052_wagon_trip_needs_wagon_and_fodder_together(seat):
    """R-052: P1 holds a wagon but no fodder, P2 holds fodder but no wagon; each has a bearer and
    3 pieces. USE_WAGON is not legal for either (before or after assigning the bearer)."""
    s = _wagon_w3(seat)
    assert W.USE_WAGON not in s.legal_actions()
    W.assign_if_needed(s, 0)
    legal = s.legal_actions()
    assert W.USE_WAGON not in legal
    assert W.move_wood(W.FW, 0) in legal


def test_R052_slot_2_fodder_is_used_first_so_the_trip_moves_at_most_two():
    """R-052 (C7): P0 holds fodder on both slots (slot 2 left from round 1's trip, slot 3 bought in
    round 2) and a second wagon. With 3 pieces in the woodpile the wagon trip moves only 2
    (slot-2 fodder first), is then over, and the fodder left is the one on slot 3."""
    steps = W.Steps()
    steps.add(
        1,
        "TR",
        0,
        *W.tr_plan(
            3,
            False,
            1,
            bearers=1,
            woodcutters=3,
            fodder=True,
            tokens=(("wagon", 0), ("wagon", 1)),
        ),
    )
    steps.add(1, "W1", 0, *W.cut(3))
    steps.add(1, "W3", 0, W.Opt(W.assign(0)), W.USE_WAGON, W.move_wood(W.FW, 0), W.END_TRIP)
    steps.add(2, "TR", 0, *W.tr_plan(3, False, 1, loans=1, fodder=True, woodcutters=1))
    for i in range(3):
        steps.add(2, "PK", i, W.rank_pick(i))
    steps.add(2, "W1", 0, *W.cut(1, -1))
    s = W.reach(3, False, 1, steps, (2, "W3", 0))
    sn = W.snap(s)
    me = T.seat_of(sn, 0)
    assert me["fodder"] == {"slot3": True, "slot2": True}
    assert me["equipment"]["wagon"] == 1
    assert sum(W.zone(sn, 0, "woodpile").values()) == 3
    assert me["mill_worker_used"] is False
    sawing_before = sum(W.zone(sn, 0, "sawing").values())
    W.assign_if_needed(s, 1)
    W.play(s, W.USE_WAGON, W.move_wood(W.FW, 0), W.move_wood(W.FW, 0))
    assert not W.ids(s.legal_actions(), W.MOVE_WOOD_IDS)
    W.end_turn(s)
    after = W.snap(s)
    assert T.seat_of(after, 0)["fodder"] == {"slot3": True, "slot2": False}
    assert T.seat_of(after, 0)["equipment"]["wagon"] == 0
    assert sum(W.zone(after, 0, "woodpile").values()) == 1
    assert sum(W.zone(after, 0, "sawing").values()) == sawing_before + 2


# --------------------------------------------------------------------------- R-053


def test_R053_one_bearer_and_two_rafts_put_two_pieces_on_the_river():
    """R-053: one bearer plus two raft tokens move two pieces to the river in one action; the rafts
    are spent at once; the bearer is used; no third river move is possible (not even by the mill
    worker, which has no raft left)."""
    s = _rafts_w3(2)
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW))
    assert W.river_move(W.FW) in s.legal_actions()
    W.play(s, W.river_move(W.FW))
    if W.END_TRIP in s.legal_actions():
        W.play(s, W.END_TRIP)
    W.assign_if_needed(s, 1)
    assert not W.ids(s.legal_actions(), W.RIVER_IDS)
    W.end_turn(s)
    sn = W.snap(s)
    assert W.zone(sn, 0, "river") == {FW_DISK: 2}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 1}
    assert T.seat_of(sn, 0)["equipment"]["raft"] == 0
    assert not W.zone(sn, 0, "sawing") and not W.zone(sn, 0, "sale")


def test_R053_each_raft_moves_one_piece_so_one_raft_allows_one_river_move():
    """R-053: with a single raft only one piece goes to the river; after it RIVER_MOVE is not legal
    for any worker and the other 2 pieces stay in the woodpile."""
    s = _rafts_w3(1)
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW))
    if W.END_TRIP in s.legal_actions():
        W.play(s, W.END_TRIP)
    W.assign_if_needed(s, 1)
    assert not W.ids(s.legal_actions(), W.RIVER_IDS)
    W.end_turn(s)
    sn = W.snap(s)
    assert W.zone(sn, 0, "river") == {FW_DISK: 1}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 2}
    assert T.seat_of(sn, 0)["equipment"]["raft"] == 0


def test_R053_river_move_needs_a_raft_token():
    """R-053: P1 has a bearer and 3 pieces but no raft: RIVER_MOVE is never legal."""
    s = _wagon_w3(1)
    assert not W.ids(s.legal_actions(), W.RIVER_IDS)
    W.assign_if_needed(s, 0)
    assert not W.ids(s.legal_actions(), W.RIVER_IDS)
    assert W.move_wood(W.FW, 0) in s.legal_actions()


def test_R053_river_wood_cannot_be_used_before_the_next_round():
    """R-053: wood placed on the river in round 1 is still on the river, untouched, at round 2's
    start; it has not reached the sawing or sale area and the rafts are back in the supply."""
    steps = _rafts(2)
    steps.add(
        1, "W3", 0, W.Opt(W.assign(0)), W.river_move(W.FW), W.river_move(W.FW), W.Opt(W.END_TRIP)
    )
    s = W.reach(3, False, 1, steps, (2, "PK", 0), key="river-r2-start")
    sn = W.snap(s)
    assert W.zone(sn, 0, "river") == {FW_DISK: 2}
    assert not W.zone(sn, 0, "sawing") and not W.zone(sn, 0, "sale")
    assert T.seat_of(sn, 0)["equipment"]["raft"] == 0


def test_R052_done_is_illegal_mid_trip_but_end_trip_is_legal():
    """R-052 (user decision 2026-11-05): once a wagon trip has moved a piece and not ended, DONE is
    not legal; END_TRIP is the only early exit."""
    s = _wagon_w3(0)
    W.assign_if_needed(s, 0)
    W.play(s, W.USE_WAGON, W.move_wood(W.FW, 0))
    legal = s.legal_actions()
    assert H.DONE not in legal
    assert W.END_TRIP in legal
    W.play(s, W.END_TRIP)
    assert not s.is_terminal()


def test_R050_done_is_legal_with_zero_pieces_moved():
    """R-050 (user decision 2026-11-05): a seat need not transport anything: DONE is legal at the
    turn start and after the worker is assigned, before any piece moves."""
    s = _wagon_w3(0)
    assert H.DONE in s.legal_actions()
    W.assign_if_needed(s, 0)
    assert H.DONE in s.legal_actions()


def test_R052_use_wagon_not_legal_when_no_piece_could_move():
    """R-052 (user decision 2026-11-05): P0 holds wagon + fodder and a bearer but an empty
    woodpile; USE_WAGON is not legal (it would leave a spent wagon and nothing to move)."""
    steps = W.Steps()
    steps.add(1, "TR", 0, *W.tr_plan(3, False, 1, bearers=1, tokens=(("wagon", 0),), fodder=True))
    s = W.reach(3, False, 1, steps, (1, "W3", 0))
    sn = W.snap(s)
    assert not W.zone(sn, 0, "woodpile")
    assert T.seat_of(sn, 0)["equipment"]["wagon"] == 1
    assert W.USE_WAGON not in s.legal_actions()
    W.assign_if_needed(s, 0)
    assert W.USE_WAGON not in s.legal_actions()


@pytest.mark.parametrize("seed", range(40))
def test_R052_a_started_wagon_trip_always_has_a_piece_to_move(seed):
    """R-052 (user decision 2026-11-05): random play; whenever USE_WAGON is offered a piece can be
    moved, and right after USE_WAGON the seat has a legal MOVE_WOOD (never stuck, no END_TRIP)."""
    rng = random.Random(seed)
    s = H.load_game(players=3).new_initial_state()
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        legal = s.legal_actions()
        if W.USE_WAGON in legal:
            assert W.ids(legal, W.MOVE_WOOD_IDS), legal
        a = rng.choice(legal)
        s.apply_action(a)
        if a == W.USE_WAGON:
            assert W.ids(s.legal_actions(), W.MOVE_WOOD_IDS)
            assert W.END_TRIP not in s.legal_actions()
