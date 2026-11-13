"""Phase 4 close (user decision 2026-11-07): with the Marketstand, BUY_FOOD and SELL_FOOD are
mutually exclusive within one Market visit, so no buy/sell cycle (and no unbounded game) exists.
"""

from __future__ import annotations

from typing import Any

from tests import harness as H
from tests.support import bldscen as B
from tests.support import travel as T

MARKET = 21  # joinery side
BUY_FOOD, SELL_FOOD = 36, 37


def _market(food: int, money: int = 5) -> Any:
    s = T.start(2, True)
    B.give(s, 0, "marketstand")
    s.food = tuple(food if i == 0 else x for i, x in enumerate(s.food))
    s.money = tuple(money if i == 0 else x for i, x in enumerate(s.money))
    T.play(s, H.MOVE_TO(MARKET))
    return s


def test_sell_food_forbids_buy_food_for_the_rest_of_the_visit() -> None:
    s = _market(food=2)
    assert BUY_FOOD in s.legal_actions() and SELL_FOOD in s.legal_actions()
    T.play(s, SELL_FOOD)
    legal = s.legal_actions()
    assert BUY_FOOD not in legal and SELL_FOOD in legal


def test_buy_food_forbids_sell_food_for_the_rest_of_the_visit() -> None:
    s = _market(food=2)
    T.play(s, BUY_FOOD)
    legal = s.legal_actions()
    assert SELL_FOOD not in legal and BUY_FOOD in legal


def test_no_buy_sell_cycle_and_next_visit_resets() -> None:
    s = _market(food=2)
    before = str(s)
    T.play(s, SELL_FOOD)
    assert str(s) != before
    T.play(s, H.DONE)
    # the flag is cleared with the visit: a later Market visit offers both again
    assert s.visit_food == 0


def test_exclusion_is_in_observer_string() -> None:
    a = _market(food=2)
    b = _market(food=2)
    T.play(a, SELL_FOOD)
    T.play(b, BUY_FOOD)
    assert str(a) != str(b)


def test_visit_is_finite_by_this_route() -> None:
    """Selling all food ends the food actions: BUY_FOOD never reappears, so the visit has at most
    food-many food actions and cannot be extended to max_game_length."""
    s = _market(food=3, money=3)
    plays = 0
    while SELL_FOOD in s.legal_actions():
        assert BUY_FOOD not in s.legal_actions() or plays == 0
        T.play(s, SELL_FOOD)
        plays += 1
    assert plays == 3
    assert BUY_FOOD not in s.legal_actions()
