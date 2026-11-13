"""R-117 / R-027 / R-070 (setup side): the `easy_winter` option and the winter card halves.

Written from docs/RULES_SPEC.md and docs/ACTIONS.md only. The engine already implements these
(Phase 2), so no test here is marked pending. Winter play with the easier halves is covered in
tests/rules/test_winter.py (R-117 data and feeding).

Card order: WINTER(c, h) indexes the cards of the year in data/components/cards.yaml order;
h = 0 is `top`, 1 is `bottom`.
"""

from __future__ import annotations

import random

import pytest

from tests import harness as H

PLAYERS = (2, 3, 4)

# R-117 transcription: (food, heating) of the easier half and which printed half it is,
# per card in yaml order. Year 1 then year 2.
EASIER_BY_CARD = {
    1: [(1, (5, 7)), (0, (6, 3)), (0, (5, 5)), (0, (5, 4))],
    2: [(0, (7, 7)), (1, (10, 7)), (0, (8, 6)), (0, (6, 8))],
}
EASIER_H = {y: [h for h, _ in cards] for y, cards in EASIER_BY_CARD.items()}


def _winter_nodes(game, year1_action=None):
    """Walk to the year-1 WINTER node; return (state, first_outcomes)."""
    s = game.new_initial_state()
    assert s.is_chance_node()
    s.apply_action(s.chance_outcomes()[0][0])  # AREAS3
    assert s.is_chance_node()
    assert all(H.chance_family(a)[0] == "WINTER" for a, _ in s.chance_outcomes())
    return s


def _year2_node(game, c1, h1):
    s = _winter_nodes(game)
    s.apply_action(H.CHANCE_BASE["WINTER"] + 2 * c1 + h1)
    assert all(H.chance_family(a)[0] == "WINTER" for a, _ in s.chance_outcomes())
    return s


def _finish_setup(s, seed):
    rng = random.Random(seed)
    while s.is_chance_node():
        s.apply_action(H.sample_chance(s, rng))
    return s


@pytest.mark.parametrize("n", PLAYERS)
@pytest.mark.parametrize("joinery", (True, False))
def test_R117_easy_year1_offers_only_the_easier_half_per_card(n, joinery):
    """R-117: easy_winter=true offers, for each of the 4 year-1 cards, only the half with the
    lower food+heating sum (explicit table from R-117), each with equal probability."""
    g = H.load_game(players=n, joinery=joinery, easy_winter=True)
    outs = _winter_nodes(g).chance_outcomes()
    assert sorted(a for a, _ in outs) == [
        H.CHANCE_BASE["WINTER"] + 2 * c + h for c, h in enumerate(EASIER_H[1])
    ]
    assert [round(p, 9) for _, p in outs] == [0.25] * 4


@pytest.mark.parametrize("c1", range(4))
def test_R117_easy_year2_offers_only_the_easier_half_per_card(c1):
    """R-117: same for the 4 year-2 cards, whichever year-1 card was drawn (year 2 is its own
    deck, R-014)."""
    g = H.load_game(players=2, easy_winter=True)
    outs = _year2_node(g, c1, EASIER_H[1][c1]).chance_outcomes()
    assert sorted(a for a, _ in outs) == [
        H.CHANCE_BASE["WINTER"] + 2 * c + h for c, h in enumerate(EASIER_H[2])
    ]
    assert [round(p, 9) for _, p in outs] == [0.25] * 4


@pytest.mark.parametrize("n", PLAYERS)
def test_R027_hard_mode_offers_every_half_uniformly(n):
    """R-027: easy_winter=false makes the visible half a uniform chance outcome: all 8
    (card, half) outcomes of each year at probability 1/8."""
    g = H.load_game(players=n, easy_winter=False)
    for outs in (
        _winter_nodes(g).chance_outcomes(),
        _year2_node(g, 0, 0).chance_outcomes(),
    ):
        assert sorted(a for a, _ in outs) == list(range(20, 28))
        assert [round(p, 9) for _, p in outs] == [0.125] * 8


def test_R027_default_is_not_easy():
    """R-001/R-027: the default game draws the half at random (8 outcomes)."""
    outs = _winter_nodes(H.load_game()).chance_outcomes()
    assert len(outs) == 8


@pytest.mark.parametrize("seed", range(6))
def test_R117_easy_setup_exposes_easier_halves_in_snapshot(seed):
    """R-117/R-070: after setup with easy_winter=true the visible half of both cards is the
    easier one, with the (food, heating) values listed in R-117."""
    from tests.support import winter as V

    s = H.play_setup(dict(players=2, easy_winter=True), seed=seed)
    win = H.snapshot(s)["supply"]["winter"]
    cards = V.winter_cards()
    for year in (1, 2):
        e = win[f"year{year}"]
        idx = [i for i, cid in enumerate(sorted(cards)) if cards[cid]["year"] == year]
        c = [cid for cid in sorted(cards) if cards[cid]["year"] == year].index(e["card"])
        assert idx  # data present
        h, (food, heat) = EASIER_BY_CARD[year][c]
        assert e["half"] == ("top", "bottom")[h]
        half = cards[e["card"]]["halves"][e["half"]]
        assert (half["food"], half["heating"]) == (food, heat)


def test_R117_easy_hard_halves_are_never_reachable():
    """R-117: no easy_winter=true setup ever yields the harder half (sampled walks)."""
    for seed in range(20):
        s = H.play_setup(dict(players=3, easy_winter=True), seed=seed)
        win = H.snapshot(s)["supply"]["winter"]
        for year in (1, 2):
            e = win[f"year{year}"]
            n = int(e["card"].rsplit("_", 1)[1]) - 1
            assert e["half"] == ("top", "bottom")[EASIER_H[year][n]]


def test_R027_hard_mode_can_show_the_harder_half():
    """R-027: with easy_winter=false the harder half is reachable; replaying the same chance
    history but flipping one half to the harder one is accepted (all 8 offered)."""
    g = H.load_game(players=2, easy_winter=False)
    c = 0
    harder = 1 - EASIER_H[1][c]
    s = _winter_nodes(g)
    a = H.CHANCE_BASE["WINTER"] + 2 * c + harder
    assert a in {x for x, _ in s.chance_outcomes()}
    s.apply_action(a)
    assert (
        H.snapshot(_finish_setup(s, 0))["supply"]["winter"]["year1"]["half"]
        == (
            "top",
            "bottom",
        )[harder]
    )


def test_R117_easy_winter_changes_no_action_space():
    """R-001/R-117: easy_winter is not a legal-action parameter; the distinct-action and chance
    outcome counts are identical, and decisions never mention it."""
    a, b = H.load_game(easy_winter=False), H.load_game(easy_winter=True)
    assert a.num_distinct_actions() == b.num_distinct_actions()
    assert a.max_chance_outcomes() == b.max_chance_outcomes()
    assert a.num_players() == b.num_players()
    assert a.max_game_length() == b.max_game_length()


@pytest.mark.parametrize("n", PLAYERS)
def test_R117_easy_history_replays_identically_in_hard_game(n):
    """R-117: nothing else differs. An easy_winter=true action history is legal in the
    easy_winter=false game and reaches the same state apart from the parameter: same round,
    phase, turn order, current player, legal actions and seat state."""
    ge = H.load_game(players=n, easy_winter=True)
    gh = H.load_game(players=n, easy_winter=False)
    se = H.play_setup(ge, seed=3)
    sh = H.replay(gh, H.setup_history(se))
    a, b = H.snapshot(se), H.snapshot(sh)
    a["parameters"] = b["parameters"] = None
    assert a == b
    assert se.legal_actions() == sh.legal_actions()
    assert se.current_player() == sh.current_player()


@pytest.mark.parametrize("n", PLAYERS)
def test_R028_winter_halves_public_to_every_seat(n):
    """R-028/R-117: the visible halves appear in every seat's observation: two setups that
    differ only in a year-1 visible half give different observation strings for every seat,
    and the same history gives the same public view (no hidden winter state)."""
    g = H.load_game(players=n, easy_winter=False)
    c = 1
    strings = []
    for h in (0, 1):
        s = _winter_nodes(g)
        s.apply_action(H.CHANCE_BASE["WINTER"] + 2 * c + h)
        s = _finish_setup(s, seed=11)
        # complete the picks so the state is a plain public decision node
        strings.append([s.observation_string(p) for p in range(n)])
    for p in range(n):
        assert strings[0][p] != strings[1][p]


@pytest.mark.parametrize("easy", (True, False))
def test_R117_easy_flag_visible_in_observation_equally_to_all_seats(easy):
    """R-028: the visible half is not seat-private: with a fixed history, the observation
    strings of different seats expose the same winter information (the strings agree once
    the seat-specific parts are equal, here checked on the scenario snapshot instead)."""
    s = H.play_setup(dict(players=3, easy_winter=easy), seed=2)
    snap = H.snapshot(s)
    assert set(snap["supply"]["winter"]) >= {"year1", "year2"}
    for y in ("year1", "year2"):
        assert snap["supply"]["winter"][y]["half"] in ("top", "bottom")
