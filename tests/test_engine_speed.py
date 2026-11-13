"""Engine speed for search (Phase 6 unit 1): fast clone, cached tables, fast apply mode."""

import random
import time

import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)


def _game(players: int = 3):
    return pyspiel.load_game(f"python_lignum(players={players})")


def _step(state, rng: random.Random) -> None:
    if state.is_chance_node():
        state.apply_action(rng.choice(state.chance_outcomes())[0])
    else:
        state.apply_action(rng.choice(state.legal_actions()))


def test_clone_is_independent_after_apply() -> None:
    rng = random.Random(3)
    state = _game().new_initial_state()
    for _ in range(300):
        if state.is_terminal():
            break
        _step(state, rng)
        clone = state.clone()
        before = str(clone), clone.history()
        assert before == (str(state), state.history())
        if state.is_terminal():
            break
        _step(state, rng)
        assert (str(clone), clone.history()) == before
        assert clone.history() != state.history()
        assert clone.get_game() is not None
        # advancing the clone does not touch the original
        orig = str(state), state.history()
        if not clone.is_terminal():
            _step(clone, rng)
        assert (str(state), state.history()) == orig


@pytest.mark.parametrize("seed", range(4))
def test_fast_apply_matches_normal_mode(seed: int) -> None:
    game = _game(2 + seed % 3)
    rng = random.Random(seed)
    normal, fast = game.new_initial_state(), game.new_initial_state()
    fast.fast_apply = True
    assert not normal.fast_apply
    while not normal.is_terminal():
        if normal.is_chance_node():
            action = rng.choice(normal.chance_outcomes())[0]
        else:
            action = rng.choice(normal.legal_actions())
        normal.apply_action(action)
        fast.apply_action(action)
        assert str(normal) == str(fast)
    assert fast.is_terminal()
    assert normal.returns() == fast.returns()
    assert fast.clone().fast_apply
    assert fast.search_clone().fast_apply


def test_default_mode_still_validates() -> None:
    state = _game().new_initial_state()
    rng = random.Random(0)
    while state.is_chance_node():
        _step(state, rng)
    illegal = next(
        a for a in range(state.get_game().num_distinct_actions()) if a not in state.legal_actions()
    )
    with pytest.raises(Exception):  # noqa: B017
        state.apply_action(illegal)


@pytest.mark.parametrize("players", [2, 3, 4])
def test_clone_is_exact_copy(players: int) -> None:
    game = _game(players)
    rng = random.Random(players)
    state = game.new_initial_state()
    for _ in range(60):
        _step(state, rng)
    clone = state.clone()
    assert clone.history() == state.history()
    assert len(state.history()) == 60
    assert clone.move_number() == state.move_number() == 60
    assert [(pa.player, pa.action) for pa in clone.full_history()] == [
        (pa.player, pa.action) for pa in state.full_history()
    ]
    assert str(clone) == str(state)
    ser = pyspiel.serialize_game_and_state(game, state)
    assert pyspiel.serialize_game_and_state(game, clone) == ser
    _, restored = pyspiel.deserialize_game_and_state(ser)
    assert restored.history() == state.history()
    assert str(restored) == str(state)
    # apply-after-clone independence, both directions
    snap = (str(state), state.history())
    _step(clone, rng)
    assert (str(state), state.history()) == snap
    assert clone.move_number() == 61
    csnap = (str(clone), clone.history())
    _step(state, rng)
    assert (str(clone), clone.history()) == csnap


def test_clone_keeps_type_and_fast_apply() -> None:
    state = _game().new_initial_state()
    state.fast_apply = True
    assert type(state.clone()) is type(state)
    assert state.clone().fast_apply


@pytest.mark.parametrize("players", [2, 3, 4])
def test_search_clone_has_same_position_no_history(players: int) -> None:
    rng = random.Random(players)
    state = _game(players).new_initial_state()
    for _ in range(60):
        _step(state, rng)
    state.fast_apply = True
    sc = state.search_clone()
    assert str(sc) == str(state)
    assert sc.fast_apply
    assert sc.legal_actions() == state.legal_actions()
    _step(sc, rng)
    assert len(state.history()) == 60


def test_search_clone_is_much_faster_than_deepcopy() -> None:
    import copy

    rng = random.Random(1)
    state = _game().new_initial_state()
    for _ in range(200):
        _step(state, rng)
    n = 300
    t0 = time.perf_counter()
    for _ in range(n):
        state.search_clone()
    fast = time.perf_counter() - t0
    # Baseline: the old path was a deepcopy of __dict__ (~144 us); compare with a pure-Python
    # deepcopy of the same fields.
    t0 = time.perf_counter()
    for _ in range(n):
        copy.deepcopy(state.__dict__)
    slow = time.perf_counter() - t0
    assert slow / fast >= 5


def test_search_clone_much_faster_than_exact_clone() -> None:
    rng = random.Random(1)
    state = _game().new_initial_state()
    for _ in range(200):
        _step(state, rng)
    n = 300
    t0 = time.perf_counter()
    for _ in range(n):
        state.search_clone()
    fast = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(n):
        state.clone()
    exact = time.perf_counter() - t0
    assert exact / fast >= 5
