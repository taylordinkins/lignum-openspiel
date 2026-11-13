"""Phase 2 unit 6: the supply path and foreman movement (R-021..R-025, R-040, R-044).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py, tests/support/rounds.py and tests/support/travel.py (public API only).

Scope notes
  * Planned work, Buildings and the Market are Phase-4 content (ACTIONS section 7); their
    locations are never asserted legal or illegal here (travel.PHASE4_KINDS).
  * `travel.oracle_moves` restates R-040 item 4 (activation) from the spec; the random-play
    test compares it with `legal_actions()` at every travel node.
  * Seats are P0.. everywhere; location numbers are the printed numbers of the chosen side.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

PLAYERS = (2, 3, 4)
BOOLS = (True, False)


def _foremen(sn: dict[str, Any]) -> list[Any]:
    return [s["foreman"] for s in H.seats(sn)]


# --------------------------------------------------------------------------- R-021 / R-022


@pytest.mark.parametrize("n", PLAYERS)
def test_R021_base_side_has_20_locations_and_never_21_or_22(n):
    """R-021: the base side has locations 1..20 plus the clearing; MOVE_TO(21) and MOVE_TO(22)
    are never legal there (ACTIONS section 3)."""
    s = T.start(n, False)
    locs = T.move_locs(s)
    assert set(locs) <= set(range(1, 21)) | {23}
    assert 21 not in locs and 22 not in locs
    assert sorted(T.spots(T.snap(s))) == [1, 2, 3, 5, 7, 9, 11, 12, 14, 15, 17, 18, 20]


@pytest.mark.parametrize("n", PLAYERS)
def test_R021_base_side_worker_locations_by_number(n):
    """R-021: Bearers 4, Fodder 6, Woodcutters 10, Tasks 13, Sawyers 16; 13 is a task location and
    14 a token spot on the base side. Entering each is legal at the start of travel (all
    affordable, none empty)."""
    s = T.start(n, False)
    legal = set(T.move_locs(s))
    assert {4, 6, 10, 13, 16} <= legal
    sn = T.snap(s)
    assert 14 in T.spots(sn) and 13 not in T.spots(sn)  # 14 is a token spot, 13 is Tasks


@pytest.mark.parametrize("n", PLAYERS)
def test_R022_joinery_side_has_22_locations_with_buildings_and_joiner(n):
    """R-022: the joinery side has locations 1..22; Bearers 4, Fodder 6, Woodcutters 10,
    Tasks 14, Joiner 16, Sawyers 18; token spots are 1 2 3 5 7 9 11 13 15 17 19 20 22."""
    s = T.start(n, True)
    sn = T.snap(s)
    assert sorted(T.spots(sn)) == [1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22]
    legal = set(T.move_locs(s))
    assert set(legal) <= set(range(1, 23)) | {23}
    assert {4, 6, 10, 14, 16, 18} <= legal
    assert T.kind_of(True, 16) == "joiner"


def test_R022_task_location_differs_by_side():
    """R-021/R-022: location 14 is the Tasks location only on the joinery side, location 13 only
    on the base side. Entering the Tasks location offers TAKE_TASK actions, entering a token
    spot offers none."""
    for joinery, tasks_loc, spot_loc in ((False, 13, 14), (True, 14, 13)):
        s = T.start(3, joinery)
        sn = T.snap(s)
        assert spot_loc in T.spots(sn) and tasks_loc not in T.spots(sn)
        T.play(s, H.MOVE_TO(tasks_loc))
        assert any(R.TAKE_TASK0 <= a <= R.TAKE_TASK_END for a in s.legal_actions())


# --------------------------------------------------------------------------- R-023


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R023_thirteen_spots_each_holding_one_token_at_the_start(n, joinery):
    """R-023: there are exactly 13 token spots; at the start every spot holds exactly one token."""
    sn = T.snap(T.start(n, joinery))
    tok = T.spots(sn)
    assert len(tok) == 13
    assert all(t is not None for t in tok.values())


@pytest.mark.parametrize("joinery", BOOLS)
def test_R023_spot_capacity_is_one_and_taken_spot_stays_empty(joinery):
    """R-023/R-042: a spot is taken by the foreman that enters (capacity 1); afterwards it is
    empty and no other seat can enter it."""
    s = T.start(3, joinery)
    loc = next(iter(T.spots(T.snap(s))))
    T.play(s, H.MOVE_TO(loc))
    assert T.spots(T.snap(s))[loc] is None
    assert s.current_player() == 1
    assert loc not in T.move_locs(s)


# --------------------------------------------------------------------------- R-024 / R-044


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R044_clearing_enterable_from_zero_with_no_acquisition_and_no_cost(n, joinery):
    """R-044/R-040(5): from location 0 MOVE_TO(clearing) is always legal; it costs nothing, takes
    nothing, and the foreman is on slot A."""
    s = T.start(n, joinery)
    assert 23 in T.move_locs(s)
    before = T.snap(s)
    T.goto_clearing(s)
    after = T.snap(s)
    assert T.seat_of(after, 0)["money"] == T.seat_of(before, 0)["money"] == 5
    assert T.seat_of(after, 0)["hired"] == T.seat_of(before, 0)["hired"]
    assert after["path"] == before["path"]
    assert T.seat_of(after, 0)["foreman"] == "A"
    assert after["clearing_order"] == [0]


@pytest.mark.parametrize("joinery", BOOLS)
def test_R044_clearing_enterable_when_broke_and_nothing_else_is(joinery):
    """R-044/R-040(5): a seat with $0 and 2 loans (so it can buy nothing) still has the clearing,
    and it is on location 10: it may move on or enter the clearing."""
    s = T.broke_p0(joinery)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 0 and me["loans"] == 2 and me["foreman"] == 10
    assert 23 in T.move_locs(s)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R044_slots_in_arrival_order_and_turn_skips_the_clearing(joinery):
    """R-044/R-024/R-040: arrival order sets the slot (A first); a foreman in the clearing is
    skipped by the cycle. Four players: P0 and P1 hire a bearer each, P2 enters first (A),
    P3 second (B), P0 third (C), P1 fourth (D)."""
    j = joinery
    s = T.start(4, j)
    T.hire(s, R.loc(j, "bearers"), R.HIRE_BEARER, 1)  # P0
    assert s.current_player() == 1
    T.hire(s, R.loc(j, "bearers"), R.HIRE_BEARER, 1)  # P1
    assert s.current_player() == 2
    T.goto_clearing(s)  # P2 -> A
    sn = T.snap(s)
    assert sn["phase"] == "TR" and s.current_player() == 3
    assert T.seat_of(sn, 2)["foreman"] == "A" and sn["clearing_order"] == [2]
    T.goto_clearing(s)  # P3 -> B
    assert s.current_player() == 0  # P2 and P3 skipped from now on
    T.goto_clearing(s)  # P0 -> C
    assert s.current_player() == 1
    assert H.phase_of(s) == "TR"
    T.goto_clearing(s)  # P1 -> D: travel over
    sn = T.snap(s)
    assert sn["phase"] == "W1"
    assert sn["clearing_order"] == [2, 3, 0, 1]
    assert _foremen(sn) == ["C", "D", "A", "B"]
    assert s.current_player() == 2  # first in clearing order has the first wood-work turn


@pytest.mark.parametrize("n", (2, 3))
def test_R044_fewer_than_four_players_only_n_slots(n):
    """R-044/R-024: with n < 4 players only the first n slots exist; travel ends when the last
    foreman enters, with letters A.. in arrival order."""
    s = T.start(n, False)
    for _ in range(n):
        assert H.phase_of(s) == "TR"
        T.goto_clearing(s)
    sn = T.snap(s)
    assert sn["phase"] == "W1"
    assert sorted(_foremen(sn)) == list("ABCD"[:n])
    assert sn["clearing_order"] == list(range(n))


def test_R044_travel_does_not_end_until_everybody_is_in_the_clearing():
    """R-044/R-040: with 2 of 3 foremen in the clearing the phase is still TR and the third
    foreman, who must move, moves again and again until it enters the clearing."""
    s = T.start(3, False)
    T.goto_clearing(s)
    T.goto_clearing(s)
    assert H.phase_of(s) == "TR" and s.current_player() == 2
    T.hire(s, R.loc(False, "bearers"), R.HIRE_BEARER, 1)
    assert H.phase_of(s) == "TR" and s.current_player() == 2  # same seat moves again
    assert min(T.move_locs(s)) > 4
    T.goto_clearing(s)
    assert H.phase_of(s) == "W1"


def test_R044_clearing_order_is_the_wood_work_turn_order():
    """R-044/R-045 example: wood work runs in clearing order. Three players: P2 enters first,
    P0 second, P1 third; W1 starts with P2."""
    s = T.start(3, False)
    T.hire(s, R.loc(False, "bearers"), R.HIRE_BEARER, 1)  # P0
    T.hire(s, R.loc(False, "bearers"), R.HIRE_BEARER, 1)  # P1
    T.goto_clearing(s)  # P2 first (A)
    T.goto_clearing(s)  # P0 (B)
    T.goto_clearing(s)  # P1 (C)
    sn = T.snap(s)
    assert sn["phase"] == "W1" and sn["clearing_order"] == [2, 0, 1]
    assert s.current_player() == 2


# --------------------------------------------------------------------------- R-040 order


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_round_1_cycle_is_p0_p1_p2_and_repeats(joinery):
    """R-040: round 1 turn order is P0, P1, P2, ... and the foremen cycle through it; after a
    move the turn passes to the next foreman."""
    j = joinery
    s = T.start(3, j)
    seen = []
    for loc in (R.loc(j, "bearers"), R.loc(j, "bearers"), R.loc(j, "bearers")):
        seen.append(s.current_player())
        T.hire(s, loc, R.HIRE_BEARER, 1)
    seen.append(s.current_player())
    assert seen == [0, 1, 2, 0]


@pytest.mark.parametrize("n", (3, 4))
def test_R040_round_2_cycle_follows_the_starting_player_track(n):
    """R-040: travel order is the starting-player track (snapshot `turn_order`, position 1 first)
    in every seasonal round; clearing seats are skipped."""
    pol = R.Script({})
    run = R.drive(T.params(n), seed=3, policy=pol, stop=lambda c: c.round == 2 and c.phase == "TR")
    assert run.stopped
    s = run.state
    order = T.snap(s)["turn_order"]
    assert sorted(order) == list(range(n))
    assert s.current_player() == order[0]
    got = []
    for _ in range(n):
        got.append(s.current_player())
        T.goto_clearing(s)
        if H.phase_of(s) != "TR":
            break
    assert got == order


def test_R040_a_foreman_makes_exactly_one_move_per_turn():
    """R-040: after MOVE_TO the foreman cannot move again in the same turn: no MOVE_TO (not even
    the clearing) is legal in the middle of a visit."""
    s = T.start(3, False)
    T.play(s, H.MOVE_TO(4), R.HIRE_BEARER)
    assert s.current_player() == 0
    assert not any(8 <= a <= 30 for a in s.legal_actions())
    assert not T.at_move_node(s)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_forward_only_never_back_never_stay(joinery):
    """R-040(1): from location 10 only higher locations (or the clearing) are legal: not 10 itself
    and nothing below."""
    j = joinery
    s = T.start(3, j)
    T.hire(s, R.loc(j, "woodcutters"), R.HIRE_WOODCUTTER, 1)  # P0 now on 10
    T.goto_clearing(s)
    T.goto_clearing(s)
    assert s.current_player() == 0
    locs = T.move_locs(s)
    assert min(locs) > R.loc(j, "woodcutters")
    assert 23 in locs


def test_R040_a_move_must_be_made_there_is_no_pass():
    """R-040(1): a foreman never passes: at a move node DONE is not legal and a destination
    must be chosen."""
    s = T.start(2, False)
    assert H.DONE not in s.legal_actions()
    assert any(8 <= a <= 30 for a in s.legal_actions())


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_skipping_locations_is_allowed(joinery):
    """R-040(2): from 0 any location ahead may be chosen: the far end is legal at the start and
    the foreman lands there."""
    j = joinery
    s = T.start(3, j)
    far = R.loc(j, "sawyers")
    assert far in T.move_locs(s)
    T.visit(s, far, R.HIRE_SAWYER)
    assert T.seat_of(T.snap(s), 0)["foreman"] == far


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_moving_on_frees_the_old_location(joinery):
    """R-040(3): a foreman occupies only the location it stands on. Four players: all four fit on
    Bearers (capacity 4) at once; when P0 moves on to Woodcutters its dump shows it there."""
    j = joinery
    b = R.loc(j, "bearers")
    s = T.start(4, j)
    for _ in range(4):
        assert b in T.move_locs(s)
        T.hire(s, b, R.HIRE_BEARER, 1)
    sn = T.snap(s)
    assert sn["phase"] == "TR" and s.current_player() == 0
    assert _foremen(sn) == [b, b, b, b]
    assert T.seat_of(sn, 0)["hired"]["bearers"] == 1
    assert sn["path"]["bearers"] == R.quantities(4)["bearers_on_path"] - 4
    T.hire(s, R.loc(j, "woodcutters"), R.HIRE_WOODCUTTER, 1)
    assert _foremen(T.snap(s))[0] == R.loc(j, "woodcutters")


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_fodder_location_second_foreman_fits_third_cannot(joinery):
    """R-040(3)/R-041: Fodder has capacity 2 and, at 3 players, 2 fodder: P0 and P1 both buy
    there, P2 cannot enter (no fodder left, and no room). When P0 stands on it the location has
    one foreman."""
    j = joinery
    f = R.loc(j, "fodder")
    s = T.start(3, j)
    T.visit(s, f, R.BUY_FODDER)
    assert f in T.move_locs(s)
    T.visit(s, f, R.BUY_FODDER)
    assert s.current_player() == 2
    assert f not in T.move_locs(s)


def test_R040_empty_visit_is_not_allowed_done_needs_an_acquisition():
    """R-040(4): the move includes at least one acquisition: after entering Woodcutters without
    hiring, DONE is not legal; after one hire it is."""
    s = T.start(3, False)
    T.play(s, H.MOVE_TO(10))
    assert H.DONE not in s.legal_actions()
    assert R.HIRE_WOODCUTTER in s.legal_actions()
    T.play(s, R.HIRE_WOODCUTTER)
    assert H.DONE in s.legal_actions()


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_taken_token_spot_cannot_be_entered(joinery):
    """R-040(4)/R-042 example: a spot whose token was taken cannot be entered; spots still holding
    a token can."""
    s = T.start(3, joinery)
    sn = T.snap(s)
    taken, other = T.spot_with(sn, "wagon")[0], T.spot_with(sn, "raft")[0]
    T.play(s, H.MOVE_TO(taken))
    assert s.current_player() == 1
    legal = T.move_locs(s)
    assert taken not in legal and other in legal


def test_R040_worker_location_with_none_left_cannot_be_entered():
    """R-040(4)/R-041: after P0 hires all 6 bearers (2 players, one loan) nobody can enter
    Bearers."""
    s = T.start(2, False)
    T.play(s, H.TAKE_LOAN)
    T.hire(s, 4, R.HIRE_BEARER, 6)
    assert s.current_player() == 1
    assert 4 not in T.move_locs(s)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_x_marker_spots_cannot_be_entered(joinery):
    """R-040(4)/R-017: with 2 players the 2 X-marker spots can never be entered, by anyone."""
    s = T.start(2, joinery, seed=2)
    xs = T.spot_with(T.snap(s), "x")
    assert len(xs) == 2
    assert not set(xs) & set(T.move_locs(s))
    T.hire(s, R.loc(joinery, "bearers"), R.HIRE_BEARER, 1)
    assert not set(xs) & set(T.move_locs(s))


# --------------------------------------------------------------------------- R-040 activation


def test_R040_activation_counts_a_loan_for_a_seat_with_no_money():
    """R-040(4)/R-076: a seat with $0 and no loan taken may still enter Bearers, Woodcutters,
    Fodder, Tasks: the loan it could take counts. Inside the location only TAKE_LOAN is legal
    (acquisitions are not legal before the loan is taken, ACTIONS 1.8)."""
    s = T.start(2, False)
    T.hire(s, 4, R.HIRE_BEARER, 5)  # P0: $5 -> $0, no loan
    T.goto_clearing(s)  # P1 steps out of the way
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 0 and me["loans"] == 0
    locs = T.move_locs(s)
    assert {10, 13} <= set(locs)
    T.play(s, H.MOVE_TO(13))
    assert sorted(s.legal_actions()) == [H.TAKE_LOAN]


def test_R040_activation_without_money_or_loans_blocks_paid_locations_only():
    """R-040(4): P0 on location 10 with $0 and both loans used cannot enter Tasks (13, $1) but can
    enter Sawyers (the free sawyer), a token spot and the clearing."""
    s = T.broke_p0(False)
    locs = T.move_locs(s)
    assert 13 not in locs
    assert 16 in locs
    assert 23 in locs
    sn = T.snap(s)
    for spot in T.spot_with(sn, *["wagon", "raft", "saw", "sledge", "dollar", "food"]):
        if spot > 10:
            assert spot in locs


def test_R040_activation_joinery_side_free_joiner_and_sawyer_with_no_money():
    """R-040(4)/R-078: the same broke seat on the joinery side cannot enter Tasks (14) but can
    enter the free Joiner (16) and Sawyers (18)."""
    s = T.broke_p0(True)
    locs = T.move_locs(s)
    assert 14 not in locs
    assert {16, 18, 23} <= set(locs)


@pytest.mark.parametrize("joinery", BOOLS)
def test_R040_saw_spot_closed_to_a_seat_with_four_saws(joinery):
    """R-040(4)/R-042 example: a spot holding a saw cannot be entered by a seat that owns 4 saws
    (but other spots can). P0 collects the two saws of rounds 1 and 2 (3 players: 2 per fill)."""

    def pol(ctx: R.Ctx) -> int | None:
        if ctx.phase != "TR" or ctx.player != 0 or ctx.snap is None:
            return None
        me = T.seat_of(ctx.snap, 0)
        if me["equipment"]["saw"] >= 4:
            return None
        saws = [s for s in T.spot_with(ctx.snap, "saw") if s in T.move_locs(ctx.state)]
        return H.MOVE_TO(saws[0]) if saws else None

    run = R.drive(
        T.params(3, joinery),
        seed=2,
        policy=pol,
        stop=lambda c: c.round == 3 and c.phase == "TR" and c.player == 0,
    )
    assert run.stopped
    sn = T.snap(run.state)
    assert T.seat_of(sn, 0)["equipment"]["saw"] == 4
    saw_spots = T.spot_with(sn, "saw")
    assert saw_spots
    legal = T.move_locs(run.state)
    assert not set(saw_spots) & set(legal)
    others = [loc for loc in T.spot_with(sn, "wagon", "raft", "sledge") if loc > 0]
    assert set(others) <= set(legal)


# --------------------------------------------------------------------------- R-040 random play


def _random_travel_policy(rng: random.Random, joinery: bool, log: list[str]):
    pos: dict[tuple[int, int], int] = {}

    def pol(ctx: R.Ctx) -> int | None:
        if ctx.phase != "TR":
            return None
        legal = ctx.legal
        if ctx.snap is not None:
            sn = ctx.snap
            got = {
                a - 7
                for a in legal
                if 8 <= a <= 30 and T.kind_of(joinery, a - 7) not in T.PHASE4_KINDS
            }
            if got != T.oracle_moves(sn, joinery):
                want = sorted(T.oracle_moves(sn, joinery))
                log.append(f"r{ctx.round} P{ctx.player}: legal {sorted(got)} != oracle {want}")
            for i, s in enumerate(H.seats(sn)):
                if s["money"] < 0 or s["loans"] > 2:
                    log.append(f"seat {i} money/loans {s['money']}/{s['loans']}")
            counts: dict[Any, int] = {}
            for s in H.seats(sn):
                if isinstance(s["foreman"], int) and s["foreman"] > 0:
                    counts[s["foreman"]] = counts.get(s["foreman"], 0) + 1
            for loc, c in counts.items():
                if c > T.CAPACITY[T.kind_of(joinery, loc)]:
                    log.append(f"capacity exceeded at {loc}: {c}")
            q = R.quantities(len(H.seats(sn)))
            seats = H.seats(sn)
            if (
                sn["path"]["bearers"] + sum(s["hired"]["bearers"] for s in seats)
                != q["bearers_on_path"]
            ):
                log.append("bearer conservation")
            if (
                sn["path"]["woodcutters"] + sum(s["hired"]["woodcutters"] for s in seats)
                != q["woodcutters_on_path"]
            ):
                log.append("woodcutter conservation")
            if (
                sn["path"]["sawyers_free"]
                + sn["path"]["sawyers_paid"]
                + sum(s["hired"]["sawyers"] for s in seats)
                != q["sawyers_price_0"] + q["sawyers_price_1"]
            ):
                log.append("sawyer conservation")
            key = (ctx.round, ctx.player)
            cur = H.seats(sn)[ctx.player]["foreman"]
            if key in pos and cur < pos[key]:
                log.append(f"foreman moved back {key}: {pos[key]} -> {cur}")
            pos[key] = cur
        moves = [
            a for a in legal if 8 <= a <= 30 and T.kind_of(joinery, a - 7) not in T.PHASE4_KINDS
        ]
        if moves:
            if H.TAKE_LOAN in legal and rng.random() < 0.1:
                return H.TAKE_LOAN
            return rng.choice(moves)
        return rng.choice(legal)

    return pol


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", (2, 3, 4))  # 2 players: X-marker spots
@pytest.mark.parametrize("seed", range(4))
def test_R040_random_travel_matches_the_activation_oracle_and_invariants(n, joinery, seed):
    """R-040/R-041/R-042/R-044: playing random legal travel moves for rounds 1-3, at every travel
    node the set of legal destinations equals the spec's activation oracle (for the non-Phase-4
    locations), money is never negative, capacities hold, hired workers plus path workers are
    conserved, and a foreman only moves forward. A foreman always has a legal move."""
    log: list[str] = []
    rng = random.Random(seed * 31 + n)
    pol = _random_travel_policy(rng, joinery, log)
    run = R.drive(T.params(n, joinery), seed=seed, policy=pol, stop=lambda c: c.round == 4)
    assert run.stopped or run.state.is_terminal()
    assert not log, log[:5]
    assert sum(1 for r, ph, _ in run.log if ph == "TR" and r <= 3) >= 3 * n


# --------------------------------------------------------------------------- R-025


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R025_path_starts_with_price_0_sawyers_and_one_at_one_dollar(n, joinery):
    """R-025/R-013: the Sawyers location holds the R-013 number of free sawyers plus one at $1."""
    p = T.snap(T.start(n, joinery))["path"]
    q = R.quantities(n)
    assert p["sawyers_free"] == q["sawyers_price_0"]
    assert p["sawyers_paid"] == q["sawyers_price_1"] == 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R025_first_sawyer_is_free_second_costs_a_dollar(joinery):
    """R-025/R-041: the first sawyer a seat takes is free, a second in the same visit costs
    exactly $1 and is the $1 sawyer; afterwards no further sawyer is legal."""
    j = joinery
    s = T.start(3, j)
    loc = R.loc(j, "sawyers")
    T.play(s, H.MOVE_TO(loc), R.HIRE_SAWYER)
    assert s.current_player() == 0 and R.HIRE_SAWYER in s.legal_actions()
    T.play(s, R.HIRE_SAWYER)
    assert R.HIRE_SAWYER not in s.legal_actions()
    T.end_visit(s)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["hired"]["sawyers"] == 2
    assert me["money"] == 4
    assert sn["path"]["sawyers_free"] == R.quantities(3)["sawyers_price_0"] - 1
    assert sn["path"]["sawyers_paid"] == 0


@pytest.mark.parametrize("joinery", BOOLS)
def test_R025_first_sawyer_free_leaves_money_untouched(joinery):
    """R-025/R-041: with one hire only, the seat keeps its $5 and holds one sawyer; the $1
    sawyer remains on the path."""
    j = joinery
    s = T.start(3, j)
    T.visit(s, R.loc(j, "sawyers"), R.HIRE_SAWYER)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 5 and me["hired"]["sawyers"] == 1
    assert sn["path"]["sawyers_paid"] == 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R025_paid_sawyer_is_taken_once_per_round_by_any_seat(joinery):
    """R-025/R-041 example: once P0 hired the $1 sawyer, P1 arriving later takes the free one only:
    one HIRE_SAWYER is legal at its visit, a second is not, despite its $5."""
    j = joinery
    loc = R.loc(j, "sawyers")
    s = T.start(3, j)
    T.visit(s, loc, R.HIRE_SAWYER, R.HIRE_SAWYER)  # P0: free + $1
    T.play(s, H.MOVE_TO(loc))  # P1
    assert R.HIRE_SAWYER in s.legal_actions()
    T.play(s, R.HIRE_SAWYER)
    assert R.HIRE_SAWYER not in s.legal_actions()
    T.end_visit(s)
    sn = T.snap(s)
    assert T.seat_of(sn, 1)["money"] == 5 and T.seat_of(sn, 1)["hired"]["sawyers"] == 1
    assert sn["path"]["sawyers_paid"] == 0


@pytest.mark.parametrize("joinery", BOOLS)
def test_R025_seat_without_money_gets_the_free_sawyer_but_not_the_paid_one(joinery):
    """R-025/R-041/R-040: at Sawyers with $0 and both loans used the move is legal (free
    sawyer); after the free sawyer the $1 one is not legal."""
    j = joinery
    s = T.broke_p0(j)
    sn = T.snap(s)
    assert T.seat_of(sn, 0)["money"] == 0
    loc = R.loc(j, "sawyers")
    assert loc in T.move_locs(s)
    T.play(s, H.MOVE_TO(loc), R.HIRE_SAWYER)
    assert R.HIRE_SAWYER not in s.legal_actions()


def test_R025_paid_sawyer_costs_exactly_one_dollar():
    """R-025/R-076: P0 (one loan, 6 bearers hired, $3 left) takes the free sawyer, then pays $1
    for the second: money $2, loans 1."""
    s = T.start(2, False)
    T.play(s, H.TAKE_LOAN)  # $9, loan 1
    T.hire(s, 4, R.HIRE_BEARER, 6)  # $3
    T.goto_clearing(s)  # P1
    assert s.current_player() == 0
    T.play(s, H.MOVE_TO(16), R.HIRE_SAWYER)
    assert R.HIRE_SAWYER in s.legal_actions()  # $3 still pays $1
    T.play(s, R.HIRE_SAWYER)
    T.end_visit(s)
    sn = T.snap(s)
    me = T.seat_of(sn, 0)
    assert me["money"] == 2 and me["hired"]["sawyers"] == 2 and me["loans"] == 1


@pytest.mark.parametrize("joinery", BOOLS)
def test_R025_sawyers_visit_ends_only_on_explicit_done(joinery):
    """R-025/ACTIONS 1.4: after the free and the $1 sawyer the same seat is still to act and
    DONE is legal; multi-unit locations end only on an explicit DONE."""
    j = joinery
    s = T.start(3, j)
    T.play(s, H.MOVE_TO(R.loc(j, "sawyers")), R.HIRE_SAWYER, R.HIRE_SAWYER)
    assert s.current_player() == 0
    assert H.DONE in s.legal_actions()


# Buildings placeholder test superseded by tests/rules/test_buildings_acquisition.py (R-106).
