"""Phase 2 unit 4: round start (calendar, path and task refill, placement cards, joiners).

Rules: R-033..R-037, R-062, R-063, R-078..R-080, R-020.
Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only. All tests go
through tests/harness.py and the round driver in tests/support/rounds.py (public API only).

Assumptions about the public surface (flagged where the spec is silent):
  * Round-start chance nodes of a seasonal round >= 2 are, in some order, TASK_DRAW (one per
    missing task), CRAFT_DRAW x3, SPOT_TOKEN x13, PLACEMENT_DRAW x (3/2/1); with no plans there is
    no RS decision, so the first decision node of such a round is PK (ACTIONS section 4/5.9).
  * Winter rounds contain no chance node and no PK/TR/W phases.
  * A seat takes the joiner by `MOVE_TO(Joiner)` alone (ACTIONS section 6 / R-078).
  * A placement card adds 1 food to each area of `food_areas` (data comment in cards.yaml).
  * dump_scenario emits `path: None` in winter (SCENARIOS section 4.3).
"""

from collections import Counter

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import winter as V

PLAYERS = (2, 3, 4)
BOOLS = (True, False)
BASE_SPOTS = [1, 2, 3, 5, 7, 9, 11, 12, 14, 15, 17, 18, 20]
JOIN_SPOTS = [1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19, 20, 22]


def _params(n, joinery):
    return {"players": n, "joinery": joinery}


def _seats(snap):
    return H.seats(snap)


def _fills(rnd):
    """Number of path fills done by the start of seasonal round `rnd` (R-035)."""
    return {1: 1, 2: 2, 3: 3, 5: 4, 6: 5, 7: 6}[rnd]


def _craft_in(tokens):
    return Counter(v for v in tokens.values() if v in R.CRAFT)


def _hire_all_p0(joinery):
    """P0 hires 2 bearers, 2 woodcutters and both sawyers in round 1 ($5 in total)."""
    j = joinery
    return [
        R.move(j, "bearers"), R.HIRE_BEARER, R.HIRE_BEARER, H.DONE,
        R.move(j, "woodcutters"), R.HIRE_WOODCUTTER, R.HIRE_WOODCUTTER, H.DONE,
        R.move(j, "sawyers"), R.HIRE_SAWYER, R.HIRE_SAWYER, H.DONE,
        R.MOVE_CLEARING,
    ]  # fmt: skip


# --------------------------------------------------------------------------- R-033


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R033_eight_rounds_in_order_and_game_ends_after_round_8(n, joinery):
    """R-033: rounds 1..8 follow one another, seasonal rounds use only seasonal phases, winter
    rounds (4, 8) only winter phases, and the game is over after round 8."""
    run = R.drive(_params(n, joinery), seed=3)
    rounds = [r for r, _, _ in run.log]
    assert rounds == sorted(rounds)
    assert sorted(set(rounds)) == list(range(1, 9))
    for rnd, phase, _ in run.log:
        if rnd in R.WINTER:
            assert phase in R.WINTER_PHASES, (rnd, phase)
        else:
            assert phase in ("SP",) + R.SEASON_PHASES, (rnd, phase)
    assert run.state.is_terminal()


@pytest.mark.parametrize("n", PLAYERS)
def test_R033_after_round_3_comes_winter_without_path_picks_or_chance(n):
    """R-033 example: after fall year 1 the next round is the year-1 winter. Winter has no supply
    path, no placement cards, no picks and no chance node (R-064, R-062)."""
    run = R.drive(_params(n, False), seed=5)
    ev = run.event(4)
    assert ev.phase not in ("PK", "TR", "RS")
    assert ev.after.get("path") is None
    assert ev.trail == []
    assert not any(ph in ("PK", "TR") for r, ph, _ in run.log if r in R.WINTER)
    ev8 = run.event(8)
    assert ev8.trail == [] and ev8.after.get("path") is None


@pytest.mark.parametrize("n", PLAYERS)
def test_R033_round_5_is_a_seasonal_round_with_placement_cards_and_picks(n):
    """R-033 example: round 5 (spring year 2) draws placement cards and has hidden picks like
    round 2."""
    run = R.drive(_params(n, False), seed=5)
    ev = run.event(5)
    assert ev.phase == "PK"
    fam = Counter(run.families(ev))
    assert fam["PLACEMENT_DRAW"] == R.quantities(n)["placement_cards_per_round"]
    assert ev.after["path"] is not None


# --------------------------------------------------------------------------- R-034


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", (2, 4))
def test_R034_step_order_fill_then_picks_then_travel_then_wood_work(n, joinery):
    """R-034: in each seasonal round >= 2 all round-start chance (steps 2-3) is resolved before
    the first decision, which is the pick (step 4); then travel (5) and wood work (6) in order.
    Round 1 has no pick step."""
    run = R.drive(_params(n, joinery), seed=1)
    for rnd in (2, 3, 5, 6, 7):
        ph = [p for r, p, _ in run.log if r == rnd]
        seq = [p for i, p in enumerate(ph) if i == 0 or ph[i - 1] != p]
        assert seq[0] == "PK", (rnd, seq)
        idx = [R.SEASON_PHASES.index(p) for p in seq]
        assert idx == sorted(idx), (rnd, seq)
        assert "TR" in seq and "W1" in seq
        assert run.families(run.event(rnd))  # chance came first
    ph1 = [p for r, p, _ in run.log if r == 1]
    assert "PK" not in ph1 and ph1[0] == "SP"


# --------------------------------------------------------------------------- R-035


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R035_all_hired_workers_are_back_on_the_path_each_round(n, joinery):
    """R-035/R-061: whatever was hired in the previous round, bearers, woodcutters and sawyers
    (R-013 at $0 plus the $1 one) are all back at round start; hired counts reset."""
    q = R.quantities(n)
    pol = R.Script({(1, 0): _hire_all_p0(joinery)})
    run = R.drive(_params(n, joinery), seed=2, policy=pol, stop=lambda c: c.round == 2)
    assert _seats(run.event(2).before)[0]["money"] == 0  # spent the full $5 in round 1
    after = run.event(2).after
    p = after["path"]
    assert p["bearers"] == q["bearers_on_path"]
    assert p["woodcutters"] == q["woodcutters_on_path"]
    assert p["sawyers_free"] == q["sawyers_price_0"]
    assert p["sawyers_paid"] == q["sawyers_price_1"]
    for s in _seats(after):
        assert R.total(s["hired"]) == 0


@pytest.mark.parametrize("n", PLAYERS)
def test_R035_fodder_topped_up_to_the_laid_out_count(n):
    """R-035: the Fodder location is topped up to the R-013 count; the fodder bought by a seat
    stays with that seat."""
    j = False
    pol = R.Script({(1, 1): [R.move(j, "fodder"), R.BUY_FODDER, R.MOVE_CLEARING]})
    run = R.drive(_params(n, j), seed=4, policy=pol, stop=lambda c: c.round == 2)
    b = run.event(2).before
    assert b["path"]["fodder"] == R.quantities(n)["fodder_on_path"] - 1
    a = run.event(2).after
    assert a["path"]["fodder"] == R.quantities(n)["fodder_on_path"]
    assert _seats(a)[1]["fodder"]["slot3"] is True


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R035_thirteen_fresh_tokens_with_the_right_mix_every_fill(n, joinery):
    """R-035/R-017/R-023: each fill (rounds 2, 3, 5, 6, 7) puts exactly 13 face-up tokens, one per
    token spot of the side: the R-017 equipment mix (X-markers at 2 players) plus the 3 craftwork
    tokens drawn; old tokens are gone (so not 26)."""
    run = R.drive(_params(n, joinery), seed=6)
    spots = JOIN_SPOTS if joinery else BASE_SPOTS
    for rnd in (2, 3, 5, 6, 7):
        ev = run.event(rnd)
        toks = H.tokens(ev.after)
        assert sorted(toks) == spots
        assert all(v is not None for v in toks.values())
        want = Counter(R.token_mix(n))
        crafts = [
            R.CRAFT[H.chance_family(a)[1]]
            for a in ev.trail
            if H.chance_family(a)[0] == "CRAFT_DRAW"
        ]
        want.update(crafts)
        assert Counter(toks.values()) == want, rnd


@pytest.mark.parametrize("n", PLAYERS)
def test_R035_spot_token_outcomes_are_placed_in_spot_order(n):
    """R-035/R-062 + ACTIONS section 2: the 13 SPOT_TOKEN outcomes fill spots 1..13 in spot
    order, so the board shows them in ascending printed-number order."""
    run = R.drive(_params(n, True), seed=8, stop=lambda c: c.round == 3)
    for rnd in (2, 3):
        ev = run.event(rnd)
        ys = [H.chance_family(a)[1] for a in ev.trail if H.chance_family(a)[0] == "SPOT_TOKEN"]
        assert len(ys) == 13
        toks = H.tokens(ev.after)
        assert [toks[k] for k in sorted(toks)] == [R.SPOT_NAMES[y] for y in ys]


@pytest.mark.parametrize("n", (2, 4))
def test_R035_craftwork_pile_of_18_serves_exactly_six_fills(n):
    """R-035: leftover craftwork leaves the game, so path + removed (+ held) = 3 per fill, and the
    18-token pile is exactly used up by the sixth fill (round 7)."""
    run = R.drive(_params(n, False), seed=9)
    for rnd in (2, 3, 5, 6, 7):
        a = run.event(rnd).after
        held = sum(R.total(s["craftwork"]) for s in _seats(a))
        removed = R.total(a["supply"].get("craftwork_removed", {}))
        got = sum(_craft_in(H.tokens(a)).values()) + removed + held
        assert got == 3 * _fills(rnd), rnd
    assert 3 * _fills(7) == sum(R.craft_totals().values())


@pytest.mark.parametrize("n", PLAYERS)
def test_R035_joiner_location_refilled_when_joinery(n):
    """R-035/R-063: with joinery the Joiner location holds 1 joiner each round while the supply
    has one; without joinery it holds none."""
    on = R.drive(_params(n, True), seed=1)
    off = R.drive(_params(n, False), seed=1)
    for rnd in (2, 3, 5, 6, 7):
        assert on.event(rnd).after["path"]["joiner"] == 1
        assert off.event(rnd).after["path"].get("joiner", 0) == 0


def test_R035_joiner_hired_in_a_round_returns_next_round_to_the_path():
    """R-035/R-078: at most one joiner per round, but the location is stocked again next round."""
    pol = R.Script({(1, 0): [R.move(True, "joiner"), R.MOVE_CLEARING]})
    run = R.drive(_params(2, True), seed=1, policy=pol, stop=lambda c: c.round == 2)
    assert run.event(2).before["path"]["joiner"] == 0
    assert run.event(2).after["path"]["joiner"] == 1


# --------------------------------------------------------------------------- R-036


@pytest.mark.parametrize("n", PLAYERS)
def test_R036_task_row_refilled_to_laid_out_count_keeping_unclaimed(n):
    """R-036: the card taken in round 1 belongs to its seat; the row is refilled by drawing exactly
    one card; unclaimed cards stay face up and the new card was not seen before."""
    j = False
    pol = R.Script({(1, 0): [R.move(j, "tasks"), R.first_legal(R.TAKE_TASK0, R.TAKE_TASK_END)]})
    run = R.drive(_params(n, j), seed=2, policy=pol, stop=lambda c: c.round == 2)
    cap = R.quantities(n)["task_cards_laid_out"]
    row1 = set(run.event(1).after["supply"]["tasks_laid_out"])
    ev = run.event(2)
    row2 = ev.after["supply"]["tasks_laid_out"]
    held = [t["id"] for t in _seats(ev.after)[0]["tasks"]]
    assert len(held) == 1 and held[0] in row1
    assert len(row2) == cap and len(set(row2)) == cap
    assert held[0] not in row2
    assert row1 - {held[0]} <= set(row2)
    assert len(set(row2) - row1) == 1
    assert run.families(ev).count("TASK_DRAW") == 1


@pytest.mark.parametrize("n", PLAYERS)
def test_R036_no_draw_when_nothing_was_taken(n):
    """R-036: if nobody takes a task the row is full already: no TASK_DRAW node, same cards."""
    run = R.drive(_params(n, False), seed=2, stop=lambda c: c.round == 3)
    row = set(run.event(1).after["supply"]["tasks_laid_out"])
    for rnd in (2, 3):
        ev = run.event(rnd)
        assert "TASK_DRAW" not in run.families(ev)
        assert set(ev.after["supply"]["tasks_laid_out"]) == row


def _take_tasks(joinery):
    tloc = R.move(joinery, "tasks")

    def pol(ctx):
        if ctx.phase != "TR":
            return None
        take = [a for a in ctx.legal if R.TAKE_TASK0 <= a <= R.TAKE_TASK_END]
        if take:
            return take[0]
        if (
            ctx.snap is not None
            and _seats(ctx.snap)[ctx.player]["money"] >= 1
            and tloc in ctx.legal
        ):
            return tloc
        return None

    return pol


@pytest.mark.parametrize("joinery", BOOLS)
def test_R036_task_deck_runs_out_row_not_replenished(joinery):
    """R-036: with four seats taking a card whenever they can, the 19-card deck eventually cannot
    refill the row: then it stays short and no TASK_DRAW node appears. Before that the row is
    always full, never repeats a card, and a drawn card was never seen before."""
    run = R.drive(_params(4, joinery), seed=11, policy=_take_tasks(joinery))
    cap = R.quantities(4)["task_cards_laid_out"]
    seen = set(run.event(1).after["supply"]["tasks_laid_out"])
    for rnd in (2, 3, 5, 6, 7):
        ev = run.event(rnd)
        row = ev.after["supply"]["tasks_laid_out"]
        held = [t["id"] for s in _seats(ev.after) for t in s["tasks"]]
        assert len(set(row)) == len(row)
        new = set(row) - seen
        assert not (set(row) & set(held))
        seen |= set(row) | set(held)
        assert len(new) == run.families(ev).count("TASK_DRAW")
        assert len(row) == cap or (len(row) < cap and len(seen) == 19), (rnd, len(row), len(seen))


# --------------------------------------------------------------------------- R-037


def _expected_areas(before, ev_trail):
    """R-037: add the drawn cards' wood and food, then 1 firewood on every area without wood."""
    cards = R.placement_cards()
    areas = [{**R.wood(a), "food": R.food(a)} for a in H.areas(before)]
    for a in ev_trail:
        fam, q = H.chance_family(a)
        if fam != "PLACEMENT_DRAW":
            continue
        card = cards[q]
        for num, kinds in card["areas"].items():
            for k in kinds:
                areas[int(num) - 1][k] += 1
        for num in card["food_areas"]:
            areas[int(num) - 1]["food"] += 1
    for a in areas:
        if a["firewood"] + a["softwood"] + a["hardwood"] == 0:
            a["firewood"] += 1
    return areas


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R037_card_count_per_round_and_none_in_round_1_or_winter(n, joinery):
    """R-037/R-013: 3/2/1 placement cards per seasonal round from round 2; none in round 1 or
    winter."""
    run = R.drive(_params(n, joinery), seed=3)
    k = R.quantities(n)["placement_cards_per_round"]
    for rnd in (2, 3, 5, 6, 7):
        assert run.families(run.event(rnd)).count("PLACEMENT_DRAW") == k
    for rnd in (1, 4, 8):
        assert "PLACEMENT_DRAW" not in run.families(run.event(rnd))


@pytest.mark.parametrize("n", PLAYERS)
def test_R037_cards_applied_then_empty_areas_get_one_firewood(n):
    """R-037: areas after the round-start step = before + card wood + card food, and then every
    area holding no wood gets 1 firewood; wood and food carry over between rounds (also winter)."""
    run = R.drive(_params(n, False), seed=12)
    for rnd in (2, 3, 5, 6, 7):
        ev = run.event(rnd)
        exp = _expected_areas(ev.before, ev.trail)
        got = [{**R.wood(a), "food": R.food(a)} for a in H.areas(ev.after)]
        assert got == exp, rnd


def test_R037_cut_empty_areas_extra_firewood_only_where_card_gave_no_wood():
    """R-037(2): with every seat's area cut empty in round 1 (4 players), an emptied area that a
    card gives wood gets no extra firewood, one that gets only food (or nothing) gets 1 firewood.
    Both situations must occur over the seeds tried."""
    j = False
    cut = [R.move(j, "woodcutters")] + [R.HIRE_WOODCUTTER] * 3 + [H.DONE, R.MOVE_CLEARING]
    seen_given, seen_extra = False, False
    for seed in range(20):
        pol = R.chain(R.Script({(1, s): list(cut) for s in range(4)}), R.cut_all_wood)
        run = R.drive(_params(4, j), seed=seed, policy=pol, stop=lambda c: c.round == 2)
        ev = run.event(2)
        assert [R.wood(a) for a in H.areas(ev.before)].count(
            {"firewood": 0, "softwood": 0, "hardwood": 0}
        ) == 4
        exp = _expected_areas(ev.before, ev.trail)
        got = [{**R.wood(a), "food": R.food(a)} for a in H.areas(ev.after)]
        assert got == exp, seed
        cards = R.placement_cards()
        given = set()
        for a in ev.trail:
            if H.chance_family(a)[0] == "PLACEMENT_DRAW":
                given |= {int(k) for k in cards[H.chance_family(a)[1]]["areas"]}
        for i, a in enumerate(H.areas(ev.before)):
            if sum(R.wood(a).values()) == 0:
                seen_given |= (i + 1) in given
                seen_extra |= (i + 1) not in given
    assert seen_given and seen_extra


@pytest.mark.parametrize("n", PLAYERS)
def test_R037_cards_are_discarded_and_never_redrawn(n):
    """R-037: used placement cards are discarded and not reshuffled: the discard pile grows by the
    drawn cards each round and holds distinct cards."""
    run = R.drive(_params(n, False), seed=7)
    k = R.quantities(n)["placement_cards_per_round"]
    ids = [c["id"] for c in R.placement_cards()]
    for i, rnd in enumerate((2, 3, 5, 6, 7), start=1):
        ev = run.event(rnd)
        disc = ev.after["supply"]["placement_discarded"]
        assert len(disc) == len(set(disc)) == k * i
        drawn = {
            ids[H.chance_family(a)[1]]
            for a in ev.trail
            if H.chance_family(a)[0] == "PLACEMENT_DRAW"
        }
        assert drawn <= set(disc)


# --------------------------------------------------------------------------- R-062


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R062_chance_families_of_a_seasonal_round(n, joinery):
    """R-062: a seasonal round >= 2 has only these chance nodes: tasks (0..cap), 3 craftwork draws,
    13 spot tokens, the placement cards; winter and later rounds never draw setup chance."""
    run = R.drive(_params(n, joinery), seed=10)
    cap = R.quantities(n)["task_cards_laid_out"]
    k = R.quantities(n)["placement_cards_per_round"]
    for ev in run.events:
        c = Counter(run.families(ev))
        if ev.round in (2, 3, 5, 6, 7):
            assert set(c) <= {"TASK_DRAW", "CRAFT_DRAW", "SPOT_TOKEN", "PLACEMENT_DRAW"}
            assert c["CRAFT_DRAW"] == 3 and c["SPOT_TOKEN"] == 13 and c["PLACEMENT_DRAW"] == k
            assert 0 <= c["TASK_DRAW"] <= cap
        elif ev.round > 1:
            assert not c


@pytest.mark.parametrize("n", PLAYERS)
def test_R062_placement_draw_is_uniform_over_undrawn_cards(n):
    """R-062/ACTIONS section 2: PLACEMENT_DRAW is uniform over the cards not yet drawn; drawn
    ones are omitted."""
    run = R.drive(_params(n, False), seed=13)
    drawn = set()
    for rnd in (2, 3, 5, 6, 7):
        ev = run.event(rnd)
        for a, outs in zip(ev.trail, ev.outcomes, strict=True):
            if H.chance_family(a)[0] != "PLACEMENT_DRAW":
                continue
            ps = {x: p for x, p in outs.items() if p > 0}
            assert set(ps) == {
                H.CHANCE_BASE["PLACEMENT_DRAW"] + q for q in range(19) if q not in drawn
            }
            assert all(abs(p - 1 / len(ps)) < 1e-9 for p in ps.values())
            drawn.add(H.chance_family(a)[1])


@pytest.mark.parametrize("n", PLAYERS)
def test_R062_spot_token_probabilities_follow_remaining_multiset(n):
    """R-062/ACTIONS section 2: each SPOT_TOKEN draw is proportional to the remaining multiset of
    the 13 tokens (10 equipment + the 3 drawn craftwork)."""
    run = R.drive(_params(n, True), seed=14, stop=lambda c: c.round == 3)
    for rnd in (2, 3):
        ev = run.event(rnd)
        rem = Counter(R.token_mix(n))
        rem.update(
            R.CRAFT[H.chance_family(a)[1]]
            for a in ev.trail
            if H.chance_family(a)[0] == "CRAFT_DRAW"
        )
        for a, outs in zip(ev.trail, ev.outcomes, strict=True):
            fam, y = H.chance_family(a)
            if fam != "SPOT_TOKEN":
                continue
            tot = sum(rem.values())
            want = {H.CHANCE_BASE["SPOT_TOKEN"] + i: rem[nm] / tot
                    for i, nm in enumerate(R.SPOT_NAMES) if rem[nm] > 0}  # fmt: skip
            got = {x: p for x, p in outs.items() if p > 0}
            assert got.keys() == want.keys()
            assert all(abs(got[x] - want[x]) < 1e-9 for x in want)
            rem[R.SPOT_NAMES[y]] -= 1
        assert sum(rem.values()) == 0


@pytest.mark.parametrize("n", (2, 4))
def test_R062_craft_draw_probabilities_follow_remaining_pile(n):
    """R-062/ACTIONS section 2: the first CRAFT_DRAW of a fill is proportional to the craftwork
    pile = totals minus removed (leftovers included) minus held."""
    run = R.drive(_params(n, False), seed=15)
    totals = R.craft_totals()
    for rnd in (2, 3, 5, 6, 7):
        ev = run.event(rnd)
        b = ev.before
        removed = b["supply"].get("craftwork_removed", {})
        left = _craft_in(H.tokens(b)) if b.get("path") else Counter()
        held = Counter()
        for s in _seats(b):
            for k in R.CRAFT:
                held[k] += (s["craftwork"] or {}).get(k, 0)
        pile = {k: totals[k] - removed.get(k, 0) - left[k] - held[k] for k in R.CRAFT}
        first = next(i for i, a in enumerate(ev.trail) if H.chance_family(a)[0] == "CRAFT_DRAW")
        got = {x: p for x, p in ev.outcomes[first].items() if p > 0}
        tot = sum(pile.values())
        want = {
            H.CHANCE_BASE["CRAFT_DRAW"] + i: pile[k] / tot for i, k in enumerate(R.CRAFT) if pile[k]
        }
        assert got.keys() == want.keys(), rnd
        assert all(abs(got[x] - want[x]) < 1e-9 for x in want)


# --------------------------------------------------------------------------- R-063


@pytest.mark.parametrize("n", (2, 3))
def test_R063_joinery_side_has_22_spot_layout_and_base_side_20(n):
    """R-063/R-021/R-022: the token spots after a fill follow the side played."""
    for joinery, spots in ((True, JOIN_SPOTS), (False, BASE_SPOTS)):
        run = R.drive(_params(n, joinery), seed=1, stop=lambda c: c.round == 2)
        assert sorted(H.tokens(run.event(2).after)) == spots


def test_R063_buildings_location_is_not_refilled():
    """R-063/R-106: the building supply is not refilled at round start: a taken building is gone
    for good; the supply keeps the others."""
    pol = R.Script(
        {
            (1, 0): [
                R.move(True, "buildings"),
                R.first_legal(R.CHOOSE_BUILDING0, R.CHOOSE_BUILDING_END),
            ]
        }
    )
    run = R.drive(_params(2, True), seed=3, policy=pol, stop=lambda c: c.round == 3)
    start = run.event(1).after["supply"]["buildings"]
    for rnd in (2, 3):
        a = run.event(rnd).after
        mine = _seats(a)[0]["buildings"]
        assert len(mine) == 1
        assert sorted(a["supply"]["buildings"]) == sorted(set(start) - set(mine))
        assert len(a["supply"]["buildings"]) == len(start) - 1


@pytest.mark.parametrize("n", (2, 4))
def test_R063_no_joiner_buildings_or_income_without_joinery(n):
    """R-063/R-002: joinery=false: no joiners, buildings or income anywhere, chance structure
    otherwise identical (13 tokens, 3 craft draws). Money stays $5 through fall year 1 (nobody
    pays or earns); after winter year 1 it is what feeding and heating leave (R-071..R-073,
    reference model in tests/support/winter.py; no income without joiners, R-079), unchanged in
    rounds 6 and 7 (default play spends nothing)."""
    run = R.drive(_params(n, False), seed=2)
    winter = run.event(4).after
    req = V.requirement(winter, 1)
    for rnd in (2, 3, 5, 6, 7):
        a = run.event(rnd).after
        assert a["supply"].get("buildings", []) == []
        assert all(s["joiners"] == 0 for s in _seats(a))
        for i, s in enumerate(_seats(a)):
            want = 5 if rnd < 4 else V.settle(_seats(winter)[i], req)["money"]
            assert s["money"] == want, (rnd, i)


# --------------------------------------------------------------------------- R-078


def test_R078_entering_joiner_location_takes_the_joiner_free():
    """R-078: entering the Joiner location takes the joiner there for free; the location is
    then empty and no other seat can enter it this round."""
    pol = R.Script({(1, 0): [R.move(True, "joiner")]})
    run = R.drive(
        _params(2, True), seed=1, policy=pol,
        stop=lambda c: c.round == 1 and c.phase == "TR" and c.player == 1,
    )  # fmt: skip
    assert run.stopped
    snap = H.snapshot(run.state)
    s0 = _seats(snap)[0]
    assert s0["joiners"] == 1 and s0["money"] == 5
    assert snap["path"]["joiner"] == 0
    assert R.move(True, "joiner") not in run.state.legal_actions()


def test_R078_joiner_location_enterable_when_stocked():
    """R-078: with the joiner present and the seat below 3 joiners the location is enterable."""
    s = H.play_setup(_params(2, True), seed=1)
    assert R.move(True, "joiner") in s.legal_actions()


def test_R078_seat_with_three_joiners_cannot_enter_though_one_is_available():
    """R-078/R-040: a seat holding 3 joiners cannot enter the Joiner location (at most 3),
    even with a joiner on the path."""
    hire = [R.move(True, "joiner"), R.MOVE_CLEARING]
    pol = R.Script({(r, 0): list(hire) for r in (1, 2, 3)})
    run = R.drive(
        _params(2, True), seed=1, policy=pol,
        stop=lambda c: c.round == 5 and c.phase == "TR" and c.player == 0,
    )  # fmt: skip
    assert run.stopped
    snap = H.snapshot(run.state)
    assert _seats(snap)[0]["joiners"] == 3
    assert snap["path"]["joiner"] == 1
    legal = run.state.legal_actions()
    assert R.move(True, "joiner") not in legal
    assert R.move(True, "bearers") in legal


# --------------------------------------------------------------------------- R-079


def test_R079_income_starts_the_round_after_hiring():
    """R-079: $1 per joiner at the start of each seasonal round; a joiner hired in round 1 pays
    first at the start of round 2 and nothing in round 1; with 2 joiners round 3 pays $2, and the
    joiner hired in round 2 yielded nothing in round 2."""
    pol = R.Script({(r, 0): [R.move(True, "joiner"), R.MOVE_CLEARING] for r in (1, 2)})
    run = R.drive(_params(2, True), seed=1, policy=pol, stop=lambda c: c.round == 3)
    m = [[s["money"] for s in _seats(run.event(r).after)] for r in (2, 3)]
    assert m[0] == [6, 5]
    assert m[1] == [8, 5]
    assert _seats(run.event(2).after)[0]["joiners"] == 1
    assert _seats(run.event(3).after)[0]["joiners"] == 2


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R079_no_income_without_joiners(n, joinery):
    """R-079: seats without joiners get nothing (and with joinery=false there is no income step)."""
    run = R.drive(_params(n, joinery), seed=2)
    for rnd in (2, 3, 5, 6, 7):
        assert all(s["money"] >= 0 for s in _seats(run.event(rnd).after))
    for rnd in (2, 3):
        assert all(s["money"] == 5 for s in _seats(run.event(rnd).after))


def test_R079_winter_pays_no_income():
    """R-079: winter pays no income: a seat owning a joiner has the same money at the start of
    winter as at the end of the preceding fall round."""
    pol = R.Script({(1, 0): [R.move(True, "joiner"), R.MOVE_CLEARING]})
    run = R.drive(_params(2, True), seed=1, policy=pol, stop=lambda c: c.round == 4)
    ev = run.event(4)
    assert [s["money"] for s in _seats(ev.after)] == [s["money"] for s in _seats(ev.before)]
    assert _seats(ev.after)[0]["joiners"] == 1


# --------------------------------------------------------------------------- R-080


def test_R080_joiner_changes_nothing_but_money_and_count_at_round_start():
    """R-080: apart from income (R-079) and the count itself, a joiner changes nothing at round
    start: same chance outcomes, same board, same legal picks, other seats untouched."""
    pol = R.Script({(1, 0): [R.move(True, "joiner"), R.MOVE_CLEARING]})
    a = R.drive(_params(2, True), seed=21, policy=pol, stop=lambda c: c.round == 2)
    b = R.drive(_params(2, True), seed=21, stop=lambda c: c.round == 2)
    sa, sb = a.event(2).after, b.event(2).after
    assert a.event(2).trail == b.event(2).trail
    s0a, s0b = dict(_seats(sa)[0]), dict(_seats(sb)[0])
    assert s0a.pop("money") == s0b.pop("money") + 1
    assert s0a.pop("joiners") == s0b.pop("joiners") + 1
    assert s0a == s0b
    assert _seats(sa)[1] == _seats(sb)[1]
    assert sa["cutting_areas"] == sb["cutting_areas"]
    assert sa["path"] == sb["path"]
    assert a.state.legal_actions() == b.state.legal_actions()


# --------------------------------------------------------------------------- R-020


def _setup_to_tr(n, joinery, seed):
    s = H.play_setup(_params(n, joinery), seed=seed, stop_phase="SP")
    sp = H.snapshot(s)
    while H.phase_of(s) == "SP":
        s.apply_action(s.legal_actions()[0])
    return sp, s


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", PLAYERS)
def test_R020_round_1_board_is_exactly_what_setup_built(n, joinery):
    """R-020: round 1 has no path refill, task refill or placement draw: path, task row and
    cutting areas at the first TR node equal those of setup (n areas with 3 firewood, the rest 2,
    no other wood or food), and the picks changed nothing but the tokens."""
    sp, s = _setup_to_tr(n, joinery, seed=4)
    tr = H.snapshot(s)
    assert tr["round"] == 1 and tr["phase"] == "TR" and s.current_player() == 0
    assert tr["path"] == sp["path"]
    assert tr["supply"]["tasks_laid_out"] == sp["supply"]["tasks_laid_out"]
    assert [R.wood(a) for a in H.areas(tr)] == [R.wood(a) for a in H.areas(sp)]
    firewood = Counter(R.wood(a)["firewood"] for a in H.areas(tr))
    assert firewood == Counter({3: n, 2: 6 - n})
    assert all(
        R.wood(a)["softwood"] == R.wood(a)["hardwood"] == 0 and R.food(a) == 0 for a in H.areas(tr)
    )


@pytest.mark.parametrize("n", PLAYERS)
def test_R020_round_1_has_no_pick_step_and_first_action_is_p0_move(n):
    """R-020: no cutting-area selection in round 1 (no PK node, picks cannot be legal at TR) and
    the first action of the game after setup is P0's supply-path move."""
    run = R.drive(_params(n, False), seed=2, stop=lambda c: c.round == 2)
    r1 = [(p, pl) for r, p, pl in run.log if r == 1]
    assert all(p != "PK" for p, _ in r1)
    first_tr = next((p, pl) for p, pl in r1 if p == "TR")
    assert first_tr == ("TR", 0)
    s = H.play_setup(_params(n, False), seed=2)
    assert all(H.PICK_AREA(a) not in s.legal_actions() for a in range(6))
