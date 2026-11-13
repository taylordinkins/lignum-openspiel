"""Phase 2 unit 11: final sale, final dollars, winner and ties, returns (R-081..R-086), and the
game-end side of R-077 and R-082.

Written from docs/RULES_SPEC.md, docs/ACTIONS.md (section 5.11, FS) and docs/SCENARIOS.md only.

How the end is observed
  * Only `state.returns()` is visible at the terminal state, so final dollars are checked through
    the returns. `winter.final_dollars` is an independent reference model (year-2 winter by
    R-071..R-073, then R-081/R-082 sales, then the R-077 repayment) and `winter.winloss_returns`
    / `winter.margin_returns` re-implement R-085/R-086; each test compares the engine's returns
    with the model's, from the snapshot at the last seat's N4 turn of round 8.
  * Phase 2 reality: the year-2 winter bill (food >= 6, heating >= 6 under every card, $3 per
    missing unit) exceeds what any seat can hold, so every seat ends the winter broke, with 2 loans
    and no sellable wood left. What can still differ between seats at the final sale is wood that
    winter cannot sell: unmilled wood on the river (R-053; one raft token per seat: 2 on the path)
    and joinery pieces (R-082). Those are the fixtures. Sale/drying-area wood, task payout (R-056),
    one- or zero-loan repayments, a river with both kinds (FS choice, A6) and the +-1 margin clip
    need a scenario loader and are reported as gaps.
"""

from __future__ import annotations

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import sawmill as M
from tests.support import winter as V

PLAYERS = (2, 3, 4)
MODES = ("win_loss", "margin")


def _expected(sn, mode):
    req = V.requirement(sn, 2)
    d = [V.final_dollars(s, req)["dollars"] for s in H.seats(sn)]
    return d, (V.winloss_returns(d) if mode == "win_loss" else V.margin_returns(d))


def _raft(*seats):
    return V.raft_steps(tuple(seats))


def _play(steps, n, mode, j=False):
    sn, state, log = V.play_to_end(steps, n=n, j=j, returns=mode)
    assert state.is_terminal()
    return sn, state, log


# --------------------------------------------------------------------------- R-081


@pytest.mark.parametrize("n", PLAYERS)
def test_R081_unsellable_leftovers_are_worth_nothing_so_default_play_ties(n):
    """R-081: the woodpile, sawing area, firewood storage and unfinished tasks are worth $0 and
    food, equipment and craftwork score nothing. Default play leaves every seat broke after winter
    year 2 with only such leftovers (woodpile disks), so all seats end on the same final dollars
    and the game is a full tie: every return is 0."""
    sn, state, _ = _play(None, n, "win_loss")
    assert all(V.pm(s["woodpile"]) for s in H.seats(sn)), "precondition: wood in woodpiles"
    d, want = _expected(sn, "win_loss")
    assert want == [0.0] * n and len(set(d)) == 1
    assert list(state.returns()) == pytest.approx([0.0] * n)


@pytest.mark.parametrize("mode", MODES)
def test_R081_river_wood_of_one_kind_is_sold_automatically_at_the_unmilled_price(mode):
    """R-081 step 2: unmilled firewood on the river sells at $3 with no drying bonus, automatically
    (no decision: the game goes on to the end without an FS river choice, which exists only when
    both kinds are on the river). P0 holds 1 river firewood disk, P1 none, so P0 is exactly $3
    ahead and the returns match the model (2 players: margin +-3/50 = 0.06)."""
    sn, state, log = _play(_raft(0), 2, mode)
    assert V.pm(H.seats(sn)[0]["river"]) == {"firewood_disk": 1}
    assert not V.pm(H.seats(sn)[1]["river"])
    assert all(ph != "FS" for _, ph, _ in log)
    d, want = _expected(sn, mode)
    assert d[0] - d[1] == 3
    assert list(state.returns()) == pytest.approx(want)
    if mode == "margin":
        assert list(state.returns()) == pytest.approx([0.06, -0.06])


def test_R081_river_wood_cannot_be_sold_before_the_end():
    """R-081/R-073: river wood is not sellable in the winter shortfall: P0 (broke, river wood)
    keeps its river firewood through winter year 2, so the N4 snapshot still shows it and it only
    scores at the final sale."""
    sn, state, _ = _play(_raft(0), 2, "win_loss")
    assert V.pm(H.seats(sn)[0]["river"])["firewood_disk"] == 1
    assert list(state.returns()) == pytest.approx([1.0, -1.0])


# --------------------------------------------------------------------------- R-082


@pytest.mark.parametrize("slot", (0, 1))
def test_R082_joinery_piece_final_dollars_follow_the_model(slot):
    """R-082: a joinery piece sells for the milled price + $3 only if its slot has a joiner (1
    joiner: slot 0 only). P0 places a firewood log in `slot`; the margin returns equal the
    reference model's (covered: $1 + $3 = $4 extra; uncovered: $0)."""
    st = M.chain_steps(True, r2_sell=2, joiner=True, joinery_q=slot)
    sn, state, _ = _play(st, 2, "margin", j=True)
    p0 = H.seats(sn)[0]
    assert p0["joiners"] == 1 and p0["joinery"][slot] == "firewood"
    d, want = _expected(sn, "margin")
    covered = slot == 0
    assert (d[0] - d[1] == 4) if covered else (d[0] - d[1] == 0)
    assert list(state.returns()) == pytest.approx(want)


# --------------------------------------------------------------------------- R-083


def test_R083_final_dollars_may_be_negative_and_a_negative_seat_can_still_win():
    """R-083: final dollars = money after the final sale - loan repayment ($16 with two loans), with
    no floor. Both seats end the game broke with 2 loans (-16 and -13 with the river sale): the
    seat on -13 wins with return +1 although both are negative."""
    sn, state, _ = _play(_raft(0), 2, "win_loss")
    req = V.requirement(sn, 2)
    d = [V.final_dollars(s, req) for s in H.seats(sn)]
    assert [x["loans"] for x in d] == [2, 2]
    assert [x["dollars"] for x in d] == [-13, -16]
    assert list(state.returns()) == pytest.approx([1.0, -1.0])


# --------------------------------------------------------------------------- R-084 / R-085


@pytest.mark.parametrize("n", PLAYERS)
def test_R085_sole_winner_gets_plus_one_and_the_others_share_minus_one(n):
    """R-085/R-084: P0 alone has the river sale, so it is the sole winner: +1; every other seat
    -1/(n-1). Sum of returns is 0."""
    sn, state, _ = _play(_raft(0), n, "win_loss")
    d, want = _expected(sn, "win_loss")
    assert d[0] > max(d[1:])
    assert want == pytest.approx([1.0] + [-1 / (n - 1)] * (n - 1))
    got = list(state.returns())
    assert got == pytest.approx(want)
    assert sum(got) == pytest.approx(0.0)


@pytest.mark.parametrize("n", (3, 4))
def test_R085_two_way_tie_shares_the_win(n):
    """R-085/R-084 (no tiebreak): P0 and P1 each sell one river firewood ($3), so they tie for the
    top; each winner gets (n-2)/(2(n-1)) and every other seat -1/(n-1): 3 players +0.25/-0.5,
    4 players +1/3/-1/3."""
    sn, state, _ = _play(_raft(0, 1), n, "win_loss")
    d, _ = _expected(sn, "win_loss")
    assert d[0] == d[1] > max(d[2:])
    want = [(n - 2) / (2 * (n - 1))] * 2 + [-1 / (n - 1)] * (n - 2)
    got = list(state.returns())
    assert got == pytest.approx(want)
    if n == 3:
        assert got == pytest.approx([0.25, 0.25, -0.5])
    assert sum(got) == pytest.approx(0.0)


def test_R085_all_seats_tied_gets_zero_for_everyone():
    """R-085 (k = n): 2 players both selling one river firewood end on the same final dollars: both
    win and both return 0."""
    sn, state, _ = _play(_raft(0, 1), 2, "win_loss")
    d, _ = _expected(sn, "win_loss")
    assert d[0] == d[1]
    assert list(state.returns()) == pytest.approx([0.0, 0.0])


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", PLAYERS)
def test_R085_returns_are_zero_before_the_game_ends(n, mode):
    """R-085/R-086: returns are 0 before the game ends: at the start and at the last seat's N4
    turn of round 8, in both modes."""
    s = H.load_game(players=n, joinery=False, returns=mode).new_initial_state()
    assert list(s.returns()) == [0.0] * n
    run = R.drive(
        {**V.params(n), "returns": mode},
        seed=V.SEED,
        policy=V.policy(None),
        stop=lambda c: c.round == 8 and c.phase == "N4",
    )
    assert run.stopped and not run.state.is_terminal()
    assert list(run.state.returns()) == [0.0] * n


# --------------------------------------------------------------------------- R-086


@pytest.mark.parametrize("n", PLAYERS)
def test_R086_margin_returns_are_difference_to_the_mean_of_the_others_over_50(n):
    """R-086: return_i = clip((d_i - mean of the others) / 50, -1, 1). P0 is $3 ahead of everyone
    (river sale): P0 gets 3/50 = 0.06 and each other seat -(3/(n-1))/50. 2 players are exactly
    zero-sum."""
    sn, state, _ = _play(_raft(0), n, "margin")
    d, want = _expected(sn, "margin")
    assert d[0] - d[1] == 3 and len(set(d[1:])) == 1
    assert want[0] == pytest.approx(0.06)
    assert want[1] == pytest.approx(-0.06 / (n - 1))
    got = list(state.returns())
    assert got == pytest.approx(want)
    if n == 2:
        assert sum(got) == pytest.approx(0.0)


@pytest.mark.parametrize("n", PLAYERS)
def test_R086_margin_with_all_seats_equal_is_zero(n):
    """R-086: equal final dollars give margin 0 for everyone."""
    _, state, _ = _play(None, n, "margin")
    assert list(state.returns()) == pytest.approx([0.0] * n)


@pytest.mark.parametrize(("mode", "utility"), (("win_loss", "ZERO_SUM"), ("margin", "GENERAL_SUM")))
def test_R086_game_utility_type_follows_returns_mode(mode, utility):
    """R-086: the game declares ZERO_SUM for win_loss and GENERAL_SUM for margin."""
    g = H.load_game(players=2, returns=mode)
    assert g.get_type().utility.name == utility


# --------------------------------------------------------------------------- FS river choice


def _both_kinds(choice: int):
    seed, _ = V.softwood_pick_seed()
    st = V.both_kinds_steps(0)
    sn, state, log = V.play_to_end(st, n=2, returns="margin", seed=seed, fs={0: choice})
    assert V.pm(H.seats(sn)[0]["river"]) == {"firewood_disk": 1, "softwood_disk": 1}
    return sn, state, log


@pytest.mark.parametrize("choice", (0, 1))
def test_R081_only_the_chosen_river_kind_is_sold(choice):
    """R-081 step 2 (user answer 2026-11-04): a seat with both firewood and softwood on its river
    sells all wood of ONE kind, its choice. P0 has 1 firewood ($3) and 1 softwood ($4) on the river
    and plays RIVER_SALE(choice): it is exactly $3 (firewood) or $4 (softwood) ahead of P1, never
    $7, so the 2-player margin return is 0.06 or 0.08."""
    sn, state, log = _both_kinds(choice)
    d, want = _expected_choice(sn, {0: choice})
    assert d[0] - d[1] == (3, 4)[choice]
    assert list(state.returns()) == pytest.approx(want)
    assert list(state.returns()) == pytest.approx([(0.06, 0.08)[choice], -(0.06, 0.08)[choice]])
    fs = [e for e in log if e[1] == "FS"]
    assert fs == [(8, "FS", 0)]


def _expected_choice(sn, choices):
    req = V.requirement(sn, 2)
    d = [
        V.final_dollars(s, req, river_choice=choices.get(i))["dollars"]
        for i, s in enumerate(H.seats(sn))
    ]
    return d, V.margin_returns(d)


def test_R081_fs_offers_both_kinds_and_never_done():
    """R-081/ACTIONS 5.11: at the FS node the seat with both kinds is offered RIVER_SALE(0) and
    RIVER_SALE(1) and never DONE (the final sale is automatic, user answer 2026-11-04). A seat
    with a single river kind (every other fixture here) gets no FS node at all. Several seats with
    both kinds (FS choices in year-2 fall clearing order) cannot be built: only 2 raft tokens
    exist per fill, so at most one seat can hold two river pieces."""
    seed, _ = V.softwood_pick_seed()
    run = R.drive(
        {**V.params(2), "returns": "margin"},
        seed=seed,
        policy=V.policy(V.both_kinds_steps(0)),
        stop=lambda c: c.phase == "FS",
    )
    assert run.stopped and run.state.current_player() == 0
    legal = run.state.legal_actions()
    assert V.RIVER_SALE0 in legal and V.RIVER_SALE0 + 1 in legal
    assert H.DONE not in legal
