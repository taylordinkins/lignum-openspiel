"""Phase 4 unit 9: Buildings acquisition (R-106, R-010, R-019, R-063).

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only, through tests/harness.py and the
helpers in tests/support (public API only).

Conventions
  * Buildings location = printed location 12 on the joinery side (R-022); MOVE_TO(12) = 19.
  * CHOOSE_BUILDING(b) = 57 + b, b = index in data/components/buildings.yaml (ACTIONS 3).
  * The visit auto-ends after the single acquisition (ACTIONS 1.4), so no DONE follows.
  * No test depends on a building's effect. None of the ten effects (R-107..R-116) fires at the
    moment of acquisition: all are conditional on a later event (transport, Market, winter, PW
    cost, drying, final sale, Fodder, Tasks-phase storage). "Effect is immediate" (R-106) is
    therefore not observable at acquisition time.
  * Seats own buildings in `seats[i]["buildings"]` (building ids), the supply is
    `supply["buildings"]` (SCENARIOS 3/4).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

BLD = R.loc(True, "buildings")  # 12
CHOOSE0 = R.CHOOSE_BUILDING0
CHOOSE_END = R.CHOOSE_BUILDING_END
CHOOSES = range(CHOOSE0, CHOOSE_END + 1)
DRAWN = {2: 6, 3: 7, 4: 8}
PLAYERS = (2, 3, 4)


def _ids() -> list[str]:
    with open(R.ROOT / "data" / "components" / "buildings.yaml", encoding="utf-8") as fh:
        return [b["id"] for b in yaml.safe_load(fh)["buildings"]]


IDS = _ids()


def _choose(bid: str) -> int:
    return CHOOSE0 + IDS.index(bid)


def _legal_chooses(s: Any) -> list[int]:
    return sorted(a for a in s.legal_actions() if a in CHOOSES)


def _supply(sn: dict[str, Any]) -> list[str]:
    return list(sn["supply"]["buildings"])


def _owned(sn: dict[str, Any], i: int) -> list[str]:
    return list(T.seat_of(sn, i)["buildings"])


def _enter(s: Any) -> None:
    T.play(s, H.MOVE_TO(BLD))


def _first(s: Any) -> int:
    return _legal_chooses(s)[0]


# --------------------------------------------------------------------------- R-106 entry


@pytest.mark.parametrize("n", PLAYERS)
def test_R106_buildings_location_enterable_with_joinery_and_empty_board(n):
    """R-106/R-040: with joinery=true, no buildings owned and a non-empty supply, MOVE_TO(12)
    is legal for the first foreman (free acquisition, activation test passes)."""
    s = T.start(n, True)
    assert _supply(T.snap(s))
    assert BLD in T.move_locs(s)


@pytest.mark.parametrize("n", PLAYERS)
def test_R106_joinery_false_never_offers_choose_building(n):
    """R-106/R-002: joinery=false: no building supply, location 12 is not Buildings, and
    CHOOSE_BUILDING is never legal during a full round of random travel."""
    s = T.start(n, False)
    assert _supply(T.snap(s)) == []
    import random

    rng = random.Random(n)
    for _ in range(3000):
        if s.is_terminal():
            break
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
            continue
        legal = s.legal_actions()
        assert not any(a in CHOOSES for a in legal)
        s.apply_action(rng.choice(legal))
    sn = H.snapshot(s) if not s.is_terminal() else None
    if sn:
        assert all(list(x["buildings"]) == [] for x in H.seats(sn))


@pytest.mark.parametrize("n", PLAYERS)
def test_R106_entering_offers_exactly_the_tiles_in_the_supply(n):
    """R-106: after MOVE_TO(Buildings) the legal CHOOSE_BUILDING(b) are exactly the tiles in the
    supply (6/7/8 of the 10); nothing else is legal until a choice is made (no DONE)."""
    s = T.start(n, True)
    sup = _supply(T.snap(s))
    assert len(sup) == DRAWN[n]
    _enter(s)
    assert _legal_chooses(s) == sorted(_choose(b) for b in sup)
    assert H.DONE not in s.legal_actions()
    assert R.MOVE_CLEARING not in s.legal_actions()


# --------------------------------------------------------------------------- R-106 choice


@pytest.mark.parametrize("n", PLAYERS)
def test_R106_choice_moves_tile_from_supply_to_seat_free_and_ends_visit(n):
    """R-106/R-010: every tile in the supply may be chosen (free choice). The tile leaves the
    supply, lands on the seat, money is unchanged, the visit auto-ends and the turn passes."""
    s0 = T.start(n, True)
    sup = _supply(T.snap(s0))
    money0 = T.seat_of(T.snap(s0), 0)["money"]
    for bid in sup:
        s = T.start(n, True)
        _enter(s)
        assert _choose(bid) in s.legal_actions()
        T.play(s, _choose(bid))
        assert s.current_player() == 1 % n
        sn = T.snap(s)
        assert _owned(sn, 0) == [bid]
        assert sorted(_supply(sn)) == sorted(set(sup) - {bid})
        assert T.seat_of(sn, 0)["money"] == money0
        assert T.seat_of(sn, 0)["loans"] == 0
        assert not any(a in CHOOSES for a in s.legal_actions())


def test_R106_tile_not_in_supply_is_not_legal_to_choose():
    """R-106: the undrawn tiles (returned to the box, R-019) are never legal choices."""
    s = T.start(2, True)
    sup = set(_supply(T.snap(s)))
    undrawn = [b for b in IDS if b not in sup]
    assert len(undrawn) == 4
    _enter(s)
    assert not set(_legal_chooses(s)) & {_choose(b) for b in undrawn}


# --------------------------------------------------------------------------- capacity


def test_R106_capacity_two_third_foreman_cannot_enter_and_taken_tile_is_gone():
    """R-106/R-040 item 3: Buildings holds 2 foremen. P0 and P1 each take one; the tile P0 took
    is no longer offered to P1; P2 cannot enter while both stand there; P3 neither."""
    s = T.start(4, True)
    sup0 = _supply(T.snap(s))
    _enter(s)
    a = _first(s)
    T.play(s, a)
    assert BLD in T.move_locs(s)  # P1: one space left
    _enter(s)
    assert a not in _legal_chooses(s)
    assert len(_legal_chooses(s)) == len(sup0) - 1
    b = _first(s)
    T.play(s, b)
    assert s.current_player() == 2
    assert BLD not in T.move_locs(s)
    sn = T.snap(s)
    assert len(_supply(sn)) == len(sup0) - 2
    assert _owned(sn, 0) != _owned(sn, 1)
    T.play(s, R.MOVE_CLEARING)
    assert BLD not in T.move_locs(s)  # P3


def test_R106_foremen_on_buildings_hold_both_spaces_until_they_move_on():
    """R-040 item 3/R-106: 4 players: P0 and P1 take buildings and stay on 12, so P2 and P3 cannot
    enter; P0, standing on 12, cannot re-enter it (forward only)."""
    s = T.start(4, True)
    for _ in range(2):
        _enter(s)
        T.play(s, _first(s))
    T.play(s, R.MOVE_CLEARING)  # P2
    assert BLD not in T.move_locs(s)  # P3 blocked
    T.play(s, R.MOVE_CLEARING)  # P3
    assert s.current_player() == 0
    assert BLD not in T.move_locs(s)


# --------------------------------------------------------------------------- per-seat limits


def _take_in(rounds_by_seat: dict[tuple[int, int], int]) -> R.Script:
    return R.Script(
        {k: [R.move(True, "buildings"), R.first_legal(CHOOSE0, CHOOSE_END)] for k in rounds_by_seat}
    )


@pytest.mark.parametrize("n", PLAYERS)
def test_R106_seat_owns_at_most_two_buildings_one_per_round(n):
    """R-106/R-010: P0 takes one in round 1 (owns 1), one in round 2 (owns 2); in round 3 the
    Buildings location is not enterable for P0. Both buildings stay (permanent) and differ."""
    pol = _take_in({(1, 0): 1, (2, 0): 1})
    run = R.drive(
        {"players": n, "joinery": True}, seed=3, policy=pol,
        stop=lambda c: c.round == 3 and c.phase == "TR" and c.player == 0,
    )  # fmt: skip
    assert run.stopped
    sn = H.snapshot(run.state)
    mine = _owned(sn, 0)
    assert len(mine) == 2 and len(set(mine)) == 2
    assert H.MOVE_TO(BLD) not in run.state.legal_actions()
    assert not set(mine) & set(_supply(sn))
    # permanence: still owned in later rounds
    assert _owned(run.event(2).after, 0) == mine[:1]


def test_R106_one_building_per_round_per_seat():
    """R-106: a visit gives exactly one building: after the choice P0's round-1 turn is over and
    its foreman is on 12, so it cannot take a second one that round. Next round it can (owns 1)."""
    pol = _take_in({(1, 0): 1})
    run = R.drive(
        {"players": 2, "joinery": True}, seed=2, policy=pol,
        stop=lambda c: c.round == 2 and c.phase == "TR" and c.player == 0,
    )  # fmt: skip
    assert run.stopped
    assert len(_owned(H.snapshot(run.state), 0)) == 1
    assert H.MOVE_TO(BLD) in run.state.legal_actions()


def test_R106_four_players_drain_the_supply_with_two_each():
    """R-106/R-019/R-063: 4 players, 8 tiles: P0,P1 take in rounds 1 and 3, P2,P3 in rounds 2
    and 5. Everyone ends with 2, the supply is empty, no tile is duplicated, and the supply is
    never refilled in between (R-063)."""
    sc: dict[tuple[int, int], list[Any]] = {}
    for rnd, seats in ((1, (0, 1)), (2, (2, 3)), (3, (0, 1)), (5, (2, 3))):
        for p in seats:
            sc[(rnd, p)] = [R.move(True, "buildings"), R.first_legal(CHOOSE0, CHOOSE_END)]
    run = R.drive(
        {"players": 4, "joinery": True}, seed=5, policy=R.Script(sc),
        stop=lambda c: c.round == 6,
    )  # fmt: skip
    assert run.stopped
    start = _supply(run.event(1).after)
    assert len(start) == 8
    sizes = [len(_supply(run.event(r).after)) for r in (2, 3, 5)]
    assert sizes == [6, 4, 2]
    sn = H.snapshot(run.state)
    held = [b for i in range(4) for b in _owned(sn, i)]
    assert _supply(sn) == []
    assert all(len(_owned(sn, i)) == 2 for i in range(4))
    assert sorted(held) == sorted(start)


# --------------------------------------------------------------------------- R-063


@pytest.mark.parametrize("n", PLAYERS)
def test_R063_supply_never_refilled_and_conserved_across_rounds(n):
    """R-063/R-106: P0 takes one tile in round 1. In every later seasonal round the supply is the
    round-1 supply minus that tile (no refill) and supply + owned = the drawn set."""
    pol = _take_in({(1, 0): 1})
    run = R.drive(
        {"players": n, "joinery": True}, seed=4, policy=pol, stop=lambda c: c.round == 7
    )  # fmt: skip
    assert run.stopped
    drawn = set(_supply(run.event(1).after))
    assert len(drawn) == DRAWN[n]
    for rnd in (2, 3, 5, 6, 7):
        a = run.event(rnd).after
        owned = [b for i in range(n) for b in _owned(a, i)]
        assert len(owned) == 1
        assert set(_supply(a)) | set(owned) == drawn
        assert len(_supply(a)) == DRAWN[n] - 1


@pytest.mark.parametrize("n", PLAYERS)
def test_R063_untouched_supply_is_constant_over_the_game(n):
    """R-063/R-019: if nobody enters Buildings the supply stays the same set in every round."""
    run = R.drive({"players": n, "joinery": True}, seed=6, stop=lambda c: c.round == 7)
    first = sorted(_supply(run.event(1).after))
    for rnd in (2, 3, 5, 6, 7):
        assert sorted(_supply(run.event(rnd).after)) == first


# --------------------------------------------------------------------------- R-019


@pytest.mark.parametrize("n", PLAYERS)
def test_R019_supply_size_by_player_count_and_distinct_known_tiles(n):
    """R-019: 2/3/4 players -> 6/7/8 distinct tiles drawn from the 10; seats own none at start."""
    sn = T.snap(T.start(n, True))
    sup = _supply(sn)
    assert len(sup) == DRAWN[n] and len(set(sup)) == len(sup) and set(sup) <= set(IDS)
    assert all(_owned(sn, i) == [] for i in range(n))


# --------------------------------------------------------------------------- R-028 public


def test_R106_owned_building_is_public_in_other_seats_observation():
    """R-106/R-028: buildings are public. After P0 takes one, P1's observation string changes and
    shows P0's holding (the observer prints building indices, ` bld <index>`)."""
    s = T.start(2, True)
    before = s.observation_string(1)
    _enter(s)
    bid = IDS[_first(s) - CHOOSE0]
    T.play(s, _first(s))
    after = s.observation_string(1)
    assert after != before
    assert _owned(T.snap(s), 0) == [bid]
    assert f" bld {IDS.index(bid)}" in after


def test_R106_taking_different_tiles_gives_different_states():
    """R-106 + CLAUDE.md (str of distinct states differ): two different choices produce states
    with different strings."""
    strs = set()
    for k in (0, 1):
        s = T.start(2, True)
        _enter(s)
        T.play(s, _legal_chooses(s)[k])
        strs.add(str(s))
    assert len(strs) == 2
