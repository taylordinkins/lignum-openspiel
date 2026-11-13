"""Phase 2 unit 10: loans (R-075, R-076, R-077 without the game-end repayment).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only. Loan legality inside the winter
shortfall is in test_winter_payments.py (R-073). The game-end repayment (R-077 last step, R-083,
R-085) needs a finished game and belongs to the scoring unit.

Notes
  * Loans taken at a turn boundary keep it a boundary (SCENARIOS 1.3: "except possibly loans"), so
    money and loans can be read right after TAKE_LOAN.
  * ACTIONS section 3: TAKE_LOAN is legal at any decision node of the acting seat except SP and PK
    while loans < 2 (A5 is open for SP/PK, structure-only).
"""

from __future__ import annotations

from typing import Any

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T
from tests.support import winter as V


def _money_loans(state: Any, seat: int = 0) -> tuple[int, int]:
    s = T.seat_of(T.snap(state), seat)
    return s["money"], s["loans"]


def test_R075_first_and_second_loan_give_four_dollars_each_and_a_third_is_illegal():
    """R-075: the first loan gives $4 (card on its 4/7 side), the second flips the card and gives
    another $4; a seat holds at most 2 loans, so TAKE_LOAN is gone afterwards."""
    s = T.start(2)
    assert _money_loans(s) == (5, 0) and H.TAKE_LOAN in s.legal_actions()
    s.apply_action(H.TAKE_LOAN)
    assert _money_loans(s) == (9, 1) and H.TAKE_LOAN in s.legal_actions()
    s.apply_action(H.TAKE_LOAN)
    assert _money_loans(s) == (13, 2)
    assert H.TAKE_LOAN not in s.legal_actions()
    assert s.current_player() == 0  # taking a loan does not end the turn


def test_R075_four_loan_cards_serve_four_seats_two_loans_each():
    """R-075: four loan cards, one per seat: with 4 seats everyone can take both loans; each ends
    with $13 and 2 loans."""
    pol = R.Script({(1, s): [H.TAKE_LOAN, H.TAKE_LOAN, R.MOVE_CLEARING] for s in range(4)})
    run = R.drive(V.params(4), seed=2, policy=pol, stop=lambda c: c.round == 2)
    assert run.stopped
    for seat in H.seats(run.event(2).after):
        assert (seat["money"], seat["loans"]) == (13, 2)


def test_R075_loans_do_not_change_other_seats():
    """R-075: a loan is the acting seat's own: other seats keep $5 and no loans."""
    s = T.start(3)
    s.apply_action(H.TAKE_LOAN)
    sn = T.snap(s)
    assert [(x["money"], x["loans"]) for x in H.seats(sn)] == [(9, 1), (5, 0), (5, 0)]


def test_R076_loan_is_legal_at_any_node_of_own_turn_except_setup_picks():
    """R-076 / ACTIONS 1.7: TAKE_LOAN is legal at every decision node of a supply-path or
    wood-work turn (and, once winter exists, bonus and N1..N4 turns) while loans < 2, and not in
    SP or PK. Recorded over a whole default game for every seat; a seat reaching 2 loans in the
    forced winter shortfall is not checked."""
    seen: dict[str, set[bool]] = {}

    def probe(ctx: R.Ctx) -> int | None:
        if ctx.snap is not None:
            loans = H.seats(ctx.snap)[ctx.player]["loans"]
            if ctx.phase in ("SP", "PK") or (loans < 2 and ctx.phase != "SF"):
                seen.setdefault(ctx.phase, set()).add(H.TAKE_LOAN in ctx.legal)
        return R.cut_all_wood(ctx)

    R.drive(V.params(2), seed=6, policy=probe)
    for ph in ("TR", "W1", "W3", "W4", "W5", "W6", "W7", "NB", "N1", "N2", "N3", "N4"):
        assert seen.get(ph) == {True}, ph
    assert seen.get("W2", {True}) == {True}  # seasonal W2 is skipped when nobody can log-drive
    for ph in ("SP", "PK"):
        assert seen.get(ph) == {False}, ph


def test_R076_loan_mid_visit_keeps_the_visit_open():
    """R-076: a loan may be taken mid-turn. After moving to the Bearers location and before hiring,
    TAKE_LOAN is legal; taking it changes money and loans only, the same seat is still in its
    visit and can hire."""
    s = T.start(2)
    s.apply_action(R.move(False, "bearers"))
    assert H.TAKE_LOAN in s.legal_actions()
    s.apply_action(H.TAKE_LOAN)
    assert s.current_player() == 0
    assert R.HIRE_BEARER in s.legal_actions()
    s.apply_action(R.HIRE_BEARER)
    s.apply_action(H.DONE)
    assert _money_loans(s) == (8, 1)


def test_R076_a_loan_taken_to_enter_a_location_counts():
    """R-076 + R-040: P0 spends all $5 on bearers, then at its next turn the Woodcutters location
    is enterable only through a loan: MOVE_TO is legal (the loan counts), the hire is not until
    TAKE_LOAN is played, after which it is."""
    j = False
    pol = R.Script({(1, 0): [R.move(j, "bearers")] + [R.HIRE_BEARER] * 5 + [H.DONE]})

    def broke(c: R.Ctx) -> bool:
        return (
            c.round == 1
            and c.phase == "TR"
            and c.player == 0
            and c.snap is not None
            and H.seats(c.snap)[0]["money"] == 0
        )

    run = R.drive(V.params(2), seed=1, policy=pol, stop=broke)
    assert run.stopped
    s = run.state
    to_wc = R.move(j, "woodcutters")
    assert to_wc in s.legal_actions()
    s.apply_action(to_wc)
    assert R.HIRE_WOODCUTTER not in s.legal_actions()
    assert H.TAKE_LOAN in s.legal_actions()
    s.apply_action(H.TAKE_LOAN)
    assert R.HIRE_WOODCUTTER in s.legal_actions()


def test_R076_loans_are_voluntary_outside_a_shortfall():
    """R-076: a loan is voluntary except where R-073 forces it: a default game with no payments due
    leaves every seat with no loans and its starting money through fall (read at the end of fall
    year 1)."""
    run = R.drive(
        V.params(2),
        seed=5,
        policy=R.cut_all_wood,
        stop=lambda c: (
            c.round == 3 and c.phase == "W7" and c.player == c.snap["clearing_order"][-1]
        ),
    )
    assert run.stopped
    for seat in H.seats(R.try_snapshot(run.state)):
        assert (seat["money"], seat["loans"]) == (5, 0)


def test_R077_loans_are_not_repaid_during_the_game():
    """R-077: no interest and no early repayment: a seat that took one loan in round 1 and spent
    nothing still has 1 loan and $9 at the end of fall year 1 (the repayment is deducted only at
    the end of scoring)."""
    steps = V.fall_steps(False, loans=1)
    run = R.drive(
        V.params(2),
        seed=V.SEED,
        policy=V.policy(steps),
        stop=lambda c: (
            c.round == 3 and c.phase == "W7" and c.player == c.snap["clearing_order"][-1]
        ),
    )
    assert run.stopped
    seat = H.seats(R.try_snapshot(run.state))[0]
    assert (seat["money"], seat["loans"]) == (9, 1)
