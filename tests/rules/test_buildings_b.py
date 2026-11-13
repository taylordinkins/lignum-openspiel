"""Phase 4 unit 11: Buildings B, Drying Area Upgrade, Small Joinery, Inn (R-111, R-112, R-113;
with R-059, R-096, R-058, R-082, R-057, R-088, R-040).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and tests/harness.py only, in the style of
test_buildings_a.py: a seat gets a building by `bldscen.give` (white-box assignment of the state's
`held_buildings`) on a state reached by scripted play with joinery=true. The buildings are
implemented, so the tests carry no pending marker.

Ids: MOVE_TO(l) = 7 + l, PW location 8, PLAN_WORK(c, pair) = 67 + 3c + pair - 1 (c = order in
data/components/planned_work.yaml), DRY_ENTER(piece) = 432 + piece (0 unmilled disk, 1 milled log
of the firewood kind).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from tests import harness as H
from tests.support import bldscen as B
from tests.support import pwscen as P
from tests.support import rounds as R
from tests.support import sawmill as SM
from tests.support import travel as T
from tests.support import winter as V
from tests.support import woodwork as W

PW_LOC = 8
FW_DISK, FW_LOG = 0, 1
LOG, DISK = "firewood_log", "firewood_disk"
CLEAR = R.MOVE_CLEARING
DRYC = B.PW_IDS.index("pw_drying")
SAWC = B.PW_IDS.index("pw_sawing")
TRADEC = B.PW_IDS.index("pw_trade")
CUTC = B.PW_IDS.index("pw_cutting")
HEATC = B.PW_IDS.index("pw_heating_supply")

UPGRADE, SMALLJ, INN = "drying_area_upgrade", "small_joinery", "inn"


def _tup(t: tuple[Any, ...], i: int, v: Any) -> tuple[Any, ...]:
    return tuple(v if j == i else x for j, x in enumerate(t))


# =========================================================================== R-111 fixtures


def _sale(s: Any) -> Counter[str]:
    return W.pm(B.me(s)["sale"])


def _drying(s: Any) -> list[Counter[str]]:
    return [W.pm(x) for x in B.me(s)["drying"]]


def _count_entries(s: Any, piece: int) -> int:
    """Apply DRY_ENTER(piece) while it is legal; returns how many went in."""
    n = 0
    while SM.dry_enter(piece) in s.legal_actions():
        s.apply_action(SM.dry_enter(piece))
        n += 1
        assert n < 20
    return n


def _dry_state(
    key: str,
    *,
    plan: int | None,
    dests: tuple[int, ...],
    mills: int,
    saws: int,
    check: Any,
    building: bool,
) -> Any:
    """P0 (joinery game) cuts len(dests) firewood disks in round 1 and carries each to dest 0
    (sawing area) or 1 (sale area, unmilled); `mills` disks are milled in round 2 into logs in the
    sale area. With `plan` P0 plans that card in round 1 with pair 1 (target round 2). Stops at
    round 2's drying phase (W7), P0 to move."""
    n = len(dests)
    r1: list[Any] = [("hire", "bearers", n)]
    if n == 2:
        r1.append(("hire", "woodcutters", 1))
    if saws:
        r1.append(("spots", ("saw",), 1))
    if plan is not None:
        r1.append(("plan", plan, 1))
    wants: dict[tuple[int, int], list[Any]] = {(1, 0): r1}
    if mills:
        wants[(2, 0)] = [("hire", "sawyers", 1)]

    def steps() -> W.Steps:
        st = W.Steps()
        for src in [0, 1] if n == 2 else [1]:
            st.add(1, "W1", 0, W.Opt(W.assign(src)), W.first_take(-1))
        for d in dests:
            st.add(1, "W3", 0, W.Opt(W.assign(0)), W.move_wood(W.FW, d))
        if mills:
            st.add(2, "W4", 0, W.Opt(W.assign(0)), W.Opt(SM.saw(0, 0)))
        return st

    cards = [B.HUT, DRYC, TRADEC, B.CRAFT]
    s = B.reach(key, wants, steps, ("node", 2, "W7", 0), check, cards)
    if building:
        B.give(s, 0, UPGRADE)
    return s


def _two_disks(plan: int | None, building: bool) -> Any:
    return _dry_state(
        ("b_two_disks", plan),
        plan=plan,
        dests=(1, 1),
        mills=0,
        saws=0,
        check=lambda s: _sale(s) == Counter({DISK: 2}),
        building=building,
    )


def _logs_and_disk(plan: int | None, building: bool) -> Any:
    return _dry_state(
        ("b_logs_disk", plan),
        plan=plan,
        dests=(0, 1),
        mills=1,
        saws=1,
        check=lambda s: _sale(s) == Counter({LOG: 4, DISK: 1}),
        building=building,
    )


def _to_next_boundary(s: Any, pred: Any, limit: int = 600) -> None:
    first = True
    for _ in range(limit):
        if not first and not s.is_chance_node():
            sn = R.try_snapshot(s)
            if sn is not None and pred(sn, s.current_player()):
                return
        first = False
        if s.is_chance_node():
            s.apply_action(s.chance_outcomes()[0][0])
        elif H.DONE in s.legal_actions():
            s.apply_action(H.DONE)
        elif CLEAR in s.legal_actions():
            s.apply_action(CLEAR)
        else:
            s.apply_action(s.legal_actions()[0])
    raise AssertionError("to_next_boundary: limit")


# =========================================================================== R-111


def test_R111_two_unmilled_disks_fit_in_the_first_area():
    """R-111: with the Drying Area Upgrade a drying area holds 2 unmilled disks (instead of 1)."""
    s = _two_disks(None, True)
    assert _count_entries(s, FW_DISK) == 2


def test_R111_without_the_upgrade_only_one_disk_fits():
    """R-059 baseline for R-111: the same two disks, no building, fill the area with one."""
    s = _two_disks(None, False)
    assert _count_entries(s, FW_DISK) == 1


def test_R111_one_log_and_one_disk_may_share_an_area_disk_first():
    """R-111: a milled log and an unmilled disk may share a drying area (disk then log)."""
    s = _logs_and_disk(None, True)
    s.apply_action(SM.dry_enter(FW_DISK))
    assert SM.dry_enter(FW_LOG) in s.legal_actions()
    s.apply_action(SM.dry_enter(FW_LOG))


def test_R111_one_log_and_one_disk_may_share_an_area_log_first():
    """R-111: the mix also works log first, then disk."""
    s = _logs_and_disk(None, True)
    s.apply_action(SM.dry_enter(FW_LOG))
    assert SM.dry_enter(FW_DISK) in s.legal_actions()
    s.apply_action(SM.dry_enter(FW_DISK))


def test_R111_area_with_a_disk_and_a_log_is_full():
    """R-111: two pieces is the limit: after disk + log no further log or disk may enter."""
    s = _logs_and_disk(None, True)
    s.apply_action(SM.dry_enter(FW_DISK))
    s.apply_action(SM.dry_enter(FW_LOG))
    legal = s.legal_actions()
    assert SM.dry_enter(FW_LOG) not in legal and SM.dry_enter(FW_DISK) not in legal


def test_R111_three_pieces_never_fit_without_pw_drying():
    """R-111: two logs fill an area; a third log (4 are available) may not enter, nor a disk."""
    s = _logs_and_disk(None, True)
    assert _count_entries(s, FW_LOG) == 2
    assert SM.dry_enter(FW_DISK) not in s.legal_actions()


def test_R111_without_the_upgrade_a_disk_and_a_log_never_mix():
    """R-059 baseline for R-111: with no building, once a disk is in, no log may enter."""
    s = _logs_and_disk(None, False)
    s.apply_action(SM.dry_enter(FW_DISK))
    assert SM.dry_enter(FW_LOG) not in s.legal_actions()


def test_R111_the_other_seats_upgrade_does_not_help_me():
    """R-111: the building is the holder's; P0 without it, while P1 holds it, fits 1 disk."""
    s = _two_disks(None, False)
    B.give(s, 1, UPGRADE)
    assert _count_entries(s, FW_DISK) == 1


def test_R111_mixed_pair_advances_together_to_the_next_area():
    """R-111/R-059: a disk + log pair in the first area moves together into the second area at the
    next drying phase (round 3), like any stack."""
    s = _logs_and_disk(None, True)
    s.apply_action(SM.dry_enter(FW_DISK))
    s.apply_action(SM.dry_enter(FW_LOG))
    _to_next_boundary(s, lambda sn, p: (sn["round"], sn["phase"], p) == (3, "W7", 0))
    assert _drying(s)[0] == Counter({DISK: 1, LOG: 1})
    _to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert _drying(s)[:2] == [Counter(), Counter({DISK: 1, LOG: 1})]


# ----- with PW Drying (R-096): the first area holds 4 pieces, any mix


def test_R111_pw_drying_and_upgrade_hold_four_mixed_pieces_in_area_one():
    """R-111 + R-096: in the PW Drying target round the first area holds 4 pieces of any mix:
    one disk and three logs all enter, a fifth piece does not."""
    s = _logs_and_disk(DRYC, True)
    s.apply_action(SM.dry_enter(FW_DISK))
    for _ in range(3):
        assert SM.dry_enter(FW_LOG) in s.legal_actions()
        s.apply_action(SM.dry_enter(FW_LOG))
    legal = s.legal_actions()
    assert SM.dry_enter(FW_LOG) not in legal and SM.dry_enter(FW_DISK) not in legal


def test_R111_pw_drying_and_upgrade_log_first_then_disk_then_logs():
    """R-111 + R-096: the 4 pieces may be entered in any order (log, disk, log, log)."""
    s = _logs_and_disk(DRYC, True)
    for piece in (FW_LOG, FW_DISK, FW_LOG, FW_LOG):
        assert SM.dry_enter(piece) in s.legal_actions()
        s.apply_action(SM.dry_enter(piece))


def test_R111_pw_drying_without_the_upgrade_still_never_mixes():
    """R-096 baseline for R-111: PW Drying alone: once a disk is in, no log may enter."""
    s = _logs_and_disk(DRYC, False)
    s.apply_action(SM.dry_enter(FW_DISK))
    assert SM.dry_enter(FW_LOG) not in s.legal_actions()


def test_R111_pw_drying_and_upgrade_four_pieces_advance_together_over_capacity():
    """R-111/R-096 (O-U4-5): the 4 mixed pieces in area 1 are forced on together into area 2 at
    round 3's drying phase, over the upgraded capacity of 2."""
    s = _logs_and_disk(DRYC, True)
    s.apply_action(SM.dry_enter(FW_DISK))
    for _ in range(3):
        s.apply_action(SM.dry_enter(FW_LOG))
    _to_next_boundary(s, lambda sn, p: (sn["round"], sn["phase"], p) == (3, "W7", 0))
    _to_next_boundary(s, lambda sn, p: sn["round"] >= 4 or sn["phase"] != "W7")
    assert _drying(s)[:2] == [Counter(), Counter({DISK: 1, LOG: 3})]


def _with_area(s: Any, area: tuple[int, ...]) -> list[str]:
    """Put `area` (3 disk counts then 3 log counts) into P0's first drying area; run the checker."""
    from lignum.invariants import check_invariants

    s.dry = _tup(s.dry, 0, _tup(s.dry[0], 0, area))
    return check_invariants(s)


def test_R111_invariant_accepts_two_mixed_pieces_with_the_upgrade():
    """R-111: the invariant check allows a disk and a log together in an upgraded seat's area."""
    s = _logs_and_disk(None, True)
    assert _with_area(s, (1, 0, 0, 1, 0, 0)) == []


def test_R111_invariant_flags_three_pieces_outside_a_pw_drying_target_round():
    """R-111: three pieces in one area exceed the upgraded capacity of 2 without PW Drying."""
    s = _logs_and_disk(None, True)
    errs = _with_area(s, (1, 0, 0, 2, 0, 0))
    assert any("drying 1 over capacity" in e for e in errs)


def test_R111_upgrade_values_come_from_data_not_code():
    """R-111 / CLAUDE.md: the capacity is a data parameter of the building in buildings.yaml."""
    b = {x["id"]: x for x in _buildings()}
    assert b[UPGRADE]["params"]["drying_area_capacity"] == 2


def _buildings() -> list[dict[str, Any]]:
    import yaml

    with open(R.ROOT / "data" / "components" / "buildings.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["buildings"]


# =========================================================================== R-112


def _final(building_seat: int | None, slot: int) -> tuple[Any, list[float], list[float]]:
    """Play to the end with P0 holding one firewood log in joinery `slot` and one joiner, handing
    `building_seat` the Small Joinery at round 8's last N4 turn. Returns (state, final dollars of
    the reference model without the building, returns of that model)."""
    st = SM.chain_steps(True, r2_sell=2, joiner=True, joinery_q=slot)
    run = R.drive(
        {**V.params(2, True), "returns": "margin"},
        seed=V.SEED,
        policy=V.policy(st),
        stop=V._last_n4_of_round_8,  # pyright: ignore[reportPrivateUsage]
    )
    assert run.stopped
    s = run.state
    sn = V.snap(s)
    d = [float(V.final_dollars(x, V.requirement(sn, 2))["dollars"]) for x in H.seats(sn)]
    p0 = H.seats(sn)[0]
    assert p0["joiners"] == 1 and p0["joinery"][slot] == "firewood"
    if building_seat is not None:
        B.give(s, building_seat, SMALLJ)
    for _ in range(500):
        if s.is_terminal():
            return s, d, V.margin_returns(d)
        legal = s.legal_actions()
        sn2 = R.try_snapshot(s)
        if sn2 is not None and sn2["phase"] == "FS":
            sales = [a for a in legal if V.RIVER_SALE0 <= a < V.RIVER_SALE0 + 2]
            s.apply_action(sales[0])
            continue
        s.apply_action(H.DONE if H.DONE in legal else legal[0])
    raise AssertionError("too many steps")


def test_R112_baseline_joinery_piece_earns_price_plus_three():
    """R-082 baseline for R-112: no building, a covered milled firewood log sells for $1 + $3, so
    P0 ends $4 ahead of P1 and the margin returns follow the model."""
    s, d, want = _final(None, 0)
    assert d[0] - d[1] == 4
    assert list(s.returns()) == pytest.approx(want)


def test_R112_small_joinery_bonus_is_four_dollars():
    """R-112: with Small Joinery the covered piece earns $1 + $4: P0 ends $5 ahead of P1."""
    s, d, _ = _final(0, 0)
    d2 = [d[0] + 1, d[1]]
    assert list(s.returns()) == pytest.approx(V.margin_returns(d2))


def test_R112_piece_in_a_slot_without_a_joiner_is_still_unsellable():
    """R-112: slot 1 has no joiner (one joiner): the piece earns nothing even with Small
    Joinery; P0 and P1 end level."""
    s, d, _ = _final(0, 1)
    assert d[0] - d[1] == 0
    assert list(s.returns()) == pytest.approx(V.margin_returns(d))


def test_R112_other_seats_small_joinery_does_not_raise_my_bonus():
    """R-112: P1 holds the building but sells no joinery piece; P0's bonus stays $3."""
    s, d, want = _final(1, 0)
    assert d[0] - d[1] == 4
    assert list(s.returns()) == pytest.approx(want)


def test_R112_bonus_value_comes_from_data_not_code():
    """R-112 / CLAUDE.md: the bonus is a data parameter of the building in buildings.yaml."""
    b = {x["id"]: x for x in _buildings()}
    assert b[SMALLJ]["params"]["joinery_bonus"] == 4


# =========================================================================== R-113


def _three(inn_seats: tuple[int, ...] = ()) -> Any:
    s = P.build([SAWC, TRADEC, DRYC, CUTC, HEATC], 1, 3)
    for seat in inn_seats:
        B.give(s, seat, INN)
    return s


def _plan_now(s: Any, c: int, pair: int) -> None:
    T.play(s, H.MOVE_TO(PW_LOC), P.PLAN(c, pair))


def _money(s: Any, i: int) -> int:
    return B.me(s, i)["money"]


def _plans(s: Any) -> list[dict[str, Any]]:
    return list(T.snap(s)["planned_work"]["plans"])


def test_R113_baseline_second_planner_pays_for_the_first_token():
    """R-088 baseline for R-113: without the Inn P1 planning Sawing after P0 pays $1."""
    s = _three()
    _plan_now(s, SAWC, 1)
    _plan_now(s, SAWC, 1)
    assert _money(s, 1) == 4


def test_R113_inn_seat_plans_a_card_with_tokens_for_free():
    """R-113: P1 holds the Inn; Sawing already has P0's token; P1 pays $0 and the plan is made."""
    s = _three((1,))
    _plan_now(s, SAWC, 1)
    _plan_now(s, SAWC, 1)
    assert _money(s, 1) == 5
    assert [p["seat"] for p in _plans(s)] == [0, 1]


def test_R113_inn_seats_tokens_still_count_for_other_seats():
    """R-113: P0 and P1 (both with the Inn) plan Sawing for free, leaving 2 tokens on it; P2
    without the Inn pays $2."""
    s = _three((0, 1))
    _plan_now(s, SAWC, 1)
    _plan_now(s, SAWC, 1)
    assert (_money(s, 0), _money(s, 1)) == (5, 5)
    _plan_now(s, SAWC, 1)
    assert _money(s, 2) == 3


def test_R113_inn_seat_with_two_tokens_on_the_card_pays_nothing():
    """R-113: Sawing holds 2 tokens; the Inn seat pays $0 (not $1 off $2); without it, $2."""
    s = _three((2,))
    for _ in range(3):
        _plan_now(s, SAWC, 1)
    assert [_money(s, i) for i in range(3)] == [5, 4, 5]
    s = _three()
    for _ in range(3):
        _plan_now(s, SAWC, 1)
    assert _money(s, 2) == 3


def test_R113_inn_seat_free_plan_counts_one_token_for_the_next_payer():
    """R-113: P0 holds the Inn and plans Sawing (free anyway); P1 without it pays $1."""
    s = _three((0,))
    _plan_now(s, SAWC, 1)
    _plan_now(s, SAWC, 1)
    assert _money(s, 0) == 5 and _money(s, 1) == 4


def test_R113_inn_does_not_make_other_seats_plans_free():
    """R-113: P0 holds the Inn; P1 and P2 without it still pay $1 and $2 on a shared card."""
    s = _three((0,))
    for _ in range(3):
        _plan_now(s, SAWC, 1)
    assert [_money(s, i) for i in range(3)] == [5, 4, 3]


def test_R113_inn_seat_without_money_can_plan_a_card_with_tokens():
    """R-113/R-040: P1 holds the Inn and $0; Sawing has a token; the plan is still legal and
    costs nothing (money stays $0)."""
    s = _three((1,))
    _plan_now(s, SAWC, 1)
    s.money = _tup(s.money, 1, 0)
    assert H.MOVE_TO(PW_LOC) in s.legal_actions()
    T.play(s, H.MOVE_TO(PW_LOC))
    assert P.PLAN(SAWC, 1) in s.legal_actions()
    T.play(s, P.PLAN(SAWC, 1))
    assert _money(s, 1) == 0
    assert len(_plans(s)) == 2


def test_R113_plan_records_are_unchanged_by_the_inn():
    """R-113/R-088: with the Inn the plan still records card, pair and target round (1 + pair)."""
    s = _three((1,))
    _plan_now(s, SAWC, 1)
    _plan_now(s, SAWC, 2)
    assert _plans(s)[1] == {"seat": 1, "card": "pw_sawing", "pair": 2, "target": 3}


def test_R113_cost_value_comes_from_data_not_code():
    """R-113 / CLAUDE.md: the planned-work cost is a data parameter of the Inn."""
    b = {x["id"]: x for x in _buildings()}
    assert b[INN]["params"]["planned_work_cost"] == 0
