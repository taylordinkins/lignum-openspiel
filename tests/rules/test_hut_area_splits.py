"""R-100 / ACTIONS 5.7: hut tokens may go to any hut area independently (all on one area or split).

Every multiset of three areas out of {drying, food, worker} is reachable through a legal
non-decreasing HUT_AREA sequence and yields the matching hut assignment.
"""

from itertools import combinations_with_replacement

import pytest

from tests.rules.test_huts import (
    BUILD_HUT,
    CLEAR,
    craft,
    hut_area,
    hut_legal,
    hut_token,
    huts,
    reach_tr,
    to_boundary_of,
)

SPLITS = list(combinations_with_replacement(range(3), 3))
NAMES = ("drying", "food", "worker")


def test_R100_all_ten_splits_enumerated():
    assert len(SPLITS) == 10


@pytest.mark.parametrize("areas", SPLITS)
def test_R100_any_split_of_three_tokens_over_the_areas(areas):
    s = reach_tr("plain")
    assert BUILD_HUT in s.legal_actions()
    s.apply_action(BUILD_HUT)
    for x in (0, 1, 2):
        s.apply_action(hut_token(x))
    for h in areas:
        assert hut_area(h) in hut_legal(s)
        s.apply_action(hut_area(h))
    s.apply_action(CLEAR)
    to_boundary_of(s, lambda sn, p: p == 1)
    assert huts(s) == {n: areas.count(i) for i, n in enumerate(NAMES)}
    assert sum(craft(s).values()) == 0
