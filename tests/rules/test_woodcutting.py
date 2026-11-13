"""Phase 2 unit 7: woodcutting and shared cutting areas (R-047, R-048).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and
tests/support/{rounds,travel,woodwork}.py (public API only).

Conventions
  * Cutting areas are 0-based in action ids (area a = printed number - 1) and 1-based in dumps.
  * Round 1 gives every seat its own 3-firewood area (R-015, R-020), so no area is shared.
    Sharing needs the hidden picks of round 2 (R-038): there every seat picks the same, or a
    chosen, area through `Steps`.
  * `ASSIGN_WORKER` may be auto-inserted when only one source is legal (ACTIONS A4), so tests use
    `assign_if_needed`.
  * Snapshots exist only at turn boundaries; results are read at the next node.
"""

from __future__ import annotations

import functools
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

PLAYERS = (2, 3, 4)
BOOLS = (False, True)
FW_DISK = "firewood_disk"
KIND_NAMES = ("firewood", "softwood", "hardwood")


def _p0_round1(n: int, j: bool, woodcutters: int) -> Any:
    """Round 1, P0 hires `woodcutters` woodcutters and enters the clearing last; state at P0's
    W1 turn (all other seats did nothing)."""
    steps = W.Steps().add(1, "TR", 0, *W.tr_plan(n, j, 1, woodcutters=woodcutters))
    s = W.reach(n, j, 1, steps, (1, "W1", 0), key=("p0r1", n, j, woodcutters))
    sn = W.snap(s)
    assert sn["clearing_order"][-1] == 0 and s.current_player() == 0
    assert T.seat_of(sn, 0)["hired"]["woodcutters"] == woodcutters
    return s


def _own_area(s: Any) -> int:
    return int(T.seat_of(W.snap(s), 0)["cutting_area"]) - 1


# --------------------------------------------------------------------------- R-047


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R047_each_hired_woodcutter_takes_one_piece_into_the_woodpile(n, joinery):
    """R-047: each woodcutter takes 1 piece from the seat's own area into the woodpile (not to
    the sawmill zones, not food). With 2 woodcutters in a 3-firewood area: woodpile 2 firewood
    disks, area 1 left, mill worker unused. Only the own area is offered (no planned work)."""
    s = _p0_round1(n, joinery, 2)
    area = _own_area(s)
    sn = W.snap(s)
    assert W.area_wood(sn, area) == {"firewood": 3, "softwood": 0, "hardwood": 0}
    W.assign_if_needed(s, 0)
    assert W.ids(s.legal_actions(), W.TAKE_WOOD_IDS) == [W.take_wood(area, W.FW)]
    W.play(s, W.take_wood(area, W.FW))
    W.assign_if_needed(s, 0)
    assert W.ids(s.legal_actions(), W.TAKE_WOOD_IDS) == [W.take_wood(area, W.FW)]
    W.play(s, W.take_wood(area, W.FW))
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 2}
    assert not W.zone(after, 0, "sawing") and not W.zone(after, 0, "sale")
    assert W.area_wood(after, area)["firewood"] == 1
    assert T.seat_of(after, 0)["mill_worker_used"] is False


@pytest.mark.parametrize("n", PLAYERS)
def test_R047_mill_worker_may_cut_one_more_piece_and_is_then_used(n):
    """R-047 + R-045: two woodcutters plus the mill worker take 3 pieces and empty the 3-firewood
    area; the mill worker is then marked used for the round. No further TAKE_WOOD is legal."""
    s = _p0_round1(n, False, 2)
    area = _own_area(s)
    for src in (0, 0, 1):
        W.assign_if_needed(s, src)
        W.play(s, W.take_wood(area, W.FW))
    legal = s.legal_actions()
    assert not W.ids(legal, W.TAKE_WOOD_IDS) and not W.ids(legal, W.ASSIGN_IDS)
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 3}
    assert sum(W.area_wood(after, area).values()) == 0
    assert T.seat_of(after, 0)["mill_worker_used"] is True


def test_R047_workers_beyond_available_wood_take_nothing_and_stay_unused():
    """R-047: P0 has 3 woodcutters and the mill worker for a 3-piece area. After 3 pieces nobody
    can take anything, DONE is legal, and the unused mill worker stays unused (it is not
    consumed by an empty area)."""
    s = _p0_round1(3, False, 3)
    area = _own_area(s)
    for _ in range(3):
        W.assign_if_needed(s, 0)
        W.play(s, W.take_wood(area, W.FW))
    legal = s.legal_actions()
    assert not W.ids(legal, W.TAKE_WOOD_IDS)
    assert not W.ids(legal, W.ASSIGN_IDS)
    assert H.DONE in legal
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 3}
    assert T.seat_of(after, 0)["mill_worker_used"] is False


@pytest.mark.parametrize("n", PLAYERS)
def test_R047_seat_without_hired_workers_cuts_with_the_mill_worker_only_once(n):
    """R-047/R-045: with no hired woodcutter the mill worker alone takes one piece; afterwards no
    second piece is possible even though the area still holds 2."""
    steps = W.Steps()
    s = W.reach(n, False, 1, steps, (1, "W1", 0), key=("plain", n))
    area = _own_area(s)
    W.assign_if_needed(s, 1)
    W.play(s, W.take_wood(area, W.FW))
    assert not W.ids(s.legal_actions(), W.TAKE_WOOD_IDS)
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {FW_DISK: 1}
    assert W.area_wood(after, area)["firewood"] == 2


# --- round 2 areas with several kinds and food


@functools.cache
def _round2_area_seed(kind: str) -> tuple[int, int]:
    """(seed, 0-based area) of a 2-player game whose round-2 pick state has an area holding
    wood of two or more kinds (kind='mixed') or an odd positive amount of food (kind='food')."""
    for seed in range(150):
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            stop=lambda c: c.round == 2 and c.phase == "PK",
        )
        if not run.stopped:
            continue
        sn = W.snap(run.state)
        for a in range(6):
            w = W.area_wood(sn, a)
            if kind == "mixed" and sum(1 for v in w.values() if v) >= 2:
                return seed, a
            if kind == "food" and R.food(H.areas(sn)[a]) % 2 == 1:  # pyright: ignore[reportUnknownMemberType]
                return seed, a
    raise AssertionError(f"no seed for {kind}")


def test_R047_player_chooses_the_kind_among_those_present_in_the_area():
    """R-047: a worker takes 1 piece of any kind the player chooses from what is in the area. The
    legal TAKE_WOOD set is exactly the kinds present in the own area; taking one kind leaves the
    others and the rest of that kind untouched."""
    seed, m = _round2_area_seed("mixed")
    steps = W.Steps().add(2, "PK", 0, H.PICK_AREA(m)).add(2, "PK", 1, W.pick_not(m))
    s = W.reach(2, False, seed, steps, (2, "W1", 0))
    sn = W.snap(s)
    assert T.seat_of(sn, 0)["cutting_area"] == m + 1
    before = W.area_wood(sn, m)
    present = [k for k, name in enumerate(KIND_NAMES) if before[name]]
    assert len(present) >= 2
    W.assign_if_needed(s, 1)
    assert W.ids(s.legal_actions(), W.TAKE_WOOD_IDS) == [W.take_wood(m, k) for k in present]
    pick = present[-1]
    W.play(s, W.take_wood(m, pick))
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "woodpile") == {f"{KIND_NAMES[pick]}_disk": 1}
    expected = dict(before)
    expected[KIND_NAMES[pick]] -= 1
    assert W.area_wood(after, m) == expected


def test_R047_food_in_the_area_is_not_taken_during_woodcutting():
    """R-047/R-039: food in the area is not taken in W1. Two seats share an area with an odd
    amount of food (the remainder stays after the reveal, R-039); the first seat in clearing
    order cuts a piece, and neither the area's food nor either seat's food storage changes."""
    seed, m = _round2_area_seed("food")
    steps = W.Steps().add(2, "PK", 0, H.PICK_AREA(m)).add(2, "PK", 1, H.PICK_AREA(m))
    s = W.reach(2, False, seed, steps, (2, "W1", 1))
    sn = W.snap(s)
    food_area = R.food(H.areas(sn)[m])  # pyright: ignore[reportUnknownMemberType]
    assert food_area >= 1
    foods = [T.seat_of(sn, i)["food"] for i in (0, 1)]
    W.assign_if_needed(s, 1)
    W.play(s, W.take_wood(m, next(k for k, nm in enumerate(KIND_NAMES) if W.area_wood(sn, m)[nm])))
    W.end_turn(s)
    after = W.snap(s)
    assert R.food(H.areas(after)[m]) == food_area  # pyright: ignore[reportUnknownMemberType]
    assert [T.seat_of(after, i)["food"] for i in (0, 1)] == foods


# --------------------------------------------------------------------------- R-048


def _shared(n: int, picks: tuple[int, ...], steps_extra: W.Steps | None = None) -> Any:
    """Round 2; seat i picks the picks[i]-th ranked area; state at the first W1 turn. All other
    round-1/2 turns are the defaults (clearing at once, nothing cut), so the round-2 clearing
    order is the reverse of round 1's (R-060) unless `steps_extra` changes travel."""
    steps = steps_extra or W.Steps()
    for i, rk in enumerate(picks):
        steps.add(2, "PK", i, W.rank_pick(rk))
    first = n - 1
    s = W.reach(n, False, 1, steps, (2, "W1", first))
    sn = W.snap(s)
    assert sn["clearing_order"][0] == s.current_player()
    return s


def _other_areas(x: int, *more: int) -> list[int]:
    return [W.move_cut(a) for a in range(6) if a != x and a not in more]


@pytest.mark.parametrize("n", (2, 3, 4))
def test_R048_first_seat_in_clearing_order_has_no_move_option(n):
    """R-048: the first seat in clearing order cannot be displaced and has no MOVE_CUT_TOKEN, even
    when every other seat shares its area and there are free areas."""
    s = _shared(n, (0,) * n)
    sn = W.snap(s)
    x = T.seat_of(sn, s.current_player())["cutting_area"] - 1
    assert all(T.seat_of(sn, i)["cutting_area"] - 1 == x for i in range(n))
    assert not W.ids(s.legal_actions(), W.MOVE_CUT_IDS)


@pytest.mark.parametrize("n", (2, 3))
def test_R048_later_sharing_seat_may_cut_the_remainder_without_paying(n):
    """R-048(1): the first seat takes one piece; the second sharing seat is offered MOVE_CUT_TOKEN
    to every token-free area (all but the shared one) and also the remaining wood. Cutting the
    remainder costs nothing and the token stays."""
    s = _shared(n, (0,) * n)
    first = s.current_player()
    sn = W.snap(s)
    x = T.seat_of(sn, first)["cutting_area"] - 1
    total = W.area_total(sn, x)
    assert total >= 2
    W.assign_if_needed(s, 1)
    k1 = W.ids(s.legal_actions(), W.TAKE_WOOD_IDS)[0]
    W.play(s, k1)
    W.end_turn(s)
    second = s.current_player()
    assert second == sn["clearing_order"][1]
    before = W.snap(s)
    assert W.area_total(before, x) == total - 1
    money = T.seat_of(before, second)["money"]
    W.assign_if_needed(s, 1)
    legal = s.legal_actions()
    assert W.ids(legal, W.MOVE_CUT_IDS) == _other_areas(x)
    remaining = W.area_wood(before, x)
    assert W.ids(legal, W.TAKE_WOOD_IDS) == [
        W.take_wood(x, k) for k, nm in enumerate(KIND_NAMES) if remaining[nm]
    ]
    W.play(s, W.ids(legal, W.TAKE_WOOD_IDS)[0])
    W.end_turn(s)
    after = W.snap(s)
    assert T.seat_of(after, second)["money"] == money
    assert T.seat_of(after, second)["cutting_area"] == x + 1
    assert W.area_total(after, x) == total - 2
    assert sum(W.zone(after, second, "woodpile").values()) == 1


def test_R048_later_sharing_seat_pays_one_dollar_moves_and_cuts_there():
    """R-048(2): the second sharing seat pays $1, its token moves to a token-free area (which may
    hold any wood) and it cuts there; the shared area keeps what the first seat left."""
    s = _shared(2, (0, 0))
    first = s.current_player()
    sn = W.snap(s)
    x = T.seat_of(sn, first)["cutting_area"] - 1
    W.assign_if_needed(s, 1)
    W.play(s, W.ids(s.legal_actions(), W.TAKE_WOOD_IDS)[0])
    W.end_turn(s)
    second = s.current_player()
    mid = W.snap(s)
    total_x = W.area_total(mid, x)
    dest = max((a for a in range(6) if a != x), key=lambda a: (W.area_total(mid, a), -a))
    wood = W.area_wood(mid, dest)
    kind = next(k for k, nm in enumerate(KIND_NAMES) if wood[nm])
    money = T.seat_of(mid, second)["money"]
    W.play(s, W.move_cut(dest))
    W.assign_if_needed(s, 1)
    assert W.ids(s.legal_actions(), W.TAKE_WOOD_IDS) == [
        W.take_wood(dest, k) for k, nm in enumerate(KIND_NAMES) if wood[nm]
    ]
    W.play(s, W.take_wood(dest, kind))
    W.end_turn(s)
    after = W.snap(s)
    me = T.seat_of(after, second)
    assert me["money"] == money - 1
    assert me["cutting_area"] == dest + 1
    assert W.zone(after, second, "woodpile") == {f"{KIND_NAMES[kind]}_disk": 1}
    assert W.area_total(after, dest) == sum(wood.values()) - 1
    assert W.area_total(after, x) == total_x


def test_R048_moving_is_allowed_even_if_the_shared_area_still_has_wood_and_no_one_cut():
    """R-048 + O-U2-5: any later sharer may pay and move regardless of how much wood remains. The
    first seat does nothing (area untouched), yet the second may move; after the move the
    second seat's token is no longer on the shared area."""
    s = _shared(2, (0, 0))
    W.end_turn(s)
    second = s.current_player()
    sn = W.snap(s)
    x = T.seat_of(sn, second)["cutting_area"] - 1
    assert W.area_total(sn, x) >= 3
    legal = s.legal_actions()
    assert W.ids(legal, W.MOVE_CUT_IDS) == _other_areas(x)
    W.play(s, W.move_cut(5 if x != 5 else 4))
    W.end_turn(s)
    assert T.seat_of(W.snap(s), second)["cutting_area"] - 1 == (5 if x != 5 else 4)


def test_R048_destination_must_have_no_other_cutting_token():
    """R-048 example: three seats share area X. The second seat moves to area Z; the third seat
    (still on X with the first) may move only to an area with no token at all: not X and not Z
    (Z now holds the second seat's token)."""
    s = _shared(3, (0, 0, 0))
    sn = W.snap(s)
    x = T.seat_of(sn, s.current_player())["cutting_area"] - 1
    z = 5 if x != 5 else 4
    W.end_turn(s)
    assert W.ids(s.legal_actions(), W.MOVE_CUT_IDS) == _other_areas(x)
    W.play(s, W.move_cut(z))
    W.end_turn(s)
    assert W.ids(s.legal_actions(), W.MOVE_CUT_IDS) == _other_areas(x, z)


def test_R048_seat_alone_in_its_area_has_no_move_option_and_sharer_excludes_occupied_areas():
    """R-048: P0 and P1 pick X, P2 picks Y. Walking W1 in clearing order: the earlier of P0/P1 and
    P2 (alone) are offered no MOVE_CUT_TOKEN; the later of P0/P1 may move to the four areas that
    hold neither X's nor Y's token."""
    s = _shared(3, (0, 0, 1))
    sn = W.snap(s)
    x = T.seat_of(sn, 0)["cutting_area"] - 1
    y = T.seat_of(sn, 2)["cutting_area"] - 1
    assert T.seat_of(sn, 1)["cutting_area"] - 1 == x and x != y
    order = sn["clearing_order"]
    offered: dict[int, list[int]] = {}
    while H.phase_of(s) == "W1":
        offered[s.current_player()] = W.ids(s.legal_actions(), W.MOVE_CUT_IDS)
        W.end_turn(s)
    later = max((0, 1), key=order.index)
    earlier = 1 - later
    assert offered[earlier] == [] and offered[2] == []
    assert offered[later] == _other_areas(x, y)


def test_R048_seat_without_money_needs_a_loan_before_it_can_move():
    """R-048 + O-U2-10: the $1 comes from money on hand; a seat short of $1 takes a loan on its own
    turn first. P0 spends its $5 on 5 bearers in round 2's travel and is the second sharer
    ($0): MOVE_CUT_TOKEN is not legal, TAKE_LOAN is, and after the loan the move is legal and
    costs $1 (loan +$4 -> $3, 1 loan)."""
    steps = W.Steps().add(
        2,
        "TR",
        0,
        H.MOVE_TO(R.loc(False, "bearers")),
        *[R.HIRE_BEARER] * 5,
        H.DONE,
        R.MOVE_CLEARING,
    )
    s = _shared(2, (0, 0), steps)
    sn = W.snap(s)
    assert sn["clearing_order"] == [1, 0]
    assert T.seat_of(sn, 0)["money"] == 0
    W.end_turn(s)
    assert s.current_player() == 0
    x = T.seat_of(W.snap(s), 0)["cutting_area"] - 1
    legal = s.legal_actions()
    assert not W.ids(legal, W.MOVE_CUT_IDS)
    assert H.TAKE_LOAN in legal
    W.play(s, H.TAKE_LOAN)
    dest = 5 if x != 5 else 4
    assert W.move_cut(dest) in s.legal_actions()
    W.play(s, W.move_cut(dest))
    W.end_turn(s)
    me = T.seat_of(W.snap(s), 0)
    assert me["money"] == 3 and me["loans"] == 1 and me["cutting_area"] == dest + 1


def test_R048_earlier_seat_cannot_move_when_only_a_later_seat_shares_its_area():
    """R-048 (user decision 2026-11-05): a seat may move its token only if an earlier seat in
    clearing order is on its area. With P0 and P1 sharing and P2 alone, the first two seats in
    clearing order (P2, P1) have no move option; P0, the later sharer, has one."""
    s = _shared(3, (1, 1, 0))
    assert not W.ids(s.legal_actions(), W.MOVE_CUT_IDS)  # P2, first in clearing order
    W.play(s, H.DONE)
    assert s.current_player() == 1
    assert not W.ids(s.legal_actions(), W.MOVE_CUT_IDS)  # P1: only P0 (later) shares
    W.play(s, H.DONE)
    assert s.current_player() == 0
    assert W.ids(s.legal_actions(), W.MOVE_CUT_IDS)
