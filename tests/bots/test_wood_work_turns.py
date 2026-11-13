"""Phase 7 unit 5a: a seat's wood-work turn (W1..W7) is chance-free and single-seat.

Claim the own-turn solver relies on: from the moment a seat becomes current_player in a wood-work
phase until its turn ends (it plays DONE, or the phase/seat changes automatically), the
sub-decisions (a) contain no chance node and (b) all belong to that one seat. Uses only the
public state API and tests/harness.py.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

import pytest

from lignum.bots import HeuristicBot
from tests.harness import DONE, load_game, phase_of

WOOD_WORK = {f"W{i}" for i in range(1, 8)}
GAMES_PER_CONFIG = 20  # x 3 player counts x 2 joinery x 2 policies = 240 games


def run_game(
    players: int,
    joinery: bool,
    seed: int,
    heuristic: bool,
    turns: Counter[str],
    violations: list[dict[str, Any]],
) -> None:
    game = load_game(players=players, joinery=joinery)
    state = game.new_initial_state()
    chance_rng = random.Random(f"c{seed}")
    rngs = [random.Random(f"{seed}:{i}") for i in range(players)]
    bots = [HeuristicBot() for _ in range(players)]
    # Mixed policy: the heuristic seat set is random per game so random seats still wander.
    use_h = [heuristic and (i % 2 == 0 or seed % 3 != 0) for i in range(players)]

    seg: dict[str, Any] | None = None  # open turn segment
    chance_in_seg = False
    cur_phase = ""
    started: set[int] = set()

    def meta(extra: str) -> dict[str, Any]:
        return {
            "seed": seed,
            "players": players,
            "joinery": joinery,
            "heuristic": heuristic,
            "reason": extra,
            "phase": seg["phase"] if seg else None,
            "seat": seg["seat"] if seg else None,
            "history": [int(a) for a in state.history()],
        }

    while not state.is_terminal():
        if state.is_chance_node():
            if seg is not None:
                chance_in_seg = True
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(chance_rng.choices(acts, probs)[0])
            continue
        ph = phase_of(state)
        p = state.current_player()
        if ph != cur_phase:
            cur_phase, started = ph, set()
            seg = None
        if seg is not None and seg["seat"] == p and chance_in_seg:
            violations.append(meta("chance node inside turn"))
        if seg is not None and seg["seat"] != p:
            seg = None  # previous seat's turn ended automatically (e.g. empty river, R-049)
        if ph in WOOD_WORK and seg is None:
            if p in started:
                violations.append(meta(f"seat {p} has a second turn segment in {ph}"))
            started.add(p)
            seg = {"phase": ph, "seat": p}
            turns[ph] += 1
        chance_in_seg = False
        legal = state.legal_actions()
        a = bots[p].choose(state, rngs[p]) if use_h[p] else rngs[p].choice(legal)
        assert a in legal
        state.apply_action(a)
        if a == DONE:
            seg = None


@pytest.mark.slow
def test_wood_work_turns_are_chance_free_and_single_seat() -> None:
    turns: Counter[str] = Counter()
    violations: list[dict[str, Any]] = []
    games = 0
    for players in (2, 3, 4):
        for joinery in (False, True):
            for heuristic in (False, True):
                for k in range(GAMES_PER_CONFIG):
                    seed = 1000 * players + 100 * int(joinery) + 10 * int(heuristic) + k
                    run_game(players, joinery, seed, heuristic, turns, violations)
                    games += 1
    print(f"games={games} turns_per_phase={dict(sorted(turns.items()))}")
    assert all(turns[ph] > 0 for ph in WOOD_WORK), f"phases never reached: {turns}"
    shown = violations[:10]
    assert not violations, f"{len(violations)} violations, first: {shown}"
