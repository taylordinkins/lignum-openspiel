"""Phase 2 unit 7: wood-work framework and wood zones (R-045, R-046).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and
tests/support/{rounds,travel,woodwork}.py (public API only).

Notes
  * Wood work is implemented; the temporary W1 stub that earlier versions of these tests were
    written against is gone, and no test here carries a pending marker.
  * Whether a seat with nothing to do is skipped (ACTIONS A2) is not fixed by the spec, so the
    order tests only assert what is present, never that a phase has a node for every seat.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import woodwork as W

PLAYERS = (2, 3, 4)
W_ORDER = ["W1", "W2", "W3", "W4", "W5", "W6", "W7"]


def _p(n: int, j: bool = False) -> dict[str, Any]:
    return {"players": n, "joinery": j}


@pytest.mark.parametrize("joinery", (False, True))
@pytest.mark.parametrize("n", PLAYERS)
def test_R045_phases_run_in_order_one_turn_per_seat_in_clearing_order(n, joinery):
    """R-045: the seven phases run W1..W7 in order each seasonal round; within a phase the seats
    act once each in clearing order (A, B, C, D) and a phase never resumes after the next began."""
    seen: list[tuple[int, str, int, list[int]]] = []

    def rec(ctx: R.Ctx) -> int | None:
        if ctx.snap is not None and ctx.phase in W_ORDER:
            seen.append((ctx.round, ctx.phase, ctx.player, list(ctx.snap["clearing_order"])))
        return None

    R.drive(_p(n, joinery), seed=3, policy=rec)
    assert seen
    for rnd in R.SEASONAL:
        rows = [r for r in seen if r[0] == rnd]
        assert rows, rnd
        phases = [W_ORDER.index(r[1]) for r in rows]
        assert phases == sorted(phases), f"round {rnd}: phases out of order"
        for ph in W_ORDER:
            prs = [r for r in rows if r[1] == ph]
            if not prs:
                continue
            players = [r[2] for r in prs]
            clearing = prs[0][3]
            assert len(players) == len(set(players)), f"round {rnd} {ph}: a seat acted twice"
            assert players == [c for c in clearing if c in players], f"round {rnd} {ph}"


def test_R045_clearing_order_is_turn_order_and_phase_waits_for_every_seat():
    """R-045/R-044: P0 hires a bearer then enters the clearing last, so the clearing order is
    P1, P2, P3, P0 (slots A..D). W1 is played P1, P2, P3, P0 and the phase marker moves on only
    after the fourth DONE."""
    steps = W.Steps().add(
        1, "TR", 0, H.MOVE_TO(R.loc(False, "bearers")), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING
    )
    s = W.reach(4, False, 1, steps, (1, "W1", 1))
    sn = W.snap(s)
    assert sn["clearing_order"] == [1, 2, 3, 0]
    assert [T.seat_of(sn, i)["foreman"] for i in (1, 2, 3, 0)] == ["A", "B", "C", "D"]
    order: list[int] = []
    while H.phase_of(s) == "W1":
        order.append(s.current_player())
        W.end_turn(s)
    assert order == [1, 2, 3, 0]


@pytest.mark.parametrize("n", PLAYERS)
def test_R045_done_is_always_legal_in_woodcutting_and_transportation(n):
    """R-045: a seat may do nothing in a phase; in W1 and W3 DONE is legal at every turn start
    (ACTIONS 4 matrix: DONE is a legal action in W1 and W3, nothing there is compulsory)."""
    checked: set[str] = set()

    def rec(ctx: R.Ctx) -> int | None:
        if ctx.snap is not None and ctx.phase in ("W1", "W3"):
            assert H.DONE in ctx.legal, (ctx.round, ctx.phase, ctx.player)
            checked.add(ctx.phase)
        return None

    R.drive(_p(n), seed=2, policy=rec)
    assert checked


def test_R045_mill_worker_used_in_woodcutting_is_gone_for_transportation():
    """R-045 (C6): the mill worker stands in once per round. P0 cuts one piece with it in W1, so in
    W3 P0 (no bearers) has no worker: no ASSIGN_WORKER, MOVE_WOOD, RIVER_MOVE or USE_WAGON, and
    the dump shows mill_worker_used."""
    steps = W.Steps().add(1, "W1", 0, *W.cut(1, W.FW, src=1))
    s = W.reach(3, False, 1, steps, (1, "W3", 0))
    sn = W.snap(s)
    assert sn["phase"] == "W3" and s.current_player() == 0
    assert T.seat_of(sn, 0)["mill_worker_used"] is True
    assert W.zone(sn, 0, "woodpile") == {"firewood_disk": 1}
    legal = s.legal_actions()
    assert not W.ids(legal, W.ASSIGN_IDS)
    assert not W.ids(legal, W.MOVE_WOOD_IDS)
    assert not W.ids(legal, W.RIVER_IDS)
    assert W.USE_WAGON not in legal
    assert H.DONE in legal


def test_R046_unmilled_hardwood_goes_to_sawing_area_only():
    """R-046: unmilled hardwood can only go to the sawing area. A hardwood disk in the woodpile:
    MOVE_WOOD(hardwood, sawing) is legal, MOVE_WOOD(hardwood, sale) and a raft move without a
    raft are not."""
    seed, h = W.hardwood_round2_seed()
    steps = _hardwood_steps(h)
    steps.add(
        2, "TR", 0, H.MOVE_TO(R.loc(False, "bearers")), R.HIRE_BEARER, H.DONE, R.MOVE_CLEARING
    )
    steps.add(2, "W1", 0, *W.cut(1, W.HW, src=1))
    s = W.reach(2, False, seed, steps, (2, "W3", 0))
    sn = W.snap(s)
    assert W.zone(sn, 0, "woodpile")["hardwood_disk"] == 1
    W.assign_if_needed(s, 0)
    legal = s.legal_actions()
    assert W.move_wood(W.HW, 0) in legal
    assert W.move_wood(W.HW, 1) not in legal
    assert W.river_move(W.HW) not in legal
    W.play(s, W.move_wood(W.HW, 0))
    W.end_turn(s)
    after = W.snap(s)
    assert W.zone(after, 0, "sawing")["hardwood_disk"] == 1
    assert not W.zone(after, 0, "sale")


def _hardwood_steps(h: int) -> W.Steps:
    steps = W.Steps()
    steps.add(2, "PK", 0, H.PICK_AREA(h))
    steps.add(2, "PK", 1, W.pick_not(h))
    return steps
