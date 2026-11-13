"""Phase 4 unit 10: Buildings A, Waterchannel, Marketstand, Storeroom, Small Workshop
(R-107, R-108, R-109, R-110; with R-053, R-093, R-098, R-104, R-105, R-100, R-095, R-071..R-074).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (5.7, 5.8, 5.10) and tests/harness.py only.

How a seat gets a building: the harness has no scenario loader, so states are reached by scripted
play (tests/support/bldscen.py, joinery=true) and the building is then handed over by assigning the
state's per-seat `held_buildings` tuple (indices into data/components/buildings.yaml) via
`bldscen.give`, the same white-box device the winter-payment tests use for `food`, `money`,
`store`. Acquisition through the Buildings location is covered by test_buildings_acquisition.py.

Ids: BUY_SAW 35, BUY_FOOD 36, SELL_FOOD 37, MOVE_TO(l) = 7 + l, joinery Market = 21, BUILD_HUT(v) =
134 + v, HUT_TOKEN(x) = 136 + x (board 0, shingle 1, stake 2, reed 3, joker 4), HUT_AREA(h) =
141 + h, RIVER_MOVE(k) = 201 + k, WC_MOVE(k, d) = 204 + 2k + d (k: firewood 0, softwood 1,
hardwood 2; d: 0 sawing area, 1 sale area), USE_PW_LOGDRIVING 212, END_TRIP 213.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from tests import harness as H
from tests.support import bldscen as B
from tests.support import pwscen as P
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import winter as V
from tests.support import woodwork as W

BUY_SAW, BUY_FOOD, SELL_FOOD = 35, 36, 37
MARKET = 21
LOAN = H.TAKE_LOAN
WC0, WC_END = 204, 209
RIVER_IDS = range(201, 204)
USE_PW_LD = 212
USE_WAGON = 210
END_TRIP = 213
BUILD_HUT0, BUILD_HUT_PW = 134, 135
HUT_IDS = range(134, 168)
REED, BOARD, SHINGLE, STAKE = 3, 0, 1, 2
FW_DISK = "firewood_disk"


def wc(k: int, d: int) -> int:
    return 204 + 2 * k + d


def hut_token(x: int) -> int:
    return 136 + x


def hut_area(h: int) -> int:
    return 141 + h


def _tup(t: tuple[Any, ...], i: int, v: Any) -> tuple[Any, ...]:
    return tuple(v if j == i else x for j, x in enumerate(t))


# =========================================================================== R-108 Marketstand


def _market(building: bool, food: int = 0) -> Any:
    """Round 1, P0 to move, optionally with the Marketstand and `food` pieces of food."""
    s = T.start(2, True)
    if building:
        B.give(s, 0, "marketstand")
    if food:
        s.food = _tup(s.food, 0, food)
    return s


def _enter_market(s: Any) -> None:
    T.play(s, H.MOVE_TO(MARKET))


def test_R108_marketstand_sells_food_one_dollar_each_any_number():
    """R-108: at the Market a seat with the Marketstand sells food at $1 per piece, any number
    (here 2 of 3, one by one), money rising and food falling by the same amounts."""
    s = _market(True, food=3)
    s.money = _tup(s.money, 0, 2)  # $2, food 3 (as after three buys; buy+sell mix is illegal)
    _enter_market(s)
    assert SELL_FOOD in s.legal_actions()
    T.play(s, SELL_FOOD, SELL_FOOD)
    T.play(s, H.DONE)
    sn = T.snap(s)
    a = T.seat_of(sn, 0)
    assert a["food"] == 1
    assert a["money"] == 2 + 2


def test_R108_marketstand_can_sell_all_food_then_no_more_sell_food():
    """R-108: food can be sold down to zero; with none left SELL_FOOD is no longer legal."""
    s = _market(True, food=3)
    _enter_market(s)
    legal = s.legal_actions()
    assert SELL_FOOD in legal
    T.play(s, SELL_FOOD, SELL_FOOD, SELL_FOOD)
    assert SELL_FOOD not in s.legal_actions()
    T.play(s, H.DONE)
    a = T.seat_of(T.snap(s), 0)
    assert a["food"] == 0 and a["money"] == 5 + 3


def test_R108_not_legal_without_the_marketstand():
    """R-108: the same seat and food without the building has no SELL_FOOD at the Market."""
    s = _market(False, food=3)
    _enter_market(s)
    assert SELL_FOOD not in s.legal_actions()


def test_R108_not_legal_with_marketstand_but_no_food():
    """R-108: holding the Marketstand with an empty food storage offers no SELL_FOOD."""
    s = _market(True, food=0)
    _enter_market(s)
    assert SELL_FOOD not in s.legal_actions()


def test_R108_not_legal_outside_the_market():
    """R-108/R-104: SELL_FOOD is a Market action only; at a travel node (food in storage, building
    held) it is not legal."""
    s = _market(True, food=3)
    assert SELL_FOOD not in s.legal_actions()


def test_R108_sale_proceeds_can_pay_a_purchase_in_the_same_visit():
    """R-104/R-108: money from sales may be used for purchases in the same visit. P0 has $0 and
    both loans used, sells 2 food ($2), then buys a saw ($1)."""
    s = _market(True, food=2)
    s.money = _tup(s.money, 0, 0)
    s.loans = _tup(s.loans, 0, 2)
    _enter_market(s)
    assert BUY_SAW not in s.legal_actions()  # no money, no loan left
    T.play(s, SELL_FOOD, SELL_FOOD)
    assert BUY_SAW in s.legal_actions()
    T.play(s, BUY_SAW, H.DONE)
    a = T.seat_of(T.snap(s), 0)
    assert a["food"] == 0 and a["money"] == 1 and a["equipment"]["saw"] == 1


def test_R108_marketstand_food_makes_a_broke_seat_able_to_enter_the_market():
    """R-104/R-040: with $0 and no loan left, a seat may enter the Market only if it can sell
    something: food with the Marketstand counts, food without it does not."""
    with_b = _market(True, food=2)
    without = _market(False, food=2)
    for s in (with_b, without):
        s.money = _tup(s.money, 0, 0)
        s.loans = _tup(s.loans, 0, 2)
    assert H.MOVE_TO(MARKET) in with_b.legal_actions()
    assert H.MOVE_TO(MARKET) not in without.legal_actions()


def test_R108_selling_touches_only_the_sellers_money_and_food():
    """R-108: money is conserved between seat and bank; the other seat is unchanged."""
    s = _market(True, food=3)
    before = T.snap(s)
    _enter_market(s)
    T.play(s, SELL_FOOD, SELL_FOOD, H.DONE)
    after = T.snap(s)  # P1 to move
    b1, a1 = T.seat_of(before, 1), T.seat_of(after, 1)
    assert (a1["money"], a1["food"]) == (b1["money"], b1["food"])
    a0 = T.seat_of(after, 0)
    assert a0["money"] == T.seat_of(before, 0)["money"] + 2
    assert a0["food"] == 1


# =========================================================================== R-109 Storeroom

STORE = "storeroom"


def _winter_state(
    building: bool, year: int = 1, **fields: tuple[Any, ...]
) -> tuple[Any, tuple[int, int]]:
    """State at the last N4 turn of winter `year` (round 4 or 8) with fields replaced."""
    rnd = 4 if year == 1 else 8
    if year == 1:
        _, base = V.first_winter(None, j=True)
        s = V.reach(None, (4, "N4", base["clearing_order"][-1]), j=True)
    else:
        run = R.drive(
            V.params(2, True), seed=V.SEED, policy=V.policy(None), stop=lambda c: c.round == 8
        )
        assert run.stopped
        base = R.try_snapshot(run.state)
        assert base is not None
        s = V.reach(None, (8, "N4", base["clearing_order"][-1]), j=True)
    assert rnd == (4 if year == 1 else 8)
    if building:
        B.give(s, 0, STORE)
    for name, value in fields.items():
        setattr(s, name, value)
    return s, V.requirement(base, year)


def _play_out(s: Any) -> None:
    """DONE (or first legal) until the next chance node (next round) or the end of the game."""
    s.apply_action(H.DONE)
    for _ in range(300):
        if s.is_chance_node() or s.is_terminal():
            return
        legal = s.legal_actions()
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("winter did not end")


def _covered(heat: int) -> dict[str, tuple[Any, ...]]:
    return {"store": ((heat, 0, 0), (0, 0, 0))}


@pytest.mark.parametrize("year", [1, 2])
def test_R109_storeroom_reduces_the_feeding_requirement_by_one(year):
    """R-109/R-071: with the Storeroom a seat holding (requirement - 1) food, $0 and no loan
    pays nothing and reaches no shortfall; without it the one missing food ($3) forces SF."""
    _, (food, heat) = _winter_state(True, year)
    kw = {**_covered(heat), "food": (food - 1, 0), "money": (0, 50), "loans": (0, 0)}
    with_b, _ = _winter_state(True, year, **kw)
    without, _ = _winter_state(False, year, **kw)
    with_b.apply_action(H.DONE)
    without.apply_action(H.DONE)
    assert not V.in_sf(with_b)
    assert V.in_sf(without)
    assert without.legal_actions() == [LOAN]


def test_R109_storeroom_charges_the_reduced_amount_in_money_when_short():
    """R-109/R-071: P0 with the Storeroom and 1 food less than (requirement - 1) misses exactly one
    food, i.e. owes $3 (not $6), paid from $20."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(True, food=(food - 2, 0), money=(20, 50), loans=(0, 0), **_covered(heat))
    _play_out(s)
    assert s.money[0] == 20 - 3 + 0
    assert s.loans[0] == 0


def test_R109_storeroom_and_joiner_net_out():
    """R-109/R-071: requirement 5 + 1 joiner - 1 Storeroom = 5. With exactly 5 food and a joiner
    P0 owes nothing; the joiner's next-spring income ($1, R-079) is the only change."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(
        True, joiners=(1, 0), food=(food, 0), money=(20, 50), loans=(0, 0), **_covered(heat)
    )
    _play_out(s)
    assert s.money[0] == 20 + 1
    assert s.food[0] == 0  # exactly the amount due was held: nothing left over


def test_R109_storeroom_keeps_surplus_food_after_the_first_winter():
    """R-109/R-074: 9 food, requirement 5 -> owes 4 with the Storeroom, keeps 5 for winter 2."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(True, food=(9, 0), money=(20, 50), **_covered(heat))
    _play_out(s)
    assert s.food[0] == 9 - (food - 1)
    assert s.money[0] == 20


def test_R109_storeroom_joiner_surplus_is_computed_after_both_adjustments():
    """R-109/R-071: with the Storeroom and 2 joiners owing requirement + 2 - 1, the kept surplus is
    food held minus that amount."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(True, joiners=(2, 0), food=(12, 0), money=(20, 50), **_covered(heat))
    _play_out(s)
    assert s.food[0] == 12 - (food + 2 - 1)


def test_R109_without_the_storeroom_surplus_food_is_returned():
    """R-071/R-074 baseline: the same board without the building leaves the food storage empty."""
    _, (food, heat) = _winter_state(False)
    s, _ = _winter_state(False, food=(9, 0), money=(20, 50), **_covered(heat))
    _play_out(s)
    assert s.food[0] == 0
    assert s.money[0] == 20


def test_R109_the_other_seat_without_the_building_does_not_keep_food():
    """R-109: the effect is per seat; P1 (no Storeroom) holding surplus loses it."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(True, food=(9, 9), money=(20, 50), store=((heat, 0, 0), (heat, 0, 0)))
    _play_out(s)
    assert s.food[0] == 9 - (food - 1)
    assert s.food[1] == 0


def test_R109_kept_food_is_still_there_in_winter_two():
    """R-109: food kept after winter 1 stays in the storage through rounds 5-7 and is on hand at
    the start of winter 2's phases."""
    _, (food, heat) = _winter_state(True)
    s, _ = _winter_state(True, food=(9, 0), money=(20, 50), **_covered(heat))
    kept = 9 - (food - 1)
    _play_out(s)
    s = P.advance(s, lambda sn, st: sn["round"] == 8 and sn["phase"] == "N4")
    assert T.seat_of(T.snap(s), 0)["food"] == kept


def test_R109_after_the_second_winter_surplus_is_not_kept():
    """R-109/R-074: with the Storeroom, surplus food after winter 2 is not kept: the storage is
    empty after feeding, as without the building."""
    _, (food, heat) = _winter_state(True, 2)
    s, _ = _winter_state(True, 2, food=(20, 0), money=(20, 50), **_covered(heat))
    _play_out(s)
    assert s.food[0] == 0


def test_R109_second_winter_kept_food_pays_that_winters_reduced_requirement():
    """R-109/R-071/R-074: winter 2 with the Storeroom: food kept from winter 1 (here set as the
    holding) plus the reduction covers the requirement; no shortfall and no money paid."""
    _, (food, heat) = _winter_state(True, 2)
    s, _ = _winter_state(True, 2, food=(food - 1, 0), money=(7, 50), loans=(0, 0), **_covered(heat))
    _play_out(s)
    assert s.money[0] == 7 and s.loans[0] == 0


# =========================================================================== R-107 Waterchannel
# Rig: 2 players, joinery, P0 collects 2 raft tokens in round 1, hires 1 bearer and 3 woodcutters,
# cuts its 3 firewood pieces, so at its round-1 W3 turn it holds 3 firewood disks in the woodpile,
# 2 rafts, 1 bearer and an unused mill worker.


def _rafts_steps() -> W.Steps:
    st = W.Steps()
    st.add(1, "W1", 0, *W.cut(3, -1, 0), W.Opt(W.assign(1)), _maybe_take)
    return st


def _maybe_take(state: Any) -> int | None:
    got = [a for a in state.legal_actions() if a in W.TAKE_WOOD_IDS]
    return got[0] if got else None


def _w3(building: bool, rafts: int = 2) -> Any:
    wants = {
        (1, 0): [("spots", ("raft",), rafts), ("hire", "bearers", 1), ("hire", "woodcutters", 3)]
    }

    def check(s: Any) -> bool:
        a = B.me(s)
        return (
            a["equipment"]["raft"] == rafts
            and a["hired"]["bearers"] == 1
            and sum(W.zone(B.snap(s), 0, "woodpile").values()) >= 3
        )

    s = B.reach(
        ("wc_w3", rafts),
        wants,
        _rafts_steps,
        ("node", 1, "W3", 0),
        check,
        [B.LOG, B.FOODS, B.HUT, B.TRADE],
    )
    if building:
        B.give(s, 0, "waterchannel")
    return s


def _wc_legal(s: Any) -> list[int]:
    return [a for a in s.legal_actions() if WC0 <= a <= WC_END]


def _river_trip(s: Any, *acts: int) -> None:
    W.assign_if_needed(s, 0)
    W.play(s, *acts)


def _boundary(s: Any) -> None:
    for _ in range(6):
        if R.try_snapshot(s) is not None:
            return
        s.apply_action(END_TRIP if END_TRIP in s.legal_actions() else H.DONE)
    raise AssertionError("no boundary")


def test_R107_waterchannel_offered_during_a_raft_trip():
    """R-107/ACTIONS 5.8: with the Waterchannel, after one raft placement the trip offers a
    WC_MOVE for a firewood disk (to sawing d=0 and to sale d=1)."""
    s = _w3(True)
    _river_trip(s, W.river_move(W.FW))
    assert wc(0, 0) in s.legal_actions() and wc(0, 1) in s.legal_actions()


def test_R107_not_legal_without_the_building():
    """R-107 baseline: the same trip without the building never offers any WC_MOVE."""
    s = _w3(False)
    _river_trip(s, W.river_move(W.FW))
    assert not _wc_legal(s)


@pytest.mark.parametrize("dest,zone", [(0, "sawing"), (1, "sale")])
def test_R107_piece_arrives_at_once_into_the_chosen_area(dest, zone):
    """R-107: one placed piece arrives at once at the sawmill, in the sawing area (d=0) or the sale
    area (d=1) by the seat's choice; the other piece stays on the river for next round."""
    s = _w3(True)
    _river_trip(s, W.river_move(W.FW), wc(0, dest))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    _boundary(s)
    sn = B.snap(s)
    assert W.zone(sn, 0, zone) == {FW_DISK: 1}
    assert W.zone(sn, 0, "river") == {FW_DISK: 1}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: 1}
    assert B.me(s)["equipment"]["raft"] == 0  # both rafts spent


def test_R107_only_one_waterchannel_piece_per_transport_phase():
    """R-107 (user answer 2026-11-04): regardless of the number of rafts, one piece per phase.
    After one WC_MOVE no further WC_MOVE is legal even with a raft left and pieces to move."""
    s = _w3(True, rafts=2)
    _river_trip(s, wc(0, 1))
    assert not _wc_legal(s)
    assert W.river_move(W.FW) in s.legal_actions()  # the second raft still places on the river


def test_R107_second_wc_move_illegal_even_in_a_second_trip_of_the_same_phase():
    """R-107: the limit is per transportation phase of the seat, not per trip: after a trip with a
    WC_MOVE ended, a second trip by the mill worker (raft left) offers no WC_MOVE."""
    s = _w3(True, rafts=2)
    # first trip: bearer, one raft, Waterchannel on that same placement
    W.assign_if_needed(s, 0)
    W.play(s, wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    if W.assign(1) in s.legal_actions():
        s.apply_action(W.assign(1))
        assert W.river_move(W.FW) in s.legal_actions()
        assert not _wc_legal(s)


def _hardwood_w3() -> Any:
    """Round 2 W3, P0 with 2 rafts, a bearer, a pile of firewood and one Overtime hardwood disk."""

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(2, "RS", 0, 133, W.Opt(H.DONE))
        st.add(2, "WS", 0, W.Opt(133), W.Opt(H.DONE))
        st.add(2, "W1", 0, *W.cut(3, W.FW, 0), W.Opt(W.assign(1)), _maybe_take)
        return st

    def check(s: Any) -> bool:
        pile = W.zone(B.snap(s), 0, "woodpile")
        return (
            B.me(s)["equipment"]["raft"] == 2
            and any("hardwood" in k for k in pile)
            and sum(pile.values()) >= 4
        )

    wants = {
        (1, 0): [("plan", B.OT, 1), ("spots", ("raft",), 2)],
        (2, 0): [("hire", "woodcutters", 3), ("hire", "bearers", 1)],
    }
    return B.reach(("hw_w3",), wants, steps, ("node", 2, "W3", 0), check, CARDS_OT)


CARDS_OT = [B.OT, B.FOODS, B.HUT, B.TRADE]


def test_R107_hardwood_disk_goes_to_sawing_but_never_to_the_sale_area():
    """R-107/R-046: with a hardwood disk in the woodpile (from Overtime), WC_MOVE of hardwood to the
    sawing area (d=0) is offered and to the sale area (d=1) is not, while firewood offers both."""
    s = _hardwood_w3()
    B.give(s, 0, "waterchannel")
    _river_trip(s, W.river_move(W.FW))
    legal = s.legal_actions()
    assert wc(0, 0) in legal and wc(0, 1) in legal
    assert wc(2, 0) in legal
    assert wc(2, 1) not in legal


def test_R107_hardwood_wc_move_lands_in_the_sawing_area():
    """R-107/R-046: a hardwood disk moved by the Waterchannel arrives at once in the sawing area."""
    s = _hardwood_w3()
    B.give(s, 0, "waterchannel")
    _river_trip(s, W.river_move(W.FW), wc(2, 0))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    _boundary(s)
    sawing = W.zone(B.snap(s), 0, "sawing")
    assert sum(v for k, v in sawing.items() if "hardwood" in k) == 1


def test_R107_the_remaining_river_piece_still_arrives_next_round():
    """R-107/R-049: the piece not moved by the Waterchannel stays on the river through round 1 and
    arrives in round 2's log driving (sawing or sale choice); the WC piece
    is not delivered twice."""
    s = _w3(True)
    _river_trip(s, W.river_move(W.FW), wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    s = P.advance(s, lambda sn, st: sn["round"] == 2 and sn["phase"] == "W2")
    sn = B.snap(s)
    if s.current_player() != 0:
        pytest.skip("seat 0 is not first in round 2's log driving")
    assert W.zone(sn, 0, "river") == {FW_DISK: 1}
    assert wc(0, 0) not in s.legal_actions()
    s.apply_action(W.move_wood(W.FW, 0))
    after = B.snap(s)
    assert not W.zone(after, 0, "river")
    assert W.zone(after, 0, "sale") == {FW_DISK: 1}


def test_R107_not_offered_on_a_bearer_or_wagon_trip():
    """R-107: the Waterchannel is for raft transport only; a bearer's MOVE_WOOD trip offers no
    WC_MOVE."""
    s = _w3(True)
    W.assign_if_needed(s, 0)
    W.play(s, W.move_wood(W.FW, 0))
    assert not _wc_legal(s)


def test_R107_no_rafts_and_a_bearer_assigned_offers_no_wc_move():
    """R-107 (raft transport only): a seat with the Waterchannel, no rafts and an assigned worker
    is offered no WC_MOVE, before or after assigning the bearer."""
    s = _w3(True, rafts=0)
    assert B.me(s)["equipment"]["raft"] == 0
    assert not _wc_legal(s)
    W.assign_if_needed(s, 0)
    assert not _wc_legal(s)


def _wagon_w3() -> Any:
    wants = {
        (1, 0): [
            ("spots", ("wagon",), 1),
            ("fodder",),
            ("hire", "bearers", 1),
            ("hire", "woodcutters", 3),
        ]
    }

    def check(s: Any) -> bool:
        a = B.me(s)
        return a["equipment"]["wagon"] == 1 and sum(W.zone(B.snap(s), 0, "woodpile").values()) >= 3

    return B.reach(
        ("wc_wagon",),
        wants,
        _rafts_steps,
        ("node", 1, "W3", 0),
        check,
        [B.LOG, B.FOODS, B.HUT, B.TRADE],
    )


def test_R107_not_offered_during_an_open_wagon_trip():
    """R-107: with the Waterchannel, an open wagon trip (USE_WAGON, one MOVE_WOOD done) offers no
    WC_MOVE; the wagon is for sawing/sale only."""
    s = _wagon_w3()
    B.give(s, 0, "waterchannel")
    W.assign_if_needed(s, 0)
    assert USE_WAGON in s.legal_actions()
    assert not _wc_legal(s)
    s.apply_action(USE_WAGON)
    assert not _wc_legal(s)
    s.apply_action(W.move_wood(W.FW, 0))
    assert not _wc_legal(s)


def _later_phase_w3() -> Any:
    """Round 1 W3 with 2 rafts and PW Log Driving planned for round 2; P0 has a bearer."""
    wants = {
        (1, 0): [
            ("plan", B.LOG, 1),
            ("spots", ("raft",), 2),
            ("hire", "bearers", 1),
            ("hire", "woodcutters", 3),
        ]
    }

    def check(s: Any) -> bool:
        a = B.me(s)
        return a["equipment"]["raft"] == 2 and sum(W.zone(B.snap(s), 0, "woodpile").values()) >= 3

    return B.reach(("wc_reset",), wants, _rafts_steps, ("node", 1, "W3", 0), check, CARDS)


def test_R107_once_per_phase_resets_in_the_next_rounds_transport_phase():
    """R-107: the one-piece limit is per transportation phase: after a WC_MOVE in round 1's W3, the
    Waterchannel is offered again in round 2's W3 (here on a PW Log Driving trip)."""
    s = _later_phase_w3()
    B.give(s, 0, "waterchannel")
    _river_trip(s, W.river_move(W.FW), wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    s = P.advance(
        s, lambda sn, st: sn["round"] == 2 and sn["phase"] == "W3" and st.current_player() == 0
    )
    assert USE_PW_LD in s.legal_actions()
    s.apply_action(USE_PW_LD)
    assert wc(0, 0) in s.legal_actions() and wc(0, 1) in s.legal_actions()


def _two_seat_w3() -> Any:
    wants = {
        (1, 0): [("spots", ("raft",), 1), ("hire", "bearers", 1), ("hire", "woodcutters", 1)],
        (1, 1): [("spots", ("raft",), 1), ("hire", "bearers", 1), ("hire", "woodcutters", 1)],
    }

    def steps() -> W.Steps:
        st = W.Steps()
        for seat in (0, 1):
            st.add(1, "W1", seat, *W.cut(1, -1, 0), W.Opt(W.assign(1)), _maybe_take)
        return st

    def check(s: Any) -> bool:
        return all(
            B.me(s, i)["equipment"]["raft"] == 1
            and B.me(s, i)["hired"]["bearers"] == 1
            and sum(W.zone(B.snap(s), i, "woodpile").values()) >= 1
            for i in (0, 1)
        )

    return B.reach(("wc_two",), wants, steps, ("node", 1, "W3", 0), check, CARDS)


def test_R107_two_seats_each_use_their_own_waterchannel_in_the_same_phase():
    """R-107: the limit is per seat: both seats own a Waterchannel and each gets its one WC_MOVE in
    the same round's transportation phase."""
    s = _two_seat_w3()
    B.give(s, 0, "waterchannel")
    B.give(s, 1, "waterchannel")
    W.assign_if_needed(s, 0)
    assert _wc_legal(s)
    acts = _wc_legal(s)
    W.play(s, acts[-1])
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    while s.current_player() == 0 and H.DONE in s.legal_actions():
        s.apply_action(H.DONE)
    assert s.current_player() == 1 and H.phase_of(s) == "W3"  # pyright: ignore[reportUnknownMemberType]
    W.assign_if_needed(s, 0)
    assert _wc_legal(s)


# ------------------------------------------------------- R-107 with PW Log Driving and Food Supply
# Rig: P0 plans Log Driving (and optionally Food Supply) in round 1, pair 1 -> target round 2;
# collects `rafts` raft tokens; in round 2 hires 3 woodcutters (and a bearer if rafts) and cuts.

CARDS = [B.LOG, B.FOODS, B.HUT, B.TRADE]


def _rounds2_steps() -> W.Steps:
    st = W.Steps()
    st.add(2, "W1", 0, *W.cut(3, -1, 0), W.Opt(W.assign(1)), _maybe_take)
    return st


def _w3_round2(key: str, plans: list[tuple[int, int]], rafts: int) -> Any:
    r1: list[Any] = [("plan", c, pair) for c, pair in plans]
    r2: list[Any] = [("hire", "woodcutters", 3)]
    if rafts:
        r1.append(("spots", ("raft",), rafts))
        r2.append(("hire", "bearers", 1))
    wants = {(1, 0): r1, (2, 0): r2}

    def check(s: Any) -> bool:
        a = B.me(s)
        return (
            a["equipment"]["raft"] == rafts and sum(W.zone(B.snap(s), 0, "woodpile").values()) >= 3
        )

    return B.reach(("w3r2", key), wants, _rounds2_steps, ("node", 2, "W3", 0), check, CARDS)


def test_R107_waterchannel_after_pw_log_driving_placement():
    """R-107/R-098: PW Log Driving (no raft) counts as raft transport: after one RIVER_MOVE of the
    PW trip the Waterchannel offers WC_MOVE; without the building it never does."""
    with_b = _w3_round2("ld", [(B.LOG, 1)], 0)
    B.give(with_b, 0, "waterchannel")
    without = _w3_round2("ld", [(B.LOG, 1)], 0)
    for s in (with_b, without):
        assert USE_PW_LD in s.legal_actions()
        s.apply_action(USE_PW_LD)
        s.apply_action(W.river_move(W.FW))
    assert wc(0, 0) in with_b.legal_actions() and wc(0, 1) in with_b.legal_actions()
    assert not _wc_legal(without)


def test_R107_pw_log_driving_wc_piece_arrives_at_once():
    """R-107/R-098: a PW Log Driving trip of two placements, one by WC_MOVE to the sale area: one
    piece sits in the sale area, one on the river, the rest of the woodpile is untouched, and no
    raft was needed."""
    s = _w3_round2("ld", [(B.LOG, 1)], 0)
    B.give(s, 0, "waterchannel")
    start = W.zone(B.snap(s), 0, "woodpile")[FW_DISK]
    s.apply_action(USE_PW_LD)
    s.apply_action(W.river_move(W.FW))
    s.apply_action(wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    _boundary(s)
    sn = B.snap(s)
    assert W.zone(sn, 0, "sale") == {FW_DISK: 1}
    assert W.zone(sn, 0, "river") == {FW_DISK: 1}
    assert W.zone(sn, 0, "woodpile") == {FW_DISK: start - 2}


def test_R107_one_piece_per_phase_across_a_raft_trip_and_a_pw_log_driving_trip():
    """R-107 (user answer 2026-11-04): a raft trip with a WC_MOVE followed by a PW Log Driving trip
    in the same transport phase gives no second Waterchannel piece."""
    s = _w3_round2("ld_raft", [(B.LOG, 1)], 2)
    B.give(s, 0, "waterchannel")
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW), wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    assert USE_PW_LD in s.legal_actions()
    s.apply_action(USE_PW_LD)
    s.apply_action(W.river_move(W.FW))
    assert not _wc_legal(s)


def test_R107_pw_log_driving_then_raft_trip_gives_one_piece_in_total():
    """R-107: the same limit in the other order: WC_MOVE used in the PW trip leaves none for a
    later raft trip of the same phase."""
    s = _w3_round2("ld_raft", [(B.LOG, 1)], 2)
    B.give(s, 0, "waterchannel")
    s.apply_action(USE_PW_LD)
    s.apply_action(W.river_move(W.FW))
    s.apply_action(wc(0, 0))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    W.assign_if_needed(s, 0)
    assert W.river_move(W.FW) in s.legal_actions()
    s.apply_action(W.river_move(W.FW))
    assert not _wc_legal(s)


def test_R107_waterchannel_piece_counts_for_pw_food_supply():
    """R-107/R-093: with Food Supply in its target round (2 food per river placement), a trip with
    one RIVER_MOVE and one WC_MOVE pays 2 food for each, 4 in total (the WC piece is a river
    placement)."""
    s = _w3_round2("food", [(B.FOODS, 1)], 2)
    B.give(s, 0, "waterchannel")
    food0 = B.me(s)["food"]
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW), wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    _boundary(s)
    assert B.me(s)["food"] == food0 + 4


def test_R107_no_food_supply_plan_no_food_from_the_waterchannel_piece():
    """R-093/R-107 baseline: without the Food Supply plan the same trip gives no food."""
    s = _w3_round2("nofood", [(B.LOG, 1)], 2)
    B.give(s, 0, "waterchannel")
    food0 = B.me(s)["food"]
    W.assign_if_needed(s, 0)
    W.play(s, W.river_move(W.FW), wc(0, 1))
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    _boundary(s)
    assert B.me(s)["food"] == food0


# =========================================================================== R-110 Small Workshop

WORKSHOP = "small_workshop"
TYPES = ("board", "shingle", "stake", "reed", "joker")


def _craft(s: Any, i: int = 0) -> Counter[str]:
    c = B.me(s, i)["craftwork"]
    return Counter({k: c.get(k, 0) for k in TYPES if c.get(k, 0)})


def _huts(s: Any, i: int = 0) -> dict[str, int]:
    h = B.me(s, i).get("huts") or {}
    return {k: h.get(k, 0) for k in ("drying", "food", "worker")}


def _holding(
    key: str,
    kinds: list[str],
    plans: list[tuple[int, int]] | None = None,
    rnd: int = 1,
    collect_rounds: int = 1,
) -> Any:
    """State at P0's travel node of round `rnd` (after its scripted collection) holding exactly the
    craftwork `kinds`, collected on the path of rounds 1..collect_rounds (nothing else bought);
    plans are made in round 1."""
    want = Counter(kinds)
    r1: list[Any] = [("plan", c, pair) for c, pair in (plans or [])] + [("tryp", kinds)]
    wants: dict[tuple[int, int], list[Any]] = {(1, 0): r1}
    for r in range(2, max(rnd, collect_rounds) + 1):
        wants[(r, 0)] = [("tryp", kinds)] if r <= collect_rounds else []

    def check(s: Any) -> bool:
        return _craft(s) == want

    stop = rnd if rnd >= collect_rounds else collect_rounds
    return B.reach(("hold", key), wants, W.Steps, ("tr", stop, 0), check, CARDS, max_seeds=1500)


def _legal_hut(s: Any) -> list[int]:
    return [a for a in s.legal_actions() if a in HUT_IDS]


def _finish(s: Any) -> None:
    """Leave the travel node (clearing) and run to the next turn-boundary snapshot."""
    s.apply_action(R.MOVE_CLEARING)
    for _ in range(40):
        if not s.is_chance_node() and R.try_snapshot(s) is not None:
            return
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        else:
            s.apply_action(s.legal_actions()[0])
    raise AssertionError("no boundary")


def test_R110_reed_replaces_the_shingle_with_the_workshop():
    """R-110/R-100: board + stake + reed (no shingle) with the Small Workshop: BUILD_HUT(0) is
    legal, HUT_TOKEN(reed) is offered, and the build consumes the reed and gives 3 huts."""
    s = _holding("bsr", ["board", "stake", "reed"])
    B.give(s, 0, WORKSHOP)
    assert BUILD_HUT0 in s.legal_actions()
    s.apply_action(BUILD_HUT0)
    assert hut_token(REED) in s.legal_actions()
    T.play(s, hut_token(BOARD), hut_token(REED), hut_token(STAKE))
    T.play(s, hut_area(0), hut_area(1), hut_area(2))
    _finish(s)
    assert sum(_craft(s).values()) == 0
    assert sum(_huts(s).values()) == 3


def test_R110_without_the_workshop_reed_never_builds_a_hut():
    """R-100/R-110 baseline: the same holding without the building offers no BUILD_HUT."""
    s = _holding("bsr", ["board", "stake", "reed"])
    assert BUILD_HUT0 not in s.legal_actions()


def test_R110_reed_cannot_replace_the_stake_or_the_board():
    """R-110: only the shingle may be replaced: board + shingle + reed (no stake) and
    shingle + stake + reed (no board) are not buildable even with the Workshop."""
    for kinds in (["board", "shingle", "reed"], ["shingle", "stake", "reed"]):
        s = _holding("no_" + "_".join(kinds), kinds)
        B.give(s, 0, WORKSHOP)
        assert BUILD_HUT0 not in s.legal_actions(), kinds


def test_R110_at_most_one_reed_per_hut():
    """R-110 ('one reed bundle'): board + reed + reed has no stake and two reeds cannot fill two
    slots, so no build; board + stake + reed + reed builds with only one reed, leaving the other."""
    s = _holding("brr", ["board", "reed", "reed"])
    B.give(s, 0, WORKSHOP)
    assert BUILD_HUT0 not in s.legal_actions()
    s = _holding("bsrr", ["board", "stake", "reed", "reed"], rnd=2, collect_rounds=2)
    B.give(s, 0, WORKSHOP)
    assert BUILD_HUT0 in s.legal_actions()
    s.apply_action(BUILD_HUT0)
    T.play(s, hut_token(BOARD), hut_token(REED), hut_token(STAKE))
    T.play(s, hut_area(0), hut_area(1), hut_area(2))
    _finish(s)
    assert _craft(s) == Counter(reed=1)


def test_R110_a_real_shingle_still_builds_and_reed_can_be_kept():
    """R-100/R-110: with board, shingle, stake and a reed, the workshop owner can build with the
    real shingle and keep the reed (HUT_TOKEN(shingle) is legal)."""
    s = _holding("bssr", ["board", "shingle", "stake", "reed"], rnd=2, collect_rounds=2)
    B.give(s, 0, WORKSHOP)
    s.apply_action(BUILD_HUT0)
    assert hut_token(SHINGLE) in s.legal_actions()
    T.play(s, hut_token(BOARD), hut_token(SHINGLE), hut_token(STAKE))
    T.play(s, hut_area(0), hut_area(1), hut_area(2))
    _finish(s)
    assert _craft(s) == Counter(reed=1)


def test_R110_pw_hut_construction_accepts_one_reed_as_a_shingle():
    """R-095/R-110: PW Hut Construction in its target round with the Workshop: reed + board are a
    valid pair (reed as the shingle): BUILD_HUT(1) legal, 2 tokens flipped."""
    s = _holding("pw_rb", ["reed", "board"], plans=[(B.HUT, 1)], rnd=2)
    B.give(s, 0, WORKSHOP)
    assert BUILD_HUT_PW in s.legal_actions()
    s.apply_action(BUILD_HUT_PW)
    assert hut_token(REED) in s.legal_actions()
    T.play(s, hut_token(BOARD), hut_token(REED), hut_area(0), hut_area(1))
    _finish(s)
    assert sum(_craft(s).values()) == 0
    assert sum(_huts(s).values()) == 2


def test_R110_pw_hut_construction_without_the_workshop_rejects_reed():
    """R-095: reed bundles are excluded from the PW build without the Workshop."""
    s = _holding("pw_rb", ["reed", "board"], plans=[(B.HUT, 1)], rnd=2)
    assert BUILD_HUT_PW not in s.legal_actions()


def test_R110_pw_hut_construction_never_takes_two_reeds():
    """R-095/R-110: at most one reed even with the Workshop: reed + reed is not a valid PW pair."""
    s = _holding("pw_rr", ["reed", "reed"], plans=[(B.HUT, 1)], rnd=2)
    B.give(s, 0, WORKSHOP)
    assert BUILD_HUT_PW not in s.legal_actions()


@pytest.mark.parametrize("workshop", [False, True])
def test_R110_reed_still_sells_as_a_set_at_the_market(workshop):
    """R-105/R-110: reed bundles sell as a set ($2 for two) at the Market with or without the
    Workshop (the building adds a hut use, it does not take the selling use away)."""
    s = _holding("rr", ["reed", "reed"])
    if workshop:
        B.give(s, 0, WORKSHOP)
    s.apply_action(H.MOVE_TO(MARKET))
    sets = [a for a in s.legal_actions() if 97 <= a <= 129]
    assert sets, "a pair of reed bundles is a sellable set"
    money0 = B.me(_holding("rr", ["reed", "reed"]))["money"]
    s.apply_action(sets[0])
    s.apply_action(H.DONE)
    sn = B.snap(s)
    p0 = T.seat_of(sn, 0)
    assert p0["money"] == money0 + 2
    assert not p0["craftwork"].get("reed", 0)
