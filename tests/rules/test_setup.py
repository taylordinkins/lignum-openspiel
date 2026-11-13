"""Phase 2 unit 3: setup (SC chance run, SP public picks, round 1 at TR).

Rules: R-012..R-020, R-026, R-027, R-031, plus R-021/R-022/R-032 for the two path sides.
ACTIONS section 2 (chance IDs), section 4 (phases SC, SP), section 5.1 (setup picks).

Planned API assumed (nothing here reads engine internals; everything goes through tests/harness.py):

  * The game "python_lignum" (players, joinery, returns, easy_winter) with chance nodes in the
    order of ACTIONS section 2: AREAS3, WINTER x2, TASK_DRAW x n, PW_DRAW x (n+2),
    BUILDING_DRAW x (6/7/8, joinery only), CRAFT_DRAW x 3, SPOT_TOKEN x 13, then decision nodes
    PICK_AREA x n (phase SP, seats 0..n-1), then round 1 at phase TR with seat 0 to act.
  * lignum.scenario.dump_scenario(state) returns the resolved scenario dict (SCENARIOS.md 2, 4, 8)
    at any decision node: parameters, round, phase, current_player, turn_order,
    seats[i] (money, loans, food, fodder, equipment, craftwork, hired, woodpile, joiners,
    buildings, foreman, cutting_area as printed 1..6 or null), cutting_areas[i].wood,
    path (bearers, woodcutters, sawyers_free, sawyers_paid, fodder, joiner, tokens keyed by printed
    location number with values wagon/raft/saw/sledge/dollar/food/x/board/shingle/stake/reed/joker),
    planned_work.laid_out, supply (tasks_laid_out, winter {year1, year2: {card, half}}, buildings,
    craftwork_removed). Card ids are the `id` fields of cards.yaml / planned_work.yaml /
    buildings.yaml in file order (index = ACTIONS chance parameter).
  * AREAS3 rank r selects the r-th k-subset (k = players) of {0..5} in lexicographic order: the
    set of 3-firewood areas (user decision 2026-11-05).
  * Setup state is public: the public observer string is identical for every seat.
"""

import itertools
import random
from math import comb

import pyspiel
import pytest

from tests import harness as H

PLAYERS = (2, 3, 4)
BOOLS = (True, False)
SEEDS = (0, 1, 2)
CRAFT_ORDER = ("board", "shingle", "stake", "reed", "joker")
EQUIP_SPOT_ORDER = ("wagon", "raft", "saw", "sledge", "dollar", "food", "x_marker")
SNAP_NAME = {"x_marker": "x"}


def _comp():
    from lignum.components import load_components

    return load_components()


def _g(obj, key):
    """Mapping-or-attribute access, so the tests do not depend on the loader's nesting types."""
    if isinstance(obj, dict) or hasattr(obj, "keys"):
        return obj[key]
    return getattr(obj, key)


def _by_players(comp, n):
    return (
        _g(comp.setup, "by_players")[n]
        if not hasattr(_g(comp.setup, "by_players"), "get")
        else (_g(comp.setup, "by_players").get(n))
    )


def _quantities(n):
    q = _by_players(_comp(), n)
    return {
        k: _g(q, k)
        for k in (
            "bearers_on_path",
            "woodcutters_on_path",
            "fodder_on_path",
            "sawyers_price_0",
            "sawyers_price_1",
            "cutting_areas_with_3_firewood",
            "cutting_areas_with_2_firewood",
            "task_cards_laid_out",
            "pw_cards_laid_out",
            "buildings_drawn",
        )
    }


def _equipment(n):
    q = _g(_by_players(_comp(), n), "path_equipment_tokens")
    return {
        k: _g(q, k) if (hasattr(q, "keys") and k in q) or hasattr(q, k) else 0
        for k in EQUIP_SPOT_ORDER
    }


def _craft_totals():
    cw = _g(_g(_comp().setup, "supply"), "craftwork_by_type")
    return {k: _g(cw, k) for k in CRAFT_ORDER}


def _token_spots(joinery):
    side = _comp().path.sides["joinery" if joinery else "base"]
    return [loc.number for loc in side if loc.kind == "token_spot"]


def _winter_ids(year):
    return [w.id for w in _comp().winter if w.year == year]


def _easier_half(card):
    h = card.halves
    tot = {k: _g(h[k], "food") + _g(h[k], "heating") for k in ("top", "bottom")}
    return 0 if tot["top"] < tot["bottom"] else 1


def _expected_sequence(n, joinery):
    q = _quantities(n)
    seq = ["AREAS3", "WINTER", "WINTER"]
    seq += ["TASK_DRAW"] * q["task_cards_laid_out"]
    seq += ["PW_DRAW"] * q["pw_cards_laid_out"]
    if joinery:
        seq += ["BUILDING_DRAW"] * q["buildings_drawn"]
    seq += ["CRAFT_DRAW"] * 3 + ["SPOT_TOKEN"] * 13
    return seq


def walk_setup(n, joinery, easy=False, seed=0):
    """Run the chance part with a seeded rng, asserting every node's outcome set and
    probabilities against an independent model. Returns (state at first SP node, chance ids)."""
    comp = _comp()
    game = H.load_game(players=n, joinery=joinery, easy_winter=easy)
    s = game.new_initial_state()
    rng = random.Random(seed)
    drawn = {"TASK_DRAW": set(), "PW_DRAW": set(), "BUILDING_DRAW": set()}
    pool = {
        "TASK_DRAW": len(comp.tasks),
        "PW_DRAW": len(comp.planned_work),
        "BUILDING_DRAW": len(comp.buildings),
    }
    craft_left = _craft_totals()
    equip = _equipment(n)
    spot_left = {k: v for k, v in equip.items() if v}
    ids = []
    seq = _expected_sequence(n, joinery)
    for i, fam_expected in enumerate(seq):
        assert s.is_chance_node(), f"node {i} should be chance ({fam_expected})"
        assert s.current_player() == pyspiel.PlayerId.CHANCE
        outs = s.chance_outcomes()
        got_ids = [a for a, _ in outs]
        assert len(set(got_ids)) == len(got_ids), "duplicate chance outcome"
        assert sorted(s.legal_actions()) == sorted(got_ids)
        assert sum(p for _, p in outs) == pytest.approx(1.0)
        assert all(p > 0 for _, p in outs)
        fams = {H.chance_family(a)[0] for a in got_ids}
        assert fams == {fam_expected}, f"node {i}: {fams} != {fam_expected}"
        probs = dict(outs)
        base = H.CHANCE_BASE[fam_expected]
        if fam_expected == "AREAS3":
            k = {2: 4, 3: 3, 4: 2}[n]
            assert sorted(got_ids) == list(range(comb(6, k)))
            assert all(p == pytest.approx(1 / comb(6, k)) for p in probs.values())
        elif fam_expected == "WINTER":
            year = 1 + sum(1 for x in ids if H.chance_family(x)[0] == "WINTER")
            cards = [w for w in comp.winter if w.year == year]
            want = {
                base + 2 * c + h
                for c, w in enumerate(cards)
                for h in ((_easier_half(w),) if easy else (0, 1))
            }
            assert set(got_ids) == want
            assert all(p == pytest.approx(1 / len(want)) for p in probs.values())
        elif fam_expected in drawn:
            left = [base + t for t in range(pool[fam_expected]) if t not in drawn[fam_expected]]
            assert sorted(got_ids) == left
            assert all(p == pytest.approx(1 / len(left)) for p in probs.values())
        elif fam_expected == "CRAFT_DRAW":
            tot = sum(craft_left.values())
            want = {
                base + x: craft_left[c] / tot for x, c in enumerate(CRAFT_ORDER) if craft_left[c]
            }
            assert set(got_ids) == set(want)
            for a, p in want.items():
                assert probs[a] == pytest.approx(p)
        else:  # SPOT_TOKEN
            tot = sum(spot_left.values())
            want = {
                base + y: spot_left[nm] / tot
                for y, nm in enumerate(list(EQUIP_SPOT_ORDER) + list(CRAFT_ORDER))
                if spot_left.get(nm)
            }
            assert set(got_ids) == set(want)
            for a, p in want.items():
                assert probs[a] == pytest.approx(p)
        a = H.sample_chance(s, rng)
        fam, par = H.chance_family(a)
        if fam in drawn:
            drawn[fam].add(par)
        elif fam == "CRAFT_DRAW":
            craft_left[CRAFT_ORDER[par]] -= 1
            spot_left[CRAFT_ORDER[par]] = spot_left.get(CRAFT_ORDER[par], 0) + 1
        elif fam == "SPOT_TOKEN":
            names = list(EQUIP_SPOT_ORDER) + list(CRAFT_ORDER)
            spot_left[names[par]] -= 1
        s.apply_action(a)
        ids.append(a)
    assert not s.is_chance_node()
    return s, ids


# ---------------------------------------------------------------- R-026 chance order and shape


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R026_chance_nodes_in_acting_order_with_valid_distributions(n, joinery, seed):
    """R-026/ACTIONS 2: setup chance nodes come in the documented order and counts; at each one
    every outcome is legal exactly once, probabilities are positive, sum to 1 and follow the
    remaining deck/pile/token counts (R-014, R-017)."""
    s, ids = walk_setup(n, joinery, seed=seed)
    assert len(ids) == len(_expected_sequence(n, joinery))
    assert len(ids) <= 37
    assert s.history() == ids
    assert s.get_game().max_chance_nodes_in_history() >= len(ids)


@pytest.mark.parametrize("n", PLAYERS)
def test_R026_no_building_draws_when_joinery_false(n):
    """R-026(4)/R-002: BUILDING_DRAW nodes exist only with joinery=true."""
    _, ids = walk_setup(n, False)
    assert all(H.chance_family(a)[0] != "BUILDING_DRAW" for a in ids)
    _, ids = walk_setup(n, True)
    assert (
        sum(H.chance_family(a)[0] == "BUILDING_DRAW" for a in ids)
        == _quantities(n)["buildings_drawn"]
    )


@pytest.mark.parametrize("n", PLAYERS)
def test_R026_no_placement_draw_in_round_1(n):
    """R-020/R-037: round 1 has no placement-card draw, so setup has no PLACEMENT_DRAW node."""
    _, ids = walk_setup(n, True)
    assert all(H.chance_family(a)[0] != "PLACEMENT_DRAW" for a in ids)


@pytest.mark.parametrize("n", PLAYERS)
def test_R026_no_decision_node_before_sp(n):
    """R-012/ACTIONS 4: nobody acts until the chance run is over; the first decision node is SP
    with seat 0 to act."""
    game = H.load_game(players=n)
    s = game.new_initial_state()
    rng = random.Random(3)
    count = 0
    while s.is_chance_node():
        assert s.current_player() == pyspiel.PlayerId.CHANCE
        s.apply_action(H.sample_chance(s, rng))
        count += 1
    assert count == len(_expected_sequence(n, True))
    assert H.phase_of(s) == "SP"
    assert s.current_player() == 0


# ---------------------------------------------------------------- R-015 AREAS3 and layout


@pytest.mark.parametrize("n", PLAYERS)
def test_R015_every_areas3_outcome_gives_a_distinct_correct_layout(n):
    """R-015/R-013: each AREAS3 outcome yields the R-013 number of 3-firewood areas (others
    2 firewood), no softwood/hardwood; across all outcomes every subset occurs exactly once and
    the 3-firewood set equals the rank-th lexicographic n-subset."""
    q = _quantities(n)
    k = n
    root = H.load_game(players=n).new_initial_state()
    combos = list(itertools.combinations(range(6), k))
    layouts = set()
    for a, _ in root.chance_outcomes():
        s, rng = root.clone(), random.Random(a)
        s.apply_action(a)
        while s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
        areas = H.areas(H.snapshot(s))
        fw = [x["wood"]["firewood"] for x in areas]
        assert len(fw) == 6
        assert sorted(fw) == sorted(
            [3] * q["cutting_areas_with_3_firewood"] + [2] * q["cutting_areas_with_2_firewood"]
        )
        assert all(x["wood"]["softwood"] == 0 and x["wood"]["hardwood"] == 0 for x in areas)
        three = frozenset(i for i, v in enumerate(fw) if v == 3)
        sub = frozenset(combos[a])
        assert three == sub  # user decision 2026-11-05: rank of the 3-firewood subset, k = players
        layouts.add(three)
    assert len(layouts) == comb(6, k)


# ---------------------------------------------------------------- R-027 winter cards


@pytest.mark.parametrize("n", PLAYERS)
def test_R027_winter_halves_random_when_not_easy(n):
    """R-027/R-014: with easy_winter=false all 8 WINTER outcomes (4 cards x 2 halves) are offered
    at both winter nodes with equal probability; year-1 node yields a year-1 card and year-2 node
    a year-2 card, visible half as chosen."""
    for seed in SEEDS:
        s, ids = walk_setup(n, True, easy=False, seed=seed)
        w = [a for a in ids if H.chance_family(a)[0] == "WINTER"]
        assert len(w) == 2
        sup = H.snapshot(s)["supply"]["winter"]
        for year, a in ((1, w[0]), (2, w[1])):
            c, h = H.chance_family(a)[1]
            entry = sup[f"year{year}"]
            assert entry["card"] == _winter_ids(year)[c]
            assert entry["half"] == ("top", "bottom")[h]


@pytest.mark.parametrize("n", PLAYERS)
def test_R027_easy_winter_only_offers_easier_half(n):
    """R-027/R-117: with easy_winter=true each card shows its lower food+heating half; only those
    outcomes are offered (card choice stays chance; ACTIONS A12)."""
    s, ids = walk_setup(n, False, easy=True, seed=5)
    w = [a for a in ids if H.chance_family(a)[0] == "WINTER"]
    sup = H.snapshot(s)["supply"]["winter"]
    for year, a in ((1, w[0]), (2, w[1])):
        c, h = H.chance_family(a)[1]
        card = [x for x in _comp().winter if x.year == year][c]
        assert h == _easier_half(card)
        assert sup[f"year{year}"]["half"] == ("top", "bottom")[h]


# ------------------------------------------------------- R-014 R-017 R-018 R-019 state


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R014_laid_out_cards_match_the_chance_draws(n, joinery, seed):
    """R-014/R-013/R-019: tasks laid out = players, PW cards = players+2, buildings 6/7/8 (joinery
    only), each exactly the cards drawn, no repeats."""
    comp = _comp()
    q = _quantities(n)
    s, ids = walk_setup(n, joinery, seed=seed)
    snap = H.snapshot(s)
    by = {
        f: [H.chance_family(a)[1] for a in ids if H.chance_family(a)[0] == f]
        for f in ("TASK_DRAW", "PW_DRAW", "BUILDING_DRAW")
    }
    assert len(snap["supply"]["tasks_laid_out"]) == q["task_cards_laid_out"] == n
    assert set(snap["supply"]["tasks_laid_out"]) == {comp.tasks[t].id for t in by["TASK_DRAW"]}
    assert len(snap["planned_work"]["laid_out"]) == q["pw_cards_laid_out"] == n + 2
    assert set(snap["planned_work"]["laid_out"]) == {comp.planned_work[c].id for c in by["PW_DRAW"]}
    if joinery:
        assert len(snap["supply"]["buildings"]) == q["buildings_drawn"]
        assert set(snap["supply"]["buildings"]) == {
            comp.buildings[b].id for b in by["BUILDING_DRAW"]
        }
    else:
        assert list(snap["supply"]["buildings"]) == []


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R017_initial_path_fill(n, joinery, seed):
    """R-017/R-013/R-023: bearers, woodcutters, fodder and sawyers per player count; $1 sawyer
    present; joiner on the Joiner location only with joinery; 13 token spots (printed numbers of
    the chosen side) each hold the SPOT_TOKEN drawn for that spot in order 1..13; the multiset is
    the setup.yaml equipment plus the 3 drawn craftwork tokens."""
    q = _quantities(n)
    s, ids = walk_setup(n, joinery, seed=seed)
    path = H.snapshot(s)["path"]
    assert path["bearers"] == q["bearers_on_path"]
    assert path["woodcutters"] == q["woodcutters_on_path"]
    assert path["fodder"] == q["fodder_on_path"]
    assert path["sawyers_free"] == q["sawyers_price_0"]
    assert path["sawyers_paid"] == q["sawyers_price_1"]
    assert path["joiner"] == (
        _g(_comp().setup, "joinery_setup")["joiners_on_path"] if joinery else 0
    )
    toks = H.tokens(H.snapshot(s))
    spots = _token_spots(joinery)
    assert len(spots) == 13
    assert sorted(toks) == sorted(spots)
    names = list(EQUIP_SPOT_ORDER) + list(CRAFT_ORDER)
    drawn = [
        SNAP_NAME.get(names[H.chance_family(a)[1]], names[H.chance_family(a)[1]])
        for a in ids
        if H.chance_family(a)[0] == "SPOT_TOKEN"
    ]
    assert [toks[sp] for sp in sorted(spots)] == drawn
    craft_drawn = sorted(
        CRAFT_ORDER[H.chance_family(a)[1]] for a in ids if H.chance_family(a)[0] == "CRAFT_DRAW"
    )
    assert len(craft_drawn) == _g(_comp().setup, "path_craftwork_tokens") == 3
    expect = []
    for nm, cnt in _equipment(n).items():
        expect += [SNAP_NAME.get(nm, nm)] * cnt
    expect += craft_drawn
    assert sorted(toks.values()) == sorted(expect)


def test_R017_two_player_mix_has_two_x_markers_and_fewer_wagon_saw():
    """R-017/R-013: 2 players: 2 X-markers, 1 wagon, 1 saw; 3 and 4 players: no X, 2 wagons, 2 saws.
    Equipment counts are 10 either way."""
    for n in PLAYERS:
        s, _ = walk_setup(n, True, seed=9)
        vals = list(H.tokens(H.snapshot(s)).values())
        assert vals.count("x") == (2 if n == 2 else 0)
        assert vals.count("wagon") == (1 if n == 2 else 2)
        assert vals.count("saw") == (1 if n == 2 else 2)
        assert vals.count("raft") == 2
        assert vals.count("sledge") == 1
        assert vals.count("dollar") == 1
        assert vals.count("food") == 2
        assert sum(v in CRAFT_ORDER for v in vals) == 3


def test_R021_R022_token_spot_numbers_follow_the_board_side():
    """R-021/R-022/R-032: the 13 token spots are keyed by the printed numbers of the chosen side
    (base 1,2,3,5,7,9,11,12,14,15,17,18,20; joinery 1,2,3,5,7,9,11,13,15,17,19,20,22)."""
    base = H.tokens(H.snapshot(walk_setup(2, False)[0]))
    join = H.tokens(H.snapshot(walk_setup(2, True)[0]))
    assert sorted(base) == [1, 2, 3, 5, 7, 9, 11, 12, 14, 15, 17, 18, 20]
    assert sorted(join) == [1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22]
    assert H.snapshot(walk_setup(2, False)[0])["parameters"]["joinery"] is False
    assert H.snapshot(walk_setup(2, True)[0])["parameters"]["joinery"] is True


# ---------------------------------------------------------------- SP picks (R-015, R-016)


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R015_sp_picks_in_seat_order_on_free_three_firewood_areas(n, joinery):
    """R-015/R-016/ACTIONS 5.1: PICK_AREA in seat order 0..n-1; legal choices are exactly the
    3-firewood areas without a token; the i-th pick has n-i options; the last pick is forced but
    still an action; after SP each seat has a distinct 3-firewood cutting_area."""
    s = H.play_setup({"players": n, "joinery": joinery}, seed=4, stop_phase="SP")
    three = {i for i, a in enumerate(H.areas(H.snapshot(s))) if a["wood"]["firewood"] == 3}
    assert len(three) == n
    taken = set()
    rng = random.Random(8)
    for seat in range(n):
        assert H.phase_of(s) == "SP"
        assert s.current_player() == seat
        legal = s.legal_actions()
        assert legal == sorted(H.PICK_AREA(a) for a in three - taken)
        assert len(legal) == n - seat
        # nothing else is legal
        for bad in (H.DONE, H.TAKE_LOAN, H.MOVE_TO(1)):
            assert bad not in legal
        for a in set(range(6)) - three:
            assert H.PICK_AREA(a) not in legal
        pick = rng.choice(legal) - 2
        s.apply_action(H.PICK_AREA(pick))
        taken.add(pick)
        if seat < n - 1:
            for a in taken:
                assert H.PICK_AREA(a) not in s.legal_actions()
    assert taken == three
    snap = H.snapshot(s)
    assert [x["cutting_area"] for x in H.seats(snap)] == [
        a + 1 for a in [p for p in _picks_in_order(s, n)]
    ]


def _picks_in_order(s, n):
    return [a - 2 for a in s.history()[-n:]]


def test_R015_sp_example_forced_last_pick_is_recorded():
    """R-015 example: with 3 players P0 and P1 choose, P2 is left with one area; that forced pick
    is still a decision node with a single legal action and is recorded in the history."""
    s = H.play_setup({"players": 3}, seed=1, stop_phase="SP")
    s.apply_action(s.legal_actions()[-1])
    s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 2
    assert len(s.legal_actions()) == 1
    before = len(s.history())
    s.apply_action(s.legal_actions()[0])
    assert len(s.history()) == before + 1


def test_R015_sp_picked_area_leaves_wood_unchanged():
    """R-015: tokens do not remove wood; SP picks leave the cutting-area wood as drawn."""
    s = H.play_setup({"players": 2}, seed=2, stop_phase="SP")
    before = [dict(a["wood"]) for a in H.areas(H.snapshot(s))]
    t = H.play_setup({"players": 2}, seed=2)
    after = [dict(a["wood"]) for a in H.areas(H.snapshot(t))]
    assert before == after


@pytest.mark.parametrize("n", PLAYERS)
def test_R016_seat_zero_starts_and_order_is_seat_order(n):
    """R-016: seat 0 is the starting player; turn order 0..n-1; foremen on location 0."""
    s = H.play_setup({"players": n}, seed=3)
    snap = H.snapshot(s)
    assert snap["turn_order"] == list(range(n))
    assert snap["current_player"] == 0 == s.current_player()
    assert all(x.get("foreman", 0) == 0 for x in H.seats(snap))


# ---------------------------------------------------------------- R-012 / R-018 / R-019 / R-020


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R018_starting_holdings(n, joinery):
    """R-018: $5 (from setup.yaml), no loans, food, fodder, workers hired, equipment, craftwork,
    wood, joiners or buildings; one seat entry per player."""
    hold = _g(_comp().setup, "starting_holdings")
    snap = H.snapshot(H.play_setup({"players": n, "joinery": joinery}, seed=6))
    st = H.seats(snap)
    assert len(st) == n
    for x in st:
        assert x["money"] == _g(hold, "money")
        assert x.get("loans", 0) == _g(hold, "loans")
        assert x.get("food", 0) == 0
        assert not any(x.get("fodder", {}).values())
        assert not any(x.get("equipment", {}).values())
        assert not any(x.get("craftwork", {}).values())
        assert not any(x.get("hired", {}).values())
        assert not x.get("woodpile")
        assert x.get("joiners", 0) == 0
        assert list(x.get("buildings", [])) == []
        assert x.get("foreman", _g(hold, "foreman_location")) == _g(hold, "foreman_location")


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R020_round_one_starts_at_tr_with_seat_zero(n, joinery):
    """R-020/R-012(7): after the SP picks round 1 is in TR, seat 0 acts, nothing is chance, only
    path moves (and loans) are offered: no PICK_AREA and no DONE (R-040: DONE needs an
    acquisition)."""
    s = H.play_setup({"players": n, "joinery": joinery}, seed=7)
    assert not s.is_chance_node() and not s.is_terminal()
    snap = H.snapshot(s)
    assert snap["round"] == 1 and snap["phase"] == "TR"
    assert s.current_player() == 0
    legal = s.legal_actions()
    assert legal
    assert all(H.PICK_AREA(a) not in legal for a in range(6))
    assert H.DONE not in legal
    assert len(s.history()) == len(_expected_sequence(n, joinery)) + n


@pytest.mark.parametrize("n", PLAYERS)
def test_R020_all_cutting_areas_set_after_setup(n):
    """R-020: each seat's cutting area is the one set in R-015; all differ and are 3-wood areas."""
    snap = H.snapshot(H.play_setup({"players": n}, seed=11))
    chosen = [x["cutting_area"] for x in H.seats(snap)]
    assert all(c is not None for c in chosen)
    assert len(set(chosen)) == n
    ar = H.areas(snap)
    assert all(ar[c - 1]["wood"]["firewood"] == 3 for c in chosen)


@pytest.mark.parametrize("n", PLAYERS)
def test_R019_joinery_setup_only_when_joinery_true(n):
    """R-019/R-017: joinery=true: one joiner on the Joiner location, none held by seats,
    buildings supply drawn; joinery=false: no joiner, no buildings."""
    comp = _comp()
    on = H.snapshot(H.play_setup({"players": n, "joinery": True}, seed=2))
    off = H.snapshot(H.play_setup({"players": n, "joinery": False}, seed=2))
    assert on["path"]["joiner"] == 1
    assert off["path"]["joiner"] == 0
    assert len(on["supply"]["buildings"]) == _quantities(n)["buildings_drawn"]
    assert len(set(on["supply"]["buildings"])) == len(on["supply"]["buildings"])
    assert set(on["supply"]["buildings"]) <= {b.id for b in comp.buildings}
    assert list(off["supply"]["buildings"]) == []
    assert all(x.get("joiners", 0) == 0 for x in H.seats(on) + H.seats(off))


# ---------------------------------------------------------------- conservation


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R017_component_conservation_after_setup(n, joinery, seed):
    """R-017/R-008/R-009: after setup the path plus seats hold exactly the setup.yaml totals:
    bearers, woodcutters, sawyers, fodder (path + seats), 13 tokens, craftwork on the path never
    exceeds the pile totals per type, nothing has been removed from the game, cards laid out are
    distinct and within the deck sizes, cutting-area wood totals match R-013."""
    comp = _comp()
    q = _quantities(n)
    snap = H.snapshot(H.play_setup({"players": n, "joinery": joinery}, seed=seed))
    st = H.seats(snap)
    path = snap["path"]
    held = lambda key: sum(x.get("hired", {}).get(key, 0) for x in st)  # noqa: E731
    assert path["bearers"] + held("bearers") == q["bearers_on_path"]
    assert path["woodcutters"] + held("woodcutters") == q["woodcutters_on_path"]
    assert (
        path["sawyers_free"] + path["sawyers_paid"] + held("sawyers")
        == q["sawyers_price_0"] + q["sawyers_price_1"]
    )
    assert path["fodder"] + sum(sum(x["fodder"].values()) for x in st) == q["fodder_on_path"]
    assert path["fodder"] <= _g(_g(comp.setup, "supply"), "fodder")
    vals = list(H.tokens(snap).values())
    assert len(vals) == 13
    totals = _craft_totals()
    for c in CRAFT_ORDER:
        assert vals.count(c) <= totals[c]
    assert not any(snap["supply"].get("craftwork_removed", {}).values())
    fw = sum(a["wood"]["firewood"] for a in H.areas(snap))
    assert fw == 3 * q["cutting_areas_with_3_firewood"] + 2 * q["cutting_areas_with_2_firewood"]
    assert len(set(snap["supply"]["tasks_laid_out"])) == n
    assert len(set(snap["planned_work"]["laid_out"])) == n + 2
    assert sum(1 for x in st if x["cutting_area"] is not None) == n


# ---------------------------------------------------------------- R-031 determinism


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R031_same_seed_same_setup(n, joinery):
    """R-031: parameters + the same chance outcomes + same picks give the identical state,
    string and snapshot; the seeded run is repeatable."""
    a = H.play_setup({"players": n, "joinery": joinery}, seed=21)
    b = H.play_setup({"players": n, "joinery": joinery}, seed=21)
    assert str(a) == str(b)
    assert H.snapshot(a) == H.snapshot(b)
    assert a.history() == b.history()


@pytest.mark.parametrize("n", PLAYERS)
def test_R031_fixed_action_list_reproduces_setup(n):
    """R-031: replaying a recorded setup action list on a fresh game reproduces the same state,
    from a different game object."""
    a = H.play_setup({"players": n}, seed=33)
    b = H.replay({"players": n}, H.setup_history(a))
    assert str(a) == str(b)
    assert H.snapshot(a) == H.snapshot(b)


def test_R031_different_seeds_give_different_setups_and_strings():
    """R-031/CLAUDE.md: distinct setups never print alike (a sample of 6 seeds yields several)."""
    strs = {str(H.play_setup({"players": 3}, seed=sd)) for sd in range(6)}
    assert len(strs) >= 4


@pytest.mark.parametrize("n", PLAYERS)
def test_R031_pick_choice_changes_state(n):
    """R-031: the recorded decisions matter: choosing a different 3-wood area at P0 gives a
    different state (when more than one is available)."""
    s0 = H.play_setup({"players": n}, seed=5, stop_phase="SP")
    legal = s0.legal_actions()
    strs = set()
    for a in legal:
        c = s0.clone()
        c.apply_action(a)
        strs.add(str(c))
    assert len(strs) == len(legal) > 1


@pytest.mark.parametrize("n", PLAYERS)
def test_R031_each_sp_step_changes_the_state_string(n):
    """R-031/CLAUDE.md: each public pick changes the full-information string."""
    s = H.play_setup({"players": n}, seed=5, stop_phase="SP")
    seen = {str(s)}
    for _ in range(n):
        s.apply_action(s.legal_actions()[0])
        assert str(s) not in seen
        seen.add(str(s))


# ---------------------------------------------------------------- observer: setup is public


@pytest.mark.parametrize("n", PLAYERS)
def test_R028_setup_state_and_picks_are_public(n):
    """R-028/R-029: during SC and SP nothing is private: every seat's observation string and
    tensor are identical, and a setup pick is visible to all (the string changes after it)."""
    game = H.load_game(players=n)
    s = game.new_initial_state()
    rng = random.Random(12)

    def same_for_all(st):
        strs = {st.observation_string(p) for p in range(n)}
        tens = {tuple(st.observation_tensor(p)) for p in range(n)}
        assert len(strs) == 1 and len(tens) == 1
        return next(iter(strs))

    while s.is_chance_node():
        same_for_all(s)
        s.apply_action(H.sample_chance(s, rng))
    prev = same_for_all(s)
    for _ in range(n):
        s.apply_action(s.legal_actions()[0])
        cur = same_for_all(s)
        assert cur != prev
        prev = cur


@pytest.mark.parametrize("n", PLAYERS)
def test_R030_state_str_is_observer_string_through_setup(n):
    """R-030: str(state) equals the full-information observer string at every setup node."""
    game = H.load_game(players=n)
    obs = game.make_py_observer(
        pyspiel.IIGObservationType(
            public_info=True, perfect_recall=False, private_info=pyspiel.PrivateInfoType.ALL_PLAYERS
        )
    )
    s = game.new_initial_state()
    rng = random.Random(14)
    while True:
        assert str(s) == obs.string_from(s, 0)
        if s.is_chance_node():
            s.apply_action(H.sample_chance(s, rng))
        elif H.phase_of(s) == "SP":
            s.apply_action(s.legal_actions()[0])
        else:
            break


def test_R032_setup_snapshot_is_side_qualified():
    """R-032: the snapshot names the board side through parameters.joinery, and token keys carry
    the side's printed numbers (13 is a token spot only on the joinery side)."""
    on = H.tokens(H.snapshot(H.play_setup({"joinery": True}, seed=1)))
    off = H.tokens(H.snapshot(H.play_setup({"joinery": False}, seed=1)))
    assert 13 in on and 13 not in off
    assert 12 in off and 12 not in on


# ------------------------------------------------ R-015 example and SP legality enforcement


def test_R015_example_three_players_areas_1_5_6():
    """R-015 example: AREAS3 = {areas 1,5,6} (0-based {0,4,5}, lexicographic rank computed from
    the 3-subsets of range(6)); P0 picks area 5, P1 area 1, P2 is forced to area 6."""
    rank = list(itertools.combinations(range(6), 3)).index((0, 4, 5))
    assert rank == 9
    game = H.load_game(players=3)
    s = game.new_initial_state()
    s.apply_action(H.CHANCE_BASE["AREAS3"] + rank)
    rng = random.Random(0)
    while s.is_chance_node():
        s.apply_action(H.sample_chance(s, rng))
    areas = H.areas(H.snapshot(s))
    assert [a["wood"]["firewood"] for a in areas] == [3, 2, 2, 2, 3, 3]
    assert s.legal_actions() == [H.PICK_AREA(a) for a in (0, 4, 5)]
    s.apply_action(H.PICK_AREA(4))
    s.apply_action(H.PICK_AREA(0))
    assert s.current_player() == 2
    assert s.legal_actions() == [H.PICK_AREA(5)]
    s.apply_action(H.PICK_AREA(5))
    assert [x["cutting_area"] for x in H.seats(H.snapshot(s))] == [5, 1, 6]


def test_R015_sp_rejects_picking_a_two_firewood_area():
    s = H.play_setup({"players": 3}, seed=4, stop_phase="SP")
    low = next(i for i, a in enumerate(H.areas(H.snapshot(s))) if a["wood"]["firewood"] == 2)
    with pytest.raises((ValueError, pyspiel.SpielError)):
        s.apply_action(H.PICK_AREA(low))


def test_R015_sp_rejects_picking_the_same_area_twice():
    s = H.play_setup({"players": 3}, seed=4, stop_phase="SP")
    first = s.legal_actions()[0]
    s.apply_action(first)
    with pytest.raises((ValueError, pyspiel.SpielError)):
        s.apply_action(first)


@pytest.mark.parametrize("bad", [H.DONE, H.TAKE_LOAN, H.MOVE_TO(1)])
def test_R015_sp_rejects_non_pick_area_actions(bad):
    s = H.play_setup({"players": 2}, seed=4, stop_phase="SP")
    with pytest.raises((ValueError, pyspiel.SpielError)):
        s.apply_action(bad)
