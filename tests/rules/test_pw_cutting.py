"""Phase 4 unit 7: PW Cutting (R-099; R-041 Woodcutters cap, R-047 cutting, R-048 shared areas,
R-103 hut/mill workers; ACTIONS 1.3 rows HIRE_WOODCUTTER / MOVE_CUT_TOKEN / TAKE_WOOD, 5.2).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and tests/harness.py only; states come from
scripted play (tests/support/pwscen.py).

Conventions
  * HIRE_WOODCUTTER = 32, MOVE_CUT_TOKEN(a) = 168 + a, ASSIGN_WORKER(w) = 174 + w (0 hired, 1 mill
    worker), TAKE_WOOD(a, k) = 177 + 3a + k with a the 0-based area. Woodcutters is location 10.
  * Scenario `cut_scn`: P0 plans Cutting in the round before the action round (pair 1); P0 picks the
    area with the most wood, P1 the next best (a different area); P0 hires `h` woodcutters and is
    first in clearing order (P1 takes a Bearers visit so that it enters the clearing second); the
    state is P0's W1 turn, and P1 is still to act in W1 after it.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import pwscen as P
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

HIRE_WC = 32
WOODCUTTERS_LOC = 10
LAYOUT = [P.CUT, P.LOG, P.TRADE, P.CRAFT]
TAKE = W.TAKE_WOOD_IDS


def cut_scn(
    key: str,
    *,
    plan: bool = True,
    act: int = 2,
    h: int = 2,
    stop: tuple[Any, ...] | None = None,
    check: bool = True,
) -> Any:
    wants: dict[tuple[int, int], list[Any]] = {}
    # R-060: next round's order is the reverse of the clearing order, so P1 starts rounds 2.. and
    # P0 only enters the clearing before it if P1 makes two moves first.
    for r in range(2, act + 1):
        wants[(r, 1)] = [("hire", "bearers", 1), ("hire", "sawyers", 1)]
        wants[(r, 0)] = []
    if plan:
        wants[(act - 1, 0)] = [("plan", P.CUT, 1)]
    wants[(act, 0)] = [("hire", "woodcutters", h)] if h else []

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(act, "PK", 0, W.rank_pick(0))
        st.add(act, "PK", 1, W.rank_pick(1))
        return st

    def ok(s: Any) -> bool:
        if not check:
            return True
        sn = P.snap(s)
        a0, a1 = own_area(sn, 0), own_area(sn, 1)
        if a0 == a1 or W.area_total(sn, a1) < 2 or W.area_total(sn, a0) < 2:
            return False
        c = s.clone()
        c.apply_action(H.DONE)
        return R.try_snapshot(c) is not None and ((c.current_player(), H.phase_of(c)) == (1, "W1"))

    return P.reach(key, LAYOUT, wants, steps, stop or ("node", act, "W1", 0), ok)


def own_area(sn: dict[str, Any], seat: int) -> int:
    """0-based cutting area of the seat's token."""
    return int(T.seat_of(sn, seat)["cutting_area"]) - 1


def outside(s: Any, own: int) -> list[int]:
    return [a for a in s.legal_actions() if a in TAKE and (a - 177) // 3 != own]


def inside(s: Any, own: int) -> list[int]:
    return [a for a in s.legal_actions() if a in TAKE and (a - 177) // 3 == own]


def area_of(a: int) -> int:
    return (a - 177) // 3


def wood_in(s: Any, area: int) -> int:
    return W.area_total(P.snap(s), area)


def assign(s: Any, w: int) -> None:
    if W.assign(w) in s.legal_actions():
        s.apply_action(W.assign(w))


def take_outside(s: Any, own: int, w: int, area: int | None = None) -> int:
    """Assign source w and take 1 piece outside the own area; returns the area used."""
    assign(s, w)
    opts = [a for a in s.legal_actions() if a in TAKE and area_of(a) != own]
    if area is not None:
        opts = [a for a in opts if area_of(a) == area]
    assert opts, f"no outside take: {s.legal_actions()}"
    s.apply_action(opts[0])
    return area_of(opts[0])


# --------------------------------------------------------------------------- item 1: hire cap


def tr_state(key: str, plan: bool) -> Any:
    wants: dict[tuple[int, int], list[Any]] = {(2, 0): []}
    wants[(1, 0)] = [("plan", P.CUT, 1)] if plan else []

    def steps() -> W.Steps:
        st = W.Steps()
        st.add(2, "PK", 0, W.rank_pick(0))
        st.add(2, "PK", 1, W.rank_pick(1))
        return st

    return P.reach(key, LAYOUT, wants, steps, ("tr", 2, 0))


def hires_possible(s: Any) -> int:
    """Take loans if needed, visit Woodcutters and hire until HIRE_WOODCUTTER is not legal."""
    for _ in range(2):
        if H.TAKE_LOAN in s.legal_actions():
            s.apply_action(H.TAKE_LOAN)
    s.apply_action(H.MOVE_TO(WOODCUTTERS_LOC))
    n = 0
    while HIRE_WC in s.legal_actions() and n < 10:
        s.apply_action(HIRE_WC)
        n += 1
    return n


def test_R099_hire_cap_is_wood_in_area_plus_two():
    """R-099 item 1: with the plan the seat may hire (wood in its selected area + 2) woodcutters."""
    s = tr_state("cut_tr_plan", True)
    w = T.own_wood(P.snap(s), 0)
    assert w >= 2
    assert hires_possible(s) == w + 2


def test_R099_without_the_plan_the_cap_is_the_wood_in_the_area():
    """R-041 baseline for R-099: the same board with no plan caps hires at the wood in the area
    (the extra two are not hireable)."""
    s = tr_state("cut_tr_noplan", False)
    w = T.own_wood(P.snap(s), 0)
    assert hires_possible(s) == w


def test_R099_cap_is_for_the_target_round_only():
    """R-099 / R-089: the plan is for round 2 only. In round 3 (and in round 1) the cap is the
    wood in the area. Round 3 is checked here."""
    wants: dict[tuple[int, int], list[Any]] = {
        (1, 0): [("plan", P.CUT, 1)],
        (1, 1): [("hire", "bearers", 1)],
        (3, 0): [],
    }
    s = P.reach("cut_tr_r3", LAYOUT, wants, W.Steps, ("tr", 3, 0))
    w = T.own_wood(P.snap(s), 0)
    assert hires_possible(s) == w


# --------------------------------------------------------------------------- item 2: outside cut


def test_R099_worker_may_take_wood_from_another_area():
    """R-099 item 2: with the plan, after ASSIGN_WORKER the legal TAKE_WOOD actions include every
    other cutting area that holds wood (any other area, tokened or not)."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    own = own_area(sn, 0)
    assign(s, 0)
    areas = {area_of(a) for a in s.legal_actions() if a in TAKE}
    with_wood = {a for a in range(6) if W.area_total(sn, a) > 0}
    assert own in areas
    assert (with_wood - {own}) <= areas
    assert own_area(sn, 1) in areas


def test_R099_no_plan_no_outside_take():
    """R-047 baseline: without the plan a worker takes only from its own area."""
    s = cut_scn("cut_w1_noplan", plan=False, h=2)
    own = own_area(P.snap(s), 0)
    assign(s, 0)
    assert inside(s, own)
    assert not outside(s, own)


def test_R099_two_workers_take_two_pieces_from_the_other_area_no_food():
    """R-099 item 2 + example: two workers move into the other seat's area and take one piece
    each: P1's area loses 2 pieces, P0's woodpile gains 2, nobody gains food, P0's cutting token
    is unchanged."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    own, other = own_area(sn, 0), own_area(sn, 1)
    pile0 = sum(W.zone(sn, 0, "woodpile").values())
    food0 = [T.seat_of(sn, i)["food"] for i in (0, 1)]
    afood0 = R.food(H.areas(sn)[other])
    other0 = W.area_total(sn, other)
    take_outside(s, own, 0, other)
    take_outside(s, own, 0, other)
    s.apply_action(H.DONE)
    sn2 = P.snap(s)
    assert sum(W.zone(sn2, 0, "woodpile").values()) == pile0 + 2
    assert W.area_total(sn2, other) == other0 - 2
    assert [T.seat_of(sn2, i)["food"] for i in (0, 1)] == food0
    assert R.food(H.areas(sn2)[other]) == afood0
    assert own_area(sn2, 0) == own


def test_R099_at_most_two_workers_outside():
    """R-099 item 2 ('at most 2 workers'): after two outside takes a third worker (the mill
    worker) may cut the own area but has no outside TAKE_WOOD."""
    s = cut_scn("cut_w1_h2", h=2)
    own = own_area(P.snap(s), 0)
    other = own_area(P.snap(s), 1)
    take_outside(s, own, 0, other)
    take_outside(s, own, 0, other)
    assign(s, 1)
    assert inside(s, own), "the third worker still cuts its own area"
    assert not outside(s, own)


def test_R099_both_outside_workers_go_to_the_same_area():
    """R-099 item 2 ('both into the same area, not two different areas'): once one worker has
    taken wood in area X outside, further outside takes are only legal in X."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    own = own_area(sn, 0)
    first = take_outside(s, own, 0)
    assign(s, 0)
    later = {area_of(a) for a in s.legal_actions() if a in TAKE and area_of(a) != own}
    assert later <= {first}


def test_R099_mill_worker_and_a_hired_worker_can_both_go_outside():
    """R-099 item 2 / R-103: the mill worker counts among the 2 moved workers. With one hired
    woodcutter plus the mill worker both take wood outside."""
    s = cut_scn("cut_w1_h1", h=1)
    own, other = own_area(P.snap(s), 0), own_area(P.snap(s), 1)
    other0 = wood_in(s, other)
    take_outside(s, own, 0, other)
    take_outside(s, own, 1, other)
    s.apply_action(H.DONE)
    assert W.area_total(P.snap(s), other) == other0 - 2


def test_R099_remaining_workers_still_cut_the_own_area():
    """R-099 item 2 ('its remaining workers cut in its own area'): one worker cuts own, two go
    outside (3 workers: 2 hired + mill): own area -1, other area -2, woodpile +3."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    own, other = own_area(sn, 0), own_area(sn, 1)
    pile0 = sum(W.zone(sn, 0, "woodpile").values())
    own0, other0 = W.area_total(sn, own), W.area_total(sn, other)
    assign(s, 0)
    s.apply_action(inside(s, own)[0])
    take_outside(s, own, 0, other)
    take_outside(s, own, 1, other)
    s.apply_action(H.DONE)
    sn2 = P.snap(s)
    assert W.area_total(sn2, own) == own0 - 1
    assert W.area_total(sn2, other) == other0 - 2
    assert sum(W.zone(sn2, 0, "woodpile").values()) == pile0 + 3


def test_R099_outside_cut_not_available_in_the_planning_round():
    """R-099 / R-089: planned in round 1 (target 2); round 1's own woodcutting phase has no
    outside TAKE_WOOD."""
    wants: dict[tuple[int, int], list[Any]] = {
        (1, 0): [("plan", P.CUT, 1), ("hire", "woodcutters", 1)],
        (1, 1): [("hire", "bearers", 1)],
    }
    s = P.reach("cut_planning_round", LAYOUT, wants, W.Steps, ("node", 1, "W1", 0))
    own = own_area(P.snap(s), 0)
    assign(s, 0)
    assert inside(s, own)
    assert not outside(s, own)


def test_R099_outside_cut_not_available_after_the_target_round():
    """R-099 / R-089: planned in round 1 for round 2: in round 3 there is no outside TAKE_WOOD."""
    s2 = P.reach(
        "cut_r3_planned",
        LAYOUT,
        {
            (1, 0): [("plan", P.CUT, 1)],
            (1, 1): [("hire", "bearers", 1)],
            (2, 1): [("hire", "bearers", 1), ("hire", "sawyers", 1)],
            (3, 0): [("hire", "woodcutters", 1)],
            (3, 1): [("hire", "bearers", 1), ("hire", "sawyers", 1)],
        },
        lambda: _picks(3),
        ("node", 3, "W1", 0),
    )
    own = own_area(P.snap(s2), 0)
    assign(s2, 0)
    assert inside(s2, own)
    assert not outside(s2, own)


def _picks(act: int) -> W.Steps:
    st = W.Steps()
    st.add(act, "PK", 0, W.rank_pick(0))
    st.add(act, "PK", 1, W.rank_pick(1))
    return st


# --------------------------------------------------------------------------- affected seat


def test_R099_affected_seat_may_pay_one_dollar_and_move_to_a_free_area():
    """R-099 last paragraph + R-048: after P0 took wood from P1's area, P1 (whose area was
    reduced) may pay $1 and move its token to an area with no token: legal MOVE_CUT_TOKEN targets
    are exactly the 4 areas that hold neither seat's token; it then pays $1 and cuts there."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    a0, a1 = own_area(sn, 0), own_area(sn, 1)
    own = a0
    take_outside(s, own, 0, a1)
    take_outside(s, own, 0, a1)
    s.apply_action(H.DONE)
    assert s.current_player() == 1 and H.phase_of(s) == "W1"
    if H.TAKE_LOAN in s.legal_actions() and T.seat_of(P.snap(s), 1)["money"] < 1:
        s.apply_action(H.TAKE_LOAN)
    moves = sorted(a for a in s.legal_actions() if a in W.MOVE_CUT_IDS)
    free = [a for a in range(6) if a not in (a0, a1)]
    assert moves == sorted(W.move_cut(a) for a in free)
    money0 = T.seat_of(P.snap(s), 1)["money"]
    dest = max(free, key=lambda a: W.area_total(P.snap(s), a))
    s.apply_action(W.move_cut(dest))
    assign(s, 1)
    assert inside(s, dest)
    s.apply_action(inside(s, dest)[0])
    s.apply_action(H.DONE)
    sn2 = P.snap(s)
    assert T.seat_of(sn2, 1)["money"] == money0 - 1
    assert own_area(sn2, 1) == dest


def test_R099_affected_seat_may_simply_cut_what_remains():
    """R-099 / R-048 option 1: P1 keeps its token and cuts whatever remains in its area."""
    s = cut_scn("cut_w1_h2", h=2)
    a1 = own_area(P.snap(s), 1)
    n = wood_in(s, a1)
    own = own_area(P.snap(s), 0)
    take_outside(s, own, 0, a1)
    take_outside(s, own, 0, a1)
    s.apply_action(H.DONE)
    assert s.current_player() == 1
    assign(s, 1)
    if n - 2 > 0:
        assert inside(s, a1)
    else:
        assert not inside(s, a1)


def test_R099_unaffected_seat_gets_no_move_option():
    """R-048 baseline: P0 takes nothing outside, so P1 is unaffected, shares no area and has no
    MOVE_CUT_TOKEN."""
    s = cut_scn("cut_w1_h2", h=2)
    own = own_area(P.snap(s), 0)
    assign(s, 0)
    s.apply_action(inside(s, own)[0])
    s.apply_action(H.DONE)
    assert s.current_player() == 1 and H.phase_of(s) == "W1"
    assert not [a for a in s.legal_actions() if a in W.MOVE_CUT_IDS]


def test_R099_area_not_reduced_gives_no_move_option_even_after_outside_take_elsewhere():
    """User ruling 2026-11-06 (b): P0 takes outside from a free area other than P1's own, so
    P1's area lost no wood and P1 (sharing no area) has no MOVE_CUT_TOKEN. Skipped when no such
    third area holds wood."""
    s = cut_scn("cut_w1_h2", h=2)
    sn = P.snap(s)
    own, a1 = own_area(sn, 0), own_area(sn, 1)
    third = [a for a in range(6) if a not in (own, a1) and W.area_total(sn, a) > 0]
    if not third:
        pytest.skip("no third area with wood in this scenario")
    take_outside(s, own, 0, third[0])
    s.apply_action(H.DONE)
    assert s.current_player() == 1 and H.phase_of(s) == "W1"
    assert not [a for a in s.legal_actions() if a in W.MOVE_CUT_IDS]
