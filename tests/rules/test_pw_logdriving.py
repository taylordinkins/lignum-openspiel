"""Phase 4 unit 7: PW Log Driving (R-098; R-053 raft placement, R-049 arrival, R-050 transport,
R-081 final sale, R-093 Food Supply interplay; ACTIONS 5.8 trips).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and tests/harness.py only; states come from
scripted play (tests/support/pwscen.py). The Waterchannel interaction is unit 10 and is not tested.

Conventions
  * USE_PW_LOGDRIVING = 212, RIVER_MOVE(k) = 201 + k, END_TRIP = 213, ASSIGN_WORKER(w) = 174 + w,
    MOVE_WOOD(k, d) = 195 + 2k + d. 2 players, base side (Woodcutters 10, Bearers 4).
  * Scenario: P0 plans Log Driving (card index in planned_work.yaml) in round r with pair p; in the
    action round it hires 3 woodcutters and cuts 4 pieces (3 hired + mill worker), so the woodpile
    holds 4 pieces at its W3 turn and no bearer is hired (unless `raft`: then also 1 bearer and
    >= 1 raft from a round-1 path spot). Stops at P0's W3 turn of the action round.
"""

from __future__ import annotations

from typing import Any

from tests import harness as H
from tests.support import pwscen as P
from tests.support import rounds as R
from tests.support import woodwork as W

USE_PW_LD = 212
END_TRIP = 213
RIVER = range(201, 204)
MOVE_WOOD = range(195, 201)
ASSIGN = range(174, 177)
LAYOUT = [P.LOG, P.CUT, P.TRADE, P.CRAFT]
LAYOUT_FS = [P.LOG, P.FOODS, P.TRADE, P.CRAFT]


def maybe_take(state: Any) -> int | None:
    """First legal TAKE_WOOD, or None (entry skipped) when the area is already empty."""
    got = [a for a in state.legal_actions() if a in W.TAKE_WOOD_IDS]
    return got[0] if got else None


def ld(
    key: str,
    *,
    plans0: list[tuple[int, int, int]] | None = None,
    plans1: list[tuple[int, int, int]] | None = None,
    act: int = 2,
    raft: bool = False,
    cut: bool = True,
    cards: list[int] | None = None,
    stop: tuple[Any, ...] | None = None,
    hire: int = 3,
    need: int = 4,
) -> Any:
    """plans are (round, card, pair). Default: P0 plans Log Driving in round act-1 (pair 1)."""
    if plans0 is None:
        plans0 = [(act - 1, P.LOG, 1)]
    wants: dict[tuple[int, int], list[Any]] = {}
    for seat, plans in ((0, plans0), (1, plans1 or [])):
        for rnd, card, pair in plans:
            wants.setdefault((rnd, seat), []).append(("plan", card, pair))
    if raft:
        wants.setdefault((1, 0), []).append(("spots", ("raft",), 1))
    if cut:
        wants.setdefault((act, 0), [])
        if hire:
            wants[(act, 0)].append(("hire", "woodcutters", hire))
        if raft:
            wants[(act, 0)].append(("hire", "bearers", 1))

    def steps() -> W.Steps:
        st = W.Steps()
        if cut:
            st.add(act, "W1", 0, *W.cut(hire, -1, 0), W.Opt(W.assign(1)), maybe_take)
        return st

    def check(s: Any) -> bool:
        if not cut:
            return True
        n = sum(W.zone(P.snap(s), 0, "woodpile").values())
        return n >= need and (not raft or P.me(s)["equipment"]["raft"] >= 1)

    return P.reach(key, cards or LAYOUT, wants, steps, stop or ("node", act, "W3", 0), check)


def count(s: Any, name: str, seat: int = 0) -> int:
    return sum(W.zone(P.snap(s), seat, name).values())


def at_boundary(s: Any) -> None:
    """Close the trip and the turn until a turn-boundary snapshot exists (none mid-turn)."""
    for _ in range(6):
        if R.try_snapshot(s) is not None:
            return
        legal = s.legal_actions()
        s.apply_action(END_TRIP if END_TRIP in legal else H.DONE)
    raise AssertionError("no boundary reached")


def drive_trip(s: Any, pieces: int) -> int:
    """Place `pieces` via RIVER_MOVE (first legal kind each time); returns how many were placed."""
    placed = 0
    for _ in range(pieces):
        opts = P.legal_in(s, RIVER)
        if not opts:
            break
        s.apply_action(opts[0])
        placed += 1
    return placed


# --------------------------------------------------------------------------- availability


def test_R098_offered_in_the_target_round_without_bearer_or_raft():
    """R-098: the holder with pieces in its woodpile may start PW Log Driving at its transport
    turn in the target round with no bearer, no mill worker and no raft token."""
    s = ld("ld_plain")
    assert count(s, "woodpile") >= 4
    assert P.me(s)["equipment"]["raft"] == 0
    assert P.me(s)["hired"]["bearers"] == 0
    assert USE_PW_LD in s.legal_actions()
    assert not P.legal_in(s, ASSIGN)  # no worker available at all, so the trip is worker-free


def test_R098_not_legal_without_a_plan():
    """R-098 baseline: the same board with no Log Driving plan: 212 is never legal."""
    s = ld("ld_noplan", plans0=[])
    assert count(s, "woodpile") >= 4
    assert USE_PW_LD not in s.legal_actions()
    assert not P.legal_in(s, RIVER)


def test_R098_other_seats_plan_does_not_give_it_to_me():
    """R-098 / R-089: only P1 planned Log Driving for round 2; P0 may not use it."""
    s = ld("ld_other", plans0=[], plans1=[(1, P.LOG, 1)])
    assert USE_PW_LD not in s.legal_actions()


def test_R098_not_legal_in_the_planning_round():
    """R-098 / R-089: planned in round 1 (target round 2), not usable in round 1's phase 3."""
    s = ld("ld_planning_round", plans0=[(1, P.LOG, 1)], act=1, need=3)
    assert count(s, "woodpile") >= 3
    assert USE_PW_LD not in s.legal_actions()


def test_R098_not_legal_in_the_round_after_the_target():
    """R-098: planned in round 1 for round 2; in round 3 it is gone."""
    s = ld("ld_after_target", plans0=[(1, P.LOG, 1)], act=3)
    assert count(s, "woodpile") >= 4
    assert USE_PW_LD not in s.legal_actions()


def test_R098_not_offered_when_the_woodpile_is_empty():
    """R-098 / ACTIONS 5.8: a trip start needs a piece to move. Holder with an empty woodpile."""
    s = ld("ld_empty_pile", cut=False)
    assert count(s, "woodpile") == 0
    assert USE_PW_LD not in s.legal_actions()
    assert not P.legal_in(s, RIVER)


# --------------------------------------------------------------------------- the trip


def test_R098_places_up_to_three_pieces_without_spending_equipment():
    """R-098: up to 3 pieces go from the woodpile to the river; no raft, no worker is spent. The
    trip closes by itself at 3 and a fourth piece cannot be placed this way."""
    s = ld("ld_plain")
    pile0 = count(s, "woodpile")
    s.apply_action(USE_PW_LD)
    assert drive_trip(s, 3) == 3
    assert not P.legal_in(s, RIVER), "no fourth PW placement"
    assert USE_PW_LD not in s.legal_actions()
    at_boundary(s)
    assert count(s, "woodpile") == pile0 - 3
    assert count(s, "river") == 3
    assert P.me(s)["equipment"]["raft"] == 0
    assert P.me(s)["mill_worker_used"] is True  # used for cutting only; unchanged by the trip


def test_R098_may_stop_after_fewer_pieces_but_not_before_the_first():
    """R-098 ('up to 3'): END_TRIP is not legal before a piece is placed; after 1 piece it ends
    the trip and only 1 piece is on the river."""
    s = ld("ld_plain")
    s.apply_action(USE_PW_LD)
    assert END_TRIP not in s.legal_actions()
    assert P.legal_in(s, RIVER)
    s.apply_action(P.legal_in(s, RIVER)[0])
    assert END_TRIP in s.legal_actions()
    s.apply_action(END_TRIP)
    at_boundary(s)
    assert count(s, "river") == 1
    assert count(s, "woodpile") >= 3


def test_R098_only_one_pw_trip_per_turn_so_at_most_three_pieces():
    """R-098: after a 2-piece trip is ended, a second USE_PW_LOGDRIVING is not legal in the same
    transport turn (the plan gives 3 pieces in all)."""
    s = ld("ld_plain")
    s.apply_action(USE_PW_LD)
    assert drive_trip(s, 2) == 2
    s.apply_action(END_TRIP)
    assert USE_PW_LD not in s.legal_actions()


def test_R098_pieces_stay_on_the_river_and_do_not_reach_the_sawmill_this_round():
    """R-098 / R-053: placed pieces are on the river, not in the sawing or sale area, and the
    mill-area counts are unchanged at the end of the turn."""
    s = ld("ld_plain")
    s0 = (count(s, "sawing"), count(s, "sale"))
    s.apply_action(USE_PW_LD)
    drive_trip(s, 3)
    at_boundary(s)
    assert (count(s, "sawing"), count(s, "sale")) == s0
    assert count(s, "river") == 3


# --------------------------------------------------------------------------- with rafts


def test_R098_raft_driving_may_follow_pw_driving_in_the_same_turn():
    """R-098: PW Log Driving (3 pieces) and then ordinary raft driving with a bearer and a raft
    (1 piece) in the same turn: 4 pieces on the river, the raft is spent, the bearer is used."""
    s = ld("ld_raft", raft=True)
    pile0 = count(s, "woodpile")
    rafts0 = P.me(s)["equipment"]["raft"]
    assert pile0 >= 4 and rafts0 >= 1
    assert USE_PW_LD in s.legal_actions()
    s.apply_action(USE_PW_LD)
    assert drive_trip(s, 3) == 3
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    assert W.assign(0) in s.legal_actions(), "the bearer is still free for a raft trip"
    s.apply_action(W.assign(0))
    assert P.legal_in(s, RIVER)
    s.apply_action(P.legal_in(s, RIVER)[0])
    at_boundary(s)
    assert count(s, "river") == 4
    assert count(s, "woodpile") == pile0 - 4
    assert P.me(s)["equipment"]["raft"] == rafts0 - 1


def test_R098_raft_driving_first_then_pw_driving_in_the_same_turn():
    """R-098 (either order within the turn): a raft trip first, then PW Log Driving is still
    offered and takes up to 3 more pieces."""
    s = ld("ld_raft", raft=True)
    pile0 = count(s, "woodpile")
    s.apply_action(W.assign(0))
    s.apply_action(P.legal_in(s, RIVER)[0])
    if END_TRIP in s.legal_actions():
        s.apply_action(END_TRIP)
    assert USE_PW_LD in s.legal_actions()
    s.apply_action(USE_PW_LD)
    assert drive_trip(s, 3) == 3
    at_boundary(s)
    assert count(s, "river") == 4
    assert count(s, "woodpile") == pile0 - 4


# --------------------------------------------------------------------------- arrival


def test_R098_pieces_arrive_in_the_next_rounds_phase_2():
    """R-098 / R-049: wood placed in round 2 is on the river at round 3's log-driving phase and
    can be moved to the sawing or sale area there (3 pieces)."""
    s = ld("ld_plain")
    s.apply_action(USE_PW_LD)
    drive_trip(s, 3)
    at_boundary(s)
    s = P.advance(
        s,
        lambda sn, st: (sn["round"], sn["phase"]) == (3, "W2") and st.current_player() == 0,
    )
    assert count(s, "river") == 3
    base = count(s, "sawing") + count(s, "sale")
    moved = 0
    for _ in range(3):
        opts = P.legal_in(s, MOVE_WOOD)
        assert opts, "arriving piece must be placeable"
        s.apply_action(opts[0])
        moved += 1
        if R.try_snapshot(s) is not None and count(s, "river") == 0:
            break
    assert moved == 3
    if R.try_snapshot(s) is None:
        at_boundary(s)
    assert count(s, "river") == 0
    assert count(s, "sawing") + count(s, "sale") == base + 3


def test_R098_round7_placement_stays_on_the_river_into_winter():
    """R-098 / R-049 / R-053: wood placed in round 7 never arrives. Round 8 (winter) starts with
    the placed pieces still on the river. (Money is scarce by round 7, so only the mill worker
    cuts: 1 piece.)"""
    s = ld("ld_r7", plans0=[(6, P.LOG, 1)], act=7, hire=0, need=1)
    s.apply_action(USE_PW_LD)
    placed = drive_trip(s, 3)
    assert placed >= 1
    at_boundary(s)
    s = P.advance(s, lambda sn, st: sn["round"] == 8)
    assert count(s, "river") == placed


# --------------------------------------------------------------------------- Food Supply link


def test_R098_counts_as_river_placement_for_pw_food_supply():
    """R-098 / R-093: P0 holds Log Driving (planned round 1, pair 2) and Food Supply (planned
    round 2, pair 1), both targeting round 3. Placing 3 pieces by PW Log Driving without a raft
    gives 2 food per piece (6)."""
    s = ld(
        "ld_food",
        plans0=[(1, P.LOG, 2), (2, P.FOODS, 1)],
        act=3,
        cards=LAYOUT_FS,
    )
    food0 = P.me(s)["food"]
    s.apply_action(USE_PW_LD)
    assert drive_trip(s, 3) == 3
    at_boundary(s)
    assert P.me(s)["food"] == food0 + 6


def test_R098_gives_no_food_without_the_food_supply_plan():
    """R-093/R-098 baseline: Log Driving alone gives no food."""
    s = ld("ld_food_none", plans0=[(1, P.LOG, 2)], act=3, cards=LAYOUT_FS)
    food0 = P.me(s)["food"]
    s.apply_action(USE_PW_LD)
    drive_trip(s, 3)
    at_boundary(s)
    assert P.me(s)["food"] == food0
