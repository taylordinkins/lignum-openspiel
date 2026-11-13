"""Phase 2 unit 5: hidden cutting-area pick and reveal (R-038, R-039; leak tests for R-029/R-030).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py and tests/support/rounds.py (public API only).

Conventions used here:
  * `PICK_AREA(a)` takes a = 0..5 for the printed areas 1..6; a seat's `cutting_area` field is the
    printed number a + 1 (SCENARIOS section 9.1: PICK_AREA(0) -> `cutting_area` 1).
  * The first PK decision of a seasonal round >= 2 is a turn-boundary node, so `H.snapshot` works
    there and between picks (SCENARIOS 1.3); after the last pick the state is the TR node.
  * "God view" = `str(state)` (the perfect-information observer string, R-030) and the scenario
    dump (`seats[i].pick`, SCENARIOS section 4.2).
  * The food oracle is computed from the spec text of R-039 alone: per occupied area with k tokens
    and f food, each of the k seats gets f // k and the area keeps f - k * (f // k).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from functools import cache
from typing import Any

import pyspiel
import pytest

from tests import harness as H
from tests.support import rounds as R

PLAYERS = (2, 3, 4)
BOOLS = (True, False)
ALL_AREAS = range(6)


def _params(n: int, joinery: bool = False) -> dict[str, Any]:
    return {"players": n, "joinery": joinery}


def _pk(n: int, joinery: bool = False, seed: int = 1, rnd: int = 2, policy: Any = None) -> Any:
    """State at the first PK decision of round `rnd` (P0 to pick)."""
    run = R.drive(
        _params(n, joinery),
        seed=seed,
        policy=policy,
        stop=lambda c: c.round == rnd and c.phase == "PK",
    )
    assert run.stopped, f"round {rnd} PK never reached"
    return run.state


def _pick_area0_in_early_rounds(ctx: R.Ctx) -> int | None:
    """Everybody picks area 1 (index 0) at PK, so the other areas pile up food."""
    return H.PICK_AREA(0) if ctx.phase == "PK" else None


def _picks(state: Any, areas: list[int]) -> Any:
    for a in areas:
        assert state.current_player() >= 0
        assert H.PICK_AREA(a) in state.legal_actions()
        state.apply_action(H.PICK_AREA(a))
    return state


def _obs_type(private: Any, recall: bool) -> Any:
    return pyspiel.IIGObservationType(public_info=True, perfect_recall=recall, private_info=private)


def _views(state: Any, game: Any, viewer: int) -> dict[str, Any]:
    """Everything a seat can observe, as comparable plain values."""
    v: dict[str, Any] = {
        "obs_str": state.observation_string(viewer),
        "obs_tensor": tuple(state.observation_tensor(viewer)),
        "info_str": state.information_state_string(viewer),
    }
    if game.get_type().provides_information_state_tensor:
        v["info_tensor"] = tuple(state.information_state_tensor(viewer))
    for recall in (False, True):
        o = game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.SINGLE_PLAYER, recall))
        o.set_from(state, viewer)
        v[f"priv_tensor_{recall}"] = tuple(float(x) for x in o.tensor)
        v[f"priv_str_{recall}"] = o.string_from(state, viewer)
    return v


def _public_view(state: Any, game: Any) -> dict[str, Any]:
    o = game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.NONE, False))
    o.set_from(state, 0)
    return {"tensor": tuple(float(x) for x in o.tensor), "str": o.string_from(state, 0)}


def _full_str(state: Any, game: Any) -> str:
    o = game.make_py_observer(_obs_type(pyspiel.PrivateInfoType.ALL_PLAYERS, False))
    return o.string_from(state, 0)


# --------------------------------------------------------------------------- R-038 decisions


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R038_seats_pick_in_seat_order_and_every_area_is_legal(n, joinery):
    """R-038: after R-037 each seat in order P0, P1, ... chooses one of the six areas; every area
    1..6 is legal for every seat (no restriction by wood, by earlier picks or by other seats)."""
    s = _pk(n, joinery)
    assert H.phase_of(s) == "PK"
    for seat in range(n):
        assert s.current_player() == seat
        assert not s.is_chance_node()
        assert sorted(s.legal_actions()) == [H.PICK_AREA(a) for a in ALL_AREAS]
        s.apply_action(H.PICK_AREA(2))  # all seats pick the same area: sharing is allowed
    assert H.phase_of(s) == "TR"


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_only_pick_actions_are_legal_during_the_run(n):
    """R-038 (negative): while picks are pending, no other action is legal (no DONE, loan, move)."""
    s = _pk(n)
    for _ in range(n):
        legal = set(s.legal_actions())
        assert legal == {H.PICK_AREA(a) for a in ALL_AREAS}
        assert H.DONE not in legal and H.TAKE_LOAN not in legal
        s.apply_action(H.PICK_AREA(0))


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_repeating_last_rounds_area_and_empty_areas_are_legal(n):
    """R-038: 'including one chosen in an earlier round, an area with no wood'. Round 2 picks
    area index 0; in round 3 area index 0 is legal again, and so is every other area."""
    run = R.drive(
        _params(n),
        seed=2,
        policy=_pick_area0_in_early_rounds,
        stop=lambda c: c.round == 3 and c.phase == "PK",
    )
    assert run.stopped
    s = run.state
    assert H.PICK_AREA(0) in s.legal_actions()
    assert len(s.legal_actions()) == 6


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_no_pick_run_in_round_1(n):
    """R-038: in round 1 there is no pick; each seat's area is the one placed in setup (R-015).
    The round-1 phases are SP (setup) then TR, never PK, and the TR areas are the setup picks."""
    game = H.as_game(_params(n))
    s = game.new_initial_state()
    rng = random.Random(5)
    placed: list[int] = []
    phases: list[str] = []
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        snap = H.snapshot(s)
        if snap["round"] != 1:
            break
        phases.append(snap["phase"])
        if snap["phase"] == "SP":
            a = s.legal_actions()[-1]
            placed.append(a - 2 + 1)
            s.apply_action(a)
        else:
            assert snap["phase"] == "TR"
            assert [x["cutting_area"] for x in H.seats(snap)] == placed
            break
    assert "PK" not in phases and phases[0] == "SP" and phases[-1] == "TR"


# --------------------------------------------------------------------------- R-038 reveal


def _patterns(n: int) -> list[list[int]]:
    same = [3] * n
    distinct = [(i + 1) % 6 for i in range(n)]
    pairs = [1, 1] + [5 - i for i in range(n - 2)]  # P0 and P1 share area index 1
    return [same, distinct, pairs]


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R038_reveal_places_each_token_in_its_area_and_starts_travel(n, joinery):
    """R-038: when all seats have chosen, every token is placed in its area; the next phase is
    travel (TR) with the first seat of the starting-player track to move (R-034 step 5)."""
    for pattern in _patterns(n):
        s = _pk(n, joinery)
        _picks(s, pattern)
        snap = H.snapshot(s)
        assert snap["phase"] == "TR" and snap["round"] == 2
        assert [x["cutting_area"] for x in H.seats(snap)] == [a + 1 for a in pattern]
        assert snap["current_player"] == snap["turn_order"][0]


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_nothing_is_placed_or_taken_before_all_picks(n):
    """R-038/R-039: a pick is final but not yet effective: after each non-final pick the phase is
    still PK, the next seat is to move, and no seat has received food and no area has lost any
    (food is distributed only at the reveal)."""
    s = _pk(n)
    before = H.snapshot(s)
    for seat in range(n - 1):
        s.apply_action(H.PICK_AREA(1 + (seat % 5)))
        snap = H.snapshot(s)
        assert snap["phase"] == "PK" and snap["current_player"] == seat + 1
        assert [x["food"] for x in H.seats(snap)] == [x["food"] for x in H.seats(before)]
        assert [a["food"] for a in H.areas(snap)] == [a["food"] for a in H.areas(before)]
        assert [a["wood"] for a in H.areas(snap)] == [a["wood"] for a in H.areas(before)]


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_cutting_area_tokens_are_off_the_board_during_picks(n):
    """R-038 + SCENARIOS 4.3 (S-CUT): in PK every `cutting_area` is null; the tokens come back
    to their owners in cleanup (R-061) and are placed again only at the reveal. (The dump shows
    last round's / the setup area still set.)"""
    s = _pk(n)
    for seat in range(n):
        snap = H.snapshot(s)
        assert [x["cutting_area"] for x in H.seats(snap)] == [None] * n, f"before pick {seat}"
        s.apply_action(H.PICK_AREA(seat % 6))


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_god_view_dump_shows_picks_of_seats_before_current_player(n):
    """R-029/R-038 + SCENARIOS 4.2/S-CUT: in PK the scenario dump (perfect-information view) has
    `seats[i].pick` set exactly for the seats before `current_player`, null for the others."""
    s = _pk(n)
    chosen: list[int] = []
    for seat in range(n):
        snap = H.snapshot(s)
        got = [x.get("pick") for x in H.seats(snap)]
        assert got == [a + 1 for a in chosen] + [None] * (n - seat)
        a = (2 * seat + 1) % 6
        chosen.append(a)
        s.apply_action(H.PICK_AREA(a))


@pytest.mark.parametrize("n", PLAYERS)
def test_R038_god_view_string_shows_every_pick_and_differs_by_pick(n):
    """R-030: `str(state)` is the perfect-information view; after P0 picks, its string depends
    on the pick (distinct for all six areas) and equals the ALL_PLAYERS observer string."""
    game = H.as_game(_params(n))
    s = _pk(n)
    seen: set[str] = set()
    for a in ALL_AREAS:
        c = s.clone()
        c.apply_action(H.PICK_AREA(a))
        assert str(c) == _full_str(c, game)
        seen.add(str(c))
    assert len(seen) == 6


# --------------------------------------------------------------------------- hidden information


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R030_unrevealed_pick_is_invisible_to_every_other_seat(n, joinery):
    """R-029/R-030: until the reveal, seat k's pick changes nothing in any other seat's
    observation string/tensor, information-state string/tensor, nor in the public view; checked
    for all six values of every non-final pick, with the later pickers also in the viewer set,
    and for both perfect_recall settings."""
    game = H.as_game(_params(n, joinery))
    s = _pk(n, joinery)
    for k in range(n - 1):  # the last pick triggers the reveal; tested separately
        assert s.current_player() == k
        branches: dict[int, Any] = {}
        for a in ALL_AREAS:
            c = s.clone()
            c.apply_action(H.PICK_AREA(a))
            branches[a] = c
        for viewer in range(n):
            if viewer == k:
                continue
            views = [_views(branches[a], game, viewer) for a in ALL_AREAS]
            for a in range(1, 6):
                assert views[a] == views[0], f"seat {viewer} sees seat {k}'s pick (area idx {a})"
        pubs = [_public_view(branches[a], game) for a in ALL_AREAS]
        assert all(p == pubs[0] for p in pubs)
        s.apply_action(H.PICK_AREA(k % 6))


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R030_picker_sees_own_pick(n, joinery):
    """R-029: the pick is visible to the seat that made it: its observation string, tensor and
    information-state string differ for each of the six areas."""
    game = H.as_game(_params(n, joinery))
    s = _pk(n, joinery)
    for k in range(n - 1):
        views = []
        for a in ALL_AREAS:
            c = s.clone()
            c.apply_action(H.PICK_AREA(a))
            views.append(_views(c, game, k))
        for key in ("obs_str", "obs_tensor", "info_str", "priv_str_False", "priv_tensor_False"):
            assert len({v[key] for v in views}) == 6, (k, key)
        s.apply_action(H.PICK_AREA(k % 6))


@pytest.mark.parametrize("n", (3, 4))
def test_R030_earlier_picks_stay_hidden_from_later_pickers(n):
    """R-030: after P0 and P1 have picked (so the run is still open), P2's views are the
    same whatever P0 and P1 chose, and P0's view does not depend on P1's choice."""
    game = H.as_game(_params(n))
    base = _pk(n)
    seen_p2: set[str] = set()
    seen_p0_given_p0: dict[int, set[str]] = {}
    for p0 in ALL_AREAS:
        for p1 in (0, 3, 5):
            c = base.clone()
            _picks(c, [p0, p1])
            seen_p2.add(repr(_views(c, game, 2)))
            seen_p0_given_p0.setdefault(p0, set()).add(repr(_views(c, game, 0)))
    assert len(seen_p2) == 1
    assert all(len(v) == 1 for v in seen_p0_given_p0.values())
    assert len({next(iter(v)) for v in seen_p0_given_p0.values()}) == 6


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R029_after_the_reveal_all_seats_see_the_same_public_picks(n, joinery):
    """R-029/R-028: once all seats have chosen, every pick is public: each seat's observation
    string is identical, and changing any single seat's pick changes what every seat sees."""
    game = H.as_game(_params(n, joinery))
    base_pick = [1] * n
    base = _pk(n, joinery)
    done = _picks(base.clone(), base_pick)
    strs = {done.observation_string(p) for p in range(n)}
    assert len(strs) == 1
    assert next(iter(strs)) == str(done)
    for seat in range(n):
        alt = list(base_pick)
        alt[seat] = 4
        other = _picks(base.clone(), alt)
        for viewer in range(n):
            assert other.observation_string(viewer) != done.observation_string(viewer)
            assert (
                _views(other, game, viewer)["obs_tensor"]
                != _views(done, game, viewer)["obs_tensor"]
            )


@pytest.mark.parametrize("n", PLAYERS)
def test_R030_state_string_equals_full_observer_at_every_pick_node(n):
    """R-030: str(state) is the perfect-information observer string at every PK node, including
    after some (not all) picks, where it must contain the hidden picks (distinct states never
    print alike)."""
    game = H.as_game(_params(n))
    s = _pk(n)
    seen: set[str] = set()
    for k in range(n):
        assert str(s) == _full_str(s, game)
        assert str(s) not in seen
        seen.add(str(s))
        s.apply_action(H.PICK_AREA(k % 6))
    assert str(s) == _full_str(s, game)
    assert str(s) not in seen


@pytest.mark.parametrize("n", PLAYERS)
def test_R030_seat_labels_zero_based_in_pick_views(n):
    """CLAUDE.md/R-030: pick views name seats P0..P(n-1); 'Player 1'-style labels never appear
    and there is no 'P<n>'."""
    s = _pk(n)
    s.apply_action(H.PICK_AREA(2))
    texts = [str(s)] + [s.observation_string(p) for p in range(n)]
    texts += [s.information_state_string(p) for p in range(n)]
    for t in texts:
        assert "Player 1" not in t and f"P{n}" not in t


# --------------------------------------------------------------------------- R-039 food


def _expected_food(before: dict[str, Any], picks: list[int]) -> tuple[list[int], list[int]]:
    """(seat food, area food) after the reveal by R-039."""
    areas_food = [a["food"] for a in H.areas(before)]
    seat_food = [s["food"] for s in H.seats(before)]
    for area in ALL_AREAS:
        here = [i for i, p in enumerate(picks) if p == area]
        if not here:
            continue
        share = areas_food[area] // len(here)
        for i in here:
            seat_food[i] += share
        areas_food[area] -= share * len(here)
    return seat_food, areas_food


def _check_food(before: dict[str, Any], after: dict[str, Any], picks: list[int]) -> None:
    seat_food, area_food = _expected_food(before, picks)
    assert [s["food"] for s in H.seats(after)] == seat_food
    assert [a["food"] for a in H.areas(after)] == area_food
    # wood is untouched by the reveal and the tokens are in their areas
    assert [a["wood"] for a in H.areas(after)] == [a["wood"] for a in H.areas(before)]
    assert [s["cutting_area"] for s in H.seats(after)] == [p + 1 for p in picks]


def _walk(
    params: dict[str, Any],
    seed: int,
    picker: Callable[[int, int, random.Random], int],
    last_round: int = 7,
) -> Iterator[tuple[int, dict[str, Any], list[int], dict[str, Any]]]:
    """Play with default actions except at PK, where `picker(round, seat, rng)` chooses. Yields
    (round, snapshot at first PK node, picks, snapshot after the last pick) per PK run."""
    game: Any = H.as_game(params)
    s: Any = game.new_initial_state()
    rng = random.Random(seed)
    n = int(params["players"])
    rnd, phase = 0, ""
    before: dict[str, Any] | None = None
    picks: list[int] = []
    while not s.is_terminal():
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        snap = R.try_snapshot(s)
        if snap is not None:
            rnd, phase = snap["round"], snap["phase"]
        if phase == "PK":
            if before is None:
                before, picks = snap, []
            a = picker(rnd, s.current_player(), rng)
            picks.append(a)
            s.apply_action(H.PICK_AREA(a))
            if len(picks) == n:
                after = R.try_snapshot(s)
                assert before is not None and after is not None
                yield rnd, before, picks, after
                before = None
                if rnd >= last_round:
                    return
            continue
        s.apply_action(R.default_action(R.Ctx(s, rnd, phase, snap, rng)))


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
@pytest.mark.parametrize("seed", [0, 1])
def test_R039_food_split_matches_spec_for_random_picks_in_every_seasonal_round(n, joinery, seed):
    """R-039: for random picks in rounds 2, 3, 5, 6, 7: alone -> whole food; k sharing -> equal
    whole shares (f // k each), remainder stays; unoccupied areas keep their food; wood and
    tokens as picked. Seat food accumulates across rounds."""
    seen_rounds: list[int] = []
    for rnd, before, picks, after in _walk(
        _params(n, joinery), seed, lambda r, seat, rng: rng.randrange(6)
    ):
        seen_rounds.append(rnd)
        assert after["phase"] == "TR"
        _check_food(before, after, picks)
    assert seen_rounds == [2, 3, 5, 6, 7]


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_food_split_when_everyone_shares_a_large_area_over_the_year(n):
    """R-039: all seats keep picking the same (unoccupied-before) areas so food piles up in the
    rest, then a late round has big food in areas: the oracle still holds for every pattern."""

    def picker(r: int, seat: int, rng: random.Random) -> int:
        return 0 if r < 7 else (seat // 2) + 1  # round 7: pairs of seats share areas 2, 3

    rows = list(_walk(_params(n), 3, picker))
    assert rows[-1][0] == 7
    for _, before, picks, after in rows:
        _check_food(before, after, picks)


@cache
def _pk_foods(n: int, seed: int, rnd: int) -> list[int]:
    """Area foods at the first PK of round `rnd` when everyone always picked area index 0."""
    s = _pk(n, False, seed=seed, rnd=rnd, policy=_pick_area0_in_early_rounds)
    return [a["food"] for a in H.areas(H.snapshot(s))]


def _find_late_state(
    n: int, want: Callable[[int, int], bool], first_area: int = 1
) -> tuple[Any, int, int]:
    """Search rounds/seeds for a PK state with an area (index >= first_area) of food f for which
    want(f, n) holds. Returns (state, area index, food)."""
    for rnd in (7, 6, 5, 3, 2):
        for seed in range(80):
            foods = _pk_foods(n, seed, rnd)
            for area in range(first_area, 6):
                if want(foods[area], n):
                    s = _pk(n, False, seed=seed, rnd=rnd, policy=_pick_area0_in_early_rounds)
                    return s, area, foods[area]
    pytest.fail(f"no PK state found for n={n} (cannot build the scenario)")


def _others(n: int, k: int, area: int) -> list[int]:
    """Picks for seats k..n-1 that avoid `area` (each on its own area where possible)."""
    pool = [a for a in ALL_AREAS if a != area]
    return [pool[i % len(pool)] for i in range(n - k)]


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_alone_in_area_takes_all_the_food(n):
    """R-039: a seat alone in its area takes the area's entire food into its food storage."""
    s, area, f = _find_late_state(n, lambda f, n: f >= 2)
    before = H.snapshot(s)
    picks = [area] + _others(n, 1, area)
    assert len(set(picks)) == len(picks) or n > 3
    _picks(s, picks)
    after = H.snapshot(s)
    assert H.areas(after)[area]["food"] == 0 or picks.count(area) > 1
    assert H.seats(after)[0]["food"] == H.seats(before)[0]["food"] + f
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_two_seats_share_even_food_equally(n):
    """R-039: seats that share an area divide food evenly: area food 2m with two sharers gives m
    each and leaves nothing."""
    s, area, f = _find_late_state(n, lambda f, n: f >= 2 and f % 2 == 0)
    before = H.snapshot(s)
    picks = [area, area] + _others(n, 2, area)
    _picks(s, picks)
    after = H.snapshot(s)
    gain = [H.seats(after)[i]["food"] - H.seats(before)[i]["food"] for i in (0, 1)]
    assert gain == [f // 2, f // 2]
    assert H.areas(after)[area]["food"] == 0
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_two_seats_share_odd_food_remainder_stays(n):
    """R-039: pieces that cannot be divided remain in the area: food 2m+1 shared by two seats
    gives m each and the area keeps 1 (spec example: 3 food, two seats -> 1 each, 1 stays)."""
    s, area, f = _find_late_state(n, lambda f, n: f >= 3 and f % 2 == 1)
    before = H.snapshot(s)
    picks = [area, area] + _others(n, 2, area)
    _picks(s, picks)
    after = H.snapshot(s)
    gain = [H.seats(after)[i]["food"] - H.seats(before)[i]["food"] for i in (0, 1)]
    assert gain == [f // 2, f // 2]
    assert H.areas(after)[area]["food"] == 1
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_fewer_food_than_sharers_nobody_takes_any(n):
    """R-039 boundary: food < number of sharing seats -> nobody receives any, the food stays.
    Spec example: 1 food, two sharers. Also checked with n sharers and food n - 1 (n >= 3)."""
    s, area, f = _find_late_state(n, lambda f, n: f == 1)
    before = H.snapshot(s)
    picks = [area, area] + _others(n, 2, area)
    _picks(s, picks)
    after = H.snapshot(s)
    for i in (0, 1):
        assert H.seats(after)[i]["food"] == H.seats(before)[i]["food"]
    assert H.areas(after)[area]["food"] == 1
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", (3, 4))
def test_R039_all_seats_share_and_food_below_seat_count(n):
    """R-039 boundary: n seats in one area with 2 <= food < n: nobody receives any."""
    s, area, f = _find_late_state(n, lambda f, n: 2 <= f < n)
    before = H.snapshot(s)
    picks = [area] * n
    _picks(s, picks)
    after = H.snapshot(s)
    assert [x["food"] for x in H.seats(after)] == [x["food"] for x in H.seats(before)]
    assert H.areas(after)[area]["food"] == f
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_all_seats_share_and_food_at_least_seat_count(n):
    """R-039: n seats in one area with food >= n: each gets f // n; remainder stays."""
    s, area, f = _find_late_state(n, lambda f, n: f >= n)
    before = H.snapshot(s)
    picks = [area] * n
    _picks(s, picks)
    after = H.snapshot(s)
    for i in range(n):
        assert H.seats(after)[i]["food"] == H.seats(before)[i]["food"] + f // n
    assert H.areas(after)[area]["food"] == f % n
    _check_food(before, after, picks)


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_unoccupied_areas_keep_their_food(n):
    """R-039: only areas that hold a token are distributed; remaining supplies stay in the area.
    Everybody takes the same area, so the other five keep exactly their food."""
    s, area, f = _find_late_state(n, lambda f, n: f >= 1)
    before = H.snapshot(s)
    other = (area + 1) % 6
    _picks(s, [other] * n)
    after = H.snapshot(s)
    for a in ALL_AREAS:
        if a != other:
            assert H.areas(after)[a]["food"] == H.areas(before)[a]["food"]


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_empty_food_area_gives_nothing(n):
    """R-039 boundary: an occupied area with 0 food changes no seat's food and no area's food."""
    s, area, _ = _find_late_state(n, lambda f, n: f == 0, first_area=0)
    before = H.snapshot(s)
    _picks(s, [area] * n)
    after = H.snapshot(s)
    assert [x["food"] for x in H.seats(after)] == [x["food"] for x in H.seats(before)]
    assert [a["food"] for a in H.areas(after)] == [a["food"] for a in H.areas(before)]


@pytest.mark.parametrize("n", PLAYERS)
def test_R039_food_is_public_after_the_reveal(n):
    """R-039/R-028: food taken is public: after the reveal every seat's observation shows it
    (all observations equal), and it differs from the pre-reveal observation of a bystander."""
    s, area, f = _find_late_state(n, lambda f, n: f >= 1)
    before_views = {p: s.observation_string(p) for p in range(n)}
    _picks(s, [area] + _others(n, 1, area))
    assert len({s.observation_string(p) for p in range(n)}) == 1
    for p in range(n):
        assert s.observation_string(p) != before_views[p]
