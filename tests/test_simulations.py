"""Random simulations over every parameter combination (PLAN.md section 6 items 2 and 3).

Each game runs through pyspiel's ``random_sim_test`` (with serialization) and through our own
random playout that runs the invariant checker after every action. Seeds are fixed.
"""

from __future__ import annotations

import numpy as np
import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum.invariants import assert_invariants, check_invariants
from tools.sim_common import COMBOS, Combo, combo_id, load

FAST_GAMES = 2  # per combination, per harness
SLOW_GAMES = 40


def playout_checked(game: pyspiel.Game, seed: int, probe_every: int = 0) -> pyspiel.State:
    rng = np.random.RandomState(seed)
    state = game.new_initial_state()
    assert_invariants(state)
    decisions = chances = 0
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(int(rng.choice(actions, p=probs)))
            chances += 1
        else:
            if probe_every and decisions % probe_every == 0:
                for action in state.legal_actions():  # every legal action applies on a clone
                    clone = state.clone()
                    clone.apply_action(action)
                    assert_invariants(clone)
            state.apply_action(int(rng.choice(state.legal_actions())))
            decisions += 1
        assert_invariants(state)
    assert decisions <= game.max_game_length()
    assert chances <= game.max_chance_nodes_in_history()
    assert len(state.history()) <= game.max_history_length()
    return state


def run_combo(c: Combo, games: int, probe_every: int = 0) -> None:
    game = load(c)
    pyspiel.random_sim_test(game, num_sims=games, serialize=True, verbose=False)
    for seed in range(games):
        state = playout_checked(game, 1000 * seed + c[0], probe_every)
        assert len(state.returns()) == c[0]  # sum to 0 is checked by the invariant checker


@pytest.mark.parametrize("combo", COMBOS, ids=combo_id)
def test_random_games_hold_invariants(combo: Combo) -> None:
    run_combo(combo, FAST_GAMES)


@pytest.mark.slow
@pytest.mark.parametrize("combo", COMBOS, ids=combo_id)
def test_random_games_hold_invariants_many(combo: Combo) -> None:
    run_combo(combo, SLOW_GAMES, probe_every=9)


def test_initial_state_is_consistent() -> None:
    for c in COMBOS:
        assert check_invariants(load(c).new_initial_state()) == []


def test_random_play_reaches_phase4_actions() -> None:
    """Planned work, huts, craftwork market, buildings and overtime all occur in random games."""
    from tools.sim_common import PHASE4_ACTIONS, action_counts

    rare = {"SELL_EQUIP", "HUT_DRY", "USE_PW_LOGDRIVING"}  # seen only in the larger sim_stats runs

    seen: set[str] = set()
    for c in COMBOS:
        if not c[1] or c[2] != "margin":
            continue
        game = load(c)
        for seed in range(15):
            seen |= set(action_counts(playout_checked(game, 77 + seed)))
    need = set(PHASE4_ACTIONS) - rare
    assert need <= seen, sorted(need - seen)
