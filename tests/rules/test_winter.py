"""Phase 2 unit 10: winter rounds (R-064..R-070, R-074) and the R-117 data side.

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py and tests/support/{rounds,sawmill,woodwork,winter}.py.

Notes
  * There is no scenario loader in the harness, so winter states are reached by scripted play
    through rounds 1-3 (`winter.fall_steps`). With seed 1 (2 players) the year-1 card is
    winter_1_4 top (food 5, heating 4); tests assert this precondition where they rely on it.
  * Feeding and heating are automatic, so results are read at the next turn boundary
    (`winter.at_phase`) or at round 5's first node, and compared with the winter-start snapshot.
  * A seat that finishes its N4 turn may see a shortfall (SF) at once; see test_winter_payments.py.
  * User decision: NB and N1..N4 each give every seat an explicit node ending in DONE (no
    auto-skip of empty phases); the tests require those nodes
    (R-064 "one turn per seat", ACTIONS section 4).
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
BOOLS = (False, True)
FW, SW, HW = 0, 1, 2
WINTER_PHASES = ("NB", "N1", "N2", "N3", "N4")


def _late_p0(j: bool) -> list[Any]:
    """P0 visits Bearers first and only then enters the clearing: clearing order P1, ..., P0."""
    return [R.move(j, "bearers"), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING]


def _steps_with(**kw: Any) -> W.Steps:
    return V.fall_steps(False, **kw)


def _woodpile(sn: dict[str, Any], seat: int) -> dict[str, int]:
    return dict(V.pm(V.seat(sn, seat)["woodpile"]))


# --------------------------------------------------------------------------- R-064


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R064_phases_run_in_order_one_turn_per_seat_in_clearing_order(n, joinery):
    """R-064: winter = bonus, then phases N1..N4 in order (feeding and heating are automatic);
    in the bonus and in each phase the seats act once each, in the clearing order of the
    preceding fall round. Holds identically with joinery true and false."""
    run = V.winter_run(None, j=joinery, n=n)
    order = V.winter_order(run)
    assert sorted(order) == list(range(n))
    rows = [(ph, p) for r, ph, p in run.log if r == 4]
    phases = [ph for ph, _ in rows]
    assert set(phases) <= set(R.WINTER_PHASES)
    for ph in WINTER_PHASES:  # every phase gives every seat an explicit node, in clearing order
        assert [p for x, p in rows if x == ph] == order, ph
    idx = [R.WINTER_PHASES.index(ph) for ph in phases]
    assert idx == sorted(idx), "phases must not go back"
    assert run.event(4).phase == "NB"


@pytest.mark.parametrize("n", PLAYERS)
def test_R064_winter_follows_fall_clearing_not_next_spring_order(n):
    """R-064 example: the winter bonus and every winter phase run in the clearing order of the
    fall round, while the starting order set after fall (and used in spring) is its reverse."""
    pol = R.Script({(3, 0): _late_p0(False)})
    run = R.drive(
        V.params(n), seed=11, policy=R.chain(pol, R.cut_all_wood), stop=lambda c: c.round == 5
    )
    assert run.stopped
    fall = run.event(4).before["clearing_order"]
    assert fall[-1] == 0 and sorted(fall) == list(range(n))
    for ph in ("NB", "N1"):
        assert [p for r, x, p in run.log if r == 4 and x == ph] == fall
    assert run.event(4).after["turn_order"] == list(reversed(fall))
    assert run.event(5).after["turn_order"] == list(reversed(fall))


@pytest.mark.parametrize("joinery", BOOLS)
def test_R064_winter_has_no_path_picks_hires_or_area_changes(joinery):
    """R-064: no supply path, no cutting-area picks, no food distribution, no log driving, nobody
    hires: the cutting areas are untouched from the winter start to its last turn, every foreman
    stays on location 0 and no worker is hired."""
    steps = _steps_with(bearers=1)
    _, start = V.first_winter(steps, j=joinery)
    s, _ = V.at_phase(steps, "N4", 0, j=joinery)
    mid = V.snap(s)
    assert start["path"] is None and mid["path"] is None
    assert start["cutting_areas"] == mid["cutting_areas"]
    for sn in (start, mid):
        for seat in H.seats(sn):
            assert seat["foreman"] == 0
            assert R.total(seat["hired"]) == 0
            assert seat["cutting_area"] is None


def test_R064_no_hire_or_travel_actions_in_winter():
    """R-064: nobody hires workers and there is no travel: no MOVE_TO and no hire/buy action is
    legal at any winter node."""
    pr = V.Probe()
    st = _steps_with()
    for ph in WINTER_PHASES:
        for seat in (0, 1):
            st.add(4, ph, seat, pr.at(f"{ph}{seat}"))
    V.winter_run(st)
    assert set(pr.seen) == {f"{ph}{seat}" for ph in WINTER_PHASES for seat in (0, 1)}
    for key, lists in pr.seen.items():
        for legal in lists:
            assert not [a for a in legal if 8 <= a <= 37], key


# --------------------------------------------------------------------------- R-065


def _bonus_state():
    return V.at_phase(None, "NB", 0)


def test_R065_every_kind_is_offered_and_declining_is_allowed():
    """R-065: before phase 1 each seat may take 1 wood piece of its choice (firewood, softwood or
    hardwood disk): all three kinds and DONE (decline) are legal for the first seat."""
    s, _ = _bonus_state()
    legal = s.legal_actions()
    for k in (FW, SW, HW):
        assert V.TAKE_BONUS0 + k in legal
    assert H.DONE in legal


@pytest.mark.parametrize("kind", (FW, SW, HW))
def test_R065_bonus_piece_goes_unmilled_into_the_woodpile(kind):
    """R-065: the chosen disk comes from the supply into the woodpile, unmilled; one piece only.
    Both seats take the same kind; each woodpile gains exactly one disk of that kind."""
    st = W.Steps()
    for seat in (0, 1):
        st.add(4, "NB", seat, V.TAKE_BONUS0 + kind, W.Opt(H.DONE))
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N1", 0)
    now = V.snap(s)
    name = f"{V.KINDS[kind]}_disk"
    for seat in (0, 1):
        before, after = _woodpile(start, seat), _woodpile(now, seat)
        assert after.get(name, 0) == before.get(name, 0) + 1
        assert sum(after.values()) == sum(before.values()) + 1
        assert V.seat(now, seat)["mill_worker_used"] is False  # no worker used


def test_R065_declining_takes_nothing():
    """R-065: taking nothing is allowed: after both seats decline (DONE) woodpiles are unchanged."""
    st = W.Steps().add(4, "NB", 0, H.DONE).add(4, "NB", 1, H.DONE)
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N1", 0)
    for seat in (0, 1):
        assert _woodpile(V.snap(s), seat) == _woodpile(start, seat)


def test_R065_only_one_piece_per_seat():
    """R-065: 'take 1 wood piece': after taking one, the same seat is not offered another bonus."""
    s, _ = _bonus_state()
    who = s.current_player()
    s.apply_action(V.TAKE_BONUS0 + FW)
    if s.current_player() == who:
        assert not [a for a in s.legal_actions() if V.TAKE_BONUS0 <= a < V.TAKE_BONUS0 + 3]


def test_R065_bonus_hardwood_without_sledge_stays_for_spring():
    """R-065 example: a hardwood disk taken as bonus in winter year 1 without a sledge stays in
    the woodpile into spring year 2 (a woodpile cannot be sold, so it survives the shortfall)."""
    st = W.Steps().add(4, "NB", 0, V.TAKE_BONUS0 + HW)
    run = V.winter_run(st)
    got = _woodpile(run.event(5).after, 0)
    assert got.get("hardwood_disk", 0) == 1


def test_R065_bonus_is_not_available_outside_the_bonus_step():
    """R-065 / ACTIONS: TAKE_BONUS exists only in NB, not in N1 or later."""
    pr = V.Probe()
    st = _steps_with().add(4, "N1", 0, pr.at("n1"))
    V.winter_run(st)
    assert not [a for a in pr.last("n1") if V.TAKE_BONUS0 <= a < V.TAKE_BONUS0 + 3]


# --------------------------------------------------------------------------- R-066


def _cut_steps(*seats: int) -> W.Steps:
    st = W.Steps()
    for seat in seats:
        st.add(4, "N1", seat, W.Opt(W.assign(1)), V.WINTER_CUT, W.Opt(H.DONE))
    return st


def test_R066_mill_worker_takes_two_firewood_disks():
    """R-066: the mill worker on the woodpile takes 2 firewood disks from the supply into the
    woodpile; the mill worker is then used for the winter. Each seat gets its own 2."""
    st = _cut_steps(0, 1)
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N2", 0)
    now = V.snap(s)
    for seat in (0, 1):
        before, after = _woodpile(start, seat), _woodpile(now, seat)
        assert after.get("firewood_disk", 0) == before.get("firewood_disk", 0) + 2
        assert V.seat(now, seat)["mill_worker_used"] is True


def test_R066_taking_nothing_is_allowed_and_leaves_the_worker_free():
    """R-066: taking nothing is allowed: DONE at N1 changes nothing and the mill worker stays
    unused (it may still be used for the sledge, R-067)."""
    st = W.Steps().add(4, "N1", 0, H.DONE).add(4, "N1", 1, H.DONE)
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N2", 0)
    now = V.snap(s)
    for seat in (0, 1):
        assert _woodpile(now, seat) == _woodpile(start, seat)
        assert V.seat(now, seat)["mill_worker_used"] is False


def test_R066_winter_cut_only_once_with_one_worker():
    """R-066 + C6: with only the mill worker (no hut workers) a second WINTER_CUT is not legal, and
    WINTER_CUT is not offered outside N1."""
    pr = V.Probe()
    st = W.Steps().add(
        4, "N1", 0, pr.at("before"), W.Opt(W.assign(1)), V.WINTER_CUT, pr.at("after")
    )
    st.add(4, "N2", 0, pr.at("n2"))
    V.winter_run(st)
    assert V.WINTER_CUT in pr.last("before") or W.assign(1) in pr.last("before")
    assert V.WINTER_CUT not in pr.union("after")
    assert V.WINTER_CUT not in pr.union("n2")


def test_R066_mill_worker_spent_by_woodcutting_cannot_sledge_or_saw():
    """R-066/R-067/R-068 + C6 ('you need to choose'): after winter woodcutting the mill worker is
    gone for the round, so a seat holding a sledge and a saw cannot use either."""
    pr = V.Probe()
    st = _steps_with(sledge=True, saw=True, bearers=1, carries=(0,))
    st.add(4, "N1", 0, W.Opt(W.assign(1)), V.WINTER_CUT, W.Opt(H.DONE))
    st.add(4, "N2", 0, pr.at("n2"))
    st.add(4, "N3", 0, pr.at("n3"))
    V.winter_run(st)
    assert V.USE_SLEDGE not in pr.union("n2")
    assert not [a for a in pr.union("n3") if a in M.SAW_IDS]


# --------------------------------------------------------------------------- R-067


def _sledge_trip(moves: list[int], food: int = 0, end: bool = True) -> tuple[Any, dict[str, Any]]:
    st = _steps_with(sledge=True, food_tokens=food)
    st.add(4, "N2", 0, W.Opt(W.assign(1)), V.USE_SLEDGE, *moves)
    if end:
        st.add(4, "N2", 0, W.Opt(V.END_TRIP), W.Opt(H.DONE))
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N3", 0)
    return s, start


def test_R067_sledge_moves_two_pieces_without_food():
    """R-067: a sledge trip moves up to 2 pieces from the woodpile to the sawmill; the sledge
    token is spent and the mill worker used. Without food a third piece is not offered."""
    pr = V.Probe()
    mv = W.move_wood(W.FW, 0)
    st = _steps_with(sledge=True)
    st.add(
        4,
        "N2",
        0,
        W.Opt(W.assign(1)),
        V.USE_SLEDGE,
        mv,
        mv,
        pr.at("cap"),
        W.Opt(V.END_TRIP),
        W.Opt(H.DONE),
    )
    _, start = V.first_winter(st)
    assert V.seat(start, 0)["equipment"]["sledge"] == 1
    assert V.seat(start, 0)["food"] == 0
    s, _ = V.at_phase(st, "N3", 0)
    now = V.snap(s)
    a, b = V.seat(start, 0), V.seat(now, 0)
    assert V.pm(b["woodpile"])["firewood_disk"] == V.pm(a["woodpile"])["firewood_disk"] - 2
    assert V.pm(b["sawing"])["firewood_disk"] == V.pm(a["sawing"])["firewood_disk"] + 2
    assert b["equipment"]["sledge"] == 0
    assert b["mill_worker_used"] is True
    # the turn continues after the trip until DONE (explicit nodes), with no move left
    assert not [x for x in pr.union("cap") if x in W.MOVE_WOOD_IDS]


def test_R067_one_food_allows_a_third_piece_and_is_spent():
    """R-067: each food piece allows 1 more piece; with 1 food the trip moves 3 and the food leaves
    the food storage. A fourth piece would need a second food, so it is not offered."""
    pr = V.Probe()
    mv = W.move_wood(W.FW, 0)
    st = _steps_with(sledge=True, food_tokens=1)
    st.add(
        4,
        "N2",
        0,
        W.Opt(W.assign(1)),
        V.USE_SLEDGE,
        mv,
        mv,
        mv,
        pr.at("cap"),
        W.Opt(V.END_TRIP),
        W.Opt(H.DONE),
    )
    _, start = V.first_winter(st)
    assert (
        V.seat(start, 0)["food"] == 1 and V.pm(V.seat(start, 0)["woodpile"])["firewood_disk"] >= 3
    )
    s, _ = V.at_phase(st, "N3", 0)
    a, b = V.seat(start, 0), V.seat(V.snap(s), 0)
    assert b["food"] == 0
    assert V.pm(b["woodpile"])["firewood_disk"] == V.pm(a["woodpile"])["firewood_disk"] - 3
    assert V.pm(b["sawing"])["firewood_disk"] == V.pm(a["sawing"])["firewood_disk"] + 3
    # the turn continues after the trip until DONE (explicit nodes), with no move left
    assert not [x for x in pr.union("cap") if x in W.MOVE_WOOD_IDS]


@pytest.mark.parametrize("pieces", (1, 2))
def test_R067_food_is_charged_only_for_pieces_beyond_the_free_two(pieces):
    """R-067: the trip may move fewer than the maximum, even one piece; food is charged only for
    pieces beyond the first 2. Moving 1 or 2 pieces while holding 1 food leaves the food unspent
    (but the sledge is spent)."""
    mv = W.move_wood(W.FW, 0)
    s, start = _sledge_trip([mv] * pieces, food=1)
    a, b = V.seat(start, 0), V.seat(V.snap(s), 0)
    assert b["food"] == a["food"] == 1
    assert b["equipment"]["sledge"] == 0
    assert V.pm(b["sawing"])["firewood_disk"] == V.pm(a["sawing"])["firewood_disk"] + pieces


def test_R067_pieces_may_go_to_the_sale_area():
    """R-067 + R-050: a sledge piece may go to the sale area instead of the sawing area (final)."""
    mv = W.move_wood(W.FW, 1)
    s, start = _sledge_trip([mv, mv])
    a, b = V.seat(start, 0), V.seat(V.snap(s), 0)
    assert V.pm(b["sale"])["firewood_disk"] == V.pm(a["sale"])["firewood_disk"] + 2
    assert V.pm(b["sawing"]) == V.pm(a["sawing"])


def test_R067_without_a_sledge_there_is_no_transport_in_winter():
    """R-067: sledge is the only transport in winter: a seat without a sledge token cannot use it,
    and no bearer, wagon or river action is legal either."""
    pr = V.Probe()
    st = _steps_with().add(4, "N2", 0, pr.at("n2")).add(4, "N2", 1, pr.at("n2b"))
    V.winter_run(st)
    for key in ("n2", "n2b"):
        legal = pr.union(key)
        assert V.USE_SLEDGE not in legal
        assert W.USE_WAGON not in legal
        assert not [a for a in legal if a in W.RIVER_IDS]
        assert not [a for a in legal if a in W.MOVE_WOOD_IDS]


def test_R067_hardwood_disk_only_to_the_sawing_area():
    """R-067 + R-046/R-050: a hardwood disk moved by sledge may only go to the sawing area."""
    pr = V.Probe()
    st = _steps_with(sledge=True)
    st.add(4, "NB", 0, V.TAKE_BONUS0 + HW)
    st.add(4, "N2", 0, W.Opt(W.assign(1)), V.USE_SLEDGE, pr.at("trip"))
    st.add(4, "N2", 0, W.move_wood(W.HW, 0), W.Opt(V.END_TRIP), W.Opt(H.DONE))
    V.winter_run(st)
    legal = pr.last("trip")
    assert W.move_wood(W.HW, 0) in legal
    assert W.move_wood(W.HW, 1) not in legal


# --------------------------------------------------------------------------- R-068


def _saw_steps(nlogs: int | None, *, mill_cut: bool = False) -> W.Steps:
    st = _steps_with(saw=True, bearers=1, carries=(0,))
    if mill_cut:
        st.add(4, "N1", 0, W.Opt(W.assign(1)), V.WINTER_CUT, W.Opt(H.DONE))
    if nlogs is None:
        st.add(4, "N3", 0, H.DONE)
    else:
        st.add(4, "N3", 0, W.Opt(W.assign(1)), M.saw(W.FW, nlogs), W.Opt(H.DONE))
    return st


@pytest.mark.parametrize("nlogs", (0, 2, 4))
def test_R068_mill_worker_saws_one_disk_split_between_storage_and_sale(nlogs):
    """R-068 (as R-054): the mill worker and a saw token mill 1 disk of the sawing area into 4
    firewood logs, placed at once: nlogs in the firewood storage, the rest in the sale area. The
    saw token is spent and the worker used."""
    st = _saw_steps(nlogs)
    _, start = V.first_winter(st)
    a = V.seat(start, 0)
    assert V.pm(a["sawing"])["firewood_disk"] == 1 and a["equipment"]["saw"] == 1
    s, _ = V.at_phase(st, "N4", 0)
    b = V.seat(V.snap(s), 0)
    assert V.pm(b["sawing"])["firewood_disk"] == 0
    assert (
        V.pm(b["firewood_storage"])["firewood_log"]
        == V.pm(a["firewood_storage"])["firewood_log"] + nlogs
    )
    assert V.pm(b["sale"])["firewood_log"] == V.pm(a["sale"])["firewood_log"] + 4 - nlogs
    assert b["equipment"]["saw"] == 0
    assert b["mill_worker_used"] is True


def test_R068_a_disk_not_sawed_stays_in_the_sawing_area():
    """R-068: sawing is optional; a disk not sawed stays in the sawing area (read at N4)."""
    st = _saw_steps(None)
    _, start = V.first_winter(st)
    s, _ = V.at_phase(st, "N4", 0)
    a, b = V.seat(start, 0), V.seat(V.snap(s), 0)
    assert V.pm(b["sawing"]) == V.pm(a["sawing"]) and V.pm(b["sawing"])["firewood_disk"] == 1
    assert b["equipment"]["saw"] == 1 and b["mill_worker_used"] is False


def test_R068_saw_needs_a_saw_token_and_a_free_mill_worker():
    """R-068 + C6: no sawing without a saw token (disk in the sawing area, no saw), and none after
    the mill worker cut wood in N1 (saw held, disk present)."""
    pr = V.Probe()
    no_saw = _steps_with(bearers=1, carries=(0,)).add(4, "N3", 0, pr.at("nosaw"))
    V.winter_run(no_saw)
    assert not [a for a in pr.union("nosaw") if a in M.SAW_IDS]
    pr2 = V.Probe()
    spent = _saw_steps(None, mill_cut=True)
    spent.table[(4, "N3", 0)].insert(0, pr2.at("spent"))
    V.winter_run(spent)
    assert not [a for a in pr2.union("spent") if a in M.SAW_IDS]


# --------------------------------------------------------------------------- R-069


def _year1_task_steps(j: bool) -> W.Steps:
    """P0 holds task_10 and has 4 logs in the sale area (a sawyer, a saw and a bearer)."""
    return V.fall_steps(
        j, saw=True, sawyer=True, bearers=1, task=M.TASK, carries=(0,), sawing=((0, 0, 0),)
    )


@pytest.mark.parametrize("joinery", BOOLS)
def test_R069_year_1_no_wood_on_tasks_or_joinery(joinery):
    """R-069: in the winter of year 1 (round 4) no wood may be placed on task cards and none on the
    joinery, even for a seat that holds a task and has milled wood in the sale area."""
    s, base = V.at_phase(_year1_task_steps(joinery), "N4", 0, j=joinery)
    seat = V.seat(V.snap(s), 0)
    assert V.pm(seat["sale"])["firewood_log"] == 4 and seat["tasks"][0]["id"] == M.TASK
    assert not [a for a in s.legal_actions() if a in V.PLACE_ALL]


def _year2_steps() -> W.Steps:
    """Solvent year 1 (2 loans, 2 food tokens, 4 firewood logs in storage, task_10), a saw taken
    in round 5, a disk carried to the sawing area in round 7."""
    st = V.fall_steps(
        False, loans=2, food_tokens=2, saw=True, sawyer=True, bearers=1, task=M.TASK,
        carries=(0,), sawing=((0, 0, 4),),
    )  # fmt: skip
    st.add(5, "TR", 0, lambda s: H.MOVE_TO(_saw_loc(s)), R.MOVE_CLEARING)
    st.add(7, "TR", 0, R.move(False, "bearers"), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING)
    st.add(7, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, 0))
    st.add(8, "N3", 0, W.Opt(W.assign(1)), M.saw(W.FW, 0), W.Opt(H.DONE))
    return st


def _saw_loc(s: Any) -> int:
    locs = [k for k, v in H.tokens(V.snap(s)).items() if v == "saw"]
    assert locs, "no saw token on the path"
    return min(locs)


def test_R069_year_2_task_placement_after_sawing():
    """R-069: in the winter of year 2 (round 8), after sawing, a seat may place wood on its task
    cards under R-055: P0 saws a disk into 4 sale-area logs (N3) and may then place a firewood log
    from the sale area on task_10's firewood slot in N4."""
    s = V.reach(_year2_steps(), (8, "N4", 0))
    seat = V.seat(V.snap(s), 0)
    assert V.pm(seat["sale"])["firewood_log"] == 4
    assert M.place_task(M.S_FW0, 0) in s.legal_actions()


def _joinery_year2_steps(dry_round: int) -> W.Steps:
    """Joinery side. Solvent year 1; saw taken in round 5; in round 6 a bearer carries a disk, the
    mill worker saws it into 4 sale-area logs; one log enters drying 1 in round `dry_round` (6 or
    7). A round-6 entry reaches drying area 2 at round 7's drying phase; a round-7 entry is still
    in drying area 1 at winter year 2 (winter does not dry, R-074)."""
    st = V.fall_steps(
        True, loans=2, food_tokens=2, saw=True, sawyer=True, bearers=1, carries=(0,),
        sawing=((0, 0, 4),),
    )  # fmt: skip
    st.add(5, "TR", 0, lambda s: H.MOVE_TO(_saw_loc(s)), R.MOVE_CLEARING)
    st.add(6, "TR", 0, R.move(True, "bearers"), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING)
    st.add(6, "W1", 0, H.DONE)
    st.add(6, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, 0))
    st.add(6, "W4", 0, W.Opt(W.assign(1)), M.saw(W.FW, 0))
    st.add(dry_round, "W7", 0, M.dry_enter(M.FW_LOG))
    return st


def test_R069_year_2_joinery_takes_only_drying_area_2_wood():
    """R-069 + R-057 (user decision: drying 2 only): in winter year 2 a milled firewood log in
    drying area 2 may be placed in the joinery (some PLACE_JOINERY legal); the same seat with its
    log still in drying area 1 and others in the sale area has no joinery placement."""
    s = V.reach(_joinery_year2_steps(6), (8, "N4", 0), j=True)
    seat = V.seat(V.snap(s), 0)
    assert V.pm(seat["drying"][1])["firewood_log"] == 1 and V.pm(seat["sale"])["firewood_log"] == 3
    assert [a for a in s.legal_actions() if a in M.PLACE_JOINERY_IDS]
    s = V.reach(_joinery_year2_steps(7), (8, "N4", 0), j=True)
    seat = V.seat(V.snap(s), 0)
    assert V.pm(seat["drying"][0])["firewood_log"] == 1 and not V.pm(seat["drying"][1])
    assert not [a for a in s.legal_actions() if a in M.PLACE_JOINERY_IDS]


def test_R069_year_2_nothing_to_place_before_sawing_in_n3():
    """R-069: placement comes after sawing: at N3 (still sawing) no placement action is legal."""
    pr = V.Probe()
    st = _year2_steps()
    st.table[(8, "N3", 0)].insert(0, pr.at("n3"))
    V.reach(st, (8, "N4", 0))
    assert not [a for a in pr.union("n3") if a in V.PLACE_ALL]


# --------------------------------------------------------------------------- R-070


def _half(card: str, half: str) -> dict[str, int]:
    return V.winter_cards()[card]["halves"][half]


@pytest.mark.parametrize("n", PLAYERS)
def test_R070_cards_in_effect_and_requirements_do_not_scale_with_players(n):
    """R-070: round 4 uses the year-1 card and round 8 the year-2 card (R-014); the requirement is
    the visible half's food and heating values from the data, the same for every player count."""
    run = V.winter_run(None, n=n)
    w = run.event(4).after["supply"]["winter"]
    y1, y2 = w["year1"], w["year2"]
    assert V.winter_cards()[y1["card"]]["year"] == 1
    assert V.winter_cards()[y2["card"]]["year"] == 2
    assert y1["half"] in ("top", "bottom") and y2["half"] in ("top", "bottom")
    f, h = V.requirement(run.event(4).after, 1)
    assert (f, h) == (
        _half(y1["card"], y1["half"])["food"],
        _half(y1["card"], y1["half"])["heating"],
    )
    assert V.requirement(run.event(4).after, 2) == (
        _half(y2["card"], y2["half"])["food"],
        _half(y2["card"], y2["half"])["heating"],
    )


@pytest.mark.parametrize("n", PLAYERS)
def test_R070_every_seat_pays_the_same_requirement(n):
    """R-070: the requirement is the same for every seat. Seats with no food at all pay the same
    amount of money for the food: each first shortfall asks for 3 x the card's food requirement
    (two loans then do not cover it)."""
    run = V.winter_run(None, n=n)
    start, end = run.event(4).after, run.event(5).after
    food_req, _ = V.requirement(start, 1)
    for i in range(n):
        s0 = V.seat(start, i)
        want = V.settle(s0, V.requirement(start, 1))
        assert want["food"] == 0
        assert V.seat(end, i)["money"] == want["money"], (i, food_req)
        assert V.seat(end, i)["loans"] == want["loans"], i


# --------------------------------------------------------------------------- R-074


@pytest.mark.parametrize("joinery", BOOLS)
def test_R074_end_of_winter_workers_back_and_spring_year_2_starts(joinery):
    """R-074: after heating the mill workers return to their worker areas (used one included), the
    phase marker is back at the first phase of the next round and the season advances: round 5 is
    spring year 2 with the seasonal start (hidden picks first, a fresh path)."""
    st = _cut_steps(0, 1)
    run = V.winter_run(st, j=joinery)
    ev = run.event(5)
    assert ev.after["round"] == 5 and ev.after["phase"] == "PK"
    assert ev.before["round"] == 4
    assert all(s["mill_worker_used"] for s in H.seats(ev.before))
    for s in H.seats(ev.after):
        assert s["mill_worker_used"] is False
        assert s["foreman"] == 0 and R.total(s["hired"]) == 0
    assert len(H.tokens(ev.after)) == 13


def test_R074_drying_wood_does_not_dry_in_winter():
    """R-074: R-059 does not run in winter. P0 is solvent for feeding, short two logs of heating
    and has 2 logs in drying area 2 (+$1 each). Selling pays $2 each there; had winter advanced
    them to area 3 ($3 each) one log would have covered the shortfall and stayed. The reference
    model sells both, and the logs are gone."""
    st = V.fall_steps(
        False, loans=2, food_tokens=2, saw=True, sawyer=True, bearers=1, carries=(0,),
        sawing=((0, 0, 2),), dry_round2=2,
    )  # fmt: skip
    run = V.winter_run(st)
    start, end = run.event(4).after, run.event(5).after
    assert V.requirement(start, 1) == (5, 4)
    a = V.seat(start, 0)
    assert V.pm(a["drying"][1])["firewood_log"] == 2, "precondition: logs in drying area 2"
    want = V.settle(a, (5, 4))
    assert V.seat(end, 0)["money"] == want["money"]
    assert V.zones_equal(V.seat(end, 0), want["zones"])


def test_R074_game_ends_after_round_8():
    """R-074: after the heating phase of round 8 the game ends (final sale R-081): no round 9
    exists, and the game is over at the end of a default play."""
    run = R.drive(V.params(2), seed=3, policy=R.cut_all_wood)
    assert max(r for r, _, _ in run.log) == 8
    assert run.state.is_terminal()


# --------------------------------------------------------------------------- R-117 (data side)

EASIER = {
    "winter_1_1": (5, 7), "winter_1_2": (6, 3), "winter_1_3": (5, 5), "winter_1_4": (5, 4),
    "winter_2_1": (7, 7), "winter_2_2": (10, 7), "winter_2_3": (8, 6), "winter_2_4": (6, 8),
}  # fmt: skip


def test_R117_easier_half_is_the_lower_food_plus_heating_sum_per_the_spec_list():
    """R-117 data side: for each of the 8 cards the half with the lower food+heating sum is the
    one listed in the spec (food/heating), and no card ties."""
    cards = V.winter_cards()
    assert set(cards) == set(EASIER)
    for cid, want in EASIER.items():
        halves = cards[cid]["halves"]
        sums = {k: v["food"] + v["heating"] for k, v in halves.items()}
        assert len(set(sums.values())) == 2, cid
        easy = min(sums, key=lambda k: sums[k])
        assert (halves[easy]["food"], halves[easy]["heating"]) == want, cid


@pytest.mark.parametrize("n", (2, 4))
def test_R117_easy_winter_plays_the_easier_half_through_feeding(n):
    """R-117: with easy_winter=true both visible halves are the easier ones, and winter then
    charges that half's values (reference model, no food held)."""
    p = {**V.params(n), "easy_winter": True}
    run = R.drive(p, seed=4, policy=R.cut_all_wood, stop=lambda c: c.round == 5)
    assert run.stopped
    start, end = run.event(4).after, run.event(5).after
    for year in (1, 2):
        w = start["supply"]["winter"][f"year{year}"]
        want = EASIER[w["card"]]
        assert V.requirement(start, year) == want
    for i in range(n):
        m = V.settle(V.seat(start, i), V.requirement(start, 1))
        assert V.seat(end, i)["money"] == m["money"] and V.seat(end, i)["loans"] == m["loans"]
