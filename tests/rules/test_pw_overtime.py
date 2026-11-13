"""Phase 4 unit 7: PW Overtime (R-097; step 3a of R-034; R-088 target rounds; R-065 bonus order;
R-046 ordinary unmilled hardwood; R-060 starting-player order; ACTIONS 5.9 and the RS/WS rows).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and tests/harness.py only. States are reached by
scripted play (tests/support/pwscen.py): P0 (and optionally P1) plan Overtime in an earlier round,
play runs on with default actions (clearing, DONE) and stops at the first decision node of the
target round.

Conventions
  * TAKE_OVERTIME = 133, DONE = 0, TAKE_BONUS(k) = 228 + k. 2 players, base side, so 4 cards are
    laid out: Overtime, Trade, Craftwork, Drying.
  * A plan made in round r with pair p targets round r + p (R-088): round 1 pair 1 -> round 2.
  * "One decision node" per ACTIONS 5.9: TAKE_OVERTIME does not close the node, a DONE follows
    (user decision 2026-11-06); `settle()` plays that DONE if the same seat is still asked.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from tests import harness as H
from tests.support import pwscen as P
from tests.support import woodwork as W

TAKE_OVERTIME = 133
TAKE_BONUS = range(228, 231)
PICKS = range(2, 8)
LAYOUT = [P.OT, P.TRADE, P.CRAFT, P.DRY]


def plans_wants(plans: dict[tuple[int, int], int]) -> dict[tuple[int, int], list[Any]]:
    """{(round, seat): pair} -> travel wants (the plan is made in `round`)."""
    return {k: [("plan", P.OT, pair)] for k, pair in plans.items()}


def reach(key: str, plans: dict[tuple[int, int], int], stop: tuple[Any, ...]) -> Any:
    return P.reach(key, LAYOUT, plans_wants(plans), W.Steps, stop)


def woodpile(s: Any, seat: int = 0) -> Counter[str]:
    return W.zone(P.snap(s), seat, "woodpile")


def hardwood(s: Any, seat: int = 0) -> int:
    return sum(v for k, v in woodpile(s, seat).items() if "hardwood" in k)


def phase(s: Any) -> str:
    return H.phase_of(s)


def settle(s: Any, phases: tuple[str, ...] = ("RS", "WS")) -> None:
    """After TAKE_OVERTIME: if the same seat is still at an RS/WS node, close it with DONE."""
    seat = s.current_player()
    if phase(s) in phases and s.current_player() == seat and H.DONE in s.legal_actions():
        s.apply_action(H.DONE)


def other_start_nodes(s: Any) -> list[tuple[str, int]]:
    """Play DONE at each RS node until the first non-RS node; list (phase, seat) visited."""
    seen: list[tuple[str, int]] = []
    for _ in range(6):
        seen.append((phase(s), s.current_player()))
        if phase(s) not in ("RS", "WS"):
            break
        s.apply_action(H.DONE)
    return seen


# --------------------------------------------------------------------------- R-097 seasonal


def test_R097_holder_gets_overtime_node_before_the_hidden_picks():
    """R-097 / R-034 step 3a: in the target round the holder's first decision is an RS node where
    TAKE_OVERTIME and DONE are legal and no PICK_AREA is (picks come after)."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    assert phase(s) == "RS"
    assert s.current_player() == 0
    legal = s.legal_actions()
    assert TAKE_OVERTIME in legal and H.DONE in legal
    assert not [a for a in legal if a in PICKS]


def test_R097_take_adds_one_unmilled_hardwood_disk_to_the_woodpile():
    """R-097: taking Overtime puts 1 hardwood disk (ordinary unmilled hardwood, R-046) into the
    seat's woodpile; the picks follow."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    before = woodpile(s)
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    assert phase(s) == "PK"
    after = woodpile(s)
    assert sum(after.values()) == sum(before.values()) + 1
    assert hardwood(s) == hardwood_of(before) + 1
    assert any("disk" in k and "hardwood" in k for k in after), after


def hardwood_of(c: Counter[str]) -> int:
    return sum(v for k, v in c.items() if "hardwood" in k)


def test_R097_overtime_is_optional_declining_adds_nothing():
    """R-097 ('optional'): DONE at the node declines; the woodpile is unchanged and the game goes
    on to the picks."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    before = woodpile(s)
    s.apply_action(H.DONE)
    assert phase(s) == "PK"
    assert woodpile(s) == before


def test_R097_only_one_hardwood_per_plan_a_second_take_is_not_legal():
    """R-097: a single disk. After TAKE_OVERTIME no further TAKE_OVERTIME is legal at any node of
    the round (checked at the node that follows and in the picks)."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    s.apply_action(TAKE_OVERTIME)
    for _ in range(3):
        if phase(s) == "PK":
            break
        assert TAKE_OVERTIME not in s.legal_actions()
        s.apply_action(H.DONE)
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_not_legal_once_the_picks_have_started():
    """R-097 timing: after declining at RS the picks run and TAKE_OVERTIME is no longer offered."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    s.apply_action(H.DONE)
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_seat_without_the_plan_is_never_offered_overtime():
    """R-097 / R-089: only the holder. P1 holds the plan, so the first decision of round 2 is
    P1's RS node; P0 gets no RS node and goes straight to the picks."""
    s = reach("ot_p1_r2", {(1, 1): 1}, ("round", 2))
    assert phase(s) == "RS"
    assert s.current_player() == 1
    assert TAKE_OVERTIME in s.legal_actions()
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()
    assert hardwood(s, 0) == 0
    assert hardwood(s, 1) >= 1


def test_R097_no_plan_no_overtime_node():
    """R-097: with no Overtime plan for the round nobody is offered TAKE_OVERTIME and round 2
    starts at the picks."""
    s = P.reach("ot_none", LAYOUT, {(1, 0): [("plan", P.TRADE, 1)]}, W.Steps, ("round", 2))
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_both_holders_decide_in_starting_player_order():
    """R-097 / R-060 / ACTIONS A3: with two holders the RS nodes follow the starting-player
    (turn_order) order, both before any pick."""
    s = reach("ot_both_r2", {(1, 0): 1, (1, 1): 1}, ("round", 2))
    order = [int(x) for x in P.snap(s)["turn_order"]]
    assert phase(s) == "RS"
    assert s.current_player() == order[0]
    assert TAKE_OVERTIME in s.legal_actions()
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    assert phase(s) == "RS"
    assert s.current_player() == order[1]
    assert TAKE_OVERTIME in s.legal_actions()
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    assert phase(s) == "PK"
    assert hardwood(s, 0) == 1 and hardwood(s, 1) == 1


def test_R097_one_holder_declining_does_not_affect_the_other():
    """R-097 (plans independent, R-089): the first holder declines, the second still takes."""
    s = reach("ot_both_r2", {(1, 0): 1, (1, 1): 1}, ("round", 2))
    first = s.current_player()
    s.apply_action(H.DONE)
    assert phase(s) == "RS" and s.current_player() != first
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    assert hardwood(s, first) == 0
    assert hardwood(s, 1 - first) == 1


def test_R097_only_in_the_target_round_not_the_round_after_planning():
    """R-097 / R-088: a pair-2 plan made in round 1 targets round 3, so round 2 has no node."""
    s = reach("ot_p0_pair2_r2", {(1, 0): 2}, ("round", 2))
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_pair_two_plan_offers_overtime_in_round_three():
    """R-097 / R-088: the same pair-2 plan is offered in round 3 (target round)."""
    s = reach("ot_p0_pair2_r3", {(1, 0): 2}, ("round", 3))
    assert phase(s) == "RS"
    assert s.current_player() == 0
    assert TAKE_OVERTIME in s.legal_actions()


def test_R097_not_offered_in_the_round_after_the_target_round():
    """R-097: the plan is used up by its target round; round 3 (after a round 2 target) shows no
    Overtime node, even if the seat declined in round 2."""
    s = reach("ot_p0_r3_after", {(1, 0): 1}, ("round", 3))
    assert phase(s) == "PK"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_not_offered_in_the_planning_round():
    """R-097 / R-089: nothing happens in the round the plan is made. Round 1 has no RS node at
    all (R-020) and no TAKE_OVERTIME anywhere in the planning visit."""
    s = P.build(LAYOUT, 1)
    s.apply_action(H.MOVE_TO(P.PW_LOC))
    assert P.PLAN(P.OT, 1) in s.legal_actions()
    assert TAKE_OVERTIME not in s.legal_actions()
    s.apply_action(P.PLAN(P.OT, 1))
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_overtime_hardwood_is_not_placed_in_the_sale_area():
    """R-097 + R-046: the extra hardwood is an unmilled disk; at transportation it can go to the
    sawing area only (MOVE_WOOD(hardwood, sale area) = 195 + 2*2 + 1 = 200 is never legal)."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    s = P.advance(s, lambda sn, st: sn["phase"] == "W3" and st.current_player() == 0)
    assert hardwood(s) >= 1
    assert 200 not in s.legal_actions()


# --------------------------------------------------------------------------- R-097 winter


def winter_state(key: str, rnd: int, plans: dict[tuple[int, int], int]) -> Any:
    return reach(key, plans, ("round", rnd))


def test_R097_round8_holder_decides_at_winter_start_before_the_bonus():
    """R-097 / ACTIONS 5.9: a round-8 holder's first decision is a WS node (TAKE_OVERTIME or
    DONE), before any TAKE_BONUS is legal for anyone (R-065)."""
    s = winter_state("ot_r8", 8, {(7, 0): 1})
    assert phase(s) == "WS"
    assert s.current_player() == 0
    legal = s.legal_actions()
    assert TAKE_OVERTIME in legal and H.DONE in legal
    assert not [a for a in legal if a in TAKE_BONUS]


def test_R097_round8_hardwood_is_in_the_woodpile_when_the_bonus_is_taken():
    """R-097 example: the hardwood disk is in the woodpile at the seat's bonus node, then the
    winter bonus softwood disk is taken in addition (two pieces gained in all)."""
    s = winter_state("ot_r8", 8, {(7, 0): 1})
    start = woodpile(s)
    s.apply_action(TAKE_OVERTIME)
    settle(s)
    for _ in range(4):
        if phase(s) == "NB" and s.current_player() == 0:
            break
        assert phase(s) == "NB", phase(s)
        s.apply_action(H.DONE)
    assert phase(s) == "NB" and s.current_player() == 0
    assert hardwood_of(woodpile(s)) == hardwood_of(start) + 1
    assert [a for a in s.legal_actions() if a in TAKE_BONUS]
    s.apply_action(228 + 1)
    # TAKE_BONUS is mid-turn (ACTIONS A2): close the seat's turn before snapshotting again.
    assert H.DONE in s.legal_actions()
    s.apply_action(H.DONE)
    assert sum(woodpile(s).values()) == sum(start.values()) + 2


def test_R097_round8_declining_leaves_the_woodpile_and_goes_to_the_bonus():
    """R-097 round 8: DONE at WS adds nothing and the next node is NB (bonus)."""
    s = winter_state("ot_r8", 8, {(7, 0): 1})
    before = woodpile(s)
    s.apply_action(H.DONE)
    assert phase(s) == "NB"
    assert TAKE_OVERTIME not in s.legal_actions()
    assert woodpile(s) == before


def test_R097_round8_seat_without_a_plan_goes_straight_to_the_bonus():
    """R-097: with no Overtime for round 8, no WS node; the first node is NB."""
    s = P.reach("ot_r8_none", LAYOUT, {}, W.Steps, ("round", 8))
    assert phase(s) == "NB"
    assert TAKE_OVERTIME not in s.legal_actions()


def test_R097_year1_winter_target_offers_overtime_at_winter_start():
    """R-097 + R-088 + user ruling 2026-11-06 (a): a pair-3 plan made in round 1 targets round 4
    (year-1 winter); the holder gets the option at WS, takes the disk, and NB follows."""
    s = reach("ot_r4", {(1, 0): 3}, ("round", 4))
    assert phase(s) == "WS"
    assert TAKE_OVERTIME in s.legal_actions()
    start = woodpile(s)
    s.apply_action(TAKE_OVERTIME)
    s.apply_action(H.DONE)
    assert phase(s) == "NB"
    assert hardwood_of(woodpile(s)) == hardwood_of(start) + 1


def test_R097_take_keeps_the_same_seat_at_the_node_with_only_done_and_loan():
    """ACTIONS 5.9: after TAKE_OVERTIME the same seat is still at RS; only DONE (and TAKE_LOAN
    while a loan is available) are legal, so no second take and no picks."""
    s = reach("ot_p0_r2", {(1, 0): 1}, ("round", 2))
    seat = s.current_player()
    s.apply_action(TAKE_OVERTIME)
    assert s.current_player() == seat
    assert s.legal_actions() == [a for a in (H.DONE, H.TAKE_LOAN) if a in s.legal_actions()]
    assert H.DONE in s.legal_actions()
    assert set(s.legal_actions()) <= {H.DONE, H.TAKE_LOAN}


def test_R097_winter_holders_decide_in_starting_player_order_not_clearing_order():
    """R-097 / R-064: with two winter holders the WS nodes follow the starting-player order
    (turn_order), not the fall clearing order that the later winter phases use. With 2 seats the
    two orders are reverses of each other, so this fails if clearing order were used."""
    s = reach("ot_r4_both", {(1, 0): 3, (1, 1): 3}, ("round", 4))
    sn = P.snap(s)
    order = [int(x) for x in sn["turn_order"]]
    clearing = [int(x) for x in sn["clearing_order"]]
    assert order != clearing
    assert phase(s) == "WS"
    assert s.current_player() == order[0]
    s.apply_action(H.DONE)
    assert phase(s) == "WS" and s.current_player() == order[1]
