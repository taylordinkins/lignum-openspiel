"""Phase 6 unit 5: hidden-pick resampler for IS-MCTS (R-029, R-038; OPENSPIEL_NOTES IS-MCTS).

`resample(state, player, rng=None)` returns a clone in which only the cutting-area picks of
other seats made earlier in the current picking run (unrevealed, R-029) are redrawn. Everything
`player` can see is preserved, so the information-state string is unchanged.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

import lignum.game as lg
from tools.sim_common import load

PLAYERS = (2, 3, 4)


def resample(state, player, rng=None):
    """Lazy import so this file collects before the module exists."""
    from lignum.bots.resample import resample as impl

    return impl(state, player, rng)


PICK_ACTIONS = set(range(6))  # pk stores 0-based area indices (PICK_AREA(a) = 2 + a)


def _step(state, rng: np.random.RandomState) -> None:
    if state.is_chance_node():
        acts, probs = zip(*state.chance_outcomes(), strict=True)
        state.apply_action(int(rng.choice(acts, p=probs)))
    else:
        state.apply_action(int(rng.choice(state.legal_actions())))


def _walk(n: int, seed: int):
    game = load((n, True, "win_loss", False))
    rng = np.random.RandomState(seed)
    s = game.new_initial_state()
    while not s.is_terminal():
        yield s
        _step(s, rng)


def _mid_run(n: int, rnd: int, npicks: int, seed: int = 0):
    """Random play to round `rnd`'s picking run with `npicks` picks already made."""
    for s in _walk(n, seed):
        if (
            not s.is_chance_node()
            and s.phase == lg.PHASE_PK
            and s.round == rnd
            and len(s.pk) == npicks
        ):
            return s.clone()
    pytest.skip("state not reached")


def _is(s, p: int) -> str:
    return s.information_state_string(p)


CASES = [(n, rnd, k) for n in PLAYERS for rnd in (2, 5) for k in range(1, n)]
IDS = [f"p{n}-r{r}-k{k}" for n, r, k in CASES]


@pytest.mark.parametrize(("n", "rnd", "k"), CASES, ids=IDS)
def test_R029_sample_info_state_equals_root_for_player(n, rnd, k) -> None:
    """R-029: the sample is indistinguishable from the root for `player` (any seat)."""
    s = _mid_run(n, rnd, k)
    for p in range(n):
        for seed in range(5):
            smp = resample(s, p, random.Random(seed))
            assert _is(smp, p) == _is(s, p)
            assert smp.observation_string(p) == s.observation_string(p)
            assert smp.current_player() == s.current_player()
            assert sorted(smp.legal_actions()) == sorted(s.legal_actions())


@pytest.mark.parametrize(("n", "rnd", "k"), CASES, ids=IDS)
def test_R029_original_state_not_mutated(n, rnd, k) -> None:
    """The input state is untouched and the sample is a distinct object."""
    s = _mid_run(n, rnd, k)
    before = (str(s), s.history(), tuple(s.pk), [_is(s, p) for p in range(n)])
    for p in range(n):
        smp = resample(s, p, random.Random(p))
        assert smp is not s
        smp.apply_action(smp.legal_actions()[0])  # mutating the sample must not touch s either
    assert before == (str(s), s.history(), tuple(s.pk), [_is(s, p) for p in range(n)])


@pytest.mark.parametrize("n", PLAYERS)
def test_R029_other_seats_picks_are_redrawn_uniformly_over_areas(n) -> None:
    """R-038: any area may be chosen; the hidden picks are redrawn, covering several areas."""
    s = _mid_run(n, 2, n - 1)
    me = s.current_player()
    hidden = [j for j in range(len(s.pk)) if j != me]
    assert hidden
    seen: dict[int, set] = {j: set() for j in hidden}
    for seed in range(120):
        smp = resample(s, me, random.Random(seed))
        for j in hidden:
            assert smp.pk[j] in PICK_ACTIONS
            seen[j].add(smp.pk[j])
    for j in hidden:
        assert len(seen[j]) >= 3, (j, seen[j])  # varies; not stuck on the true pick


@pytest.mark.parametrize("n", PLAYERS)
def test_R029_draw_independent_of_true_hidden_picks(n) -> None:
    """No leak: with the same rng, states differing only in hidden picks give the same sample
    of the hidden part, and sampled picks do not favour the true pick."""
    s = _mid_run(n, 2, n - 1)
    me = s.current_player()
    hidden = [j for j in range(len(s.pk)) if j != me]
    # Build an alternative root that differs only in the hidden picks (indistinguishable to me).
    alt = s.clone()
    alt.pk = tuple((a + 1) % 6 if j in hidden else a for j, a in enumerate(s.pk))
    assert _is(alt, me) == _is(s, me)
    for seed in range(30):
        a = resample(s, me, random.Random(seed))
        b = resample(alt, me, random.Random(seed))
        assert tuple(a.pk) == tuple(b.pk)
        assert str(a) == str(b)
    # Frequency of the true pick is not inflated above the uniform 1/6 (loose bound).
    hits = sum(
        resample(s, me, random.Random(1000 + i)).pk[hidden[0]] == s.pk[hidden[0]]
        for i in range(300)
    )
    assert hits < 300 * 0.4


@pytest.mark.parametrize("n", PLAYERS)
def test_R029_fixed_rng_is_deterministic(n) -> None:
    """The same rng seed gives the same sample; rng=None is accepted."""
    s = _mid_run(n, 2, n - 1)
    me = s.current_player()
    a = resample(s, me, random.Random(7))
    b = resample(s, me, random.Random(7))
    assert str(a) == str(b) and tuple(a.pk) == tuple(b.pk)
    c = resample(s, me)
    assert _is(c, me) == _is(s, me)


@pytest.mark.parametrize(("n", "rnd", "k"), CASES, ids=IDS)
def test_R029_own_and_public_history_unchanged(n, rnd, k) -> None:
    """Only other seats' hidden picks change: own pick, revealed pick log, round and phase stay."""
    s = _mid_run(n, rnd, k)
    for p in range(n):
        smp = resample(s, p, random.Random(3))
        assert len(smp.pk) == len(s.pk)
        for j in range(len(s.pk)):
            if j == p:
                assert smp.pk[j] == s.pk[j]
        assert smp.pick_log == s.pick_log
        assert (smp.round, smp.phase) == (s.round, s.phase)
        # Seats with no pick yet (including later seats) stay unpicked.
        assert not smp.is_terminal() and not smp.is_chance_node()


def test_R029_player_with_own_pick_keeps_it_when_not_current() -> None:
    """Resampling for seat 0 (which has picked) keeps its pick; later seats' picks are redrawn."""
    s = _mid_run(4, 2, 3)
    own = s.pk[0]
    changed = set()
    for seed in range(60):
        smp = resample(s, 0, random.Random(seed))
        assert smp.pk[0] == own
        assert _is(smp, 0) == _is(s, 0)
        changed |= {j for j in (1, 2) if smp.pk[j] != s.pk[j]}
    assert changed == {1, 2}


@pytest.mark.parametrize("n", PLAYERS)
def test_R029_no_hidden_picks_returns_equivalent_state(n) -> None:
    """R-029: outside a picking run with prior picks (start of run, round 1, winter, other
    phases) nothing is hidden, so the sample equals the root."""
    seen_phases = set()
    checked = 0
    for s in _walk(n, 4):
        if s.is_chance_node():
            continue
        hidden_present = s.phase == lg.PHASE_PK and len(s.pk) > 0
        if hidden_present:
            continue
        key = (s.round, s.phase)
        if key in seen_phases:
            continue
        seen_phases.add(key)
        for p in range(n):
            smp = resample(s, p, random.Random(1))
            assert smp is not s
            assert str(smp) == str(s)
            assert _is(smp, p) == _is(s, p)
        checked += 1
    assert checked > 10
    assert any(r == 1 for r, _ in seen_phases)  # round 1 has no picks (R-038)


@pytest.mark.parametrize("n", PLAYERS)
def test_R029_winter_round_unchanged(n) -> None:
    """Winter rounds (4, 8) have no picks: resampling is the identity on the state."""
    for s in _walk(n, 6):
        if not s.is_chance_node() and s.round in (4, 8):
            for p in range(n):
                assert str(resample(s, p, random.Random(0))) == str(s)
            return
    pytest.skip("no winter reached")


@pytest.mark.parametrize("n", PLAYERS)
@pytest.mark.parametrize("rnd", (2, 5))
def test_R029_sample_is_legal_and_plays_to_the_end(n, rnd) -> None:
    """A sample is a legal state: random play from it reaches a terminal state."""
    s = _mid_run(n, rnd, n - 1)
    me = s.current_player()
    for seed in range(3):
        smp = resample(s, me, random.Random(seed))
        rng = np.random.RandomState(seed)
        steps = 0
        while not smp.is_terminal():
            la = smp.legal_actions() if not smp.is_chance_node() else None
            if la is not None:
                assert la
            _step(smp, rng)
            steps += 1
            assert steps < 100_000
        assert len(smp.returns()) == n


def test_R029_usable_as_ismcts_resampler_callback() -> None:
    """The function fits `bot.set_resampler(cb)`: cb(state, player) -> state with equal key."""
    s = _mid_run(3, 2, 2)
    me = s.current_player()
    cb = resample  # called as cb(state, player) with the rng defaulted
    assert _is(cb(s, me), me) == _is(s, me)
