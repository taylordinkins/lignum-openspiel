"""Phase 6 unit 3: lignum.bots.value (expected-dollars value function) and the bot base move."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pyspiel
import pytest

import lignum.game  # noqa: F401  (registers the game)
from lignum import actions as A
from lignum.bots import RandomBot, bot_candidates
from lignum.bots.value import value, value_diff
from lignum.components import load_components
from lignum.game import PHASE_FS, PHASE_N2, PHASE_N4, PHASE_PK, PHASE_W6, LignumState


def _game(players: int = 2) -> Any:
    return pyspiel.load_game(f"python_lignum(players={players})")


def _playout(players: int, seed: int, stop: Any = None) -> Any:
    """Random playout; yields each state (not copied) until terminal or ``stop(state)``."""
    rng = np.random.RandomState(seed)
    s = _game(players).new_initial_state()
    while not s.is_terminal():
        yield s
        if stop is not None and stop(s):
            return
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(int(rng.choice(acts, p=probs)))
        else:
            s.apply_action(int(rng.choice(bot_candidates(s))))
    yield s


def _until(players: int, seed: int, pred: Any) -> LignumState:
    for s in _playout(players, seed, stop=pred):
        if pred(s):
            return s.clone()
    raise AssertionError("predicate never reached")


def _set(s: LignumState, name: str, seat: int, new: Any) -> LignumState:
    c = s.clone()
    row = list(getattr(c, name))
    row[seat] = new
    setattr(c, name, tuple(row))
    return c


@pytest.fixture(scope="module")
def mid() -> LignumState:
    return _until(2, 3, lambda s: s.phase == PHASE_W6)


def test_base_bot_reexport_matches_server() -> None:
    import server.bots as sb

    assert sb.RandomBot is RandomBot and sb.bot_candidates is bot_candidates


def test_more_money_is_better(mid: LignumState) -> None:
    richer = _set(mid, "money", 0, mid.money[0] + 3)
    assert value(richer, 0) == pytest.approx(value(mid, 0) + 3)
    assert value_diff(richer, 0) > value_diff(mid, 0)


def test_sellable_wood_is_better(mid: LignumState) -> None:
    base = _set(mid, "sale_logs", 0, (0, 0, 0))
    base = _set(base, "sale", 0, (0, 0, 0))
    wood = _set(base, "sale_logs", 0, (0, 0, 1))  # one milled hardwood
    assert value(wood, 0) > value(base, 0)
    assert value(wood, 1) == value(base, 1)


def test_completed_task_beats_incomplete(mid: LignumState) -> None:
    s = _set(mid, "held_tasks", 0, (0,))
    n_req = len(load_components().tasks[0].requirements)
    empty, partial, done = s.clone(), s.clone(), s.clone()
    rest = (0,) * (len(s.filled) - 1)
    empty.filled = (0,) + rest
    partial.filled = (1,) + rest
    done.filled = ((1 << n_req) - 1,) + rest
    assert value(empty, 0) < value(partial, 0) < value(done, 0)


def test_loan_lowers_value(mid: LignumState) -> None:
    loaned = _set(mid, "loans", 0, 1)
    loaned = _set(loaned, "money", 0, mid.money[0] + 4)
    assert value(loaned, 0) < value(mid, 0)


def test_more_food_never_hurts(mid: LignumState) -> None:
    fed = _set(mid, "food", 0, mid.food[0] + 5)
    assert value(fed, 0) >= value(mid, 0)


@pytest.mark.parametrize("players", [2, 3, 4])
def test_last_decision_value_matches_final_dollars(players: int) -> None:
    """Value just before the last action approximates the real final dollars (D9 forgiveness
    and leftovers zeroed from the SF phase of the last winter), and terminal value is exact."""
    for seed in range(4):
        rng = np.random.RandomState(seed)
        s = _game(players).new_initial_state()
        prev = s
        while not s.is_terminal():
            if s.is_chance_node():
                acts, probs = zip(*s.chance_outcomes(), strict=True)
                s.apply_action(int(rng.choice(acts, p=probs)))
            else:
                prev = s.clone()
                s.apply_action(int(rng.choice(bot_candidates(s))))
        for p in range(players):
            assert value(s, p) == s.final[p]
            assert abs(value(prev, p) - s.final[p]) <= 3, (seed, p)


def test_final_sale_river_choice_ranks_like_final_dollars(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-081 step 2: after a seat sells one river kind the other is gone; value must show it."""
    orig = LignumState._begin_final_sale

    def patched(self: LignumState) -> None:
        self.river = tuple((1, 5, 0) for _ in range(self.n))  # 1 firewood, 5 softwood each
        orig(self)

    monkeypatch.setattr(LignumState, "_begin_final_sale", patched)
    s = _until(3, 1, lambda s: s.phase == PHASE_FS)
    seat = s.fs_pending[0]
    scored: list[tuple[float, float]] = []
    for a in s.legal_actions():
        if A.decode(a).name != "RIVER_SALE":
            continue
        c = s.clone()
        c.apply_action(a)
        scored.append((value(c, seat), _finish(c)[seat]))
    assert len(scored) == 2
    (v0, f0), (v1, f1) = scored
    assert f0 != f1
    assert (v0 > v1) == (f0 > f1) and v0 != v1


def _finish(s: LignumState) -> tuple[float, ...]:
    """Final dollars after the rest of the final sale (only river choices remain)."""
    s = s.clone()
    while not s.is_terminal():
        s.apply_action(s.legal_actions()[0])
    return tuple(float(x) for x in s.final)


def test_last_winter_leftovers_worth_nothing(mid: LignumState) -> None:
    t = mid._tables()  # pyright: ignore[reportPrivateUsage]
    s = mid.clone()
    s.round, s.phase = t.winter_rounds[1], PHASE_N4
    s.wint = tuple(range(s.n))
    s.woodpile = _set(s, "woodpile", 0, (0, 0, 3)).woodpile
    empty = s.clone()
    empty.woodpile = _set(s, "woodpile", 0, (0, 0, 0)).woodpile
    s.phase = PHASE_N4  # past N2: the woodpile is dead weight
    empty.phase = PHASE_N4
    assert value(s, 0) == value(empty, 0)
    s.phase = empty.phase = PHASE_N2  # the sledge can still move it to the sale area (R-067)
    assert value(s, 0) > value(empty, 0)


def test_no_hidden_pick_dependence() -> None:
    s = _until(3, 5, lambda s: s.phase == PHASE_PK and len(s.pk) == 0)
    seen: dict[int, set[float]] = {1: set(), 2: set()}
    for a in s.legal_actions():
        c = s.clone()
        c.apply_action(a)  # seat 0's hidden pick differs
        assert c.pk != s.pk
        for p in (1, 2):
            seen[p].add(value(c, p))
    assert all(len(v) == 1 for v in seen.values())
    # the picker's own value is also pick-independent here (picks are not valued)
    assert value(s, 1) == next(iter(seen[1]))


@pytest.mark.parametrize("players", [2, 3, 4])
def test_random_playouts_run(players: int) -> None:
    for seed in range(3):
        for s in _playout(players, seed):
            for p in range(s.num_players()):
                assert np.isfinite(value(s, p))
            assert np.isfinite(value_diff(s, 0))


def test_speed_note(capsys: pytest.CaptureFixture[str]) -> None:
    states = [s.clone() for i, s in enumerate(_playout(3, 2)) if i % 40 == 0]
    t0 = time.perf_counter()
    calls = 0
    for _ in range(5):
        for s in states:
            for p in range(3):
                value(s, p)
                calls += 1
    us = (time.perf_counter() - t0) / calls * 1e6
    print(f"value(): {us:.1f} us per call")
    assert us < 2000
