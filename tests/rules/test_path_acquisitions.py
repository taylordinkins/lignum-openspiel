"""Phase 2 unit 6: acquisitions on the supply path and loans (R-041, R-042, R-043, R-076).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py, tests/support/rounds.py and tests/support/travel.py (public API only).

Conventions
  * A visit is `MOVE_TO(loc)`, then acquisitions, then DONE; single-acquisition locations (Fodder,
    Tasks, token spots, Joiner) end the visit automatically (ACTIONS 1.4), so no DONE follows.
  * Mid-visit states have no scenario dump (SCENARIOS 1.3): money and holdings are read from the
    dump taken when the next seat is to move.
  * After the last possible multi-unit acquisition (money or supply used up) the spec does not
    say whether the visit closes by itself; helpers close it with DONE only if it is still open
    (`travel.end_visit`). Assertions about legality right after the last hire hold either way.
  * Market, Planned work and Buildings are Phase-4 content and are not exercised.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

PLAYERS = (2, 3, 4)
BOOLS = (True, False)
TAKE_TASKS = range(R.TAKE_TASK0, R.TAKE_TASK_END + 1)


def _take_task_id(task: str) -> int:
    return R.TAKE_TASK0 + R.task_ids().index(task)


def _legal_tasks(s: Any) -> list[int]:
    return sorted(a for a in s.legal_actions() if a in TAKE_TASKS)


# --------------------------------------------------------------------------- R-041 Bearers


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R041_bearers_cost_one_dollar_each_and_go_to_the_worker_area(n, joinery):
    """R-041/R-043: each bearer costs $1; three hires leave $2, three bearers in the worker area
    and three fewer on the path. DONE is legal after the first hire and the turn passes."""
    j = joinery
    s = T.start(n, j)
    T.play(s, H.MOVE_TO(R.loc(j, "bearers")))
    assert H.DONE not in s.legal_actions()
    for _ in range(3):
        T.play(s, R.HIRE_BEARER)
        assert H.DONE in s.legal_actions() and R.HIRE_BEARER in s.legal_actions()
    T.play(s, H.DONE)
    assert s.current_player() == 1 % n
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 2
    assert me["hired"] == {"woodcutters": 0, "bearers": 3, "sawyers": 0}
    assert sn["path"]["bearers"] == R.quantities(n)["bearers_on_path"] - 3


@pytest.mark.parametrize("joinery", BOOLS)
def test_R041_bearers_cannot_be_hired_without_money_and_use_all_five_dollars(joinery):
    """R-041/R-040: with $5 exactly five bearers can be hired; the sixth HIRE_BEARER is not
    legal (no money), although the location still has bearers. Money ends at $0."""
    j = joinery
    s = T.start(3, j)
    T.play(s, H.MOVE_TO(R.loc(j, "bearers")), *([R.HIRE_BEARER] * 5))
    assert R.HIRE_BEARER not in s.legal_actions()
    T.end_visit(s)
    sn = T.snap(s)
    assert T.seat_of(sn, 0)["money"] == 0
    assert T.seat_of(sn, 0)["hired"]["bearers"] == 5
    assert sn["path"]["bearers"] == R.quantities(3)["bearers_on_path"] - 5


@pytest.mark.parametrize("joinery", BOOLS)
def test_R041_bearers_limited_to_those_remaining_on_the_location(joinery):
    """R-041: two players, 6 bearers: P0 takes a loan ($9) and hires all 6 ($3 left); a seventh
    is not legal and the location is then closed to P1 (R-040 item 4)."""
    j = joinery
    b = R.loc(j, "bearers")
    s = T.start(2, j)
    T.play(s, H.TAKE_LOAN, H.MOVE_TO(b), *([R.HIRE_BEARER] * 6))
    assert R.HIRE_BEARER not in s.legal_actions()
    T.end_visit(s)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 3 and me["loans"] == 1 and me["hired"]["bearers"] == 6
    assert sn["path"]["bearers"] == 0
    assert s.current_player() == 1
    assert b not in T.move_locs(s)


# --------------------------------------------------------------------------- R-041 Woodcutters


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R041_woodcutters_capped_by_wood_in_own_cutting_area_round_1(n, joinery):
    """R-041 example: in round 1 each seat's area holds 3 firewood; with $5 a seat may hire 1, 2 or
    3 woodcutters but not 4. Three hires cost $3 (left $2)."""
    j = joinery
    s = T.start(n, j)
    sn0 = T.snap(s)
    assert T.own_wood(sn0, 0) == 3
    T.play(s, H.MOVE_TO(R.loc(j, "woodcutters")))
    for _ in range(3):
        assert R.HIRE_WOODCUTTER in s.legal_actions()
        T.play(s, R.HIRE_WOODCUTTER)
    assert R.HIRE_WOODCUTTER not in s.legal_actions()
    T.end_visit(s)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 2 and me["hired"]["woodcutters"] == 3
    assert sn["path"]["woodcutters"] == R.quantities(n)["woodcutters_on_path"] - 3


@pytest.mark.parametrize("which", ("fewest", "most"))
def test_R041_woodcutters_cap_follows_wood_pieces_in_the_picked_area(which):
    """R-041/R-038 example: from round 2 the cap is the wood in the area the seat picked (any
    kind, food not counted); hires stop at min(wood, money). All seats pick the same area."""
    run = R.drive(T.params(3), seed=4, stop=lambda c: c.round == 2 and c.phase == "PK")
    assert run.stopped
    s = run.state
    areas = H.areas(T.snap(s))
    wood = [T.total_wood(a) for a in areas]
    target = wood.index(min(wood) if which == "fewest" else max(wood))
    for _ in range(3):
        T.play(s, H.PICK_AREA(target))
    sn = T.snap(s)
    assert sn["phase"] == "TR"
    me_idx = s.current_player()
    me = T.seat_of(sn, me_idx)
    cap = T.total_wood(H.areas(sn)[target])
    assert cap == wood[target] and me["cutting_area"] == target + 1
    T.play(s, H.MOVE_TO(10))
    hires = 0
    while R.HIRE_WOODCUTTER in s.legal_actions():
        T.play(s, R.HIRE_WOODCUTTER)
        hires += 1
    assert hires == min(cap, me["money"])
    T.end_visit(s)
    assert T.seat_of(T.snap(s), me_idx)["money"] == me["money"] - hires


@pytest.mark.parametrize("joinery", BOOLS)
def test_R041_woodcutters_hired_with_no_money_need_a_loan(joinery):
    """R-041/R-076: the broke seat at Woodcutters has no HIRE_WOODCUTTER until it takes a loan;
    then one hire costs $1 (+$4 - $1 = $3)."""
    j = joinery
    s = T.start(2, j)
    T.hire(s, R.loc(j, "bearers"), R.HIRE_BEARER, 5)
    T.goto_clearing(s)  # P1
    T.play(s, H.MOVE_TO(R.loc(j, "woodcutters")))
    assert R.HIRE_WOODCUTTER not in s.legal_actions()
    T.play(s, H.TAKE_LOAN)
    assert R.HIRE_WOODCUTTER in s.legal_actions()
    T.play(s, R.HIRE_WOODCUTTER)
    T.end_visit(s)
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 3 and me["loans"] == 1 and me["hired"]["woodcutters"] == 1


# --------------------------------------------------------------------------- R-041 Fodder / R-043


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R041_fodder_costs_one_dollar_goes_to_the_value_3_slot(n, joinery):
    """R-041/R-043: buying fodder costs $1, puts it on the value-3 slot and ends the visit by
    itself (one fodder per seat per round); the path loses one fodder."""
    j = joinery
    s = T.start(n, j)
    T.play(s, H.MOVE_TO(R.loc(j, "fodder")))
    assert R.BUY_FODDER in s.legal_actions()
    T.play(s, R.BUY_FODDER)
    assert s.current_player() == 1  # the visit ended automatically
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 4
    assert me["fodder"] == {"slot3": True, "slot2": False}
    assert me["fodder_bought"] is True
    assert sn["path"]["fodder"] == R.quantities(n)["fodder_on_path"] - 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R041_fodder_location_empty_when_the_only_fodder_is_bought(joinery):
    """R-041/R-040(4): two players, 1 fodder: after P0 buys it, P1 cannot enter Fodder."""
    j = joinery
    f = R.loc(j, "fodder")
    s = T.start(2, j)
    T.visit(s, f, R.BUY_FODDER)
    assert T.snap(s)["path"]["fodder"] == 0
    assert f not in T.move_locs(s)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R043_value_3_slot_occupied_blocks_buying_in_a_later_round(joinery):
    """R-043/R-041: fodder stays on the slot; in round 2 the seat cannot enter Fodder (its value-3
    slot is occupied) though the location is refilled and the seat has money."""
    j = joinery
    f = R.loc(j, "fodder")
    pol = R.Script({(1, 0): [H.MOVE_TO(f), R.BUY_FODDER, R.MOVE_CLEARING]})
    run = R.drive(
        T.params(3, j),
        seed=4,
        policy=pol,
        stop=lambda c: c.round == 2 and c.phase == "TR" and c.player == 0,
    )
    assert run.stopped
    sn = T.snap(run.state)
    me = T.seat_of(sn, 0)
    assert me["fodder"]["slot3"] is True and me["money"] >= 1
    assert sn["path"]["fodder"] == R.quantities(3)["fodder_on_path"]
    assert f not in T.move_locs(run.state)


# --------------------------------------------------------------------------- R-041 Tasks / R-043


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R041_task_costs_one_dollar_and_goes_next_to_the_sawmill(n, joinery):
    """R-041/R-043: at Tasks exactly the face-up cards are takeable (TAKE_TASK(t)); taking one
    costs $1, the card belongs to the seat (unfilled), leaves the row, and the visit ends."""
    j = joinery
    s = T.start(n, j)
    sn0 = T.snap(s)
    row = sn0["supply"]["tasks_laid_out"]
    assert len(row) == R.quantities(n)["task_cards_laid_out"]
    T.play(s, H.MOVE_TO(R.loc(j, "tasks")))
    assert _legal_tasks(s) == sorted(_take_task_id(t) for t in row)
    T.play(s, _take_task_id(row[1]))
    assert s.current_player() == 1
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 4
    assert [t["id"] for t in me["tasks"]] == [row[1]]
    assert me["tasks"][0].get("filled", []) == []
    assert me["task_taken"] is True
    assert sorted(sn["supply"]["tasks_laid_out"]) == sorted(set(row) - {row[1]})


@pytest.mark.parametrize("joinery", BOOLS)
def test_R041_card_taken_by_one_seat_is_not_offered_to_the_next(joinery):
    """R-041: P0 takes card X at Tasks; P1's offer at Tasks is the row without X, and P1's own
    card is a different one."""
    j = joinery
    t = R.loc(j, "tasks")
    s = T.start(3, j)
    row = T.snap(s)["supply"]["tasks_laid_out"]
    T.play(s, H.MOVE_TO(t), _take_task_id(row[0]))
    T.play(s, H.MOVE_TO(t))
    assert _take_task_id(row[0]) not in s.legal_actions()
    assert _legal_tasks(s) == sorted(_take_task_id(x) for x in row[1:])
    T.play(s, _take_task_id(row[2]))
    sn = T.snap(s)
    assert [x["id"] for x in T.seat_of(sn, 1)["tasks"]] == [row[2]]
    assert [x["id"] for x in T.seat_of(sn, 0)["tasks"]] == [row[0]]


# --------------------------------------------------------------------------- R-042 token spots


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("tok", ("saw", "wagon", "raft", "sledge"))
def test_R042_equipment_token_goes_to_the_equipment_area_for_free(tok, joinery):
    """R-042: entering a spot holding an equipment token takes it for nothing: the seat's
    equipment count for that type becomes 1, money stays $5, the spot is empty and the turn
    passes (no DONE needed)."""
    s = T.start(3, joinery)
    loc = T.spot_with(T.snap(s), tok)[0]
    T.play(s, H.MOVE_TO(loc))
    assert s.current_player() == 1
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["equipment"][tok] == 1
    assert sum(me["equipment"].values()) == 1
    assert me["money"] == 5
    assert T.spots(sn)[loc] is None


@pytest.mark.parametrize("joinery", BOOLS)
def test_R042_dollar_token_is_exchanged_for_one_dollar(joinery):
    """R-042: the dollar-coin token pays $1 from the bank (5 -> 6) and is not kept as equipment;
    the spot is empty."""
    s = T.start(3, joinery)
    loc = T.spot_with(T.snap(s), "dollar")[0]
    T.play(s, H.MOVE_TO(loc))
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 6
    assert sum(me["equipment"].values()) == 0 and sum(me["craftwork"].values()) == 0
    assert T.spots(sn)[loc] is None


@pytest.mark.parametrize("joinery", BOOLS)
def test_R042_food_token_is_exchanged_for_one_food(joinery):
    """R-042/R-043: a food token becomes 1 food in the food storage (O-U2-2); money unchanged."""
    s = T.start(3, joinery)
    loc = T.spot_with(T.snap(s), "food")[0]
    T.play(s, H.MOVE_TO(loc))
    me = T.seat_of(T.snap(s), 0)
    assert me["food"] == 1 and me["money"] == 5


@pytest.mark.parametrize("joinery", BOOLS)
def test_R042_craftwork_token_goes_to_the_public_craftwork_area(joinery):
    """R-042/R-028: a craftwork token (board, shingle, stake, reed or joker) is held openly in the
    craftwork area: the dump counts one of exactly that type."""
    s = T.start(3, joinery)
    sn0 = T.snap(s)
    loc = T.spot_with(sn0, *R.CRAFT)[0]
    kind = T.spots(sn0)[loc]
    T.play(s, H.MOVE_TO(loc))
    me = T.seat_of(T.snap(s), 0)
    assert me["craftwork"][kind] == 1
    assert sum(me["craftwork"].values()) == 1
    assert me["money"] == 5


@pytest.mark.parametrize("joinery", BOOLS)
def test_R042_no_limit_on_non_saw_equipment(joinery):
    """R-042: a seat may hold any number of rafts: P0 takes both rafts of the round (3 players),
    on two separate turns."""
    s = T.start(3, joinery)
    r1, r2 = T.spot_with(T.snap(s), "raft")
    T.play(s, H.MOVE_TO(r1))
    T.goto_clearing(s)
    T.goto_clearing(s)
    assert s.current_player() == 0
    assert r2 in T.move_locs(s)
    T.play(s, H.MOVE_TO(r2))
    assert T.seat_of(T.snap(s), 0)["equipment"]["raft"] == 2


def test_R042_two_players_have_exactly_two_x_marker_spots_never_entered():
    """R-042/R-017: the 2-player path has two X-marker spots; their tokens are not takeable and
    stay put after a full set of moves."""
    s = T.start(2, False, seed=2)
    xs = T.spot_with(T.snap(s), "x")
    assert len(xs) == 2
    assert set(xs).isdisjoint(T.move_locs(s))
    for x in xs:
        assert H.MOVE_TO(x) not in s.legal_actions()


# --------------------------------------------------------------------------- R-076 loans


@pytest.mark.parametrize("joinery", BOOLS)
def test_R076_first_loan_four_dollars_second_four_dollars_third_illegal(joinery):
    """R-076/R-075: a loan is legal on the seat's own travel node: +$4 each, loans 1 then 2
    (money $5 -> $9 -> $13); after two loans TAKE_LOAN is no longer legal. The turn is not
    passed by taking a loan."""
    s = T.start(3, joinery)
    assert H.TAKE_LOAN in s.legal_actions()
    T.play(s, H.TAKE_LOAN)
    assert s.current_player() == 0
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 9 and me["loans"] == 1
    assert H.TAKE_LOAN in s.legal_actions()
    T.play(s, H.TAKE_LOAN)
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 13 and me["loans"] == 2
    assert H.TAKE_LOAN not in s.legal_actions()
    assert s.current_player() == 0


def test_R076_loan_is_not_legal_for_a_seat_that_is_not_to_act():
    """R-076/ACTIONS 3: a loan is possible only on the seat's own turn: while P0 acts, P1 and P2
    have no legal action at all."""
    s = T.start(3, False)
    assert s.current_player() == 0
    assert s.legal_actions(1) == [] and s.legal_actions(2) == []
    assert H.TAKE_LOAN in s.legal_actions(0)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R076_loan_counts_for_entering_but_is_not_taken_automatically(joinery):
    """R-076/R-040(4): P0 at $0, no loan, may enter Tasks. Entering takes no loan (money still $0,
    no task takeable) and only TAKE_LOAN is legal; DONE is not. After the loan, taking a task
    leaves $3 (0 + 4 - 1) and loans 1."""
    j = joinery
    s = T.start(2, j)
    T.hire(s, R.loc(j, "bearers"), R.HIRE_BEARER, 5)
    T.goto_clearing(s)
    assert T.seat_of(T.snap(s), 0)["money"] == 0
    row = T.snap(s)["supply"]["tasks_laid_out"]
    T.play(s, H.MOVE_TO(R.loc(j, "tasks")))
    assert sorted(s.legal_actions()) == [H.TAKE_LOAN]
    T.play(s, H.TAKE_LOAN)
    assert H.DONE not in s.legal_actions()  # a loan alone is not an acquisition
    assert _legal_tasks(s) == sorted(_take_task_id(t) for t in row)
    T.play(s, _take_task_id(row[0]))
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 3 and me["loans"] == 1
    assert [t["id"] for t in me["tasks"]] == [row[0]]


def test_R076_second_loan_also_counts_for_entering():
    """R-076/R-040(4): a seat with $0 and one loan used may still enter Tasks counting the second
    loan; inside, TAKE_LOAN is the only legal action and leaves $4, then the task costs $1 ($3)."""
    s = T.start(3, False)
    T.play(s, H.TAKE_LOAN)  # $9
    T.hire(s, 4, R.HIRE_BEARER, 8)  # $1
    T.goto_clearing(s)
    T.goto_clearing(s)
    T.hire(s, 10, R.HIRE_WOODCUTTER, 1)  # $0, loans 1
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 0 and me["loans"] == 1
    assert 13 in T.move_locs(s)
    T.play(s, H.MOVE_TO(13))
    assert sorted(s.legal_actions()) == [H.TAKE_LOAN]
    T.play(s, H.TAKE_LOAN)
    T.play(s, _legal_tasks(s)[0])
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 3 and me["loans"] == 2


@pytest.mark.parametrize("joinery", BOOLS)
def test_R076_two_loans_used_and_no_money_closes_paid_locations(joinery):
    """R-076/R-040(4): P0 on location 10 with $0 and both loans taken has no TAKE_LOAN; Tasks
    ($1) is closed to it while Sawyers (free sawyer) stays open. At most 2 loans in total."""
    s = T.broke_p0(joinery)
    me = T.seat_of(T.snap(s), 0)
    assert me["money"] == 0 and me["loans"] == 2
    assert H.TAKE_LOAN not in s.legal_actions()
    assert R.loc(joinery, "tasks") not in T.move_locs(s)
    assert R.loc(joinery, "sawyers") in T.move_locs(s)
