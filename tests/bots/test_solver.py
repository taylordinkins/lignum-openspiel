"""Phase 7 unit 5b: the own-turn solver (lignum.bots.solver) and the heuristic-v6 seat."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from lignum import actions as A
from lignum.bots import HeuristicBot
from lignum.bots.base import bot_candidates
from lignum.bots.solver import WOOD_WORK_PHASES, solve_turn, turn_over
from lignum.bots.value import value
from lignum.bots.weights import load_profile
from lignum.game import LignumState
from tests.harness import load_game

PROFILE = "heuristic-v6"


def expand(s: LignumState) -> list[int]:
    acts = bot_candidates(s)
    return sorted(a for a in acts if A.decode(a).name not in ("BUILD_HUT",)) or sorted(acts)


def wood_work_states(players: int, seed: int, want: int) -> list[LignumState]:
    """First ``want`` wood-work decision states of a v6-vs-v4 game (own turns of seat 0)."""
    game = load_game(players=players, joinery=True)
    s = game.new_initial_state()
    assert isinstance(s, LignumState)
    cr = random.Random(f"c{seed}")
    bots = [HeuristicBot(profile=PROFILE)] + [HeuristicBot(profile="heuristic-v4")] * (players - 1)
    rngs = [random.Random(f"{seed}:{i}") for i in range(players)]
    out: list[LignumState] = []
    while not s.is_terminal() and len(out) < want:
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(cr.choices(acts, probs)[0])
            continue
        p = s.current_player()
        if p == 0 and s.phase in WOOD_WORK_PHASES and len(s.legal_actions()) > 1:
            out.append(s.clone())
        s.apply_action(bots[p].choose(s, rngs[p]))
    return out


def brute_best(
    s: LignumState, seat: int, score: Callable[[LignumState], float], budget: int = 20000
) -> float | None:
    key = (s.phase, s.w_turn)
    best = -1e18
    n = 0
    stack: list[tuple[LignumState, int]] = [(s, 0)]
    while stack:
        node, _ = stack.pop()
        for a in expand(node):
            n += 1
            if n > budget:
                return None
            c = node.clone()
            c.apply_action(a)
            if turn_over(c, a, seat, key):
                best = max(best, score(c))
            else:
                stack.append((c, 0))
    return best


def test_exhaustive_equals_brute_force() -> None:
    vw = load_profile(PROFILE)["value"]
    checked = 0
    for st in wood_work_states(2, 21, 60):
        score = lambda x: value(x, 0, vw)  # noqa: E731
        brute = brute_best(st, 0, score, budget=1500)
        if brute is None:
            continue
        plan = solve_turn(st, 0, expand, score, beam=10_000, node_cap=10**6, max_depth=50)
        assert plan is not None and plan.exhaustive
        assert plan.score == pytest.approx(brute)
        checked += 1
    assert checked >= 10


def test_plan_is_legal_deterministic_and_stays_in_turn() -> None:
    vw = load_profile(PROFILE)["value"]
    sv = load_profile(PROFILE)["solver"]
    for st in wood_work_states(3, 5, 40):
        key = (st.phase, st.w_turn)

        def score(x: LignumState) -> float:
            return value(x, 0, vw)

        args = (st, 0, expand, score, sv["beam"], sv["node_cap"], sv["max_depth"])
        p1, p2 = solve_turn(*args), solve_turn(*args)
        assert p1 == p2 and p1 is not None
        c = st.clone()
        for i, a in enumerate(p1.actions):
            assert a in c.legal_actions()
            c.apply_action(a)
            if i < len(p1.actions) - 1:  # only the last action may end the turn
                assert not turn_over(c, a, 0, key)


def test_node_cap_respected() -> None:
    vw = load_profile(PROFILE)["value"]
    for st in wood_work_states(2, 22, 30):
        plan = solve_turn(
            st, 0, expand, lambda x: value(x, 0, vw), beam=3, node_cap=25, max_depth=12
        )
        assert plan is None or (plan.nodes <= 25 and plan.actions)


def test_profile_and_v4_unchanged() -> None:
    assert load_profile("heuristic-v4").get("solver") is None
    sv = load_profile(PROFILE)["solver"]
    assert set(sv) == {"enabled", "beam", "node_cap", "max_depth", "phases"}
    v4 = {k: v for k, v in load_profile("heuristic-v4").items() if k != "solver"}
    v6 = {k: v for k, v in load_profile(PROFILE).items() if k != "solver"}
    assert v4 == v6


@pytest.mark.parametrize("players", [2, 3, 4])
def test_v6_plays_a_legal_game(players: int) -> None:
    game = load_game(players=players, joinery=True)
    s = game.new_initial_state()
    cr = random.Random("c9")
    bots = [HeuristicBot(profile=PROFILE) for _ in range(players)]
    rngs = [random.Random(f"9:{i}") for i in range(players)]
    while not s.is_terminal():
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(cr.choices(acts, probs)[0])
            continue
        p = s.current_player()
        a = bots[p].choose(s, rngs[p])
        assert a in s.legal_actions()
        s.apply_action(a)


def test_phases_key_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    import lignum.bots.heuristic as H
    from lignum.game import PHASE_W1, PHASE_W3, PHASE_W4, PHASE_W5, PHASE_W6, PHASE_W7

    assert set(load_profile(PROFILE)["solver"]["phases"]) == {"W1", "W2", "W3", "W4", "W6"}
    states = wood_work_states(2, 21, 80)  # generated before the spy is installed
    seen: set[int] = set()
    real = H.solve_turn

    def spy(state: LignumState, *a: object, **k: object):  # type: ignore[no-untyped-def]
        seen.add(state.phase)
        return real(state, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(H, "solve_turn", spy)

    def run(phases: list[str]) -> None:
        seen.clear()
        w = {
            **load_profile(PROFILE),
            "solver": {**load_profile(PROFILE)["solver"], "phases": phases},
        }
        bot = HeuristicBot(w)
        for st in states:
            bot.choose(st, random.Random(0))

    run(["W3"])
    assert seen == {PHASE_W3}
    run(["W1", "W4", "W6"])
    assert seen <= {PHASE_W1, PHASE_W4, PHASE_W6} and PHASE_W6 in seen
    run(["W5", "W7"])
    assert seen <= {PHASE_W5, PHASE_W7}


def test_not_exhaustive_when_frontier_left_unexpanded() -> None:
    vw = load_profile(PROFILE)["value"]

    def run(st: LignumState, depth: int, cap: int = 10**6):  # noqa: ANN202
        return solve_turn(
            st, 0, expand, lambda x: value(x, 0, vw), beam=10**6, node_cap=cap, max_depth=depth
        )

    seen = 0
    for st in wood_work_states(2, 22, 30):
        full = run(st, 12)
        if full is None or not full.exhaustive or len(full.actions) < 2:
            continue
        seen += 1
        assert not run(st, 1).exhaustive  # depth stop with live children left
        assert not run(st, 12, cap=1).exhaustive  # cap stop with an unexpanded frontier
    assert seen
