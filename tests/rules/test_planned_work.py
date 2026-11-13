"""Phase 4 unit 3: planned work core (R-087, R-088, R-089, R-014, R-026, R-062, R-040, R-041, R-042,
R-033).

Written from docs/RULES_SPEC.md, docs/ACTIONS.md and docs/SCENARIOS.md only, through
tests/harness.py and tests/support/{rounds,travel}.py. There is no scenario loader in the harness,
so every state is reached by scripted play: `build()` plays setup choosing the PW_DRAW outcomes, and
`run_to()` plays whole rounds with per-(round, seat) travel scripts, the clearing as default and
DONE (else the first legal action) everywhere else.

Scope: making a plan (PLAN_WORK 67..96), cost, target round and wrap-around, which cards are
available, one plan per round, pairs, duplicates, visibility, and that plans persist. NOT tested
here: what each card does (units 4-8). R-089's "executed" has no observable beyond the plan
staying recorded and nothing being forced on the seat; see the report.

Conventions
  * PW card index c = order in data/components/planned_work.yaml (PLAN_WORK(c, pair) = 67 + 3c +
    pair - 1; PW_DRAW(c) = 47 + c). The yaml is read for ids and printed seasons only.
  * A plan in the dump is {seat, card, pair, target}; one token lies on the card per plan, so the
    cost is $1 per plan already made on the card (R-088 item 4 and its Sawing example).
  * Round numbers are R-033's: 1..3 spring..fall y1, 4 winter y1, 5..7, 8 winter y2.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from tests import harness as H
from tests.support import rounds as R
from tests.support import travel as T

PW_LOC = 8
PW_DRAW0 = 47
PLAN0 = 67
BOOLS = (False, True)

_DATA = R._yaml("planned_work.yaml")["planned_work"]  # pyright: ignore[reportPrivateUsage]
IDS: list[str] = [c["id"] for c in _DATA]
SEASONS: dict[int, list[str]] = {i: list(c["seasons"]) for i, c in enumerate(_DATA)}
WINTER_OK = {i for i, s in SEASONS.items() if "winter" in s}

TRADE, CRAFT, SAW, FOODS, HEAT, HUT, DRY, OT, LOG, CUT = range(10)
# Winter-capable cards are Sawing, Heating Supply and Overtime (data; R-088 item 3).
L3 = [TRADE, SAW, HEAT, DRY, CUT]  # 3 players: 5 cards laid out (R-014)
L4 = [SAW, HEAT, TRADE, DRY, LOG, CUT]  # 4 players: 6 cards
L2_NO_WINTER = [TRADE, CRAFT, DRY, CUT]  # 2 players: 4 cards, none printed for winter
L2_WINTER = [TRADE, SAW, DRY, CUT]
# Four seats, Sawing the only winter-capable card laid out (for the cost-gate tests below).
L4_SAW_ONLY = [SAW, TRADE, DRY, CUT, LOG, CRAFT]
# Keep the fixtures tied to the yaml: these layouts mean what their names say.
assert not set(L2_NO_WINTER) & WINTER_OK
assert set(L2_WINTER) & WINTER_OK
assert set(L4_SAW_ONLY) & WINTER_OK == {SAW}


def PLAN(c: int, pair: int) -> int:
    return PLAN0 + 3 * c + (pair - 1)


def plan_ids(legal: list[int]) -> list[int]:
    return [a for a in legal if PLAN0 <= a < PLAN0 + 30]


def build(n: int, cards: list[int] | None, joinery: bool = False, seed: int = 1) -> Any:
    """Play setup choosing the PW_DRAW outcomes `cards` in order (random if None); stop at the
    first travel node of round 1."""
    game: Any = H.as_game({"players": n, "joinery": joinery})
    s: Any = game.new_initial_state()
    rng = random.Random(seed)
    want = None if cards is None else [PW_DRAW0 + c for c in cards]
    while not s.is_terminal():
        if s.is_chance_node():
            outs = [a for a, p in s.chance_outcomes() if p > 0]
            if want and all(PW_DRAW0 <= a < PW_DRAW0 + 10 for a in outs):
                a = want.pop(0)
                assert a in outs
                s.apply_action(a)
            else:
                s.apply_action(H.sample_chance(s, rng))
            continue
        ph = R.try_snapshot(s)
        if ph is None or ph["phase"] != "SP" and ph["phase"] != "PK":
            break
        s.apply_action(s.legal_actions()[0])
    assert not want
    assert H.phase_of(s) == "TR"
    return s


Scripts = dict[tuple[int, int], list[int]]


def run_to(
    s: Any,
    rnd: int,
    scripts: Scripts | None = None,
    seed: int = 3,
    chance_log: list[int] | None = None,
) -> Any:
    """Play on until the first travel node of round `rnd` (all foremen on 0). `scripts` maps
    (round, seat) to the travel actions that seat plays in that round before going to the
    clearing; everything outside travel takes DONE when legal, else the first legal action."""
    q: Scripts = {k: list(v) for k, v in (scripts or {}).items()}
    rng = random.Random(seed)
    cur = 1
    for _ in range(40000):
        assert not s.is_terminal()
        if s.is_chance_node():
            a = H.sample_chance(s, rng)
            if chance_log is not None:
                chance_log.append(a)
            s.apply_action(a)
            continue
        sn = R.try_snapshot(s)
        legal = s.legal_actions()
        if sn is not None:
            cur = sn["round"]
            if sn["phase"] == "TR" and cur == rnd and all(x["foreman"] == 0 for x in H.seats(sn)):
                return s
        script = q.get((cur, s.current_player()))
        if script and script[0] in legal:
            a = script.pop(0)
        elif sn is not None and sn["phase"] == "TR" or R.MOVE_CLEARING in legal:
            a = R.MOVE_CLEARING
        else:
            a = H.DONE if H.DONE in legal else legal[0]
        assert a in legal, f"scripted/default action {a} illegal in round {cur}: {legal}"
        s.apply_action(a)
    raise AssertionError("run_to: step limit")


def plans(s: Any) -> list[dict[str, Any]]:
    return list(T.snap(s)["planned_work"]["plans"])


def laid_out(s: Any) -> list[str]:
    return list(T.snap(s)["planned_work"]["laid_out"])


def money(s: Any, i: int) -> int:
    return T.seat_of(T.snap(s), i)["money"]


def enter(s: Any) -> Any:
    return T.play(s, H.MOVE_TO(PW_LOC))


def plan_now(s: Any, c: int, pair: int) -> Any:
    """MOVE_TO(PW) + PLAN_WORK; the visit closes by itself (ACTIONS 1.4)."""
    return T.play(s, H.MOVE_TO(PW_LOC), PLAN(c, pair))


def rec(seat: int, c: int, pair: int, made: int) -> dict[str, Any]:
    return {"seat": seat, "card": IDS[c], "pair": pair, "target": made + pair}


# --------------------------------------------------------------------------- R-014 / R-026 / R-062


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", (2, 3, 4))
def test_R014_players_plus_two_distinct_pw_cards_laid_out(n, joinery):
    """R-014/R-087: players + 2 distinct PW cards are laid out beside the PW location."""
    s = build(n, None, joinery)
    lo = laid_out(s)
    assert len(lo) == n + 2 == len(set(lo))
    assert set(lo) <= set(IDS)


@pytest.mark.parametrize("n", (2, 3, 4))
def test_R026_pw_draw_nodes_offer_only_undrawn_cards_uniformly(n):
    """R-026(2)/ACTIONS 2: setup has players + 2 PW_DRAW chance nodes, each uniform over the cards
    not yet drawn (outcome ids 47..56)."""
    game: Any = H.as_game({"players": n, "joinery": False})
    s: Any = game.new_initial_state()
    rng = random.Random(0)
    drawn: list[int] = []
    while s.is_chance_node():
        outs = s.chance_outcomes()
        if all(PW_DRAW0 <= a < PW_DRAW0 + 10 for a, _ in outs):
            ids = sorted(a for a, _ in outs)
            assert ids == [PW_DRAW0 + c for c in range(10) if PW_DRAW0 + c not in drawn]
            assert all(abs(p - 1 / len(ids)) < 1e-9 for _, p in outs)
            a = H.sample_chance(s, rng)
            drawn.append(a)
            s.apply_action(a)
        else:
            s.apply_action(H.sample_chance(s, rng))
    assert len(drawn) == n + 2
    assert [IDS[a - PW_DRAW0] for a in drawn] and set(laid_out_from_snapshot(s)) == {
        IDS[a - PW_DRAW0] for a in drawn
    }


def laid_out_from_snapshot(s: Any) -> list[str]:
    return list(T.snap(s)["planned_work"]["laid_out"])


def test_R014_chosen_pw_draws_are_the_laid_out_cards():
    """R-014/R-026: the cards drawn by the PW_DRAW outcomes are exactly the laid-out cards."""
    s = build(4, L4)
    assert set(laid_out(s)) == {IDS[c] for c in L4}


def test_R062_no_pw_draw_after_setup_and_layout_is_fixed():
    """R-062/R-087: seasonal rounds have no PW chance node (task, path-token and placement draws
    only) and the PW layout does not change or refill all game."""
    s = build(3, L3)
    before = laid_out(s)
    log: list[int] = []
    run_to(s, 6, chance_log=log)
    assert log
    assert not [
        a for a in log if PW_DRAW0 <= a < PW_DRAW0 + 10 and H.chance_family(a)[0] == "PW_DRAW"
    ]
    assert laid_out(s) == before


# --------------------------------------------------------------------------- R-040/041/042 location


@pytest.mark.parametrize("joinery", BOOLS)
@pytest.mark.parametrize("n", (2, 3, 4))
def test_R040_planned_work_is_a_legal_destination_in_round_1(n, joinery):
    """R-040 item 4/R-088: in round 1 a seat with $5, unused pairs and a free laid-out card
    that may be planned for summer can enter Planned work (location 8 on both sides)."""
    s = T.start(n, joinery)
    assert H.MOVE_TO(PW_LOC) in s.legal_actions()


# Buildings placeholder test superseded by tests/rules/test_buildings_acquisition.py (R-106).


def test_R088_entering_pw_offers_only_plans_on_laid_out_cards_and_no_done():
    """R-088 items 1-3: right after entering, PLAN_WORK is legal for pair 1 and 2 on every laid-out
    card (summer and fall printed on all of them), pair 3 (target winter) only on winter-capable
    cards, never on a card that is not laid out; DONE and moves are not legal (no empty visit)."""
    s = build(3, L3)
    enter(s)
    legal = s.legal_actions()
    want = set()
    for c in L3:
        want |= {PLAN(c, 1), PLAN(c, 2)}
        if c in WINTER_OK:
            want.add(PLAN(c, 3))
    assert set(plan_ids(legal)) == want
    assert H.DONE not in legal
    assert not T.at_move_node(s)


def test_R042_a_plan_is_one_acquisition_and_the_visit_ends_automatically():
    """R-042/ACTIONS 1.4: PLAN_WORK ends the visit (single acquisition); the next seat is to move
    and the plan is recorded as {seat, card, pair, target} with seat 0 standing on location 8."""
    s = build(3, L3)
    plan_now(s, SAW, 1)
    assert s.current_player() == 1
    assert plans(s) == [rec(0, SAW, 1, 1)]
    assert T.seat_of(T.snap(s), 0)["foreman"] == PW_LOC


def test_R040_planned_work_holds_four_foremen():
    """R-021/R-040 item 3: Planned work has capacity 4, so in a 4-player game all four seats may
    enter it in the same round, each making one plan."""
    s = build(4, L4)
    for seat in range(4):
        assert s.current_player() == seat
        assert H.MOVE_TO(PW_LOC) in s.legal_actions()
        plan_now(s, [SAW, HEAT, TRADE, DRY][seat], 1)
    assert [p["seat"] for p in plans(s)] == [0, 1, 2, 3]


def test_R088_one_plan_per_round_the_foreman_cannot_return():
    """R-088 (Base p.7 'only plan one PW per round')/R-040 item 1: after planning, the seat's next
    travel node in the same round offers no PLAN_WORK and no move to location 8."""
    s = build(3, L3)
    plan_now(s, SAW, 1)
    T.goto_clearing(s)
    T.goto_clearing(s)
    assert s.current_player() == 0
    legal = s.legal_actions()
    assert not plan_ids(legal)
    assert H.MOVE_TO(PW_LOC) not in legal


def test_R087_three_pairs_means_at_most_three_plans_in_the_game():
    """R-087/R-040: P0 plans in rounds 1, 2, 3 with pairs 1, 2, 3 (distinct cards); in round 5 it
    has no unused pair so Planned work is not enterable for it while P1 can still enter."""
    s = build(3, L3)
    scripts: Scripts = {
        (1, 0): [H.MOVE_TO(PW_LOC), PLAN(TRADE, 1)],
        (2, 0): [H.MOVE_TO(PW_LOC), PLAN(SAW, 2)],
        (3, 0): [H.MOVE_TO(PW_LOC), PLAN(DRY, 3)],
    }
    run_to(s, 5, scripts)
    mine = [p for p in plans(s) if p["seat"] == 0]
    assert sorted(p["pair"] for p in mine) == [1, 2, 3]
    assert len(mine) == 3
    t = T.snap(s)
    order = t["turn_order"]
    seen = {}
    for _ in order:
        me = s.current_player()
        seen[me] = H.MOVE_TO(PW_LOC) in s.legal_actions()
        T.goto_clearing(s)
    assert seen[0] is False
    assert seen[1] is True and seen[2] is True


# --------------------------------------------------------------------------- R-088 target round


@pytest.mark.parametrize("pair", (1, 2, 3))
def test_R088_target_round_is_current_round_plus_pair_number(pair):
    """R-088 item 2: planned in round 1, pair n targets round 1 + n (2 summer, 3 fall, 4 winter y1;
    the winter target uses a winter-capable card). The plan record carries seat, card, pair and
    target."""
    s = build(3, L3)
    plan_now(s, SAW, pair)
    assert plans(s) == [rec(0, SAW, pair, 1)]


def test_R088_winter_target_only_for_cards_printed_for_winter():
    """R-088 item 3 ('Not all PW may be planned for the winter round'): in round 1 pair 3 targets
    winter y1; PLAN_WORK(c, 3) is legal exactly for the laid-out cards whose printed seasons include
    winter (data), and for the others the pair-1 and pair-2 plans stay legal."""
    s = build(4, L4)
    enter(s)
    legal = set(s.legal_actions())
    for c in L4:
        assert (PLAN(c, 3) in legal) == (c in WINTER_OK), IDS[c]
        assert PLAN(c, 1) in legal and PLAN(c, 2) in legal


def test_R088_plan_for_a_card_that_is_not_laid_out_is_illegal():
    """R-087/R-088 item 1: only laid-out cards can be planned: every PLAN_WORK id of a card outside
    the layout is illegal at the PW location."""
    s = build(3, L3)
    enter(s)
    legal = set(s.legal_actions())
    for c in range(10):
        if c not in L3:
            assert not {PLAN(c, p) for p in (1, 2, 3)} & legal, IDS[c]


def test_R088_round_3_wraps_into_year_2():
    """R-088 item 2 (worked example): in round 3 (fall y1) pair 1 targets round 4 (winter y1),
    pair 2 targets round 5 (spring y2), pair 3 targets round 6 (summer y2); only the winter target
    needs a winter-capable card."""
    s = build(3, L3)
    run_to(s, 3)
    enter(s)
    legal = set(s.legal_actions())
    for c in L3:
        assert (PLAN(c, 1) in legal) == (c in WINTER_OK)
        assert PLAN(c, 2) in legal and PLAN(c, 3) in legal
    T.play(s, PLAN(TRADE, 2))
    assert plans(s) == [rec(0, TRADE, 2, 3)]
    assert plans(s)[0]["target"] == 5


def test_R088_round_3_pair_3_targets_round_6():
    """R-088 item 2: from round 3, pair 3 lands in round 6."""
    s = build(3, L3)
    run_to(s, 3)
    plan_now(s, DRY, 3)
    assert plans(s)[0]["target"] == 6


def test_R088_round_5_pair_3_reaches_winter_y2_only_with_winter_cards():
    """R-088 items 2-3: in round 5 pair 3 targets round 8 (winter y2): legal only for
    winter-capable cards; pairs 1 and 2 (rounds 6, 7) are legal for every card."""
    s = build(3, L3)
    run_to(s, 5)
    enter(s)
    legal = set(s.legal_actions())
    for c in L3:
        assert (PLAN(c, 3) in legal) == (c in WINTER_OK)
        assert PLAN(c, 1) in legal and PLAN(c, 2) in legal
    seat = s.current_player()
    T.play(s, PLAN(SAW, 3))
    assert plans(s) == [rec(seat, SAW, 3, 5)]


def test_R088_round_6_pair_3_would_land_after_round_8_and_is_illegal():
    """R-088 item 2/D20: in round 6 pair 3 would target round 9, so no PLAN_WORK with pair 3 is
    legal for any card; pair 2 (round 8, winter) needs a winter card; pair 1 (round 7) any."""
    s = build(3, L3)
    run_to(s, 6)
    enter(s)
    legal = set(s.legal_actions())
    for c in L3:
        assert PLAN(c, 3) not in legal
        assert (PLAN(c, 2) in legal) == (c in WINTER_OK)
        assert PLAN(c, 1) in legal


def test_R088_round_7_only_pair_1_to_winter_y2_is_possible():
    """R-088 items 2-3: in round 7 pair 2 and 3 overshoot round 8 (illegal); pair 1 targets winter
    y2 and is legal only on winter-capable cards."""
    s = build(2, L2_WINTER)
    run_to(s, 7)
    enter(s)
    legal = set(s.legal_actions())
    assert plan_ids(list(legal)) == [PLAN(SAW, 1)]


def test_R040_pw_not_enterable_when_no_card_can_be_planned_for_the_target():
    """R-040 item 4/R-088 'activation': in round 7 with no winter-printed card laid out, no pair
    reaches a printed season, so Planned work cannot be entered even with money and unused pairs;
    the clearing is. With a winter-capable card laid out it can be entered."""
    s = build(2, L2_NO_WINTER)
    run_to(s, 7)
    legal = s.legal_actions()
    assert H.MOVE_TO(PW_LOC) not in legal
    assert R.MOVE_CLEARING in legal
    s2 = build(2, L2_WINTER)
    run_to(s2, 7)
    assert H.MOVE_TO(PW_LOC) in s2.legal_actions()


# --------------------------------------------------------------------------- R-088 cost


def test_R088_plan_on_an_untouched_card_is_free():
    """R-088 item 4: a plan on a card nobody has planned costs $0."""
    s = build(3, L3)
    plan_now(s, SAW, 1)
    assert money(s, 0) == 5


def test_R088_cost_is_one_dollar_per_plan_already_on_the_card():
    """R-088 item 4: with four seats planning the same card in turn the prices are $0, $1, $2, $3
    (money 5, 4, 3, 2): each earlier plan left one token on the card; the seat's own new token does
    not count."""
    s = build(4, L4)
    for seat in range(4):
        plan_now(s, SAW, 1)
        assert money(s, seat) == 5 - seat
    assert len(plans(s)) == 4


def test_R088_cost_goes_to_the_bank_and_other_cards_stay_free():
    """R-088 item 4: only the chosen card's tokens count; a plan on a different card costs $0
    even after another card has tokens."""
    s = build(3, L3)
    plan_now(s, SAW, 1)
    plan_now(s, HEAT, 1)
    assert money(s, 1) == 5


def test_R088_own_earlier_tokens_on_the_card_are_paid_for_too():
    """R-088 item 4 (FAQ Official: 'even if you placed it there yourself'): P0 plans Sawing in
    round 1 (pair 1) and again in round 2 (pair 2): the second costs $1."""
    s = build(3, L3)
    scripts: Scripts = {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(SAW, 1)]}
    run_to(s, 2, scripts)
    assert money(s, 0) == 5
    while s.current_player() != 0:
        T.goto_clearing(s)
    plan_now(s, SAW, 2)
    assert money(s, 0) == 4
    assert [p["pair"] for p in plans(s) if p["seat"] == 0] == [1, 2]


def test_R088_tokens_of_plans_whose_target_has_passed_still_count():
    """R-087/R-088 item 4: tokens are never removed. P0 plans Trade in round 1 for round 2; in
    round 3, after the target round, P1 planning Trade still pays $1."""
    s = build(3, L3)
    run_to(s, 3, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(TRADE, 1)]})
    assert plans(s) == [rec(0, TRADE, 1, 1)]
    while s.current_player() != 1:
        T.goto_clearing(s)
    before = money(s, 1)
    plan_now(s, TRADE, 2)
    assert money(s, 1) == before - 1


def test_R088_unaffordable_plan_needs_a_loan_first():
    """R-088 item 4/R-040 item 4/ACTIONS 1.8: four seats plan Sawing in round 1 (prices 0..3) and
    again in round 2 (4, 5, 6, 7). The third seat in round 2's order has at most $5 for a $6
    plan: it can enter Planned work (a loan counts) but PLAN_WORK is illegal until TAKE_LOAN is
    played, then it pays $6 from money + $4."""
    s = build(4, L4)
    run_to(s, 2, {(1, k): [H.MOVE_TO(PW_LOC), PLAN(SAW, 1)] for k in range(4)})
    assert len(plans(s)) == 4
    for _ in range(2):  # first two seats pay $4 and $5 (loan if short)
        seat = s.current_player()
        enter(s)
        if PLAN(SAW, 2) not in s.legal_actions():
            T.play(s, H.TAKE_LOAN)
        T.play(s, PLAN(SAW, 2))
        assert seat in {p["seat"] for p in plans(s)}
    seat = s.current_player()
    m0 = money(s, seat)
    loans0 = T.seat_of(T.snap(s), seat)["loans"]
    assert m0 <= 5 and loans0 <= 1
    assert H.MOVE_TO(PW_LOC) in s.legal_actions()
    enter(s)
    assert PLAN(SAW, 2) not in s.legal_actions()
    T.play(s, H.TAKE_LOAN)
    assert PLAN(SAW, 2) in s.legal_actions()
    T.play(s, PLAN(SAW, 2))
    me = T.seat_of(T.snap(s), seat)
    assert me["money"] == m0 + 4 - 6
    assert me["loans"] == loans0 + 1


# ------------------------------------------------------------------- R-087 pairs, duplicates


def test_R087_a_used_pair_is_never_reusable():
    """R-087: P0 plans with pair 1 in round 1; in round 2 no PLAN_WORK with pair 1 is legal for
    P0 on any card, while pairs 2 and 3 are."""
    s = build(3, L3)
    run_to(s, 2, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(TRADE, 1)]})
    while s.current_player() != 0:
        T.goto_clearing(s)
    enter(s)
    legal = set(s.legal_actions())
    assert not {PLAN(c, 1) for c in L3} & legal
    assert PLAN(SAW, 2) in legal and PLAN(DRY, 3) in legal


def test_R087_same_card_with_a_different_pair_and_target_is_allowed():
    """R-087: a seat may plan the same card more than once with different pairs. Sawing for
    round 2 (pair 1, round 1) and for round 4 (pair 2, round 2) are both legal and recorded."""
    s = build(3, L3)
    run_to(s, 2, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(SAW, 1)]})
    while s.current_player() != 0:
        T.goto_clearing(s)
    enter(s)
    assert PLAN(SAW, 2) in s.legal_actions()
    T.play(s, PLAN(SAW, 2))
    assert [(p["card"], p["target"]) for p in plans(s) if p["seat"] == 0] == [
        (IDS[SAW], 2),
        (IDS[SAW], 4),
    ]


def test_R087_same_card_for_the_same_target_twice_is_illegal():
    """R-087/R-088 item 3 (user answer 2026-11-04): P0 plans Sawing for round 4 with pair 3 in
    round 1; in round 2 Sawing with pair 2 would again target round 4 and is illegal, even though
    pair 2 is unused. Heating Supply with pair 2 (same target, different card) is legal, and
    Sawing with a pair that gives another target stays legal."""
    s = build(3, L3)
    run_to(s, 2, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(SAW, 3)]})
    while s.current_player() != 0:
        T.goto_clearing(s)
    enter(s)
    legal = set(s.legal_actions())
    assert PLAN(SAW, 2) not in legal  # round 2 + 2 = 4: duplicate
    assert PLAN(HEAT, 2) in legal
    assert PLAN(SAW, 1) in legal  # round 3: different target


def test_R087_two_plans_on_one_season_with_different_cards_are_both_kept():
    """R-087 (O-U4-2): a seat may hold two plans landing on the same target season if the cards
    differ. P0 plans Sawing (pair 3, round 1) and Heating Supply (pair 2, round 2), both targeting
    winter y1 (round 4); both records exist."""
    s = build(3, L3)
    run_to(s, 2, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(SAW, 3)]})
    while s.current_player() != 0:
        T.goto_clearing(s)
    plan_now(s, HEAT, 2)
    got = [(p["card"], p["target"]) for p in plans(s) if p["seat"] == 0]
    assert sorted(got) == sorted([(IDS[SAW], 4), (IDS[HEAT], 4)])


def test_R087_other_seats_may_plan_the_same_card_for_the_same_round():
    """R-087: several seats may plan the same card, including for the same target round (the
    duplicate ban is per seat)."""
    s = build(3, L3)
    plan_now(s, SAW, 3)
    enter(s)
    assert PLAN(SAW, 3) in s.legal_actions()
    T.play(s, PLAN(SAW, 3))
    assert [(p["seat"], p["target"]) for p in plans(s)] == [(0, 4), (1, 4)]
    assert money(s, 1) == 4


def test_R087_plans_are_public_to_every_seat():
    """R-087/R-028: plans are public. Two games differ only in which card P0 plans (both free, same
    pair): every other seat's observation differs, so the placement is visible to them."""
    a = build(3, L3)
    b = build(3, L3)
    plan_now(a, SAW, 1)
    plan_now(b, HEAT, 1)
    for seat in (1, 2):
        assert a.observation_string(seat) != b.observation_string(seat)
    assert plans(a) == [rec(0, SAW, 1, 1)]


# --------------------------------------------------------------------------- R-089 and effects


def test_R089_plan_tokens_stay_after_the_target_round_has_passed():
    """R-089/R-087: a plan is used (or lost) only in its target round and its tokens stay: P0's
    Trade plan for round 2 is unchanged in round 3."""
    s = build(3, L3)
    run_to(s, 3, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(TRADE, 1)]})
    assert plans(s) == [rec(0, TRADE, 1, 1)]


def test_R089_unusable_plan_is_lost_without_forcing_a_decision_or_refund():
    """R-089: a plan whose preparations are missing is lost: Trade with no equipment to sell. The
    game proceeds through the target round with only default play, and money at round 3 equals a
    game where P0 never planned (a free plan, no refund, no income)."""
    a = build(3, L3, seed=5)
    b = build(3, L3, seed=5)
    run_to(a, 3, {(1, 0): [H.MOVE_TO(PW_LOC), PLAN(TRADE, 1)]}, seed=9)
    run_to(b, 3, seed=9)
    assert [money(a, i) for i in range(3)] == [money(b, i) for i in range(3)]
    assert len(plans(a)) == 1 and not plans(b)


def test_R089_planning_does_not_apply_the_card_effect():
    """R-089/R-090..R-099 (effects belong to later units): making a plan only places tokens and
    pays the cost. For every card, planning it with pair 1 leaves the planner's other holdings and
    every other seat unchanged (only the foreman moves; the first plan is free)."""
    for c in L4:
        s = build(4, L4)
        before = T.snap(s)
        plan_now(s, c, 1)
        after = T.snap(s)
        for i in range(4):
            x = dict(T.seat_of(before, i))
            y = dict(T.seat_of(after, i))
            x.pop("foreman")
            y.pop("foreman")
            assert x == y, f"{IDS[c]} changed seat {i}"
        assert after["cutting_areas"] == before["cutting_areas"], IDS[c]
        assert after["path"]["tokens"] == before["path"]["tokens"], IDS[c]


def test_R033_target_rounds_are_counted_with_winter_as_one_round():
    """R-033/R-088: winter y1 is round 4, so planned in round 3 (fall) pair 1 targets round 4 and
    planned in round 5 (spring y2) pair 3 targets round 8; no pair skips a winter."""
    s = build(3, L3)
    run_to(s, 3)
    plan_now(s, SAW, 1)
    assert plans(s)[0]["target"] == 4
    run_to(s, 5)
    while s.current_player() != 0:
        T.goto_clearing(s)
    plan_now(s, HEAT, 3)
    assert [p["target"] for p in plans(s)] == [4, 8]


# ------------------------------------------- R-088 / R-040 item 4: entry needs a payable plan
#
# Setup shared by the tests below (4 seats, Sawing the only winter-capable card laid out). In round
# 1 every seat plans Sawing with pair 2 (prices $0..$3), and in round 2 pair 3 is used up the
# same way (Sawing, or a free Trade plan for one seat). In round 3 every seat has only pair 1
# left, which targets winter (round 4), so the only plannable card is Sawing, priced at $1 per
# token on it.


def saw_tokens(s: Any) -> int:
    return sum(1 for p in plans(s) if p["card"] == IDS[SAW])


def pay_plan(s: Any, c: int, pair: int) -> None:
    """Enter Planned work, take loans until the plan is legal, and make it."""
    enter(s)
    while PLAN(c, pair) not in s.legal_actions():
        T.play(s, H.TAKE_LOAN)
    T.play(s, PLAN(c, pair))


def round3_gate(free_seat_in_round_2: bool) -> tuple[Any, int]:
    """Return (state at the first round-3 travel node, the seat that planned free Trade in round 2
    or -1)."""
    s = build(4, L4_SAW_ONLY)
    run_to(s, 2, {(1, k): [H.MOVE_TO(PW_LOC), PLAN(SAW, 2)] for k in range(4)})
    free = s.current_player() if free_seat_in_round_2 else -1
    for _ in range(4):
        if s.current_player() == free:
            pay_plan(s, TRADE, 3)
        else:
            pay_plan(s, SAW, 3)
    run_to(s, 3)
    return s, free


def goto_seat(s: Any, seat: int) -> None:
    while s.current_player() != seat:
        T.goto_clearing(s)


def purse(s: Any, seat: int) -> tuple[int, int]:
    x = T.seat_of(T.snap(s), seat)
    return x["money"], x["loans"]


def test_R040_pw_entry_counts_one_remaining_loan():
    """R-040 item 4/R-088 final paragraph/R-076: P0 in round 3 has $3 and one loan left; Sawing
    (the only plannable card) costs $7 (seven tokens on it). $3 < $7 <= $3 + $4, so Planned work is
    enterable; after entering PLAN_WORK is illegal and the only way forward is TAKE_LOAN, after
    which the plan is legal and costs $7."""
    s, _ = round3_gate(True)
    assert saw_tokens(s) == 7
    goto_seat(s, 0)
    assert purse(s, 0) == (3, 1)
    assert H.MOVE_TO(PW_LOC) in s.legal_actions()
    enter(s)
    legal = s.legal_actions()
    assert not plan_ids(legal)
    assert H.TAKE_LOAN in legal
    assert H.DONE not in legal
    T.play(s, H.TAKE_LOAN)
    assert plan_ids(s.legal_actions()) == [PLAN(SAW, 1)]
    T.play(s, PLAN(SAW, 1))
    assert purse(s, 0) == (3 + 4 - 7, 2)
    assert plans(s)[-1] == rec(0, SAW, 1, 3)


def test_R040_pw_entry_counts_both_remaining_loans():
    """R-040 item 4/R-075/R-076: P3 in round 3 has $2 and no loan; Sawing costs $7.
    $2 + $4 = $6 < $7 but $2 + $8 = $10 >= $7, so Planned work is enterable only if BOTH loans
    count. After entering, one loan is not enough (PLAN_WORK still illegal), the second makes it
    legal; money ends at $2 + 8 - 7 = $3 with two loans."""
    s, free = round3_gate(True)
    assert free == 3 and saw_tokens(s) == 7
    goto_seat(s, 3)
    assert purse(s, 3) == (2, 0)
    assert H.MOVE_TO(PW_LOC) in s.legal_actions()
    enter(s)
    assert not plan_ids(s.legal_actions())
    T.play(s, H.TAKE_LOAN)
    assert not plan_ids(s.legal_actions())
    assert H.TAKE_LOAN in s.legal_actions()
    T.play(s, H.TAKE_LOAN)
    assert plan_ids(s.legal_actions()) == [PLAN(SAW, 1)]
    T.play(s, PLAN(SAW, 1))
    assert purse(s, 3) == (3, 2)


def test_R040_pw_entry_needs_money_plus_all_remaining_loans_to_cover_the_price():
    """R-040 item 4/R-088 final paragraph: with eight tokens on Sawing (the only plannable card
    for pair 1 in round 3) every seat has $2 and one loan left: $2 + $4 = $6 < $8, so Planned work
    is not enterable for any of them (no free card; money and loans both short), while the
    clearing stays available. Contrast: with seven tokens the same layout lets the seats in."""
    s, _ = round3_gate(False)
    assert saw_tokens(s) == 8
    for seat in range(4):
        goto_seat(s, seat)
        assert purse(s, seat) == (2, 1)
        legal = s.legal_actions()
        assert H.MOVE_TO(PW_LOC) not in legal, seat
        assert R.MOVE_CLEARING in legal
        T.goto_clearing(s)


def test_R040_pw_entry_flips_when_the_price_passes_money_plus_remaining_loans():
    """R-040 item 4/R-088 final paragraph: P3 in round 3 with seven tokens on Sawing is let in
    (money + remaining loans covers the price), while P3 in the sibling game with eight tokens
    (one more plan paid for, a loan used) is shut out: the gate follows money + remaining loans,
    not a fixed rule."""
    s7, _ = round3_gate(True)
    goto_seat(s7, 3)
    m7, l7 = purse(s7, 3)
    assert saw_tokens(s7) == 7 and m7 + 4 * (2 - l7) >= 7
    assert H.MOVE_TO(PW_LOC) in s7.legal_actions()
    s8, _ = round3_gate(False)
    goto_seat(s8, 3)
    m8, l8 = purse(s8, 3)
    assert saw_tokens(s8) == 8 and m8 + 4 * (2 - l8) < 8
    assert H.MOVE_TO(PW_LOC) not in s8.legal_actions()
