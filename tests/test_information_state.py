"""Information state with perfect recall (PLAN.md D27, OPENSPIEL_NOTES hidden picks).

The recall observer adds a per-round log of earlier rounds' revealed picks; the observation
(perfect_recall=False) is unchanged. Hidden picks never leak into another seat's view.
"""

from __future__ import annotations

import numpy as np
import pyspiel
import pytest

import lignum.game as lg
from tools.sim_common import load

COMBOS = [(n, True, "win_loss", False) for n in (2, 3, 4)]


def _step(state: pyspiel.State, rng: np.random.RandomState) -> None:
    if state.is_chance_node():
        actions, probs = zip(*state.chance_outcomes(), strict=True)
        state.apply_action(int(rng.choice(actions, p=probs)))
    else:
        state.apply_action(int(rng.choice(state.legal_actions())))


def _to_pick_phase(game: pyspiel.Game, seed: int, min_log: int = 1) -> lg.LignumState:
    """Random play to the first hidden-pick node with at least ``min_log`` logged rounds."""
    rng = np.random.RandomState(seed)
    state = game.new_initial_state()
    while not state.is_terminal():
        assert isinstance(state, lg.LignumState)
        if (
            state.phase == lg.PHASE_PK
            and not state.pk
            and len(state.pick_log) >= min_log
            and not state.is_chance_node()
        ):
            return state
        _step(state, rng)
    pytest.skip("no pick phase reached")


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: f"p{c[0]}")
def test_past_picks_change_info_state_not_observation(combo) -> None:
    state = _to_pick_phase(load(combo), seed=1)
    other = state.clone()
    other.pick_log = (tuple((a + 1) % 5 for a in other.pick_log[0]),) + other.pick_log[1:]
    for seat in range(state.n):
        assert state.observation_string(seat) == other.observation_string(seat)
        assert state.observation_tensor(seat) == other.observation_tensor(seat)
        assert state.information_state_string(seat) != other.information_state_string(seat)
        assert state.information_state_tensor(seat) != other.information_state_tensor(seat)


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: f"p{c[0]}")
def test_hidden_pick_invariance(combo) -> None:
    state = _to_pick_phase(load(combo), seed=2)
    n = state.n
    # Enumerate every combination of the earlier seats' picks, then look from the last seat.
    leaves: list[lg.LignumState] = []

    def walk(s: lg.LignumState) -> None:
        if len(s.pk) == n - 1:
            leaves.append(s)
            return
        for a in s.legal_actions():
            c = s.clone()
            c.apply_action(a)
            walk(c)  # type: ignore[arg-type]

    walk(state)
    assert len(leaves) > 1
    last = n - 1
    assert {s.information_state_string(last) for s in leaves} == {
        leaves[0].information_state_string(last)
    }
    assert len({tuple(s.information_state_tensor(last)) for s in leaves}) == 1
    # The last seat's own pick changes its view.
    views = set()
    for a in leaves[0].legal_actions():
        c = leaves[0].clone()
        c.apply_action(a)
        views.add(c.information_state_string(last))
    assert len(views) > 1
    # Full-information strings still distinguish the hidden picks.
    assert len({str(s) for s in leaves}) == len(leaves)
    # Other seats do see their own picks only.
    for seat in range(last):
        assert len({s.information_state_string(seat) for s in leaves}) > 1 or n == 2


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: f"p{c[0]}")
def test_info_state_stable_under_clone(combo) -> None:
    game = load(combo)
    rng = np.random.RandomState(3)
    state = game.new_initial_state()
    while not state.is_terminal():
        c = state.clone()
        for seat in range(state.n):
            assert c.information_state_string(seat) == state.information_state_string(seat)
            assert c.information_state_tensor(seat) == state.information_state_tensor(seat)
        _step(state, rng)


@pytest.mark.parametrize("combo", COMBOS, ids=lambda c: f"p{c[0]}")
def test_log_holds_revealed_picks(combo) -> None:
    game = load(combo)
    rng = np.random.RandomState(4)
    state = game.new_initial_state()
    assert isinstance(state, lg.LignumState)
    reveals = 0
    while not state.is_terminal():
        before = len(state.pick_log)
        old = state.picks
        _step(state, rng)
        if len(state.pick_log) > before:
            reveals += 1
            assert state.pick_log[-1] == old
            for seat in range(state.n):
                text = state.information_state_string(seat)
                assert "log " + ";".join(",".join(map(str, r)) for r in state.pick_log) in text
                assert "log " not in state.observation_string(seat)
    assert reveals >= 1
