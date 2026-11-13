"""Phase 2 unit 9: end of round (R-060 player order, R-061 cleanup, R-063 both sides).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and the round
driver in tests/support/rounds.py.

Notes
  * The end of a round leads to chance nodes (and dump_scenario raises S-NOTDECISION there), so
    results are read at the first decision node of the next round (`Event.after`) and compared to
    the last turn-boundary snapshot of the finished round (`Event.before`, the last seat's W7).
  * R-061 holds identically with joinery true and false (R-063), so the cleanup tests are
    parametrized over both sides.
  * Winter has no travel, so the order after fall is read from the winter start and from the
    following spring (R-060, O-U2-7).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R

PLAYERS = (2, 3, 4)
BOOLS = (False, True)
RESET_KEYS = (
    "foreman",
    "cutting_area",
    "hired",
    "mill_worker_used",
    "task_taken",
    "fodder_bought",
)


def _params(n: int, joinery: bool) -> dict[str, Any]:
    return {"players": n, "joinery": joinery}


def _seats(snap: dict[str, Any]) -> list[dict[str, Any]]:
    return H.seats(snap)


def _late_p0(j: bool) -> list[Any]:
    """P0 visits Bearers first and only then enters the clearing, so everyone else gets a lower
    clearing slot: clearing order is P1, P2, ..., P0 (R-040, R-044)."""
    return [R.move(j, "bearers"), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING]


def _spend_all_p0(j: bool) -> list[Any]:
    """P0 hires 2 bearers, buys fodder, hires 2 woodcutters and 1 free sawyer ($5 in total)."""
    return [
        R.move(j, "bearers"), R.HIRE_BEARER, R.HIRE_BEARER, H.DONE,
        R.move(j, "fodder"), R.BUY_FODDER,
        R.move(j, "woodcutters"), R.HIRE_WOODCUTTER, R.HIRE_WOODCUTTER, H.DONE,
        R.move(j, "sawyers"), R.HIRE_SAWYER, H.DONE,
        R.MOVE_CLEARING,
    ]  # fmt: skip


def _cheap_p0(j: bool) -> list[Any]:
    """P0 hires 2 bearers and the free sawyer, then enters the clearing."""
    return [
        R.move(j, "bearers"), R.HIRE_BEARER, R.HIRE_BEARER, H.DONE,
        R.move(j, "sawyers"), R.HIRE_SAWYER, H.DONE,
        R.MOVE_CLEARING,
    ]  # fmt: skip


def _late_script(n: int, j: bool, rounds: tuple[int, ...]) -> R.Script:
    return R.Script({(r, 0): _late_p0(j) for r in rounds})


# --------------------------------------------------------------------------- R-060


@pytest.mark.parametrize("n", PLAYERS)
def test_R060_next_order_is_reverse_of_clearing_order(n):
    """R-060: after phase 7 the next round's starting-player order is the reverse of the clearing
    order (last slot first, slot A last). P0 enters the clearing last, so clearing = P1..Pn-1, P0
    and the next order is P0, Pn-1, ..., P1."""
    run = R.drive(
        _params(n, False), seed=5, policy=_late_script(n, False, (1,)), stop=lambda c: c.round == 2
    )
    ev = run.event(2)
    assert ev.before["clearing_order"] == list(range(1, n)) + [0]
    assert ev.after["turn_order"] == [0] + list(range(n - 1, 0, -1))


@pytest.mark.parametrize("n", PLAYERS)
def test_R060_default_clearing_p0_first_makes_p0_last_next_round(n):
    """R-060 + R-044: entering the clearing first gives the last place in the next round's travel.
    Everyone enters in seat order (A=P0, ...), so the next order is Pn-1, ..., P0."""
    run = R.drive(_params(n, False), seed=5, stop=lambda c: c.round == 2)
    ev = run.event(2)
    assert ev.before["clearing_order"] == list(range(n))
    assert ev.after["turn_order"] == list(range(n - 1, -1, -1))


@pytest.mark.parametrize("n", PLAYERS)
def test_R060_order_is_a_permutation_and_drives_next_travel(n):
    """R-060: the new order is a permutation of the seats, and the first foreman to move in the
    next round's travel is the seat in starting-player position 1."""
    run = R.drive(
        _params(n, False),
        seed=7,
        policy=_late_script(n, False, (1,)),
        stop=lambda c: c.round == 2 and c.phase == "TR",
    )
    assert run.stopped
    ev = run.event(2)
    order = ev.after["turn_order"]
    assert sorted(order) == list(range(n))
    assert run.state.current_player() == order[0]
    sn = R.try_snapshot(run.state)
    assert sn is not None and sn["turn_order"] == order


def test_R060_order_follows_clearing_not_previous_order_or_seat_number():
    """R-060: only the clearing order matters. Round 1: P0 late (clearing P1, P0) gives next order
    P0, P1. In round 2 (order P0, P1) P0 enters first (A=P0), so round 3 order is P1, P0."""
    run = R.drive(
        _params(2, False),
        seed=3,
        policy=_late_script(2, False, (1,)),
        stop=lambda c: c.round == 3,
    )
    assert run.event(2).after["turn_order"] == [0, 1]
    assert run.event(2).before["clearing_order"] == [1, 0]
    assert run.event(3).before["clearing_order"] == [0, 1]
    assert run.event(3).after["turn_order"] == [1, 0]


@pytest.mark.parametrize("n", PLAYERS)
def test_R060_fall_clearing_is_winter_turn_order_and_next_spring_order(n):
    """R-060 / O-U2-7: after fall (round 3) the order is set from the fall clearing as usual; the
    winter phases use the fall clearing order unchanged (R-064), and the order set after fall
    stays unchanged through winter into round 5."""
    run = R.drive(
        _params(n, False),
        seed=11,
        policy=_late_script(n, False, (3,)),
        stop=lambda c: c.round == 5,
    )
    fall_clearing = run.event(4).before["clearing_order"]
    assert fall_clearing[-1] == 0 and sorted(fall_clearing) == list(range(n))
    want = list(reversed(fall_clearing))
    w = run.event(4).after
    assert w["round"] == 4
    assert w["turn_order"] == want
    assert w["clearing_order"] == fall_clearing
    assert run.event(5).after["turn_order"] == want


def test_R060_winter_does_not_form_a_new_clearing_order():
    """R-060: winter has no supply path, so no new clearing order is formed: the order set after
    round 7 (not round 3's winter) is used the same way after round 7 -> winter 8, and round 8's
    clearing order equals round 7's."""
    # P0 is broke after winter year 1 (R-073), so it cannot enter Bearers; it takes the first
    # enterable (free) token spot before the clearing, which makes it the last in clearing order.
    late = R.Script({(7, 0): [R.first_legal(H.MOVE_TO(1), H.MOVE_TO(22)), R.MOVE_CLEARING]})
    run = R.drive(
        _params(2, False),
        seed=13,
        policy=late,
        stop=lambda c: c.round == 8,
    )
    assert run.event(8).after["clearing_order"] == run.event(8).before["clearing_order"] == [1, 0]
    assert run.event(8).after["turn_order"] == [0, 1]


# --------------------------------------------------------------------------- R-061


def _cleanup_run(n: int, j: bool, seed: int = 4):
    steps = R.chain(R.Script({(1, 0): _spend_all_p0(j)}), R.cut_all_wood)
    return R.drive(_params(n, j), seed=seed, policy=steps, stop=lambda c: c.round == 2)


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R061_hired_workers_all_return_used_or_not(n, joinery):
    """R-061 step 1: hired bearers, woodcutters and sawyers, used or not, go back to the path.
    P0 hired 2 bearers, 2 woodcutters, 1 sawyer; at the end of W7 they are still counted as hired,
    and in round 2 every seat's hired counts are 0 and the path holds the full R-013 count."""
    run = _cleanup_run(n, joinery)
    ev = run.event(2)
    assert _seats(ev.before)[0]["hired"] == {"woodcutters": 2, "bearers": 2, "sawyers": 1}
    q = R.quantities(n)
    for s in _seats(ev.after):
        assert R.total(s["hired"]) == 0
    p = ev.after["path"]
    assert p["bearers"] == q["bearers_on_path"]
    assert p["woodcutters"] == q["woodcutters_on_path"]
    assert p["sawyers_free"] == q["sawyers_price_0"]
    assert p["sawyers_paid"] == q["sawyers_price_1"]
    assert p["fodder"] == q["fodder_on_path"]


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R061_mill_workers_foremen_and_cutting_tokens_reset(n, joinery):
    """R-061 step 2: mill workers return to their worker areas (unused), foremen go to location 0,
    cutting-area tokens go back to their owners (no seat has a cutting area at the picks)."""
    run = _cleanup_run(n, joinery)
    ev = run.event(2)
    assert any(s["mill_worker_used"] for s in _seats(ev.before))
    assert all(s["foreman"] in ("A", "B", "C", "D") for s in _seats(ev.before))
    for s in _seats(ev.after):
        assert s["mill_worker_used"] is False
        assert s["foreman"] == 0
        assert s["cutting_area"] is None
        assert s["task_taken"] is False
        assert s["fodder_bought"] is False
    assert ev.after["clearing_order"] is None


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R061_seat_holdings_unchanged_by_cleanup(n, joinery):
    """R-061 last paragraph: tokens, money, food, fodder, tasks, plans and wood held by seats are
    unchanged by cleanup (only the per-round fields reset). Joinery side has no income here
    because no joiners are owned (R-079)."""
    run = _cleanup_run(n, joinery)
    ev = run.event(2)
    b = [{k: v for k, v in s.items() if k not in RESET_KEYS} for s in _seats(ev.before)]
    a = [{k: v for k, v in s.items() if k not in RESET_KEYS} for s in _seats(ev.after)]
    # the bought fodder and a woodpile with cut wood must be part of what is compared
    assert b[0]["fodder"]["slot3"] is True and R.total(b[0]["woodpile"]) > 0
    assert a == b


@pytest.mark.parametrize("joinery", BOOLS)
def test_R061_wood_and_food_left_in_cutting_areas_stay(joinery):
    """R-061: wood and food left in the cutting areas stay. Round start only adds (placement cards,
    extra firewood: R-037), so no area ends round 2's start with less of anything than the end of
    round 1."""
    run = _cleanup_run(2, joinery)
    ev = run.event(2)
    assert R.total([a["wood"] for a in ev.before["cutting_areas"]]) < 6 * 3 + 1  # some cut away
    for ba, aa in zip(ev.before["cutting_areas"], ev.after["cutting_areas"], strict=True):
        for k, v in R.wood(ba).items():
            assert R.wood(aa)[k] >= v
        assert R.food(aa) >= R.food(ba)


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R061_leftover_craftwork_tokens_leave_the_game(n, joinery):
    """R-061 step 3: craftwork tokens still on the path are removed from the game: the
    craftwork_removed count grows by exactly the craftwork left on the path at the end of the
    round (no seat takes any here; the finished round's path is read at W7)."""
    run = R.drive(_params(n, joinery), seed=6, stop=lambda c: c.round == 3)
    for rnd in (2, 3):
        ev = run.event(rnd)
        left = sum(1 for v in H.tokens(ev.before).values() if v in R.CRAFT)
        assert left > 0
        prev = R.total(run.event(rnd - 1).after["supply"]["craftwork_removed"])
        now = R.total(ev.after["supply"]["craftwork_removed"])
        assert now - prev == left, rnd


@pytest.mark.parametrize("joinery", BOOLS)
def test_R061_leftover_equipment_tokens_return_to_supply_not_removed(joinery):
    """R-061 step 3: leftover equipment tokens return to the supply (usable in later fills), so
    they never count as removed from the game; the craftwork pile is the only thing that runs
    out. Every fill still has the full R-017 equipment mix even though nobody took any token."""
    n = 3
    run = R.drive(_params(n, joinery), seed=8)
    want = R.token_mix(n)
    for rnd in (2, 3, 5, 6, 7):
        toks = list(H.tokens(run.event(rnd).after).values())
        for kind, cnt in want.items():
            assert toks.count(kind) == cnt, (rnd, kind)
        assert not any(
            k in run.event(rnd).after["supply"].get("equipment_removed", {}) for k in want
        )


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R061_after_fall_next_round_is_winter_with_everything_reset(n, joinery):
    """R-061 steps 2, 4, 5: also after fall, before winter: workers and foremen reset, phase
    marker at position 1 (first winter phase), season marker advances to round 4, no path in
    winter and no cutting-area tokens."""
    steps = R.Script({(3, 0): _cheap_p0(joinery)})
    run = R.drive(_params(n, joinery), seed=9, policy=steps, stop=lambda c: c.round == 4)
    ev = run.event(4)
    assert ev.before["round"] == 3 and ev.after["round"] == 4
    assert ev.after["phase"] in ("WS", "NB")
    for s in _seats(ev.after):
        assert R.total(s["hired"]) == 0
        assert s["foreman"] == 0
        assert s["mill_worker_used"] is False
        assert s["cutting_area"] is None
    assert ev.after["path"] is None


@pytest.mark.parametrize("joinery", BOOLS)
def test_R061_after_winter_spring_starts_fresh_seasonal_round(joinery):
    """R-061 step 5: after winter year 1 the next round is spring year 2 (round 5), which starts
    with the seasonal round-start steps: hidden-pick phase first, a fresh 13-token path, a full set
    of workers and no foremen away from location 0."""
    run = R.drive(_params(2, joinery), seed=10, stop=lambda c: c.round == 5)
    after = run.event(5).after
    assert after["round"] == 5 and after["phase"] == "PK"
    assert len(H.tokens(after)) == 13
    assert all(s["foreman"] == 0 and R.total(s["hired"]) == 0 for s in _seats(after))


def test_R061_every_seasonal_round_ends_with_the_same_reset():
    """R-061: the reset is identical in every seasonal round (2 players, default play): at rounds
    2, 3, 5, 6, 7 every seat is back on location 0, nothing hired, no cutting-area token placed,
    clearing order cleared."""
    run = R.drive(_params(2, False), seed=12)
    for rnd in (2, 3, 5, 6, 7):
        a = run.event(rnd).after
        assert a["clearing_order"] is None
        assert all(
            s["foreman"] == 0 and R.total(s["hired"]) == 0 and s["cutting_area"] is None
            for s in _seats(a)
        )


def test_R061_unspent_loan_and_task_holdings_survive():
    """R-061: tasks, loans and money are unchanged by cleanup. P0 takes a loan and a task card in
    round 1 (still held in round 2)."""
    j = False
    pol = R.Script(
        {
            (1, 0): [
                H.TAKE_LOAN,
                R.move(j, "tasks"),
                R.first_legal(R.TAKE_TASK0, R.TAKE_TASK_END),
                R.MOVE_CLEARING,
            ]
        }
    )
    run = R.drive(_params(2, j), seed=2, policy=pol, stop=lambda c: c.round == 2)
    ev = run.event(2)
    b, a = _seats(ev.before)[0], _seats(ev.after)[0]
    assert b["loans"] == 1 and len(b["tasks"]) == 1
    assert a["loans"] == 1 and a["tasks"] == b["tasks"]
    assert a["money"] == b["money"]


# --------------------------------------------------------------------------- R-063


@pytest.mark.parametrize("n", PLAYERS)
def test_R063_player_order_is_identical_on_both_sides(n):
    """R-063: R-058..R-061 are identical with joinery true and false: the same play gives the same
    clearing order and the same next-round starting order on both sides."""
    base = R.drive(
        _params(n, False), seed=5, policy=_late_script(n, False, (1,)), stop=lambda c: c.round == 2
    )
    join = R.drive(
        _params(n, True), seed=5, policy=_late_script(n, True, (1,)), stop=lambda c: c.round == 2
    )
    assert base.event(2).before["clearing_order"] == join.event(2).before["clearing_order"]
    assert base.event(2).after["turn_order"] == join.event(2).after["turn_order"]


def test_R063_joiners_are_not_workers_and_stay_with_the_seat_through_cleanup():
    """R-063/R-061: a joiner taken in round 1 is not a hired worker; cleanup does not return it
    to the path. It stays with the seat (the Joiner location is stocked again by R-035)."""
    pol = R.Script({(1, 0): [R.move(True, "joiner"), R.MOVE_CLEARING]})
    run = R.drive(_params(2, True), seed=1, policy=pol, stop=lambda c: c.round == 2)
    ev = run.event(2)
    assert _seats(ev.before)[0]["joiners"] == 1
    assert _seats(ev.after)[0]["joiners"] == 1
    assert ev.after["path"]["joiner"] == 1  # refilled, not "returned"
