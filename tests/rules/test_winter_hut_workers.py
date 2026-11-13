"""Phase 4 unit 8: winter hut workers and winter worker sources (R-064, R-066, R-067, R-068,
R-074, R-101, R-102, R-103).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (5.2, A1, C5 windows) and the harness only.
There is no scenario loader, so the winter state is reached by scripted play: seat 0 collects the
craft tokens of a "plain" set (stake, board, shingle) plus the saw and sledge spots in round 1,
hires two bearers, carries two disks to its sawing area, and builds three worker huts. Seeds are
searched until the path gives that holding.

ASSIGN_WORKER(w) = 174 + w: 0 hired, 1 mill worker, 2 hut worker. In winter nobody hires, so
ASSIGN_WORKER(0) must never be legal in N1, N2, N3 (R-064; docs/ACTIONS.md 5.2 agrees).
"""

from __future__ import annotations

import functools
from typing import Any

import pytest

from tests import harness as H
from tests.rules import test_huts as HT
from tests.support import rounds as R
from tests.support import sawmill as SM
from tests.support import travel as T
from tests.support import winter as V
from tests.support import woodwork as W

HIRED, MILL, HUT = W.assign(0), W.assign(1), W.assign(2)
FW_DISK = "firewood_disk"
SAW_IDS = SM.SAW_IDS
BUILD_WORKER_HUTS = (2, 2, 2)


def seat0(s: Any) -> dict[str, Any]:
    return V.seat(V.snap(s), 0)


def huts_left(s: Any) -> int:
    return HT.huts(s)["worker"]


def n_fw(s: Any) -> int:
    return int(V.pm(seat0(s)["woodpile"]).get(FW_DISK, 0))


def _cut(ctx: R.Ctx) -> int | None:
    """W1: cut with hired workers and the mill worker only (never a hut worker)."""
    if ctx.phase != "W1":
        return None
    legal = ctx.legal
    got = [a for a in legal if a in W.TAKE_WOOD_IDS]
    if got:
        return got[0]
    for a in (HIRED, MILL):
        if a in legal:
            return a
    return None


class _Fail(Exception):
    pass


def _carry_to_sawing(state: Any) -> int | None:
    got = [a for a in state.legal_actions() if a in W.MOVE_WOOD_IDS and (a - 195) % 2 == 0]
    return got[0] if got else None


def _build(seed: int, stop: tuple[int, str, int]) -> Any:
    saw = W.spot_loc(2, False, seed, "saw", 0)
    sledge = W.spot_loc(2, False, seed, "sledge", 0)
    bearers = (R.loc(False, "bearers"), [R.HIRE_BEARER, R.HIRE_BEARER, H.DONE])
    tr = HT.Tr0(mand=[(saw, []), (sledge, []), bearers], builds={1: [BUILD_WORKER_HUTS]})
    st = W.Steps()
    for _ in range(2):
        st.add(1, "W3", 0, W.Opt(HIRED), _carry_to_sawing)
    # round 2: one more bearer carries one more disk to the sawing area (round 3: no carry)
    st.add(2, "TR", 0, H.MOVE_TO(R.loc(False, "bearers")), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING)
    st.add(2, "W3", 0, W.Opt(HIRED), _carry_to_sawing)
    # winter bonus: one firewood disk into the woodpile
    st.add(4, "NB", 0, V.TAKE_BONUS0 + 0, W.Opt(H.DONE))
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(st, tr, _cut),
        stop=lambda c: (c.round, c.phase, c.player) == stop,
    )
    if not run.stopped:
        raise _Fail("not reached")
    return run.state


def _ok(s: Any) -> bool:
    me = seat0(s)
    eq = me["equipment"]
    return (
        huts_left(s) == 3
        and eq.get("saw", 0) == 1
        and eq.get("sledge", 0) == 1
        and sum(V.pm(me["sawing"]).values()) >= 2
        and sum(V.pm(me["woodpile"]).values()) >= 1
    )


@functools.cache
def _seed() -> int:
    for seed in range(1, 1500):
        if not HT.is_plain(HT.r1_holding(seed, False)):
            continue
        try:
            s = _build(seed, (4, "N1", 0))
        except (_Fail, AssertionError, IndexError, KeyError):
            continue
        if _ok(s):
            return seed
    raise AssertionError("no seed gives the winter holding")


_CACHE: dict[tuple[int, str, int], Any] = {}


def at_turn(phase: str) -> Any:
    """State at seat 0's turn in winter phase `phase` of round 4, each seat before it passing."""
    key = (4, phase, 0)
    if key not in _CACHE:
        _CACHE[key] = _build(_seed(), key)
    s = _CACHE[key].clone()
    assert V.snap(s)["phase"] == phase and s.current_player() == 0
    return s


def to_next_boundary(s: Any, seat: int = 0) -> dict[str, Any]:
    """End turns (DONE) until the next turn-boundary node of `seat`; return its snapshot."""
    first = True
    for _ in range(100):
        if not first:
            sn = R.try_snapshot(s)
            if sn is not None and s.current_player() == seat and not s.is_chance_node():
                return sn
        first = False
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        else:
            legal = s.legal_actions()
            s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("no boundary")


def _sledge_trip(s: Any, src: int) -> None:
    """A full 2-piece sledge trip by worker source `src`."""
    T.play(s, src, V.USE_SLEDGE)
    for _ in range(2):
        pick = [a for a in s.legal_actions() if a in W.MOVE_WOOD_IDS and (a - 195) % 2 == 0]
        assert pick, f"piece not offered: {s.legal_actions()}"
        s.apply_action(pick[0])
    if V.END_TRIP in s.legal_actions():
        s.apply_action(V.END_TRIP)


def _saw_one(s: Any, src: int) -> None:
    T.play(s, src, SM.saw(0, 0))


# --------------------------------------------------------------------------- precondition


def test_scenario_has_what_the_tests_need():
    """Scenario sanity (not a rule): at N1 seat 0 holds 3 worker huts, one saw, one sledge, two
    disks in the sawing area and wood in the woodpile; mill worker unused, nobody hired."""
    s = at_turn("N1")
    me = seat0(s)
    assert huts_left(s) == 3
    assert me["equipment"]["saw"] == 1 and me["equipment"]["sledge"] == 1
    assert sum(V.pm(me["sawing"]).values()) >= 2
    assert sum(V.pm(me["woodpile"]).values()) >= 2
    assert me["mill_worker_used"] is False
    assert R.total(me["hired"]) == 0


# --------------------------------------------------------------------------- N1


def test_R066_hut_worker_first_action_gives_two_firewood():
    """R-066/R-103: the first winter woodcutting action gives 2 firewood whoever performs it: a
    hut worker doing it first gets 2, its token is spent, the mill worker stays unused."""
    s = at_turn("N1")
    before = n_fw(s)
    assert HUT in s.legal_actions()
    T.play(s, HUT, V.WINTER_CUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    assert V.pm(V.seat(sn, 0)["woodpile"])[FW_DISK] == before + 2
    assert huts_left(s) == 2
    assert V.seat(sn, 0)["mill_worker_used"] is False


def test_R066_second_hut_worker_gives_one_firewood():
    """R-066/R-103: each further woodcutting action gives 1 firewood: two hut workers give
    2 + 1 = 3 and two tokens are spent."""
    s = at_turn("N1")
    before = n_fw(s)
    T.play(s, HUT, V.WINTER_CUT, HUT, V.WINTER_CUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert n_fw(s) == before + 3
    assert huts_left(s) == 1


def test_R066_three_hut_workers_then_mill_worker_give_two_one_one_one():
    """R-066/R-103: three hut workers give 2 + 1 + 1; then ASSIGN_WORKER(2) is no longer legal
    (tokens gone) but the untouched mill worker still cuts for +1 (hut workers are not limited
    by C6)."""
    s = at_turn("N1")
    before = n_fw(s)
    T.play(s, HUT, V.WINTER_CUT, HUT, V.WINTER_CUT, HUT, V.WINTER_CUT)
    assert HUT not in s.legal_actions()
    assert MILL in s.legal_actions()
    T.play(s, MILL, V.WINTER_CUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    assert V.pm(V.seat(sn, 0)["woodpile"])[FW_DISK] == before + 5
    assert huts_left(s) == 0
    assert V.seat(sn, 0)["mill_worker_used"] is True


def test_R066_mill_worker_first_gives_two_then_hut_worker_one():
    """R-066 (FAQ Official): the first action gives 2 whoever performs it; a hut worker acting
    after the mill worker is a further action and gives only 1."""
    s = at_turn("N1")
    before = n_fw(s)
    T.play(s, MILL, V.WINTER_CUT, HUT, V.WINTER_CUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert n_fw(s) == before + 3
    assert huts_left(s) == 2


def test_R066_hut_worker_first_then_mill_worker_gives_one():
    """R-066: the 2 belongs to the first action, not to the mill worker: hut worker first (+2),
    then the mill worker (+1)."""
    s = at_turn("N1")
    before = n_fw(s)
    T.play(s, HUT, V.WINTER_CUT, MILL, V.WINTER_CUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    assert V.pm(V.seat(sn, 0)["woodpile"])[FW_DISK] == before + 3
    assert V.seat(sn, 0)["mill_worker_used"] is True
    assert huts_left(s) == 2


def test_R066_mill_worker_once_but_hut_workers_not_limited():
    """R-066 + C6: after the mill worker cut, ASSIGN_WORKER(1) is not legal again while hut
    workers still are."""
    s = at_turn("N1")
    T.play(s, MILL, V.WINTER_CUT)
    legal = s.legal_actions()
    assert MILL not in legal
    assert HUT in legal


def test_R103_unused_hut_workers_stay_through_winter_woodcutting():
    """R-103: a token not used stays: passing N1 with DONE leaves three tokens and the woodpile
    unchanged."""
    s = at_turn("N1")
    before = seat0(s)["woodpile"]
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert huts_left(s) == 3
    assert seat0(s)["woodpile"] == before


def test_R066_winter_cut_needs_assign_and_exists_only_in_n1():
    """R-066: WINTER_CUT is not legal before ASSIGN_WORKER, nor in N2."""
    s = at_turn("N1")
    assert V.WINTER_CUT not in s.legal_actions()
    assert V.WINTER_CUT not in at_turn("N2").legal_actions()


# --------------------------------------------------------------------------- hired workers


@pytest.mark.parametrize("phase", ["N1", "N2", "N3"])
def test_R064_hired_worker_source_is_never_legal_in_winter(phase):
    """R-064 / ACTIONS 5.2: nobody hires in winter, so ASSIGN_WORKER(0) is not legal in N1, N2 or
    N3 even though seat 0 holds the equipment (sledge, saw) and wood a hired bearer or sawyer
    would need."""
    s = at_turn(phase)
    assert HIRED not in s.legal_actions()


@pytest.mark.parametrize("phase", ["N1", "N2", "N3"])
def test_R103_mill_and_hut_worker_sources_offered_in_winter(phase):
    """R-103 / ACTIONS 5.2: with a free mill worker, a hut token and the equipment and wood the
    work needs, ASSIGN_WORKER(1) and ASSIGN_WORKER(2) are both legal in N1, N2 and N3."""
    legal = at_turn(phase).legal_actions()
    assert MILL in legal
    assert HUT in legal


@pytest.mark.parametrize("phase", ["N1", "N2", "N3"])
def test_R064_hired_worker_still_not_legal_after_a_first_worker(phase):
    """R-064: after a hut worker was committed and acted, ASSIGN_WORKER(0) is still not legal."""
    s = at_turn(phase)
    if phase == "N1":
        T.play(s, HUT, V.WINTER_CUT)
    elif phase == "N2":
        _sledge_trip(s, HUT)
    else:
        _saw_one(s, HUT)
    assert HIRED not in s.legal_actions()


def test_R064_no_hired_workers_on_seat_in_winter():
    """R-064: seat 0 hired two bearers in round 1; at the winter start none remain."""
    assert R.total(seat0(at_turn("N1"))["hired"]) == 0


# --------------------------------------------------------------------------- N2 sledge


def test_R067_hut_worker_sledge_trip_spends_token_and_sledge():
    """R-067/R-103: a hut worker with a sledge moves 2 pieces to the sawing area: the hut token
    and the sledge token are spent; the mill worker stays unused."""
    s = at_turn("N2")
    me = seat0(s)
    sledge0 = me["equipment"]["sledge"]
    pile0 = sum(V.pm(me["woodpile"]).values())
    saw0 = sum(V.pm(me["sawing"]).values())
    assert V.USE_SLEDGE not in s.legal_actions()  # needs ASSIGN_WORKER first
    _sledge_trip(s, HUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    now = V.seat(sn, 0)
    assert now["equipment"]["sledge"] == sledge0 - 1
    assert huts_left(s) == 2
    assert now["mill_worker_used"] is False
    assert sum(V.pm(now["woodpile"]).values()) == pile0 - 2
    assert sum(V.pm(now["sawing"]).values()) == saw0 + 2


def test_R067_each_worker_needs_its_own_sledge():
    """R-067: with one sledge, once a hut worker used it neither the mill worker nor another hut
    worker can transport: no ASSIGN_WORKER and no USE_SLEDGE is offered."""
    s = at_turn("N2")
    _sledge_trip(s, HUT)
    legal = s.legal_actions()
    assert MILL not in legal and HUT not in legal
    assert V.USE_SLEDGE not in legal


def test_R067_mill_worker_sledge_leaves_no_sledge_for_a_hut_worker():
    """R-067 + C6: the mill worker uses the only sledge; a hut worker cannot also transport."""
    s = at_turn("N2")
    _sledge_trip(s, MILL)
    legal = s.legal_actions()
    assert HUT not in legal and MILL not in legal


# --------------------------------------------------------------------------- N3 sawing


def test_R068_hut_worker_saws_a_disk_with_a_saw():
    """R-068/R-103: a hut worker with a saw mills one disk (SAW(0, 0): 4 logs to the sale area):
    the saw and the hut token are spent, the mill worker stays unused."""
    s = at_turn("N3")
    me = seat0(s)
    saw0 = me["equipment"]["saw"]
    disks0 = V.pm(me["sawing"])[FW_DISK]
    logs0 = V.pm(me["sale"])["firewood_log"]
    assert SM.saw(0, 0) not in s.legal_actions()  # needs ASSIGN_WORKER first
    _saw_one(s, HUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    now = V.seat(sn, 0)
    assert V.pm(now["sawing"])[FW_DISK] == disks0 - 1
    assert V.pm(now["sale"])["firewood_log"] == logs0 + 4
    assert now["equipment"]["saw"] == saw0 - 1
    assert huts_left(s) == 2
    assert now["mill_worker_used"] is False


def test_R068_each_worker_needs_its_own_saw():
    """R-068: two sawing actions need two saws: with a single saw, after a hut worker sawed no
    further worker (mill or hut) can be assigned although a disk remains in the sawing area."""
    s = at_turn("N3")
    _saw_one(s, HUT)
    legal = s.legal_actions()
    assert MILL not in legal and HUT not in legal
    assert not [a for a in legal if a in SAW_IDS]


def test_R068_mill_worker_saws_then_hut_worker_blocked_without_second_saw():
    """R-068 + C6: the mill worker sawed with the only saw; a hut worker cannot saw too."""
    s = at_turn("N3")
    _saw_one(s, MILL)
    legal = s.legal_actions()
    assert HUT not in legal and MILL not in legal


# --------------------------------------------------------------------------- counters (C6)


def test_R103_hut_worker_cut_leaves_mill_worker_free_in_n2():
    """R-103 + C6 (worker-use counters): a hut worker used for winter woodcutting does not use up
    the mill worker: ASSIGN_WORKER(1) is legal in N2."""
    s = at_turn("N1")
    T.play(s, HUT, V.WINTER_CUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert V.snap(s)["phase"] == "N2"
    assert MILL in s.legal_actions()


def test_R103_hut_worker_sledge_leaves_mill_worker_free_for_n3():
    """R-103 + C6: a hut worker's sledge trip is neither a hired worker nor the mill worker: in
    N3 the mill worker is unused and legal."""
    s = at_turn("N2")
    _sledge_trip(s, HUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert V.snap(s)["phase"] == "N3"
    assert seat0(s)["mill_worker_used"] is False
    assert MILL in s.legal_actions()


def test_R103_hut_worker_saw_is_not_counted_as_hired_or_mill():
    """R-103: after a hut worker sawed in N3, the mill worker is unused and no hired worker is
    recorded as used."""
    s = at_turn("N3")
    _saw_one(s, HUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    assert V.seat(sn, 0)["mill_worker_used"] is False
    assert R.total(V.seat(sn, 0)["hired"]) == 0


def test_C6_mill_worker_in_n1_blocks_n2_and_n3():
    """C6 / R-066: the mill worker is once per round across woodcut, sledge and sawing: used in
    N1, ASSIGN_WORKER(1) is not legal in N2 or N3; hut workers still are."""
    s = at_turn("N1")
    T.play(s, MILL, V.WINTER_CUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert V.snap(s)["phase"] == "N2"
    assert MILL not in s.legal_actions()
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert V.snap(s)["phase"] == "N3"
    assert MILL not in s.legal_actions()
    assert HUT in s.legal_actions()


def test_C6_mill_worker_in_n2_blocks_n3():
    """C6: the sledge by the mill worker (N2) blocks the mill worker in N3; hut workers stay."""
    s = at_turn("N2")
    _sledge_trip(s, MILL)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    assert V.snap(s)["phase"] == "N3"
    assert seat0(s)["mill_worker_used"] is True
    assert MILL not in s.legal_actions()
    assert HUT in s.legal_actions()


def test_C6_mill_worker_in_n3_is_spent_and_resets_in_spring():
    """C6 / R-074: the mill worker used for sawing in N3 is spent for the rest of winter and is
    back (flag cleared) at the start of round 5."""
    s = at_turn("N3")
    _saw_one(s, MILL)
    assert MILL not in s.legal_actions()
    s.apply_action(H.DONE)
    to_next_boundary(s)
    for _ in range(300):
        sn = R.try_snapshot(s)
        if sn is not None and sn["round"] == 5:
            break
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        else:
            legal = s.legal_actions()
            s.apply_action(H.DONE if H.DONE in legal else legal[0])
    assert seat0(s)["mill_worker_used"] is False


def test_R103_one_hut_worker_in_each_winter_phase():
    """R-103: three tokens, one used in each of N1, N2, N3 (each phase has its own work):
    all three are spent at the end and the mill worker is still unused."""
    s = at_turn("N1")
    T.play(s, HUT, V.WINTER_CUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    _sledge_trip(s, HUT)
    s.apply_action(H.DONE)
    to_next_boundary(s)
    _saw_one(s, HUT)
    s.apply_action(H.DONE)
    sn = to_next_boundary(s)
    assert huts_left(s) == 0
    assert V.seat(sn, 0)["mill_worker_used"] is False


# --------------------------------------------------------------------------- huts in winter

HUT_IDS = HT.HUT_IDS


def test_R102_hut_food_and_dry_windows_open_at_winter_turns():
    """R-102/R-074/C5: seat 0 has worker huts only, so no HUT_FOOD/HUT_DRY is legal in winter
    (nothing to spend); BUILD_HUT is not legal either (no craft tokens left)."""
    s = at_turn("N1")
    assert not [a for a in s.legal_actions() if a in HUT_IDS]


def _to_sale(state: Any) -> int | None:
    got = [a for a in state.legal_actions() if a in W.MOVE_WOOD_IDS and (a - 195) % 2 == 1]
    return got[0] if got else None


def test_R074_drying_hut_still_moves_wood_in_winter():
    """R-074/R-101: a drying hut token moves 1 piece one area right in a winter turn although wood
    does not dry then: seat 0 builds three drying huts and carries one piece to its sale area in
    round 1; at its N1 turn HUT_DRY from the sale area is legal, moves the piece into drying
    area 1 and spends one token."""
    seed = HT.find_seed("plain")
    bearers = (R.loc(False, "bearers"), [R.HIRE_BEARER, H.DONE])
    tr = HT.Tr0(mand=[bearers], builds={1: [(0, 0, 0)]})
    st = W.Steps().add(1, "W3", 0, W.Opt(HIRED), _to_sale)
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(st, tr, _cut),
        stop=lambda c: (c.round, c.phase, c.player) == (4, "N1", 0),
    )
    assert run.stopped
    s = run.state
    me = seat0(s)
    sale0 = sum(V.pm(me["sale"]).values())
    assert HT.huts(s)["drying"] == 3
    assert sale0 >= 1, "scenario: a piece should be in the sale area"
    dry = [a for a in s.legal_actions() if a in HT.HUT_DRY_IDS]
    assert dry, "drying hut must work in winter"
    assert HT.hut_dry(0, 0) in dry or HT.hut_dry(0, 1) in dry
    s.apply_action(HT.hut_dry(0, 0) if HT.hut_dry(0, 0) in dry else HT.hut_dry(0, 1))
    s.apply_action(H.DONE)
    to_next_boundary(s)
    now = seat0(s)
    assert sum(V.pm(now["sale"]).values()) == sale0 - 1
    assert sum(V.pm(now["drying"][0]).values()) == 1
    assert HT.huts(s)["drying"] == 2


def test_R102_food_hut_takes_area_food_in_winter():
    """R-102: hut food in winter is legal for any area holding food (every area is free); the
    existing R-102 winter test covers it; here the window also stays open after a hut worker
    action is not required: HUT_FOOD is a window action, ASSIGN_WORKER is not."""
    seed = HT._winter_seed()  # pyright: ignore[reportPrivateUsage]
    tr = HT.Tr0(builds={1: [(1, 1, 1)]})
    run = R.drive(
        {"players": 2, "joinery": False},
        seed=seed,
        policy=R.chain(tr, _cut),
        stop=lambda c: (c.round, c.phase, c.player) == (4, "N1", 0),
    )
    s = run.state
    sn = T.snap(s)
    foods = [R.food(a) for a in H.areas(sn)]
    a = next(a for a, f in enumerate(foods) if f > 0)
    assert HT.hut_food(a) in s.legal_actions()
    # a non-window action (the winter cut with the mill worker) closes the window
    T.play(s, MILL, V.WINTER_CUT)
    assert HT.hut_food(a) not in s.legal_actions()


def test_R102_winter_food_hut_reaches_an_area_a_seat_picked_in_the_fall():
    """R-102: in winter every area is free, including one that held a seat's token in the round-3
    fall and still holds food: HUT_FOOD for that area is legal at the N1 turn."""
    s = HT.winter_picked_state()
    picked = s._test_round3_areas  # pyright: ignore[reportAttributeAccessIssue]
    foods = [R.food(a) for a in H.areas(T.snap(s))]
    stocked = [a for a in picked if foods[a] > 0]
    assert stocked
    for a in stocked:
        assert HT.hut_food(a) in s.legal_actions()
