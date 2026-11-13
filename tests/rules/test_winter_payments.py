"""Phase 2 unit 10: winter feeding, heating and the money shortfall (R-071, R-072, R-073).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (section 5.10) and docs/SCENARIOS.md only.

Notes
  * Feeding (N5) and heating (N6) are automatic; only the shortfall (SF) asks for decisions.
    Results are read at round 5's first node; shortfall legality is read with
    `winter.to_shortfall`, which plays round 4 up to the first SF node of a seat (mid-turn: no
    snapshot, only `legal_actions`).
  * `winter.settle` is an independent reference model of the three rules. It follows the test
    policy of `rounds.default_action` (DONE if legal, else the lowest legal id: TAKE_LOAN first,
    then the lowest SELL id).
  * Year 1 food is scarce in Phase 2 (no Market, no Storeroom): a seat can hold at most the 2 path
    food tokens plus cutting-area food, so surplus food, a year-2 winter and the Storeroom cannot
    be reached without a scenario loader (reported as a harness gap).
  * Seed 1, 2 players: year-1 card winter_1_4 top, food 5 / heating 4 (asserted where relied on).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as M
from tests.support import winter as V
from tests.support import woodwork as W

PLAYERS = (2, 3, 4)
SELL_FW_LOG = M.sell(0, M.FW_LOG)


def _solvent(j: bool = False) -> W.Steps:
    """P0: 2 loans, 2 food tokens, 4 firewood logs in the firewood storage."""
    return V.fall_steps(
        j,
        loans=2,
        food_tokens=2,
        saw=True,
        sawyer=True,
        bearers=1,
        carries=(0,),
        sawing=((0, 0, 4),),
    )


VARIANTS: dict[str, Any] = {
    "zero": lambda j: None,
    "solvent": _solvent,
    "food_only": lambda j: V.fall_steps(j, food_tokens=2),
    "split": lambda j: V.fall_steps(
        j, saw=True, sawyer=True, bearers=1, carries=(0,), sawing=((0, 0, 2),)
    ),
    "sale_logs": lambda j: V.fall_steps(
        j, saw=True, sawyer=True, bearers=1, carries=(0,), sawing=((0, 0, 0),), food_tokens=2
    ),
    "sawing_disk": lambda j: V.fall_steps(j, saw=True, bearers=1, task=M.TASK, carries=(0,)),
    "drying": lambda j: V.fall_steps(
        j, loans=2, food_tokens=2, saw=True, sawyer=True, bearers=1, carries=(0,),
        sawing=((0, 0, 2),), dry_round2=2,
    ),
    "overshoot": lambda j: V.fall_steps(
        j, food_tokens=2, saw=True, sawyer=True, bearers=1, carries=(0,), sawing=((0, 0, 4),)
    ),
    "joiner": lambda j: V.fall_steps(j, loans=2, food_tokens=2, joiner=True),
}  # fmt: skip


def _income(sn: dict[str, Any], seat: int) -> int:
    return int(V.seat(sn, seat).get("joiners", 0))


# --------------------------------------------------------------------------- end to end


@pytest.mark.parametrize(
    ("name", "joinery"),
    [(k, False) for k in VARIANTS if k != "joiner"] + [("joiner", True), ("solvent", True)],
)
def test_R073_winter_settlement_matches_the_reference_model(name, joinery):
    """R-071/R-072/R-073: every seat is fed (food short costs $3 each, joiners add 1 food), then
    heated from its firewood storage cheapest kind first, with shortfalls resolved loans first,
    then selling, then forgiveness. Compared field by field with the reference model for each
    seat: money (plus joiner income at spring start, R-079), loans, food (always 0 afterwards)
    and the six sellable/stored wood zones."""
    steps = VARIANTS[name](joinery)
    run = V.winter_run(steps, j=joinery)
    start, end = run.event(4).after, run.event(5).after
    req = V.requirement(start, 1)
    for i in range(2):
        a = V.seat(start, i)
        want = V.settle(a, req, joiners=_income(start, i))
        b = V.seat(end, i)
        assert b["money"] == want["money"] + _income(start, i), (name, i)
        assert b["loans"] == want["loans"], (name, i)
        assert b["food"] == 0, (name, i)
        assert V.zones_equal(b, want["zones"]), (name, i)


@pytest.mark.parametrize("n", (3, 4))
def test_R073_winter_settlement_with_more_players(n):
    """R-071..R-073: the same reference model holds for 3 and 4 players (no scaling, R-070)."""
    run = V.winter_run(None, n=n)
    start, end = run.event(4).after, run.event(5).after
    req = V.requirement(start, 1)
    for i in range(n):
        want = V.settle(V.seat(start, i), req)
        b = V.seat(end, i)
        assert (b["money"], b["loans"], b["food"]) == (want["money"], want["loans"], 0), i


# --------------------------------------------------------------------------- R-071


@pytest.mark.parametrize("n", (2, 3))
def test_R071_feeding_runs_in_fall_clearing_order(n):
    """R-071: each seat in clearing order pays for feeding. P0 enters the clearing last in fall,
    so the fall clearing order is P1.. then P0; with nobody holding enough food, the first
    shortfall node after the last N4 turn belongs to the first seat of that order, and loans come
    first (only TAKE_LOAN is legal)."""
    late = R.Script({(3, 0): [R.move(False, "bearers"), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING]})
    _, base = V.first_winter(late, n=n)  # type: ignore[arg-type]
    order = base["clearing_order"]
    assert order[-1] == 0 and order[0] != 0
    s = V.reach(late, (4, "N4", order[-1]), n=n)  # type: ignore[arg-type]
    s.apply_action(H.DONE)
    assert V.in_sf(s) and s.current_player() == order[0]
    assert s.legal_actions() == [H.TAKE_LOAN]


def test_R071_missing_food_is_paid_in_money_after_loans():
    """R-071: with less food than due the seat pays $3 per missing food. P0 holds 2 food (the two
    path tokens) and money 5; with the visible half's food 5 it misses 3 and owes $9: money 5 is
    short, so the only legal action is TAKE_LOAN (loans first); one loan ($9) covers it, after
    which DONE is legal."""
    s = V.to_shortfall(VARIANTS["food_only"](False), seat=0)
    start = V.first_winter(VARIANTS["food_only"](False))[1]
    f, _ = V.requirement(start, 1)
    a = V.seat(start, 0)
    due = 3 * (f - a["food"])
    assert a["food"] == 2 and due == 9 and a["money"] == 5
    assert s.legal_actions() == [H.TAKE_LOAN]
    s.apply_action(H.TAKE_LOAN)
    assert H.DONE in s.legal_actions()


def test_R071_food_storage_is_empty_after_feeding_and_other_holdings_stay():
    """R-071: after feeding all food left is returned to the supply (food storage empty, spec: a
    surplus cannot be kept); equipment and craftwork are unaffected."""
    run = V.winter_run(VARIANTS["sawing_disk"](False))
    start, end = run.event(4).after, run.event(5).after
    for i in range(2):
        a, b = V.seat(start, i), V.seat(end, i)
        assert b["food"] == 0
        assert b["equipment"] == a["equipment"]
        assert b["craftwork"] == a["craftwork"]
    assert V.seat(start, 0)["equipment"]["saw"] == 1


def test_R071_each_joiner_adds_one_food_due():
    """R-071: +1 food due per joiner (joinery=true). P0 has 1 joiner, 2 food and 2 loans (money
    13): it misses (food requirement + 1 - 2) food. Round 5 shows the money after paying that
    amount, then heating (storage empty) and the joiner's income."""
    run = V.winter_run(VARIANTS["joiner"](True), j=True)
    start, end = run.event(4).after, run.event(5).after
    a = V.seat(start, 0)
    assert a["joiners"] == 1 and a["food"] == 2 and a["loans"] == 2
    f, h = V.requirement(start, 1)
    want = V.settle(a, (f, h), joiners=1)
    assert V.seat(end, 0)["money"] == want["money"] + 1
    # without the joiner the food part would cost $3 less
    no_joiner = V.settle({**a, "joiners": 0}, (f, h), joiners=0)
    assert want["money"] <= no_joiner["money"]


# --------------------------------------------------------------------------- R-072


def test_R072_heating_pays_milled_pieces_from_storage_and_keeps_surplus():
    """R-072: the heating requirement is paid in milled pieces from the firewood storage; pieces
    return to the supply; the rest stays for next winter. P0 (solvent: food paid with loan money)
    holds 4 firewood logs and the card needs 4: storage empty, no further money lost."""
    run = V.winter_run(_solvent())
    start, end = run.event(4).after, run.event(5).after
    f, h = V.requirement(start, 1)
    assert (f, h) == (5, 4) and V.pm(V.seat(start, 0)["firewood_storage"])["firewood_log"] == 4
    b = V.seat(end, 0)
    assert V.pm(b["firewood_storage"]) == {}
    # money: 13 minus 4 for the bearer, food 3 x (5 - 2) = 9
    assert b["money"] == V.seat(start, 0)["money"] - 9


def test_R072_only_the_firewood_storage_pays_heating():
    """R-072: unmilled wood and milled wood elsewhere (sale area, drying, sawing area, woodpile)
    cannot pay heating. P0 has 4 logs in the sale area and none in storage: heating is fully
    missing (the reference model sells wood and forgives, it never uses the sale area directly)."""
    run = V.winter_run(VARIANTS["sale_logs"](False))
    start, end = run.event(4).after, run.event(5).after
    a = V.seat(start, 0)
    assert V.pm(a["sale"])["firewood_log"] == 4 and not V.pm(a["firewood_storage"])
    want = V.settle(a, V.requirement(start, 1))
    b = V.seat(end, 0)
    assert b["money"] == want["money"] and V.zones_equal(b, want["zones"])


# --------------------------------------------------------------------------- R-073


def test_R073_loans_come_before_selling_even_with_sellable_wood():
    """R-073 / FAQ Official: a seat short of money must take a loan before selling any wood.
    P0 ($4, no food) has 2 logs in the sale area and 2 in the storage, all sellable: while it is
    below the due amount ($15 for 5 food) and has loans left, TAKE_LOAN is the only legal action
    and no SELL is offered (after the first loan too)."""
    s = V.to_shortfall(VARIANTS["split"](False), seat=0)
    assert V.requirement(V.first_winter(VARIANTS["split"](False))[1], 1) == (5, 4)
    assert s.legal_actions() == [H.TAKE_LOAN]
    s.apply_action(H.TAKE_LOAN)
    assert s.legal_actions() == [H.TAKE_LOAN]


def test_R073_selling_order_sale_area_before_firewood_storage_and_extra_sales():
    """R-073 (user answer 2026-11-04): after 2 loans ($12 of the $15 due) the seat sells; pieces
    in the sale and drying areas first, those in the sawing area and firewood storage only once
    the former are gone. P0 has 2 logs in the sale area ($1 each) and 2 in the storage ($1 each):
    storage SELL is not legal until the sale area is empty; DONE is illegal while money < due and
    a piece is sellable; once due is covered ($15) further sales stay legal (extra sales) and so
    is DONE; TAKE_LOAN is gone (2 loans)."""
    s = V.to_shortfall(VARIANTS["split"](False), seat=0)
    storage = M.sell(5, M.FW_LOG)
    s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.TAKE_LOAN)
    legal = s.legal_actions()
    assert V.sells(legal) == [SELL_FW_LOG]
    assert H.DONE not in legal and H.TAKE_LOAN not in legal
    s.apply_action(SELL_FW_LOG)  # $13
    s.apply_action(SELL_FW_LOG)  # $14
    legal = s.legal_actions()
    assert V.sells(legal) == [storage] and H.DONE not in legal
    s.apply_action(storage)  # $15: covered
    legal = s.legal_actions()
    assert H.DONE in legal
    assert V.sells(legal) == [storage]  # one more storage log: optional extra sale


def test_R073_woodpile_wood_cannot_be_sold_and_the_rest_is_forgiven():
    """R-073 step 3/4 (D9): the woodpile cannot be sold. A seat with only woodpile wood, two loans
    ($13 in all) and a $15 food bill has nothing to sell: after the second loan no SELL is legal
    and DONE is. It pays all its money; the remaining shortfall is forgiven."""
    s = V.to_shortfall(None, seat=0)
    start = V.first_winter(None)[1]
    a = V.seat(start, 0)
    f, _ = V.requirement(start, 1)
    assert a["money"] == 5 and a["food"] == 0 and V.pm(a["woodpile"])["firewood_disk"] > 0
    assert 3 * f > 13, "precondition: loans cannot cover the bill"
    s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.TAKE_LOAN)
    legal = s.legal_actions()
    assert not V.sells(legal)
    assert H.TAKE_LOAN not in legal and H.DONE in legal


def test_R073_forgiven_shortfall_leaves_money_zero_and_two_loans():
    """R-073 step 4 / D9: P0 (no food, nothing sellable, 2 loans) pays everything it has: money 0,
    2 loans held, the rest forgiven, and the game goes on to spring year 2 (also heating: nothing
    in the storage, no loans left, nothing to sell: forgiven too)."""
    run = V.winter_run(None)
    b = V.seat(run.event(5).after, 0)
    assert b["money"] == 0 and b["loans"] == 2 and b["food"] == 0


def test_R073_unmilled_disk_in_sawing_area_is_sellable_only_last():
    """R-073 step 3 / R-058: an unmilled firewood disk in the sawing area may be sold (unmilled
    price) once the sale and drying areas are empty, but unmilled wood in the woodpile may not.
    P0 (no food, 2 loans taken) is offered exactly the sawing-area disk."""
    s = V.to_shortfall(VARIANTS["sawing_disk"](False), seat=0)
    s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.TAKE_LOAN)
    assert V.sells(s.legal_actions()) == [M.sell(4, M.FW_DISK)]
    assert H.DONE not in s.legal_actions()
    s.apply_action(M.sell(4, M.FW_DISK))
    legal = s.legal_actions()
    assert not V.sells(legal) and H.DONE in legal


def test_R073_unmilled_hardwood_cannot_be_sold():
    """R-073 / R-058: unmilled hardwood has no sale value. P0 takes a hardwood bonus disk and
    moves it by sledge to its sawing area; at the shortfall (2 loans taken) nothing sellable is
    offered and DONE is legal."""
    st = V.fall_steps(False, sledge=True)
    st.add(4, "NB", 0, V.TAKE_BONUS0 + 2)
    st.add(
        4,
        "N2",
        0,
        W.Opt(W.assign(1)),
        V.USE_SLEDGE,
        W.move_wood(W.HW, 0),
        W.Opt(V.END_TRIP),
        W.Opt(H.DONE),
    )
    s = V.to_shortfall(st, seat=0)
    s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.TAKE_LOAN)
    assert not [a for a in V.sells(s.legal_actions()) if (a - 396) % 6 == 4]
    assert H.DONE in s.legal_actions()


def test_R073_loan_stops_once_the_bill_is_covered():
    """R-073: a second loan is taken only while money is still below due. P0 ($5) holds 2 food and
    owes $9: one loan makes $9, so DONE is legal and no selling is needed."""
    s = V.to_shortfall(VARIANTS["food_only"](False), seat=0)
    s.apply_action(H.TAKE_LOAN)
    legal = s.legal_actions()
    assert H.DONE in legal and not V.sells(legal)


def test_R073_money_overshoot_stays_with_the_seat():
    """R-073 example (loan 1 leaves it below, loan 2 passes it, overshoot stays): P0 has $4, 2 food
    and 4 logs in storage; the card needs 5 food and 4 heating. It owes $9: loan 1 -> $8, loan 2
    -> $12, pays $9, keeps $3; heating is covered by the storage logs. Two loans held, storage and
    food empty."""
    run = V.winter_run(VARIANTS["overshoot"](False))
    start, end = run.event(4).after, run.event(5).after
    a = V.seat(start, 0)
    assert V.requirement(start, 1) == (5, 4)
    assert (a["money"], a["loans"], a["food"]) == (4, 0, 2)
    b = V.seat(end, 0)
    assert (b["money"], b["loans"], b["food"]) == (3, 2, 0)
    assert not V.pm(b["firewood_storage"])


def test_R073_no_selling_once_the_loans_alone_cover_the_bill():
    """R-073 step 3: selling (including optional extra sales) happens only when the seat is still
    short after both loans, or once a sale has begun. P0 ($4, 2 food, due $9, 4 firewood logs in
    its storage) is at $12 after two loans: the only legal action is DONE, no SELL is offered even
    though sellable logs exist."""
    s = V.to_shortfall(VARIANTS["overshoot"](False), seat=0)
    assert s.legal_actions() == [H.TAKE_LOAN]
    s.apply_action(H.TAKE_LOAN)  # $8 < $9
    assert s.legal_actions() == [H.TAKE_LOAN]
    s.apply_action(H.TAKE_LOAN)  # $12 >= $9
    assert s.legal_actions() == [H.DONE]


def test_R073_selling_starts_only_when_still_short_and_extra_sales_follow():
    """R-073 step 3: short after both loans -> SELL is offered (sale area first). Once the sales
    have covered the bill, DONE is legal and further (extra) sales stay legal. P0 'split' owes $15
    with $12 after two loans."""
    s = V.to_shortfall(VARIANTS["split"](False), seat=0)
    s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.TAKE_LOAN)
    assert V.sells(s.legal_actions())
    for _ in range(3):
        s.apply_action(V.sells(s.legal_actions())[0])  # $15, bill covered
    legal = s.legal_actions()
    assert H.DONE in legal and V.sells(legal)


# ------------------------------------------------- direct-state checks (white-box setup)


def _winter_state(j: bool, **fields: tuple[Any, ...]) -> tuple[Any, tuple[int, int]]:
    """State at the last N4 turn of round 4 with the given per-seat fields replaced (the harness
    has no scenario loader, and year-1 play cannot build these holdings)."""
    _, base = V.first_winter(None, j=j)
    s = V.reach(None, (4, "N4", base["clearing_order"][-1]), j=j)
    for name, value in fields.items():
        setattr(s, name, value)
    return s, V.requirement(base, 1)


def _play_out_winter(s: Any) -> None:
    """DONE (or the first legal action) until round 5 begins."""
    s.apply_action(H.DONE)
    for _ in range(200):
        if s.is_chance_node():
            return
        legal = s.legal_actions()
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("winter did not end")


def test_R072_heating_pays_cheapest_kind_first_from_a_mixed_storage():
    """R-072: with 2 firewood, 1 softwood and 2 hardwood logs in the storage and 4 pieces due,
    P0 pays both firewood, the softwood and one hardwood: one hardwood log stays."""
    s, (_, heat) = _winter_state(False, store=((2, 1, 2), (0, 0, 0)), money=(50, 50))
    assert heat == 4
    _play_out_winter(s)
    assert s.store[0] == (0, 0, 1)
    assert s.loans[0] == 0


def test_R071_joiner_adds_exactly_one_food_due_when_the_seat_can_pay():
    """R-071: P0 with 1 joiner, 2 food, $20 and heating covered owes 3 x (5 + 1 - 2) = $12; the
    joiner income of the next spring ($1, R-079) follows: $20 - 12 + 1 = $9."""
    s, (food, _) = _winter_state(
        True, joiners=(1, 0), food=(2, 0), money=(20, 50), store=((4, 0, 0), (0, 0, 0))
    )
    assert food == 5
    _play_out_winter(s)
    assert s.money[0] == 20 - 12 + 1
    assert s.loans[0] == 0


def test_R071_surplus_food_is_discarded_after_feeding():
    """R-071: 9 food held, 5 due: nothing is paid in money and all food leaves the storage."""
    s, (food, _) = _winter_state(False, food=(9, 0), money=(20, 50), store=((4, 0, 0), (0, 0, 0)))
    assert food == 5
    _play_out_winter(s)
    assert s.food[0] == 0
    assert s.money[0] == 20
