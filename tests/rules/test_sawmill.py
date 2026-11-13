"""Phase 2 unit 8: sawing, tasks, selling, drying, joinery wood (R-054..R-059, R-063, R-082).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and
tests/support/{rounds,travel,woodwork,sawmill}.py. Sawing, tasks, selling and drying are
implemented, so these tests carry no pending marker.

Notes
  * No scenario loader exists in the harness, so states are reached by scripted play.
  * Snapshots exist only at turn boundaries: results are read at the next node after DONE.
  * ASSIGN_WORKER may be auto-inserted (ACTIONS A4); `W.assign_if_needed` / `W.Opt` handle both.
  * Several rules cannot be exercised end to end with the current harness (see the report):
    task completion payout (R-056 final), mixed-kind joinery in one turn (R-057), d3 sale only
    after a winter.
"""

from __future__ import annotations

import functools
from collections import Counter

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as M
from tests.support import winter as V
from tests.support import woodwork as W

BOOLS = (False, True)
FW, SW, HW = "firewood", "softwood", "hardwood"


def _at(steps: W.Steps, stop: tuple[int, str, int], key: object, n: int = 2, j: bool = False):
    return M.reach(steps, stop, key=key, n=n, j=j)


def _after(s):
    """DONE for the acting seat, return the snapshot-reading state (next boundary).

    If DONE ends the round the next node is the round-start chance run (no snapshot exists
    there), so chance outcomes are applied until a decision node is reached."""
    W.end_turn(s)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    return s


def _w4_one(j):
    return _at(M.one_disk_steps(j), (1, "W4", 0), ("w4one", j), j=j)


def _w5_one(j, nlogs=0, task=False):
    return _at(
        M.one_disk_steps(j, with_task=task, nlogs=nlogs),
        (1, "W5", 0),
        ("w5one", j, nlogs, task),
        j=j,
    )


def _w5_two(j, nlogs):
    return _at(M.two_pieces_steps(j, nlogs), (1, "W5", 0), ("w5two", j, nlogs), j=j)


# --------------------------------------------------------------------------- R-054


@pytest.mark.parametrize("nlogs", range(5))
@pytest.mark.parametrize("joinery", BOOLS)
def test_R054_saw_replaces_firewood_disk_by_four_logs_split_freely(joinery, nlogs):
    """R-054: a milled firewood disk becomes 4 logs placed at once, any split between firewood
    storage and sale area; the sawyer and the saw are spent (R-017: saw returns to supply)."""
    s = _w4_one(joinery)
    sn = W.snap(s)
    assert W.zone(sn, 0, "sawing") == Counter({"firewood_disk": 1})
    assert W.me(s, 0)["equipment"]["saw"] == 1
    W.assign_if_needed(s, 0)
    assert M.saw(0, nlogs) in s.legal_actions()
    assert M.saw(0, 5) not in s.legal_actions()  # 5-6 logs only with PW Heating (Phase 4)
    W.play(s, M.saw(0, nlogs))
    _after(s)
    assert not M.zone(s, "sawing")
    assert M.zone(s, "firewood_storage") == M.logs("firewood", nlogs)
    assert M.zone(s, "sale") == M.logs("firewood", 4 - nlogs)
    assert W.me(s, 0)["equipment"]["saw"] == 0


def test_R054_one_sawyer_one_saw_mill_one_disk_other_stays():
    """R-054: a sawyer or saw is used for one disk only. 2 disks, 1 sawyer, 1 saw (mill worker
    already used cutting): after one SAW nothing more is legal; the other disk stays in the
    sawing area."""
    steps = M.r1_steps(
        2, False, bearers=2, woodcutters=1, sawyers=1, saws=1, cuts=(0, 1), carries=(0, 0)
    )
    s = _at(steps, (1, "W4", 0), "w4two_sawing")
    assert M.zone(s, "sawing") == Counter({"firewood_disk": 2})
    W.assign_if_needed(s, 0)
    W.play(s, M.saw(0, 2))
    legal = s.legal_actions()
    assert not W.ids(legal, M.SAW_IDS)
    assert not W.ids(legal, W.ASSIGN_IDS)
    assert H.DONE in legal
    _after(s)
    assert M.zone(s, "sawing") == Counter({"firewood_disk": 1})
    assert M.zone(s, "firewood_storage") == M.logs("firewood", 2)
    assert M.zone(s, "sale") == M.logs("firewood", 2)


def test_R054_second_saw_stays_without_second_sawyer():
    """R-054 example: 1 sawyer and 2 saws, 2 disks: only one disk is milled, the second saw
    remains in the equipment area, the second disk stays (3 players: two saw tokens)."""
    steps = M.r1_steps(
        3, False, bearers=2, woodcutters=1, sawyers=1, saws=2, cuts=(0, 1), carries=(0, 0)
    )
    s = _at(steps, (1, "W4", 0), "w4_3p_two_saws", n=3)
    assert W.me(s, 0)["equipment"]["saw"] == 2
    W.assign_if_needed(s, 0)
    W.play(s, M.saw(0, 4))
    assert not W.ids(s.legal_actions(), M.SAW_IDS)
    _after(s)
    assert W.me(s, 0)["equipment"]["saw"] == 1
    assert M.zone(s, "sawing") == Counter({"firewood_disk": 1})


def test_R054_cannot_saw_without_a_saw():
    """R-054 (negative): a sawyer but no saw token: no SAW and no worker assignment is legal."""
    steps = M.r1_steps(2, False, bearers=1, sawyers=1, cuts=(1,), carries=(0,))
    s = _at(steps, (1, "W4", 0), "w4_nosaw")
    assert W.me(s, 0)["equipment"]["saw"] == 0
    assert M.zone(s, "sawing") == Counter({"firewood_disk": 1})
    legal = s.legal_actions()
    assert not W.ids(legal, M.SAW_IDS) and not W.ids(legal, W.ASSIGN_IDS)
    assert H.DONE in legal


def test_R054_cannot_saw_without_sawyer_or_mill_worker():
    """R-054 (negative): a saw but no sawyer and the mill worker used up cutting: no SAW."""
    steps = M.r1_steps(2, False, bearers=1, saws=1, cuts=(1,), carries=(0,))
    s = _at(steps, (1, "W4", 0), "w4_noworker")
    assert W.me(s, 0)["mill_worker_used"] is True
    legal = s.legal_actions()
    assert not W.ids(legal, M.SAW_IDS) and not W.ids(legal, W.ASSIGN_IDS)


def test_R054_mill_worker_can_saw_in_place_of_a_sawyer():
    """R-054/R-045: the mill worker may saw; it is then used for the round and the saw is spent."""
    steps = M.r1_steps(2, False, bearers=1, woodcutters=1, saws=1, cuts=(0,), carries=(0,))
    s = _at(steps, (1, "W4", 0), "w4_millsaw")
    assert W.me(s, 0)["mill_worker_used"] is False
    W.assign_if_needed(s, 1)
    W.play(s, M.saw(0, 4))
    _after(s)
    assert M.zone(s, "firewood_storage") == M.logs("firewood", 4)
    assert W.me(s, 0)["mill_worker_used"] is True
    assert W.me(s, 0)["equipment"]["saw"] == 0


# --- round 2 kinds


@functools.cache
def _softwood_round2() -> tuple[int, int]:
    for seed in range(150):
        run = R.drive(
            {"players": 2, "joinery": False},
            seed=seed,
            stop=lambda c: c.round == 2 and c.phase == "PK",
        )
        if not run.stopped:
            continue
        sn = W.snap(run.state)
        for a in range(6):
            if W.area_wood(sn, a)["softwood"] > 0:
                return seed, a
    raise AssertionError("no seed with round-2 softwood")


def _r2_sawn(kind: str, nlogs: int, stop: tuple[int, str, int]):
    seed, area = W.hardwood_round2_seed() if kind == HW else _softwood_round2()
    k = W.HW if kind == HW else W.SW
    st = M.r1_steps(2, False, saws=1, seed=seed)
    st.add(2, "PK", 0, H.PICK_AREA(area))
    st.add(2, "PK", 1, W.pick_not(area))
    st.add(
        2,
        "TR",
        0,
        H.MOVE_TO(R.loc(False, "bearers")),
        R.HIRE_BEARER,
        H.DONE,
        H.MOVE_TO(R.loc(False, "sawyers")),
        R.HIRE_SAWYER,
        H.DONE,
        R.MOVE_CLEARING,
    )
    st.add(2, "W1", 0, W.Opt(W.assign(1)), W.first_take(k))
    st.add(2, "W3", 0, W.Opt(W.assign(0)), W.move_wood(k, 0))
    st.add(2, "W4", 0, W.Opt(W.assign(0)), M.saw(k, nlogs))
    return M.reach(st, stop, key=("r2sawn", kind, nlogs, stop), n=2, j=False, seed=seed)


def test_R054_softwood_disk_gives_three_logs():
    """R-054 example: a softwood disk becomes 3 logs: 1 to storage, 2 to the sale area. Disks of
    other kinds are untouched; the saw token kept from round 1 is spent."""
    s = _r2_sawn(SW, 1, (2, "W5", 0))
    assert M.zone(s, "firewood_storage") == M.logs("softwood", 1)
    assert M.zone(s, "sale") == M.logs("softwood", 2)
    assert W.me(s, 0)["equipment"]["saw"] == 0


def test_R054_hardwood_disk_gives_one_log_and_saw_ids_bound_n():
    """R-054: a hardwood disk becomes 1 log (here to the sale area)."""
    s = _r2_sawn(HW, 0, (2, "W5", 0))
    assert M.zone(s, "sale") == M.logs("hardwood", 1)
    assert not M.zone(s, "firewood_storage")
    assert not M.zone(s, "sawing")


# --------------------------------------------------------------------------- R-055 / R-056


@pytest.mark.parametrize("joinery", BOOLS)
def test_R055_stage0_slot_takes_sale_area_piece_and_locks(joinery):
    """R-055: a no-bonus requirement accepts milled wood from the sale area; the placed piece is
    locked on the card (filled slot recorded, piece gone from the sale area)."""
    s = _w5_one(joinery, task=True)
    assert M.tasks(s) == [{"id": M.TASK, "filled": []}]
    assert M.zone(s, "sale") == M.logs("firewood", 4)
    legal = s.legal_actions()
    assert M.place_task(M.S_FW0, 0) in legal
    assert M.place_task(M.S_FW0, 1) not in legal  # drying 1 is empty
    assert M.place_task(M.S_FW0, 2) not in legal  # source 2 only in round 8 (Phase 4)
    W.play(s, M.place_task(M.S_FW0, 0))
    _after(s)
    t = M.tasks(s)[0]
    assert t["id"] == M.TASK and list(t["filled"]) == [M.S_FW0 - M.S_HW0]
    assert M.zone(s, "sale") == M.logs("firewood", 3)


def test_R055_plus1_slot_rejects_sale_area_piece():
    """R-055: a +1 requirement fits only second-drying-area wood; sale-area wood does not."""
    s = _w5_one(False, task=True)
    legal = s.legal_actions()
    for r in range(3):
        assert M.place_task(M.S_FW1, r) not in legal


def test_R055_slot_for_absent_kind_not_offered():
    """R-055: the hardwood slot cannot be filled with firewood (kind must match exactly), and
    there is no hardwood in round 1."""
    s = _w5_one(False, task=True)
    legal = s.legal_actions()
    for r in range(3):
        assert M.place_task(M.S_HW0, r) not in legal


def test_R055_unmilled_disk_does_not_fit_milled_slot_and_storage_is_not_a_source():
    """R-055: milledness must match, and wood in the firewood storage cannot be used. P0 holds
    task_10, the sale area has only an unmilled firewood disk, 4 milled logs sit in storage."""
    steps = M.r1_steps(
        2,
        False,
        bearers=2,
        woodcutters=1,
        sawyers=1,
        saws=1,
        task=M.TASK,
        cuts=(0, 1),
        carries=(0, 1),
        sawing=((0, 0, 4),),
    )
    s = _at(steps, (1, "W5", 0), "w5_task_disk_only")
    assert M.zone(s, "sale") == Counter({"firewood_disk": 1})
    assert M.zone(s, "firewood_storage") == M.logs("firewood", 4)
    assert not M.legal_in(s, M.PLACE_TASK_IDS)


def test_R055_no_task_card_no_placement():
    """R-055: wood may be placed only on cards the seat holds."""
    s = _w5_one(False, task=False)
    assert M.zone(s, "sale") == M.logs("firewood", 4)
    assert not M.legal_in(s, M.PLACE_TASK_IDS)


def test_R055_stage0_slot_accepts_first_drying_area_but_plus1_does_not():
    """R-055: round 2 phase 5, 2 logs in drying 1 and 2 in the sale area. The no-bonus slot
    accepts first-drying-area wood (source 1); the +1 slot accepts nothing (second area empty)."""
    s = _at(M.chain_steps(False), (2, "W5", 0), ("chain", False, "r2w5"))
    assert M.drying(s)[0] == M.logs("firewood", 2)
    assert M.zone(s, "sale") == M.logs("firewood", 2)
    legal = s.legal_actions()
    assert M.place_task(M.S_FW0, 1) in legal
    assert M.place_task(M.S_FW0, 0) in legal
    for r in range(3):
        assert M.place_task(M.S_FW1, r) not in legal


def test_R055_over_dried_wood_does_not_fit_but_exact_stage_does():
    """R-055: round 3 phase 5: only 2 logs in drying 2 (sale and drying 1 empty). The +1 slot
    accepts them; the no-bonus slot does not (over-dried wood does not fit)."""
    s = _at(M.chain_steps(False, r2_sell=2), (3, "W5", 0), ("chain", False, "r3w5"))
    assert M.drying(s) == [Counter(), M.logs("firewood", 2), Counter()]
    assert not M.zone(s, "sale")
    legal = s.legal_actions()
    for r in range(3):
        assert M.place_task(M.S_FW0, r) not in legal
    assert M.place_task(M.S_FW1, 0) in legal
    W.play(s, M.place_task(M.S_FW1, 0))
    _after(s)
    assert list(M.tasks(s)[0]["filled"]) == [2]
    assert M.drying(s)[1] == M.logs("firewood", 1)


def test_R056_partial_completion_across_rounds_pays_nothing_yet():
    """R-055/R-056: pieces may be placed one by one over rounds; the card stays held and
    unfinished (no hardwood), and placing never pays money (the reward comes at game end)."""
    s = _at(
        M.chain_steps(False, r2_place=True, r2_sell=2),
        (3, "W5", 0),
        ("chain", False, "r3w5placed"),
    )
    assert list(M.tasks(s)[0]["filled"]) == [1]  # placed in round 2
    before = M.money(s)
    W.play(s, M.place_task(M.S_FW1, 0))
    _after(s)
    assert sorted(M.tasks(s)[0]["filled"]) == [1, 2]
    assert M.money(s) == before
    assert M.tasks(s)[0]["id"] == M.TASK


# --------------------------------------------------------------------------- R-057 / R-063


def test_R057_joinery_placement_from_drying_2_any_slot_no_joiner_needed():
    """R-057: milled wood from the second drying area goes into a joinery slot chosen by the
    seat, without a joiner; one piece per kind (a second firewood is then illegal); locked."""
    s = _at(M.chain_steps(True, r2_sell=2), (3, "W5", 0), ("chain", True, "r3w5sold"), j=True)
    assert W.me(s, 0)["joiners"] == 0
    legal = s.legal_actions()
    for q in range(3):
        assert M.place_joinery(W.FW, q) in legal
    W.play(s, M.place_joinery(W.FW, 1))
    assert not M.legal_in(s, M.PLACE_JOINERY_IDS)  # second firewood: kind already there
    _after(s)
    assert list(W.me(s, 0)["joinery"]) == [None, "firewood", None]
    assert M.drying(s)[1] == M.logs("firewood", 1)


def test_R057_only_second_drying_area_wood_may_go_to_joinery():
    """R-057 (negative): round 2 phase 5 has milled wood in drying 1 and the sale area but none
    in drying 2: no joinery placement is legal."""
    s = _at(M.chain_steps(True), (2, "W5", 0), ("chain", True, "r2w5"), j=True)
    assert M.drying(s)[0] == M.logs("firewood", 2)
    assert not M.legal_in(s, M.PLACE_JOINERY_IDS)


def test_R063_no_joinery_placement_on_the_base_side():
    """R-063/R-057: with joinery=false there is no joinery placement even with wood in drying 2."""
    s = _at(M.chain_steps(False, r2_sell=2), (3, "W5", 0), ("chain", False, "r3w5"))
    assert M.drying(s)[1] == M.logs("firewood", 2)
    assert not M.legal_in(s, M.PLACE_JOINERY_IDS)


def test_R063_joiner_location_holds_one_joiner_only_with_joinery():
    """R-063/R-035: round 2 start: the path holds 1 joiner with joinery=true and none otherwise."""
    for j, want in ((True, 1), (False, 0)):
        s = _at(M.chain_steps(j), (2, "TR", 0), ("chain", j, "r2tr"), j=j)
        assert (W.snap(s)["path"]["joiner"] or 0) == want


def test_R063_wood_work_phases_identical_in_both_modes():
    """R-063: sawing, selling and drying behave the same on both sides: after the chain, the
    round-3 drying state is identical."""
    a = _at(M.chain_steps(False, r2_sell=2), (3, "W5", 0), ("chain", False, "r3w5"))
    b = _at(M.chain_steps(True, r2_sell=2), (3, "W5", 0), ("chain", True, "r3w5sold"), j=True)
    assert M.drying(a) == M.drying(b)
    assert M.money(a) == M.money(b)


# --------------------------------------------------------------------------- R-058


@pytest.mark.parametrize("joinery", BOOLS)
def test_R058_sale_area_prices_unmilled_firewood_3_milled_1(joinery):
    """R-058: unmilled firewood $3, milled firewood $1 from the sale area; sold wood leaves."""
    s = _at(M.two_pieces_steps(joinery, 0), (1, "W6", 0), ("w6two", joinery), j=joinery)
    assert M.zone(s, "sale") == Counter({"firewood_disk": 1, "firewood_log": 4})
    m0 = M.money(s)
    W.play(s, M.sell(0, M.FW_DISK), M.sell(0, M.FW_LOG))
    _after(s)
    assert M.money(s) == m0 + 4
    assert M.zone(s, "sale") == M.logs("firewood", 3)


def test_R058_only_sale_and_drying_areas_and_never_unmilled_hardwood():
    """R-058 (negative): sawing area and firewood storage wood cannot be sold in a seasonal
    round; unmilled hardwood has no price."""
    s = _at(M.two_pieces_steps(False, 2), (1, "W6", 0), ("w6two2", False))
    assert M.zone(s, "firewood_storage") == M.logs("firewood", 2)
    legal = s.legal_actions()
    for z in (4, 5):
        for p in range(6):
            assert M.sell(z, p) not in legal
    for z in range(4):
        assert M.sell(z, M.HW_DISK) not in legal
    assert M.sell(0, M.FW_DISK) in legal and M.sell(0, M.FW_LOG) in legal
    assert H.DONE in legal  # selling is optional for sale-area wood


def test_R058_first_drying_area_has_no_bonus():
    """R-058: milled firewood sold from drying 1 earns $1 each (bonus +0)."""
    st = M.chain_steps(False)
    st.add(2, "W6", 0, M.sell(1, M.FW_LOG), M.sell(1, M.FW_LOG))
    s = _at(st, (2, "W6", 0), ("chain", False, "r2w6"))
    assert M.drying(s)[0] == M.logs("firewood", 2)
    m0 = M.money(s)
    W.play(s, M.sell(1, M.FW_LOG), M.sell(1, M.FW_LOG))
    assert H.DONE in s.legal_actions()  # sale area wood may stay
    _after(s)
    assert M.money(s) == m0 + 2
    assert M.drying(s)[0] == Counter()


def test_R058_second_drying_area_bonus_plus_one():
    """R-058: milled firewood sold from drying 2 earns $1 + $1 = $2."""
    s = _at(M.chain_steps(False, r2_sell=2), (3, "W6", 0), ("chain", False, "r3w6"))
    assert M.drying(s)[1] == M.logs("firewood", 2)
    m0 = M.money(s)
    W.play(s, M.sell(2, M.FW_LOG))
    _after(s)
    assert M.money(s) == m0 + 2
    assert M.drying(s)[1] == M.logs("firewood", 1)


def test_R058_milled_hardwood_5_and_milled_softwood_2():
    """R-058: milled hardwood $5; milled softwood $2 each (round 2 sawing of each kind)."""
    s = _r2_sawn(HW, 0, (2, "W6", 0))
    m0 = M.money(s)
    W.play(s, M.sell(0, M.HW_LOG))
    _after(s)
    assert M.money(s) == m0 + 5
    s = _r2_sawn(SW, 1, (2, "W6", 0))
    m0 = M.money(s)
    W.play(s, M.sell(0, M.SW_LOG), M.sell(0, M.SW_LOG))
    _after(s)
    assert M.money(s) == m0 + 4


def test_R058_third_drying_area_wood_must_be_sold_with_plus_two():
    """R-058: wood on the third drying area must be sold: DONE is illegal until it is, and a milled
    firewood log pays $1 + $2 = $3. Reached in round 5 (round 3 phase 7 fills drying 3, winter
    year 1 in between). P0 must survive the winter without selling that log (R-073 sells drying
    wood when short): it takes 2 loans ($13 - $1 bearer = $12), holds the 2 path food tokens (food
    bill 3 x (5 - 2) = $9) and 3 of the disk's 4 logs in the firewood storage (heating 4: 1 piece
    missing = $3), so winter costs exactly the $12 and the 4th log (in drying 3) is untouched."""
    st = V.fall_steps(
        False, loans=2, food_tokens=2, saw=True, sawyer=True, bearers=1, carries=(0,),
        sawing=((0, 0, 3),), dry_round1=1,
    )  # fmt: skip
    s = V.reach(st, (5, "W6", 0))
    assert V.requirement(V.snap(s), 1) == (5, 4)  # winter_1_4 top, seed 1
    assert M.drying(s)[2] == M.logs("firewood", 1)
    assert H.DONE not in s.legal_actions()
    m0 = M.money(s)
    assert m0 == 0
    W.play(s, M.sell(3, M.FW_LOG))
    assert H.DONE in s.legal_actions()
    _after(s)
    assert M.money(s) == m0 + 3


# --------------------------------------------------------------------------- R-059


@pytest.mark.parametrize("joinery", BOOLS)
def test_R059_sale_area_enters_first_drying_up_to_two_logs(joinery):
    """R-059: the seat chooses which sale-area pieces enter drying 1, as many as fit: 2 milled
    logs; a third is not legal; the rest stays in the sale area."""
    s = _at(M.one_disk_steps(joinery), (1, "W7", 0), ("w7one", joinery), j=joinery)
    assert M.zone(s, "sale") == M.logs("firewood", 4)
    W.play(s, M.dry_enter(M.FW_LOG), M.dry_enter(M.FW_LOG))
    assert M.dry_enter(M.FW_LOG) not in s.legal_actions()
    assert H.DONE in s.legal_actions()
    _after(s)
    assert M.drying(s)[0] == M.logs("firewood", 2)
    assert M.zone(s, "sale") == M.logs("firewood", 2)


@pytest.mark.parametrize("disk_first", BOOLS)
def test_R059_unmilled_disk_never_shares_a_drying_area_with_logs(disk_first):
    """R-059: a drying area holds 1 unmilled disk or up to 2 milled logs, never both. Sale area
    holds 1 unmilled firewood disk and 4 logs."""
    s = _at(M.two_pieces_steps(False, 0), (1, "W7", 0), ("w7two", False))
    assert M.zone(s, "sale") == Counter({"firewood_disk": 1, "firewood_log": 4})
    if disk_first:
        W.play(s, M.dry_enter(M.FW_DISK))
        assert M.dry_enter(M.FW_LOG) not in s.legal_actions()
        assert M.dry_enter(M.FW_DISK) not in s.legal_actions()
    else:
        W.play(s, M.dry_enter(M.FW_LOG))
        assert M.dry_enter(M.FW_DISK) not in s.legal_actions()
        assert M.dry_enter(M.FW_LOG) in s.legal_actions()
    _after(s)
    want = Counter({"firewood_disk": 1}) if disk_first else M.logs("firewood", 1)
    assert M.drying(s)[0] == want


def test_R059_areas_advance_right_to_left_without_chaining():
    """R-059: round 2 phase 7: drying 1 holds 2 logs, sale area 2 logs. After P0 enters the 2
    sale logs: old drying-1 wood is in drying 2 (not drying 3), new wood in drying 1."""
    st = M.chain_steps(False)
    st.add(2, "W7", 0, M.dry_enter(M.FW_LOG), M.dry_enter(M.FW_LOG))
    s = _at(st, (2, "W7", 0), ("chain", False, "r2w7"))
    assert M.drying(s)[0] == M.logs("firewood", 2) and M.zone(s, "sale") == M.logs("firewood", 2)
    W.play(s, M.dry_enter(M.FW_LOG), M.dry_enter(M.FW_LOG))
    _after(s)
    assert M.drying(s) == [M.logs("firewood", 2), M.logs("firewood", 2), Counter()]
    assert not M.zone(s, "sale")


def test_R059_drying_wood_cannot_be_left_behind_sale_wood_may_stay():
    """R-059: finishing the phase without entering anything still advances drying 1 to drying 2
    (wood cannot be left behind); unentered sale-area wood stays in the sale area."""
    s = _at(M.chain_steps(False), (2, "W7", 0), ("chain", False, "r2w7"))
    _after(s)
    assert M.drying(s) == [Counter(), M.logs("firewood", 2), Counter()]
    assert M.zone(s, "sale") == M.logs("firewood", 2)


def test_R059_second_area_advances_to_third():
    """R-059: round 3 phase 7: drying 2's wood moves to drying 3 (it will be sold next time)."""
    s = _at(M.chain_steps(False, r2_sell=2), (3, "W7", 0), ("chain", False, "r3w7"))
    assert M.drying(s)[1] == M.logs("firewood", 2)
    _after(s)
    assert M.drying(s) == [Counter(), Counter(), M.logs("firewood", 2)]


# --------------------------------------------------------------------------- R-082


def _final_margin(q: int) -> list[float]:
    """Play round 1..3 per chain_steps (joiner hired in round 2, one firewood log placed into
    joinery slot q in round 3), then default play to the end. Returns margin returns."""
    st = M.chain_steps(True, r2_sell=2, joiner=True, joinery_q=q)
    run = R.drive({"players": 2, "joinery": True, "returns": "margin"}, seed=M.SEED, policy=st)
    assert run.state.is_terminal()
    return list(run.state.returns())


def test_R082_joinery_piece_sells_for_milled_price_plus_3_only_if_slot_has_joiner():
    """R-082: with 1 joiner only slot 1 (index 0) is covered. The same game with the firewood log
    in slot 1 versus slot 2 differs by exactly $1 + $3 = $4 in P0's final dollars; 2-player
    margin returns are (d0 - d1) / 50, so P0's return differs by 4/50 and P1's by -4/50."""
    covered, uncovered = _final_margin(0), _final_margin(1)
    assert covered[0] - uncovered[0] == pytest.approx(4 / 50)
    assert covered[1] - uncovered[1] == pytest.approx(-4 / 50)


def test_R082_slots_without_a_joiner_are_equivalent_and_worth_nothing():
    """R-082/R-057 (negative): slots 2 and 3 have no joiner with 1 joiner, so placing the piece
    in either gives the same final result."""
    assert _final_margin(1) == pytest.approx(_final_margin(2))
