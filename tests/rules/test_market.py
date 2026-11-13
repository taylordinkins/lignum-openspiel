"""Phase 4 unit 1: the Market location (R-104, R-041, R-042, R-017, R-026, R-062).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py and tests/support/{rounds,travel}.py. No scenario loader exists in the harness, so
every state is reached by scripted play in round 1 (P0 moves first).

Scope: BUY_SAW (35) and BUY_FOOD (36) at the Market, Market as a legal destination, and the
craftwork pile / CRAFT_DRAW bookkeeping around Market visits. SELL_FOOD, SELL_SET and SELL_EQUIP
need the Marketstand, craftwork or PW Trade and are only asserted to be illegal without them.

Conventions
  * A Market visit is MOVE_TO(market), then any number of BUY_*, then an explicit DONE (the Market
    is a multi-unit location; ACTIONS 1.4 does not list it among the auto-ending ones, see the
    ambiguity note in the report). Helpers close a visit with DONE only if it is still open.
  * Money, saws and food are read from the dump taken when the next seat is to move.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

BUY_SAW, BUY_FOOD, SELL_FOOD = 35, 36, 37
SELL_SET0, SELL_SET_END = 97, 129
SELL_EQUIP0, SELL_EQUIP_END = 130, 132
PLAYERS = (2, 3, 4)
BOOLS = (True, False)


def market(joinery: bool) -> int:
    """Printed Market location (R-021, R-022)."""
    return 21 if joinery else 19


def go(s: Any, joinery: bool, *acts: int) -> Any:
    """MOVE_TO(Market) followed by `acts`; the visit is left open."""
    return T.play(s, H.MOVE_TO(market(joinery)), *acts)


def others_to_clearing(s: Any, n: int) -> None:
    """After seat 0 has moved, seats 1..n-1 each go to the clearing."""
    for _ in range(1, n):
        T.goto_clearing(s)


def me(s: Any, i: int = 0) -> dict[str, Any]:
    return T.seat_of(T.snap(s), i)


# --------------------------------------------------------------------------- destination


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R104_market_is_a_legal_destination_in_round_1(n, joinery):
    """R-104/R-040: the Market (19 base, 21 joinery) can be entered by a seat that can afford a
    purchase; the Phase-2 gate on the Market destination is lifted (user decision, Phase 4)."""
    s = T.start(n, joinery)
    assert H.MOVE_TO(market(joinery)) in s.legal_actions()


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_entering_the_market_offers_both_purchases_and_no_done(joinery):
    """R-104/R-040 item 4: right after entering, BUY_SAW and BUY_FOOD are legal; DONE is not (a
    visit cannot be empty); no move is legal mid-visit."""
    s = T.start(3, joinery)
    go(s, joinery)
    legal = set(s.legal_actions())
    assert BUY_SAW in legal and BUY_FOOD in legal
    assert H.DONE not in legal
    assert not T.at_move_node(s)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_buy_actions_are_not_legal_outside_the_market(joinery):
    """R-104/R-041: BUY_SAW and BUY_FOOD exist only during a Market visit: not at a move node, not
    during a Bearers visit."""
    s = T.start(3, joinery)
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal
    T.play(s, R.move(joinery, "bearers"), R.HIRE_BEARER)
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal


# --------------------------------------------------------------------------- buying


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R104_buy_saw_costs_one_dollar_and_goes_to_equipment(n, joinery):
    """R-104/R-041/R-043: a saw costs $1, paid to the bank, and joins the equipment area."""
    s = T.start(n, joinery)
    go(s, joinery, BUY_SAW)
    assert H.DONE in s.legal_actions()
    T.play(s, H.DONE)
    assert s.current_player() == 1
    seat = me(s)
    assert seat["money"] == 4
    assert seat["equipment"]["saw"] == 1
    assert seat["food"] == 0


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R104_buy_food_costs_one_dollar_and_goes_to_food_storage(n, joinery):
    """R-104/R-041/R-043: a food costs $1 and goes to the food storage."""
    s = T.start(n, joinery)
    go(s, joinery, BUY_FOOD)
    assert H.DONE in s.legal_actions()
    T.play(s, H.DONE)
    seat = me(s)
    assert seat["money"] == 4
    assert seat["food"] == 1
    assert seat["equipment"]["saw"] == 0


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_market_visit_does_not_end_by_itself(joinery):
    """R-104: any number of purchases within one visit: after a purchase the visit stays open and
    both purchases remain legal while money lasts (visit end rule: explicit DONE)."""
    s = T.start(3, joinery)
    go(s, joinery, BUY_FOOD)
    assert s.current_player() == 0 and not T.at_move_node(s)
    legal = set(s.legal_actions())
    assert {BUY_SAW, BUY_FOOD, H.DONE} <= legal


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize(
    "order",
    [
        (BUY_SAW, BUY_SAW, BUY_FOOD, BUY_FOOD, BUY_FOOD),
        (BUY_FOOD, BUY_SAW, BUY_FOOD, BUY_SAW, BUY_FOOD),
        (BUY_FOOD, BUY_FOOD, BUY_FOOD, BUY_SAW, BUY_SAW),
    ],
    ids=["saws-first", "interleaved", "food-first"],
)
def test_R104_purchases_in_any_order_and_number(order, joinery):
    """R-104: saws and food may be bought in any order and any number in one visit; five purchases
    cost $5 in total regardless of order."""
    s = T.start(3, joinery)
    go(s, joinery, *order)
    T.end_visit(s)
    seat = me(s)
    assert seat["money"] == 0
    assert seat["equipment"]["saw"] == 2
    assert seat["food"] == 3


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_no_purchase_is_legal_without_money(joinery):
    """R-104/R-041: purchases cost $1; with $0 (no loan taken yet) neither BUY is legal, DONE is
    (the visit already had a purchase) and TAKE_LOAN is."""
    s = T.start(3, joinery)
    go(s, joinery, *([BUY_FOOD] * 5))
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal
    assert H.DONE in legal and H.TAKE_LOAN in legal


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_loan_taken_mid_visit_pays_for_purchases(joinery):
    """R-104/R-076: a loan taken during the visit gives $4 and re-enables purchases."""
    s = T.start(3, joinery)
    go(s, joinery, *([BUY_FOOD] * 5), H.TAKE_LOAN)
    assert BUY_SAW in s.legal_actions() and BUY_FOOD in s.legal_actions()
    T.play(s, BUY_SAW, BUY_SAW)
    T.end_visit(s)
    seat = me(s)
    assert seat["money"] == 2
    assert seat["loans"] == 1
    assert seat["equipment"]["saw"] == 2 and seat["food"] == 5


# --------------------------------------------------------------------------- caps


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_at_most_four_saws_owned(joinery):
    """R-104/R-041: a fourth saw is allowed, a fifth is not, even with money left ($5 -> $1);
    food stays purchasable."""
    s = T.start(3, joinery)
    go(s, joinery, *([BUY_SAW] * 3))
    assert BUY_SAW in s.legal_actions()
    T.play(s, BUY_SAW)
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal
    assert BUY_FOOD in legal
    T.play(s, BUY_FOOD)
    assert BUY_SAW not in s.legal_actions()
    T.end_visit(s)
    seat = me(s)
    assert seat["equipment"]["saw"] == 4 and seat["food"] == 1 and seat["money"] == 0


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_saw_cap_is_not_a_money_limit_and_food_is_unlimited(joinery):
    """R-104/R-041/R-009: with two loans ($13), 4 saws are bought and BUY_SAW then stays illegal
    while $9 remain; food has no supply cap: all 9 remaining dollars buy 9 food."""
    s = T.start(3, joinery)
    T.play(s, H.TAKE_LOAN, H.TAKE_LOAN)
    go(s, joinery, *([BUY_SAW] * 4))
    assert BUY_SAW not in s.legal_actions()
    for _ in range(9):
        assert BUY_FOOD in s.legal_actions()
        T.play(s, BUY_FOOD)
        assert BUY_SAW not in s.legal_actions()
    assert BUY_FOOD not in s.legal_actions()
    T.end_visit(s)
    seat = me(s)
    assert seat["money"] == 0 and seat["loans"] == 2
    assert seat["equipment"]["saw"] == 4 and seat["food"] == 9


def _saw_spots_before_market(sn: dict[str, Any], joinery: bool) -> list[int]:
    return [loc for loc in T.spot_with(sn, "saw") if loc < market(joinery)]


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_saws_from_token_spots_count_toward_the_cap(joinery):
    """R-104/R-041/R-042: saws taken from token spots count toward the 4-saw limit at the Market:
    with 2 saws from spots only 2 more can be bought."""
    for seed in range(1, 60):
        s = T.start(3, joinery, seed)
        spots = _saw_spots_before_market(T.snap(s), joinery)
        if len(spots) == 2:
            break
    else:  # pragma: no cover
        pytest.fail("no seed puts both saw tokens before the Market")
    T.play(s, H.MOVE_TO(spots[0]))
    T.goto_clearing(s)
    T.goto_clearing(s)
    T.play(s, H.MOVE_TO(spots[1]))
    go(s, joinery, BUY_SAW, BUY_SAW)
    assert BUY_SAW not in s.legal_actions()
    assert BUY_FOOD in s.legal_actions()
    T.end_visit(s)
    assert me(s)["equipment"]["saw"] == 4


# --------------------------------------------------------------------------- activation


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_market_not_enterable_with_no_money_and_two_loans(joinery):
    """R-104/R-040 item 4: a seat with $0, two loans (no further loan possible), no craftwork, no
    Marketstand and no Trade plan has nothing to do at the Market, so MOVE_TO(market) is illegal;
    the clearing remains legal."""
    s = T.broke_p0(joinery)
    sn = T.snap(s)
    seat = T.seat_of(sn, 0)
    assert seat["money"] == 0 and seat["loans"] == 2
    legal = set(s.legal_actions())
    assert H.MOVE_TO(market(joinery)) not in legal
    assert R.MOVE_CLEARING in legal


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_market_enterable_with_no_money_if_a_loan_is_available(joinery):
    """R-104/R-040 item 4/R-076: a seat with $0 and fewer than two loans may enter the Market (the
    loan counts); once inside, a purchase needs the loan first."""
    s = T.start(4, joinery)
    T.hire(s, R.loc(joinery, "bearers"), R.HIRE_BEARER, 5)
    for _ in (1, 2, 3):
        T.goto_clearing(s)
    assert s.current_player() == 0
    assert T.seat_of(T.snap(s), 0)["money"] == 0
    assert H.MOVE_TO(market(joinery)) in s.legal_actions()
    T.play(s, H.MOVE_TO(market(joinery)))
    legal = set(s.legal_actions())
    assert BUY_SAW not in legal and BUY_FOOD not in legal
    assert H.TAKE_LOAN in legal
    T.play(s, H.TAKE_LOAN)
    assert BUY_FOOD in s.legal_actions()
    T.play(s, BUY_FOOD)
    T.end_visit(s)
    seat = T.seat_of(T.snap(s), 0)
    assert seat["money"] == 3 and seat["food"] == 1 and seat["loans"] == 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_market_capacity_is_four_foremen(joinery):
    """R-104/R-021/R-022/R-040 item 3: the Market holds up to four foremen (unlike token spots),
    so with 4 players all four may visit it in one round."""
    s = T.start(4, joinery)
    for seat_no in range(4):
        assert s.current_player() == seat_no
        assert H.MOVE_TO(market(joinery)) in s.legal_actions()
        T.visit(s, market(joinery), BUY_FOOD)
    for i in range(4):
        assert me(s, i)["food"] == 1 and me(s, i)["money"] == 4


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_market_cannot_be_revisited_once_passed(joinery):
    """R-040 item 1/R-104: foremen only move forward, so after the Market the seat can never
    choose it again."""
    s = T.start(3, joinery)
    T.visit(s, market(joinery), BUY_FOOD)
    others_to_clearing(s, 3)
    assert s.current_player() == 0
    assert H.MOVE_TO(market(joinery)) not in s.legal_actions()


# --------------------------------------------------------------------------- things not for sale


@pytest.mark.parametrize("joinery", BOOLS)
def test_R104_nothing_to_sell_without_marketstand_craftwork_or_trade(joinery):
    """R-104/R-108/R-105/R-090: a seat with food but no Marketstand, no craftwork and no Trade plan
    has no SELL_FOOD, SELL_SET or SELL_EQUIP action at the Market."""
    s = T.start(3, joinery)
    go(s, joinery, BUY_FOOD, BUY_FOOD)
    legal = set(s.legal_actions())
    assert SELL_FOOD not in legal
    assert not any(SELL_SET0 <= a <= SELL_SET_END for a in legal)
    assert not any(SELL_EQUIP0 <= a <= SELL_EQUIP_END for a in legal)


# --------------------------------------------------------------------------- craftwork pile


def _market_policy():
    """Seat 0 buys one food at the Market whenever it may enter it; everyone else, and seat 0
    otherwise, goes to the clearing. Returns (policy, counter)."""
    bought = {"n": 0, "open": False}

    def policy(ctx: R.Ctx) -> int | None:
        if ctx.phase != "TR" or ctx.player != 0:
            return None
        legal = ctx.legal
        if R.MOVE_CLEARING in legal:  # a move node
            bought["open"] = False
            for loc in (19, 21):
                if H.MOVE_TO(loc) in legal and ctx.snap is not None:
                    joinery = bool(ctx.snap["parameters"]["joinery"])
                    if loc == market(joinery):
                        bought["open"] = True
                        return H.MOVE_TO(loc)
            return None
        if bought["open"] and BUY_FOOD in legal:
            bought["open"] = False
            bought["n"] += 1
            return BUY_FOOD
        return H.DONE if H.DONE in legal else None

    return policy, bought


@pytest.mark.parametrize("joinery", BOOLS)
def test_R017_R062_craftwork_pile_is_exactly_drawn_in_six_fills_with_market_visits(joinery):
    """R-017/R-035/R-062/R-026: with seat 0 visiting the Market in the seasonal rounds, the
    CRAFT_DRAW nodes still total 18 over the game (3 in each of rounds 1, 2, 3, 5, 6, 7, none in
    winter), drawing each type exactly its pile count (4 board, 4 shingle, 4 stake, 4 reed,
    2 joker): Market buys neither refill nor consume the pile."""
    policy, bought = _market_policy()
    run = R.drive({"players": 3, "joinery": joinery}, seed=5, policy=policy)
    assert bought["n"] > 0, "scenario must actually use the Market"
    per_type = [0] * 5
    for ev in run.events:
        n_craft = 0
        for a in ev.trail:
            fam, x = H.chance_family(a)
            if fam == "CRAFT_DRAW":
                per_type[x] += 1
                n_craft += 1
        assert n_craft == (3 if ev.round in R.SEASONAL else 0), f"round {ev.round}"
    assert per_type == [4, 4, 4, 4, 2]


@pytest.mark.parametrize("joinery", BOOLS)
def test_R017_R061_unsold_craftwork_on_path_is_removed_not_returned_to_pile(joinery):
    """R-061/R-035/R-017: Market visits that take no craftwork leave the 3 craftwork tokens on the
    path; cleanup removes them from the game. Round 2's three CRAFT_DRAWs then come from the
    remaining 15, so round 2 draws proportionally to the pile left after round 1's 3."""
    policy, _ = _market_policy()
    run = R.drive(
        {"players": 3, "joinery": joinery}, seed=5, policy=policy, stop=lambda c: c.round == 3
    )
    ev1 = run.event(1)
    ev2 = run.event(2)
    first1 = [H.chance_family(a) for a in ev1.trail if H.chance_family(a)[0] == "CRAFT_DRAW"]
    second = [(i, a) for i, a in enumerate(ev2.trail) if H.chance_family(a)[0] == "CRAFT_DRAW"]
    assert len(first1) == 3 and len(second) == 3
    totals = R.craft_totals()
    pile = {k: totals[k] for k in R.CRAFT}
    for _, x in first1:
        pile[R.CRAFT[x]] -= 1
    outs = ev2.outcomes[second[0][0]]
    tot = sum(pile.values())
    assert tot == 15
    for x, k in enumerate(R.CRAFT):
        assert outs.get(H.CHANCE_BASE["CRAFT_DRAW"] + x, 0) == pytest.approx(pile[k] / tot)
