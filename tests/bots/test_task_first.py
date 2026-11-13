"""Task-first policy of heuristic-v3 (Phase 7 unit 1f, D38): gated by profile keys, drying
capacity in the schedule, feasibility valuation, hidden-pick needs."""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import Any

import pyspiel

import lignum.game  # noqa: F401  (registers the game)
from lignum.bots.heuristic import HeuristicBot
from lignum.bots.tasks import Assessment, TaskPlanner
from lignum.bots.value import value
from lignum.bots.weights import load_profile
from lignum.game import PHASE_W5


def _planner(w: Mapping[str, Any]) -> tuple[TaskPlanner, Any]:
    game = pyspiel.load_game("python_lignum(players=2)")
    state = game.new_initial_state()
    return TaskPlanner(state._tables(), w), state  # pyright: ignore[reportPrivateUsage]


def test_task_first_keys_only_in_v3() -> None:
    v3 = load_profile("heuristic-v3")
    assert v3["task_first"] == 1 and v3["value"]["task_first"] == 1
    for name in ("heuristic", "heuristic-v1", "heuristic-v2"):
        w = load_profile(name)
        assert "task_first" not in w and "task_first" not in w["value"]


def test_drying_one_holds_two_logs_pushes_a_third_to_a_later_round() -> None:
    planner, _ = _planner(load_profile("heuristic-v3")["value"])
    cohort: dict[int, int] = {}
    first = planner._fresh_ready(1, 1, cohort)  # pyright: ignore[reportPrivateUsage]
    assert first is not None
    for _ in range(2):
        planner._enter(cohort, 1, first)  # pyright: ignore[reportPrivateUsage]
    later = planner._fresh_ready(1, 1, cohort)  # pyright: ignore[reportPrivateUsage]
    assert later == first + 1
    # v2 (no cohort) ignores the capacity
    assert planner._fresh_ready(1, 1) == first  # pyright: ignore[reportPrivateUsage]


def test_stage_zero_needs_no_drying_slot() -> None:
    planner, _ = _planner(load_profile("heuristic-v3")["value"])
    cohort = {5: 2}
    planner._enter(cohort, 0, 5)  # pyright: ignore[reportPrivateUsage]
    assert cohort == {5: 2}
    assert planner._fresh_ready(0, 3, cohort) == 3  # pyright: ignore[reportPrivateUsage]


def test_worth_is_near_reward_when_feasible_and_zero_otherwise() -> None:
    w = load_profile("heuristic-v3")["value"]
    planner, _ = _planner(w)
    ok = Assessment(prob=0.9, net=0.0, feasible=True, cost=0.0)
    no = Assessment(prob=0.9, net=0.0, feasible=False, cost=0.0)
    assert 0.8 * 20 <= planner.worth(ok, 20) <= 20
    assert planner.worth(no, 20) == 0.0


def test_v3_plays_a_legal_game_with_finite_values() -> None:
    game = pyspiel.load_game("python_lignum(players=2)")
    bots = [HeuristicBot(profile="heuristic-v3"), HeuristicBot(profile="heuristic-v2")]
    rng = random.Random(5)
    state = game.new_initial_state()
    w5 = 0
    while not state.is_terminal():
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(acts, weights=probs)[0])
            continue
        seat = state.current_player()
        if state.phase == PHASE_W5:
            w5 += 1
            assert abs(value(state, seat, bots[0].vw)) < 1000
        action = bots[seat].choose(state.clone(), rng)
        assert action in state.legal_actions()
        state.apply_action(action)
    assert w5 > 0


def test_pick_needs_count_unfilled_slots_beyond_wood_in_hand() -> None:
    game = pyspiel.load_game("python_lignum(players=2)")
    bot = HeuristicBot(profile="heuristic-v3")
    state = game.new_initial_state()
    rng = random.Random(1)
    while state.is_chance_node():
        acts, probs = zip(*state.chance_outcomes(), strict=True)
        state.apply_action(rng.choices(acts, weights=probs)[0])
    seat = state.current_player()
    assert bot._wood_needs(state) == (0, 0, 0)  # pyright: ignore[reportPrivateUsage]
    state.held_tasks = (*state.held_tasks[:seat], (0,), *state.held_tasks[seat + 1 :])
    state.filled = (0,) * len(state.filled)
    # task 0 needs milled hardwood and milled firewood: one of each, none in hand
    assert bot._wood_needs(state) == (1, 0, 1)  # pyright: ignore[reportPrivateUsage]
